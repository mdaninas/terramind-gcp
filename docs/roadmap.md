# Roadmap

The offline analyzer, synthetic retrieval and private analysis API are implemented
and verified. Protected GitHub Actions deployment through WIF passed. Portfolio
release verification passed for the documented source. Project billing was
disabled on 2026-11-10 (Asia/Jakarta); the project was retained and resource
deletion has not been verified. See the [shutdown record](evaluations/billing-disabled-2026-11-10.json).

| Area | Scope | Status |
| --- | --- | --- |
| Offline analysis | Local normalization, deterministic risk rules, JSON and Markdown reports | Implemented and verified locally |
| Cloud foundation | Terraform foundation and private Cloud Run health service | Deployed and verified; federation exchange passed |
| Retrieval and explanations | Synthetic runbooks, Firestore vector retrieval and Gemini explanations | CLI implemented and verified locally and on GCP |
| API and delivery | Analysis API, private report page and GitHub Actions deployment | Deployed and verified; protected WIF delivery and cloud analysis passed |
| Release verification | End-to-end evaluation, walkthrough and deployment documentation | Fresh-clone commands, screenshots, walkthrough and cost/cleanup record verified |
| Synthetic PR review | Manual trusted workflow, managed bot comment and neutral head check | Implemented and verified locally; hosted publishing unverified |
| Eventarc source indexing | Private generation-bound receiver, fenced ingestion and durable receipts | Implemented and verified locally; opt-in Terraform validated; cloud activation unverified |
| Incident Memory | Local TF-IDF similarity over fabricated incidents with provenance and evidence labels | Implemented; four curated top-one retrieval cases passed |
| User portal | Google OIDC configuration, synthetic demo login, owned reports and paginated filters | Implemented and verified locally; live Google login and managed deployment unverified |

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
At verification time, the vector index was READY and the expiry policy was ACTIVE. See
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

After verification, the owner chose to disable billing and retain the project.
The console confirmed that billing was disabled. This stops billable services;
individual resource deletion and recovery were not verified. Release tagging and
any future full resource cleanup remain owner actions. No new cloud deployment
or paid model evaluation was needed for the billing shutdown.

Acceptance criteria: documented commands work for a new developer, no credentials
or raw plans enter version control, and the cloud lifecycle is documented with
billing status and any resource removal claims supported by evidence.

## Scope boundaries

The MVP does not apply infrastructure changes or approve deployments. Paid resources
and cloud IAM changes require explicit owner approval. After MVP verification,
the owner requested synthetic PR review and Eventarc indexing. See their
[security design](pr-integration.md), [indexing contract](eventarc-indexing.md) and
[local verification](integrations-verification.md). Neither new integration has
been exercised against its live hosted destination.

The subsequent [Incident Memory](incident-memory.md) and
[single-host portal](user-portal.md) implement the requested local incident,
login, dashboard and history workflows. See their [verification record](portal-verification.md).
Additional policy packs remain the next requested development work.
