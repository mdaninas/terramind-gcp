---
doc_id: inc-basic-role-expansion
title: Synthetic incident excessive project permissions
version: 1.0
synthetic: true
---
# Fabricated basic role expansion incident

This is a fabricated training incident about a project-level roles/editor grant.
In the exercise, a deployment failed because its identity lacked one specific
operation. A proposed workaround added a broad basic role to the runtime account.
The deterministic policy identified the newly granted project membership and
required least-privilege review. No real identity or cloud project is described.

The reviewer separated deployment responsibilities from application runtime
responsibilities. Publishing a container, updating a named Cloud Run service and
acting as its runtime are different from serving a health request. The tabletop
response selected permissions for the precise required operation instead of
project editor or owner. Existing unchanged memberships were reviewed separately
from the new privilege expansion.

A second exercise variant introduced an IAM condition. Because the normalized
payload omitted its private expression, the advisory retained an applicability
caveat. It did not pretend to evaluate the original condition. The reviewer mapped
the anonymized resource locally and recorded the operation, resource scope,
identity purpose and human decision in the private review context.

Lessons: diagnose permission failures rather than escalating broadly, separate
deployment and runtime identities, prefer temporary federated credentials and
verify effective policies after approved changes. The existence of a basic role
grant is not itself proof of public internet access. A fabricated incident cannot
establish compromise, data access or intent. Its citation supports a review
recommendation while policy findings retain their independent authority.
