"""Check versionable files without printing matched secret material."""

import re
import subprocess
import sys
from pathlib import Path

PATTERNS = (
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    rb"AIza[0-9A-Za-z_-]{35}",
    rb"gh[pousr]_[0-9A-Za-z]{30,}",
    rb'"type"\s*:\s*"service_account"',
)


def main() -> int:
    names = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
        )
        .decode()
        .split("\0")
    )
    failed = False
    for name in dict.fromkeys(filter(None, names)):
        path = Path(name)
        if not path.is_file():
            continue
        forbidden = (
            path.suffix in {".sqlite", ".sqlite3", ".db"}
            or name.endswith(
                (
                    ".sqlite-wal",
                    ".sqlite-shm",
                    ".sqlite3-wal",
                    ".sqlite3-shm",
                    ".sqlite-journal",
                    ".sqlite3-journal",
                    ".db-wal",
                    ".db-shm",
                    ".db-journal",
                )
            )
            or path.suffix in {".tfstate", ".tfplan", ".plan", ".tfvars", ".tfbackend"}
            or ".tfstate." in name
            or name.endswith(".tfvars.json")
            or path.name == "backend.hcl"
            or (path.name.startswith(".env") and path.name != ".env.example")
            or name.startswith(("artifacts/", "gha-creds-"))
        )
        data = path.read_bytes()
        forbidden |= data.startswith(b"SQLite format 3\0")
        if path.suffix == ".json":
            import json

            try:
                payload = json.loads(data)
                forbidden |= isinstance(payload, dict) and (
                    "resource_changes" in payload
                    or "refresh_token" in payload
                    or ("terraform_version" in payload and "resources" in payload)
                )
            except (ValueError, UnicodeError):
                pass
        if forbidden or any(re.search(pattern, data) for pattern in PATTERNS):
            print(f"Public file check failed: {name}")
            failed = True
    print(
        "Public file privacy checks passed."
        if not failed
        else "Remove private files before publishing."
    )
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
