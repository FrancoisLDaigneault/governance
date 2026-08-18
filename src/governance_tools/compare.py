"""Pure comparison logic: canonical JSON and the stricter-than-baseline guard.

No IO here. Canonical form must stay byte-identical to the shell reference
implementation (sorted keys, compact separators) so projections compare as
plain strings.
"""

import json

REVIEW_FLAGS = (
    "dismiss_stale_reviews_on_push",
    "require_code_owner_review",
    "require_last_push_approval",
    "required_review_thread_resolution",
)


def canon(value: object) -> str:
    """Canonical JSON for any already-parsed value."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def canon_text(raw: str) -> str:
    """Canonical JSON for raw API output; empty output canonicalizes to null."""
    text = raw.strip()
    return canon(json.loads(text) if text else None)


def _obj(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _rules(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [r for r in value if isinstance(r, dict)]


def _strings(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {v for v in value if isinstance(v, str)}


def _count(value: object) -> int:
    """Review counts only; booleans are not counts even though bool is an int."""
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _rule_type_extras(live: dict[str, object], desired: dict[str, object]) -> list[str]:
    live_types = {t for r in _rules(live.get("rules")) if isinstance(t := r.get("type"), str)}
    wanted = _strings(desired.get("rule_types"))
    return [f"- extra rule type: {t}" for t in sorted(live_types - wanted)]


def _ref_scope_extras(live: dict[str, object], desired: dict[str, object]) -> list[str]:
    """Protecting more refs, or excluding fewer, is stricter than the baseline."""
    live_ref = _obj(_obj(live.get("conditions")).get("ref_name"))
    want_ref = _obj(_obj(desired.get("conditions")).get("ref_name"))
    extras = [
        f"- extra protected ref: {ref}"
        for ref in sorted(_strings(live_ref.get("include")) - _strings(want_ref.get("include")))
    ]
    extras += [
        f"- ref excluded by baseline but protected live: {ref}"
        for ref in sorted(_strings(want_ref.get("exclude")) - _strings(live_ref.get("exclude")))
    ]
    return extras


def _review_extras(live: dict[str, object], desired: dict[str, object]) -> list[str]:
    pull_rules = [r for r in _rules(live.get("rules")) if r.get("type") == "pull_request"]
    live_pr = _obj(pull_rules[0].get("parameters")) if pull_rules else None
    wanted_pr = desired.get("pr")
    if not live_pr or not isinstance(wanted_pr, dict):
        return []
    extras: list[str] = []
    live_n = _count(live_pr.get("required_approving_review_count"))
    want_n = _count(wanted_pr.get("required_approving_review_count"))
    if live_n > want_n:
        extras.append(f"- required_approving_review_count: live {live_n} > baseline {want_n}")
    extras += [
        f"- {flag}: enabled live, not required by baseline"
        for flag in REVIEW_FLAGS
        if live_pr.get(flag) and not wanted_pr.get(flag)
    ]
    return extras


def stricter_extras(live: dict[str, object], desired: dict[str, object]) -> list[str]:
    """Protections present live that the baseline does not ask for.

    A non-empty result means normalizing to the baseline would LOWER the live
    ruleset, so the control is skipped unless the operator forces it.
    """
    return (
        _rule_type_extras(live, desired)
        + _ref_scope_extras(live, desired)
        + _review_extras(live, desired)
    )
