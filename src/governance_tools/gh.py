"""The only module that talks to the network, through the `gh` CLI.

Everything else takes a GhClient and stays pure, so the whole tool is testable
without touching GitHub.
"""

import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

# A repository name is substituted into `repos/{repo}/...` path templates, and
# HTTP clients normalize `..` segments: an unvalidated name such as
# `../../orgs/acme` would aim a corrective write at a different endpoint.
_REPO_RE = re.compile(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+")
# An organization login carries no slash and no dot, so it can never be mistaken
# for OWNER/REPO and can never climb out of an `orgs/{org}/...` template.
_ORG_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?")


def is_valid_repo(repo: str) -> bool:
    """True for a plain OWNER/REPO identifier, with no path traversal."""
    return _REPO_RE.fullmatch(repo) is not None


def is_valid_org(org: str) -> bool:
    """True for a bare organization login, with no slash and no path traversal."""
    return _ORG_RE.fullmatch(org) is not None


@dataclass(frozen=True)
class GhResult:
    """Outcome of one `gh` invocation."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    @property
    def combined(self) -> str:
        """stdout and stderr together, as the shell captured them with 2>&1."""
        return self.stdout + self.stderr

    def first_error_line(self) -> str:
        """The first line of output, used as the reported read error."""
        return self.combined.strip().splitlines()[0] if self.combined.strip() else "gh failed"


class GhClient(Protocol):
    """Minimal surface a gh backend must provide (one method, easy to fake)."""

    def run(self, args: Sequence[str], stdin: str | None = None) -> GhResult: ...


class Gh:
    """Real backend: runs the `gh` executable."""

    def run(self, args: Sequence[str], stdin: str | None = None) -> GhResult:
        completed = subprocess.run(
            ["gh", *args],
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
        )
        return GhResult(completed.returncode, completed.stdout, completed.stderr)


def api_get(client: GhClient, endpoint: str, jq: str | None = None) -> GhResult:
    """GET an API endpoint, optionally projected through a jq filter."""
    args = ["api", endpoint]
    if jq is not None:
        args += ["--jq", jq]
    return client.run(args)


def api_write(client: GhClient, method: str, endpoint: str, body: str | None = None) -> GhResult:
    """Call a mutating endpoint; an empty body is sent when body is None."""
    args = ["api", "-X", method, endpoint]
    if body is None:
        return client.run(args)
    return client.run([*args, "--input", "-"], stdin=body)


def repo_field(client: GhClient, repo: str, field: str, jq: str) -> GhResult:
    """Read one field of a repository through `gh repo view`."""
    return client.run(["repo", "view", repo, "--json", field, "--jq", jq])


def list_repos(client: GhClient, owner: str) -> GhResult:
    """Every non-archived repository owned by `owner`, one per line, sorted."""
    return client.run(
        [
            "repo",
            "list",
            owner,
            "--limit",
            "200",
            "--json",
            "nameWithOwner,isArchived",
            "--jq",
            ".[] | select(.isArchived | not) | .nameWithOwner",
        ]
    )


def current_login(client: GhClient) -> GhResult:
    """The authenticated user's login."""
    return api_get(client, "user", ".login")


def list_orgs(client: GhClient) -> GhResult:
    """Logins of every organization the authenticated user belongs to."""
    return api_get(client, "user/orgs", ".[].login")
