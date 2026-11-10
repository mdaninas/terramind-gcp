# Synthetic Incident Memory

Incident Memory finds contextual similarities between deterministic findings and
the four packaged fabricated incident reports. It is implemented as local TF-IDF
cosine matching, without Google embeddings, model calls or external document
search. The CLI and user portal expose the same typed result contract.

```sh
uv run --locked terramind incidents --input examples/normalized-plans/public_bucket.json --output artifacts/incident-memory.json
```

Each match carries its stable document ID, title, version, source path, SHA-256,
excerpt, related rule IDs and lexical cosine score. The evidence label explicitly
states that the source is a synthetic tabletop incident. Scores are lexical
similarity, not a probability, causal finding or prediction of a real incident.

Only fixed policy queries derived from the report's rule IDs are searched. Raw
Terraform values and arbitrary user queries never enter the matcher. TF-IDF uses
only incident documents; ordinary runbooks do not appear as incident matches.
The corpus is checked for duplicate IDs and body/hash mismatches. The standard
quality gate also checks the packaged corpus against reviewed Markdown sources.

Results default to the top three documents scoring at least 0.08, with a maximum
of five when called programmatically. An analysis without findings returns
`not_requested` and no matches. Unsupported future rule queries yield `partial`.
Similarity never modifies the original findings, severity or policy version.

The frozen four-query evaluation ranks the intended fabricated incident first
for public bucket access, world administrative ingress, basic project-role grants
and persistent-resource deletion. All four expectations pass. These small curated
cases establish repeatable behavior on this corpus, not general semantic recall
or real-incident detection quality. See the [verification record](portal-verification.md).

Source documents remain the existing synthetic incident Markdown under
`knowledge-base/incidents/`. No real organization documents or incident records
were added. `incident-memory.v1.schema.json` defines the separate output contract;
the existing deterministic report schema is unchanged.
