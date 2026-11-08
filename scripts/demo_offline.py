"""Run the credential-free synthetic demo; never read a user's raw plan."""

from pathlib import Path

from terramind.normalizer.io import load_normalized
from terramind.reports.render import build_report, markdown
from terramind.schemas.normalized import NormalizedPlan, serialize_plan


def main() -> None:
    names = ("public_bucket", "ssh_open_world", "project_owner_grant", "bucket_delete")
    changes = tuple(
        change
        for name in names
        for change in load_normalized(
            (Path("examples/normalized-plans") / f"{name}.json").read_bytes()
        ).changes
    )
    plan = NormalizedPlan(schema_version="1.0", source="synthetic-demo", changes=changes)
    report = build_report(plan)
    directory = Path("artifacts")
    directory.mkdir(exist_ok=True)
    (directory / "demo.normalized.json").write_text(serialize_plan(plan) + "\n", encoding="utf-8")
    (directory / "demo-report.json").write_text(
        report.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (directory / "demo-report.md").write_text(markdown(report), encoding="utf-8")
    print(f"{report.overall_risk}: {len(report.findings)} deterministic findings")
    print("Reports: artifacts/demo-report.json and artifacts/demo-report.md")


if __name__ == "__main__":
    main()
