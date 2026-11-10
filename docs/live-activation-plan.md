# Live integration activation plan

Historical approved proposal. The subsequent
[hosted verification record](live-integrations-verification.md) supersedes the
operating state below. Resources were applied, Google login was exercised and
billing was disabled again after six analysis submissions. Advisory limitations
and the failed latest strict smoke are recorded with the actual results.

Prepared on 2026-11-10 from `d7ef9b502fe30c7f900e7d787526afda62383ef8`
plus the uncommitted durable-portal and verification changes. This is a reviewable
activation proposal, not a record of successful hosted verification.

## Operating state when prepared

The dedicated project is `terramind-gcp-mdaninas`, in `us-central1`.
Billing was re-linked to its existing open billing account under the owner's prior
approval to reactivate it when needed. Cloud Shell returned `billingEnabled: true`.
The private `terramind-dev` service and existing state/runbook buckets remain.
No new resource or IAM apply has been performed during this preparation.

The first remote-state refresh was blocked by disabled billing. After activation,
the copied historical variable file proposed removing six existing API IAM
resources. That plan was rejected. Explicitly preserving analysis activation,
the current immutable image and the one-instance cap produced the Eventarc plan
below without removals.

## Eventarc plan

The reviewed remote-state plan contains **17 additions, zero changes and zero
deletions**. It retains the existing private analysis API and its IAM. Additions:

- Eventarc, Pub/Sub and Storage API enablement records.
- `terramind-dev-events`, a separate internal-ingress, IAM-protected Cloud Run
  receiver, with zero minimum instances, one maximum instance and concurrency one.
- `terramind-dev-evt-index` and `terramind-dev-evt-call`, separate runtime and
  delivery identities.
- Database-conditioned Firestore document CRUD and transaction-read permissions
  for the receiver, read-only access to the existing synthetic source bucket, and
  the two prediction/quota permissions needed for embedding calls.
- Eventarc receiver permissions for the delivery identity and invoker permission
  restricted to the event receiver service.
- Pub/Sub publisher for the project's Cloud Storage service agent, the finalized
  event trigger, receipt expiry and the receiver request-URL logging exclusion.

The preliminary plan uses the currently deployed image only to review resource
and permission changes. It must not be applied with that old image: first promote
the reviewed new source through the trusted protected workflow, obtain its
immutable digest, re-plan and verify that no unrelated changes or deletions appear.
The old unsafe plan must never be applied.

## Durable portal proposal

The new standalone [portal environment](../terraform/environments/portal/main.tf)
uses a separate `terramind/portal` state prefix in the existing private backend.
It is locally validated and mock-planned, not yet deployed or live-planned with
the final OAuth client and promoted image.

- A private `terramind-portal` Cloud Run service, with invoker IAM enforced,
  zero minimum instances, one maximum instance and concurrency one.
- A dedicated `terramind-portal` identity and separate Firestore Native database.
  Sessions, pending login flows and owned reports survive instance replacement.
- CRUD and transaction-read permissions restricted to the portal database.
  Read-only document access to the existing knowledge database, plus the two
  project-scoped model prediction/quota permissions. No source-bucket write,
  vector-index administration or IAM administration permissions for the portal.
- Browser client access to the portal database denied through Firestore rules.
  TTL policies for sessions, login flows and reports, an owned-active-report index,
  and index exemptions for report payloads and login secrets.
- OAuth client secret supplied by one existing Secret Manager secret, pinned to
  a numeric version. Terraform manages the runtime's accessor binding, not secret
  contents. Create and populate that secret privately after approval; never put
  its value in Terraform variables, source, shell history or screenshots.
- Explicit operator-only Cloud Run invokers, request-URL logging excluded before
  service creation, and no `allUsers` or `allAuthenticatedUsers` invoker grant.

The browser uses the official authenticated Cloud Run proxy, bound only to
`127.0.0.1:8091`. This is a privately hosted operator portal, not a public website.
The Google OAuth callback is exactly `http://127.0.0.1:8091/auth/callback`.
The service separately allowlists its exact Cloud Run transport hostname because
the official proxy rewrites Host. Origin and CSRF validation still use only the
configured loopback origin; forwarded identity/host headers are not trusted.
Cloud Run itself retains authenticated invocation on every remote request.

Google Auth Platform is not yet configured. The prepared branding form uses
Terramind, the project's current operator as support/contact, External **testing**
audience, and has not accepted the Google API Services User Data Policy or created
credentials. Restrict test users and portal admission to the explicitly reviewed
operator account. Request only `openid email`, not Drive, Gmail or cloud-admin
OAuth scopes. The owner completes any interactive account login or consent.

### Storage bounds and limitations

The cloud adapter enforces 512 unexpired sessions, 512 active reports per owner,
2,048 active reports globally, a 600 KiB report bound, a five-minute single-use
login flow and 24-hour report visibility. Sessions expire after 30 minutes idle
or four hours absolute. Capacity accounting conservatively includes idle sessions
until their absolute expiry. TTL deletion is asynchronous; read paths enforce
expiry independently. Report list/count/cursor operations always filter by owner.
Capacity checks use projected metadata, not report bodies, in transactions.
At capacity a write can read up to 2,049 metadata documents; these reads are billed.
Database-conditioned IAM is database-wide, not collection-level authorization.

## GitHub verification proposal

Commit the reviewed changes without a co-author trailer using
`Prepare live cloud verification`, push a `codex/` branch and open a synthetic
verification PR. The new `examples/normalized-plans/live_verification.json`
contains only fabricated facts and exercises all eight rule IDs. Dispatch the
trusted-main `Review synthetic PR fixtures` workflow for that PR and verify its
managed bot comment, exact reviewed SHA, neutral check and repeat update behavior.
The workflow must retain its existing limited permissions and must not execute PR
code or obtain cloud credentials. Merge only the reviewed passing source before
the protected deployment workflow promotes its immutable image.

The connector rejected branch creation with integration permission 403; no branch
was created by that attempt. Authenticated Git transport and the GitHub browser UI
are the fallback. No broader GitHub App permissions are needed for this test.

## Bounded hosted verification

After explicit approval for new paid resources and IAM:

1. Obtain the reviewed OAuth client, secret and allowed operator privately.
2. Promote the trusted image, review the final private plans and reject any
   unrelated mutation or deletion before apply.
3. Apply the approved Eventarc and portal configurations. Verify anonymous
   invocation rejection, Firestore indexes/TTL and the exact image digests.
4. Publish matching synthetic source objects and verify receipt persistence,
   updated twelve-document corpus, unchanged-content reuse and expired lease
   recovery. Never run manual ingestion concurrently with event indexing.
5. Complete a real Google sign-in through the private proxy, create/read/export
   synthetic reports, test history filters, logout and session/report persistence.
6. Request at most six cloud analysis reports during this verification. Stop and
   investigate dependency failures rather than looping model calls indefinitely.
   Record observed usage and latency without raw prompts, tokens or personal data.
7. Record hosted PR and cloud evidence separately from local SDK/model doubles.
   Restore disabled billing after verification unless the owner explicitly elects
   to keep the hosted demo active.

Zero minimum instances and bounded requests reduce usage; they are not a hard
spending cap. Storage, Firestore, model calls, Pub/Sub and Eventarc can incur
charges while billing is active, including when the services are idle.

## Preparation checks

The full Python quality gate passed: 493 tests in 16.07 seconds, 97.19%
normalization/policy coverage, strict mypy on 70 source files and all Ruff,
schema/corpus drift checks. The initial expanded infrastructure checks passed
19 mock cases and Checkov reported 53 passed, zero failed, four existing documented
exceptions. The final portal validation and all four mock cases passed again
after additional variable constraints; the Firestore adapter reached 96.36%
branch coverage. These results do not establish live readiness.

References: [authenticated Cloud Run proxy](https://docs.cloud.google.com/run/docs/authenticating/developers),
[official proxy Host rewriting](https://github.com/GoogleCloudPlatform/cloud-run-proxy/blob/main/main.go),
[Google OAuth web-server flow](https://developers.google.com/identity/protocols/oauth2/web-server),
[Firestore transactions](https://docs.cloud.google.com/firestore/native/docs/manage-data/transactions),
and [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy).
