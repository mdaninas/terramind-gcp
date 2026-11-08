# Local evaluation

Evaluated on 2026-11-08 using Python 3.12.13 on Windows. These results cover the
offline analyzer. Cloud deployment, model quality and retrieval have not been evaluated.

| Check | Result |
| --- | --- |
| Automated tests | 154 passed |
| Normalization and policy coverage, including branches | 97.58% |
| Four policy rule functions | 100% coverage |
| Required synthetic scenarios | All eight expectations passed |
| Ruff lint and formatting | Passed |
| Strict mypy checks | Passed |
| JSON Schema validity, fixture validation and schema drift | Passed |
| Offline demo | Four HIGH findings, JSON and Markdown output |
| Isolated runtime-only demo | Passed |
| Dependency audit | No known vulnerabilities reported |
| Source archive and wheel | Built successfully |

The tests cover rule positives, negatives and edge cases; IAM membership changes;
public access prevention; firewall protocols and port ranges; deletion and replacement;
input size and depth limits; sensitive-value exclusion; sanitized errors; and
execution with network access denied.

## Reproduce

```sh
uv sync --locked
uv run --locked python scripts/check.py
uv run --locked python scripts/demo_offline.py
uv run --locked python scripts/benchmark.py
uv build
```

The recorded standalone benchmark normalized and reported 100 synthetic changes
in 0.003826 seconds. The automated performance test also passed the two-second
acceptance threshold. Timing depends on the machine and does not predict cloud latency.

GNU Make was unavailable on the evaluation machine. Native Python/uv commands were
verified; the corresponding Make targets were not executed.

## Limits

All fixtures are synthetic. The offline analyzer checks four explicit policies;
an empty finding list is not a guarantee of safety. Reports describe proposed
changes and do not verify deployed exposure, IAM effectiveness or recovery readiness.
See the [normalization scope](normalization.md) and [threat model](threat-model.md).
