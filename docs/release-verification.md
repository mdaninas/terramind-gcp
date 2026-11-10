# Portfolio release verification

The MVP implementation and its portfolio documentation are verified. The offline
reproduction used a fresh GitHub clone of source
`280f6e339a39f11e1d20a5bf49b6a3324bfbdb81` on 2026-11-10 (Asia/Jakarta), with a
separate virtual environment and no Google credentials supplied. Application code
was unchanged during this documentation pass. No release tag was published.

The dedicated GCP deployment remains active. No provisioning, IAM changes,
Terraform apply, ingestion or paid model requests were performed during this pass.
A read-only Cloud Run description confirmed the same deployed digest is Ready
with minimum zero and maximum one instance. Fresh service and project IAM reads
contained no public principals. These reads do not audit organization inheritance.
The previous [live API deployment](api-delivery-verification.md) remains separate
evidence; local screenshots do not imply a second cloud deployment.

## Files and decisions

| Files | Purpose |
| --- | --- |
| README.md | Reproducible entry point, complete application flow, screenshot and supported scope |
| docs/demo-script.md | Timed walkthrough, expected results, local/cloud distinctions |
| docs/images/*.png | Actual local desktop, finding-details and mobile captures |
| docs/cost-and-cleanup.md | Explicit usage estimate, current rate sources, retained resource and cleanup limits |
| docs/release-verification.md | Commands, acceptance results, security and remaining operator work |
| docs/evaluations/release-2026-11-10.json | Content-free reproduction evidence and screenshot hashes |
| docs/roadmap.md, docs/evaluation.md, CHANGELOG.md | Current implementation and verification status |
| .gitignore | Exclude browser automation output, downloads and temporary profiles |

The report screenshots come from the existing server-rendered UI. No frontend
framework, public login, extra cloud service or new policy pack was introduced.
Mermaid keeps the architecture diagram editable in GitHub. Generated browser state,
private cloud inventory, temporary clones, package builds and verification logs
remain outside version control. Selected PNGs contain only synthetic report content.

## Commands and observed results

A new clone was created from `https://github.com/mdaninas/terramind-gcp.git` in an
ignored verification directory. These documented commands ran in that clone:

```sh
uv sync --locked
uv run --locked python scripts/check.py
uv run --locked python scripts/demo_offline.py
uv run --locked python scripts/demo_retrieval.py
uv run --locked python scripts/benchmark.py
uv run --locked python scripts/check_public_files.py
uv build
make setup
make lint
make test
make demo-offline
```

Read-only `gcloud run services describe`, `gcloud run services get-iam-policy`
and `gcloud projects get-iam-policy` commands checked the existing deployment.

All reproduction commands returned zero. GNU Make 4.4.1 was run from a portable tool directory;
its archive matched the checksum in the
[Scoop manifest](https://github.com/ScoopInstaller/Main/blob/master/bucket/make.json).
No system PATH or shell profile changes were needed. Setup reused the local package
cache where available; this does not establish an air-gapped installation.

The server was then started from the clone in offline mode on loopback port 8083:

```sh
uv run --locked --extra api python -m terramind.api
uv run --locked python scripts/demo_cloud.py --url http://127.0.0.1:8083 --local
```

`PORT=8083` selected the verification port; the README retains the default 8080.
The documented benign and public-bucket CLI commands also passed in the clone,
returning NO_KNOWN_FINDINGS and TM-GCP-001 respectively. The HTTP client verified
four unchanged HIGH findings, saved JSON, Markdown and HTML. The observed analysis request took 0.007 seconds. Retrieval was not_requested
and the model was null. This check does not exercise Cloud Run IAM or Google services.

| Acceptance check | Evidence |
| --- | --- |
| Automated tests | 297 passed; normalization/policy branch-aware coverage 97.58% |
| Quality | Ruff lint/format, strict mypy and generated schema checks passed |
| Required fixtures and security behavior | All eight expectations and privacy/injection/fallback tests passed |
| 100-change local performance | 0.004588 seconds in the standalone benchmark; under the two-second target |
| Offline report | Four HIGH findings; no requested retrieval/model |
| Packages | Source archive and wheel built from the clone |
| Browser UI | Preview button created a report; Markdown downloaded; JSON opened; zero console errors |
| Responsive layout | Desktop 1440 x 1080 and mobile 390 x 844 inspected; no horizontal overflow on mobile |
| Infrastructure and hosted delivery | Previously verified fmt/validate, twelve mock cases, documented Checkov exceptions, green CI and protected WIF deployment |
| Live retrieval/advisory | Previously verified 10/10 queries and cloud report with four findings and ten validated sources |
| Resource lifecycle | Active deployment explicitly documented; cleanup not executed |

The [machine-readable record](evaluations/release-2026-11-10.json) includes source,
commands, results and PNG hashes. The browser captures used the unchanged local
application source and synthetic sample. The published Gemini example is from the
earlier live CLI evaluation, with its provenance documented separately.

## Current-checkout status recheck

On 2026-11-10 (Asia/Jakarta), source `e53c43e` was checked in the existing local
checkout before the status documentation updates. This was not another fresh
clone or deployment. The [recheck record](evaluations/status-recheck-2026-11-10.json)
keeps these results separate from the earlier release and live cloud evidence.

- `uv run --locked python scripts/check.py`: 297 tests passed in 8.93 seconds;
  normalization/policy coverage 97.58%; Ruff, mypy and schema checks passed.
- Offline analysis produced four HIGH findings. The retrieval test double hit
  all ten intended documents in the top three with zero cloud calls.
- The 100-change benchmark took 0.003820 seconds. Source archive and wheel builds
  passed. Local HTTP analysis took 0.031 seconds and preserved all four findings
  through saved JSON, Markdown and HTML; retrieval was not requested, model null.
- Infrastructure formatting, validation in all three roots and twelve
  mock-provider tests passed. Checkov reported 17 Terraform checks passed,
  zero failed and four documented skips; Dockerfile checks were 48 passed,
  zero failed and zero skipped. Actionlint passed both workflows.
- Public-file privacy scanning and `git diff --check` passed after the status
  documentation updates.

The attempted read-only `gcloud run services describe` could not authenticate:
the current gcloud configuration had zero cached accounts and no active account.
Anonymous GET requests to the previously recorded Cloud Run `/health` and `/demo`
returned 403. This confirms those anonymous requests were rejected; it does not
reconfirm runtime readiness, the image digest, IAM policies, authenticated access,
Firestore or model behavior. No provisioning, IAM changes, deployment, cloud
analysis, ingestion or paid model requests were performed. Cloud state remains
supported by the earlier authenticated verification, with this limitation explicit.

## Security and remaining operator work

The scanner and final file review exclude credentials, raw plans/state, local
profiles, saved Terraform plans and operator artifacts. A nonexistent ADC path and
an empty cloud configuration path were selected for fresh-clone checks; package
installation and GitHub cloning still used the network. The offline network-denial
test and explicit null-model output verify the rule-only path independently.

The private runtime, shared authorized report access, database-level IAM boundary,
model limitations and cost controls remain documented in the
[threat model](threat-model.md) and [security exceptions](security-exceptions.md).
No claim of full scanner coverage, semantic AI correctness, hard spending limits or
enterprise access isolation is made.

Budget notification delivery, a Monitoring notification channel and organization
inherited policies remain unverified operator checks. They are not silently
reported as passing. Final shutdown requires review of the dedicated inventory,
delete protections, retained object/image versions and private Terraform destroy
plans. Follow the [cleanup order](cost-and-cleanup.md#cleanup-order) and verify actual
removal before claiming the project no longer has active resources.

PR comments, Eventarc indexing, historical incident search as a product feature,
new policies and a full dashboard remain deferred. Portfolio artifacts are ready
for review; release tagging and resource deletion are separate owner actions.
