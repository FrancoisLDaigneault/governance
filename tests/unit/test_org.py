"""Organization-scope checks.

The invariants under test: an organization control classifies like any other, a
control the API cannot write never reports a correction it did not make, and a
ruleset weakened to evaluate or handed a bypass actor is caught rather than
passed over.
"""

import pytest
from conftest import ORG_IDS, FakeGh, fail, ok

from governance_tools.baseline import Control
from governance_tools.compare import canon
from governance_tools.org import audit_orgs, check_org, org_facts
from governance_tools.report import DRIFT, ERR, MANUAL, OK, Mode

RULESET_ID = "org-ruleset-floor-no-destruction"
TWO_FACTOR = "org-two-factor-requirement"
MEMBER_MANUAL = "org-member-privileges-manual"
RETENTION = "org-actions-retention"


def _by_id(controls: list[Control], control_id: str) -> Control:
    return next(c for c in controls if c.id == control_id)


def _status(gh: FakeGh, controls: list[Control], control_id: str, mode: Mode | None = None) -> str:
    report = check_org(gh, controls, "o", mode)
    return next(r.status for r in report.results if r.control_id == control_id)


def test_compliant_org_is_all_ok(compliant_org: FakeGh, org_controls: list[Control]) -> None:
    report = check_org(compliant_org, org_controls, "o")
    assert report.error == ""
    assert {r.status for r in report.results} == {OK}
    assert compliant_org.mutations == [], "a dry run must never write"


def test_every_shipped_org_control_is_reported(
    compliant_org: FakeGh, org_controls: list[Control]
) -> None:
    report = check_org(compliant_org, org_controls, "o")
    assert [r.control_id for r in report.results] == [c.id for c in org_controls]


def test_unreadable_org_reports_an_error_and_no_results(org_controls: list[Control]) -> None:
    gh = FakeGh(rules=[("--jq .login", fail("HTTP 404: Not Found"))])
    report = check_org(gh, org_controls, "nope")
    assert "HTTP 404" in report.error
    assert report.results == []


def test_org_facts_is_empty_when_the_org_reads_back() -> None:
    assert org_facts(FakeGh(rules=[("--jq .login", ok("o"))]), "o") == ""


def test_org_read_failure_is_err_never_drift(
    compliant_org: FakeGh, org_controls: list[Control]
) -> None:
    """A failed read is an error, and must not fall through to a corrective write."""
    compliant_org.override("{days}", fail("HTTP 403: Forbidden"))
    assert _status(compliant_org, org_controls, RETENTION, Mode(apply=True)) == ERR
    assert compliant_org.mutations == []


def test_drifted_org_control_is_drift_in_dry_run(
    compliant_org: FakeGh, org_controls: list[Control]
) -> None:
    compliant_org.override("{days}", ok('{"days":90}'))
    assert _status(compliant_org, org_controls, RETENTION) == DRIFT
    assert compliant_org.mutations == []


def test_writable_org_control_is_applied(
    compliant_org: FakeGh, org_controls: list[Control]
) -> None:
    """The corrective call goes out, and the endpoint is the organization's."""
    calls = {"n": 0}
    drifted, desired = ok('{"days":90}'), ok('{"days":30}')

    class Healing(FakeGh):
        def run(self, args, stdin=None):  # type: ignore[no-untyped-def]
            super().run(args, stdin)
            if "{days}" in " ".join(args):
                calls["n"] += 1
                return drifted if calls["n"] == 1 else desired
            return FakeGh.run(self, args, stdin)

    gh = Healing(rules=[("--jq .login", ok("o"))])
    assert _status(gh, org_controls, RETENTION, Mode(apply=True)) == "APPLIED"
    assert any("orgs/o/actions/permissions" in c.joined for c in gh.mutations)


@pytest.mark.parametrize("control_id", [TWO_FACTOR, MEMBER_MANUAL])
def test_manual_control_reports_manual_and_never_writes(
    compliant_org: FakeGh, org_controls: list[Control], control_id: str
) -> None:
    """The API accepts these writes and keeps the old value: never claim APPLIED."""
    control = _by_id(org_controls, control_id)
    # Both controls under test carry boolean desired values, so inverting each
    # one is the drifted state whichever way the baseline points.
    live = {key: not value for key, value in control.desired.items()}
    compliant_org.override(control.projection or "", ok(canon(live)))
    report = check_org(compliant_org, org_controls, "o", Mode(apply=True))
    result = next(r for r in report.results if r.control_id == control_id)
    assert result.status == MANUAL
    assert any(detail.startswith("manual: ") for detail in result.details)
    assert compliant_org.mutations == [], "a manual control must never issue a write"


def test_two_factor_drift_names_the_web_ui_step(
    compliant_org: FakeGh, org_controls: list[Control]
) -> None:
    """The audit is the standing reminder until the owner enables it."""
    off = '{"two_factor_requirement_enabled":false}'
    compliant_org.override("{two_factor_requirement_enabled}", ok(off))
    report = check_org(compliant_org, org_controls, "o", Mode(apply=True))
    result = next(r for r in report.results if r.control_id == TWO_FACTOR)
    assert result.status == MANUAL
    assert "Authentication security" in " ".join(result.details)


def test_manual_control_is_plain_drift_in_dry_run(
    compliant_org: FakeGh, org_controls: list[Control]
) -> None:
    off = '{"two_factor_requirement_enabled":false}'
    compliant_org.override("{two_factor_requirement_enabled}", ok(off))
    assert _status(compliant_org, org_controls, TWO_FACTOR) == DRIFT


def _weakened(control: Control, **changes: object) -> str:
    return canon({**control.desired, **changes})


def test_ruleset_in_evaluate_mode_is_drift(
    compliant_org: FakeGh, org_controls: list[Control]
) -> None:
    """A ruleset flipped to evaluate enforces nothing; that is silent weakening."""
    control = _by_id(org_controls, RULESET_ID)
    compliant_org.override(f"rulesets/{ORG_IDS}1", ok(_weakened(control, enforcement="evaluate")))
    assert _status(compliant_org, org_controls, RULESET_ID) == DRIFT


def test_ruleset_with_a_bypass_actor_is_drift(
    compliant_org: FakeGh, org_controls: list[Control]
) -> None:
    """A bypass actor makes the rule optional for whoever holds it."""
    control = _by_id(org_controls, RULESET_ID)
    actors = [{"actor_id": 1, "actor_type": "OrganizationAdmin", "bypass_mode": "always"}]
    compliant_org.override(f"rulesets/{ORG_IDS}1", ok(_weakened(control, bypass_actors=actors)))
    assert _status(compliant_org, org_controls, RULESET_ID) == DRIFT


def test_missing_org_ruleset_is_drift(compliant_org: FakeGh, org_controls: list[Control]) -> None:
    compliant_org.override('select(.name=="floor-no-destruction")', ok(""))
    assert _status(compliant_org, org_controls, RULESET_ID) == DRIFT


def test_audit_orgs_rows_and_no_errors(compliant_org: FakeGh, org_controls: list[Control]) -> None:
    rows, errors = audit_orgs(compliant_org, org_controls, ["o"])
    assert set(rows["o"].values()) == {OK}
    assert errors == []


def test_audit_orgs_records_an_unreachable_org(org_controls: list[Control]) -> None:
    """An org that cannot be read renders as ERR cells, never as a missing row."""
    gh = FakeGh(rules=[("--jq .login", fail("HTTP 404"))])
    rows, errors = audit_orgs(gh, org_controls, ["nope"])
    assert set(rows["nope"].values()) == {ERR}
    assert f"0/{len(org_controls)} controls" in errors[0]
