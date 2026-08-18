"""The controls that project fields of the repository object itself.

Unlike the dedicated-endpoint controls, these four read `repos/{repo}` and
correct it with a partial PATCH. They share one endpoint, so the tests pin that
each one reads through its own projection and writes only its own fields: a
control that widened its payload would silently reset a sibling's setting.
"""

import pytest
from conftest import FakeGh, ok

from governance_tools.baseline import Control, load_controls
from governance_tools.check import check_control
from governance_tools.compare import canon
from governance_tools.report import DRIFT, OK, Mode

REPO_OBJECT_CONTROLS = (
    "merge-methods-squash-only",
    "delete-branch-on-merge",
    "unused-collaboration-surfaces",
    "web-commit-signoff",
)


def control(control_id: str) -> Control:
    return next(c for c in load_controls() if c.id == control_id)


@pytest.fixture(params=REPO_OBJECT_CONTROLS)
def repo_object_control(request: pytest.FixtureRequest) -> Control:
    """Each of the four controls in turn, taken from the shipped baseline."""
    return control(str(request.param))


def test_every_repo_object_control_reads_and_writes_the_repository_object(
    repo_object_control: Control,
) -> None:
    assert repo_object_control.kind == "json"
    assert repo_object_control.read_endpoint == "repos/{repo}"
    assert repo_object_control.apply_endpoint == "repos/{repo}"
    assert repo_object_control.apply_method == "PATCH"


def test_every_repo_object_control_applies_to_private_repositories(
    repo_object_control: Control,
) -> None:
    """These are plain repository fields, not plan-gated security features."""
    assert repo_object_control.applicability == "all"
    assert repo_object_control.applies_to("private")


def test_payload_governs_exactly_the_projected_fields(repo_object_control: Control) -> None:
    """A payload wider than the projection would write fields nothing audits."""
    assert repo_object_control.apply_payload == repo_object_control.desired


def test_matching_live_state_is_ok(repo_object_control: Control) -> None:
    desired = canon(repo_object_control.desired)
    gh = FakeGh(rules=[(repo_object_control.projection or "", ok(desired))])
    result = check_control(gh, repo_object_control, "o/r", "public", Mode())
    assert result.status == OK
    assert gh.mutations == []


def test_differing_live_state_is_drift_and_never_writes(repo_object_control: Control) -> None:
    flipped = {key: not value for key, value in repo_object_control.desired.items()}
    gh = FakeGh(rules=[(repo_object_control.projection or "", ok(canon(flipped)))])
    result = check_control(gh, repo_object_control, "o/r", "public", Mode())
    assert result.status == DRIFT
    assert gh.mutations == [], "dry-run must never mutate"


def test_apply_sends_only_this_control_fields(repo_object_control: Control) -> None:
    """The corrective PATCH carries this control's fields and nothing else."""
    flipped = {key: not value for key, value in repo_object_control.desired.items()}
    gh = FakeGh(rules=[(repo_object_control.projection or "", ok(canon(flipped)))])
    gh.override("-X PATCH", ok())
    check_control(gh, repo_object_control, "o/r", "public", Mode(apply=True))
    writes = gh.mutations
    assert len(writes) == 1, "exactly one corrective call"
    assert writes[0].args[:4] == ("api", "-X", "PATCH", "repos/o/r")
    assert writes[0].stdin == canon(repo_object_control.desired)


def test_merge_methods_forbid_rebase_and_merge_commits() -> None:
    """Rebase merging does not re-sign commits, so required_signatures rejects them."""
    desired = control("merge-methods-squash-only").desired
    assert desired == {
        "allow_merge_commit": False,
        "allow_rebase_merge": False,
        "allow_squash_merge": True,
    }


def test_unused_surfaces_disable_the_wiki_but_leave_issues_alone() -> None:
    """The wiki is an ungoverned second repository; issues carry the templates."""
    desired = control("unused-collaboration-surfaces").desired
    assert desired == {"has_projects": False, "has_wiki": False}
    assert "has_issues" not in desired


def test_repo_object_controls_never_loosen_a_setting() -> None:
    """Every governed value is the restrictive one, so applying can only tighten."""
    restrictive = {
        "allow_merge_commit": False,
        "allow_rebase_merge": False,
        "allow_squash_merge": True,
        "delete_branch_on_merge": True,
        "has_projects": False,
        "has_wiki": False,
        "web_commit_signoff_required": True,
    }
    for control_id in REPO_OBJECT_CONTROLS:
        for field, value in control(control_id).desired.items():
            assert value == restrictive[field], f"{control_id}: {field} is not the safe value"


def test_secret_scanning_toggles_stay_ungoverned() -> None:
    """Governing them as disabled would make --apply switch off extra scanning."""
    governed = {c.projection or "" for c in load_controls()}
    joined = " ".join(governed)
    assert "secret_scanning_validity_checks" not in joined
    assert "secret_scanning_non_provider_patterns" not in joined
