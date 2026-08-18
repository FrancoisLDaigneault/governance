"""Load and validate baseline.json into typed controls.

The JSON stays the single source of truth for what is governed; this module is
the only place that turns untyped JSON into checked values, so every other
module works on a validated Control.
"""

import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

JsonDict = dict[str, object]

KINDS = ("ruleset", "json", "status204")
APPLICABILITIES = ("public", "all")

# baseline.json ships inside the package, so an installed wheel can find it;
# a repo-root path would only resolve for an editable install.
BASELINE_PATH = Path(str(files("governance_tools") / "baseline.json"))


class BaselineError(ValueError):
    """The baseline file is missing a field or carries an unusable value."""


@dataclass(frozen=True)
class Control:
    """One governed repository setting."""

    id: str
    kind: str
    applicability: str
    desired: JsonDict
    apply_method: str
    apply_endpoint: str
    read_endpoint: str | None = None
    projection: str | None = None
    ruleset_name: str | None = None
    apply_payload: JsonDict | None = None
    apply_preserve: str | None = None

    def applies_to(self, visibility: str) -> bool:
        """Public-only controls need a public repo (private ones need a paid plan)."""
        return self.applicability != "public" or visibility == "public"


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


def _get_opt_dict(raw: JsonDict, key: str, cid: str) -> JsonDict | None:
    if key not in raw:
        return None
    return _get_dict(raw, key, cid)


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
    control = Control(
        id=cid,
        kind=kind,
        applicability=applicability,
        desired=_get_dict(raw, "desired", cid),
        apply_method=_get_str(raw, "apply_method", cid),
        apply_endpoint=_get_str(raw, "apply_endpoint", cid),
        read_endpoint=_get_opt_str(raw, "read_endpoint", cid),
        projection=_get_opt_str(raw, "projection", cid),
        ruleset_name=_get_opt_str(raw, "ruleset_name", cid),
        apply_payload=_get_opt_dict(raw, "apply_payload", cid),
        apply_preserve=_get_opt_str(raw, "apply_preserve", cid),
    )
    if control.kind == "ruleset" and not control.ruleset_name:
        raise BaselineError(f"control {cid}: ruleset controls need a ruleset_name")
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
