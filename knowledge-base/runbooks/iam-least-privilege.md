---
doc_id: rb-iam-least-privilege
title: Synthetic project IAM least privilege review
version: 1.0
synthetic: true
---
# Project basic roles

Synthetic training runbook. A proposed project-level roles/owner or roles/editor
grant expands broad administrative capabilities. Review newly granted membership
and changes to conditions separately from existing unchanged access. A basic role
grant is an authorization risk; it does not by itself mean internet exposure.

Ask which exact application operation requires the permission. Prefer a narrowly
defined predefined role or a reviewed custom role at the smallest supported
resource scope. Separate the runtime identity from deployment and knowledge
ingestion identities. A health-only runtime should not receive database write,
storage administration or project administration privileges merely for convenience.

For deployment, prefer short-lived federated credentials, a scoped Artifact
Registry writer, the named Cloud Run service update permission and actAs only on
its runtime account. Do not replace a failing permission with project owner or
editor. Diagnose the missing operation and review the relevant role instead.
An IAM condition can restrict applicability, but a redacted condition cannot be
evaluated from sanitized facts. Preserve the review caveat when its effect is unknown.

Document the operation, scope, identity purpose, expiry if applicable and the
reason the narrower permission is sufficient. Verify the actual policy after an
approved change, including inherited access where relevant. Keep original account
identifiers in the local review context. Do not put credentials, service-account
keys or authorization headers into runbooks or model prompts. The deterministic
finding remains authoritative even if an advisory recommends a practical role.
