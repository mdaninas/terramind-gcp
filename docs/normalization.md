# Normalized schemas 1.0 and 1.1

The [committed schema](../schemas/normalized-plan.v1.schema.json) is the structural
contract. The [report schema](../schemas/report.v1.schema.json) describes output.
Extra fields are rejected at every normalized object boundary. Pydantic also
checks port bounds/order, action sequences, address/type agreement, type-specific
attributes and unique aliases. JSON Schema covers the structural cross-field rules;
numeric port-range ordering and unique alias semantics require runtime validation.

Default normalization retains schema 1.0 and the four core rules. Explicit
`normalize --policy-pack storage-hardening` or
`--policy-pack database-hardening` produces schema 1.1 and the additional closed
facts described in [policy packs](policy-packs.md). Both flags can be supplied.
Pack names are unique, allowlisted and retained in the normalized plan; analysis
uses that selection and always includes core rules. Schema 1.0 rejects new facts
and nonempty pack selections. Both versions share the major-version schema files.

## Limits and error behavior

- Terraform JSON format major version 1; unsupported major versions are rejected.
- Local raw input: 5 MiB and at most 100 resource-change records, including data
  records. Data-mode reads are validated and omitted from managed-resource policy checks.
- Normalized input/output: 256 KiB and at most 100 managed changes. No truncation.
- JSON nesting: at most 64 levels; duplicate keys and non-finite numbers rejected.
- Bounded lists: 100 entries (grants, members, bindings, allows, ports); strings
  read from risk-relevant raw fields are at most 4096 characters. Large policy
  JSON strings must be split into smaller IAM resources for this MVP.
- Missing/invalid objects, malformed CIDRs/ports and unsupported action sequences
  return CLI exit code 2 with a sanitized error. Findings themselves return 0;
  the CLI does not act as a deployment approval gate.
- State JSON and raw Terraform plans are rejected by the normalized input loader.
  Only `normalize` accepts Terraform-shaped input, with explicit `resource_changes`.
- Duplicate raw addresses, including deposed-object variants, are rejected;
  deposed-object correlation is not currently implemented.

## Facts preserved

The following table describes core schema 1.0. Schema 1.1 additionally allows the
bounded hardening fields documented in the pack definitions, including boolean
before/after comparison outcomes. Raw before values never leave normalization.

| Resource scope | Allowed attributes |
| --- | --- |
| Bucket IAM member/binding/policy | `grants`, verified `public_access_prevention` |
| Project IAM member/binding/policy | `grants` |
| Bucket | `public_access_prevention` |
| VPC firewall | `direction`, `disabled`, world-only `source_ranges`, `allow` protocol/port facts |
| Supported persistent resources and opaque unsupported resources | Empty attributes |

All aliases use `<supported_type>.resource_NNNN`. Unknown provider resource types
become `unsupported_resource.resource_NNNN`; their attributes are discarded and a
limitation is included. `schema_version` and `source` must be explicit; the only
source values are `synthetic-demo` and `local-normalizer`.

`grants` contain `role`, `principal` (`allUsers`, `allAuthenticatedUsers`,
`redacted`) and `newly_granted`. The analyzer detects object-read roles objectViewer,
objectAdmin, objectUser, storage.admin and legacyObjectReader. Basic owner/editor
are checked at project scope. Legacy bucket reader/owner are retained as categories
but do not independently establish object-content read access. Other roles and
custom permissions are outside this policy pack.

Public access prevention is correlated only to an exact bucket name in known
non-sensitive bucket change facts within the same plan, with no planned deletion.
The IAM resource cannot self-assert prevention using arbitrary raw attributes.
Inherited organization settings, preexisting resources absent from the change list,
ACLs and signed URLs are not resolved. Even enforced prevention leaves a HIGH
REVIEW finding for proposed public grants.

Firewall checks accept TCP (`tcp`/`6`), UDP (`udp`/`17`) and all protocols.
Explicit allow entries without ports mean all ports; a world CIDR without an allow
entry is insufficient. TCP 22, TCP/UDP 3389 and inclusive ranges are recognized.
Only enabled ingress proposals are checked. Provider defaults are applied for
omitted direction/disabled flags; unknown flags are not defaulted. Missing source
ranges are not inferred as public. Deny rules, hierarchy/priority, targets and live
VM reachability require separate human review.

Deletion checks include buckets, SQL instances/databases, zonal/regional disks,
Firestore databases, Bigtable instances, Spanner instances/databases and Filestore
instances. Both Terraform replacement action orders include deletion. This list
is explicit; unsupported persistent resource types are not implicitly covered.

## References used for implementation

- [Terraform JSON format, unknown and sensitive markers](https://developer.hashicorp.com/terraform/internals/json-format)
- [Terraform show plaintext sensitivity warning](https://developer.hashicorp.com/terraform/cli/commands/show)
- [Cloud Storage public access prevention](https://docs.cloud.google.com/storage/docs/public-access-prevention)
- [Cloud Storage predefined roles](https://docs.cloud.google.com/storage/docs/access-control/iam-roles)
- [VPC firewall rule semantics](https://docs.cloud.google.com/firewall/docs/firewalls)

These references informed the parser and narrow rule scope; they do not establish
complete security coverage or the current state of a user's infrastructure.
