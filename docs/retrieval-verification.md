# Retrieval verification

Local verification and live Google Cloud checks are recorded separately. The
implementation uses the existing dedicated project and synthetic data only.
This is the retrieval feature's verification snapshot. Subsequent API and delivery
work is recorded in the [current verification](api-delivery-verification.md).

## Files and architecture

| Area | Files created or updated |
| --- | --- |
| Knowledge | `knowledge-base/runbooks/*.md`, `knowledge-base/incidents/*.md` |
| Ingestion and retrieval | `src/terramind/rag/{contracts,corpus,ingestion,retrieval,evaluation,local}.py` |
| Generation | `src/terramind/llm/{contracts,service}.py` |
| Cloud boundaries | `src/terramind/cloud/{budget,google,settings}.py`, `src/terramind/knowledge_cli.py` |
| Report contracts | `schemas/{report,knowledge-chunk,advisory-response}.v1.schema.json`, schema exporter, report renderer |
| Verification | Knowledge/SDK tests, synthesis/CLI integration tests, ten retrieval cases, ten synthesis cases, malicious Markdown fixture |
| Developer experience | Cloud dependency extra and lockfile, `.env.example`, Make targets, local retrieval demo and documentation |

The optional Google adapters implement provider-independent protocols. Source
loading, chunking and ingestion do not import Google SDKs. The offline CLI retains
its credential-free dependency path. Model output owns advisory prose only;
deterministic findings and overall risk are rebuilt independently and retained
unchanged on every failure path.

Heading-aware character windows keep chunking small and reproducible. Their token
count is approximate, and short sections are retained without padding. Stable IDs
allow atomic replacement/pruning; text hash, title and embedding profile govern
vector reuse. A manual single-operator ingestion command avoids a queue, event
trigger or distributed indexing coordinator in the MVP.

Strict local response validation is separate from model formatting instructions.
References must identify supplied chunks for the associated finding. Invalid
responses produce visible deterministic fallback rather than fabricated success.
See the [feature and operating guide](retrieval-and-explanations.md) for limits,
provider references, global endpoint implications and exact reproduction commands.

## Commands executed locally

```sh
uv run --locked python scripts/check.py
uv run --locked pytest tests/unit/test_knowledge.py tests/unit/test_cloud_adapters.py tests/integration/test_explanations.py tests/integration/test_knowledge_cli.py tests/evals/test_retrieval.py --cov=terramind.rag --cov=terramind.llm --cov=terramind.cloud --cov=terramind.knowledge_cli --cov-report=term-missing
uv run --locked python scripts/demo_retrieval.py
uv run --locked python scripts/demo_offline.py
uv run --locked python scripts/export_schemas.py
uv export --locked --all-extras --no-emit-project --format requirements-txt --output-file artifacts/audit-requirements.txt --quiet
uv run --locked pip-audit --no-deps --disable-pip --requirement artifacts/audit-requirements.txt
```

- Full Python suite: **226 passed**; lint, formatting, strict mypy and schema checks passed.
- Normalization and policy branch-aware coverage: **97.58%**.
- Retrieval, generation, cloud adapters and cloud CLI: **88.66%** separately measured coverage.
- Ten local lexical retrieval cases: **10/10 hit at three**. This measures the local
  test double and contract plumbing, not Google embedding quality.
- Ten synthesis contract cases: deterministic HIGH findings preserved and no
  unrecognized citation IDs emitted, including malformed and adversarial outputs.
- Original offline demo: **four HIGH findings**. Local retrieval demo makes zero cloud calls.
- Source distribution and wheel built. A base-only wheel installation completed
  offline analysis without Google SDK or FastAPI packages installed.
- Dependency audit including cloud extra: **no known vulnerabilities reported**.
  The audit completed despite a Windows cache-write warning.

## Live cloud checks

The reviewed source-only archive was uploaded to Cloud Shell, verified by SHA-256,
and extracted without plan files, state, private variables or credentials. Cloud
dependencies were installed from the lock export with `pip --require-hashes`.
The configured project number was checked before any data operation.

The same CLI operations documented in the feature guide were executed using the
authenticated operator, not the health-only Cloud Run runtime identity:

- Initial ingestion: **10 documents, 10 chunks, 10 embeddings**, one changed corpus,
  zero stale deletions, **33 RPC attempts** including storage operations.
- Identical rerun: **zero embeddings, zero document changes**, **11 read attempts**.
- Google embeddings with Firestore vector retrieval: **10/10 hit at three**,
  ten queries and **20 RPC attempts**, exit 0.
- Gemini synthesis: **four HIGH findings preserved**, ten source references
  independently matched to Firestore records and local document hashes, exit 0.
  The model was **gemini-3.5-flash**, with a normal STOP finish, **1,094 output
  tokens**, **4.095 seconds** for generation and **nine RPC attempts** overall.
  The timing excludes retrieval and is a single observation, not a latency guarantee.

Early live requests exercised deterministic fallback for provider formatting,
incomplete output and reference-format failures. The final provider schema is
small, output allowance is 4,096 tokens, supported models use minimal thinking,
and incomplete generations are rejected explicitly. Model-visible references use
readable document/section identities. The final citation list is rebuilt from
validated per-finding references; internal provenance hashes are application-owned.
The final cloud modules were checked against the locally tested syntax-tree
hashes before execution. No infrastructure or permission changes were used to
work around a generation failure.

The [frozen live query results](evaluations/retrieval-2026-11-09.json) and actual
[synthetic JSON/Markdown report](../examples/generated-reports/README.md) are
included for inspection. Private diagnostic files and provider output remain
under ignored artifacts or the private Cloud Shell workspace.

## Security and remaining work

No new infrastructure, APIs or IAM changes were required for these operator-run
checks. The existing private Cloud Run service continues to provide liveness.
Only the ten reviewed synthetic documents and sanitized synthetic fixture facts
were sent to Google services. No tool execution or credential values enter model
context. Application errors omit provider details and input values.

These tests do not establish semantic correctness for arbitrary model prose.
Prompt instructions and lexical approval guards are defense in depth; immutable
findings, validated references and escaped rendering provide the enforceable
boundaries. Health-runtime data/prediction roles, analysis routes, report storage,
private presentation and protected deployment remain subsequent work. Cloud
resources and indexed synthetic documents remain active for development, with
cleanup tracked for completion of the portfolio project.
