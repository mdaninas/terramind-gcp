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

## Local report page

Run `uv run --locked --extra api python -m terramind.api`, open
`http://127.0.0.1:8080/demo` and select **Analyze synthetic sample**. Expect the same
four findings, a JSON link and a Markdown download. This mode uses process memory
and makes no provider calls. In another terminal, run
`uv run --locked python scripts/demo_cloud.py --url http://127.0.0.1:8080 --local`
to verify the HTTP flow. Reports disappear on restart or expiry.

The cloud CLI has verified Gemini explanations and Firestore retrieval separately.
The hosted analysis API and protected deployment workflow still need activation
and live verification. See the [cloud demonstration instructions](delivery.md#cloud-demonstration).
