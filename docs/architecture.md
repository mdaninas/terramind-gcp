# Architecture decisions

Offline analysis is implemented and verified locally. The isolated GCP foundation
and private Cloud Run liveness API are deployed, with real authentication checks.
See the [roadmap](roadmap.md).

## Dependency direction

The CLI depends on normalization, policies and reporting. Policies depend only on
immutable typed contracts. The report builder runs policies and derives the maximum
severity. It owns findings; later model/retrieval adapters can add advisory text
through separate contracts without replacing findings.

No cloud SDK, HTTP server, credentials lookup, external subprocess or network
client is part of the offline analysis path. Pydantic is the sole base runtime
dependency; FastAPI and Uvicorn are optional API dependencies. This keeps a
runtime-only offline installation small and reproducible.

## Local privacy boundary (ADR 001)

Parse bounded Terraform JSON locally and project it into a closed vocabulary,
rather than redact a copy of the full plan. Resource aliases use managed input
order (`resource_0001`); they reveal no original name and avoid reversible hashes
of predictable private identifiers. Aliases are stable for identical ordered
inputs but are not persistent identities across differently ordered plans.

Only world CIDRs survive normalization. Nonpublic IAM principals become
`redacted`; supported roles remain enums. Private CIDRs, labels, names, project IDs,
conditions, prior values, unknown/sensitive masks, outputs and provider details do
not survive. Unknown/sensitive facts generate closed limitation codes.

Tradeoff: the cloud cannot map aliases back to real infrastructure. Engineers must
correlate findings locally. Terraform names/order are not a trust boundary for
policy authority; the future API must re-run rules on submitted facts.

## Differential IAM facts (ADR 002)

Compute membership, role, scope and condition differences locally. Only
`newly_granted: true|false|null` crosses the boundary; prior identities and condition
expressions do not. Changed conditions conservatively count as new grants. New
conditional grants and unavailable prior facts yield REVIEW instead of certainty.

Tradeoff: redaction loses per-principal readability. The analyzer covers member, binding and
policy resources for bucket and project IAM, not custom-role permission expansion.

## Reports and risk authority (ADR 003)

Rule functions are pure and deterministic, with stable rule IDs and evidence.
Overall risk is the maximum severity, including REVIEW findings. An empty result
is `NO_KNOWN_FINDINGS`. UUID/timestamps identify report invocations, so the complete
report JSON is not byte-identical across runs even when findings are identical.

JSON Schema is generated from code, checked for drift and validated against all
samples. Pydantic additionally checks numeric port ranges and alias uniqueness.
Both output formats derive from the same report. Markdown includes only trusted
templates and allowlisted facts, avoiding injection from raw resource strings.

## HTTP and cloud foundation

The packaged API adapter exposes `/health` and the container probe `/healthz`;
`apps/api/main.py` is a thin source-tree
entry point. Cloud Run owns authentication. The local server binds to loopback,
while the non-root container listens on Cloud Run's assigned port. Content-free
structured logs replace raw URL access logs. No analysis endpoints or data adapters
are exposed yet.

Terraform separates state bootstrap from the dev environment. Modules manage
identity, image storage, synthetic runbooks, a named Firestore database and private
Cloud Run. A null image prepares the supporting resources first; a verified digest
then enables the service. Mock-provider plan tests validate security defaults without
contacting GCP. These tests cannot establish deployed IAM or index readiness.

The runtime has no data roles until an implemented adapter needs them. Ingestion
uses a separate identity with database-conditioned permissions and bucket-scoped
object access. The GitHub identity can publish images and update the existing
service, with trust restricted to exact repository and owner IDs, main, a protected
environment and the manual deployment workflow. It has no Terraform-state access.

Retrieval and Gemini advisory adapters are implemented behind provider-independent
contracts and an explicit synthetic cloud CLI. Report persistence, private
presentation and the deployment workflow remain planned. See
[deployment setup](setup-gcp.md) and [security exceptions](security-exceptions.md).

## Evidence and advisory boundary

The optional cloud CLI imports Google SDKs only after local validation. A separate
knowledge package handles strict synthetic metadata, heading-aware chunking,
idempotent embedding reuse and atomic Firestore synchronization. Source Markdown
is private and content addressed; the vector collection is fixed by the adapter.

Retrieval runs once per applicable policy type, with at most three sources per
type in the default profile. Generation receives immutable finding facts and
untrusted excerpts. Closed response contracts exclude severity and policy changes.
The application validates finding coverage and resolves citations only from the
provided source set before constructing an advisory. Provider failure, malformed
output or missing evidence returns the original deterministic findings with a
visible limitation. Markdown escapes all advisory text and source titles.

Local lexical vectors and fixture prose provide reproducible contract tests;
their scores are labeled separately from live Google embedding evaluations.
The [retrieval guide](retrieval-and-explanations.md) documents tradeoffs, limits
and the authenticated operator workflow.
