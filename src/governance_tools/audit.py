"""Fleet drift audit: check repositories and organizations against the baseline.

A target that cannot be fully checked is rendered as ERR cells and never
silently dropped, so the audit can never exit 0 with something unaudited.
"""

import sys

from governance_tools.baseline import load_controls, split_by_scope
from governance_tools.bootstrap import check_repo
from governance_tools.control import Control
from governance_tools.gh import Gh, GhClient, is_valid_repo, list_repos
from governance_tools.matrix import count_cells, print_totals, render_matrix
from governance_tools.org import audit_orgs
from governance_tools.report import RepoReport, use_unix_newlines
from governance_tools.report import statuses_for as _statuses_for

USAGE = "usage: audit.py [--all | OWNER/REPO ...]"
FLEET_ORG = "fld-forge"


def statuses_for(report: RepoReport, controls: list[Control]) -> dict[str, str]:
    """One status per baseline control; anything missing back-fills as ERR."""
    return _statuses_for(report.results, [control.id for control in controls])


def _lines(text: str) -> list[str]:
    """Non-empty, stripped lines of gh output."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def resolve_orgs(_client: GhClient, args: list[str]) -> list[str]:
    """The governed organization under --all; none for explicit repositories."""
    return [FLEET_ORG] if args and args[0] == "--all" else []


def _fleet(client: GhClient) -> list[str] | None:
    """Non-archived repositories owned by the governed organization."""
    listing = list_repos(client, FLEET_ORG)
    if not listing.ok:
        print(
            f"error: cannot list repositories for {FLEET_ORG}: {listing.first_error_line()}",
            file=sys.stderr,
        )
        return None
    return sorted(_lines(listing.stdout))


def resolve_repos(client: GhClient, args: list[str]) -> list[str] | None:
    """Explicit repositories, or every repository in the governed organization.

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


def _org_section(
    client: GhClient, controls: list[Control], orgs: list[str]
) -> tuple[tuple[int, int], list[str]]:
    """Print the organization matrix; returns its cell counts and error log.

    Organization controls share no columns with repository controls, so they get
    their own section rather than a row whose cells would mean something else.
    """
    rows, errors = audit_orgs(client, controls, orgs)
    if not rows:
        return (0, 0), errors
    print("\n== organization controls ==\n")
    print("\n".join(render_matrix(rows, controls, label="org")))
    return count_cells(rows), errors


def main(argv: list[str] | None = None, client: GhClient | None = None) -> int:
    use_unix_newlines()
    args = list(sys.argv[1:] if argv is None else argv)
    gh_client = client or Gh()
    repos = resolve_repos(gh_client, args)
    if not repos:
        print(USAGE, file=sys.stderr)
        return 2
    orgs = resolve_orgs(gh_client, args)
    # Loaded once and passed on: two independent reads could disagree and raise
    # a KeyError while rendering, after the whole fleet had already been audited.
    repo_controls, org_controls = split_by_scope(load_controls())
    rows, errors = audit(gh_client, repo_controls, repos)
    if not rows:
        print("no results collected")
        return 2
    print("\n".join(render_matrix(rows, repo_controls)))
    drift, bad = count_cells(rows)
    if orgs and org_controls:
        (org_drift, org_bad), org_errors = _org_section(gh_client, org_controls, orgs)
        drift, bad = drift + org_drift, bad + org_bad
        errors += org_errors
    return print_totals(drift, bad, errors)
