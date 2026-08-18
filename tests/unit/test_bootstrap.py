"""Classification, exit codes and the dry-run-by-default invariant."""

from collections.abc import Sequence

from conftest import FakeGh, compliant_rules, fail, ok

from governance_tools.baseline import Control, load_controls
from governance_tools.bootstrap import check_control, check_repo, main, repo_facts
from governance_tools.gh import GhResult
from governance_tools.report import (
    APPLIED,
    DRIFT,
    ERR,
    FAIL,
    NA,
    OK,
    STRICT,
    ControlResult,
    Mode,
    RepoReport,
    exit_code,
    render,
    summary_line,
)

PUBLIC_ONLY = Control(
    id="pub",
    kind="json",
    applicability="public",
    desired={"enabled": True},
    apply_method="PUT",
    apply_endpoint="repos/{repo}/x",
    read_endpoint="repos/{repo}/x",
    projection="{enabled}",
)

RULESET = Control(
    id="rs",
    kind="ruleset",
    applicability="all",
    desired={
        "rule_types": ["deletion"],
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
    },
    apply_method="POST",
    apply_endpoint="repos/{repo}/rulesets",
    read_endpoint="repos/{repo}/rulesets",
    projection="{rule_types}",
    ruleset_name="main-protection",
    apply_payload={"name": "main-protection"},
)


def test_public_only_control_is_na_on_private() -> None:
    result = check_control(FakeGh(), PUBLIC_ONLY, "o/r", "private", Mode())
    assert result.status == NA
    assert "public-only control on a private repo" in result.details[0]


def test_matching_state_is_ok() -> None:
    gh = FakeGh(rules=[("repos/o/r/x", ok('{"enabled":true}'))])
    assert check_control(gh, PUBLIC_ONLY, "o/r", "public", Mode()).status == OK


def test_differing_state_is_drift_in_dry_run() -> None:
    gh = FakeGh(rules=[("repos/o/r/x", ok('{"enabled":false}'))])
    result = check_control(gh, PUBLIC_ONLY, "o/r", "public", Mode())
    assert result.status == DRIFT
    assert result.details[0].startswith("desired: ")
    assert gh.mutations == [], "dry-run must never mutate"


def test_read_failure_is_err_and_never_writes() -> None:
    gh = FakeGh(rules=[("repos/o/r/x", fail("HTTP 403"))])
    result = check_control(gh, PUBLIC_ONLY, "o/r", "public", Mode(apply=True))
    assert result.status == ERR
    assert gh.mutations == [], "a read error must never fall through to a write"


def test_stricter_live_ruleset_is_skipped_even_with_apply() -> None:
    live = (
        '{"rules":[{"type":"deletion"},{"type":"required_linear_history"}],'
        '"conditions":{"ref_name":{"include":["~DEFAULT_BRANCH"],"exclude":[]}}}'
    )
    gh = FakeGh(
        rules=[
            ("includes_parents", ok("5")),
            ("rulesets/5 --jq", ok('{"rule_types":["deletion","required_linear_history"]}')),
            ("rulesets/5", ok(live)),
        ]
    )
    result = check_control(gh, RULESET, "o/r", "public", Mode(apply=True))
    assert result.status == STRICT
    assert "- extra rule type: required_linear_history" in result.details
    assert gh.mutations == [], "a stricter ruleset must never be normalized without --force"


def test_force_normalize_bypasses_the_guard() -> None:
    live = '{"rules":[{"type":"deletion"},{"type":"required_linear_history"}]}'
    gh = FakeGh(
        rules=[
            ("includes_parents", ok("5")),
            ("rulesets/5 --jq", ok('{"rule_types":["deletion","required_linear_history"]}')),
            ("rulesets/5", ok(live)),
        ]
    )
    result = check_control(gh, RULESET, "o/r", "public", Mode(apply=True, force=True))
    assert result.status != STRICT
    assert gh.mutations, "--force-normalize must allow the corrective write"


def test_failed_stricter_check_is_err_and_refuses_to_normalize() -> None:
    gh = FakeGh(
        rules=[
            ("includes_parents", ok("5")),
            ("rulesets/5 --jq", ok('{"rule_types":["other"]}')),
            ("rulesets/5", fail("HTTP 502")),
        ]
    )
    result = check_control(gh, RULESET, "o/r", "public", Mode(apply=True))
    assert result.status == ERR
    assert "refusing to normalize" in result.details[0]
    assert gh.mutations == []


class Healing(FakeGh):
    """Reads as drifted until a write happens, then reads as compliant."""

    written: bool = False

    def run(self, args: Sequence[str], stdin: str | None = None) -> GhResult:
        super().run(args, stdin)
        if "-X" in args:
            self.written = True
            return ok()
        return ok('{"enabled":true}' if self.written else '{"enabled":false}')


def test_apply_then_matching_recheck_is_applied() -> None:
    healing = Healing()
    result = check_control(healing, PUBLIC_ONLY, "o/r", "public", Mode(apply=True))
    assert result.status == APPLIED
    assert healing.mutations, "the corrective call must have been issued"


def test_apply_that_does_not_take_effect_is_fail() -> None:
    gh = FakeGh(rules=[("repos/o/r/x", ok('{"enabled":false}'))])
    result = check_control(gh, PUBLIC_ONLY, "o/r", "public", Mode(apply=True))
    assert result.status == FAIL
    assert "applied but live state still differs" in result.details[0]


def test_apply_error_is_fail() -> None:
    gh = FakeGh(rules=[("-X", fail("HTTP 422 Unprocessable")), ("repos/o/r/x", ok("{}"))])
    result = check_control(gh, PUBLIC_ONLY, "o/r", "public", Mode(apply=True))
    assert result.status == FAIL
    assert "apply error" in result.details[0]


class Flaky(FakeGh):
    """First read succeeds (drift), the post-apply re-check fails."""

    reads: int = 0

    def run(self, args: Sequence[str], stdin: str | None = None) -> GhResult:
        super().run(args, stdin)
        if "-X" in args:
            return ok()
        self.reads += 1
        return ok('{"enabled":false}') if self.reads == 1 else fail("HTTP 500")


def test_failed_recheck_after_apply_is_err() -> None:
    result = check_control(Flaky(), PUBLIC_ONLY, "o/r", "public", Mode(apply=True))
    assert result.status == ERR
    assert "re-check read failed" in result.details[0]


def test_repo_facts_reports_visibility_and_archived() -> None:
    gh = FakeGh(rules=[("--json visibility", ok("public")), ("--json isArchived", ok("true"))])
    assert repo_facts(gh, "o/r") == ("public", True, "")


def test_repo_facts_surfaces_a_read_error() -> None:
    gh = FakeGh(rules=[("--json visibility", fail("Could not resolve to a Repository"))])
    _, _, error = repo_facts(gh, "o/r")
    assert "Could not resolve" in error


def test_archived_repo_is_skipped_cleanly() -> None:
    gh = FakeGh(rules=[("--json visibility", ok("public")), ("--json isArchived", ok("true"))])
    report = check_repo(gh, load_controls(), "o/r")
    assert report.archived
    assert report.results == []
    assert exit_code(report) == 0
    assert "archived" in render(report, apply=False)[0]


def test_unreachable_repo_reports_an_error() -> None:
    gh = FakeGh(rules=[("--json visibility", fail("HTTP 404"))])
    report = check_repo(gh, load_controls(), "o/r")
    assert report.error
    assert report.results == []


def test_compliant_repo_is_all_ok(compliant: FakeGh, controls: list[Control]) -> None:
    report = check_repo(compliant, controls, "o/r")
    assert [r.status for r in report.results] == [OK] * len(controls)
    assert exit_code(report) == 0
    assert compliant.mutations == []


def test_private_repo_marks_public_controls_na(controls: list[Control]) -> None:
    gh = FakeGh(rules=compliant_rules(controls, visibility="private"))
    report = check_repo(gh, controls, "o/r")
    assert NA in [r.status for r in report.results]


def test_exit_code_flags_any_unclean_status() -> None:
    for status in (DRIFT, ERR, STRICT, FAIL):
        report = RepoReport("o/r", results=[ControlResult("a", status)])
        assert exit_code(report) == 1, status
    for status in (OK, NA, APPLIED):
        report = RepoReport("o/r", results=[ControlResult("a", status)])
        assert exit_code(report) == 0, status


def test_summary_line_counts_each_category() -> None:
    report = RepoReport(
        "o/r",
        results=[
            ControlResult("a", DRIFT),
            ControlResult("b", ERR),
            ControlResult("c", STRICT),
        ],
    )
    assert summary_line(report, apply=False) == (
        "== done: 1 drift(s), 1 error(s), 1 stricter-than-baseline skip(s) =="
    )
    assert summary_line(report, apply=True).startswith("== done: 0 failure(s)")


def test_render_emits_machine_readable_ctl_lines() -> None:
    report = RepoReport("o/r", visibility="public", results=[ControlResult("a", DRIFT, ("d",))])
    lines = render(report, apply=False)
    assert lines[0].startswith("== governance bootstrap: o/r (visibility: public, mode: dry-run)")
    assert lines[1] == "CTL a DRIFT"
    assert lines[2] == "     d"


def test_main_rejects_missing_repo() -> None:
    assert main([], client=FakeGh()) == 2


def test_main_rejects_flag_in_first_position() -> None:
    assert main(["--apply"], client=FakeGh()) == 2


def test_main_rejects_unknown_argument() -> None:
    assert main(["o/r", "--aplly"], client=FakeGh()) == 2


def test_main_returns_1_when_the_repo_cannot_be_read() -> None:
    gh = FakeGh(rules=[("--json visibility", fail("HTTP 404"))])
    assert main(["o/r"], client=gh) == 1


def test_main_dry_run_on_compliant_repo_exits_0(compliant: FakeGh) -> None:
    assert main(["o/r"], client=compliant) == 0
    assert compliant.mutations == []


def test_weaker_live_ruleset_falls_through_to_drift() -> None:
    """The guard must only skip stricter rulesets; a weaker one is ordinary drift."""
    live = '{"rules":[],"conditions":{"ref_name":{"include":["~DEFAULT_BRANCH"],"exclude":[]}}}'
    gh = FakeGh(
        rules=[
            ("includes_parents", ok("5")),
            ("rulesets/5 --jq", ok('{"rule_types":[]}')),
            ("rulesets/5", ok(live)),
        ]
    )
    result = check_control(gh, RULESET, "o/r", "public", Mode())
    assert result.status == DRIFT
    assert gh.mutations == []


def test_archived_read_failure_is_reported() -> None:
    gh = FakeGh(
        rules=[("--json visibility", ok("public")), ("--json isArchived", fail("HTTP 500"))]
    )
    _, _, error = repo_facts(gh, "o/r")
    assert error == "HTTP 500"


def test_main_accepts_force_normalize(compliant: FakeGh) -> None:
    assert main(["o/r", "--apply", "--force-normalize"], client=compliant) == 0


def test_main_rejects_a_path_traversal_repo_name() -> None:
    """The name is substituted into API paths: `..` must never reach a template."""
    gh = FakeGh()
    assert main(["../../orgs/acme", "--apply"], client=gh) == 2
    assert gh.calls == [], "an invalid name must be rejected before any gh call"


def test_main_rejects_a_name_without_a_slash() -> None:
    assert main(["notarepo"], client=FakeGh()) == 2


def test_main_rejects_an_empty_repo_name() -> None:
    assert main([""], client=FakeGh()) == 2
