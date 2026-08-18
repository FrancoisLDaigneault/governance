"""Fleet drift audit: check repositories against the baseline and render a matrix.

A repository that cannot be fully checked is rendered as ERR cells and never
silently dropped, so the audit can never exit 0 with a repository unaudited.
"""

import sys

from governance_tools.baseline import Control, load_controls
from governance_tools.bootstrap import check_repo
from governance_tools.gh import (
    Gh,
    GhClient,
    current_login,
    is_valid_repo,
    list_orgs,
    list_repos,
)
from governance_tools.report import (
    DRIFT,
    ERR,
    NA,
    OK,
    STRICT,
    RepoReport,
    use_unix_newlines,
)

MARKS = {OK: "OK", DRIFT: "DRIFT", NA: "-", STRICT: "STRICT"}
CLEAN_CELLS = (OK, DRIFT, NA)
USAGE = "usage: audit.py [--all | OWNER/REPO ...]"


def statuses_for(report: RepoReport, controls: list[Control]) -> dict[str, str]:
    """One status per baseline control; anything missing back-fills as ERR."""
    seen = {result.control_id: result.status for result in report.results}
    return {control.id: seen.get(control.id, ERR) for control in controls}


def _lines(text: str) -> list[str]:
    """Non-empty, stripped lines of gh output."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def _owners(client: GhClient) -> list[str] | None:
    """The authenticated user, then every organization they belong to."""
    login = current_login(client)
    if not login.ok:
        print(f"error: cannot read the current user: {login.first_error_line()}", file=sys.stderr)
        return None
    orgs = list_orgs(client)
    if not orgs.ok:
        print(f"error: cannot list organizations: {orgs.first_error_line()}", file=sys.stderr)
        return None
    return [login.stdout.strip(), *_lines(orgs.stdout)]


def _fleet(client: GhClient) -> list[str] | None:
    """Non-archived repositories of the user and of every org they belong to.

    A failed listing returns None instead of a shorter fleet: an owner dropped
    here would take its repositories out of the matrix and report them clean.
    """
    owners = _owners(client)
    if owners is None:
        return None
    repos: set[str] = set()
    for owner in owners:
        listing = list_repos(client, owner)
        if not listing.ok:
            print(
                f"error: cannot list repositories for {owner}: {listing.first_error_line()}",
                file=sys.stderr,
            )
            return None
        repos.update(_lines(listing.stdout))
    return sorted(repos)


def resolve_repos(client: GhClient, args: list[str]) -> list[str] | None:
    """Explicit repositories, or the whole fleet across the user and their orgs.

    None means a usage error; the caller prints the usage line and exits 2.
    Names are shape-checked here because they are substituted into API paths.
    """
    if args and args[0] == "--all":
        if len(args) > 1:
            print("--all takes no other argument", file=sys.stderr)
            return None
        return _fleet(client)
    if not args:
        return None
    invalid = [arg for arg in args if not is_valid_repo(arg)]
    if invalid:
        joined = ", ".join(repr(arg) for arg in invalid)
        print(f"not a repository name (expected OWNER/REPO): {joined}", file=sys.stderr)
        return None
    return list(args)


def _cell(statuses: dict[str, str], control_id: str, width: int) -> str:
    """One matrix cell; a status the row never recorded renders as ERR."""
    status = statuses.get(control_id, ERR)
    return MARKS.get(status, status).ljust(width)


def render_matrix(rows: dict[str, dict[str, str]], controls: list[Control]) -> list[str]:
    codes = {control.id: f"C{i + 1}" for i, control in enumerate(controls)}
    repo_width = max(len(repo) for repo in rows)
    col_width = max(6, *(len(code) for code in codes.values()))
    legend = ", ".join(f"{codes[c.id]}={c.id}" for c in controls)
    header = (
        "repo".ljust(repo_width) + "  " + "  ".join(codes[c.id].ljust(col_width) for c in controls)
    )
    lines = [
        f"legend: {legend}",
        "cells: OK = compliant, DRIFT = differs from baseline, - = not applicable,",
        "       ERR = could not be checked, STRICT = live is stricter (skipped)",
        "",
        header,
        "-" * len(header),
    ]
    for repo in sorted(rows):
        cells = [_cell(rows[repo], control.id, col_width) for control in controls]
        lines.append(repo.ljust(repo_width) + "  " + "  ".join(cells))
    return lines


def count_cells(rows: dict[str, dict[str, str]]) -> tuple[int, int]:
    """Drift cells, and cells that could not be checked or were skipped."""
    drift = sum(1 for statuses in rows.values() for s in statuses.values() if s == DRIFT)
    bad = sum(1 for statuses in rows.values() for s in statuses.values() if s not in CLEAN_CELLS)
    return drift, bad


def audit(
    client: GhClient, controls: list[Control], repos: list[str]
) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Check every repository; returns the matrix rows and the error log."""
    rows: dict[str, dict[str, str]] = {}
    errors: list[str] = []
    for repo in repos:
        print(f"auditing {repo} ...", file=sys.stderr)
        report = check_repo(client, controls, repo)
        if report.archived:
            print(f"skipping archived {repo}", file=sys.stderr)
            continue
        rows[repo] = statuses_for(report, controls)
        checked = len(report.results)
        if report.error or checked < len(controls):
            errors.append(f"--- {repo} ({checked}/{len(controls)} controls) ---")
            errors.append(report.error or "run did not report every control")
    return rows, errors


def main(argv: list[str] | None = None, client: GhClient | None = None) -> int:
    use_unix_newlines()
    args = list(sys.argv[1:] if argv is None else argv)
    gh_client = client or Gh()
    repos = resolve_repos(gh_client, args)
    if not repos:
        print(USAGE, file=sys.stderr)
        return 2
    # Loaded once and passed on: two independent reads could disagree and raise
    # a KeyError while rendering, after the whole fleet had already been audited.
    controls = load_controls()
    rows, errors = audit(gh_client, controls, repos)
    if not rows:
        print("no results collected")
        return 2
    print("\n".join(render_matrix(rows, controls)))
    drift, bad = count_cells(rows)
    print(f"\ntotal drift cells: {drift}")
    if bad:
        print(f"total unchecked/skipped cells: {bad}")
    if errors:
        print("\n== repositories that could not be fully audited ==")
        print("\n".join(errors))
    return 1 if drift or bad else 0
