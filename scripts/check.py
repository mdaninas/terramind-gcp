"""Cross-platform quality gate matching make lint + make test."""

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lint-only", action="store_true")
    args = parser.parse_args()
    commands = [
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "ruff", "format", "--check", "."],
        [sys.executable, "-m", "mypy"],
        [sys.executable, "scripts/export_schemas.py", "--check"],
        [sys.executable, "scripts/export_event_corpus.py", "--check"],
    ]
    if not args.lint_only:
        commands.append([sys.executable, "-m", "pytest", "--cov", "--cov-report=term-missing"])
    for command in commands:
        print("Running:", " ".join(command), flush=True)
        result = subprocess.run(command, check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
