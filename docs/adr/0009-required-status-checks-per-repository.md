# ADR-0009: Required status checks, per repository, behind the release-please token

- Status: accepted
- Date: 2026-08-19
- Supersedes: [ADR-0005](0005-branch-protection-without-required-checks.md)

## Context

ADR-0005 deliberately left required status checks out of the branch ruleset:
release-automation pull requests are pushed with the workflow's default token,
GitHub triggers no CI on bot-token pushes (the anti-recursion rule), so a
required-checks rule would wait forever on checks that never report and every
release PR would deadlock.

Two things changed. First, the deadlock has a standard resolution: when
release-please pushes its branches with a fine-grained personal access token
(`RELEASE_PLEASE_TOKEN`, Contents + Pull requests read/write), the push is an
ordinary user event, CI runs on the release PR like on any other branch, and
the checks report. Second, the fleet audit proved the enforcement gap is real:
every quality gate in the fleet is green by discipline, not by constraint —
nothing on the platform refuses a merge with red CI.

An organization-wide rule was considered and rejected: check contexts differ
between repositories. At the time of this decision, `fld-forge/.github`
carried no CI at all; it now emits its own `CodeQL` and `validation` contexts,
but still does not emit the complete Python-profile context set.

## Decision

Required status checks are governed **per repository**, in the repo-level
`main-protection` ruleset of the baseline:

- The default `required_status_checks` rule requires `CodeQL`,
  `dependency-review`, `pip-audit`, `quality`, `secrets-scan`, `semgrep`,
  `uv-audit` and `zizmor`, with `strict_required_status_checks_policy: true`
  (the branch must be up to date with the base before merging).
- `fld-forge/.github` is carved out through a baseline **override** requiring
  exactly `CodeQL` and `validation`, the contexts that repository emits. A
  control may carry per-target replacement `desired`/`apply_payload` values,
  keyed by OWNER/REPO. Same projection, same endpoints — only what is desired
  differs, and the full per-target value stays readable in `baseline.json`.
- The `mature-discipline` org ruleset is hardened to squash-only merges
  (`allowed_merge_methods: ["squash"]`) in the same wave: rebase merges rewrite
  commits without re-signing them, which `required_signatures` then rejects.

Activation follows the definitions: each live ruleset is normalized only
after its required contexts have reported successfully on a pull request. The
release repositories also require `RELEASE_PLEASE_TOKEN`; applying their
checks before that token exists recreates the ADR-0005 deadlock. The `.github`
contexts have no release-token dependency.

## Consequences

Until a changed baseline is applied, the audit reports DRIFT for the affected
target. That drift is the honest state of a fleet in transition, not noise to
silence.

After activation, a red or missing check blocks the merge at the platform
level. The `.github` override requires its two repository-specific contexts,
and the audit guards all three repositories. The strict policy means a stale
pull request must be updated before merge.

The override mechanism is repo-scope only, validated at load time, and
wholesale: an override replaces the whole desired value rather than merging
fragments, so no reader ever has to compute the effective state.
