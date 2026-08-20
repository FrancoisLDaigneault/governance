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
| [0005](0005-branch-protection-without-required-checks.md) | Branch protection without required status checks | superseded by 0009 |
| [0006](0006-signed-commits-and-the-enablement-order.md) | Signed commits, and the order in which the rule is enabled | accepted |
| [0007](0007-organization-scope-is-a-separate-baseline.md) | Organization scope is a separate baseline, not a control kind | accepted |
| [0008](0008-pre-commit-framework-replaces-the-shell-hook.md) | pre-commit framework replaces the versioned shell hook | accepted |
| [0009](0009-required-status-checks-per-repository.md) | Required status checks, per repository, behind the release-please token | accepted |
| [0010](0010-fleet-standard-alignment.md) | Alignment on the fleet repository standard | accepted |
| [0011](0011-uv-native-dependency-audit.md) | uv-native dependency audit | accepted |
| [0012](0012-standalone-semgrep-ce-gate.md) | Standalone Semgrep CE gate | accepted |
| [0013](0013-complementary-static-and-supply-chain-gates.md) | Complementary static and supply-chain gates | accepted |

Conventions: MADR-lite, numbered, immutable once accepted (supersede with a
new ADR instead of editing history). New significant decisions get the next
number.
