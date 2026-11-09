"""Generate committed JSON Schema; CI can detect contract drift without writing."""

import argparse
import json
import sys
from pathlib import Path

from terramind.llm.contracts import ModelNarrative
from terramind.rag.contracts import Chunk
from terramind.schemas.api import AnalysisRequest
from terramind.schemas.normalized import NormalizedPlan
from terramind.schemas.report import Report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for name, model in (
        ("normalized-plan.v1", NormalizedPlan),
        ("analysis-request.v1", AnalysisRequest),
        ("report.v1", Report),
        ("knowledge-chunk.v1", Chunk),
        ("advisory-response.v1", ModelNarrative),
    ):
        path = Path("schemas") / f"{name}.schema.json"
        content = json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                print(f"Schema drift: regenerate {path}", file=sys.stderr)
                return 1
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
