# Analysis API and report delivery

The synchronous API and report page are implemented and verified locally and in
the hosted CI container. The protected deployment environment is configured. The
existing Cloud Run deployment still serves the earlier health image; runtime IAM
activation, WIF exchange and a deployed analysis remain outstanding gates.

## Local demonstration

```sh
uv sync --locked
uv run --locked --extra api python -m terramind.api
```

Open `http://127.0.0.1:8080/demo`. The preview uses one packaged synthetic sample
with all four risk rules. Selecting **Analyze synthetic sample** sends that same
sample to the API and opens a stored report. JSON and Markdown exports are available
from the report page. Viewing the preview never invokes a model or writes a report.

In another terminal:

```sh
uv run --locked python scripts/demo_cloud.py --url http://127.0.0.1:8080 --local
```

This checks the real local HTTP service, deterministic findings, persistence,
Markdown and HTML. It does not test Cloud Run authentication or Google services.
`make demo-api` runs the same check. Local mode uses bounded process memory,
makes no provider calls and discards reports on restart. It binds to loopback;
it is not an authentication server.

## HTTP contract

| Endpoint | Behavior |
| --- | --- |
| `GET /health`, `GET /healthz` | Liveness, no SDK initialization or provider calls |
| `POST /v1/analyses` | Synthetic normalized JSON, returns a saved report with 201 and a Location header |
| `GET /v1/analyses/{analysis_id}` | Saved JSON report, or 404 when missing/expired |
| `GET /v1/analyses/{analysis_id}/markdown` | Markdown attachment |
| `GET /v1/analyses/{analysis_id}/view` | Escaped HTML report |
| `GET /demo` | Packaged synthetic preview with an analysis button |
| `GET /assets/report.css`, `GET /assets/demo.js` | Packaged assets, no external dependencies |

The request is the normalized object itself, without a wrapper. See
[`analysis-request.v1.schema.json`](../schemas/analysis-request.v1.schema.json).
The hosted subset permits `source: synthetic-demo` only. Raw plans, unknown
properties, original resource names and `local-normalizer` payloads are rejected.
The label cannot establish where a caller obtained facts; authorized callers must
use synthetic data. No file upload or production-plan submission UI is provided.

```sh
curl --fail --silent --show-error \
  --header 'Content-Type: application/json' \
  --data-binary @src/terramind/api/assets/sample.json \
  http://127.0.0.1:8080/v1/analyses
```

Malformed JSON, duplicate keys, non-finite numbers and excessive nesting return
400. Schema violations return 422. The actual streamed body is limited to 256 KiB
regardless of Content-Length (413). Compressed bodies or another media type return
415. A body read taking over five seconds returns 408. Provider/validation details
and rejected input values are omitted from errors and logs.

Only one analysis runs at a time per process, with six admitted requests per rolling
minute by default. Busy or exhausted instances return 429 with Retry-After. These
are process-local controls; restarts and additional instances reset/multiply them.
They are not a hard spending cap. Keep the approved Cloud Run instance cap at one.

Model or retrieval failures return a saved deterministic report with an explicit
fallback when storage works. Storage failure returns 503 and no successful report
Location. Unexpected internal errors return a content-free 500. Invalid report IDs
are rejected before persistence is queried.

## Composition and retention

`api/service.py` composes the existing policy/retrieval/explanation layers through
an injectable service. HTTP parsing and rendering stay outside the policy engine.
Google imports and ADC discovery are deferred until cloud data/model operations.
Synchronous SDK work runs outside the event loop. The analysis call budget is 23
seconds and 20 physical RPC attempts, including bounded transient retries. A report
write has a separate three-second, one-attempt budget. These are RPC budgets, not
an absolute service latency guarantee; Cloud Run retains its 30-second deadline.

`reports/store.py` defines an immutable synthetic report record. The memory adapter
holds at most 128 unexpired reports. The Firestore adapter uses the fixed `analyses`
collection and create-only writes; it never overwrites an existing report or retries
an ambiguous write. Only report JSON, a generated UUID, a synthetic marker and a
timezone-aware `expires_at` are stored. Request plans, prompts and embeddings are
not copied into report records. UTF-8 report JSON is limited to 512 KiB.

Reports expire after 24 hours, configurable down to one hour. Reads enforce expiry
immediately, even when Firestore has not physically deleted a record. The existing
TTL policy schedules eventual deletion; physical deletion is asynchronous. The
prepared Terraform change excludes the report JSON body from indexing. See
[Firestore TTL behavior](https://firebase.google.com/docs/firestore/ttl).

## Authentication and presentation

Cloud Run invoker IAM protects every hosted route, including demo assets and exports.
The application does not trust caller-supplied identity headers or implement user
login. All authorized invokers share this single demo trust boundary and can read
reports by ID. UUIDs are not per-user authorization; multi-tenancy is out of scope.
No listing or search endpoint is provided.

For a browser demonstration after an approved deployment, use the authenticated
Google Cloud CLI proxy and open its loopback URL:

```sh
gcloud run services proxy terramind-dev --project "$GCP_PROJECT_ID" --region "$GCP_REGION" --port=8081
```

Open `http://127.0.0.1:8081/demo`. The proxy supplies Google authentication; do not
put identity tokens into URLs or browser storage. Direct navigation to a private
Cloud Run URL does not supply an identity token automatically.

All report text is escaped before HTML rendering. Content Security Policy permits
only same-origin scripts, styles and connections, with no frames, forms or remote
assets. Responses use no-store, nosniff, DENY framing and no-referrer headers.
The frontend submits only its packaged sample and renders errors as fixed text.

Request telemetry uses fixed route templates, generated request IDs, method/status
categories and elapsed time. Analysis events contain risk, finding count, retrieval
status and advisory presence. Bodies, report IDs, arbitrary paths, query strings,
headers, prompts and provider exceptions are omitted. Existing Cloud Run request
metrics and the configured server-error alert remain the basic monitoring layer.

See [delivery and approval instructions](delivery.md) and the
[verification record](api-delivery-verification.md).
