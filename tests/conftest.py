"""Shared test doubles.

Every test drives the real code through FakeGh: the suite never touches the
network, and mutations are recorded so "no write without --apply" is provable.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

import pytest

from governance_tools.baseline import Control, load_controls, split_by_scope
from governance_tools.compare import canon
from governance_tools.gh import GhResult


@dataclass(frozen=True)
class Call:
    """One recorded gh invocation."""

    args: tuple[str, ...]
    stdin: str | None = None

    @property
    def joined(self) -> str:
        return " ".join(self.args)

    @property
    def is_mutation(self) -> bool:
        return "-X" in self.args


@dataclass
class FakeGh:
    """Scripted gh backend: first rule whose pattern is in the command wins."""

    rules: list[tuple[str, GhResult]] = field(default_factory=list)
    default: GhResult = GhResult(0, "", "")
    calls: list[Call] = field(default_factory=list)

    def run(self, args: Sequence[str], stdin: str | None = None) -> GhResult:
        call = Call(tuple(args), stdin)
        self.calls.append(call)
        for pattern, result in self.rules:
            if pattern in call.joined:
                return result
        return self.default

    @property
    def mutations(self) -> list[Call]:
        return [c for c in self.calls if c.is_mutation]

    def override(self, pattern: str, result: GhResult) -> None:
        """Put a rule in front of the existing ones."""
        self.rules.insert(0, (pattern, result))


# Synthetic ruleset id prefix for organization controls. A numeric offset would
# not be enough: rules match by substring, and "rulesets/1" is a substring of
# "rulesets/100", so one scope would answer the other's detail call.
ORG_IDS = "org"


def ok(stdout: str = "") -> GhResult:
    return GhResult(0, stdout, "")


def fail(stderr: str, code: int = 1) -> GhResult:
    return GhResult(code, "", stderr)


def compliant_rules(
    controls: list[Control], visibility: str = "public", ruleset_prefix: str = ""
) -> list[tuple[str, GhResult]]:
    """Rules that make every control read back exactly its desired state.

    `ruleset_prefix` namespaces the synthetic ruleset ids so repository and
    organization rules can share one fake without answering each other's calls.
    """
    rules: list[tuple[str, GhResult]] = [
        ("--json visibility", ok(visibility)),
        ("--json isArchived", ok("false")),
    ]
    for index, control in enumerate(controls, start=1):
        if control.na_when:
            # "false" = the control does govern this target, so the run goes on
            # to compare state; a compliant fixture must not short-circuit to NA.
            rules.append((control.na_when, ok("false")))
        if control.kind == "ruleset":
            ruleset_id = f"{ruleset_prefix}{index}"
            rules.append((f'select(.name=="{control.ruleset_name}")', ok(ruleset_id)))
            rules.append((f"rulesets/{ruleset_id}", ok(canon(control.desired))))
        elif control.kind == "status204":
            rules.append((control.read_endpoint or "", ok()))
        else:
            rules.append((control.projection or "", ok(canon(control.desired))))
    return rules


@pytest.fixture
def controls() -> list[Control]:
    """The real repository controls, so tests exercise the shipped configuration."""
    return split_by_scope(load_controls())[0]


@pytest.fixture
def org_controls() -> list[Control]:
    """The real organization controls."""
    return split_by_scope(load_controls())[1]


@pytest.fixture
def compliant(controls: list[Control]) -> FakeGh:
    return FakeGh(rules=compliant_rules(controls))


@pytest.fixture
def compliant_org(org_controls: list[Control]) -> FakeGh:
    """Every organization control reads back exactly its desired state."""
    # The org_facts probe is matched on its jq filter, not on the endpoint: the
    # endpoint `orgs/o` is a prefix of several control reads and would shadow them.
    return FakeGh(
        rules=[("--jq .login", ok("o")), *compliant_rules(org_controls, ruleset_prefix=ORG_IDS)]
    )
