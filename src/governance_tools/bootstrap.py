"""Apply the governance baseline to one repository or one organization.

Dry-run by default: `--apply` is required for any mutation, and
`--force-normalize` is the only way past the stricter-than-baseline guard.
"""

import sys

from governance_tools.baseline import load_controls, split_by_scope
from governance_tools.control import Control
from governance_tools.gh import Gh, GhClient
from governance_tools.identifiers import is_valid_org, is_valid_repo
from governance_tools.org import check_org
from governance_tools.report import (
    Mode,
    exit_code,
    render,
    render_org,
    results_exit_code,
    use_unix_newlines,
)
from governance_tools.repository import check_repo

USAGE = "usage: bootstrap.py (OWNER/REPO | --org ORG) [--apply] [--force-normalize]"


def _parse_flags(args: list[str]) -> tuple[bool, bool] | None:
    apply = force = False
    for arg in args:
        if arg == "--apply":
            apply = True
        elif arg == "--force-normalize":
            force = True
        else:
            print(f"unknown argument: {arg}", file=sys.stderr)
            return None
    return apply, force


def _parse_target(args: list[str]) -> tuple[str, str, list[str]] | None:
    """(scope, target, remaining arguments); None on a usage error.

    Both names are shape-checked before they reach an API path template:
    `../../orgs/acme` would otherwise resolve to a different endpoint once the
    `..` segments normalize, and the two shapes cannot be confused because an
    organization login carries no slash.
    """
    if args[0] == "--org":
        org = args[1] if len(args) > 1 else ""
        if not is_valid_org(org):
            print(f"not an organization login: {org!r}", file=sys.stderr)
            return None
        return "org", org, args[2:]
    if args[0].startswith("--"):
        return None
    if not is_valid_repo(args[0]):
        print(f"not a repository name (expected OWNER/REPO): {args[0]!r}", file=sys.stderr)
        return None
    return "repo", args[0], args[1:]


def _parse_args(args: list[str]) -> tuple[str, str, bool, bool] | None:
    """(scope, target, apply, force); None on a usage error."""
    if not args:
        return None
    parsed = _parse_target(args)
    if parsed is None:
        return None
    scope, target, rest = parsed
    flags = _parse_flags(rest)
    if flags is None:
        return None
    return scope, target, flags[0], flags[1]


def _run_org(client: GhClient, controls: list[Control], org: str, mode: Mode) -> int:
    report = check_org(client, controls, org, mode)
    if report.error:
        print(f"ERROR: {org}: {report.error}", file=sys.stderr)
        return 1
    print("\n".join(render_org(report, apply=mode.apply)))
    return results_exit_code(report.results)


def _run_repo(client: GhClient, controls: list[Control], repo: str, mode: Mode) -> int:
    report = check_repo(client, controls, repo, mode)
    if report.error:
        print(f"ERROR: {report.repo}: {report.error}", file=sys.stderr)
        return 1
    print("\n".join(render(report, apply=mode.apply)))
    return exit_code(report)


def main(argv: list[str] | None = None, client: GhClient | None = None) -> int:
    parsed = _parse_args(list(sys.argv[1:] if argv is None else argv))
    if parsed is None:
        print(USAGE, file=sys.stderr)
        return 2
    use_unix_newlines()
    scope, target, apply, force = parsed
    gh_client = client or Gh()
    repo_controls, org_controls = split_by_scope(load_controls())
    mode = Mode(apply=apply, force=force)
    if scope == "org":
        return _run_org(gh_client, org_controls, target, mode)
    return _run_repo(gh_client, repo_controls, target, mode)
