---
doc_id: rb-backup-deletion
title: Synthetic persistent data deletion review
version: 1.0
synthetic: true
---
# Persistent resource deletion

Synthetic training runbook. A Terraform delete or replacement of a bucket,
managed database or persistent disk is a change risk requiring human review.
Replacement includes a delete action even when a create action also appears.
The proposed action does not prove that backups are absent or that data loss
will occur. Backup readiness must be verified independently.

Map the anonymized resource to its real local plan entry. Ask whether removal is
intentional, which consumers depend on the data and who owns the change. Verify
the required recovery point and recovery time, the age and integrity of a backup,
and whether a restore has been tested. A backup that exists but cannot be restored
does not meet the operational requirement. Do not infer these facts from a model.

Check deletion protection, bucket object versions, retention, soft-delete behavior
and the exact destroy scope. Nonempty protected resources may block destruction;
do not remove controls merely to make an unreviewed apply succeed. State storage
and its history need a separate retention and cleanup decision. Deleting a current
object version can leave other generations and associated storage costs.

Record the approved sequence, a private state backup, recovery evidence and the
owner's decision before any infrastructure mutation. An image rollback cannot
reverse a destructive database change. Verify removal and billing behavior after
authorized cleanup instead of treating an attempted command as success. Keep all
raw state, plans and actual recovery credentials outside the repository and model
context. Terramind identifies proposed destructive actions and never executes them.
