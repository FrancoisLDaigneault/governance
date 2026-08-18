"""Property-based tests for the pure comparison core.

The invariant that matters: adding protection live must ALWAYS be reported as
stricter (so it is skipped), never silently normalized away.
"""

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from governance_tools.compare import canon, canon_text, stricter_extras

settings.register_profile("deterministic", derandomize=True, max_examples=50, deadline=None)
settings.load_profile("deterministic")

RULE_TYPES = ("deletion", "non_fast_forward", "pull_request", "required_signatures")
EXTRA_TYPES = ("required_linear_history", "required_status_checks", "creation", "update")

json_values = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text(),
    lambda children: (
        st.lists(children, max_size=4)
        | st.dictionaries(st.text(min_size=1, max_size=8), children, max_size=4)
    ),
    max_leaves=12,
)


def desired_from(types: list[str], refs: list[str]) -> dict[str, object]:
    return {
        "rule_types": sorted(types),
        "conditions": {"ref_name": {"include": sorted(refs), "exclude": []}},
    }


def live_from(types: list[str], refs: list[str]) -> dict[str, object]:
    return {
        "rules": [{"type": t} for t in types],
        "conditions": {"ref_name": {"include": refs, "exclude": []}},
    }


@given(value=json_values)
def test_canon_is_idempotent(value: object) -> None:
    once = canon(value)
    assert canon_text(once) == once


@given(value=st.dictionaries(st.text(min_size=1, max_size=6), st.integers(), max_size=5))
def test_canon_round_trips_through_json(value: dict[str, int]) -> None:
    assert json.loads(canon(value)) == value


@given(
    types=st.lists(st.sampled_from(RULE_TYPES), min_size=1, max_size=4, unique=True),
    refs=st.lists(st.text(min_size=1, max_size=6), min_size=1, max_size=3, unique=True),
)
def test_live_equal_to_baseline_is_never_stricter(types: list[str], refs: list[str]) -> None:
    assert stricter_extras(live_from(types, refs), desired_from(types, refs)) == []


@given(
    types=st.lists(st.sampled_from(RULE_TYPES), min_size=1, max_size=4, unique=True),
    refs=st.lists(st.text(min_size=1, max_size=6), min_size=1, max_size=3, unique=True),
    extra=st.sampled_from(EXTRA_TYPES),
)
def test_extra_rule_type_always_reported(types: list[str], refs: list[str], extra: str) -> None:
    live = live_from([*types, extra], refs)
    assert f"- extra rule type: {extra}" in stricter_extras(live, desired_from(types, refs))


@given(
    types=st.lists(st.sampled_from(RULE_TYPES), min_size=1, max_size=4, unique=True),
    refs=st.lists(st.text(min_size=1, max_size=6), min_size=1, max_size=3, unique=True),
    extra=st.text(min_size=1, max_size=6),
)
def test_extra_protected_ref_always_reported(types: list[str], refs: list[str], extra: str) -> None:
    if extra in refs:
        return
    live = live_from(types, [*refs, extra])
    assert f"- extra protected ref: {extra}" in stricter_extras(live, desired_from(types, refs))


@given(
    types=st.lists(st.sampled_from(RULE_TYPES), min_size=2, max_size=4, unique=True),
    refs=st.lists(st.text(min_size=1, max_size=6), min_size=1, max_size=3, unique=True),
)
def test_removing_protection_is_drift_not_stricter(types: list[str], refs: list[str]) -> None:
    """A weaker live ruleset must fall through to normal drift handling."""
    live = live_from(types[:-1], refs)
    assert stricter_extras(live, desired_from(types, refs)) == []


@given(live=json_values, desired=json_values)
def test_guard_never_raises_on_arbitrary_input(live: object, desired: object) -> None:
    """The guard runs on whatever the API returned; it must never crash."""
    live_dict = live if isinstance(live, dict) else {}
    desired_dict = desired if isinstance(desired, dict) else {}
    assert isinstance(stricter_extras(live_dict, desired_dict), list)
