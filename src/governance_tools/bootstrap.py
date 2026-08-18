"""Apply the governance baseline to one repository.

Dry-run by default: `--apply` is required for any mutation, and
`--force-normalize` is the only way past the stricter-than-baseline guard.
"""

import sys

from governance_tools.baseline import Control, load_controls
from governance_tools.compare import canon, stricter_extras
from governance_tools.controls import apply_control, fetch_ruleset, read_live
from governance_tools.gh import Gh, GhClient, is_valid_repo, repo_field
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
    use_unix_newlines,
)

USAGE = "usage: bootstrap.py OWNER/REPO [--apply] [--force-normalize]"


def repo_facts(client: GhClient, repo: str) -> tuple[str, bool, str]:
    """Visibility and archived flag; the third value is a read error, if any."""
    visibility = repo_field(client, repo, "visibility", ".visibility | ascii_downcase")
    if not visibility.ok:
        return "", False, visibility.first_error_line()
    archived = repo_field(client, repo, "isArchived", ".isArchived")
    if not archived.ok:
        return "", False, archived.first_error_line()
    return visibility.stdout.strip(), archived.stdout.strip() == "true", ""


def _stricter_guard(
    client: GhClient, control: Control, repo: str, ruleset_id: str
) -> ControlResult | None:
    """Refuse to lower a live ruleset that is stricter than the baseline."""
    try:
        live_ruleset = fetch_ruleset(client, repo, ruleset_id)
    except RuntimeError:
        return ControlResult(
            control.id, ERR, ("stricter-than-baseline check failed; refusing to normalize",)
        )
    extras = stricter_extras(live_ruleset, control.desired)
    if not extras:
        return None
    return ControlResult(
        control.id,
        STRICT,
        (
            "live ruleset is stricter than the baseline; skipped",
            *extras,
            "re-run with --force-normalize to overwrite it with the baseline",
        ),
    )


def _apply_and_recheck(
    client: GhClient, control: Control, repo: str, ruleset_id: str, desired: str
) -> ControlResult:
    result = apply_control(client, control, repo, ruleset_id)
    if not result.ok:
        message = " ".join(result.combined.strip().splitlines()[:2])
        return ControlResult(control.id, FAIL, (f"apply error: {message}",))
    after = read_live(client, control, repo)
    if after.error:
        return ControlResult(
            control.id, ERR, (f"applied, but the re-check read failed: {after.error}",)
        )
    if after.canonical == desired:
        return ControlResult(control.id, APPLIED)
    return ControlResult(
        control.id,
        FAIL,
        (
            "applied but live state still differs",
            f"desired: {desired}",
            f"live:    {after.canonical}",
        ),
    )


def check_control(
    client: GhClient, control: Control, repo: str, visibility: str, mode: Mode
) -> ControlResult:
    """Classify one control, applying the corrective call when asked."""
    if not control.applies_to(visibility):
        detail = f"skipped: public-only control on a {visibility} repo (needs a paid plan)"
        return ControlResult(control.id, NA, (detail,))
    live = read_live(client, control, repo)
    if live.error:
        return ControlResult(control.id, ERR, (f"read failed: {live.error}",))
    desired = canon(control.desired)
    if live.canonical == desired:
        return ControlResult(control.id, OK)
    if control.kind == "ruleset" and live.ruleset_id and not mode.force:
        guard = _stricter_guard(client, control, repo, live.ruleset_id)
        if guard is not None:
            return guard
    if not mode.apply:
        return ControlResult(
            control.id, DRIFT, (f"desired: {desired}", f"live:    {live.canonical}")
        )
    return _apply_and_recheck(client, control, repo, live.ruleset_id, desired)


def check_repo(
    client: GhClient, controls: list[Control], repo: str, mode: Mode | None = None
) -> RepoReport:
    """Check every control of one repository (the entry point audit.py uses)."""
    run = mode or Mode()
    visibility, archived, error = repo_facts(client, repo)
    if error:
        return RepoReport(repo, error=error)
    if archived:
        return RepoReport(repo, visibility=visibility, archived=True)
    results = [check_control(client, c, repo, visibility, run) for c in controls]
    return RepoReport(repo, visibility=visibility, results=results)


def _parse_args(args: list[str]) -> tuple[str, bool, bool] | None:
    if not args or args[0].startswith("--"):
        return None
    # Shape-checked before it reaches an API path template: `../../orgs/acme`
    # would otherwise resolve to an org endpoint once `..` segments normalize.
    if not is_valid_repo(args[0]):
        print(f"not a repository name (expected OWNER/REPO): {args[0]!r}", file=sys.stderr)
        return None
    apply = force = False
    for arg in args[1:]:
        if arg == "--apply":
            apply = True
        elif arg == "--force-normalize":
            force = True
        else:
            print(f"unknown argument: {arg}", file=sys.stderr)
            return None
    return args[0], apply, force


def main(argv: list[str] | None = None, client: GhClient | None = None) -> int:
    parsed = _parse_args(list(sys.argv[1:] if argv is None else argv))
    if parsed is None:
        print(USAGE, file=sys.stderr)
        return 2
    use_unix_newlines()
    repo, apply, force = parsed
    report = check_repo(client or Gh(), load_controls(), repo, Mode(apply=apply, force=force))
    if report.error:
        print(f"ERROR: {report.repo}: {report.error}", file=sys.stderr)
        return 1
    print("\n".join(render(report, apply=apply)))
    return exit_code(report)
