# Changelog

## Unreleased

- Added synthetic Incident Memory using local TF-IDF cosine similarity, source
  provenance and explicit tabletop-evidence labels. Four frozen policy queries
  ranked the intended fabricated incident first without changing policy findings.
- Added a separate single-host portal with Google OIDC configuration, loopback-only
  synthetic login, server-side sessions, owned reports, paginated history and
  risk/rule/UTC-date filtering. Report JSON/Markdown and incident sources preserve
  the user ownership boundary.
- Verified local portal flows and the real google-auth verifier against locally
  signed synthetic tokens. Live Google login and hosted portal deployment remain
  unverified; no new billing, IAM or paid model operations were performed.

- Added a manual trusted-main workflow for synthetic PR fixture analysis, one
  managed bot comment and a neutral check bound to the reviewed head. Read-only
  analysis is separated from publishing permissions; PR code is never executed.
- Added a separate opt-in Eventarc receiver with generation-bound source checks,
  packaged synthetic corpus, durable receipts and transactionally fenced index
  updates. Terraform defaults keep the new service, trigger and IAM disabled.
- Verified new integrations with local API/SDK doubles and infrastructure mock
  plans. Hosted comment/check publication and live Eventarc delivery remain
  unverified. Billing stays disabled and the existing project is retained.

- Added actual local desktop/mobile report screenshots, the full architecture flow
  and a timed walkthrough, with local and cloud evidence labeled separately.
- Verified fresh-clone setup, lint/types/schemas, all 297 tests, package builds,
  local HTTP reports and all four documented Make targets without Google credentials.
- Added a sourced usage-cost scenario, content-free release evidence and active
  resource/cleanup status. No additional cloud deployment or model call was made.

- Matched federation to GitHub's immutable owner/repository subject format and
  added a fail-closed OIDC metadata check before deployment builds.

- Added strict synthetic analysis endpoints, create-only expiring reports,
  Markdown downloads and a minimal escaped report page with a packaged demo.
- Added local admission/size/deadline limits, safe analysis telemetry, memory and
  Firestore report adapters, and an authenticated cloud demonstration client.
- Prepared credential-free CI, protected manual WIF image deployment, environment
  and runtime guards, and explicitly opt-in runtime IAM/index configuration.
  Verified hosted CI, a real WIF exchange and immutable Cloud Run image deployment.
- Verified live synthetic analysis with four HIGH findings, ten validated sources,
  saved JSON, Markdown and HTML; anonymous requests were rejected. One analysis
  request took 10.898 seconds. Resources remain active pending final cleanup.

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
  for Cloud Run's reserved-path compatibility.

## 0.1.0 - 2026-11-08

- Added a Python offline CLI, bounded local normalization, strict schema v1.0 and
  generated JSON Schemas, four deterministic policies and JSON/Markdown reports.
- Added eight synthetic normalized scenarios, unit/integration/privacy tests,
  lint/type/coverage/schema checks, dependency lock and credential-free demo.
- Documented the roadmap, architecture decisions, supported normalization scope,
  security boundary and local walkthrough.

Cloud deployment, RAG/model adapters, private API/report page and hosted CI are
not implemented in this release. No Phase 2 functionality is included.
