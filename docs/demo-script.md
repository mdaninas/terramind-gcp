# Two-minute offline walkthrough

Prerequisites: Python 3.12+, uv, terminal in repository root. No GCP credentials.
Install dependencies once with `uv sync --locked`.

1. Run `uv run --locked python scripts/demo_offline.py` (or `make demo-offline`).
2. Open `artifacts/demo-report.md`. Expect HIGH overall and exactly these findings:
   TM-GCP-001 public object-read grant, TM-GCP-002 world SSH ingress,
   TM-GCP-003 project owner grant, TM-GCP-004 bucket deletion (REVIEW).
3. Open `artifacts/demo-report.json` to inspect rule IDs, evidence, remediation,
   policy version and explicit `rag_status=not_requested`, `model_id=null`.
4. Run a benign example:

   ```sh
   uv run --locked terramind analyze --input examples/normalized-plans/no_changes.json --output artifacts/benign.md --format markdown
   ```

5. Open `artifacts/benign.md`: `NO_KNOWN_FINDINGS` plus visible limitations.
6. Run `uv run --locked python scripts/check.py` to reproduce lint/type/schema/test
   verification. This is local verification, not a successful GitHub Actions run.

Demonstrate prevention-aware behavior with `public_bucket_pap_enforced.json`:
TM-GCP-001 remains HIGH but status is REVIEW; the report says prevention blocks the
public grant, avoiding an assertion of actual exposed data.

The demo reads packaged synthetic normalized fixtures only. A real local plan is
not needed. No Terraform CLI, API enablement or infrastructure provisioning occurs.
A cloud demo, private HTML page, screenshots and AI explanations are planned.
