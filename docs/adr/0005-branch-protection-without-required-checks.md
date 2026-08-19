# ADR-0005: Branch protection without required status checks

- Status: superseded by [ADR-0009](0009-required-status-checks-per-repository.md)
- Date: 2026-08-17

## Context

Every governed repository changes only through pull requests: the branch
ruleset blocks direct pushes, force-pushes and branch deletion, with no bypass
actors. The obvious next tightening is to require status checks to pass before
a merge, so that no pull request can land red.

That tightening is unavailable, for a structural reason rather than a
preference. Release-automation pull requests are opened by a bot authenticated
with the workflow's default token, and GitHub deliberately does not trigger
workflow runs from events caused by that token - the anti-recursion rule that
stops a workflow from endlessly re-triggering itself. Those pull requests
therefore carry no check runs at all. A required-checks rule waits for a check
that will never be reported, so every release pull request becomes permanently
unmergeable. It is a deadlock, not an inconvenience: the release train stops
and cannot be restarted without removing the rule.

## Decision

The branch ruleset requires a pull request, and deliberately does **not**
require status checks. Approving reviews are set to zero: a single maintainer
cannot approve their own pull request, and review happens before the merge in
the orchestrated process rather than as a platform approval.

What the ruleset does enforce, and what compensates:

- **Pull requests only** - direct pushes to the protected branch are rejected.
- **No bypass actors** - the rule applies to the owner as well.
- **Required signatures** (ADR-0006) - every commit on the branch is verified.
- **Protected tags** - release tags cannot be deleted or moved.
- **Immutable releases** - published assets and their tag are frozen.
- **Post-merge CI is authoritative** - the merge commit is always built and
  tested on the protected branch, so a red result is caught there.

Check verification before a merge is procedural: the pull request's checks are
read and required to be green by the process that performs the merge, not by
the platform.

## Consequences

**A maintainer who "hardens" this by adding required status checks will break
releases in every governed repository.** The failure is not obvious from the
setting: normal pull requests keep merging, and only the automated release
pull requests hang, indefinitely, with no error message beyond an unsatisfied
requirement. That warning is the reason this ADR exists.

The accepted trade-off is that a green pull request is a process guarantee
rather than a platform guarantee. External posture scanners score this as
incomplete branch protection; the score is correct about the mechanism and
wrong about the risk, and it should be read next to this record.

Revisit if GitHub ever lets a required-checks rule exempt bot-authored release
pull requests cleanly. Until then, the compensating controls above are the
answer, and they are enforced by the baseline rather than remembered.
