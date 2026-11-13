# User portal, login and report history

The portal is a separate server-rendered application with Google OpenID Connect
configuration, local synthetic demo accounts, owner-scoped reports, a dashboard
and paginated history filters. Local API, cryptographic verifier and browser
checks passed. Subsequent real Google login, private Cloud Run hosting, Firestore
report persistence, exports, filters and logout were exercised on 2026-11-10.
The updated portal image also passed real Google login and logout on 2026-11-11.
The 2026-11-13 window verified two real Google owners, 21 and one reports,
two-page history, cross-owner export rejection and revocation of both sessions.
See the [latest operational verification](operational-verification.md), earlier
[advisory verification](advisory-verification.md), historical
[hosted results](live-integrations-verification.md) and
[local verification](portal-verification.md). Billing is disabled.

## Try the local synthetic demo

Install the locked portal dependencies. In PowerShell, run:

```powershell
$env:TERRAMIND_SERVICE = 'portal'
$env:HOST = '127.0.0.1'
$env:PORT = '8080'
$env:PORTAL_ORIGIN = 'http://127.0.0.1:8080'
$env:PORTAL_AUTH_MODE = 'demo'
$env:PORTAL_ANALYSIS_MODE = 'offline'
$env:PORTAL_DATABASE = 'artifacts/portal.sqlite3'
uv run --locked --extra portal python -m terramind.api
```

Open `http://127.0.0.1:8080/login`. Choose the synthetic analyst or reviewer,
select the core risk sample, no-change sample, Storage hardening or Database
hardening, and inspect its report, incident context and exports. Hardening samples
explicitly select their respective optional pack. Reports show policy version and
pack selection, and history supports all eight rule IDs. Incident Memory reports
partial coverage for the new rules because the four curated incidents cover only
the core rules. See [policy packs](policy-packs.md).
Sign out and choose the other account to see a separate history. These disposable
accounts demonstrate ownership behavior; they are not identity verification.
Demo mode rejects non-loopback client connections and Cloud Run environments,
and the supported entry point refuses a public-interface demo bind.

The dashboard supports risk, rule and UTC date filters, with 20 reports per page.
Counts use the same owner, expiry and filters as the list; HIGH and CRITICAL
reports contribute to the high-risk total. Cursor pagination uses creation time
and UUID to handle tied timestamps. Empty filters and empty histories have
explicit UI states. Reports can be read as HTML, exported as a JSON bundle or
downloaded as Markdown with the separately labeled incident context.

![Local synthetic dashboard with two owned reports](images/portal-desktop.jpg)

Actual local synthetic-login capture. This does not show a live Google sign-in,
cloud analysis or hosted deployment.

## Configure Google login

Create or select a reviewed Google OAuth web client and register exactly
`PORTAL_ORIGIN/auth/callback` as its authorized redirect URI. Provider setup is an
operator action. The approved hosted verification used an External testing client
with one reviewed test user and a Secret Manager client-secret binding.
Supply these values through private environment or secret storage:

- `PORTAL_AUTH_MODE=google`.
- `PORTAL_ORIGIN`, an HTTPS origin, or an explicitly registered loopback HTTP
  origin for development. Do not include a path, query, fragment or credentials.
- `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`.
- `PORTAL_ALLOWED_EMAILS`, a comma-separated exact allowlist of verified Google
  email addresses. Wildcard/domain-wide admission is not supported.

The authorization request uses code flow with state, nonce and an S256 PKCE
challenge. The protected sign-in form opens a same-origin continuation page;
its explicit Google link starts a new navigation. This preserves the strict
`form-action 'self'` policy in browsers that also check a form's redirect chain.
A pending flow is bound to the browser's anonymous server session,
expires after five minutes and is consumed once before exchange. Redirect URIs
come only from configuration. The token exchange uses Google's fixed HTTPS
endpoint and does not follow redirects. Certificate requests have a five-second
timeout; the token request has a ten-second timeout and a bounded response body.

`google-auth` verifies signature, Google issuer, audience and token times with a
30-second clock-skew allowance. The application then checks nonce, authorized
party, verified email and exact allowlist. Ownership uses a SHA-256 of the
provider and stable Google `sub`, not an email supplied by a browser. Raw profile
names/emails and provider ID/access/refresh tokens are not saved in reports or
SQLite. Client secrets are not stored in SQLite or included in settings repr.
Pending nonces/verifiers and CSRF values are sensitive server-side state and are
held in the private database. The reviewed testing client completed a real code
exchange with matching state and nonce. Negative provider-side PKCE cases were
not exercised live.

## Session and ownership boundary

Opaque random session tokens are stored only as SHA-256 digests on the server.
Successful login rotates the session and CSRF token; logout revokes the server
session. Sessions expire after 30 minutes idle or four hours absolute. They persist
across application restarts. Reducing the email allowlist does not immediately
revoke already issued sessions; expire or revoke those sessions during maintenance.

Cookies are HttpOnly and SameSite=Lax. HTTPS uses Secure, a `__Host-` name, root
path and no Domain attribute. State-changing forms require both an exact Origin
and a session-bound CSRF token. Referrers are restricted to origin, excluding
callback codes and report paths. CSP permits only local images/styles and forms;
no external JavaScript, browser token storage or password handling is used.

Every report read, export, list, count and filter binds to the authenticated
server-side owner. An existing report owned by another user returns the same 404
as an absent/expired report. A request cannot choose its owner through headers or
query fields. The portal does not mount the original shared-demo API; its SQLite
reports cannot be fetched through the old API's report namespace. The old
analysis app retains its documented shared authorized-demo boundary.

The local SQLite database uses parameterized queries and create-only report
writes. It retains active reports for at most 24 hours and removes expired rows
on subsequent state maintenance; read paths never serve expired reports. Idle
data can remain on disk until another maintenance request. There is no secure
erase or database encryption claim. Keep the database, journals and backups in
a private directory with appropriate operating-system permissions. The public
file check rejects common SQLite extensions, journals and SQLite headers.

Bounds: 512 active sessions, 512 active reports per owner, 2,048 active reports
overall, 600 KiB per report bundle, four KiB form bodies, and six admitted analyses
per minute with one analysis at a time per process. These availability/cost
controls are not enterprise rate limiting or tenant isolation.

## Optional cloud analysis and hosting limits

The subsequent [live activation plan](live-activation-plan.md) provides a durable
Firestore adapter and standalone private Cloud Run configuration. The configuration
was applied under explicit approval, followed by real Google login and durable
report verification. Billing was disabled after testing. The original single-host
verification remains historical evidence; current results are recorded separately.

Offline is the default. `PORTAL_ANALYSIS_MODE=cloud` requires Google authentication,
the cloud extras, approved GCP configuration/credentials and active billing for
the metered services. It reuses the existing bounded retrieval/Gemini adapter and
preserves deterministic fallback findings. The UI labels that mode explicitly;
the report page includes advisory text and validated source references when present.
Both scenarios are generated server-side from synthetic facts. There is no
arbitrary plan upload or production-data submission flow.

The default SQLite adapter remains for single-host use. Set
`PORTAL_STORAGE_BACKEND=firestore` and `PORTAL_FIRESTORE_DATABASE` only with Google
authentication and approved cloud configuration. A Cloud Run portal refuses
SQLite storage. The new environment uses a separate portal database and retains
Cloud Run invoker IAM independently of Google application login.

For an approved operator-only rollout, run the official authenticated proxy on
`127.0.0.1:8091`; register that exact origin's `/auth/callback` with the reviewed
OAuth web client. `PORTAL_TRANSPORT_HOST` allowlists one exact Cloud Run hostname
to accommodate the proxy's Host rewrite. Set Terraform's optional `transport_host`
to the exact hostname returned in `service_url`, rather than assuming its URL
format. The original Origin/CSRF boundary stays
fixed to the loopback origin. No forwarded host or identity header grants access.
This is a private hosted operator demo, not a public login website. An HTTPS
public-facing rollout would need its own ingress and OAuth review.

During the original single-host implementation no billing, cloud IAM, OAuth
settings or paid resources changed. During subsequent approved activation,
the OAuth client, scoped IAM and private resources were configured and tested.
The core portal report returned a validated advisory; optional-pack reports used
safe fallback. Six total analysis submissions were counted, including a no-change
sample without retrieval/model calls. Billing was then disabled and the proxy stopped.

The approved 2026-11-11 follow-up verified new core and optional-pack advisories
through the private API, promoted the same image to the portal and rechecked
Google login, the existing dashboard and logout. No new portal analyses were
submitted. Billing was disabled again and both authenticated proxies were stopped.

The approved 2026-11-13 window promoted the wording correction and created 22
no-change reports without retrieval or model generation. The read-only checker
used 18 GETs to verify stable cursor traversal, disjoint histories, own exports,
cross-owner 404s, anonymous 401 and owner-override rejection. Both Google sessions
were revoked; subsequent reads using their cookies returned 401. Temporary access
for the second account was removed from the portal and OAuth Testing, billing
was disabled again and all workspace-owned proxies were stopped. This verifies
the tested ownership boundaries, not large-scale capacity.

References: [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect),
[google-auth token verifier](https://googleapis.dev/python/google-auth/latest/reference/google.oauth2.id_token.html),
[OAuth security guidance](https://www.rfc-editor.org/rfc/rfc9700.html), and
[OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).
