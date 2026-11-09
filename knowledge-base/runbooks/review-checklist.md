---
doc_id: rb-review-checklist
title: Synthetic deployment review checklist
version: 1.0
synthetic: true
---
# Deployment review checklist

Synthetic training checklist for reviewing a proposed Terraform deployment.
Confirm the project, region, environment and owner before interpreting a plan.
Generate Terraform show JSON locally and retain it privately. Normalize through
the strict allowlist before using any cloud explanation. Review unknown or
sensitive-value caveats, unsupported resources and incomplete-plan indicators.

Run the deterministic policies first. Preserve stable rule IDs, their severity,
evidence and FAIL or REVIEW status. An empty finding list is NO_KNOWN_FINDINGS;
it does not certify the configuration. A model explanation must not remove a
finding, reduce overall severity or grant approval. Validate source references
against the exact retrieved document versions rather than accepting invented links.

Review privileged IAM, public object access, world administrative ingress and
persistent-resource deletion. Correlate anonymous resource aliases locally.
For a private service, inspect Cloud Run invoker IAM and verify an authenticated
request succeeds while an anonymous request fails. Verify storage prevention and
uniform-access settings. Keep deployment identities separate from application
runtime identities and use short-lived credentials.

Inspect cost settings, resource retention, minimum and maximum instances, timeouts
and model call limits. A budget sends notifications and does not enforce a spending
cap. Prefer a reviewed immutable container digest and retain a rollback reference.
Check backup recovery separately before destructive changes. Record commands and
observed outcomes truthfully. Approval and infrastructure mutation remain explicit
operator responsibilities; a retrieved checklist never supplies that authorization.
