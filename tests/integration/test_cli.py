"""Both CLI entry points end to end, against a fully mocked gh layer."""

import pytest
from conftest import FakeGh, compliant_rules, fail, ok

from governance_tools import audit as audit_cli
from governance_tools import bootstrap as bootstrap_cli
from governance_tools.baseline import Control


def test_bootstrap_dry_run_on_compliant_repo(
    controls: list[Control], compliant: FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    code = bootstrap_cli.main(["o/r"], client=compliant)
    out = capsys.readouterr().out
    assert code == 0
    assert out.count(" OK") == len(controls)
    assert "== done: 0 drift(s) ==" in out
    assert compliant.mutations == []


def test_bootstrap_dry_run_reports_drift(
    controls: list[Control], capsys: pytest.CaptureFixture[str]
) -> None:
    gh = FakeGh(rules=compliant_rules(controls))
    gh.override("immutable-releases", ok('{"enabled":false}'))
    code = bootstrap_cli.main(["o/r"], client=gh)
    out = capsys.readouterr().out
    assert code == 1
    assert "CTL immutable-releases DRIFT" in out
    assert "== done: 1 drift(s) ==" in out
    assert gh.mutations == [], "dry-run must not mutate even when it finds drift"


def test_bootstrap_apply_issues_corrective_calls(controls: list[Control]) -> None:
    gh = FakeGh(rules=compliant_rules(controls))
    gh.override("immutable-releases", ok('{"enabled":false}'))
    bootstrap_cli.main(["o/r", "--apply"], client=gh)
    assert gh.mutations, "--apply must issue the corrective call"
    assert any("immutable-releases" in call.joined for call in gh.mutations)


def test_bootstrap_on_unreachable_repo_exits_1(capsys: pytest.CaptureFixture[str]) -> None:
    gh = FakeGh(rules=[("--json visibility", fail("Could not resolve to a Repository"))])
    assert bootstrap_cli.main(["o/missing"], client=gh) == 1
    assert "Could not resolve" in capsys.readouterr().err


def test_bootstrap_reports_a_read_error_per_control(
    controls: list[Control], capsys: pytest.CaptureFixture[str]
) -> None:
    gh = FakeGh(rules=compliant_rules(controls))
    gh.override("immutable-releases", fail("HTTP 403: Forbidden"))
    code = bootstrap_cli.main(["o/r"], client=gh)
    out = capsys.readouterr().out
    assert code == 1
    assert "CTL immutable-releases ERR" in out
    assert "1 error(s)" in out


def test_audit_matrix_on_compliant_fleet(
    compliant: FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    code = audit_cli.main(["o/r"], client=compliant)
    out = capsys.readouterr().out
    assert code == 0
    assert "total drift cells: 0" in out
    assert "legend: C1=ruleset-main-protection" in out


def test_audit_matrix_counts_drift_cells(
    controls: list[Control], capsys: pytest.CaptureFixture[str]
) -> None:
    gh = FakeGh(rules=compliant_rules(controls))
    gh.override("immutable-releases", ok('{"enabled":false}'))
    code = audit_cli.main(["o/r"], client=gh)
    out = capsys.readouterr().out
    assert code == 1
    assert "total drift cells: 1" in out


def test_audit_never_exits_0_with_an_unaudited_repo(
    controls: list[Control], compliant: FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    """A compliant repo plus an unreachable one must still fail the run."""

    class Mixed(FakeGh):
        def run(self, args, stdin=None):  # type: ignore[no-untyped-def]
            if "o/missing" in " ".join(args):
                return fail("Could not resolve to a Repository")
            return super().run(args, stdin)

    gh = Mixed(rules=compliant_rules(controls))
    code = audit_cli.main(["o/r", "o/missing"], client=gh)
    out = capsys.readouterr().out
    assert code == 1
    assert f"total unchecked/skipped cells: {len(controls)}" in out
    assert "repositories that could not be fully audited" in out
    assert "o/missing" in out


def test_audit_all_enumerates_the_fleet(
    controls: list[Control], capsys: pytest.CaptureFixture[str]
) -> None:
    gh = FakeGh(rules=[("api user", ok("me")), ("repo list", ok("me/one\n"))])
    gh.rules += compliant_rules(controls)
    assert audit_cli.main(["--all"], client=gh) == 0
    assert "me/one" in capsys.readouterr().out


def test_audit_survives_a_repo_returning_garbage(
    controls: list[Control], capsys: pytest.CaptureFixture[str]
) -> None:
    """One unparseable response must cost one cell, not the whole fleet run.

    The in-process rewrite gave up the shell's subprocess-per-repo isolation, so
    an exception escaping here would lose every repository already audited.
    """

    class Garbled(FakeGh):
        def run(self, args, stdin=None):  # type: ignore[no-untyped-def]
            joined = " ".join(args)
            if "o/broken" in joined and "immutable-releases" in joined:
                return ok("<!DOCTYPE html>")
            return super().run(args, stdin)

    gh = Garbled(rules=compliant_rules(controls))
    code = audit_cli.main(["o/broken", "o/sane"], client=gh)
    out = capsys.readouterr().out
    rows = {line.split()[0]: line for line in out.splitlines() if line.startswith("o/")}
    assert code == 1
    assert set(rows) == {"o/broken", "o/sane"}, "both repositories must be reported"
    assert rows["o/broken"].count("ERR") == 1, "exactly one cell is lost"
    assert "ERR" not in rows["o/sane"], "the healthy repo is unaffected"
    assert "total unchecked/skipped cells: 1" in out
