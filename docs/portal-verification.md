# Incident Memory and user portal verification

Historical local record. Subsequent real Google login, Firestore report workflows
and revision persistence are documented in the
[hosted verification](live-integrations-verification.md).

The local Incident Memory and user portal implementations were verified on
2026-11-10 (Asia/Jakarta), in the existing Windows checkout based on
`018fc5dc139c7eda4719ea689898b317f8d02a6f`, before committing these changes.
The [machine-readable record](evaluations/portal-2026-11-10.json) separates
application tests, mocked provider verification, browser checks and remaining
live work. This is not a fresh-clone or managed-cloud deployment claim.

## Implemented behavior

[Incident Memory](incident-memory.md) uses local TF-IDF cosine similarity on four
fabricated incidents. Matching sources retain IDs, hashes, versions and explicit
synthetic-evidence labels. Searches derive from policy IDs and do not change the
deterministic report. A CLI command and a versioned result schema are included.

The [portal](user-portal.md) provides synthetic demo login and configurable Google
OIDC, server-side sessions, owner-scoped report reads/exports, dashboard counts,
and history filters by risk, rule and UTC dates. SQLite provides bounded local
persistence and tied-timestamp pagination. The portal runs as a separate app;
its records are not exposed through the old shared-demo API.

## Observed results

| Check | Result |
| --- | --- |
| Full application suite | 435 passed in 11.97 seconds |
| Normalization/policy branch-aware coverage | 97.58%, unchanged |
| Targeted portal/incident suite | 67 passed |
| Portal/incident module branch-aware coverage | 91.31%, measured separately |
| Frozen synthetic incident queries | 4/4 expected documents ranked first |
| Ruff, strict mypy, schemas and packaged corpus | Passed; mypy checked 64 source files |
| Signed-token verification | Real google-auth verifier with ephemeral local RSA tokens and stubbed provider HTTP |
| Dependency audit | No known vulnerabilities; non-fatal Windows cache-write warning |
| Dockerfile Checkov | 48 passed, zero failed, zero skipped |
| Actionlint | Three workflows passed; ShellCheck integration disabled |
| Packaging | Source archive and wheel built; base-only wheel imports loaded incident corpus and portal bundle |
| Real local browser | Synthetic login, risk/benign scenarios, report persistence after restart, risk/rule filtering, Markdown export, logout and separate empty reviewer history passed |
| Browser console inspection | No errors or warnings observed |

Authentication tests exercise forged signatures, wrong issuer/audience, expired
and future tokens, nonce mismatch, unverified/disallowed email, wrong authorized
party and missing subject. State is browser-bound, expiring and single-use; login
rotates session tokens. Additional tests cover cookie attributes, logout/idle/
absolute expiry, CSRF/Origin failures, unrecognized hosts, remote demo rejection,
and private database/journal detection.

Report tests verify cross-user access rejection for HTML/JSON/Markdown, owner-only
counts and pagination, retention, create-only writes, corrupted rows, duplicate/
oversized forms, invalid filters/cursors and escaped advisory content. Stored
provider tokens, real profiles, OAuth client secrets and raw session cookies are
not part of the report contract.

The real Chrome form flow caught a referrer-policy issue that mocked form requests
did not reveal. The portal now uses `strict-origin`, preserving request-origin
validation while excluding path/query values from referrers. The corrected
synthetic login, analysis and logout flows passed in Chrome. No Origin/CSRF check
was removed.

The [desktop capture](images/portal-desktop.jpg) contains only two synthetic reports
and a synthetic display name. At the small breakpoint, the measured document and
content widths were both 417 pixels. Screenshot capture timed out in the browser
tool; the viewport override was reset. Mobile visual verification remains
incomplete and no mobile screenshot is presented as proof.

The temporary portal server was stopped after verification. SQLite files, browser
downloads, tokens and raw logs remain outside version control. Only the selected
synthetic screenshot and content-free result record are public artifacts.

Reproduce the principal checks:

```sh
uv run --locked python scripts/check.py
uv run --locked pytest tests/evals/test_incident_memory.py tests/integration/test_portal.py tests/security/test_portal_auth.py tests/unit/test_portal_store.py tests/unit/test_portal_views.py --cov=terramind.incidents --cov=terramind.portal --cov-report=term-missing --cov-fail-under=80 -q
uv run --locked terramind incidents --input examples/normalized-plans/public_bucket.json --output artifacts/incident-memory.json
uv run --locked python scripts/check_public_files.py
uv build
```

Follow the [portal setup](user-portal.md) for the real browser flow. Standard
cryptographic library verification is exercised locally; a live Google OAuth
client, account login and provider PKCE behavior still need a separately configured
smoke check. Cloud portal hosting and a managed durable backend are not delivered
by this single-host change. No cloud IAM, billing, infrastructure provisioning or
paid model requests were performed during this implementation.

The prior PR/Eventarc source was already committed and pushed. Its
[hosted CI run](https://github.com/mdaninas/terramind-gcp/actions/runs/42757795778)
passed. That hosted run verifies the prior integration commit, not these later
uncommitted portal changes. Additional policy packs are the next requested work.
