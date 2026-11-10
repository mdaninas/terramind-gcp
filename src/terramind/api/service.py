"""Application composition with explicit cloud opt-in and per-process admission limits."""

import json
import logging
import os
import time
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Literal

from terramind.cloud.budget import CallBudget, DependencyUnavailable
from terramind.cloud.settings import CloudSettings
from terramind.llm.diagnostics import LIMITATIONS, AdvisoryReason, AdvisoryUnavailable
from terramind.llm.service import explain, policy_fallback
from terramind.reports.render import build_report
from terramind.reports.store import MemoryReportStore, ReportStore, StoredAnalysis
from terramind.schemas.normalized import NormalizedPlan
from terramind.schemas.report import Report


@dataclass(frozen=True)
class ApiSettings:
    mode: Literal["offline", "cloud"] = "offline"
    retention_hours: int = 24
    requests_per_minute: int = 6

    def __post_init__(self) -> None:
        if self.mode not in {"offline", "cloud"}:
            raise ValueError("API mode must be offline or cloud")
        if not 1 <= self.retention_hours <= 24 or not 1 <= self.requests_per_minute <= 30:
            raise ValueError("API limits are outside the supported range")

    @classmethod
    def from_env(cls) -> "ApiSettings":
        mode = os.environ.get("TERRAMIND_API_MODE", "offline")
        if mode not in {"offline", "cloud"}:
            raise ValueError("API mode must be offline or cloud")
        return cls(
            mode="cloud" if mode == "cloud" else "offline",
            retention_hours=int(os.environ.get("REPORT_RETENTION_HOURS", "24")),
            requests_per_minute=int(os.environ.get("ANALYSES_PER_MINUTE", "6")),
        )


class Throttled(RuntimeError):
    """The process-local analysis admission limit was reached."""


class AdmissionGate:
    def __init__(self, per_minute: int):
        self.limit = per_minute
        self.recent: deque[float] = deque()
        self.busy = False
        self.lock = Lock()

    @contextmanager
    def enter(self) -> Iterator[None]:
        with self.lock:
            now = time.monotonic()
            while self.recent and self.recent[0] <= now - 60:
                self.recent.popleft()
            if self.busy or len(self.recent) >= self.limit:
                raise Throttled("Analysis limit reached")
            self.busy = True
            self.recent.append(now)
        try:
            yield
        finally:
            with self.lock:
                self.busy = False


def cloud_analysis(plan: NormalizedPlan, settings: CloudSettings) -> Report:
    base = build_report(plan)
    if not base.findings or len(base.findings) > 12:
        return (
            base
            if not base.findings
            else policy_fallback(
                base, "not_requested", "Advisory finding limit exceeded; review all findings."
            )
        )
    embedder = None
    synthesizer = None
    knowledge = None
    budget: CallBudget | None = None
    started = time.monotonic()

    def observe(reason: AdvisoryReason) -> None:
        logging.getLogger("terramind.api").info(
            json.dumps(
                {
                    "event": "advisory_outcome",
                    "reason": reason.value,
                    "finding_count": len(base.findings),
                    "physical_calls": budget.calls if budget is not None else 0,
                    "duration_ms": round((time.monotonic() - started) * 1000, 3),
                }
            )
        )

    try:
        from terramind.cloud.google import (
            FirestoreKnowledgeStore,
            GeminiSynthesizer,
            GoogleEmbedder,
        )
        from terramind.rag.retrieval import Retriever

        budget = CallBudget(seconds=23, max_calls=20, per_call=20)
        embedder = GoogleEmbedder(settings, budget)
        knowledge = FirestoreKnowledgeStore(settings, budget)
        synthesizer = GeminiSynthesizer(settings, budget)
        return explain(
            plan,
            Retriever(embedder, knowledge),
            synthesizer,
            language=settings.language,
            observe=observe,
        )
    except Exception as error:
        reason = (
            error.reason if isinstance(error, AdvisoryUnavailable) else AdvisoryReason.DEPENDENCY
        )
        observe(reason)
        return policy_fallback(base, "unavailable", LIMITATIONS[reason])
    finally:
        for client in (
            embedder.client if embedder else None,
            synthesizer.client if synthesizer else None,
            knowledge.client if knowledge else None,
        ):
            if client:
                with suppress(Exception):
                    client.close()


class AnalysisService:
    def __init__(
        self,
        settings: ApiSettings,
        store: ReportStore,
        analyze: Callable[[NormalizedPlan], Report] = build_report,
    ):
        self.settings, self.store, self.analyze = settings, store, analyze
        self.gate = AdmissionGate(settings.requests_per_minute)

    def create(self, plan: NormalizedPlan) -> Report:
        if plan.source != "synthetic-demo":
            raise ValueError("Only synthetic-demo requests are permitted")
        with self.gate.enter():
            report = self.analyze(plan)
            record = StoredAnalysis(
                analysis_id=report.analysis_id,
                report_json=report.model_dump_json(),
                expires_at=datetime.now(UTC) + timedelta(hours=self.settings.retention_hours),
            )
            self.store.save(record)
            return report

    def get(self, analysis_id: str) -> Report | None:
        record = self.store.get(analysis_id)
        return record.report if record and record.expires_at > datetime.now(UTC) else None


def default_service(settings: ApiSettings) -> AnalysisService:
    if settings.mode == "offline":
        return AnalysisService(settings, MemoryReportStore())
    cloud = CloudSettings.from_env()

    # ADC and SDK imports are deferred until an analysis/report request, keeping
    # liveness independent of provider availability and the offline extra small.
    class LazyStore:
        @contextmanager
        def connection(self) -> Iterator[ReportStore]:
            try:
                from terramind.cloud.reports import FirestoreReportStore

                store = FirestoreReportStore(cloud)
            except Exception:
                raise DependencyUnavailable("Report storage unavailable") from None
            try:
                yield store
            finally:
                with suppress(Exception):
                    store.client.close()

        def save(self, record: StoredAnalysis) -> None:
            with self.connection() as store:
                store.save(record)

        def get(self, analysis_id: str) -> StoredAnalysis | None:
            with self.connection() as store:
                return store.get(analysis_id)

    return AnalysisService(settings, LazyStore(), lambda plan: cloud_analysis(plan, cloud))
