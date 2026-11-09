# Local evaluation

Local checks were rerun on 2026-11-09 using Python 3.12.13 on Windows. Cloud
verification used a dedicated GCP project and Cloud Shell. These results cover
the offline analyzer, cloud foundation and synthetic retrieval/model integration.
They do not establish general semantic correctness of model-generated advice.

| Check | Result |
| --- | --- |
| Automated Python tests | 226 passed |
| Normalization and policy coverage, including branches | 97.58% |
| Four policy rule functions | 100% coverage |
| Required synthetic scenarios | All eight expectations passed |
| Ruff lint and formatting | Passed |
| Strict mypy checks | Passed |
| JSON Schema validity, fixture validation and schema drift | Passed |
| Offline demo | Four HIGH findings, JSON and Markdown output |
| Isolated runtime-only demo | Passed |
| Dependency audit | No known vulnerabilities reported |
| Source archive and wheel | Built successfully |
| API adapter coverage, measured separately | 94.92% |
| Actual local Uvicorn HTTP request | `/healthz` returned 200 with the expected JSON |
| Terraform 1.17.1 formatting and validation | All three configuration roots passed |
| Terraform mock-provider tests | Ten passed; no cloud calls or apply |
| Checkov 3.4.3 Terraform scan | 17 passed, zero failed, four documented exceptions |
| Checkov 3.4.3 Dockerfile scan | 48 passed, zero failed, zero skipped |
| Container build and execution | Cloud Shell Linux amd64 build passed; hardened container returned HTTP 200 |
| Deployed authenticated/unauthenticated calls | `/health`: authenticated 200 with expected JSON; anonymous 403 |
| Private storage | Both buckets enforce public access prevention and uniform access |
| Firestore | Native database, vector index READY, expiry ACTIVE, deny-all client release verified |
| Budget | IDR 180,000 monthly, project-filtered, credits excluded, 50/90/100% thresholds verified; delivery untested |
| Retrieval/model/cloud CLI coverage, measured separately | 88.66% |
| Local lexical retrieval test double | 10/10 hit at three, zero cloud calls |
| Google embeddings and Firestore retrieval | 10/10 hit at three across the same frozen queries |
| Live ingestion rerun | Zero embedding calls and zero document changes |
| Live Gemini synthesis | Four HIGH findings retained; ten verified citations; normal STOP finish |
| Measured model generation | 4.095 seconds in one observed run; 1,094 output tokens |

The tests cover rule positives, negatives and edge cases; IAM membership changes;
public access prevention; firewall protocols and port ranges; deletion and replacement;
input size and depth limits; sensitive-value exclusion; sanitized errors; and
execution with network access denied.
API tests additionally cover liveness, disabled documentation routes, absence of
unimplemented analysis routes, safe error handling, log content exclusion and
Cloud Run port configuration.

The [retrieval verification](retrieval-verification.md) records source integrity,
malicious-runbook and malformed-model checks. The [live query results](evaluations/retrieval-2026-11-09.json)
and [synthetic report](../examples/generated-reports/grounded-synthetic.md) are
inspectable. The generation timing excludes retrieval and is one observation,
not a latency guarantee. Terraform and container results above retain the earlier
foundation verification; their configuration was not changed in this step.

## Reproduce

```sh
uv sync --locked
uv run --locked python scripts/check.py
uv run --locked python scripts/demo_offline.py
uv run --locked python scripts/demo_retrieval.py
uv run --locked python scripts/benchmark.py
uv run --locked python scripts/check_infrastructure.py --scan
uv build
```

The recorded standalone benchmark normalized and reported 100 synthetic changes
in 0.003826 seconds. The automated performance test also passed the two-second
acceptance threshold. Timing depends on the machine and does not predict cloud latency.

GNU Make was unavailable on the evaluation machine. Native Python/uv commands were
verified; the corresponding Make targets were not executed.
The Terraform command requires an installed binary, or an explicit `--terraform`
path. [Cloud foundation verification](cloud-foundation-verification.md) records
the files, exact local commands and remaining checks.

## Limits

All fixtures are synthetic. The offline analyzer checks four explicit policies;
an empty finding list is not a guarantee of safety. Reports describe proposed
changes and do not verify deployed exposure, IAM effectiveness or recovery readiness.
See the [normalization scope](normalization.md) and [threat model](threat-model.md).
