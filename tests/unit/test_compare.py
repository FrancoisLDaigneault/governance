"""The pure comparison core: canonical JSON and the stricter-than-baseline guard."""

from governance_tools.compare import canon, canon_text, stricter_extras

BASE_DESIRED: dict[str, object] = {
    "conditions": {"ref_name": {"exclude": [], "include": ["~DEFAULT_BRANCH"]}},
    "pr": {
        "dismiss_stale_reviews_on_push": False,
        "require_code_owner_review": False,
        "require_last_push_approval": False,
        "required_approving_review_count": 0,
        "required_review_thread_resolution": False,
    },
    "rule_types": ["deletion", "non_fast_forward", "pull_request", "required_signatures"],
}


def live_ruleset(**overrides: object) -> dict[str, object]:
    """A live ruleset that matches BASE_DESIRED unless overridden."""
    live: dict[str, object] = {
        "conditions": {"ref_name": {"exclude": [], "include": ["~DEFAULT_BRANCH"]}},
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "required_signatures"},
            {
                "type": "pull_request",
                "parameters": {
                    "required_approving_review_count": 0,
                    "dismiss_stale_reviews_on_push": False,
                    "require_code_owner_review": False,
                    "require_last_push_approval": False,
                    "required_review_thread_resolution": False,
                },
            },
        ],
    }
    live.update(overrides)
    return live


def test_canon_sorts_keys_and_strips_whitespace() -> None:
    assert canon({"b": 1, "a": {"d": 2, "c": 3}}) == '{"a":{"c":3,"d":2},"b":1}'


def test_canon_text_parses_then_canonicalizes() -> None:
    assert canon_text('{ "b": 1,\n  "a": 2 }') == '{"a":2,"b":1}'


def test_canon_text_treats_empty_output_as_null() -> None:
    assert canon_text("   \n ") == "null"


def test_canon_text_is_idempotent() -> None:
    once = canon_text('{"b":[3,1],"a":{"z":1,"y":2}}')
    assert canon_text(once) == once


def test_matching_ruleset_has_no_extras() -> None:
    assert stricter_extras(live_ruleset(), BASE_DESIRED) == []


def test_extra_rule_type_is_stricter() -> None:
    live = live_ruleset()
    rules = live["rules"]
    assert isinstance(rules, list)
    rules.append({"type": "required_linear_history"})
    assert stricter_extras(live, BASE_DESIRED) == ["- extra rule type: required_linear_history"]


def test_missing_rule_type_is_not_stricter() -> None:
    """A weaker live ruleset is plain drift, never a stricter-than-baseline skip."""
    live = live_ruleset(rules=[{"type": "deletion"}])
    assert stricter_extras(live, BASE_DESIRED) == []


def test_extra_protected_ref_is_stricter() -> None:
    live = live_ruleset(
        conditions={"ref_name": {"exclude": [], "include": ["~DEFAULT_BRANCH", "refs/heads/*"]}}
    )
    assert stricter_extras(live, BASE_DESIRED) == ["- extra protected ref: refs/heads/*"]


def test_baseline_exclusion_not_excluded_live_is_stricter() -> None:
    desired = dict(BASE_DESIRED)
    desired["conditions"] = {
        "ref_name": {"exclude": ["refs/heads/tmp"], "include": ["~DEFAULT_BRANCH"]}
    }
    assert stricter_extras(live_ruleset(), desired) == [
        "- ref excluded by baseline but protected live: refs/heads/tmp"
    ]


def test_higher_review_count_is_stricter() -> None:
    live = live_ruleset()
    rules = live["rules"]
    assert isinstance(rules, list)
    rules[3]["parameters"] = {"required_approving_review_count": 2}
    assert stricter_extras(live, BASE_DESIRED) == [
        "- required_approving_review_count: live 2 > baseline 0"
    ]


def test_lower_review_count_is_not_stricter() -> None:
    desired = dict(BASE_DESIRED)
    desired["pr"] = {"required_approving_review_count": 3}
    assert stricter_extras(live_ruleset(), desired) == []


def test_each_review_flag_enabled_live_is_stricter() -> None:
    flags = (
        "dismiss_stale_reviews_on_push",
        "require_code_owner_review",
        "require_last_push_approval",
        "required_review_thread_resolution",
    )
    for flag in flags:
        live = live_ruleset()
        rules = live["rules"]
        assert isinstance(rules, list)
        rules[3]["parameters"] = {flag: True}
        assert stricter_extras(live, BASE_DESIRED) == [
            f"- {flag}: enabled live, not required by baseline"
        ], f"{flag} was not detected as stricter"


def test_flag_required_by_baseline_is_not_extra() -> None:
    desired = dict(BASE_DESIRED)
    desired["pr"] = {"require_code_owner_review": True}
    live = live_ruleset()
    rules = live["rules"]
    assert isinstance(rules, list)
    rules[3]["parameters"] = {"require_code_owner_review": True}
    assert stricter_extras(live, desired) == []


def test_review_extras_skipped_when_no_pull_request_rule() -> None:
    live = live_ruleset(rules=[{"type": "deletion"}])
    desired = dict(BASE_DESIRED)
    desired["rule_types"] = ["deletion"]
    assert stricter_extras(live, desired) == []


def test_malformed_live_shapes_are_tolerated() -> None:
    """Unexpected types must not raise: the guard runs on whatever the API sent."""
    assert stricter_extras({"rules": "not-a-list", "conditions": 5}, BASE_DESIRED) == []


def test_boolean_is_not_treated_as_a_review_count() -> None:
    live = live_ruleset()
    rules = live["rules"]
    assert isinstance(rules, list)
    rules[3]["parameters"] = {"required_approving_review_count": True}
    assert stricter_extras(live, BASE_DESIRED) == []
