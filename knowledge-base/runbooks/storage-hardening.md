---
doc_id: rb-storage-hardening
title: Synthetic Cloud Storage hardening review
version: 1.0
synthetic: true
---
# Cloud Storage hardening

Synthetic training runbook. No real bucket or incident is described.
Review uniform bucket-level access disabled and inherited public access prevention
as separate hardening settings. Uniform bucket-level access disables object ACLs
and makes IAM the access-control mechanism. Disabling it can restore ACL-based
access control; it does not prove a public grant or an object disclosure.

For TM-GCP-005, compare explicit before and after settings. A create with
uniform_bucket_level_access=false or a change from true to false requires review
of existing ACL dependencies before enabling uniform access. A label-only update
to an already disabled setting is outside this change rule. Missing or sensitive
settings provide no compliance assurance.

For TM-GCP-006, inherited public access prevention delegates the effective setting
to organization policy. Verify that policy locally or enforce bucket prevention.
Never describe inherited as proof that public principals can access objects.
Changing enforced to inherited requires REVIEW even when organization policy
might still block public access. Record intent and review evidence before rollout.

Use the original plan locally to identify the alias. Do not upload bucket names,
ACL identities or raw Terraform plans. Advice cannot remove deterministic findings.
