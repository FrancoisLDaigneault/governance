# Architecture Decision Records

Significant technical decisions for this repository, recorded as short ADRs
(context / decision / consequences). The "why" behind the tooling lives here
so it does not have to be re-litigated; the "what" is enforced by the gates
themselves.

| ADR | Title | Status |
| --- | --- | --- |
| [0001](0001-governance-tooling-in-its-own-repository.md) | Governance tooling lives in its own repository | accepted |
| [0002](0002-python-rewrite-over-shell.md) | Python rewrite of the shell reference implementation | accepted |
| [0003](0003-pure-logic-separated-from-io.md) | Pure logic separated from IO as a security property | accepted |
| [0004](0004-desired-state-with-a-stricter-guard.md) | Desired state, not a minimum floor, with a stricter-than-baseline guard | accepted |
| [0005](0005-branch-protection-without-required-checks.md) | Branch protection without required status checks | accepted |
| [0006](0006-signed-commits-and-the-enablement-order.md) | Signed commits, and the order in which the rule is enabled | accepted |

Conventions: MADR-lite, numbered, immutable once accepted (supersede with a
new ADR instead of editing history). New significant decisions get the next
number.
