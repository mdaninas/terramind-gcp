"""Local-only CLI. No network clients, credentials or infrastructure execution."""

import argparse
import sys
from pathlib import Path

from terramind.errors import InputError
from terramind.normalizer.io import load_normalized, read_bounded
from terramind.normalizer.plan import normalize
from terramind.reports.render import build_report, markdown
from terramind.schemas.normalized import MAX_PLAN_BYTES, MAX_REQUEST_BYTES, serialize_plan


def _write(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    except OSError:
        raise InputError("Unable to write output file") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Terramind offline Terraform change analysis")
    subparsers = parser.add_subparsers(dest="command", required=True)
    normalizer = subparsers.add_parser(
        "normalize", help="Normalize a LOCAL Terraform show JSON plan"
    )
    normalizer.add_argument("--input", type=Path, required=True)
    normalizer.add_argument("--output", type=Path, required=True)
    analyzer = subparsers.add_parser("analyze", help="Analyze strictly normalized JSON offline")
    analyzer.add_argument("--input", type=Path, required=True)
    analyzer.add_argument("--output", type=Path, required=True)
    analyzer.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    try:
        if args.input.resolve() == args.output.resolve():
            raise InputError("Input and output must be different files")
        if args.command == "normalize":
            plan = normalize(read_bounded(args.input, MAX_PLAN_BYTES))
            _write(args.output, serialize_plan(plan))
        else:
            plan = load_normalized(read_bounded(args.input, MAX_REQUEST_BYTES))
            report = build_report(plan)
            result = (
                markdown(report) if args.format == "markdown" else report.model_dump_json(indent=2)
            )
            _write(args.output, result)
        return 0
    except InputError as error:
        print(f"terramind: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
