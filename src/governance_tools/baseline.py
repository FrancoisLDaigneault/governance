"""Load and validate baseline.json into typed controls.

The JSON stays the single source of truth for what is governed; this module is
the only place that turns untyped JSON into checked values, so every other
module works on a validated Control.
"""

import json
from importlib.resources import files
from pathlib import Path

from governance_tools.control import (
    APPLICABILITIES,
    KINDS,
    PLACEHOLDERS,
    SCOPES,
    Control,
    JsonDict,
    Override,
)
from governance_tools.identifiers import is_valid_repo

# baseline.json ships inside the package, so an installed wheel can find it;
# a repo-root path would only resolve for an editable install.
BASELINE_PATH = Path(str(files("governance_tools") / "baseline.json"))


class BaselineError(ValueError):
    """The baseline file is missing a field or carries an unusable value."""


def _get_str(raw: JsonDict, key: str, cid: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str):
        raise BaselineError(f"control {cid}: {key} must be a string, got {type(value).__name__}")
    return value


def _get_opt_str(raw: JsonDict, key: str, cid: str) -> str | None:
    if key not in raw:
        return None
    return _get_str(raw, key, cid)


def _get_dict(raw: JsonDict, key: str, cid: str) -> JsonDict:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise BaselineError(f"control {cid}: {key} must be an object")
    return value


def _parse_na(raw: JsonDict, cid: str, kind: str) -> tuple[str | None, str | None]:
    """Live applicability probe: a jq filter on the read endpoint, and its reason.

    The probe re-reads `read_endpoint`, which only a `json` control can answer:
    a ruleset read is a listing, and a 204 endpoint returns no body at all.
    """
    when = _get_opt_str(raw, "na_when", cid)
    reason = _get_opt_str(raw, "na_reason", cid)
    if (when is None) != (reason is None):
        raise BaselineError(f"control {cid}: na_when and na_reason must come together")
    if when is not None and kind != "json":
        raise BaselineError(f"control {cid}: na_when needs kind 'json', got {kind!r}")
    return when, reason


def _parse_scope(raw: JsonDict, cid: str) -> str:
    scope = raw.get("scope", "repo")
    if scope not in SCOPES:
        raise BaselineError(f"control {cid}: unknown scope {scope!r} (expected one of {SCOPES})")
    return str(scope)


def _parse_override(value: object, cid: str, target: str, has_payload: bool) -> Override:
    if not isinstance(value, dict) or not value:
        raise BaselineError(f"control {cid}: override {target} must be a non-empty object")
    unknown = sorted(set(value) - {"desired", "apply_payload"})
    if unknown:
        raise BaselineError(f"control {cid}: override {target} carries unknown keys {unknown}")
    if "apply_payload" in value and not has_payload:
        raise BaselineError(
            f"control {cid}: override {target} carries apply_payload, but the control has none"
        )
    desired = _get_dict(value, "desired", cid) if "desired" in value else None
    payload = _get_dict(value, "apply_payload", cid) if "apply_payload" in value else None
    return Override(desired=desired, apply_payload=payload)


def _parse_overrides(raw: JsonDict, cid: str, scope: str) -> dict[str, Override]:
    """Per-target replacements, repo scope only, keyed by a validated OWNER/REPO."""
    if "overrides" not in raw:
        return {}
    if scope != "repo":
        raise BaselineError(f"control {cid}: overrides need scope 'repo', got {scope!r}")
    section = _get_dict(raw, "overrides", cid)
    has_payload = "apply_payload" in raw
    parsed: dict[str, Override] = {}
    for target, value in section.items():
        if not is_valid_repo(target):
            raise BaselineError(f"control {cid}: override key {target!r} is not OWNER/REPO")
        parsed[target] = _parse_override(value, cid, target, has_payload)
    return parsed


def _parse_apply(raw: JsonDict, cid: str, manual_reason: str | None) -> tuple[str, str]:
    """A manual control carries no corrective call; every other one must."""
    if manual_reason is None:
        return _get_str(raw, "apply_method", cid), _get_str(raw, "apply_endpoint", cid)
    declared = [key for key in ("apply_method", "apply_endpoint", "apply_payload") if key in raw]
    if declared:
        raise BaselineError(
            f"control {cid}: manual controls must not declare {', '.join(declared)}"
        )
    return "", ""


def _check_endpoints(control: Control) -> None:
    """Endpoints must carry the placeholder of their scope, and only that one.

    This is what makes it impossible for an organization control to aim at a
    repository endpoint, or the reverse, once the target is substituted in.
    """
    wanted = control.placeholder
    other = PLACEHOLDERS["org" if control.scope == "repo" else "repo"]
    for name in ("read_endpoint", "apply_endpoint"):
        template = getattr(control, name)
        if template and (wanted not in template or other in template):
            raise BaselineError(f"control {control.id}: {name} must carry {wanted}, not {other}")


def _parse_control(raw: JsonDict) -> Control:
    cid = raw.get("id")
    if not isinstance(cid, str) or not cid:
        raise BaselineError("every control needs a non-empty string id")
    kind = _get_str(raw, "kind", cid)
    if kind not in KINDS:
        raise BaselineError(f"control {cid}: unknown kind {kind!r} (expected one of {KINDS})")
    applicability = _get_str(raw, "applicability", cid)
    if applicability not in APPLICABILITIES:
        raise BaselineError(f"control {cid}: unknown applicability {applicability!r}")
    manual_reason = _get_opt_str(raw, "manual_reason", cid)
    apply_method, apply_endpoint = _parse_apply(raw, cid, manual_reason)
    na_when, na_reason = _parse_na(raw, cid, kind)
    scope = _parse_scope(raw, cid)
    control = Control(
        id=cid,
        kind=kind,
        applicability=applicability,
        desired=_get_dict(raw, "desired", cid),
        apply_method=apply_method,
        apply_endpoint=apply_endpoint,
        scope=scope,
        read_endpoint=_get_opt_str(raw, "read_endpoint", cid),
        projection=_get_opt_str(raw, "projection", cid),
        ruleset_name=_get_opt_str(raw, "ruleset_name", cid),
        apply_payload=_get_dict(raw, "apply_payload", cid) if "apply_payload" in raw else None,
        apply_preserve=_get_opt_str(raw, "apply_preserve", cid),
        manual_reason=manual_reason,
        na_when=na_when,
        na_reason=na_reason,
        overrides=_parse_overrides(raw, cid, scope),
    )
    if control.kind == "ruleset" and not control.ruleset_name:
        raise BaselineError(f"control {cid}: ruleset controls need a ruleset_name")
    if control.scope == "org" and control.applicability != "all":
        raise BaselineError(
            f"control {cid}: organization controls are not visibility-gated, "
            "applicability must be 'all'"
        )
    _check_endpoints(control)
    return control


def load_controls(path: Path | None = None) -> list[Control]:
    """Parse and validate every control; raises BaselineError on a bad file."""
    source = path or BASELINE_PATH
    document = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise BaselineError(f"{source}: top level must be an object")
    controls = document.get("controls")
    if not isinstance(controls, list) or not controls:
        raise BaselineError(f"{source}: controls must be a non-empty list")
    parsed = [_parse_control(c) for c in controls if isinstance(c, dict)]
    if len(parsed) != len(controls):
        raise BaselineError(f"{source}: every control must be an object")
    ids = [c.id for c in parsed]
    if len(set(ids)) != len(ids):
        raise BaselineError(f"{source}: duplicate control ids")
    return parsed


def split_by_scope(controls: list[Control]) -> tuple[list[Control], list[Control]]:
    """(repository controls, organization controls), in baseline order."""
    return (
        [c for c in controls if c.scope == "repo"],
        [c for c in controls if c.scope == "org"],
    )
