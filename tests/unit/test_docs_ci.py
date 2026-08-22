"""CI and release workflow documentation drift gate.

The workflows define schedules, jobs, secrets and release assets that the
docs also state. Each claim is derive-checked against the workflow file it
describes, so a cron move, a job rename, a secret rename or a new release
asset fails the suite until the docs follow. Only anchored patterns are
checked, never prose wording.
"""

import re

import test_docs
import test_standards
import yaml

REPO = test_standards.REPO

WEEKDAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")

# Every non-quality CI job and the tool name the security docs use for it.
# A job added to ci.yml must be added here and documented in the same change.
JOB_TOOLS = {
    "dependency-review": "dependency review",
    "pip-audit": "pip-audit",
    "secrets-scan": "gitleaks",
    "semgrep": "semgrep",
    "uv-audit": "uv audit",
    "zizmor": "zizmor",
}


def _workflow(name: str) -> str:
    return (REPO / ".github" / "workflows" / name).read_text(encoding="utf-8")


def _cron(workflow: str) -> tuple[str, str]:
    """The workflow's single cron schedule, as (weekday name, HH:MM)."""
    crons = re.findall(r'cron: "(\d+) (\d+) \* \* (\d+)"', _workflow(workflow))
    assert len(crons) == 1, f"{workflow}: expected exactly one weekly cron, found {crons}"
    minute, hour, day = crons[0]
    return WEEKDAYS[int(day)], f"{int(hour):02d}:{int(minute):02d}"


def test_ci_schedule_documented() -> None:
    day, time = _cron("ci.yml")
    claim = re.search(r"every (\w+) at (\d+:\d+) UTC", test_docs._flat("NORTHSTAR.md"))
    assert claim, "NORTHSTAR.md: 'every DAY at HH:MM UTC' cadence claim not found"
    assert (claim.group(1), claim.group(2)) == (day, time), (
        f"NORTHSTAR.md says CI runs every {claim.group(1)} at {claim.group(2)} UTC, "
        f"ci.yml schedules {day} at {time}"
    )


def test_fleet_audit_schedule_documented() -> None:
    day, time = _cron("fleet-audit.yml")
    claim = re.search(r"(\w+)s at (\d+:\d+) UTC", test_docs._flat("docs/scheduled-audit.md"))
    assert claim, "docs/scheduled-audit.md: 'DAYs at HH:MM UTC' claim not found"
    assert (claim.group(1), claim.group(2)) == (day, time), (
        f"docs/scheduled-audit.md says {claim.group(1)}s at {claim.group(2)} UTC, "
        f"fleet-audit.yml schedules {day} at {time}"
    )


def test_quality_command_count_documented() -> None:
    total = len(test_docs._gate_commands())
    claims = {
        "README.md": r"All (\w+) run in the CI quality job",
        "AGENTS.md": r"The (\w+) quality commands",
    }
    for doc, pattern in claims.items():
        claim = re.search(pattern, test_docs._flat(doc))
        assert claim, f"{doc}: quality-command count claim matching {pattern!r} not found"
        assert test_docs._NUMBER_WORDS.get(claim.group(1).lower()) == total, (
            f"{doc} says {claim.group(1)} quality commands, the justfile defines {total}"
        )


def test_semgrep_invocation_documented() -> None:
    match = re.search(r"- run: (uvx semgrep\S+ [^\n]+)", _workflow("ci.yml"))
    assert match, "ci.yml: semgrep invocation not found"
    command = match.group(1).strip()
    assert command in test_docs._flat("NORTHSTAR.md"), (
        f"NORTHSTAR.md does not quote the CI semgrep invocation verbatim: {command}"
    )


def test_security_jobs_documented() -> None:
    """The security docs mention the tool behind every non-quality CI job."""
    jobs_block = _workflow("ci.yml").split("\njobs:\n", 1)[1]
    jobs = set(re.findall(r"^  ([\w-]+):$", jobs_block, re.MULTILINE)) - {"quality"}
    assert jobs == set(JOB_TOOLS), (
        f"ci.yml jobs {sorted(jobs)} diverge from the documented map {sorted(JOB_TOOLS)}"
    )
    for doc in ("README.md", "SECURITY.md"):
        text = test_docs._text(doc).lower()
        missing = [tool for tool in JOB_TOOLS.values() if tool not in text]
        assert not missing, f"{doc}: security tooling not mentioned: {missing}"


def test_audit_secret_documented() -> None:
    """The docs name the fleet-audit secret the workflow actually requires."""
    secrets = set(re.findall(r"secrets\.(\w+)", _workflow("fleet-audit.yml")))
    secrets -= {"GITHUB_TOKEN"}
    assert len(secrets) == 1, f"fleet-audit.yml: expected one audit secret, found {sorted(secrets)}"
    (name,) = secrets
    for doc in ("README.md", "docs/scheduled-audit.md"):
        assert name in test_docs._text(doc), f"{doc}: the audit secret {name} is not named"


def test_release_workflow_documented() -> None:
    """AGENTS' release-PR quirk stays tied to the identity the workflow pushes
    with, and SECURITY names the assets the release workflow builds.

    release-please pushes the release PR with a GitHub App installation
    token, so the PR gets CI like any other branch. A github.token fallback
    would silently restore the old behavior (GitHub anti-recursion: no checks
    on the release PR), so the gate fails if one reappears, and the doc claim
    must stay unconditional while none does.

    Dropping or renaming the step that mints the token is just as silent: the
    reference resolves to an empty string, release-please pushes with nothing,
    and no other gate here parses workflow expressions. So the minting step is
    asserted alongside the expression that consumes it.
    """
    workflow = _workflow("release-please.yml")
    # Parsed rather than text-matched: the workflow explains in prose why the
    # fallback is gone, and that mention must not read as the expression.
    steps = yaml.safe_load(workflow)["jobs"]["release-please"]["steps"]
    minted = [step for step in steps if step.get("id") == "app-token"]
    assert len(minted) == 1, (
        "release-please.yml: no single step with id 'app-token' mints the "
        "installation token, so ${{ steps.app-token.outputs.token }} resolves "
        "to an empty string and the AGENTS.md claim that release PRs run CI "
        "like any other branch becomes false"
    )
    release = [step for step in steps if step.get("id") == "release"]
    assert len(release) == 1, "release-please.yml: no single step with id 'release'"
    pushed_with = release[0]["with"]["token"]
    assert pushed_with == "${{ steps.app-token.outputs.token }}", (
        "release-please.yml: the release PR is no longer pushed with the app "
        "installation token; rewrite the AGENTS.md release-PR checks quirk "
        "for whatever identity replaced it"
    )
    assert "github.token" not in yaml.dump(steps), (
        "release-please.yml: a github.token fallback is back; pushes made with "
        "it trigger no workflow (anti-recursion), so release PRs would silently "
        "carry no checks instead of failing loudly"
    )
    # Both halves are anchored: the identity alone would still read as true
    # next to a later sentence reinstating a fallback, and a doc that
    # contradicts itself on this point is what the gate exists to catch.
    agents_flat = test_docs._flat("AGENTS.md")
    for claim in (
        "release-please PRs are pushed with a `fld-forge-release` GitHub App",
        "There is no `github.token` fallback",
    ):
        assert claim in agents_flat, (
            f"AGENTS.md: release-PR checks quirk is missing {claim!r}; it must "
            f"state both the app identity and that nothing falls back to "
            f"github.token, or the claim stops matching the workflow"
        )
    agents = test_docs._text("AGENTS.md")
    for anchor in ("merge_method=squash", "-f sha=", "verification.verified"):
        assert anchor in agents, (
            f"AGENTS.md: the guarded REST squash runbook for release PRs must "
            f"quote {anchor!r} (required_signatures blocks GraphQL merges of "
            f"unsigned release-please heads)"
        )
    assets = set(re.findall(r"(sbom\.\w+\.json|SHA256SUMS|attestation\.intoto\.jsonl)", workflow))
    assert assets, "release-please.yml: no generated release asset names found"
    security = test_docs._text("SECURITY.md")
    missing = [asset for asset in sorted(assets) if asset not in security]
    assert not missing, f"SECURITY.md: release assets not documented: {missing}"
