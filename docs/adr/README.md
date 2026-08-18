# Architecture Decision Records

Significant technical decisions for this repository, recorded as short ADRs
(context / decision / consequences). The "why" behind the tooling lives here
so it does not have to be re-litigated; the "what" is enforced by the gates
themselves.

| ADR | Title | Status |
| --- | --- | --- |
| [0001](0001-extracted-from-pi-config.md) | Extracted from pi-config into its own repository | accepted |
| [0002](0002-python-rewrite-over-shell.md) | Python rewrite of the shell reference implementation | accepted |
| [0003](0003-pure-logic-separated-from-io.md) | Pure logic separated from IO as a security property | accepted |
| [0004](0004-desired-state-with-a-stricter-guard.md) | Desired state, not a minimum floor, with a stricter-than-baseline guard | accepted |

Conventions: MADR-lite, numbered, immutable once accepted (supersede with a
new ADR instead of editing history). New significant decisions get the next
number.
