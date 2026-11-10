# Roadmap

The offline analyzer, synthetic retrieval and private analysis API are implemented
and verified. Protected GitHub Actions deployment through WIF passed. Portfolio
release verification passed for the documented source; cloud resources are active.

| Area | Scope | Status |
| --- | --- | --- |
| Offline analysis | Local normalization, deterministic risk rules, JSON and Markdown reports | Implemented and verified locally |
| Cloud foundation | Terraform foundation and private Cloud Run health service | Deployed and verified; federation exchange passed |
| Retrieval and explanations | Synthetic runbooks, Firestore vector retrieval and Gemini explanations | CLI implemented and verified locally and on GCP |
| API and delivery | Analysis API, private report page and GitHub Actions deployment | Deployed and verified; protected WIF delivery and cloud analysis passed |
| Release verification | End-to-end evaluation, walkthrough and deployment documentation | Fresh-clone commands, screenshots, walkthrough and cost/cleanup record verified |

## Offline analyzer

The analyzer provides a bounded local Terraform JSON normalizer, four pure
GCP policy rules, versioned schemas, synthetic examples and report exports.

Acceptance criteria: eight fixture expectations pass, lint and type checks pass,
normalization and policy coverage exceeds 80%, and local analysis of 100 changes
finishes in under two seconds. See the [evaluation](evaluation.md) for measured results.

## Cloud foundation

Separate Terraform state bootstrap and modules are provided for Artifact Registry,
private Cloud Run, Firestore, synthetic-runbook storage, IAM, Workload Identity
Federation and observability. A minimal FastAPI health service is packaged.
Formatting, validation, mock plans and security scans are available locally.

Acceptance criteria: Terraform formatting, validation and security scans pass;
an authenticated deployed request succeeds; unauthenticated requests fail; storage
buckets remain private. These checks passed in an approved dedicated project.
The vector index is READY and the expiry policy is ACTIVE. See
[verification evidence](cloud-foundation-verification.md) and [setup instructions](setup-gcp.md).

## Retrieval and explanations

Ten synthetic Markdown documents, heading-aware chunks, idempotent ingestion,
768-dimensional Google embeddings, Firestore vector retrieval and structured
Gemini explanations are implemented behind the optional knowledge CLI. Model
names and endpoints remain configurable.

Acceptance criteria: at least eight of ten curated queries retrieve the intended
runbook in the top three, citations map to supplied sources, and model outages or
prompt injection cannot remove or downgrade deterministic findings. Record local
mock tests and live cloud evaluations separately.

The live evaluation retrieved the expected document in the top three for all ten
queries. Identical re-ingestion made zero embedding calls or document changes.
A live Gemini report preserved all four findings and validated ten source
references. See the [verification record](retrieval-verification.md).

## API and delivery

Strict synthetic-only analysis endpoints, expiring report storage, Markdown
downloads, a minimal HTML report page, credential-free pull request CI and protected
manual deployment using OIDC and immutable image digests are implemented. The
local API and hosted CI are verified. The protected development environment has a
required owner reviewer and an exact main branch policy. Approved runtime activation,
WIF exchange, immutable image deployment and authenticated cloud analysis passed.
The saved report preserved four HIGH findings and ten validated source references;
anonymous requests were rejected.
See the [verification record](api-delivery-verification.md).

Acceptance criteria: offline and authorized cloud demos work end to end, hosted CI
passes, deployed smoke checks pass, and untrusted pull requests receive no deployment
credentials.

## Release verification

Actual local desktop/mobile screenshots, a timed walkthrough, the full application
flow, measured evaluations and a sourced cost scenario are documented. A fresh
GitHub clone passed setup, lint/types/schemas, all 297 tests, package builds and the
local HTTP flow without Google credentials. All four documented Make targets passed.
See the [release verification record](release-verification.md).

The existing cloud deployment remains active with explicit cost controls and
cleanup instructions. Release tagging and final resource deletion are owner actions;
no new cloud deployment or paid model evaluation was needed for this documentation pass.

Acceptance criteria: documented commands work for a new developer, no credentials
or raw plans enter version control, and cloud resources are documented as active or
verified as removed.

## Scope boundaries

The MVP does not apply infrastructure changes or approve deployments. Paid resources
and cloud IAM changes require explicit owner approval. Pull request commenting,
Eventarc indexing triggers, expanded policy packs and a full dashboard are deferred
until the MVP is complete.
