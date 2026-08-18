# ADR-0001: Governance tooling lives in its own repository

- Status: accepted
- Date: 2026-08-18

## Context

The baseline, the bootstrap command and the fleet audit were first built as a
subdirectory of an unrelated project, because that project happened to hold the
hand-maintained platform-settings inventory the baseline was derived from.
That was convenience, not cohesion: governing the GitHub settings of *other*
repositories is its own product, with its own blast radius, its own release
cadence and its own audience.

The mismatch showed up in the tooling before anyone named it. The governance
directory was excluded from the host project's wheel; none of that project's
gates covered it, because they were Python-only and this was shell; and a
dedicated shellcheck job had to be bolted on for this directory alone.

## Decision

Give the governance tooling its own repository, with its own full apparatus:
CI, gates, release chain and governance documents. The host project keeps only
what is about itself.

## Consequences

Each repository states one purpose, and neither borrows the other's
infrastructure. This one carries the cost of its own apparatus, which is the
honest price of the separation.

`baseline.json` is the executable form of the desired state for the fleet. Where
a repository also keeps a human-readable settings inventory of its own, the two
are reconciled by running an audit against that repository - never by editing
one document to match the other.
