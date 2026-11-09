# Cost controls, rollback and cleanup

An isolated portfolio project has been created with owner approval. The deployment
remains active for development; cleanup has not been executed. Its private resource
inventory is kept outside version control. Remove the dedicated resources when the
portfolio work is finished, following the order below.

## Cost drivers and controls

| Service | Cost driver | Configured control |
| --- | --- | --- |
| Cloud Run | Requests, CPU, memory and egress | Request-based CPU, minimum zero instances, maximum two by default, concurrency eight, request timeout 30 seconds |
| Firestore | Document operations, vector indexes, storage and TTL deletions | Dedicated synthetic database, fixed 768-dimensional index, report expiry field prepared |
| Cloud Storage | Stored versions, operations, soft-deleted data and egress | Private synthetic source bucket, 30-day source lifecycle, versioned state history lifecycle |
| Artifact Registry | Image storage and transfers | Immutable tags, old untagged-image deletion after 14 days, keep ten recent versions |
| Logging and Monitoring | Retained logs, queries, alerts and notifications | Content-free application telemetry, automatic request-URL log exclusion for this service |
| Embeddings and Gemini | Input/output tokens and model requests | Explicit synthetic CLI execution, text/token limits, shared RPC deadlines and bounded attempts; no background ingestion or generation |

Immutable tagged images are retained until deliberately removed; the untagged
cleanup rule does not cap total registry storage. Soft-deleted objects can continue
to incur retention costs after logical deletion. Firestore TTL is asynchronous and
does not guarantee immediate deletion. A report writer must set `expires_at` before
the configured TTL policy can expire reports; that writer is not implemented yet.

Set a project-filtered Cloud Billing budget and notification thresholds before
provisioning. Budget alerts do not impose a spending cap. Instance settings reduce
exposure but do not bound all charges, especially storage, egress and later model
calls. Review current pricing and applicable quotas for the approved project and
region. This repository does not claim a fixed monthly price or a free deployment.

The optional `terraform/project` configuration provides monthly alerts at 50%,
90% and 100% of an approved amount in the billing account's currency. It excludes
promotional and other credits from the usage calculation so credit consumption is
visible even when net billed cost is zero. A deployment may use a lower instance
limit than the default, such as one maximum instance for a small portfolio demo.

The current demo uses a maximum of one Cloud Run instance and a monthly alert of
IDR 180,000, approximately the approved USD 10 target when configured. The billing
account uses IDR, so exchange-rate movements change the USD equivalent. The budget
amount, project filter, gross-usage calculation and thresholds were verified using
the Billing Budgets API. Notification delivery has not been tested. No automatic
shutdown is configured, and the alert does not stop spending.

The knowledge CLI has now made live embedding and Gemini requests during
verification. Ten synthetic Markdown objects and ten vector records remain stored.
Identical re-ingestion reuses vectors and performs reads without embedding or
document writes. Generated source objects retain the existing lifecycle and
soft-delete behavior. See the [retrieval limits](retrieval-and-explanations.md)
before repeating metered evaluations. The Cloud Run health service itself does
not invoke models or retrieve knowledge yet.

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
