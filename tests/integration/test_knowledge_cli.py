import json
import socket

from terramind.knowledge_cli import main
from terramind.schemas.report import Report


def test_local_corpus_plan_makes_no_network_calls(monkeypatch, capsys):
    def denied(*args, **kwargs):
        raise AssertionError("Local plan must not make network calls")

    monkeypatch.setattr(socket, "create_connection", denied)
    assert main(["plan"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "mode": "local-corpus-plan",
        "documents": 12,
        "chunks": 12,
        "cloud_calls": 0,
    }


def test_cloud_commands_require_explicit_execution_and_safe_input(tmp_path, fixture_dir, capsys):
    assert main(["ingest"]) == 2
    assert (
        main(
            [
                "analyze",
                "--input",
                str(fixture_dir / "public_bucket.json"),
                "--output",
                str(tmp_path / "report.json"),
            ]
        )
        == 2
    )
    value = json.loads((fixture_dir / "public_bucket.json").read_bytes())
    value["source"] = "local-normalizer"
    path = tmp_path / "local.json"
    path.write_text(json.dumps(value))
    assert (
        main(
            [
                "analyze",
                "--execute",
                "--input",
                str(path),
                "--output",
                str(tmp_path / "report.json"),
            ]
        )
        == 2
    )
    assert not (tmp_path / "report.json").exists()
    assert "Traceback" not in capsys.readouterr().err


def test_missing_credentials_still_write_deterministic_fallback(
    monkeypatch, tmp_path, fixture_dir, capsys
):
    monkeypatch.setenv("GCP_PROJECT_ID", "terramind-synthetic-example")

    def unavailable(*args, **kwargs):
        raise RuntimeError("synthetic-private-credential-canary")

    monkeypatch.setattr("terramind.cloud.google.GoogleEmbedder", unavailable)
    output = tmp_path / "fallback.json"
    assert (
        main(
            [
                "analyze",
                "--execute",
                "--input",
                str(fixture_dir / "public_bucket.json"),
                "--output",
                str(output),
            ]
        )
        == 1
    )
    report = Report.model_validate_json(output.read_bytes())
    assert report.overall_risk == "HIGH" and len(report.findings) == 1
    assert report.advisory is None and report.rag_status == "unavailable"
    captured = capsys.readouterr()
    assert (
        "synthetic-private-credential-canary"
        not in captured.out + captured.err + output.read_text()
    )


def test_empty_cloud_analysis_skips_credential_discovery(monkeypatch, tmp_path, fixture_dir):
    monkeypatch.setenv("GCP_PROJECT_ID", "terramind-synthetic-example")

    def forbidden(*args, **kwargs):
        raise AssertionError("No cloud adapter should initialize for an empty finding set")

    monkeypatch.setattr("terramind.cloud.google.GoogleEmbedder", forbidden)
    assert (
        main(
            [
                "analyze",
                "--execute",
                "--input",
                str(fixture_dir / "no_changes.json"),
                "--output",
                str(tmp_path / "empty.json"),
            ]
        )
        == 0
    )
