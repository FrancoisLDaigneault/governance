# ADR-0006: Signed commits, and the order in which the rule is enabled

- Status: accepted
- Date: 2026-08-17

## Context

Release artifacts carry cryptographically verified provenance attestations,
but nothing authenticated the commits that produced them: anyone holding a
token could commit under the maintainer's name. That asymmetry - signed
outputs, unsigned inputs - is the last unauthenticated link in the chain.

Most of the work turned out to be already done. Commits created by GitHub
itself, which is every squash merge and every release-automation commit, are
signed with its web-flow key and report as verified. A pull-request-only flow
therefore yields a protected branch whose history is already fully signed,
at no cost. What was missing was the branch commits written on a workstation,
and a rule to require the property instead of hoping for it.

## Empirical discovery, which dictates the order

The `required_signatures` rule gates **every commit on the pull-request
branch**, not only the squash commit that lands on the protected branch. This
was proven the expensive way: with the rule enabled but the workstation's
signing key not yet registered, the pull request introducing the rule blocked
itself. Its branch commit was signed locally and reported a good signature
offline, yet the API returned `verified: false` with reason `unknown_key`, and
the merge was refused. Removing the rule flipped the same pull request to a
clean, mergeable state with no other change.

Two facts follow from that reason code. `unknown_key` is not `unsigned`: the
signature is present and intact, and GitHub simply does not recognise the key.
Verification is therefore **retroactive** - registering the key flips existing
commits to verified without rewriting or re-signing anything.

## Decision

Commits are SSH-signed from the working clone, with signing configured
repo-locally rather than globally, and `required_signatures` is enforced by the
branch ruleset.

The enablement order is mandatory, and enabling out of order blocks every
pull request from that machine:

1. **Register the signing key** on the account first.
2. **Verify** that an existing branch commit now reports `verified: true`.
3. **Enable** the `required_signatures` rule only then.

## Consequences

A key uploaded under **Authentication keys** instead of **Signing keys**
produces exactly the `unknown_key` symptom, with a locally valid signature and
a rejected merge. The two key types are separate categories on the same
settings page, the upload form defaults to the authentication kind, and nothing
in the error names the mistake. Written down it is a one-minute fix; unwritten
it costs an hour of looking in the wrong place.

**Squash-merge is mandatory, permanently.** A rebase merge replays author
commits without re-signing them, so it would land commits on a
signature-gated branch that the branch's own rule would reject. The merge
method is therefore part of this decision, not a stylistic preference.

Any additional machine must register its own signing key before it can merge;
its pull requests are blocked until then, by design. Release-automation pull
requests are unaffected, since bot commits are web-flow signed.

Existing history predating the rule stays unverified. Ruleset rules gate new
pushes only, so the rule can be adopted without rewriting history.
