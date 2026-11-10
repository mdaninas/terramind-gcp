"""Strict smoke and diagnostic regressions using local provider/HTTP doubles only."""

import copy
import io
import json
import sys
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import urlsplit

import jsonschema
import pytest
from fastapi.testclient import TestClient

from scripts import demo_cloud
from terramind.api.app import create_app, demo_plan
from terramind.api.service import AnalysisService, ApiSettings, cloud_analysis
from terramind.cloud import google
from terramind.cloud.budget import CallBudget, DependencyUnavailable
from terramind.cloud.google import generation_schema
from terramind.cloud.settings import CloudSettings
from terramind.llm.diagnostics import LIMITATIONS, AdvisoryReason
from terramind.llm.service import explain
from terramind.policies.samples import hardening_sample
from terramind.reports.render import build_report
from terramind.reports.store import MemoryReportStore
from tests.knowledge_helpers import RecordingSynthesizer, local_system


@pytest.fixture
def local_http(monkeypatch):
    _, _, _, retriever = local_system()
    analyzed = []
    fallback = []

    def analyze(plan):
        analyzed.append(plan.policy_packs)
        model = RecordingSynthesizer()
        if any(pack in plan.policy_packs for pack in fallback):
            model.generate = lambda _: (_ for _ in ()).throw(TimeoutError("private-canary"))
        report = explain(plan, retriever, model)
        if "source_provenance" in fallback:
            source = report.advisory.sources[0].model_copy(update={"content_hash": "0" * 64})
            advisory = report.advisory.model_copy(
                update={"sources": (source, *report.advisory.sources[1:])}
            )
            report = report.model_copy(update={"advisory": advisory})
        if "advisory_coverage" in fallback:
            explanation = report.advisory.explanations[0].model_copy(
                update={"finding_id": "TM-GCP-001:google_storage_bucket.resource_9999"}
            )
            advisory = report.advisory.model_copy(
                update={"explanations": (explanation, *report.advisory.explanations[1:])}
            )
            report = report.model_copy(update={"advisory": advisory})
        return report

    client = TestClient(
        create_app(AnalysisService(ApiSettings(), MemoryReportStore(), analyze)),
        follow_redirects=False,
    )

    class Response(io.BytesIO):
        pass

    def open_request(request, timeout):
        path = urlsplit(request.full_url).path
        response = client.request(
            request.get_method(), path, content=request.data, headers=dict(request.header_items())
        )
        if response.status_code >= 400:
            raise HTTPError(request.full_url, response.status_code, "private-canary", {}, None)
        body = Response(response.content)
        body.status = response.status_code
        return body

    monkeypatch.setattr(
        demo_cloud, "build_opener", lambda *args: SimpleNamespace(open=open_request)
    )
    with client:
        yield analyzed, fallback


def test_strict_three_scenarios_verify_findings_sources_and_exports(local_http):
    analyzed, _ = local_http
    results = [
        demo_cloud.run(
            "http://127.0.0.1:8080", local=True, require_advisory=True, scenario=scenario
        )
        for scenario in demo_cloud.SCENARIOS
    ]
    assert [r["finding_count"] for r in results] == [4, 2, 2]
    assert all(r["status"] == "passed" and r["advisory_present"] for r in results)
    assert all(r["report_round_trip_verified"] and r["markdown_and_page_verified"] for r in results)
    assert len(analyzed) == 3


def test_cli_keeps_failed_pack_evidence_and_never_retries(
    local_http, monkeypatch, tmp_path, capsys
):
    analyzed, fallback = local_http
    fallback.append("storage-hardening")
    output = tmp_path / "summary.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "demo_cloud",
            "--url",
            "http://127.0.0.1:8080",
            "--local",
            "--require-advisory",
            "--all-scenarios",
            "--output",
            str(output),
        ],
    )
    assert demo_cloud.main() == 1
    summary = json.loads(output.read_text())
    assert summary["status"] == "failed" and len(summary["results"]) == 3
    assert summary["analysis_submissions"] == summary["analysis_submission_limit"] == 3
    assert len(analyzed) == 3
    failure = summary["results"][1]
    assert failure["stage"] == "advisory" and failure["advisory_failure"] == "provider_timeout"
    assert failure["finding_count"] == 2 and failure["findings_preserved"]
    assert failure["report_round_trip_verified"] and failure["markdown_and_page_verified"]
    assert summary["results"][2]["status"] == "passed"
    assert "private-canary" not in output.read_text() + capsys.readouterr().out


def test_configuration_failure_never_discloses_the_url_or_token(monkeypatch, tmp_path, capsys):
    output = tmp_path / "failure.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "demo_cloud",
            "--url",
            "https://private-canary.invalid",
            "--require-advisory",
            "--output",
            str(output),
        ],
    )
    monkeypatch.setenv("TERRAMIND_ID_TOKEN", "private-token-canary")
    assert demo_cloud.main() == 1
    result = json.loads(output.read_text())
    assert result["stage"] == "configuration" and not result["analysis_submitted"]
    text = output.read_text() + capsys.readouterr().out
    assert "private-canary" not in text and "private-token-canary" not in text


@pytest.mark.parametrize("sample", demo_cloud.SCENARIOS)
def test_provider_schema_constrains_pack_finding_and_citation_identifiers(sample):
    _, _, _, retriever = local_system()
    model = RecordingSynthesizer()
    plan = demo_plan() if sample == "risk-demo" else hardening_sample(sample)
    report = explain(plan, retriever, model)
    assert report.advisory is not None
    prompt = model.prompts[0]
    schema = generation_schema(prompt)
    narrative = json.loads(model.generate(prompt))
    jsonschema.validate(narrative, schema)
    explanations = schema["properties"]["explanations"]
    assert explanations["minItems"] == explanations["maxItems"] == len(report.findings)
    broken = copy.deepcopy(narrative)
    broken["explanations"][0]["finding_id"] = "TM-GCP-001:google_storage_bucket.resource_9999"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(broken, schema)
    broken = copy.deepcopy(narrative)
    broken["explanations"][0]["citation_ids"] = ["synthetic-unknown-source"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(broken, schema)


@pytest.mark.parametrize("fault", ["source_provenance", "advisory_coverage"])
def test_strict_smoke_rejects_tampered_sources_and_finding_coverage(local_http, fault):
    analyzed, faults = local_http
    faults.append(fault)
    with pytest.raises(demo_cloud.VerificationFailure) as error:
        demo_cloud.run("http://127.0.0.1:8080", local=True, require_advisory=True)
    assert error.value.summary["stage"] == fault
    assert error.value.summary["findings_preserved"] and len(analyzed) == 1


@pytest.mark.parametrize("reason", [AdvisoryReason.DEADLINE, AdvisoryReason.INCOMPLETE])
def test_classified_generation_failures_keep_findings_and_safe_limitations(reason):
    _, _, _, retriever = local_system()

    class Model:
        model_id = "synthetic-model"

        def generate(self, prompt):
            raise DependencyUnavailable("private-provider-canary", reason=reason)

    observed = []
    plan = hardening_sample("storage-hardening")
    report = explain(plan, retriever, Model(), observe=observed.append)
    assert report.findings == build_report(plan).findings and report.advisory is None
    assert observed == [reason] and LIMITATIONS[reason] in report.limitations
    assert "private-provider-canary" not in report.model_dump_json()


def test_validation_and_coverage_failures_have_distinct_outcomes():
    _, _, _, retriever = local_system()
    for transform, expected in [
        (lambda _: "{broken", AdvisoryReason.RESPONSE_CONTRACT),
        (lambda v: dict(v, explanations=v["explanations"] * 2), AdvisoryReason.FINDING_COVERAGE),
    ]:
        observed = []
        report = explain(
            demo_plan(), retriever, RecordingSynthesizer(transform), observe=observed.append
        )
        assert observed == [expected] and LIMITATIONS[expected] in report.limitations


def test_budget_preserves_timeout_and_deadline_classification(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("terramind.cloud.budget.time.monotonic", lambda: clock[0])
    budget = CallBudget(seconds=2)
    with pytest.raises(DependencyUnavailable) as error:
        budget.run(
            lambda _: (_ for _ in ()).throw(TimeoutError("private-canary")),
            transient=lambda _: False,
        )
    assert error.value.reason == AdvisoryReason.TIMEOUT
    clock[0] = 3.0
    with pytest.raises(DependencyUnavailable) as error:
        budget.run(lambda _: None, transient=lambda _: False)
    assert error.value.reason == AdvisoryReason.DEADLINE


@pytest.mark.parametrize(
    "status,reason",
    [
        (400, AdvisoryReason.REJECTED),
        (429, AdvisoryReason.RATE_LIMIT),
        (504, AdvisoryReason.TIMEOUT),
    ],
)
def test_provider_status_classification_never_exposes_error_content(status, reason):
    class ProviderError(Exception):
        code = status

    with pytest.raises(DependencyUnavailable) as error:
        CallBudget().run(
            lambda _: (_ for _ in ()).throw(ProviderError("private-canary")),
            transient=lambda _: False,
        )
    assert error.value.reason == reason and "private-canary" not in str(error.value)


def test_cloud_diagnostics_contain_only_fixed_outcomes_and_counts(monkeypatch, caplog):
    from unittest.mock import Mock

    _, embedder, store, _ = local_system()
    model = RecordingSynthesizer(lambda _: "private-provider-canary")
    for adapter in (embedder, store, model):
        adapter.client = Mock()
    monkeypatch.setattr(google, "GoogleEmbedder", lambda *args: embedder)
    monkeypatch.setattr(google, "FirestoreKnowledgeStore", lambda *args: store)
    monkeypatch.setattr(google, "GeminiSynthesizer", lambda *args: model)
    report = cloud_analysis(demo_plan(), CloudSettings(project_id="synthetic-project"))
    assert report.advisory is None
    records = [json.loads(r.message) for r in caplog.records if '"advisory_outcome"' in r.message]
    assert len(records) == 1
    assert records[0]["reason"] == "response_contract"
    assert set(records[0]) == {"event", "reason", "finding_count", "physical_calls", "duration_ms"}
    assert "private-provider-canary" not in caplog.text + report.model_dump_json()
