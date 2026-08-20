# ADR-0013: Complementary static and supply-chain gates

- Status: accepted
- Date: 2026-08-20
- Amends: [ADR-0009](0009-required-status-checks-per-repository.md), [ADR-0010](0010-fleet-standard-alignment.md)
- Supersedes in part: [ADR-0011](0011-uv-native-dependency-audit.md)

## Context

Independent analyzers make different trade-offs and can report issues that
another analyzer misses. ty provides fast diagnostics and warning severities,
while mypy's mature strict mode is a separate implementation of Python's type
system. Likewise, `uv audit` reads the uv lock graph and reports OSV plus
project-status data, while pip-audit consumes an exported requirements view.
GitHub Dependency Review adds a pull-request delta check before a changed
vulnerable dependency reaches the default branch.

Keeping only one tool in each pair reduces CI time but makes that tool's blind
spots a fleet-wide blind spot. The projects are small enough that the measured
cost is acceptable. The controls must remain independently visible and pinned
where their interfaces are still evolving.

## Decision

Run both type checkers in the required `quality` job and local quality gates:

```text
uv run ty check --error-on-warning src scripts tests
uv run mypy
```

Lock mypy 2.3.1 through the uv development group and configure strict mode for
`src`, `scripts`, and `tests` under Python 3.12. Keep ty 0.0.73 and its existing
warning-blocking configuration. Do not add global ignores to reconcile the
checkers; fix a real diagnostic narrowly.

Keep `uv audit --locked` and restore a separate `pip-audit` job. The latter
exports the locked graph without the project package, then runs pinned
pip-audit 2.10.1 with `--no-deps`, so it audits the export without performing a
second dependency resolution. Neither scanner replaces the other.

Run `actions/dependency-review-action` v5, pinned to a full commit SHA, only on
pull requests. It fails at moderate severity, disables license policy and PR
comments, and receives only `contents: read`.

The `main-protection` baseline requires eight sorted contexts: `CodeQL`,
`dependency-review`, `pip-audit`, `quality`, `secrets-scan`, `semgrep`,
`uv-audit`, and `zizmor`, with strict status checks enabled. As amended on
2026-08-20, the `.github` override requires its own `CodeQL` and `validation`
contexts instead of the full Python-profile context set.

Activation follows ADR-0009: prove every new context on feature and release
pull requests, merge the workflows, prove them again, review the exact ruleset
payload, and only then apply it without force normalization.

## Consequences

Type checking and dependency auditing consume more CI time and may produce
partially overlapping findings. That duplication is intentional defense in
depth. deptry, Hypothesis, Ruff, Semgrep, CodeQL, gitleaks, uv-audit and zizmor
remain in place; this decision neither adds mutation testing nor changes fleet
runtime behavior.

Dependency Review has no push or schedule signal because it compares a pull
request base and head. Registry and advisory availability can still fail the
networked gates. Future tool updates require independent validation rather
than assuming equivalent findings.

Rollback preserves mergeability: first remove a context from the reviewed
baseline and apply that narrower ruleset while all old checks still exist;
only then remove its workflow job. Removing mypy follows the same order inside
`quality`: update the documented local gate and dependency lock together, but
keep the stable `quality` context throughout.
