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
| Fleet audit duration | 26.021 s (3 repositories + 1 organization) | < 60 s for the current fleet | `uv run python scripts/audit.py --all`, wall clock |

Supporting indicators:

| Indicator | Current | Target | Measurement |
| --- | --- | --- | --- |
| Test suite duration | 1.87 s (251 tests), 276 cases passed | < 5 s | `uv run pytest -q` (CI gate) |
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
| Fleet drift cells | 0 (3 repositories + 1 organization) | 0 | `uv run python scripts/audit.py --all` |
| Controls looser than GitHub's default | 0 | 0, always | Baseline review at each change (`GOVERNANCE.md`) |
| Release integrity (SBOM + provenance attestation) | v0.8.0 verified: 5 assets, attestation and checksums pass (2026-08-21) | every release verified | release assets + `gh attestation verify` (see `SECURITY.md`) |
| Open vulnerability alerts / time-to-patch | baseline not yet recorded | record baseline, then 0 critical open | GitHub Security tab (CodeQL, Dependency Review, `uv audit --locked`, pip-audit, Dependabot, secret scanning) |
| Semgrep CE findings | 0 in the adoption preflight | 0 | `uvx semgrep==1.173.0 scan --config p/python --metrics=off --error src scripts` (CI gate) |

## Maintainability

North Star KPI:

| KPI | Current | Target | Measurement |
| --- | --- | --- | --- |
| Branch coverage | 99.32% | >= 90% (enforced floor) | every full `uv run pytest` run (pre-commit framework + CI + `just check`) |

Supporting indicators:

| Indicator | Current | Target | Measurement |
| --- | --- | --- | --- |
| Static-analysis violations | 0 | 0 | Ruff, ty, mypy, deptry, Import Linter, Semgrep and CodeQL gates |
| Required pull-request checks | 8 of 8 green | 8 of 8 green | Live `main-protection` ruleset and PR check rollup |
| src module / script size | max 197 / 8 lines | <= 200 / <= 20 | `tests/unit/test_standards.py` (the limit is a test) |
| Green tests | 251 (237 unit / 14 integration), 276 cases passed | 100% green | `uv run pytest` (pre-commit framework + CI) |
| Modules performing network IO | 1 of 15 (`gh.py`) | stays 1 | Import Linter contracts; everything else takes a `GhClient` (`scheduled_audit` writes only its own log files) |

## Scalability

(For this tool, scalability means the baseline keeps holding as the fleet and
the control set grow.)

North Star KPI:

| KPI | Current | Target | Measurement |
| --- | --- | --- | --- |
| Cost per audited repository | 8.674 s (26.021 s / 3 repositories) | stays under 5 s per repo | Fleet audit duration divided by repository count |

Supporting indicators:

| Indicator | Current | Target | Measurement |
| --- | --- | --- | --- |
| Governed controls | 26 (14 repository, 12 organization) | grows only with a recorded decision | `src/governance_tools/baseline.json` |
| Repositories covered by a fleet audit | 3 (every non-archived `fld-forge` repo) | 100% of `fld-forge` repositories | `scripts/audit.py --all` enumerates them |
| Unaudited repository able to pass a run | 0 (structurally impossible) | 0, always | Missing controls back-fill as `ERR` and force a non-zero exit |

A KPI that is always green effortlessly should be tightened; a KPI that is always red should be fixed or dropped.
