# ADR-0003: Pure logic separated from IO as a security property

- Status: accepted
- Date: 2026-08-18

## Context

This tool holds credentials that change settings on every repository it is
pointed at. Its dangerous behaviours are decisions, not network calls: *is this
drift or a read error, is the live ruleset stricter than the baseline, may this
control be written*. Testing those against the real API would be slow, would
mutate real repositories, and would be skipped in practice.

## Decision

`gh.py` is the only module that spawns a subprocess. Every other function takes
a `GhClient` (a one-method protocol), so the whole tool runs against a fake
backend that records calls. The comparison layer (`compare.py`) is pure: it
takes two dictionaries and returns strings.

The read path is total. A `gh` call that exits 0 while printing something that
is not JSON is mapped to a per-control error, never allowed to raise: an
exception escaping there would abort a fleet audit and lose repositories
already checked - the isolation the shell got for free from one subprocess per
repository.

## Consequences

The suite never touches the network, and the invariants are asserted directly:
`gh.mutations == []` on every dry-run path, a read failure never falling
through to a corrective write, an unparseable response costing exactly one
cell. `is_mutation` keys on the `-X` flag, which is safe because `api_write` is
the only function that emits it and it always does.

The cost is one indirection everywhere and a fake that must stay faithful to
`gh`'s real behaviour (exit codes, stdout/stderr split, the 404-vs-error
distinction). That fidelity is itself covered by tests naming each case.
