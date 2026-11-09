"""Expiring synthetic reports behind a small persistence boundary."""

import re
from datetime import UTC, datetime
from threading import Lock
from typing import Annotated, Literal, Protocol

from pydantic import AwareDatetime, Field, model_validator

from terramind.cloud.budget import DependencyUnavailable
from terramind.schemas.normalized import ClosedModel
from terramind.schemas.report import Report

MAX_REPORT_BYTES = 512 * 1024
ANALYSIS_ID = r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"


def valid_id(value: str) -> bool:
    return re.fullmatch(ANALYSIS_ID, value) is not None


class StoredAnalysis(ClosedModel):
    analysis_id: Annotated[str, Field(pattern=f"^{ANALYSIS_ID}$")]
    source: Literal["synthetic-demo"] = "synthetic-demo"
    report_json: str = Field(max_length=MAX_REPORT_BYTES)
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def consistent(self) -> "StoredAnalysis":
        if len(self.report_json.encode()) > MAX_REPORT_BYTES:
            raise ValueError("Report exceeds its storage limit")
        if self.report.analysis_id != self.analysis_id:
            raise ValueError("Stored report identity mismatch")
        return self

    @property
    def report(self) -> Report:
        return Report.model_validate_json(self.report_json)


class ReportStore(Protocol):
    def save(self, record: StoredAnalysis) -> None: ...

    def get(self, analysis_id: str) -> StoredAnalysis | None: ...


class MemoryReportStore:
    """Bounded, process-local development storage; restart discards reports."""

    def __init__(self, capacity: int = 128):
        self.records: dict[str, StoredAnalysis] = {}
        self.capacity = capacity
        self.lock = Lock()

    def save(self, record: StoredAnalysis) -> None:
        with self.lock:
            now = datetime.now(UTC)
            self.records = {
                key: item for key, item in self.records.items() if item.expires_at > now
            }
            if record.analysis_id in self.records or len(self.records) >= self.capacity:
                raise DependencyUnavailable("Report storage unavailable")
            self.records[record.analysis_id] = record

    def get(self, analysis_id: str) -> StoredAnalysis | None:
        if not valid_id(analysis_id):
            return None
        with self.lock:
            record = self.records.get(analysis_id)
            if record and record.expires_at <= datetime.now(UTC):
                del self.records[analysis_id]
                return None
            return record
