# Infrastructure security exceptions

Checkov is pinned to 3.4.3. The following resource-level exceptions are explicit;
there is no global skip list. Revisit them before using real data or expanding access.

| Check | Resources | Decision and remaining risk |
| --- | --- | --- |
| CKV_GCP_62: bucket access logging | Bootstrap state and synthetic-runbook buckets | Legacy Cloud Storage access-log delivery requires an additional log bucket and analytics-writer grant. It is omitted from this small demo. Administrative audit logs remain available, but object read/write auditing is incomplete unless Data Access audit logging is separately enabled and reviewed for cost and metadata retention. Both buckets enforce public access prevention, uniform access and versioning. |
| CKV_GCP_84: registry customer-managed encryption | Container repository | Google-managed encryption at rest is used. A dedicated Cloud KMS key adds operational work and metered resources for synthetic images. This configuration does not provide customer-managed key control. |
| CKV_GCP_125: GitHub OIDC condition | Parameterized WIF provider module | Checkov 3.4.3 cannot resolve the module's interpolated subject to a literal repository name, including when a variable file is supplied. Terraform mock plans check the fully evaluated repository name, immutable repository and owner IDs, main branch, protected environment subject, exact workflow and manual event, joined without an OR bypass. No live token exchange has been verified. |

## Identity boundaries

The API runtime has no project data roles while it only serves liveness. The image
deployer can write its Artifact Registry repository, update its existing Cloud Run
service and act as its runtime identity. It cannot create infrastructure, edit IAM,
read Terraform state or impersonate the ingestion identity through these grants.

The ingestion identity has bucket-scoped object access and a custom Firestore entity
role conditioned on one named database. It has no model, IAM or index-administration
permissions. Human impersonation permissions are not granted automatically.

Firestore server libraries enforce IAM and bypass client Security Rules. The IAM
condition isolates the named database; it does not enforce collection-level access.
Client rules deny all direct client reads/writes. Collection allowlists for
`knowledge_chunks` and `analyses` must be enforced in the later application adapters.
This is an explicit limitation relative to a collection-level authorization goal.

## Logging boundaries

Application request logs contain generated request IDs, a fixed route category,
method category, status and elapsed time. They omit bodies, arbitrary paths, query
strings, incoming identifiers, headers and exception text. Uvicorn URL access logs
are disabled. A service-specific Logging exclusion avoids retaining automatic
Cloud Run request URLs in the default log bucket. Built-in request metrics,
application logs, system logs and administrative audit logs remain available.

Additional organization-level sinks can independently export automatic request
logs. Review them before deployment; this project cannot guarantee their retention
behavior. Do not put credentials in URLs.

## References

- [Firestore server-library IAM](https://docs.cloud.google.com/firestore/native/docs/security/iam)
- [Firestore per-database IAM conditions](https://docs.cloud.google.com/firestore/native/docs/manage-databases#configure_per-database_access_permissions)
- [GitHub OIDC federation and immutable numeric claims](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines)
