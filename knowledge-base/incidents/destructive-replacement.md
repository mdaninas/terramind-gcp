---
doc_id: inc-destructive-replacement
title: Synthetic incident destructive database replacement
version: 1.0
synthetic: true
---
# Fabricated destructive replacement incident

This fabricated tabletop incident concerns a planned managed database replacement.
The Terraform action list contained both create and delete. The exercise author
mistook the create action for proof that the operation preserved data. Review
identified the delete action and retained the persistent-resource change-risk
finding. No real database was deleted and no real outage is represented.

The owner was asked to confirm intent, dependencies, recovery requirements and
restore-test evidence. The exercise intentionally provided no backup facts in the
sanitized plan. The reviewer therefore stated that readiness needed verification,
rather than claiming that backups were missing. A model recommendation did not
stand in for a recovery test or an operator approval.

The proposed sequence kept deletion protection until the exact change and cleanup
scope were reviewed. Private state history was retained separately. A documented
image rollback was recognized as insufficient for reversing database destruction.
For the related bucket exercise, the reviewer considered noncurrent generations,
retention and soft-deleted data before discussing remaining storage charges.

The training lesson is to inspect complete action sets, distinguish replacement
from a harmless creation and verify recoverability independently. Similarity to a
retrieved synthetic incident is context, not a prediction of data loss. The risk
report preserves the deterministic finding, stable source reference and missing
evidence caveat. No command in an incident narrative can authorize Terraform
execution, remove protection or trigger an automatic remediation.
