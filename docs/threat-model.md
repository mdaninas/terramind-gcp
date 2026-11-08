# Threat model

Assets: raw local Terraform values, credentials, private resource identifiers and
the integrity of deterministic findings. Inputs are untrusted even when described
as Terraform JSON. Repository examples are handcrafted synthetic normalized facts.

| Threat | Current control | Residual risk / planned work |
| --- | --- | --- |
| Raw plan/state leaks to cloud | No network clients; local allowlist projection; cloud boundary will accept normalized schema only | CLI users must keep original files outside source control; no system can infer all semantic sensitivity |
| Private identifiers leak through reports | Generated ordinal aliases, private CIDRs omitted, identity redaction, closed enums; canary tests | Aliases/types/counts still disclose structural facts; only synthetic data is approved for cloud demos |
| Marked sensitive values affect output | Risk-relevant sensitive attributes omitted and limitation emitted | Redacted unknown facts can hide risks; no known findings never means safe |
| Malicious plan text or Markdown injection | Arbitrary descriptions/labels/conditions omitted; no command execution from plan fields | Retrieval/model prompt injection defenses and a malicious runbook fixture are planned |
| Parser resource exhaustion / ambiguity | 5 MiB/256 KiB limits, max 100 changes, bounded collections, depth 64, duplicate-key rejection | Local caller already controls its own files; limits are conservative and reject some large legitimate plans |
| Incorrect exposure claim | Explicit protocol/ports/source facts; prevention-aware REVIEW; no live reachability or backup claims | Hierarchical firewall precedence, IAM deny/conditions, unsupported resource types and custom roles need human review |
| Model downgrades policy | No model dependency in the offline analyzer; reports derive severity from pure rules | Model integration must preserve this boundary under adversarial mocked AI responses |
| Supply-chain dependency risk | uv lock with hashes, Ruff/mypy, pip-audit and bounded runtime dependencies | Audits report only known vulnerabilities; online setup/audit contact package services |
| Accidental cloud mutation | No apply endpoint or deployment workflow; the infrastructure checker uses backend-free validation and mock plans | Operator deployment instructions include apply commands that require explicit approval and verified parameters |
| Unauthorized service invocation | Cloud Run invoker IAM requires explicit callers; deployed `/health` returned anonymous 403 and authenticated 200 | Project/service policies contain no public principals; organization inheritance needs separate review |
| Overprivileged service identity | Runtime has no data roles for liveness; image deployment and ingestion use separate identities | Later adapters require a reviewed permission change; Firestore collection scoping remains application-enforced |

No raw input, schema-validation values or original file paths are emitted by
application errors. CLI help displays only documented commands. There is no logging
of input values or report payloads. The offline network-denial test replaces socket
creation and runs normalization plus report generation.

`.gitignore` excludes common plan/state/credential names and all generated artifacts;
this is defense in depth, not a guarantee against deliberate staging. No real plan
or state file is checked in. Tests create synthetic Terraform-shaped objects in
memory or temporary test directories, never persistent raw-plan fixtures.

Cloud Run authentication is deployed and verified. Federation trust is deployed,
but GitHub environment protection and a real token exchange remain unverified.
Firestore client rules deny all access; server SDKs use database-conditioned IAM,
which does not enforce collection restrictions. A report TTL field is prepared,
but no report writer sets expiry yet. See [security exceptions](security-exceptions.md)
for scanner exceptions and logging boundaries. Retrieval/model adapters, CI
privileges and actual cleanup evidence remain planned.
