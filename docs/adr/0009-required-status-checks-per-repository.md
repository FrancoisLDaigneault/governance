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

An organization-wide rule was considered and rejected: `fld-forge/.github`
carries no CI at all (community files and ruleset definitions only), so a
required-checks rule in the `mature-discipline` org ruleset would block every
merge there permanently, and the check contexts differ between repositories.

## Decision

Required status checks are governed **per repository**, in the repo-level
`main-protection` ruleset of the baseline:

- The `required_status_checks` rule requires `quality`, `pip-audit`,
  `secrets-scan`, `zizmor` and `CodeQL`, with
  `strict_required_status_checks_policy: true` (the branch must be up to date
  with the base before merging).
- `fld-forge/.github` is carved out through a baseline **override**: a control
  may carry per-target replacement `desired`/`apply_payload` values, keyed by
  OWNER/REPO. Same projection, same endpoints — only what is desired differs,
  and the full per-target value stays readable in `baseline.json`.
- The `mature-discipline` org ruleset is hardened to squash-only merges
  (`allowed_merge_methods: ["squash"]`) in the same wave: rebase merges rewrite
  commits without re-signing them, which `required_signatures` then rejects.

**Activation is deliberately deferred.** This ADR lands the definitions; the
live rulesets are only normalized to them (phase 2) after
`RELEASE_PLEASE_TOKEN` exists in every repository whose release PRs must
satisfy the checks. Applying the checks rule before the token is in place
recreates the ADR-0005 deadlock, exactly as that record warned.

## Consequences

Until phase 2 runs, the audit reports DRIFT on `ruleset-main-protection` for
`pi-config` and `governance`: live rulesets do not yet carry the checks rule.
That drift is the honest state of a fleet in transition, not noise to silence.

After phase 2, a red or missing check blocks the merge at the platform level,
`.github` keeps its checks-free ruleset through the override, and the audit
guards all of it. The strict policy means a stale release PR must be updated
(release-please force-refreshes its branches on every push to main).

The override mechanism is repo-scope only, validated at load time, and
wholesale: an override replaces the whole desired value rather than merging
fragments, so no reader ever has to compute the effective state.
