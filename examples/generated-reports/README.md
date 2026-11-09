# Synthetic grounded report

`grounded-synthetic.json` and `grounded-synthetic.md` contain the same verified
report generated on 2026-11-09 using the private knowledge CLI, Firestore vector
retrieval and `gemini-3.5-flash`. All input facts and knowledge documents are
synthetic. The sample includes all four deterministic HIGH findings and ten
validated document/section references.

The JSON preserves policy evidence separately from advisory prose and records
source versions, paths and content hashes. Model wording, analysis UUIDs and
timestamps vary between runs. This sample is neither a deployment approval nor
evidence about real infrastructure exposure or backup readiness.

See the [retrieval guide](../../docs/retrieval-and-explanations.md) and
[verification record](../../docs/retrieval-verification.md) to reproduce the checks.
