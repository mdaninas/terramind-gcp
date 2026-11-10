# Optional policy pack verification

Historical local record. The later [hosted verification](live-integrations-verification.md)
records live corpus synchronization and expected pack findings, together with
advisory fallback rather than successful generated pack explanations.

Local verification ran on 2026-11-10 using Python 3.12.13 on Windows. The source
baseline is `bc787489661e8964653a7e068ffedafe3ce71b42`, plus the uncommitted
policy-pack changes. This record does not claim a cloud rollout. The content-free
[evaluation record](evaluations/policy-packs-2026-11-10.json) captures the scope.

## Implemented behavior

- Core rules always run. Two optional packs add four rules for bucket access
  controls and SQL connectivity/TLS. Default normalization still emits 1.0;
  explicit pack selection emits 1.1 with bounded, sanitized facts.
- Local before/after comparison avoids new hardening findings for unchanged weak
  settings during label updates. Known creates and weakening changes produce
  evidence; unavailable before facts require REVIEW. Inherited bucket prevention
  always requires REVIEW rather than an assertion of public exposure.
- Nested unknown and sensitive markers suppress affected facts. Missing TLS mode
  is not inferred from `require_ssl`. Public SQL IPv4 and a non-expiring, static
  world authorization must both be explicit before the world-source rule fires.
  Networks with explicit expiration remain uncertain.
- Report JSON/Markdown, API report pages, portal reports and PR summaries retain
  selected pack names. Portal scenarios exercise both packs and owned history
  supports all eight rule IDs. PR publishing remains a neutral check.
- Two new fabricated runbooks expand the packaged corpus to twelve documents.
  Four additional rule queries rank their intended runbook first in local lexical
  tests. A controlled model double validates citations and preserves severity;
  an attempted model risk override falls back to deterministic findings.
- The original four incident retrieval cases remain unchanged. New hardening
  rules receive partial Incident Memory coverage and no invented incident matches.

## Results

| Check | Observed result |
| --- | --- |
| `uv run --locked python scripts/check.py` | Passed, 481 tests in 12.88 seconds |
| Normalization and policy branch coverage | 97.19%, above the 80% gate |
| Optional hardening policy functions | 100% coverage in the full suite |
| Ruff and formatting | Passed, 143 formatted files |
| Strict mypy | Passed, 68 source files |
| JSON Schema and packaged corpus drift | Passed, both normalized versions validated |
| API fixture round trips | Passed for the two new committed 1.1 samples |
| Portal scenarios and filters | Passed, including cross-owner read and history isolation |
| Synthetic PR prepare/publish doubles | Passed, pack names retained and checks remain neutral |
| Existing retrieval and incident evaluations | Passed without changing curated query expectations |
| CLI sample exports | Passed, Storage MEDIUM and SQL HIGH, two findings each |
| `uv build` | Source distribution and wheel built successfully |
| Wheel content inspection | New normalizer/policies and twelve synthetic documents present |
| Public-file privacy and diff whitespace | Passed |

The preceding Incident Memory commit was pushed without a co-author trailer and
its [GitHub CI run passed](https://github.com/mdaninas/terramind-gcp/actions/runs/42771807375).
The policy-pack changes described here have not yet been committed or pushed.

## Verification boundaries

No dependency, Terraform, cloud IAM, billing or paid-service changes were needed.
Billing remains disabled according to the last verified shutdown record. These
checks use local synthetic inputs, SDK/HTTP doubles and a controlled model double.
No new live Google embedding, Gemini, Firestore ingestion or Eventarc operation
was performed. The expanded corpus requires a separately authorized cloud rollout
and ingestion before cloud results can include these runbooks.

Live Google login, hosted portal deployment, hosted PR comment/check publication
and Eventarc delivery remain unverified. No new browser screenshot or mobile
visual-verification claim is made for the additional portal scenarios. Existing
deployment and evaluation records retain their original source and scope.
