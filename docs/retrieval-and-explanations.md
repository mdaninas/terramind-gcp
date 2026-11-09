# Retrieval and explanations

Terramind keeps policy decisions independent of retrieval and generation. The
optional cloud CLI explains existing findings using synthetic Markdown sources,
Google embeddings, Firestore vector search and Gemini structured output. The
offline analyzer still runs with Pydantic alone and makes no cloud calls.

## Components and trust boundaries

| Component | Responsibility |
| --- | --- |
| `knowledge-base/runbooks/` and `knowledge-base/incidents/` | Six synthetic runbooks and four fabricated tabletop incidents |
| `rag/corpus.py` | Bounded loading, strict synthetic metadata, heading-aware chunks and hashes |
| `rag/ingestion.py` | Embed changed text, reuse matching profiles and synchronize stable chunk IDs |
| `cloud/google.py` | Official Google SDK adapters for embeddings, Firestore, source storage and Gemini |
| `rag/retrieval.py` | Top three sources per policy type, with dimension, profile and integrity validation |
| `llm/service.py` | Ground existing findings, validate source references and return deterministic fallback |
| `knowledge_cli.py` | Explicit synthetic cloud operations, separate from the offline CLI |

Documents use stable `doc_id`, title and version metadata. Their `content_hash` is
SHA-256 of the canonical Markdown body: UTF-8, LF newlines, outer whitespace
removed. Source objects contain precisely that body. Each chunk records its source
path, document hash, heading-derived section ID and text hash. Chunk IDs derive from
document and section identity, so editing content updates existing records.
Readable `doc_id:section_id` citation labels are derived from that same identity.
The model sees those labels, titles and excerpts; internal hashes and source paths
remain in the application-owned provenance catalog rather than the prompt.

Chunks target 1,800 characters, approximately 450 English tokens, with at most 160
characters of overlap inside a section. This is a character heuristic rather than
a tokenizer guarantee. Short sections remain short. Headings inside fenced code
are retained as text. Duplicate heading slugs are rejected instead of creating
ambiguous citations. A document is limited to 48 KiB and a corpus to 128 chunks.

The supplied ten short documents currently produce ten chunks. The malicious
`tests/fixtures/prompt_injection.md` fixture is outside the ingestion directories.
Synthetic labels and credential-marker checks are defensive controls, not a
guarantee that arbitrary owner-supplied documents contain no private information.
Only the reviewed repository corpus is approved for the cloud demonstration.

## Local demonstration

```sh
uv sync --locked
uv run --locked terramind-knowledge plan
uv run --locked python scripts/demo_retrieval.py
uv run --locked python scripts/demo_offline.py
```

The retrieval demo uses local lexical vectors, an in-memory store and explicitly
labeled fixture prose. It writes evaluation JSON and JSON/Markdown reports under
ignored `artifacts/`. It does not call Gemini or Firestore and its retrieval score
does not measure Google embedding quality. The original offline demo remains the
credential-free deterministic product path.

## Cloud ingestion and evaluation

Use the existing approved dedicated project, named Firestore database and private
runbook bucket. Install the locked cloud extra when using a runtime-only checkout:
`uv sync --locked --extra cloud`. Development dependencies already include the SDKs
for adapter tests. Authenticate with short-lived operator ADC; never use JSON keys.
The examples below use Bash in Cloud Shell and run from the repository root.

```sh
export GCP_PROJECT_ID="YOUR_APPROVED_PROJECT_ID"
export GOOGLE_CLOUD_PROJECT="$GCP_PROJECT_ID"
export GOOGLE_CLOUD_QUOTA_PROJECT="$GCP_PROJECT_ID"
export CLOUDSDK_CORE_PROJECT="$GCP_PROJECT_ID"
export FIRESTORE_DATABASE="terramind-dev"
export RUNBOOK_BUCKET="$GCP_PROJECT_ID-terramind-dev-runbooks"
export EMBEDDING_MODEL="gemini-embedding-001"
export EMBEDDING_LOCATION="us-central1"
export GEMINI_MODEL="gemini-3.5-flash"
export GEMINI_LOCATION="global"
export EXPLANATION_LANGUAGE="en"

uv run --locked --extra cloud terramind-knowledge plan
uv run --locked --extra cloud terramind-knowledge ingest --execute
uv run --locked --extra cloud terramind-knowledge ingest --execute
uv run --locked --extra cloud terramind-knowledge evaluate --execute --output artifacts/retrieval-live-evaluation.json
uv run --locked --extra cloud terramind-knowledge analyze --execute --input examples/normalized-plans/public_bucket.json --output artifacts/gemini-live-report.json
```

`--execute` explicitly enables metered calls. It does not provision resources,
change IAM or apply Terraform. Verify project parameters and owner authorization
before using it. The cloud analysis command accepts the closed normalized schema
and `source=synthetic-demo`; it refuses raw plans and locally normalized real plans.
Keep outputs private until inspected. The command returns exit 1 with a valid
policy report when AI is unavailable, and exit 2 for invalid input/configuration.

Ingestion reads the bounded collection, reuses vectors only when text hash, title
and embedding model match, and performs a single atomic Firestore batch for changed
records and stale-ID removal. Identical reruns make no embedding calls or document
writes. Content-addressed Markdown objects use create-only generation preconditions.
Publish failures can leave unused source objects; the bucket lifecycle handles
their retention. This manual MVP supports one reviewed corpus and one ingestion
operator at a time, without event triggers or background workers.

Queries use `RETRIEVAL_QUERY`; documents use `RETRIEVAL_DOCUMENT` with their title.
The SDK requests 768 dimensions, disables silent truncation and validates finite,
nonzero vectors. Vectors are normalized and Firestore searches with COSINE distance.
The existing native Terraform vector index is used without an additional index.

The configured model defaults and locations were checked against official Google
documentation on 2026-11-09. Availability and quota must still be verified for the
actual project. A global Gemini endpoint can process data outside the ordinary
resource region; do not treat `GCP_REGION` as a model residency guarantee.
[Embedding configuration](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/embeddings/get-text-embeddings),
[Gemini model availability](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-5-flash),
[Firestore vector search](https://firebase.google.com/docs/firestore/vector-search).

## Grounding, fallback and cost controls

The model receives only deterministic finding facts and short retrieved excerpts.
It receives no original plan, credentials, account identity or environment dump.
System instructions classify excerpts as untrusted data. Tool calling and automatic
continuation are disabled. These prompt controls supplement the architectural
boundary; they do not prove that every possible narrative is correct.

The response schema contains summary, per-finding explanations, recommendations,
citation IDs and limitations. The application supplies model identity, retrieval
status and source metadata after validation. The model cannot supply severity or
replace findings. Every finding must appear exactly once and cite its own allowed
sources. The top-level model reference list is treated as untrusted and rebuilt
from validated per-finding references, so descriptive or invented entries never
become report citations. Unknown or unrelated references are dropped and flagged; losing all
references causes fallback. Invalid JSON, injected output fields, forbidden approval
assertions, empty retrieval and provider failures preserve all policy findings.
Model prose and source titles are escaped when rendered as Markdown. A small
provider formatting schema avoids unsupported or expensive grammar constraints;
the complete Pydantic contract is always enforced after generation. A non-STOP
finish reason, including token truncation, is rejected even if the text parses.

For the documented `gemini-3.5-flash` and `gemini-3.1-flash-lite` models, the
adapter uses the supported `MINIMAL` thinking level. This task explains existing
policy facts and does not delegate policy reasoning to the model. Other configured
model IDs receive no model-specific thinking option. Verify support before
extending that allowlist. [Supported thinking levels](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/guides/gemini-3-5-flash).

At most twelve findings receive one synthesis request, and at most four distinct
policy types produce retrieval queries. Larger reports retain all findings with a
visible advisory-limit caveat. Empty finding sets make no cloud calls. Prompt and
response sizes are bounded, and generation is limited to 4,096 output tokens.

Adapters share an RPC deadline and physical-attempt budget: analysis 25 seconds / 20
attempts, ingestion 240 seconds / 200 attempts, evaluation 120 seconds / 50 attempts.
Individual RPC timeouts are at most twenty seconds for analysis and eight seconds
for ingestion/evaluation. Up to two retries are allowed
only for transient errors. SDK retries are disabled to avoid multiplication, and
ambiguous writes are reconciled by rerunning ingestion rather than blindly retried.
Credential setup and provider transport behavior can affect observed wall time;
these limits are not an enforceable monetary spending cap. The existing budget
provides alerts, and source/image/storage retention still matters.

## Scope of this change

This guide covers library and CLI integration. The deployed Cloud Run service
continues to expose liveness only. Analysis HTTP routes, report persistence, the
report page and deployment workflows are now implemented locally; their cloud
activation is documented in the [API guide](analysis-api.md) and
[delivery review](delivery.md). Live CLI checks use
the already authorized operator identity; they do not establish that the current
health-only runtime or ingestion service account can invoke models.
