# Eventarc synthetic source indexing

A separate private FastAPI receiver handles Cloud Storage finalized events at
`POST /events/storage`. The implementation and SDK adapters are verified with
local doubles; Terraform configuration is validated and mock-planned. Eventarc,
the receiver deployment, its new IAM and live event delivery have not been
activated or verified on GCP. Project billing remains disabled.

## Source contract

The receiver supports the content-addressed objects already written by the
knowledge CLI: `sources/{doc_id}/{content_hash}.md`, with canonical Markdown body
bytes and `synthetic=true` / `content_hash` object metadata. Only objects matching
the synthetic corpus packaged in that receiver image are eligible. Old revisions,
arbitrary uploads and unknown paths are acknowledged as ignored before cloud
client discovery. This is a reviewed-corpus synchronization trigger, not a general
upload-to-AI endpoint or an editor for arbitrary bucket documents.

For a corpus change, edit the approved synthetic Markdown locally, run
`uv run --locked python scripts/export_event_corpus.py`, and review the package
diff. The quality gate rejects packaged-corpus drift. After a separately approved
deployment of that immutable image, publish the matching source objects using the
knowledge CLI. A matching finalized object triggers synchronization of the entire
packaged corpus. Do not run manual full-corpus ingestion concurrently with event
indexing; use the controlled maintenance procedure below.

The receiver requires binary CloudEvents v1.0 with the storage-finalized type,
exact configured bucket/source, matching object subject and a positive generation.
JSON data is streamed with a 64 KiB limit, duplicate-key/depth checks and a
five-second body timeout. Unsupported media/content encoding is rejected.
Event headers are not authentication: the dedicated Cloud Run service must enforce
invoker IAM. Local servers do not implement Google authentication.

## Idempotence and failure handling

- GCS reads bind the exact generation and use generation-match preconditions,
  bounded byte ranges, metadata checks and exact packaged-body/hash comparison.
  No arbitrary source text reaches embeddings and the handler never republishes
  source objects, avoiding a recursive trigger loop.
- A receipt key covers the corpus revision, embedding model, bucket, object name
  and generation. Repeated deliveries, including a different CloudEvent ID, reuse
  the durable receipt across worker restarts. Receipts expire after seven days;
  later repeats still reuse unchanged stored vectors.
- A Firestore transaction claims a five-minute corpus lease with a unique owner.
  Busy deliveries receive 503 with Retry-After. Embeddings are staged outside the
  transaction and reuse unchanged content/title/model combinations.
- The final transaction checks the owner, lease expiry and unchanged prior index.
  Chunk writes/deletions, the success receipt and lease release commit atomically.
  Expired workers or concurrent manual writes cannot commit that staged result.
- Failure before commit records no success receipt. A failed release expires;
  redelivery can retry. An ambiguous committed response is reconciled by the receipt.
  Embeddings computed before a failed write can be billed again on retry; the
  design does not promise exactly-once model calls or a hard spending cap.
- Invalid events return 400, oversized events 413, unsupported encodings/media
  415, body timeouts 408 and dependency/busy failures 503. Monitor repeated invalid
  deliveries and pause the trigger for investigation. Eventarc redelivery and
  retention behavior still require live verification before enabling.

Application errors omit event payloads, object identifiers and provider exception
details. Raw access logging remains disabled. The optional service has its own
request-log exclusion, matching the existing synthetic privacy boundary.

## Infrastructure and activation

`enable_eventarc_indexing=false` is the default. Enabling it prepares:

- A dedicated internal-ingress Cloud Run service, IAM enforced, minimum zero and
  maximum one instance, concurrency one and a 240-second request timeout.
- Separate receiver and trigger identities. The receiver gets read-only access
  to the named source bucket, database-conditioned document writes and model
  prediction/quota permissions. Database-scoped `datastore.databases.get` supports
  transaction begin/rollback. The trigger can invoke only the event service.
- A bucket-filtered finalized-event trigger, Eventarc/Pub/Sub APIs, the required
  Cloud Storage service-agent publisher grant, and a receipt TTL field.

The database IAM boundary is database-wide, not per collection. Shared authorized
operators must protect this synthetic-only database. The receiver cannot upload
objects, change IAM or administer database indexes with its runtime permissions.

Do not enable billing, apply Terraform, grant IAM or deploy these resources as part
of local verification. A future activation requires explicit owner approval,
current provider/region review and a private plan showing the exact additions.
The manual image-promotion workflow currently deploys the analysis service only;
event receiver updates require a separately reviewed infrastructure deployment.

After authorized activation, verify private invocation, one matching generation,
redelivery, expired-lease recovery, unchanged re-upload and old-revision rejection
before claiming cloud readiness. Pause/delete the trigger before maintenance,
manual ingestion, rollback or removing the source bucket/database. Resume only
after the packaged corpus, deployed image and bucket objects agree. Follow the
[cleanup guide](cost-and-cleanup.md) for any approved full deletion.

## Local verification

```sh
uv run --locked python scripts/export_event_corpus.py --check
uv run --locked pytest tests/integration/test_eventarc.py tests/unit/test_eventarc_adapters.py -q
uv run --locked python scripts/check_infrastructure.py --terraform ./artifacts/tools/terraform/terraform.exe --scan
```

Select `TERRAMIND_SERVICE=events` to serve the separate receiver using the existing
container entry point. It remains disabled unless `TERRAMIND_EVENTARC_MODE=cloud`
is explicitly configured. Health checks do not initialize cloud SDK clients.

References: [Cloud Storage triggers](https://docs.cloud.google.com/run/docs/triggering/storage-triggers),
[Eventarc Terraform](https://docs.cloud.google.com/eventarc/docs/creating-triggers-terraform),
and [trigger resource](https://registry.terraform.io/providers/hashicorp/google/8.10.0/docs/resources/eventarc_trigger).
The transaction permission follows [Firestore server IAM](https://docs.cloud.google.com/firestore/native/docs/security/iam).
