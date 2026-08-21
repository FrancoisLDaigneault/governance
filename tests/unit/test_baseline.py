"""Baseline loading and validation."""

import json
from pathlib import Path

import pytest

import governance_tools
from governance_tools.baseline import BASELINE_PATH, BaselineError, load_controls, split_by_scope
from governance_tools.control import Control

EXPECTED_CONTROLS = 26


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
    # Preserve IndexError for an empty baseline; next(...) would raise StopIteration.
    assert [c.id for c in controls][0] == "ruleset-main-protection"  # noqa: RUF015


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
    assert control.na_when is None
    assert control.na_reason is None
    assert control.allow_when is None
    assert control.allow_reason is None


def test_baseline_ships_inside_the_installed_package() -> None:
    """A path outside the package directory cannot be in the built wheel."""
    package_dir = Path(governance_tools.__file__).resolve().parent
    assert BASELINE_PATH.parent == package_dir, (
        f"baseline.json must live in {package_dir} to ship in the wheel, "
        f"found it in {BASELINE_PATH.parent}"
    )
    assert BASELINE_PATH.is_file()


def test_scope_defaults_to_repo(tmp_path: Path) -> None:
    control = load_controls(write_baseline(tmp_path, [valid_control()]))[0]
    assert control.scope == "repo"
    assert control.placeholder == "{repo}"
    assert control.is_manual is False


def test_unknown_scope_is_rejected(tmp_path: Path) -> None:
    path = write_baseline(tmp_path, [valid_control(scope="team")])
    with pytest.raises(BaselineError, match="unknown scope"):
        load_controls(path)


def test_org_control_must_not_carry_a_repo_endpoint(tmp_path: Path) -> None:
    """The guard that stops an organization control aiming at a repository."""
    path = write_baseline(tmp_path, [valid_control(scope="org")])
    with pytest.raises(BaselineError, match=r"apply_endpoint must carry \{org\}"):
        load_controls(path)


def test_repo_control_must_not_carry_an_org_endpoint(tmp_path: Path) -> None:
    path = write_baseline(tmp_path, [valid_control(apply_endpoint="orgs/{org}/thing")])
    with pytest.raises(BaselineError, match=r"apply_endpoint must carry \{repo\}"):
        load_controls(path)


def test_org_control_read_endpoint_is_checked_too(tmp_path: Path) -> None:
    path = write_baseline(
        tmp_path,
        [
            valid_control(
                scope="org", apply_endpoint="orgs/{org}/thing", read_endpoint="repos/{repo}/thing"
            )
        ],
    )
    with pytest.raises(BaselineError, match=r"read_endpoint must carry \{org\}"):
        load_controls(path)


def test_org_control_must_be_applicability_all(tmp_path: Path) -> None:
    """Organization controls are plan-gated, never visibility-gated."""
    path = write_baseline(
        tmp_path,
        [valid_control(scope="org", applicability="public", apply_endpoint="orgs/{org}/thing")],
    )
    with pytest.raises(BaselineError, match="applicability must be 'all'"):
        load_controls(path)


def test_manual_control_needs_no_apply_call(tmp_path: Path) -> None:
    raw = valid_control(manual_reason="web UI only")
    del raw["apply_method"]
    del raw["apply_endpoint"]
    control = load_controls(write_baseline(tmp_path, [raw]))[0]
    assert control.is_manual
    assert control.apply_method == ""


def test_manual_control_must_not_declare_an_apply_call(tmp_path: Path) -> None:
    """A manual control carrying a corrective call would be a lie."""
    path = write_baseline(tmp_path, [valid_control(manual_reason="web UI only")])
    with pytest.raises(BaselineError, match="must not declare apply_method"):
        load_controls(path)


def test_split_by_scope_partitions_the_shipped_baseline() -> None:
    repo_controls, org_controls = split_by_scope(load_controls())
    assert len(repo_controls) + len(org_controls) == EXPECTED_CONTROLS
    assert {c.scope for c in repo_controls} == {"repo"}
    assert {c.scope for c in org_controls} == {"org"}
    assert org_controls, "the baseline must govern organization state"


def test_shipped_org_controls_read_organization_endpoints() -> None:
    for control in split_by_scope(load_controls())[1]:
        assert (control.read_endpoint or "").startswith("orgs/{org}"), control.id


def test_na_probe_is_parsed(tmp_path: Path) -> None:
    raw = valid_control(na_when=".languages | length == 0", na_reason="no supported language")
    control = load_controls(write_baseline(tmp_path, [raw]))[0]
    assert control.na_when == ".languages | length == 0"
    assert control.na_reason == "no supported language"


@pytest.mark.parametrize("field", ["na_when", "na_reason"])
def test_half_declared_na_probe_is_rejected(tmp_path: Path, field: str) -> None:
    """A probe without a reason renders NA unexplained; a reason alone is dead text."""
    path = write_baseline(tmp_path, [valid_control(**{field: "x"})])
    with pytest.raises(BaselineError, match="na_when and na_reason must come together"):
        load_controls(path)


def test_na_probe_on_a_non_json_control_is_rejected(tmp_path: Path) -> None:
    """The probe re-reads read_endpoint; a 204 endpoint has no body to filter."""
    raw = valid_control(kind="status204", na_when=".x", na_reason="why")
    with pytest.raises(BaselineError, match="na_when needs kind 'json'"):
        load_controls(write_baseline(tmp_path, [raw]))


def test_allowance_probe_is_parsed(tmp_path: Path) -> None:
    raw = valid_control(allow_when='.plan.name == "team"', allow_reason="plan limit")
    control = load_controls(write_baseline(tmp_path, [raw]))[0]
    assert control.allow_when == '.plan.name == "team"'
    assert control.allow_reason == "plan limit"


@pytest.mark.parametrize("field", ["allow_when", "allow_reason"])
def test_half_declared_allowance_probe_is_rejected(tmp_path: Path, field: str) -> None:
    path = write_baseline(tmp_path, [valid_control(**{field: "x"})])
    with pytest.raises(BaselineError, match="allow_when and allow_reason must come together"):
        load_controls(path)


def test_only_codeql_probes_applicability() -> None:
    """CodeQL is the one control that analyses source; the rest configure settings.

    A setting is meaningful whether or not the repository carries code, so a
    second probe would be scope creep rather than a fix.
    """
    probing = [c.id for c in load_controls() if c.na_when]
    assert probing == ["codeql-default-setup"]


def test_override_resolves_for_its_target(tmp_path: Path) -> None:
    raw = valid_control(
        apply_payload={"enabled": True},
        overrides={
            "o/special": {"desired": {"enabled": False}, "apply_payload": {"enabled": False}}
        },
    )
    control = load_controls(write_baseline(tmp_path, [raw]))[0]
    resolved = control.for_target("o/special")
    assert resolved.desired == {"enabled": False}
    assert resolved.apply_payload == {"enabled": False}
    assert resolved.apply_endpoint == control.apply_endpoint
    assert resolved.projection == control.projection


def test_override_leaves_other_targets_alone(tmp_path: Path) -> None:
    raw = valid_control(overrides={"o/special": {"desired": {"enabled": False}}})
    control = load_controls(write_baseline(tmp_path, [raw]))[0]
    assert control.for_target("o/other") is control


def test_override_desired_only_keeps_base_payload(tmp_path: Path) -> None:
    raw = valid_control(
        apply_payload={"enabled": True},
        overrides={"o/special": {"desired": {"enabled": False}}},
    )
    resolved = load_controls(write_baseline(tmp_path, [raw]))[0].for_target("o/special")
    assert resolved.desired == {"enabled": False}
    assert resolved.apply_payload == {"enabled": True}


def test_override_on_org_control_is_rejected(tmp_path: Path) -> None:
    """An organization control has exactly one target; an override is a contradiction."""
    raw = valid_control(
        scope="org",
        apply_endpoint="orgs/{org}/thing",
        overrides={"o/r": {"desired": {"enabled": False}}},
    )
    with pytest.raises(BaselineError, match="overrides need scope 'repo'"):
        load_controls(write_baseline(tmp_path, [raw]))


def test_override_with_unknown_key_is_rejected(tmp_path: Path) -> None:
    """Only desired and apply_payload may differ: endpoints and projection stay shared."""
    raw = valid_control(overrides={"o/r": {"desired": {"enabled": False}, "projection": "{x}"}})
    with pytest.raises(BaselineError, match="unknown keys"):
        load_controls(write_baseline(tmp_path, [raw]))


def test_override_key_must_be_owner_repo(tmp_path: Path) -> None:
    raw = valid_control(overrides={"../../orgs/acme": {"desired": {"enabled": False}}})
    with pytest.raises(BaselineError, match="is not OWNER/REPO"):
        load_controls(write_baseline(tmp_path, [raw]))


def test_override_payload_without_base_payload_is_rejected(tmp_path: Path) -> None:
    raw = valid_control(overrides={"o/r": {"apply_payload": {"enabled": False}}})
    with pytest.raises(BaselineError, match="the control has none"):
        load_controls(write_baseline(tmp_path, [raw]))


def test_empty_override_is_rejected(tmp_path: Path) -> None:
    raw = valid_control(overrides={"o/r": {}})
    with pytest.raises(BaselineError, match="non-empty object"):
        load_controls(write_baseline(tmp_path, [raw]))


def test_non_object_override_is_rejected(tmp_path: Path) -> None:
    raw = valid_control(overrides={"o/r": "nope"})
    with pytest.raises(BaselineError, match="non-empty object"):
        load_controls(write_baseline(tmp_path, [raw]))


def test_shipped_main_protection_requires_the_quality_gates() -> None:
    """The eight required CI contexts and strict apply payload stay identical."""
    control = next(c for c in load_controls() if c.id == "ruleset-main-protection")
    contexts = [
        "CodeQL",
        "dependency-review",
        "pip-audit",
        "quality",
        "secrets-scan",
        "semgrep",
        "uv-audit",
        "zizmor",
    ]
    assert control.desired["checks"] == {"contexts": contexts, "strict": True}
    rule_types = control.desired["rule_types"]
    assert isinstance(rule_types, list)
    assert "required_status_checks" in rule_types
    assert control.apply_payload is not None
    rules = control.apply_payload["rules"]
    assert isinstance(rules, list)
    required = next(rule for rule in rules if rule["type"] == "required_status_checks")
    assert required["parameters"] == {
        "strict_required_status_checks_policy": True,
        "required_status_checks": [{"context": context} for context in contexts],
    }


def test_shipped_dot_github_override_requires_own_gates() -> None:
    """The .github override requires only the contexts that repository emits."""
    control = next(c for c in load_controls() if c.id == "ruleset-main-protection")
    resolved = control.for_target("fld-forge/.github")
    contexts = ["CodeQL", "validation"]
    assert resolved is not control
    assert resolved.desired["checks"] == {"contexts": contexts, "strict": True}
    assert resolved.desired["bypass_actors"] == []
    assert resolved.desired["rule_types"] == [
        "deletion",
        "non_fast_forward",
        "pull_request",
        "required_signatures",
        "required_status_checks",
    ]
    assert resolved.apply_payload is not None
    assert resolved.apply_payload["bypass_actors"] == []
    rules = resolved.apply_payload["rules"]
    assert isinstance(rules, list)
    assert [rule["type"] for rule in rules] == [
        "pull_request",
        "required_status_checks",
        "non_fast_forward",
        "deletion",
        "required_signatures",
    ]
    required = next(rule for rule in rules if rule["type"] == "required_status_checks")
    assert required["parameters"] == {
        "strict_required_status_checks_policy": True,
        "required_status_checks": [{"context": context} for context in contexts],
    }


def test_shipped_mature_discipline_pins_squash_only() -> None:
    """Rebase merges rewrite commits unsigned; the org ruleset pins squash."""
    control = next(c for c in load_controls() if c.id == "org-ruleset-mature-discipline")
    pr = control.desired["pr"]
    assert isinstance(pr, dict)
    assert pr["allowed_merge_methods"] == ["squash"]
    assert control.projection is not None
    assert "allowed_merge_methods" in control.projection


def test_shipped_manual_controls_are_the_documented_three() -> None:
    """Manual means the API cannot correct it; the set is deliberate, not incidental."""
    manual = [c.id for c in load_controls() if c.is_manual]
    assert manual == [
        "org-security-configuration",
        "org-member-privileges-manual",
        "org-outside-collaborator-invitations",
        "org-two-factor-requirement",
    ]
