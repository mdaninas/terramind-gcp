---
doc_id: rb-public-bucket
title: Synthetic public bucket access review
version: 1.0
synthetic: true
---
# Public bucket access

Synthetic training runbook. No real bucket, organization or incident is described.
Review a proposed Cloud Storage object-read grant to allUsers or
allAuthenticatedUsers. A role such as roles/storage.objectViewer permits reading
objects when the grant is effective. allAuthenticatedUsers includes identities
outside the project; it does not mean only the application's users.

Start with the proposed IAM membership difference. A newly added public principal
is relevant even if other unrelated grants already existed. Confirm whether public
access prevention is verifiably enforced on the affected bucket. If prevention is
enforced, describe the proposal as a conflicting intent requiring review rather
than proof that data is exposed. Missing values or redacted conditions require
uncertainty, not an assumption that the grant is effective.

Ask the owner who needs object access and for what duration. Prefer an explicit
service account or approved group with a bucket-scoped object role. Remove the
public grant in the proposed configuration when public distribution is unnecessary.
Retain uniform bucket-level access and enforced public access prevention for
private data. Consider a separately reviewed distribution mechanism when public
content is a real requirement.

The reviewer must inspect the original plan locally to map anonymized resource
aliases to the intended bucket. Do not upload object contents, IAM identities or
raw Terraform plans to an explanation service. Record the deterministic finding,
the applicable prevention setting, the intended audience and the review decision.
Plan facts describe proposed access and do not establish that any object was read.
