import time

from terramind.normalizer.plan import normalize
from terramind.reports.render import build_report


def test_100_changes_under_two_seconds(terraform_plan, encode):
    raw = terraform_plan()
    template = raw["resource_changes"][0]
    raw["resource_changes"] = [
        dict(template, address=f"synthetic.resource_{i}") for i in range(100)
    ]
    data = encode(raw)
    start = time.perf_counter()
    report = build_report(normalize(data))
    elapsed = time.perf_counter() - start
    assert len(report.findings) == 100
    assert elapsed < 2.0
