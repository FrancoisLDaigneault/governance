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

# Fragments of the release-assets commands that populate or prune dist/. Each
# has to run before the attestation freezes its subjects; see
# test_release_asset_step_order. The tuple is maintained by hand: recognizing
# "any step that writes to dist/" would mean parsing shell, so a producer added
# to the workflow and not added here is not covered. Adding one is part of
# adding the step.
DIST_PRODUCERS = (
    "uv build",
    "rm -f dist/.gitignore",
    "sbom.cdx.json",
    "sbom.spdx.json",
    "SHA256SUMS",
)


def _workflow(name: str) -> str:
    return (REPO / ".github" / "workflows" / name).read_text(encoding="utf-8")


def _cron(workflow: str) -> tuple[str, str]:
    """The workflow's single cron schedule, as (weekday name, HH:MM)."""
    crons = re.findall(r'cron: "(\d+) (\d+) \* \* (\d+)"', _workflow(workflow))
    assert len(crons) == 1, f"{workflow}: expected exactly one weekly cron, found {crons}"
    minute, hour, day = crons[0]
    return WEEKDAYS[int(day)], f"{int(hour):02d}:{int(minute):02d}"


def _asset_step_mappings() -> list[dict[str, object]]:
    """The release-assets steps as parsed, before they are flattened."""
    job = yaml.safe_load(_workflow("release-please.yml"))["jobs"]["release-assets"]
    steps: list[dict[str, object]] = job["steps"]
    return steps


def _asset_steps() -> list[str]:
    """The release-assets steps, each flattened to its action and command.

    `name:` is deliberately left out and comments never survive the parse, so
    a step is located by what it runs rather than by how it is described.
    `with:` is left out too, which is why the attestation's `subject-path` is
    asserted against the mappings instead.
    """
    return [f"{step.get('uses', '')} {step.get('run', '')}" for step in _asset_step_mappings()]


def _only_step(bodies: list[str], fragment: str, role: str) -> int:
    """Index of the one release-assets step whose command carries `fragment`.

    Uniqueness is asserted, not assumed: taking the first of several matches
    would compare an arbitrary index, and the order assertion below would then
    pass or fail for a reason unrelated to the order it claims to check.
    """
    hits = [index for index, body in enumerate(bodies) if fragment in body]
    assert len(hits) == 1, (
        f"release-please.yml: expected exactly one release-assets step whose "
        f"command carries {fragment!r} ({role}), found {len(hits)} at {hits}; "
        f"the step-order gate cannot tell which one it must compare"
    )
    return hits[0]


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


def test_release_asset_step_order() -> None:
    """dist/ is complete before the attestation freezes what it signs.

    The attestation resolves `subject-path: dist/*` once, when it runs. Every
    step that populates or prunes dist/ therefore has to precede it: a file
    added afterwards ships unattested, and one left behind that should have
    gone is signed as a stray subject. That is the v0.7.0 incident, where the
    dist/.gitignore uv build creates became a subject of the release. The
    bundle copy is the mirror case and has to follow the attestation, or it
    would end up attesting itself.

    SHA256SUMS carries a second, stricter constraint: it has to be written
    after every other producer, not merely before the attestation. Written
    earlier it checksums whatever dist/ held at that moment, and the files
    written after it are attested but absent from it -- `sha256sum --check`
    then reports success over a subset, which reads exactly like a full pass.

    Both constraints are read against DIST_PRODUCERS, a hand-maintained tuple:
    a producer added to the workflow but not to it escapes this gate.

    Reordering these steps is silent: the workflow states the constraint in a
    comment, the assets look plausible either way, and the damage only shows
    up in a published release that can no longer be changed.
    """
    bodies = _asset_steps()
    attest = _only_step(bodies, "attest-build-provenance", "attests dist/")
    for fragment in DIST_PRODUCERS:
        producer = _only_step(bodies, fragment, "populates or prunes dist/")
        assert producer < attest, (
            f"release-please.yml: the release-assets step running {fragment!r} "
            f"is at index {producer}, after the attestation at index {attest}; "
            f"it must run before, or what it writes to dist/ ships unattested "
            f"and what it deletes is attested as a stray subject"
        )
    inputs = _asset_step_mappings()[attest].get("with")
    assert isinstance(inputs, dict), (
        f"release-please.yml: the attestation step at index {attest} declares "
        f"no `with:` mapping, so it attests nothing this gate can read"
    )
    subject = inputs.get("subject-path")
    assert subject == "dist/*", (
        f"release-please.yml: the attestation attests {subject!r}, not "
        f"'dist/*'; the step-order gate above only proves that dist/ is "
        f"complete when the attestation runs, which is worth nothing if the "
        f"attestation no longer covers all of dist/"
    )
    checksums = _only_step(bodies, "SHA256SUMS", "checksums dist/")
    late = sorted(
        fragment
        for fragment in DIST_PRODUCERS
        if fragment != "SHA256SUMS"
        and _only_step(bodies, fragment, "populates or prunes dist/") > checksums
    )
    assert not late, (
        f"release-please.yml: the release-assets step writing SHA256SUMS is at "
        f"index {checksums}, before {late}; SHA256SUMS must be written after "
        f"every other producer or it checksums an incomplete dist/, and the "
        f"assets written after it ship attested but unchecksummed while "
        f"`sha256sum --check` still reports success over the subset it covers"
    )
    copy = _only_step(bodies, "attestation.intoto.jsonl", "ships the bundle")
    upload = _only_step(bodies, "gh release upload", "uploads the assets")
    publish = _only_step(bodies, "--draft=false", "publishes the release")
    assert attest < copy < upload < publish, (
        f"release-please.yml: release-assets must attest (index {attest}), then "
        f"copy the bundle ({copy}), then upload ({upload}), then publish "
        f"({publish}). Copying before the attestation makes the bundle attest "
        f"itself; publishing before the upload locks an immutable release with "
        f"assets missing"
    )
