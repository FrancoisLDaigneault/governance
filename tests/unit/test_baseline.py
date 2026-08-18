"""Baseline loading and validation."""

import json
from pathlib import Path

import pytest

from governance_tools.baseline import BASELINE_PATH, BaselineError, Control, load_controls

EXPECTED_CONTROLS = 10


def write_baseline(tmp_path: Path, controls: object) -> Path:
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps({"controls": controls}), encoding="utf-8")
    return path


def valid_control(**overrides: object) -> dict[str, object]:
    control: dict[str, object] = {
        "id": "sample",
        "kind": "json",
        "applicability": "all",
        "desired": {"enabled": True},
        "apply_method": "PUT",
        "apply_endpoint": "repos/{repo}/thing",
    }
    control.update(overrides)
    return control


def test_shipped_baseline_loads() -> None:
    controls = load_controls()
    assert len(controls) == EXPECTED_CONTROLS
    assert BASELINE_PATH.is_file()
    assert [c.id for c in controls][0] == "ruleset-main-protection"


def test_shipped_baseline_governs_read_only_workflow_permissions() -> None:
    """can_approve_pull_request_reviews must never be forced: it would loosen repos."""
    control = next(c for c in load_controls() if c.id == "actions-workflow-permissions")
    assert control.desired == {"default_workflow_permissions": "read"}
    assert control.apply_preserve == "{can_approve_pull_request_reviews}"


def test_public_control_is_not_applicable_to_private_repo() -> None:
    control = Control(
        id="x",
        kind="json",
        applicability="public",
        desired={},
        apply_method="PUT",
        apply_endpoint="e",
    )
    assert control.applies_to("public")
    assert not control.applies_to("private")


def test_control_for_all_applies_everywhere() -> None:
    control = Control(
        id="x", kind="json", applicability="all", desired={}, apply_method="PUT", apply_endpoint="e"
    )
    assert control.applies_to("private")


def test_missing_id_is_rejected(tmp_path: Path) -> None:
    path = write_baseline(tmp_path, [{"kind": "json"}])
    with pytest.raises(BaselineError, match="non-empty string id"):
        load_controls(path)


def test_unknown_kind_is_rejected(tmp_path: Path) -> None:
    path = write_baseline(tmp_path, [valid_control(kind="telepathy")])
    with pytest.raises(BaselineError, match="unknown kind"):
        load_controls(path)


def test_unknown_applicability_is_rejected(tmp_path: Path) -> None:
    path = write_baseline(tmp_path, [valid_control(applicability="sometimes")])
    with pytest.raises(BaselineError, match="unknown applicability"):
        load_controls(path)


def test_ruleset_without_name_is_rejected(tmp_path: Path) -> None:
    path = write_baseline(tmp_path, [valid_control(kind="ruleset")])
    with pytest.raises(BaselineError, match="ruleset_name"):
        load_controls(path)


def test_non_string_field_is_rejected(tmp_path: Path) -> None:
    path = write_baseline(tmp_path, [valid_control(apply_method=7)])
    with pytest.raises(BaselineError, match="apply_method must be a string"):
        load_controls(path)


def test_non_object_desired_is_rejected(tmp_path: Path) -> None:
    path = write_baseline(tmp_path, [valid_control(desired="yes")])
    with pytest.raises(BaselineError, match="desired must be an object"):
        load_controls(path)


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    path = write_baseline(tmp_path, [valid_control(), valid_control()])
    with pytest.raises(BaselineError, match="duplicate control ids"):
        load_controls(path)


def test_empty_control_list_is_rejected(tmp_path: Path) -> None:
    path = write_baseline(tmp_path, [])
    with pytest.raises(BaselineError, match="non-empty list"):
        load_controls(path)


def test_non_object_control_is_rejected(tmp_path: Path) -> None:
    path = write_baseline(tmp_path, ["nope"])
    with pytest.raises(BaselineError, match="every control must be an object"):
        load_controls(path)


def test_non_object_document_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    path.write_text('["not", "an", "object"]', encoding="utf-8")
    with pytest.raises(BaselineError, match="top level must be an object"):
        load_controls(path)


def test_optional_fields_default_to_none(tmp_path: Path) -> None:
    path = write_baseline(tmp_path, [valid_control()])
    control = load_controls(path)[0]
    assert control.read_endpoint is None
    assert control.apply_payload is None
    assert control.apply_preserve is None
