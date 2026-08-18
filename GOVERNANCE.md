# Governance

This is a single-maintainer project. This file states how decisions are made -
honestly, without invented committees.

## Roles

- **Maintainer** (final say on everything): [@FrancoisLDaigneault](https://github.com/FrancoisLDaigneault).
- **AI agents** execute day-to-day changes under the maintainer's
  orchestration. Every change that lands on `main` goes through a pull
  request, the automated gates, and an independent review before merge; the
  `main-protection` ruleset rejects direct pushes for everyone.

## Decisions

Significant technical decisions are recorded as ADRs in
[`docs/adr/`](docs/adr/README.md) (context, decision, consequences). Accepted
ADRs are superseded by new ones, not rewritten.

## Changing the baseline

`src/governance_tools/baseline.json` is the policy this repository enforces on
others, so a change to it is a governance decision, not a code tweak:

- Every desired value must mirror a verified live state, not an assumption.
- A control may not encode a value looser than GitHub's own default.
- Adding or removing a control changes the fleet matrix; run the audit before
  and after, and record the difference in the pull request.

The repository applies its own baseline to itself, so a change that would break
a repository breaks this one first.

## Contributions, releases, security

- Contribution path and quality gates: [`CONTRIBUTING.md`](CONTRIBUTING.md).
- Releases are automated: release-please opens a release PR from the
  Conventional Commits on `main`; merging it publishes the tag, changelog and
  signed release assets.
- Security reports: [`SECURITY.md`](SECURITY.md).
