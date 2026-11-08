# Architecture decisions

Offline analysis is implemented and verified locally. Cloud integrations are planned.
See the [roadmap](roadmap.md).

## Dependency direction

The CLI depends on normalization, policies and reporting. Policies depend only on
immutable typed contracts. The report builder runs policies and derives the maximum
severity. It owns findings; later model/retrieval adapters can add advisory text
through separate contracts without replacing findings.

No cloud SDK, FastAPI server, credentials lookup, external subprocess or network
client is part of the offline analysis path. Pydantic is the sole direct runtime
dependency. This keeps a fresh local demonstration small and reproducible.

## Local privacy boundary (ADR 001)

Parse bounded Terraform JSON locally and project it into a closed vocabulary,
rather than redact a copy of the full plan. Resource aliases use managed input
order (`resource_0001`); they reveal no original name and avoid reversible hashes
of predictable private identifiers. Aliases are stable for identical ordered
inputs but are not persistent identities across differently ordered plans.

Only world CIDRs survive normalization. Nonpublic IAM principals become
`redacted`; supported roles remain enums. Private CIDRs, labels, names, project IDs,
conditions, prior values, unknown/sensitive masks, outputs and provider details do
not survive. Unknown/sensitive facts generate closed limitation codes.

Tradeoff: the cloud cannot map aliases back to real infrastructure. Engineers must
correlate findings locally. Terraform names/order are not a trust boundary for
policy authority; the future API must re-run rules on submitted facts.

## Differential IAM facts (ADR 002)

Compute membership, role, scope and condition differences locally. Only
`newly_granted: true|false|null` crosses the boundary; prior identities and condition
expressions do not. Changed conditions conservatively count as new grants. New
conditional grants and unavailable prior facts yield REVIEW instead of certainty.

Tradeoff: redaction loses per-principal readability. The analyzer covers member, binding and
policy resources for bucket and project IAM, not custom-role permission expansion.

## Reports and risk authority (ADR 003)

Rule functions are pure and deterministic, with stable rule IDs and evidence.
Overall risk is the maximum severity, including REVIEW findings. An empty result
is `NO_KNOWN_FINDINGS`. UUID/timestamps identify report invocations, so the complete
report JSON is not byte-identical across runs even when findings are identical.

JSON Schema is generated from code, checked for drift and validated against all
samples. Pydantic additionally checks numeric port ranges and alias uniqueness.
Both output formats derive from the same report. Markdown includes only trusted
templates and allowlisted facts, avoiding injection from raw resource strings.

## Future adapters

Planned adapters include authenticated Cloud Run/FastAPI hosting, Terraform
infrastructure, Firestore retrieval, Gemini explanations, report persistence,
private presentation and GitHub Actions deployment with Workload Identity Federation.
The corresponding packages and directories will be added when implemented, avoiding empty
scaffolding that suggests functionality exists today.
