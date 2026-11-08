# Roadmap

The offline analyzer is available. Planned work includes cloud hosting, retrieval,
AI explanations and secure delivery.

| Area | Scope | Status |
| --- | --- | --- |
| Offline analysis | Local normalization, deterministic risk rules, JSON and Markdown reports | Implemented and verified locally |
| Cloud foundation | Terraform foundation and private Cloud Run health service | Planned |
| Retrieval and explanations | Synthetic runbooks, Firestore vector retrieval and Gemini explanations | Planned |
| API and delivery | Analysis API, private report page and GitHub Actions deployment | Planned |
| Release verification | End-to-end evaluation, walkthrough and deployment documentation | Planned |

## Offline analyzer

The analyzer provides a bounded local Terraform JSON normalizer, four pure
GCP policy rules, versioned schemas, synthetic examples and report exports.

Acceptance criteria: eight fixture expectations pass, lint and type checks pass,
normalization and policy coverage exceeds 80%, and local analysis of 100 changes
finishes in under two seconds. See the [evaluation](evaluation.md) for measured results.

## Cloud foundation

Add a separate Terraform state bootstrap and modules for Artifact Registry, private
Cloud Run, Firestore, synthetic-runbook storage, IAM, Workload Identity Federation
and observability. Package a minimal FastAPI health service.

Acceptance criteria: Terraform formatting, validation and security scans pass;
an authenticated deployed request succeeds; unauthenticated requests fail; storage
buckets remain private. Deployment checks require an approved, configured GCP project.

## Retrieval and explanations

Add 8-12 synthetic Markdown documents, heading-aware chunks, idempotent ingestion,
768-dimensional Google embeddings, Firestore vector retrieval and structured
Gemini explanations. Keep model names and endpoints configurable.

Acceptance criteria: at least eight of ten curated queries retrieve the intended
runbook in the top three, citations map to supplied sources, and model outages or
prompt injection cannot remove or downgrade deterministic findings. Record local
mock tests and live cloud evaluations separately.

## API and delivery

Add strict analysis endpoints, sanitized report storage and retention, Markdown
downloads, a minimal private HTML report page, credential-free pull request CI and
protected deployment using OIDC and immutable image digests.

Acceptance criteria: offline and authorized cloud demos work end to end, hosted CI
passes, deployed smoke checks pass, and untrusted pull requests receive no deployment
credentials.

## Release verification

Complete screenshots, the walkthrough, measured evaluations, cost drivers,
deployment and cleanup instructions, and fresh-clone reproduction.

Acceptance criteria: documented commands work for a new developer, no credentials
or raw plans enter version control, and cloud resources are documented as active or
verified as removed.

## Scope boundaries

The MVP does not apply infrastructure changes or approve deployments. Paid resources
and cloud IAM changes require explicit owner approval. Pull request commenting,
Eventarc indexing triggers, expanded policy packs and a full dashboard are deferred
until the MVP is complete.
