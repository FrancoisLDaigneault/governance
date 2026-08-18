# NORTHSTAR - governance

Steering KPIs for this repository (the governance baseline as code: it applies
and audits GitHub repository settings across a fleet). One North Star KPI per
axis, plus supporting indicators. Every value is measured; an unmeasured value
is written as unmeasured, never invented. Updated whenever a measurement
changes category.

## Speed

North Star KPI:

| KPI | Current | Target | Measurement |
| --- | --- | --- | --- |
| Fleet audit duration | 31 s (11 repositories) | < 60 s for the current fleet | `uv run python scripts/audit.py --all`, wall clock |

Supporting indicators:

| Indicator | Current | Target | Measurement |
| --- | --- | --- | --- |
| Test suite duration | 1.1 s (139 tests) | < 5 s | `uv run pytest -q` (CI gate) |
| Time to bring one repository to compliance | not yet measured | < 2 min wall clock | Time `scripts/bootstrap.py OWNER/REPO --apply` end to end |

Measurement cadence: CI runs on every push/PR to `main` and every Tuesday at
06:00 UTC - the weekly run catches bit-rot without anyone pushing.

## Security

North Star KPI:

| KPI | Current | Target | Measurement |
| --- | --- | --- | --- |
| Repository settings written without an explicit `--apply` | 0 | 0, always | Tests assert `gh.mutations == []` on every dry-run path |

Supporting indicators:

| Indicator | Current | Target | Measurement |
| --- | --- | --- | --- |
| Fleet drift cells | 39 of 110 (10 controls x 11 repos) | trending to 0 on governed repos | `uv run python scripts/audit.py --all` |
| Controls looser than GitHub's default | 0 | 0, always | Baseline review at each change (`GOVERNANCE.md`) |
| Release integrity (SBOM + provenance attestation) | not yet measured (no release cut) | every release verified | release assets + `gh attestation verify` (see `SECURITY.md`) |
| Open vulnerability alerts / time-to-patch | baseline not yet recorded | record baseline, then 0 critical open | GitHub Security tab (CodeQL, pip-audit, Dependabot, secret scanning) |

## Maintainability

North Star KPI:

| KPI | Current | Target | Measurement |
| --- | --- | --- | --- |
| Branch coverage | 99.51% | >= 90% (enforced floor) | every full `uv run pytest` run (hook + CI + `just check`) |

Supporting indicators:

| Indicator | Current | Target | Measurement |
| --- | --- | --- | --- |
| Ruff violations (C901=8, PLR0915=30, PLR0913=5) | 0 | 0 | `uv run ruff check .` (pre-commit hook + CI) |
| src module / script size | max 162 / 8 lines | <= 200 / <= 20 | `tests/unit/test_standards.py` (the limit is a test) |
| Green tests | 139 (129 unit / 10 integration) | 100% green | `uv run pytest` (hook + CI) |
| Modules performing IO | 1 of 8 (`gh.py`) | stays 1 | Import review; everything else takes a `GhClient` |

## Scalability

(For this tool, scalability means the baseline keeps holding as the fleet and
the control set grow.)

North Star KPI:

| KPI | Current | Target | Measurement |
| --- | --- | --- | --- |
| Cost per audited repository | 2.8 s (31 s / 11 repos) | stays under 5 s per repo | Fleet audit duration divided by repository count |

Supporting indicators:

| Indicator | Current | Target | Measurement |
| --- | --- | --- | --- |
| Governed controls | 10 | grows only with a recorded decision | `src/governance_tools/baseline.json` |
| Repositories covered by a fleet audit | 11 (every non-archived repo owned) | 100% of owned repositories | `scripts/audit.py --all` enumerates them |
| Unaudited repository able to pass a run | 0 (structurally impossible) | 0, always | Missing controls back-fill as `ERR` and force a non-zero exit |

A KPI that is always green effortlessly should be tightened; a KPI that is always red should be fixed or dropped.
