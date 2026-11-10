"""Validate and mock-plan infrastructure without cloud credentials or remote state."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--terraform", default="terraform", help="Terraform executable or absolute path"
    )
    parser.add_argument(
        "--scan", action="store_true", help="Run pinned Checkov on Terraform sources"
    )
    args = parser.parse_args()
    executable = shutil.which(args.terraform)
    if executable is None:
        parser.error("Terraform was not found; install it or pass --terraform")
    executable = str(Path(executable).resolve())
    workspace = Path(__file__).resolve().parents[1]
    env = dict(os.environ, TF_IN_AUTOMATION="1", CHECKPOINT_DISABLE="1")
    commands: list[tuple[list[str], dict[str, str]]] = [
        ([executable, "fmt", "-check", "-recursive", "terraform"], env),
    ]
    for name in ("project", "bootstrap", "environments/dev", "environments/portal"):
        # Do not touch an operator's initialized backend or cached credentials.
        data_directory = workspace / "artifacts" / "terraform-validation" / name
        data_directory.mkdir(parents=True, exist_ok=True)
        isolated = dict(env, TF_DATA_DIR=str(data_directory))
        prefix = [executable, f"-chdir=terraform/{name}"]
        commands.extend(
            [
                (
                    [*prefix, "init", "-backend=false", "-input=false", "-lockfile=readonly"],
                    isolated,
                ),
                ([*prefix, "validate", "-no-color"], isolated),
                ([*prefix, "test", "-no-color"], isolated),
            ]
        )
    if args.scan:
        commands.append(
            (
                [
                    "uv",
                    "tool",
                    "run",
                    "--from",
                    "checkov==3.4.3",
                    "checkov",
                    "--directory",
                    "terraform",
                    "--framework",
                    "terraform",
                    "--skip-download",
                    "--compact",
                    "--quiet",
                ],
                env,
            )
        )
    for command, environment in commands:
        print("Running:", " ".join(command), flush=True)
        result = subprocess.run(command, cwd=workspace, env=environment, check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
