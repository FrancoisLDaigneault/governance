# ADR-0015: Import boundaries as architecture fitness gates

- Status: accepted
- Date: 2026-08-20

## Context

The desired-state loader imported identifier validation from `gh.py`, coupling
pure configuration validation to the GitHub adapter. Repository checks also
lived in the bootstrap CLI even though the fleet audit reused them. Those
accidental dependencies were visible in review but not enforced.

## Decision

Move identifier validation mechanically to `identifiers.py` and shared
repository checks to `repository.py`. Keep `audit` and `bootstrap` mutually
independent with an Import Linter contract. Keep `baseline` from depending on
`gh` with a second contract.

Ruff TID251 confines `subprocess`, `socket`, `http.client` and `urllib.request`
to `gh.py`, and prevents production modules from importing tests or command
wrappers. Tests are exempt. Deptry continues to detect undeclared external
dependencies.

Run both gates through `just check`, pre-commit and the CI quality job. Do not
add a global layers contract: the package has no stable layer hierarchy that
would justify one.

## Consequences

Architectural drift now fails before merge. Import Linter is a locked
development dependency; the runtime remains stdlib-only. The extraction adds
no behavior, class, interface or factory. Future boundary changes must update
the contracts deliberately rather than bypassing the gate.
