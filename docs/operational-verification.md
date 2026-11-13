# Live operational verification

The owner-approved 2026-11-13 window completed the bounded portal, notification,
Firestore fencing and image-promotion checks prepared in the
[operational procedure](operational-readiness.md). All analysis inputs were
synthetic. Billing was disabled again, the project was retained and local proxies
were stopped. Budget email receipt remains unverified.

See the [content-free evidence](evaluations/operational-live-2026-11-13.json).
Account addresses, credentials, session cookies, report IDs, raw cloud responses,
private Terraform plans/state and mailbox screenshots remain outside version
control. The interrupted window resumed within its original approved request
budget; the deployment smoke, fencing probe and health requests were not repeated.

## Trusted deployment

Source `88602fbba9553e486be4b7f123dcd62b278d6a1b` includes the application wording
correction published in v1.0.1 and the operational verification tooling.
[Source CI](https://github.com/mdaninas/terramind-gcp/actions/runs/43372714959)
passed. The protected
[deployment workflow](https://github.com/mdaninas/terramind-gcp/actions/runs/43377459596)
passed with the existing required development-environment review intact.
Application/API version is 1.0.1. This did not move the published release tag.

The API, Eventarc receiver and portal were Ready on the same immutable image:

```text
sha256:813cecbd0b78fa26b6f35a137018cf03fa0b22e825fd8791ce12c60a252d59e6
```

Audited plans retained private invocation, zero minimum and one maximum instance
per service, and internal receiver ingress. No cloud IAM expansion was needed.
The approved notification configuration, project purpose label `demo` and budget
display name `Terramind monthly alert` were applied separately from image promotion.
Existing amount, thresholds, scope and default budget recipients were preserved.

## Analysis and portal results

Exactly 23 of 23 approved analysis submissions were used:

| Check | Verified result |
| --- | --- |
| Protected core smoke | One HTTP 201 analysis in 9.24 seconds, four findings preserved, validated Gemini advisory, eight sources and saved HTML/JSON/Markdown reads |
| No-change portal samples | 22 successful reports, 21 for owner A and one for owner B, with no retrieval or model generation requested |
| Real Google authentication | Both controlled accounts completed Google login; scopes remained `openid` and `email` |
| Owned history | A had 21 reports across two pages; B had one report on one page; stable totals, unique IDs and disjoint histories passed |
| Report access | Both owners could read their own HTML/JSON/Markdown; cross-owner reads returned 404 for all three formats |
| Access guards | Anonymous history returned 401; owner query override returned 400 |
| Session closeout | Both sessions logged out and subsequent history reads using the revoked cookies returned 401 |

The read-only portal checker used 18 of its maximum 32 GET requests and submitted
zero analyses. The 22 no-change reports were created separately under the shared
submission ledger. No submission was repeated to force success. This dataset
verifies the tested ownership and cursor boundaries, not large-scale capacity.
Earlier core/Storage/Database advisory results remain in the
[2026-11-11 record](advisory-verification.md); those scenarios were not all rerun.

## Notifications and effective policies

A real Google Cloud Monitoring email for the temporary synthetic 2xx policy was
received by the approved operator at 13:36 Asia/Jakarta. Its project, policy and
request-count metric matched. Three approved authenticated health GETs were used.
This verifies the email delivery path; it does not test the normal server-error
threshold. The temporary probe policy was removed, while the permanent operator
channel and normal server-error attachment were retained.

The existing IDR 180,000 monthly project budget retained its 50%, 90% and 100%
current-spend thresholds, credit exclusion and default billing/project recipients.
The operator email channel attachment was read back successfully. A focused
recipient-mailbox search did not find a budget email. Budget receipt remains
unverified, as allowed by the approved window. No spend was forced and no budget
threshold was reduced to trigger delivery. These alerts are not a hard cost cap.

Effective policies for `storage.publicAccessPrevention`, `run.allowedIngress`
and `iam.allowedPolicyMemberDomains` were read using existing access. No policy
was changed. These three reads are not an exhaustive organization-policy audit.

## Firestore fencing scope

One probe used the real ingestion coordinator against fresh, isolated
`verification_*` collections in the existing Firestore database. Active-lease
rejection, competing stale/current commits, stale-commit fencing, current commit
recording and duplicate receipt skipping passed. Cleanup of the three owned
document references was verified. No chunks were staged, and there were no model
or embedding calls. This checks the Firestore adapter's transaction fencing; it
does not establish a new concurrent end-to-end Eventarc/embedding test. Earlier
real Eventarc delivery and replay results remain in the
[hosted integration record](live-integrations-verification.md).

## Final closeout and remaining observation

The temporary second account was removed from the portal allowlist and OAuth
Testing users. The original operator remained, with unchanged OAuth scopes.
Removing a test user does not reset Google's lifetime user-cap accounting.
Both portal sessions were revoked and workspace-owned listeners on ports 8091,
8092 and 8093 were stopped. The isolated Firestore probe data and temporary
Monitoring policy were removed; the permanent alert channel was retained.

At 07:28 UTC (14:28 Asia/Jakarta), final cleanup independently read
`billingEnabled=false` and an empty billing-account association. The console
also showed that the project has no billing account. The project was retained;
resource deletion and future data recoverability are not claimed. Accrued charges
can appear later. Future paid execution needs new owner approval.

The remaining observation is actual budget email receipt under a genuine
threshold event. Configuration is verified, delivery is not. No extra paid test
is scheduled to force this outcome.
