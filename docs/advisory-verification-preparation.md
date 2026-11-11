# Advisory verification preparation

The previous [hosted window](live-integrations-verification.md) returned valid
core advice but fallback for Storage and Database hardening, and its last strict
deployment smoke failed. The retained results cannot distinguish generation,
deadline and validation failures. These changes prepare a diagnosable rerun;
they do not establish that either live gap is resolved.

## Prepared changes

- Generation retains supported array bounds, uses the current request's exact
  explanation count, and enumerates only its finding and citation identifiers.
  Recommendations and limitations are limited to three entries. Concise prose is
  requested while the full response, finding, severity and citation checks remain.
- Safe fallback distinguishes deadline/call limits, timeout, provider rejection,
  rate limiting, incomplete/empty output, response validation, finding coverage
  and citation coverage. The `advisory_outcome` event contains only a fixed reason,
  finding count, physical-call count and elapsed time. No prompt, provider text,
  exception message, token or account identifier is emitted.
- The existing 23-second shared deadline, 20-call ceiling, 20-second per-call
  ceiling and 4,096 output-token cap remain. These changes do not increase retry
  counts or switch models. They are targeted mitigations, not a retrospective
  diagnosis of the earlier provider responses.
- Strict smoke supports core, Storage and Database scenarios. It independently
  checks deterministic findings, pack/version selection, saved-report round trip,
  exports, exact finding coverage and canonical source provenance. Missing or
  invalid advice still fails the check.
- Failures now write a content-free JSON summary with the failed stage, safe
  reason, submission count and timing. The deployment workflow retains that one
  artifact for one day even when smoke fails. It has no `continue-on-error` path.

Google documents array bounds and string enums as supported structured-output
fields, and also warns that complex schemas can be rejected. See
[the provider's schema documentation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/control-generated-output#supported-schema-fields).
Provider acceptance and live output quality still require the approved rerun.

The first approved 2026-11-11 rerun validated Storage advice, but core generation
was rejected with `INVALID_ARGUMENT` and Database advice failed its response
contract. A follow-up uses short request-local finding/source aliases in the
provider schema and restores only registered aliases to their original IDs before
the unchanged strict validation. Unknown aliases, risk overrides and non-ASCII
prose remain rejected. This reduces grammar size without removing sources or
loosening the output contract. Prose instructions explicitly avoid terms rejected
by the existing assertion guard. The precise earlier Database validation error
was not retained, so this is a targeted mitigation pending the next live result.

## Local verification

The new tests use explicit local HTTP and model doubles. They exercise all three
scenarios, preserve a failed pack's evidence without retrying it, reject altered
source hashes and finding coverage, and ensure diagnostic output excludes private
canaries. JSON Schema tests reject unsupported finding/citation identifiers for
each scenario. Local results are not a live Gemini evaluation.

Observed checks: 510 tests passed in 27.49 seconds; normalization/policy coverage
was 97.19%. Ruff, strict mypy on 71 source files, schema/corpus drift checks,
actionlint, public-file privacy and whitespace checks passed. Source distribution
and wheel builds passed, and the wheel contains the new diagnostics module.

Run the quality gate and workflow check:

```sh
uv run --locked python scripts/check.py
actionlint -shellcheck= .github/workflows/deploy.yml
```

The existing local API can exercise deterministic exports for one hardening pack:

```sh
uv run --locked python scripts/demo_cloud.py --local --url http://127.0.0.1:8080 --scenario storage-hardening
```

## Next approved live window

Billing remains disabled during preparation. Before any new metered operation,
obtain explicit approval for a fresh bounded window and publish the reviewed
source without a co-author trailer. Suggested commit: `Prepare advisory verification`.

The default protected deployment still submits one core analysis. Selecting the
new `verify_policy_packs` dispatch input runs this strict command instead:

```sh
uv run --locked python scripts/demo_cloud.py --url "$CLOUD_RUN_URL" --require-advisory --all-scenarios
```

It attempts each of the three packaged scenarios once, with at most three
analysis submissions per invocation. A transport timeout counts as a submission;
the runner does not resubmit an ambiguous request. If a preflight check prevents
submission, the evidence records that case with `analysis_submitted: false`.
Any failed scenario leaves the overall result failed.

For an approved end-to-end window, bound total API/portal analysis submissions to
six, including the three strict API cases. Promote the same reviewed immutable
image to the private portal using an audited image-only plan. Keep existing IAM,
OAuth scopes, instance caps and ingress settings. Do not run extra analyses to
force a green result: retain diagnostics for any failure and stop at the approved
limit. Restore disabled billing after testing and verify the association is empty.

Success requires real validated advisory output for both hardening packs and a
green strict smoke, with unchanged deterministic findings and correct sources.
Those outcomes remain pending; no billing, IAM, Terraform apply or paid model
operation was performed during this preparation.
