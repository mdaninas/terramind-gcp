# Optional infrastructure policy packs

The four `gcp-core` rules always run. Two optional packs add four deterministic
change checks. They are implemented and tested locally with synthetic data.
The expanded twelve-document corpus was synchronized on GCP, and hosted portal
samples returned the expected pack findings with available retrieval. Their live
advisories used fallback, so successful generated pack explanations remain
unverified. See the [hosted record](live-integrations-verification.md).

| Pack | Rule | Trigger | Severity and status |
| --- | --- | --- | --- |
| `storage-hardening` | TM-GCP-005 | Explicit bucket uniform access disabled on create or newly disabled | MEDIUM FAIL; REVIEW if the before setting is unknown |
| `storage-hardening` | TM-GCP-006 | Explicit public access prevention inherited on create or newly inherited | MEDIUM REVIEW, inherited organization policy may still enforce prevention |
| `database-hardening` | TM-GCP-007 | Public IPv4 enabled with a world IPv4 authorized network on create or newly enabled | HIGH FAIL; REVIEW if the before combination is unknown |
| `database-hardening` | TM-GCP-008 | Explicit SSL mode allows unencrypted connections on create or newly weakened | MEDIUM FAIL; REVIEW if the before setting is unknown |

These rules evaluate creates, updates and replacements. A label-only update with
identical weak settings does not produce a new hardening finding. Persistent
deletion remains independently covered by the core rule, including replacements.
This is change analysis, not a scan of all existing infrastructure.

## Usage

Normalize synthetic Terraform show JSON locally, selecting one or both packs:

```sh
uv run --locked terramind normalize --input artifacts/synthetic-plan.json --output artifacts/normalized.json --policy-pack storage-hardening --policy-pack database-hardening
uv run --locked terramind analyze --input artifacts/normalized.json --output artifacts/hardening-report.md --format markdown
```

The raw example path is user-created local synthetic input, not a committed plan.
To try a committed normalized sample directly:

```sh
uv run --locked terramind analyze --input examples/normalized-plans/storage-hardening.json --output artifacts/storage-report.md --format markdown
uv run --locked terramind analyze --input examples/normalized-plans/database-hardening.json --output artifacts/database-report.json
```

Selection lives in the normalized input and appears in JSON, Markdown, portal
reports and PR summaries. The portal offers both fixed synthetic scenarios and
filters history by all eight rule IDs. The private analysis API accepts synthetic
1.1 inputs with the same validation. Existing 1.0 fixtures retain core behavior.
Re-normalize with the pack flags to add facts to a legacy input. Editing only its
version cannot recover facts that were discarded during local normalization.

## Closed facts and limitations

Schema 1.1 adds unique `policy_packs` values `storage-hardening` and
`database-hardening`. Schema 1.0 rejects nonempty selections and new fields.
The exported major-version JSON Schemas describe both versions.

| Resource | Additional closed attributes |
| --- | --- |
| Bucket | `uniform_bucket_level_access`, `newly_disabled_uniform_access`, `newly_inherited_prevention` |
| Cloud SQL instance | `ipv4_enabled`, `world_authorized_network`, `newly_world_accessible`, `ssl_mode`, `newly_unencrypted` |

All new flags are booleans or null. SSL mode is one of
`ALLOW_UNENCRYPTED_AND_ENCRYPTED`, `ENCRYPTED_ONLY`,
`TRUSTED_CLIENT_CERTIFICATE_REQUIRED`, or `unknown`. Existing bucket prevention
retains `enforced`, `inherited` or `unknown`. The local normalizer compares raw
before and after values, emitting only these bounded facts. It drops resource
names, private CIDRs, network labels and arbitrary settings. Nested unknown or
sensitive markers suppress the affected facts. Missing flags are not defaulted.

Inherited prevention does not prove public access. Disabled uniform access does
not prove that an ACL grants access. SQL world-source authorization does not
prove deployed reachability, a successful login or an actual breach. SQL IPv6
networks, effective organization policies, runtime networking, legacy `require_ssl`
inference, credentials, client behavior and recovery readiness are outside these
new rules. A world network with an explicit expiration is treated as uncertain;
the normalizer does not infer whether a temporal authorization remains effective.
Missing facts do not establish compliance.

The corpus now includes twelve documents, eight synthetic runbooks and four
fabricated incidents. Four new retrieval queries are supported and local advisory
tests preserve severity and validated provenance. Incident Memory remains limited
to four curated core-rule incident queries, so additional rules receive partial
incident coverage, with no invented incident matches. Local lexical tests and a
model double do not establish live Google embedding or Gemini answer quality.
The separate approved [live verification](advisory-verification.md) subsequently
validated both hardening advisories, retrieval provenance and a strict deployment
smoke against the synchronized corpus.

## Implementation references

- [Cloud Storage uniform bucket-level access](https://docs.cloud.google.com/storage/docs/uniform-bucket-level-access)
- [Public access prevention, including inherited policy](https://docs.cloud.google.com/storage/docs/public-access-prevention)
- [Cloud SQL Terraform instance fields](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/sql_database_instance)
- [Cloud SQL SSL/TLS modes](https://docs.cloud.google.com/sql/docs/mysql/configure-ssl-instance)

These references define setting semantics; the findings retain the narrower
evidence and uncertainty described above.
