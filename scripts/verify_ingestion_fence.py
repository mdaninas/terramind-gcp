"""Prepare or execute a bounded real-Firestore lease probe in fresh synthetic collections."""

import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from terramind.cloud.budget import CallBudget
from terramind.cloud.settings import CloudSettings
from terramind.events.google import FirestoreIndexCoordinator
from terramind.events.service import IndexingBusy, Lease


def probe(
    client: Any, settings: CloudSettings, *, manifest_directory: Path | None = None
) -> dict[str, object]:
    # Each run owns only these three fresh documents. The live corpus is never selected.
    namespace = "verification_" + uuid4().hex
    keys = [hashlib.sha256(f"{namespace}:{i}".encode()).hexdigest() for i in (0, 1)]
    control = client.collection(namespace + "_control").document("corpus")
    receipts = client.collection(namespace + "_receipts")
    references = [control, *(receipts.document(key) for key in keys)]
    if any(ref.get(timeout=5, retry=None).exists for ref in references):
        raise ValueError("Verification namespace collision")
    if manifest_directory is not None:
        manifest_directory.mkdir(parents=True, exist_ok=True)
        (manifest_directory / f"{namespace}.json").write_text(
            json.dumps({"documents": [ref.path for ref in references]}, indent=2) + "\n",
            encoding="utf-8",
        )

    def coordinator() -> FirestoreIndexCoordinator:
        target = FirestoreIndexCoordinator(settings, CallBudget(seconds=30, max_calls=20), client)
        target.lock = control
        target.chunks = client.collection(namespace + "_chunks")
        target.receipts = receipts
        return target

    first, second = coordinator(), coordinator()
    summary: dict[str, object] = {
        "status": "failed",
        "stage": "claim",
        "mode": "firestore_adapter_sandbox",
        "analysis_submissions": 0,
        "model_calls": 0,
        "staged_chunks": 0,
    }
    try:
        older = first.claim(keys[0])
        if older is None:
            raise ValueError("Unexpected receipt")
        try:
            second.claim(keys[1])
        except IndexingBusy:
            summary["active_lease_rejected"] = True
        else:
            raise ValueError("Active lease was not fenced")
        # The reference is unique to this run; this operation never expires the runtime lock.
        control.update(
            {"expires_at": datetime.now(UTC) - timedelta(seconds=1)}, timeout=5, retry=None
        )
        newer = second.claim(keys[1])
        if newer is None:
            raise ValueError("Unexpected receipt")
        first.release(older)
        if control.get(timeout=5, retry=None).to_dict()["owner"] != newer.owner:
            raise ValueError("A stale release removed the new worker's lock")
        summary["stage"] = "concurrent_commits"

        def commit(target: FirestoreIndexCoordinator, lease: Lease) -> str:
            try:
                target.commit(lease, (), ())
            except IndexingBusy:
                return "fenced"
            return "committed"

        with ThreadPoolExecutor(max_workers=2) as pool:
            stale = pool.submit(commit, first, older)
            current = pool.submit(commit, second, newer)
            if stale.result() != "fenced" or current.result() != "committed":
                raise ValueError("Concurrent fencing failed")
        if receipts.document(keys[0]).get(timeout=5, retry=None).exists:
            raise ValueError("A stale worker wrote a receipt")
        if not receipts.document(keys[1]).get(timeout=5, retry=None).exists:
            raise ValueError("The current worker did not write its receipt")
        if control.get(timeout=5, retry=None).exists or second.claim(keys[1]) is not None:
            raise ValueError("Receipt replay or atomic lock release failed")
        summary.update(
            status="passed",
            stage="complete",
            stale_commit_fenced=True,
            current_commit_recorded=True,
            duplicate_receipt_skipped=True,
        )
    except Exception:
        summary.update(status="failed")
    finally:
        try:
            for ref in references:
                ref.delete(timeout=5, retry=None)
            if any(ref.get(timeout=5, retry=None).exists for ref in references):
                raise ValueError("Sandbox cleanup incomplete")
            summary["sandbox_cleanup_verified"] = True
        except Exception:
            summary.update(status="failed", stage="cleanup", sandbox_cleanup_verified=False)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--execute", action="store_true", help="Requires explicit owner approval")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", args.project) or not re.fullmatch(
        r"[a-z][a-z0-9-]{3,61}[a-z0-9]", args.database
    ):
        parser.error("Use the approved project and named database")
    summary: dict[str, object] = {
        "status": "prepared",
        "mode": "no_cloud_calls",
        "execute": False,
        "analysis_submissions": 0,
        "model_calls": 0,
        "planned_scope": "Three fresh synthetic documents, two competing worker commits, cleanup",
    }
    if args.execute:
        try:
            from google.cloud import firestore

            settings = CloudSettings(project_id=args.project, database=args.database)
            summary = probe(
                firestore.Client(project=args.project, database=args.database),
                settings,
                manifest_directory=Path("artifacts/operational-readiness/private"),
            )
        except Exception:
            summary = {"status": "failed", "stage": "configuration", "model_calls": 0}
    path = Path("artifacts/operational-readiness/ingestion-fence-summary.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] in {"prepared", "passed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
