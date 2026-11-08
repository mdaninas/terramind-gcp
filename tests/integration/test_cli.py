import json
import subprocess
import sys

import pytest

from terramind.cli import main


def test_cli_normalize_and_analyze(tmp_path, terraform_plan, encode):
    raw_path = tmp_path / "input.json"
    normalized_path = tmp_path / "normalized.json"
    report_path = tmp_path / "report.json"
    raw_path.write_bytes(encode(terraform_plan()))
    assert main(["normalize", "--input", str(raw_path), "--output", str(normalized_path)]) == 0
    assert main(["analyze", "--input", str(normalized_path), "--output", str(report_path)]) == 0
    report = json.loads(report_path.read_text())
    assert report["overall_risk"] == "HIGH"
    assert report["findings"][0]["rule_id"] == "TM-GCP-001"
    assert (
        main(
            [
                "analyze",
                "--input",
                str(normalized_path),
                "--output",
                str(report_path),
                "--format",
                "markdown",
            ]
        )
        == 0
    )
    assert "TM-GCP-001" in report_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("command", ["normalize", "analyze"])
def test_errors_dont_leak_input(tmp_path, capsys, command):
    path = tmp_path / "canary-private-filename.json"
    path.write_text('{"password":"synthetic-private-canary",', encoding="utf-8")
    assert main([command, "--input", str(path), "--output", str(tmp_path / "out")]) == 2
    output = capsys.readouterr()
    assert "Invalid JSON" in output.err
    assert "canary" not in output.err
    assert not output.out


def test_cli_preserves_input_and_handles_write_errors(tmp_path, fixture_dir, capsys):
    path = fixture_dir / "no_changes.json"
    original = path.read_bytes()
    assert main(["analyze", "--input", str(path), "--output", str(path)]) == 2
    assert path.read_bytes() == original
    assert main(["analyze", "--input", str(path), "--output", str(tmp_path)]) == 2
    assert "Unable to write output" in capsys.readouterr().err


def test_installed_entrypoint_and_demo():
    help_result = subprocess.run(
        [sys.executable, "-m", "terramind.cli", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "normalize" in help_result.stdout
    result = subprocess.run(
        [sys.executable, "scripts/demo_offline.py"], capture_output=True, text=True, check=True
    )
    assert "HIGH: 4 deterministic findings" in result.stdout
