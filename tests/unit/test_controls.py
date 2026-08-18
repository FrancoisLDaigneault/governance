"""Control IO against a fake gh: the read/apply behaviours that must not regress."""

import json

import pytest
from conftest import FakeGh, fail, ok

from governance_tools.baseline import Control
from governance_tools.compare import canon
from governance_tools.controls import (
    ABSENT,
    apply_control,
    endpoint_for,
    fetch_ruleset,
    read_live,
)

RULESET = Control(
    id="rs",
    kind="ruleset",
    applicability="public",
    desired={"name": "main-protection"},
    apply_method="POST",
    apply_endpoint="repos/{repo}/rulesets",
    read_endpoint="repos/{repo}/rulesets",
    projection="{name}",
    ruleset_name="main-protection",
    apply_payload={"name": "main-protection"},
)

FLAG = Control(
    id="flag",
    kind="status204",
    applicability="all",
    desired={"enabled": True},
    apply_method="PUT",
    apply_endpoint="repos/{repo}/vulnerability-alerts",
    read_endpoint="repos/{repo}/vulnerability-alerts",
)

JSON_CTL = Control(
    id="j",
    kind="json",
    applicability="all",
    desired={"status": "enabled"},
    apply_method="PATCH",
    apply_endpoint="repos/{repo}",
    read_endpoint="repos/{repo}",
    projection="{status}",
    apply_payload={"status": "enabled"},
)

PRESERVING = Control(
    id="perm",
    kind="json",
    applicability="all",
    desired={"default_workflow_permissions": "read"},
    apply_method="PUT",
    apply_endpoint="repos/{repo}/actions/permissions/workflow",
    read_endpoint="repos/{repo}/actions/permissions/workflow",
    projection="{default_workflow_permissions}",
    apply_payload={"default_workflow_permissions": "read"},
    apply_preserve="{can_approve_pull_request_reviews}",
)


def test_endpoint_substitutes_the_repo() -> None:
    assert endpoint_for("repos/{repo}/x", "o/r") == "repos/o/r/x"


def test_ruleset_absent_reads_as_absent() -> None:
    gh = FakeGh(rules=[("includes_parents", ok(""))])
    state = read_live(gh, RULESET, "o/r")
    assert state.canonical == ABSENT
    assert state.ruleset_id == ""


def test_ruleset_present_reads_its_projection() -> None:
    gh = FakeGh(
        rules=[("includes_parents", ok("42")), ("rulesets/42", ok('{"name":"main-protection"}'))]
    )
    state = read_live(gh, RULESET, "o/r")
    assert state.ruleset_id == "42"
    assert state.canonical == canon({"name": "main-protection"})


def test_ruleset_listing_failure_is_a_read_error() -> None:
    gh = FakeGh(rules=[("includes_parents", fail("HTTP 403: Forbidden"))])
    state = read_live(gh, RULESET, "o/r")
    assert state.error == "HTTP 403: Forbidden"
    assert state.canonical == ""


def test_ruleset_projection_failure_is_a_read_error() -> None:
    gh = FakeGh(rules=[("includes_parents", ok("7")), ("rulesets/7", fail("HTTP 500"))])
    state = read_live(gh, RULESET, "o/r")
    assert state.error == "HTTP 500"


def test_status204_success_means_enabled() -> None:
    assert read_live(FakeGh(), FLAG, "o/r").canonical == canon({"enabled": True})


def test_status404_means_disabled_not_an_error() -> None:
    gh = FakeGh(rules=[("vulnerability-alerts", fail("gh: HTTP 404 Not Found"))])
    state = read_live(gh, FLAG, "o/r")
    assert state.canonical == canon({"enabled": False})
    assert state.error == ""


def test_status403_is_an_error_not_disabled() -> None:
    """The distinction that matters: auth failure must never read as 'disabled'."""
    gh = FakeGh(rules=[("vulnerability-alerts", fail("HTTP 403: Forbidden"))])
    state = read_live(gh, FLAG, "o/r")
    assert state.error == "HTTP 403: Forbidden"
    assert state.canonical == ""


def test_network_failure_is_an_error() -> None:
    gh = FakeGh(rules=[("vulnerability-alerts", fail("dial tcp: lookup api.github.com"))])
    assert read_live(FakeGh(rules=gh.rules), FLAG, "o/r").error.startswith("dial tcp")


def test_json_control_reads_projection() -> None:
    gh = FakeGh(rules=[("repos/o/r", ok('{"status":"enabled"}'))])
    assert read_live(gh, JSON_CTL, "o/r").canonical == canon({"status": "enabled"})


def test_json_control_read_failure() -> None:
    gh = FakeGh(rules=[("repos/o/r", fail("HTTP 401"))])
    assert read_live(gh, JSON_CTL, "o/r").error == "HTTP 401"


def test_fetch_ruleset_raises_when_the_read_fails() -> None:
    """A failed stricter-check must never read as 'not stricter'."""
    gh = FakeGh(rules=[("rulesets/9", fail("HTTP 502"))])
    with pytest.raises(RuntimeError, match="HTTP 502"):
        fetch_ruleset(gh, "repos/o/r/rulesets/9")


def test_fetch_ruleset_tolerates_unparseable_success() -> None:
    gh = FakeGh(rules=[("rulesets/9", ok("not json"))])
    assert fetch_ruleset(gh, "repos/o/r/rulesets/9") == {}


def test_fetch_ruleset_ignores_non_object_json() -> None:
    gh = FakeGh(rules=[("rulesets/9", ok("[1,2]"))])
    assert fetch_ruleset(gh, "repos/o/r/rulesets/9") == {}


def test_fetch_ruleset_returns_the_object() -> None:
    gh = FakeGh(rules=[("rulesets/9", ok('{"rules":[]}'))])
    assert fetch_ruleset(gh, "repos/o/r/rulesets/9") == {"rules": []}


def test_apply_creates_a_new_ruleset_with_post() -> None:
    gh = FakeGh()
    assert apply_control(gh, RULESET, "o/r", "").ok
    call = gh.mutations[0]
    assert "POST" in call.args
    assert call.args[-2:] == ("--input", "-")
    assert json.loads(call.stdin or "") == {"name": "main-protection"}


def test_apply_updates_an_existing_ruleset_with_put_on_its_id() -> None:
    gh = FakeGh()
    apply_control(gh, RULESET, "o/r", "42")
    call = gh.mutations[0]
    assert "PUT" in call.args
    assert "repos/o/r/rulesets/42" in call.joined


def test_apply_without_payload_sends_an_empty_body() -> None:
    gh = FakeGh()
    apply_control(gh, FLAG, "o/r", "")
    call = gh.mutations[0]
    assert call.stdin is None
    assert "--input" not in call.args


def test_apply_preserve_merges_the_ungoverned_field() -> None:
    gh = FakeGh(rules=[("can_approve", ok('{"can_approve_pull_request_reviews":true}'))])
    assert apply_control(gh, PRESERVING, "o/r", "").ok
    body = json.loads(gh.mutations[0].stdin or "")
    assert body == {
        "can_approve_pull_request_reviews": True,
        "default_workflow_permissions": "read",
    }


def test_apply_preserve_refuses_when_the_read_fails() -> None:
    gh = FakeGh(rules=[("can_approve", fail("HTTP 500"))])
    result = apply_control(gh, PRESERVING, "o/r", "")
    assert not result.ok
    assert "refusing to write" in result.stderr
    assert gh.mutations == [], "no write may be issued when the preserve read failed"


def test_apply_preserve_refuses_on_empty_read() -> None:
    gh = FakeGh(rules=[("can_approve", ok("   "))])
    assert not apply_control(gh, PRESERVING, "o/r", "").ok
    assert gh.mutations == []


def test_apply_preserve_refuses_on_null_read() -> None:
    gh = FakeGh(rules=[("can_approve", ok('{"can_approve_pull_request_reviews":null}'))])
    assert not apply_control(gh, PRESERVING, "o/r", "").ok
    assert gh.mutations == []


def test_apply_preserve_refuses_on_unparseable_read() -> None:
    gh = FakeGh(rules=[("can_approve", ok("<html>"))])
    assert not apply_control(gh, PRESERVING, "o/r", "").ok
    assert gh.mutations == []


def test_apply_preserve_refuses_on_non_object_read() -> None:
    gh = FakeGh(rules=[("can_approve", ok("[1]"))])
    assert not apply_control(gh, PRESERVING, "o/r", "").ok
    assert gh.mutations == []


def test_unparseable_json_response_is_an_error_not_drift() -> None:
    """gh can exit 0 and print something that is not JSON; that is a read error."""
    gh = FakeGh(rules=[("repos/o/r", ok("not json"))])
    state = read_live(gh, JSON_CTL, "o/r")
    assert state.error.startswith("unparseable response:")
    assert state.canonical == ""


def test_unparseable_ruleset_response_is_an_error_not_drift() -> None:
    gh = FakeGh(rules=[("includes_parents", ok("7")), ("rulesets/7", ok("<html>"))])
    state = read_live(gh, RULESET, "o/r")
    assert state.error.startswith("unparseable response:")
    assert state.ruleset_id == "7", "the id stays available for the caller"


def test_apply_preserve_accepts_a_value_containing_the_word_null() -> None:
    """The null check reads the parsed value, not the raw text."""
    gh = FakeGh(rules=[("can_approve", ok('{"policy":"nullable"}'))])
    result = apply_control(gh, PRESERVING, "o/r", "")
    assert result.ok
    assert json.loads(gh.mutations[0].stdin or "")["policy"] == "nullable"
