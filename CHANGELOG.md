# Changelog

## Unreleased

- Matched federation to GitHub's immutable owner/repository subject format and
  added a fail-closed OIDC metadata check before deployment builds.

- Added strict synthetic analysis endpoints, create-only expiring reports,
  Markdown downloads and a minimal escaped report page with a packaged demo.
- Added local admission/size/deadline limits, safe analysis telemetry, memory and
  Firestore report adapters, and an authenticated cloud demonstration client.
- Prepared credential-free CI, protected manual WIF image deployment, environment
  and runtime guards, and explicitly opt-in runtime IAM/index configuration.
  Hosted runs and deployment of the analysis image remain unverified.

- Added ten synthetic knowledge documents, heading-aware chunks, idempotent
  Google embedding ingestion, private source publishing and Firestore retrieval.
- Added Gemini advisory contracts, source validation, strict deterministic
  fallback, escaped report rendering and bounded model/RPC settings.
- Added a separate synthetic cloud CLI, local retrieval test-double demo, golden
  citation/failure cases and a malicious runbook test fixture.
- Verified ten live retrieval queries, idempotent re-ingestion and a grounded
  Gemini report retaining all four findings with ten validated source references.
- Added a FastAPI liveness service, safe structured request telemetry and a
  non-root container definition with a restricted build context.
- Added separate Terraform state bootstrap and modular cloud configuration for
  private Cloud Run, Artifact Registry, Firestore vectors and TTL, synthetic
  runbook storage, scoped service identities, federation and server-error alerts.
- Added credential-free infrastructure checks, mock-provider tests, pinned
  provider lockfiles, deployment guidance and explicit security exceptions.
- Added an optional dedicated-project root with billing alerts that count usage
  before credits, audit configuration and protected project deletion.
- Verified the approved Cloud Run deployment: `/health` returns authenticated
  200 and anonymous 403; private buckets and the ready Firestore index were checked.
- Retained `/healthz` for internal probes and added the external `/health` alias
  for Cloud Run's reserved-path compatibility. Federation exchange remains untested.

## 0.1.0 - 2026-11-08

- Added a Python offline CLI, bounded local normalization, strict schema v1.0 and
  generated JSON Schemas, four deterministic policies and JSON/Markdown reports.
- Added eight synthetic normalized scenarios, unit/integration/privacy tests,
  lint/type/coverage/schema checks, dependency lock and credential-free demo.
- Documented the roadmap, architecture decisions, supported normalization scope,
  security boundary and local walkthrough.

Cloud deployment, RAG/model adapters, private API/report page and hosted CI are
not implemented in this release. No Phase 2 functionality is included.
