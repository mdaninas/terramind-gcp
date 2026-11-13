# Cost controls, rollback and cleanup

Current update, 2026-11-13: the approved operational window finished and
**billing is disabled again**. Final cleanup at 07:28 UTC (14:28 Asia/Jakarta)
independently confirmed `billingEnabled: false` and no billing-account association.
The console also showed that the project has no billing account. The project is
retained; resource deletion and future data recoverability are not claimed. See
the [latest verification](operational-verification.md) and
[evidence](evaluations/operational-live-2026-11-13.json). All workspace-owned
proxies on ports 8091, 8092 and 8093 were stopped.

Exactly 23 approved analysis submissions were used: one validated core advisory
smoke and 22 no-change portal samples without retrieval/model generation. Both
Google owners, cross-owner report rejection and multi-page history passed.
One isolated real-Firestore fencing probe cleaned its three owned references.
Monitoring email was received. Temporary access and the probe policy were removed,
both sessions were revoked and the permanent notification channel was retained.
The existing budget's amount, scope and thresholds were preserved; actual budget
email receipt remains unverified. All three private services retained zero minimum
and one maximum instance on the promoted image. Accrued charges can appear later.

## Historical advisory window

The 2026-11-11 follow-up used six of six approved analysis submissions: four validated
advisories and two policy-preserving fallbacks. The final strict smoke passed
all three scenarios. Image updates and CLI metadata reconciliation created or
destroyed no resources and did not expand IAM. All three services retained zero
minimum and one maximum instance. Real Google login on the updated portal passed;
no further portal analysis was submitted. Accrued charges can appear later.

## Historical integration window

The 2026-11-10 window applied the reviewed Eventarc and durable portal resources. Each of
the three Cloud Run services retained zero minimum and one maximum instance.
Six analysis submissions included two validated advisories, three safe fallbacks
and one no-change sample without retrieval/model calls. Twelve canonical source
documents, their object generations, one obsolete-path synthetic test object,
twelve knowledge chunks and four portal reports were observed before shutdown.
Actual accrued charges can appear after shutdown; no zero-cost claim is made.

## Earlier billing shutdown

An isolated Terramind project was created and deployed with owner approval.
On 2026-11-10 (Asia/Jakarta), the owner chose to disable billing and retain the
project. The Google Cloud console confirmed `Billing is disabled` for the
Terramind project and showed a successful disable notification. See the
[content-free shutdown record](evaluations/billing-disabled-2026-11-10.json).

Billable services stop when project billing is disabled. This action does not
establish that each resource was deleted or that stored data will be recoverable:
Google may remove some resources. Charges accrued before disabling billing may
still appear later. See [Google's billing documentation](https://docs.cloud.google.com/billing/docs/how-to/modify-project#disable_billing_for_a_project).
The shared billing account and other projects were not changed.

No Terraform apply/destroy, project deletion or individual resource deletion was
performed in this shutdown. The private inventory and screenshot are retained
outside version control. Billing was changed in the console, so Terraform's
earlier project configuration/state may no longer match the billing association.
Review any future plan; re-enabling billing or resuming paid workloads needs
explicit owner approval. The resource-specific controls and usage estimates below
describe the earlier deployment. The cleanup order remains guidance for a future
full deletion, not a record of executed cleanup.

## Cost drivers and controls

| Service | Cost driver | Configured control |
| --- | --- | --- |
| Cloud Run | Requests, CPU, memory and egress | Request-based CPU, minimum zero instances, maximum two by default, concurrency eight, request timeout 30 seconds |
| Firestore | Document operations, vector indexes, storage and TTL deletions | Dedicated synthetic database, fixed 768-dimensional index, active report expiry policy; deployed writer enforces 24-hour expiry |
| Cloud Storage | Stored versions, operations, soft-deleted data and egress | Private synthetic source bucket, 30-day source lifecycle, versioned state history lifecycle |
| Artifact Registry | Image storage and transfers | Immutable tags, old untagged-image deletion after 14 days, keep ten recent versions |
| Logging and Monitoring | Retained logs, queries, alerts and notifications | Content-free application telemetry, automatic request-URL log exclusion for this service |
| Embeddings and Gemini | Input/output tokens and model requests | Explicit synthetic CLI execution; deployed API admits one analysis at a time and six per minute per process; token/RPC limits, no background generation |

Immutable tagged images are retained until deliberately removed; the untagged
cleanup rule does not cap total registry storage. Soft-deleted objects can continue
to incur retention costs after logical deletion. Firestore TTL is asynchronous and
does not guarantee immediate deletion. The new report writer sets `expires_at` and
refuses expired reads; cloud report creation and reads are verified. Process-local rate
limits reset on restart and are multiplied by additional instances.

Set a project-filtered Cloud Billing budget and notification thresholds before
provisioning. Budget alerts do not impose a spending cap. Instance settings reduce
exposure but do not bound all charges, especially storage, egress and model
calls. Review current pricing and applicable quotas for the approved project and
region. This repository does not claim a fixed monthly price or a free deployment.

The optional `terraform/project` configuration provides monthly alerts at 50%,
90% and 100% of an approved amount in the billing account's currency. It excludes
promotional and other credits from the usage calculation so credit consumption is
visible even when net billed cost is zero. A deployment may use a lower instance
limit than the default, such as one maximum instance for a small synthetic demo.

The current demo uses a maximum of one Cloud Run instance and a monthly alert of
IDR 180,000, approximately the approved USD 10 target when configured. The billing
account uses IDR, so exchange-rate movements change the USD equivalent. The budget
amount, project filter, gross-usage calculation and thresholds were verified using
the Billing Budgets API. Budget email receipt remains unverified. No automatic
shutdown is configured, and the alert does not stop spending.

The approved [operational window](operational-verification.md) configured the
operator email channel and attached it to the existing budget and normal
server-error policy. A temporary 2xx probe produced a real Monitoring email and
was then removed. This checks Monitoring delivery, not the server-error threshold
or budget delivery. A focused mailbox search found no budget notification.
No spend was forced and no threshold was reduced to trigger an email.

The knowledge CLI has now made live embedding and Gemini requests during
verification. Ten synthetic Markdown objects and ten vector records remain stored.
Identical re-ingestion reuses vectors and performs reads without embedding or
document writes. Generated source objects retain the existing lifecycle and
soft-delete behavior. See the [retrieval limits](retrieval-and-explanations.md)
before repeating metered evaluations. The deployed analysis API invokes retrieval
and Gemini only for admitted analysis requests. Health, preview and report reads
do not trigger model generation. A live workflow analysis took 10.898 seconds;
independent verification reused that saved report without another model call.

## Worked usage estimate

Prices checked on 2026-11-10. This illustrative USD calculation uses public
on-demand list prices before free allowances, credits, tax or currency conversion.
It is a component estimate, not a bill forecast or spending limit.

Assume 100 analyses in a month, each with one Gemini 3.5 Flash global request,
5,000 uncached input tokens and 1,500 total billed output tokens (including reasoning).
Assume 30 billed instance-seconds per analysis including startup/shutdown overhead,
1 vCPU, 0.5 GiB RAM and six authenticated HTTP requests per analysis.
These are planning assumptions, not measurements of every report.

| Component | Calculation | Estimated USD |
| --- | --- | --- |
| Gemini input | 100 x 5,000 / 1,000,000 x $1.50 | 0.75000 |
| Gemini output | 100 x 1,500 / 1,000,000 x $9.00 | 1.35000 |
| Cloud Run CPU | 100 x 30 x $0.000024 | 0.07200 |
| Cloud Run memory | 100 x 30 x 0.5 x $0.0000025 | 0.00375 |
| Cloud Run requests | 600 / 1,000,000 x $0.40 | 0.00024 |
| Selected component subtotal | Sum before discounts and omitted services | **2.17599** |

Model rates are from [Google model pricing](https://cloud.google.com/model-garden/pricing)
(standard global service, without caching or batch discounts). Compute rates are
from [Cloud Run request-based pricing](https://cloud.google.com/run/pricing).
Actual billed model output can include reasoning tokens beyond visible prose;
retries and longer inputs change usage.

The subtotal excludes embeddings, Firestore document/vector-index reads and TTL
deletes, database/index storage, object versions and soft deletes, image storage,
network transfer, logging/monitoring and deployment activity. They add to the bill.
A four-rule report makes up to four query embeddings and retrieves up to three
chunks per rule. Re-indexing changed documents adds embedding and write operations.
Firestore vector queries can bill both returned documents and scanned index entries;
see [Firestore billing](https://firebase.google.com/docs/firestore/pricing).

Image storage persists while Cloud Run is idle. The
[Artifact Registry pricing page](https://cloud.google.com/artifact-registry/pricing)
lists a shared 0.5 GiB allowance and storage charges above it; immutable tagged
images are retained until explicitly removed. State/runbook object generations
also remain subject to [Cloud Storage pricing](https://cloud.google.com/storage/pricing).
Free allowances can already be consumed by other projects on the billing account.
Use the actual billing account's IDR SKUs and current usage to forecast its bill.

For a zero-analysis night, no application background job requests Gemini or
embeddings. Retained storage and other metered services can still incur charges.
The instance cap and alert budget do not guarantee a maximum monthly cost.

## Rollback

Keep the previous verified container digest. Set `container_image` to that digest,
review a private Terraform plan and obtain approval before applying it. Schema and
database changes need their own recovery review; an image rollback does not undo
data changes. The application never applies or rolls back infrastructure itself.

## Cleanup order

1. Confirm the exact project and resource prefix and obtain approval for deletion.
2. Disable future deployment jobs or revoke their trust after reviewing active use.
3. Set `deletion_protection=false` in the dev variables, review and approve the
   protection-change plan, then apply that reviewed plan. Both Cloud Run and
   Firestore must have protection disabled in actual Terraform state before destroy.
4. Back up any required synthetic reports and inspect all runbook object versions.
   Bucket `force_destroy=false` intentionally blocks deletion of nonempty buckets.
   Empty only the approved bucket and versions after reviewing them.
5. Create and review a private destroy plan:

   ```sh
   terraform -chdir=terraform/environments/dev plan -destroy -out="$PRIVATE_PLAN_DIR/destroy.plan"
   ```

6. Apply the reviewed destroy plan only after explicit approval. Confirm removal
   through resource lists and billing views; do not infer removal from an attempted
   command. Project APIs intentionally remain enabled.
7. Retain the state bucket until the environment's state and history are no longer
   needed. Archive them privately. If bootstrap state was migrated into that bucket,
   remove the local `backend.tf` and use `terraform init -migrate-state` to migrate
   bootstrap back to protected local state before removing the backend bucket.
   Keep a separate private backup during this operation.
8. Review state-bucket object generations and remaining Terraform locks. After
   approved state archival, explicitly remove the approved object versions, then
   review a separate bootstrap destroy plan. Never enable `force_destroy` merely
   to bypass this review. Verify soft-delete retention and remaining storage charges.
9. If a dedicated project was created with `terraform/project`, preserve its state
   privately before removing its backend bucket. Set its `deletion_policy` to
   `DELETE` only when final shutdown is approved, review the change and a destroy
   plan, then remove the project-scoped budget and project. Do not delete a shared
   lab project. Verify project lifecycle state and billing status after shutdown;
   do not claim that all charges stop instantly.

Never commit or upload private plan files, state, tokens or credentials as build
artifacts. Keep `PRIVATE_PLAN_DIR` outside source control and clean it up under the
operator's normal secure file-handling procedure.

## References

- [Google Cloud budgets and alerts](https://docs.cloud.google.com/billing/docs/how-to/budgets)
- [Cloud Run pricing](https://cloud.google.com/run/pricing)
- [Firestore pricing](https://cloud.google.com/firestore/pricing)
- [Cloud Storage soft delete](https://docs.cloud.google.com/storage/docs/soft-delete)
