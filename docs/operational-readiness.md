# Operational verification preparation

The separately approved [live window](operational-verification.md) subsequently
completed on 2026-11-13 using source `88602fb`. Image promotion, two-account
pagination/ownership, real-Firestore sandbox fencing and Monitoring email delivery
passed. Budget email receipt remains unverified. Billing is disabled again.
The preparation snapshot below records what was known before execution; its
pending statuses are historical. Procedures remain guidance for a newly approved
future window, not authorization to repeat the completed tests.

Prepared locally on 2026-11-13. The owner subsequently authorized commit and push
of this preparation. Publication does not authorize the proposed cloud window.
No release, billing change, cloud IAM change, real Terraform plan/apply,
notification, cloud analysis or Firestore probe was performed during preparation.
Historical cloud results remain in the [live advisory record](advisory-verification.md).

Published release [v1.0.1](https://github.com/mdaninas/terramind-gcp/releases/tag/v1.0.1)
points to `35192b8ffc40d0a047184ae2311a6bc2e59e5a1e`. Its application wording
corrections had not yet been promoted at preparation time. The then-current hosted
digest is `sha256:d37a72be12c3f460e9ba9857936d94f7ebdd76edf764366ec545d88afe6bdb06`.
Billing had last been independently verified disabled on 2026-11-11, with the project
retained. This preparation does not establish a fresh cloud inventory.

## Preparation review package (before execution)

| Remaining check | Prepared implementation | Live status |
| --- | --- | --- |
| Documentation consistency | Historical release results separated from subsequent PR, Eventarc, portal and advisory verification; published release links recorded | Documentation prepared locally |
| Monitoring notifications | Optional email channel, existing-channel validation, normal server-error policy attachment, disabled-by-default synthetic delivery probe | Not applied; recipient and delivery unverified |
| Budget notifications | Up to five approved same-project email channels; existing billing/project recipients retained | Not applied; budget email receipt unverified |
| Portal owner isolation and larger history | Read-only checker for two authenticated sessions, 21 no-change reports for A and one for B, cursor traversal and exports | Local HTTP/store checks passed; Google/Firestore run pending |
| Competing ingestion workers | Opt-in sandbox using the real coordinator, two worker commits and fresh synthetic collections | Local transaction double passed; real Firestore run pending |
| Runtime wording correction | Image-only Terraform plan checker and promotion/rollback procedure | No image built or promoted in this preparation |

See the [content-free preparation record](evaluations/operational-readiness-2026-11-13.json).
Prepared procedures are not evidence of a successful live run.
The [synthetic review request](operations/verification-window.example.json) records
the proposed bounds with approval explicitly false. Copy it to ignored operator
storage before replacing synthetic values; it is not an execution credential.

## Approval and inputs for a future window

Before any cloud execution, the owner must review and approve the concrete diff,
source commit, notification recipient, second Google test account, private
Terraform plans and bounded test window. Publication was authorized separately
after local review. Account addresses, OAuth data, tokens,
session cookies, state, plans, raw cloud responses and screenshots with account
details stay in ignored operator storage, never in public evidence.

The second account needs an explicit portal allowlist entry and membership in the
existing OAuth testing application's test users. Both Google sign-ins are completed
by the users. The existing operator can run the authenticated Cloud Run proxy for
both browser profiles; a second Cloud Run invoker grant is not needed for this
test. Review effective organization policies read-only before deployment, including
public-access prevention, allowed identities and Cloud Run ingress restrictions.
Insufficient access leaves that inspection unverified; do not change those policies
to complete a test.

Proposed window, requiring new approval:

- At most 23 analysis submissions: one default protected deployment smoke and
  22 no-change portal samples (21 for A, one for B). Keep `verify_policy_packs`
  false for this window. No-change reports require no retrieval or model calls.
- No extra analyses to force success. An ambiguous timeout still consumes a
  submission; stop rather than repeat a possibly completed POST. Respect the
  existing six-per-minute admission limit and `Retry-After` response.
- At most 32 GET requests in the portal checker, four history pages per owner,
  eight-second request timeouts and one invocation. There are no write routes in
  this checker.
- One ingestion sandbox invocation, no embeddings or model calls, three newly
  owned documents and verification of their cleanup. A failed cleanup is a failed
  verification, even when fencing passed.
- One temporary notification policy, at most three authenticated health GETs,
  and a 15-minute delivery-observation window. No VM or artificial server failure
  is required. Budget email delivery may remain pending beyond that window.
- Zero minimum and one maximum instance per service. These are not a hard cost
  cap. Restore disabled billing, independently verify an empty billing association,
  and stop both local proxies at the end, including after failures.

Any increase, rerun or additional model scenario requires a new decision. Preserve
failures and stop at the bounds.

## Notifications

The dev root now accepts `notification_email` (null by default). The address is
sensitive in Terraform output and remains in private state. Alternatively, supply
approved existing resource names in `notification_channels`. Names must belong to
the configured project. The server-error policy retains its original 5xx condition.

After approval, copy the existing private variables, preserve their runtime and
IAM settings, and set only the approved recipient/channel values. Run a saved
plan with the existing backend. Review channel creation and policy attachment as
a separate change from the image-only promotion. No IAM grant is added by these
configuration changes; an operator with existing appropriate access must apply
the reviewed plan. Do not apply a synthetic example file.

The dev output `operator_notification_channel` supplies the optional channel
resource name. Add that name to the separate project root's private
`monitoring_notification_channels` list and review its saved plan. Keep the
existing billing account, currency, amount, project filter, thresholds and default
recipients. Stop if the plan would relink billing, replace the project or change
unrelated settings. Confirm through a read that the selected channel is an email
channel and that both policies reference the expected resource name.
At preparation time, the released project configuration also contained unapplied
display-name and purpose-label wording corrections. If such changes appear in a refreshed
plan, identify them explicitly for separate review; do not include them silently
in a notification-only approval.
If an API returns a project-number resource name, first confirm the number-to-ID
mapping read-only, then use its equivalent `projects/PROJECT_ID/notificationChannels/CHANNEL_ID`
name in these variables. Validation deliberately requires the approved project ID.

Email channel configuration alone does not prove delivery. For a bounded delivery
test, the reviewed dev plan can temporarily set `enable_notification_probe=true`.
It creates an independently labeled policy for successful 2xx traffic to the
existing API service. After applying only that approved plan, issue the approved
health GETs, wait up to 15 minutes, and record both the Monitoring incident and
recipient confirmation. This checks the delivery path; it does not exercise the
production server-error threshold. Set the flag back to false, review the plan
removing only the temporary policy, and verify removal after approval.
The built-in metric counts all 2xx requests to that service, so another successful
request can also satisfy this temporary condition. It is not a route-specific
health metric.

For budget alerts, inspect the existing budget and wait for a genuine threshold
notification to the approved recipient. Do not spend money or weaken thresholds
to force an email. Monitoring receipt and budget receipt are separate results;
keep budget delivery pending until a real budget notification is received.

Google documents [email channels and channel testing](https://docs.cloud.google.com/monitoring/support/notification-options#test)
and [budget email recipients](https://docs.cloud.google.com/billing/docs/how-to/budgets-notification-recipients).
The pinned provider's [channel](https://registry.terraform.io/providers/hashicorp/google/8.10.0/docs/resources/monitoring_notification_channel)
and [budget](https://registry.terraform.io/providers/hashicorp/google/8.10.0/docs/resources/billing_budget)
schemas define the prepared fields. No message is sent during local checks.

## Two-account portal and pagination

Use two separate browser profiles on the same approved loopback origin
`http://127.0.0.1:8091`. Each user completes Google login. Under the approved
submission budget, create only the packaged no-change sample: 21 reports for A
and one for B. Keep two owned report IDs for the checker. Let reports expire
under the existing 24-hour policy; do not delete pre-existing reports.

The checker requires each profile's portal session cookie, supplied privately in
process environment variables. The owner obtains these values locally; they
must never be pasted into chat, command arguments, public notes or screenshots.
In PowerShell, hidden entry avoids putting values into command history:

```powershell
$env:TERRAMIND_SESSION_A = [Net.NetworkCredential]::new('', (Read-Host 'Session A' -AsSecureString)).Password
$env:TERRAMIND_SESSION_B = [Net.NetworkCredential]::new('', (Read-Host 'Session B' -AsSecureString)).Password
uv run --locked python scripts/verify_portal_access.py --url http://127.0.0.1:8091 --report-a <owned-report-A> --report-b <owned-report-B>
Remove-Item Env:TERRAMIND_SESSION_A, Env:TERRAMIND_SESSION_B
```

The IDs are generated UUIDs, not account identifiers. Supply actual UUID arguments
in place of the angle-bracket placeholders. The checker only sends cookies to
the explicit loopback IPv4 proxy and does not follow redirects. It validates
complete cursor traversal, stable totals, unique report IDs, disjoint histories,
both owners' HTML/JSON/Markdown reads, cross-owner 404 responses, anonymous 401
and rejection of an owner query override. The no-change dataset must fit within
80 reports per owner. Expired sessions, concurrent writes or existing larger
datasets fail the check; inspect the cause rather than automatically retrying.

Only stage, counts and pass/fail flags enter
`artifacts/operational-readiness/portal-summary.json`. Report payloads, IDs and
cookies are not emitted. Log out both profiles after testing.

## Ingestion fencing

This command is safe for local preparation and does not create a cloud client:

```sh
uv run --locked python scripts/verify_ingestion_fence.py --project terramind-demo --database terramind-dev
```

It returns `prepared`, not `passed`. Only after approval, replace the synthetic
project with the approved project and add `--execute`. Use existing authorized
Application Default Credentials, never a service-account key. The operator needs
Firestore access to the fresh verification collections; do not expand runtime IAM.

The probe runs the real coordinator against random `verification_*` collection
names in the approved existing database. It confirms active-lease rejection,
controlled expiry in its own sandbox, stale-release protection, competing stale
and current commits, receipt replay, and verified cleanup of exactly its three
document references. It does not select `ingestion_control/corpus`,
`knowledge_chunks` or normal ingestion receipts for reads/writes. No corpus
chunks are staged. This is a real-Firestore adapter fencing check, not a new
Eventarc delivery or embedding evaluation. Those boundaries must remain in the
result. Prior end-to-end Eventarc delivery is recorded separately.

Failure details remain private. The content-free result is saved under
`artifacts/operational-readiness/ingestion-fence-summary.json`. If cleanup fails,
stop and retain the exact three owned references from the private
`artifacts/operational-readiness/private/verification_*.json` manifest for review;
the manifest is written before any test mutation. Never run a
recursive delete or touch existing runtime collections to clear the test.

## Image promotion and rollback

For any future promotion, choose an exact reviewed trusted source commit.
The published v1.0.1 tag identifies
`35192b8ffc40d0a047184ae2311a6bc2e59e5a1e`; the subsequent live source and image
are recorded in the [execution results](operational-verification.md).
The existing main-only workflow builds its own dispatch SHA, so
record that SHA explicitly. It must contain the intended release correction.
Do not weaken environment review or WIF to dispatch from an untrusted ref.

Use the existing protected workflow once with `verify_policy_packs=false` after
approval. It builds and publishes an immutable image and updates only the API.
Record the resulting full image URI. In private dev and portal variables,
preserve all existing values and change only `container_image` or `image` to that
same digest. Notification and second-account configuration changes must already
have been separately reviewed and reconciled; they will be rejected by the
image-only checker if mixed into promotion.

For each root, initialize its existing backend and save a normal, refreshed plan
under ignored `artifacts/operational-readiness/`. Never use a targeted plan or
`-refresh=false` to hide drift. Export the private plan JSON with `terraform show
-json` and run:

```sh
uv run --locked python scripts/check_promotion_plan.py --plan artifacts/operational-readiness/dev-plan.json --root dev --project APPROVED_PROJECT --image REVIEWED_IMAGE_URI
uv run --locked python scripts/check_promotion_plan.py --plan artifacts/operational-readiness/portal-plan.json --root portal --project APPROVED_PROJECT --image REVIEWED_IMAGE_URI
```

The checker requires the full known service set, exact project/location/service
identity and digest. It permits image changes and CLI metadata reconciliation;
it rejects unresolved configuration changes, unrelated mutations, creation,
deletion, replacement, altered environment, scaling, ingress or IAM settings.
Computed provider status fields are ignored. A pass is a review aid, not apply
authorization. Keep the complete private human-reviewed plan with the approval.

Apply only the individually approved saved plans. Confirm all three services are
Ready on the same digest, minimum zero and maximum one instance, with unchanged
invoker policies and internal Eventarc ingress. Check authenticated API health
reports version 1.0.1, then manually verify portal login, the corrected visible
wording, existing history and logout. No extra model analysis is needed for UI.

For an image rollback, set both image variables to the retained prior digest,
repeat the full plan/guard/review sequence, and use the approved saved plans.
Do not reset Terraform state or use mutable tags. Image rollback does not undo
data writes or restore billing state.

## Evidence and closeout

Keep a private ledger before each request, counting ambiguous submissions. Record
the actual source SHA, image digest, timestamps, stages/counts, independently read
billing result, recipient-confirmed delivery flags and pending checks. A failed
test remains failed. Do not turn a prepared command, configured channel or local
test result into a live-success claim.

At closeout, remove the temporary notification policy through its approved plan,
revert the second account if access was temporary, log out both users and clear
session environment variables. Independently verify the sandbox is empty. Disable
billing using the approved shutdown procedure, read back `billingEnabled=false`
and an empty association, and stop the known workspace-owned proxies. Keep the
project. Publish only content-free evidence after review. Cloud execution requires
approval separately from publication of this preparation.
