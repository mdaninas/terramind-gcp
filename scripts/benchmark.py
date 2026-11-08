"""Reproducible local 100-change normalization/report timing; synthetic data only."""

import json
import platform
import time

from terramind.normalizer.plan import normalize
from terramind.reports.render import build_report


def main() -> None:
    data = json.dumps(
        {
            "format_version": "1.2",
            "resource_changes": [
                {
                    "address": f"synthetic.resource_{index}",
                    "type": "google_storage_bucket_iam_member",
                    "change": {
                        "actions": ["create"],
                        "before": None,
                        "after": {"role": "roles/storage.objectViewer", "member": "allUsers"},
                    },
                }
                for index in range(100)
            ],
        }
    ).encode()
    start = time.perf_counter()
    report = build_report(normalize(data))
    elapsed = time.perf_counter() - start
    print(
        json.dumps(
            {
                "python": platform.python_version(),
                "changes": 100,
                "findings": len(report.findings),
                "elapsed_seconds": round(elapsed, 6),
            }
        )
    )


if __name__ == "__main__":
    main()
