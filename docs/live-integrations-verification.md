# Hosted integration verification

Live verification on 2026-11-10 uses synthetic data in the dedicated approved
Google Cloud project. This record supplements the historical local checks and
the [activation proposal](live-activation-plan.md). Verification is in progress;
Google portal login and final billing shutdown are still pending.

## Trusted PR review and delivery

[PR #1](https://github.com/mdaninas/terramind-gcp/pull/1) exercised all eight rules
and both optional packs through the trusted-main manual workflow. Two successful
attempts of [review run 42788780002](https://github.com/mdaninas/terramind-gcp/actions/runs/42788780002)
produced one managed bot comment, without duplicates, and neutral head checks.
The published review identifies the exact analyzed head,
`9c241a7cb49dba84808aec2681343c2aaf59f049`.

The reviewed PR passed CI and merged as
`743008fc4d5946b25a39114adb372f99104e9306`.
[Protected deployment 42790086598](https://github.com/mdaninas/terramind-gcp/actions/runs/42790086598)
passed the required owner review, WIF authentication, private-runtime checks,
immutable image publication and end-to-end cloud analysis with an advisory.
This consumed one of the six approved analysis requests.

The deployed application image digest is
`sha256:064d19ea6482132d9c0912dbb9f35d2018239b2be7532dce18185a32f09efc1c`.
The Eventarc receiver and portal use this same image. A later Terraform-only
correction configures the exact hostname returned by Cloud Run for the official
authenticated proxy. It changes the portal environment and probe Host headers.

The live browser exposed a separate login issue: Chrome blocked the form's
cross-origin OAuth redirect under `form-action 'self'`. The corrected form
renders a same-origin continuation page with a Google link, preserving that CSP.
A local real-browser regression reached a separate synthetic origin successfully;
the full 493-test quality gate and six portal Terraform cases passed. This local
regression does not establish a successful Google login.

## Real Eventarc delivery

The receiver and trigger were applied with separate runtime and delivery
identities, internal ingress and authenticated invocation. Service-agent
initialization and IAM propagation required retries of the remaining additions.
No unrelated deletion was applied.

Observed against the real bucket, Eventarc subscription and Firestore database:

- Before publishing: ten indexed documents, ten chunks and no ingestion receipts.
- An expired synthetic corpus lease was created using a create-only precondition.
  Uploading the canonical Storage hardening source produced a receipt, removed
  that lease and synchronized all twelve packaged documents.
- Publishing the Database hardening source produced a second receipt. Reuploading
  identical Storage content created a new generation and a third receipt. All
  twelve knowledge document update times remained unchanged after these uploads.
- A timestamp seek on the existing Eventarc subscription replayed the three
  retained messages. Pub/Sub push metrics increased from two ACKs before the
  third upload to six ACKs after the third upload and replay. Receipt count
  remained three and all knowledge document update times remained unchanged.
- One synthetic object path absent from the current package was acknowledged
  without a new receipt or knowledge update. The eventual push metric was seven
  `ack_200` responses, with three receipts and twelve unchanged chunks.
- Every one of the twelve canonical source objects matched its packaged body,
  SHA-256 metadata and synthetic marker.

Acknowledged-message retention was enabled only for this bounded replay test and
restored to its original disabled setting. Metrics establish successful delivery
and state invariance; they are not an independent count of embedding API calls.
Expired-lease recovery was exercised live. An active worker's stale commit fence
remains covered by local transaction tests rather than a live concurrent-worker
experiment.

## Portal and operating state

The private portal, separate Firestore database, index, TTL policies and
Secret Manager runtime binding were applied. Google OAuth uses an External
testing client, one approved test user and the exact loopback callback. Only the
approved operator has Cloud Run invoker access. Interactive login and report
verification remain pending.

Public evidence excludes OAuth secrets, tokens, login callback URLs, account
emails, raw plans, state and private report storage. Detailed operator artifacts
remain ignored under `artifacts/live-activation/`.
