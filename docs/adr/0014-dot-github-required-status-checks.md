# ADR-0014: Repository-specific required checks for .github

- Status: accepted
- Date: 2026-08-20
- Amends: [ADR-0009](0009-required-status-checks-per-repository.md), [ADR-0013](0013-complementary-static-and-supply-chain-gates.md)

## Context

ADR-0009 established repository-specific required status checks because the
fleet does not emit one universal set of contexts. ADR-0013 later fixed the
Python repository profile at eight contexts. At those decision points,
`fld-forge/.github` did not emit the complete Python profile and its override
therefore required no checks.

The `.github` repository now emits two stable contexts: `CodeQL` for static
analysis and `validation` for its policy and configuration checks. Both have
reported successfully on pull requests. Leaving them optional would preserve
a known enforcement gap, while requiring the Python profile would deadlock
every pull request because those contexts do not exist in this repository.

## Decision

Keep the eight-context default for the Python repositories: `CodeQL`,
`dependency-review`, `pip-audit`, `quality`, `secrets-scan`, `semgrep`,
`uv-audit`, and `zizmor`.

Change only the `fld-forge/.github` baseline override to require exactly
`CodeQL` and `validation`, with strict status checks enabled. Preserve the
existing active enforcement, default-branch condition, zero bypass actors,
pull-request rule, signed commits, and deletion and force-push protections.

The override remains repository-specific; no organization-wide check names
are introduced. Apply the live ruleset only after this baseline change is
reviewed and both contexts have been observed on a pull request.

## Consequences

A missing, failed, or stale `.github` check blocks merging at the platform
level. The governance audit reports drift until ruleset `main-protection` is
normalized to the reviewed baseline.

The Python repositories retain their eight independent contexts unchanged.
Future context changes require a new ADR, a baseline update, successful pull
request evidence, and reviewed live application in that order. Rollback first
removes a context from the baseline and live ruleset, then removes its
workflow job, so the repository never waits on a context that cannot report.
