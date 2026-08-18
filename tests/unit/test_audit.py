"""Fleet matrix rendering, back-filling and exit codes.

The invariant under test: a repository that cannot be fully checked must never
let the audit exit 0.
"""

from conftest import FakeGh, compliant_rules, fail, ok

from governance_tools.audit import (
    audit,
    count_cells,
    main,
    render_matrix,
    resolve_repos,
    statuses_for,
)
from governance_tools.baseline import Control
from governance_tools.report import DRIFT, ERR, NA, OK, ControlResult, RepoReport


def test_statuses_for_backfills_missing_controls_as_err(controls: list[Control]) -> None:
    report = RepoReport("o/r", results=[ControlResult(controls[0].id, OK)])
    statuses = statuses_for(report, controls)
    assert statuses[controls[0].id] == OK
    assert all(statuses[c.id] == ERR for c in controls[1:])


def test_statuses_for_unreachable_repo_is_all_err(controls: list[Control]) -> None:
    report = RepoReport("o/r", error="HTTP 404")
    assert set(statuses_for(report, controls).values()) == {ERR}


def test_count_cells_separates_drift_from_unchecked() -> None:
    rows = {
        "a": {"c1": OK, "c2": DRIFT, "c3": NA},
        "b": {"c1": ERR, "c2": "STRICTER-THAN-BASELINE"},
    }
    assert count_cells(rows) == (1, 2)


def test_render_matrix_lists_every_control_and_repo(controls: list[Control]) -> None:
    rows = {"o/r": {c.id: OK for c in controls}}
    lines = render_matrix(rows, controls)
    assert lines[0].startswith("legend: C1=")
    assert any(line.startswith("o/r") and "OK" in line for line in lines)


def test_render_matrix_marks_na_with_a_dash(controls: list[Control]) -> None:
    rows = {"o/r": {c.id: NA for c in controls}}
    assert any("-" in line for line in render_matrix(rows, controls)[5:])


def test_resolve_repos_returns_explicit_names() -> None:
    assert resolve_repos(FakeGh(), ["a/b", "c/d"]) == ["a/b", "c/d"]


def test_resolve_repos_none_without_arguments() -> None:
    assert resolve_repos(FakeGh(), []) is None


def test_resolve_repos_all_enumerates_and_sorts() -> None:
    gh = FakeGh(rules=[("api user", ok("me")), ("repo list", ok("me/z\nme/a\n"))])
    assert resolve_repos(gh, ["--all"]) == ["me/a", "me/z"]


def test_resolve_repos_all_handles_login_failure() -> None:
    gh = FakeGh(rules=[("api user", fail("not logged in"))])
    assert resolve_repos(gh, ["--all"]) is None


def test_resolve_repos_all_handles_listing_failure() -> None:
    gh = FakeGh(rules=[("api user", ok("me")), ("repo list", fail("HTTP 500"))])
    assert resolve_repos(gh, ["--all"]) is None


def test_audit_skips_archived_repos(controls: list[Control]) -> None:
    gh = FakeGh(rules=[("--json visibility", ok("public")), ("--json isArchived", ok("true"))])
    rows, errors = audit(gh, controls, ["o/archived"])
    assert rows == {}
    assert errors == []


def test_audit_records_an_unreachable_repo(controls: list[Control]) -> None:
    gh = FakeGh(rules=[("--json visibility", fail("Could not resolve to a Repository"))])
    rows, errors = audit(gh, controls, ["o/missing"])
    assert set(rows["o/missing"].values()) == {ERR}
    assert "0/10 controls" in errors[0]


def test_audit_of_compliant_repo_has_no_errors(compliant: FakeGh, controls: list[Control]) -> None:
    rows, errors = audit(compliant, controls, ["o/r"])
    assert set(rows["o/r"].values()) == {OK}
    assert errors == []


def test_main_without_arguments_is_usage_error() -> None:
    assert main([], client=FakeGh()) == 2


def test_main_returns_2_when_every_repo_is_archived(controls: list[Control]) -> None:
    gh = FakeGh(rules=[("--json visibility", ok("public")), ("--json isArchived", ok("true"))])
    assert main(["o/archived"], client=gh) == 2


def test_main_on_compliant_fleet_exits_0(compliant: FakeGh) -> None:
    assert main(["o/r"], client=compliant) == 0
    assert compliant.mutations == [], "the audit must never mutate anything"


def test_main_on_drifted_repo_exits_1(controls: list[Control]) -> None:
    gh = FakeGh(rules=compliant_rules(controls))
    gh.override("vulnerability-alerts", fail("gh: HTTP 404 Not Found"))
    assert main(["o/r"], client=gh) == 1


def test_main_on_unreachable_repo_exits_1() -> None:
    """The regression that mattered: a repo that cannot be audited must fail the run."""
    gh = FakeGh(rules=[("--json visibility", fail("HTTP 404"))])
    assert main(["o/r"], client=gh) == 1
