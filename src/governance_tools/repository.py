"""Repository reads and per-control checks shared by bootstrap and audit."""

from governance_tools.check import check_control
from governance_tools.control import Control
from governance_tools.gh import GhClient, repo_field
from governance_tools.report import Mode, RepoReport


def repo_facts(client: GhClient, repo: str) -> tuple[str, bool, str]:
    """Visibility and archived flag; the third value is a read error, if any."""
    visibility = repo_field(client, repo, "visibility", ".visibility | ascii_downcase")
    if not visibility.ok:
        return "", False, visibility.first_error_line()
    archived = repo_field(client, repo, "isArchived", ".isArchived")
    if not archived.ok:
        return "", False, archived.first_error_line()
    return visibility.stdout.strip(), archived.stdout.strip() == "true", ""


def check_repo(
    client: GhClient, controls: list[Control], repo: str, mode: Mode | None = None
) -> RepoReport:
    """Check every control of one repository."""
    run = mode or Mode()
    visibility, archived, error = repo_facts(client, repo)
    if error:
        return RepoReport(repo, error=error)
    if archived:
        return RepoReport(repo, visibility=visibility, archived=True)
    results = [check_control(client, c.for_target(repo), repo, visibility, run) for c in controls]
    return RepoReport(repo, visibility=visibility, results=results)
