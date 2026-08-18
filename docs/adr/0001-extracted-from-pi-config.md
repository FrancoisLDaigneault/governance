# ADR-0001: Extracted from pi-config into its own repository

- Status: accepted
- Date: 2026-08-18

## Context

The baseline, the bootstrap script and the fleet audit were first built inside
[pi-config](https://github.com/FrancoisLDaigneault/pi-config), because that is
where the hand-maintained platform-settings inventory (`docs/repo-settings.md`)
already lived. pi-config does one thing: sync, restore and back up the Pi
configuration. Governing the GitHub settings of *other* repositories is a
different product with a different blast radius.

The mismatch showed up in the tooling before anyone named it: the governance
directory was excluded from the wheel, no existing gate covered it (ruff, mypy
and the test suite are Python-only, and it was shell), and a dedicated
shellcheck job had to be bolted on for it alone.

## Decision

Extract the governance tooling into this repository. `git subtree split`
preserved the available history. pi-config keeps `docs/adr/` and
`docs/repo-settings.md` - decisions and settings *about pi-config itself* - and
its shellcheck job was narrowed back to its own hook.

## Consequences

Each repository states one purpose. This one carries the cost of its own full
apparatus (CI, release chain, governance docs) instead of borrowing pi-config's,
which is the honest price of the separation. `docs/repo-settings.md` stays in
pi-config as its own inventory, while `baseline.json` here is the executable
form for the fleet; the two must be reconciled by running an audit against
pi-config, not by editing one to match the other.
