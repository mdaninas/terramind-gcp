# Threat model

Assets: raw local Terraform values, credentials, private resource identifiers and
the integrity of deterministic findings. Inputs are untrusted even when described
as Terraform JSON. Repository examples are handcrafted synthetic normalized facts.

| Threat | Current control | Residual risk / planned work |
| --- | --- | --- |
| Raw plan/state leaks to cloud | Offline path has no network clients; local allowlist projection; API accepts only strict synthetic normalized facts | Callers must keep original files outside source control; a source label cannot prove facts are synthetic |
| Private identifiers leak through reports | Generated ordinal aliases, private CIDRs omitted, identity redaction, closed enums; canary tests | Aliases/types/counts still disclose structural facts; only synthetic data is approved for cloud demos |
| Marked sensitive values affect output | Risk-relevant sensitive attributes omitted and limitation emitted | Redacted unknown facts can hide risks; no known findings never means safe |
| Malicious plan text or Markdown injection | Arbitrary plan strings omitted; retrieved text is untrusted; model tools disabled; advisory Markdown escaped; malicious runbook tested | Prompt instructions cannot guarantee semantic correctness; generated advice still needs review |
| Parser resource exhaustion / ambiguity | 5 MiB/256 KiB limits, max 100 changes, bounded collections, depth 64, duplicate-key rejection | Local caller already controls its own files; limits are conservative and reject some large legitimate plans |
| Incorrect exposure claim | Explicit protocol/ports/source facts; prevention-aware REVIEW; no live reachability or backup claims | Hierarchical firewall precedence, IAM deny/conditions, unsupported resource types and custom roles need human review |
| Model downgrades policy | Offline rules remain independent; model schema excludes policy fields; immutable findings survive malformed, injected and unavailable responses | Advisory prose can still be wrong; lexical approval guards are defensive rather than semantic proof |
| Supply-chain dependency risk | uv lock with hashes, Ruff/mypy, pip-audit and bounded runtime dependencies | Audits report only known vulnerabilities; online setup/audit contact package services |
| PR code or artifact injection | Manual main-only review checks out trusted code; read-only blob analysis; separate publisher validates a bounded same-run artifact and current SHAs | Review covers synthetic normalized JSON only; hosted publishing and rerun deduplication passed; maintainer access and trusted main must remain protected |
| Event replay or stale index writes | Exact bucket/generation/source allowlist, packaged corpus checks, durable receipts and atomically fenced Firestore writes | Embeddings can repeat after a failed commit; TTL is asynchronous; live delivery/replay passed, concurrent stale-worker fencing remains locally tested |
| Accidental cloud mutation | No apply endpoint; deployment workflow is manual/main/protected-environment only and changes an image digest; infrastructure checks use mock plans | Operator Terraform apply and IAM changes require explicit approval and verified parameters |
| Unauthorized service invocation | Cloud Run invoker IAM requires explicit callers; deployed health/demo/analysis rejected anonymous calls; authenticated report reads returned 200 | Project/service policies contain no public principals; organization inheritance needs separate review |
| Overprivileged service identity | Runtime analysis roles are explicit opt-in and activated with custom permissions; deployment and ingestion use separate identities | Runtime data IAM isolates a database, not collections; model invocation is project-scoped |
| Shared API report theft or stale data | Private Cloud Run, generated UUIDs, no shared-API listing route, application expiry and Firestore TTL | Original API invokers share report access; UUIDs are not user authorization; portal records use a separate ownership boundary |
| Portal report access across users | Every read/export/list/count binds to the authenticated owner; separate local SQLite namespace or private portal Firestore database; uniform 404 for other owners | Cross-owner isolation and larger pagination datasets remain locally tested; database IAM does not enforce application ownership |
| Login forgery, session theft or CSRF | Google token verifier, exact allowlist, nonce/state bound to server session, PKCE request, token rotation, server revocation, idle/absolute expiry and Origin plus CSRF checks | Real Google login passed for one approved account in a private operator demo; demo accounts require loopback and are not real identity verification |
| Misleading incident similarity | Packaged synthetic-only incident corpus, hash validation, source references and explicit tabletop labels; scores do not change findings | Lexical similarity on four curated incidents is not semantic recall or real-incident evidence |
| HTTP or presentation abuse | Streamed 256 KiB limit, five-second body timeout, strict media/schema, escaped HTML, CSP, one analysis at a time and a rolling admission limit | Admission limits reset per process and do not provide a hard spending cap |
| Untrusted pull request deployment | CI has no OIDC/cloud credentials; privileged job consumes only the trusted manual run's image artifact | Protected main-only deployment and WIF exchange passed; main/workflow changes and reviewers must remain protected |

No raw input, schema-validation values or original file paths are emitted by
application errors. CLI help displays only documented commands. There is no logging
of input values or report payloads. The offline network-denial test replaces socket
creation and runs normalization plus report generation.

`.gitignore` excludes common plan/state/credential names and all generated artifacts;
this is defense in depth, not a guarantee against deliberate staging. No real plan
or state file is checked in. Tests create synthetic Terraform-shaped objects in
memory or temporary test directories, never persistent raw-plan fixtures.

Cloud Run authentication, protected GitHub environment enforcement and a real WIF
token exchange are verified.
Firestore client rules deny all access; server SDKs use database-conditioned IAM,
which does not enforce collection restrictions. The report writer sets an aware
expiry timestamp and refuses expired reads before physical TTL deletion. See [security exceptions](security-exceptions.md)
for scanner exceptions and logging boundaries. Retrieval/model adapters operate
through the synthetic cloud CLI and deployed API. The runtime has named-database
get/list/create and project-scoped prediction/quota use, without update/delete or
administration. Hosted CI and cloud report delivery passed. The owner subsequently
disabled project billing, retaining the project; individual resource deletion
was not verified. See the [billing shutdown record](evaluations/billing-disabled-2026-11-10.json).
If billing is re-enabled, indexed synthetic sources incur metered
storage and read/write usage; model calls have explicit time, attempt and token
limits. Budget alerts do not stop spending.
