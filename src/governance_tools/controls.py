"""Per-control IO: read the live projected state, and run the corrective call.

Every function here takes a GhClient, so the network is injectable. A read that
fails sets `error`: a read error is an error, never drift, and never falls
through to a corrective write.
"""

import json
from dataclasses import dataclass

from governance_tools.baseline import Control
from governance_tools.compare import canon, canon_text
from governance_tools.gh import GhClient, GhResult, api_get, api_write

ABSENT = '"absent"'


@dataclass(frozen=True)
class LiveState:
    """Projected live state of one control."""

    canonical: str = ""
    ruleset_id: str = ""
    error: str = ""


def endpoint_for(template: str, repo: str) -> str:
    return template.replace("{repo}", repo)


def _read_ruleset(client: GhClient, control: Control, repo: str) -> LiveState:
    # includes_parents=false: after an org migration a parent ruleset could
    # otherwise match by name and the repo-level follow-up call would 404.
    listing = api_get(
        client,
        f"{endpoint_for(control.read_endpoint or '', repo)}?includes_parents=false",
        f'[.[] | select(.name=="{control.ruleset_name}")][0].id // empty',
    )
    if not listing.ok:
        return LiveState(error=listing.first_error_line())
    ruleset_id = listing.stdout.strip()
    if not ruleset_id:
        return LiveState(canonical=ABSENT)
    projected = api_get(client, f"repos/{repo}/rulesets/{ruleset_id}", control.projection)
    if not projected.ok:
        return LiveState(ruleset_id=ruleset_id, error=projected.first_error_line())
    return LiveState(canonical=canon_text(projected.stdout), ruleset_id=ruleset_id)


def _read_status204(client: GhClient, control: Control, repo: str) -> LiveState:
    # 204 = enabled, 404 = disabled; anything else (401/403/5xx) is a read
    # error and must not be mistaken for "disabled".
    result = api_get(client, endpoint_for(control.read_endpoint or "", repo))
    if result.ok:
        return LiveState(canonical=canon({"enabled": True}))
    if "HTTP 404" in result.combined:
        return LiveState(canonical=canon({"enabled": False}))
    return LiveState(error=result.first_error_line())


def _read_json(client: GhClient, control: Control, repo: str) -> LiveState:
    result = api_get(client, endpoint_for(control.read_endpoint or "", repo), control.projection)
    if not result.ok:
        return LiveState(error=result.first_error_line())
    return LiveState(canonical=canon_text(result.stdout))


def read_live(client: GhClient, control: Control, repo: str) -> LiveState:
    """Read one control's live projected state."""
    if control.kind == "ruleset":
        return _read_ruleset(client, control, repo)
    if control.kind == "status204":
        return _read_status204(client, control, repo)
    return _read_json(client, control, repo)


def fetch_ruleset(client: GhClient, repo: str, ruleset_id: str) -> dict[str, object]:
    """Full live ruleset object, for the stricter-than-baseline guard.

    Raises RuntimeError when the read itself fails: a failed check must never
    read as "not stricter". Unparseable but successful output yields {}, which
    the guard treats as no extras, matching the reference implementation.
    """
    result = api_get(client, f"repos/{repo}/rulesets/{ruleset_id}")
    if not result.ok:
        raise RuntimeError(result.first_error_line())
    try:
        parsed = json.loads(result.stdout)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _preserved_body(client: GhClient, control: Control, repo: str, payload: str) -> str | None:
    """Merge ungoverned-but-required fields, read live, into the request body.

    Returns None when the preserve read fails, is empty or is null: the write is
    then refused rather than sending a partial body to a privileged endpoint.
    """
    result = api_get(
        client, endpoint_for(control.read_endpoint or "", repo), control.apply_preserve
    )
    keep = result.stdout.strip()
    if not result.ok or not keep or "null" in keep:
        return None
    try:
        parsed = json.loads(keep)
    except ValueError:
        return None
    if not isinstance(parsed, dict):
        return None
    merged: dict[str, object] = dict(parsed)
    body = json.loads(payload)
    if isinstance(body, dict):
        merged.update(body)
    return canon(merged)


def apply_control(client: GhClient, control: Control, repo: str, ruleset_id: str) -> GhResult:
    """Run the corrective call. Assumes read_live ran first."""
    method = control.apply_method
    endpoint = endpoint_for(control.apply_endpoint, repo)
    if control.kind == "ruleset" and ruleset_id:
        method = "PUT"
        endpoint = f"repos/{repo}/rulesets/{ruleset_id}"
    body = canon(control.apply_payload) if control.apply_payload is not None else None
    if control.apply_preserve and body is not None:
        body = _preserved_body(client, control, repo, body)
        if body is None:
            return GhResult(
                1,
                "",
                f"preserve read failed or empty ({control.apply_preserve}); refusing to write",
            )
    return api_write(client, method, endpoint, body)
