"""Per-control IO: read the live projected state, and run the corrective call.

Every function here takes a GhClient, so the network is injectable. A read that
fails sets `error`: a read error is an error, never drift, and never falls
through to a corrective write.
"""

import json
from dataclasses import dataclass

from governance_tools.compare import canon, canon_text
from governance_tools.control import Control
from governance_tools.gh import GhClient, GhResult, api_get, api_write

ABSENT = '"absent"'


@dataclass(frozen=True)
class LiveState:
    """Projected live state of one control."""

    canonical: str = ""
    ruleset_id: str = ""
    error: str = ""


def endpoint_for(template: str, target: str) -> str:
    """Substitute the scope placeholder with the target.

    Both placeholders are replaced because loading validates that a template
    carries exactly the one its scope requires, so only one can ever match.
    """
    return template.replace("{repo}", target).replace("{org}", target)


def ruleset_endpoint(control: Control, target: str, ruleset_id: str) -> str:
    """Detail endpoint of one ruleset, derived from the control's own listing.

    Derived rather than hardcoded so the same code serves `repos/{repo}/rulesets`
    and `orgs/{org}/rulesets`.
    """
    return f"{endpoint_for(control.read_endpoint or '', target)}/{ruleset_id}"


def _canonical(raw: str) -> tuple[str, str]:
    """(canonical, error): an unparseable success response is an error, never drift.

    `gh` can exit 0 and still print something that is not JSON (a stray notice,
    or a jq filter emitting several values). Letting that raise here would abort
    the whole run, losing repositories a fleet audit had already checked.
    """
    try:
        return canon_text(raw), ""
    except ValueError:
        return "", f"unparseable response: {raw.strip()[:80]}"


def _read_ruleset(client: GhClient, control: Control, target: str) -> LiveState:
    # includes_parents=false: after an org migration a parent ruleset could
    # otherwise match by name and the repo-level follow-up call would 404. The
    # organization listing ignores the parameter, which is why it is safe here.
    listing = api_get(
        client,
        f"{endpoint_for(control.read_endpoint or '', target)}?includes_parents=false",
        f'[.[] | select(.name=="{control.ruleset_name}")][0].id // empty',
    )
    if not listing.ok:
        return LiveState(error=listing.first_error_line())
    ruleset_id = listing.stdout.strip()
    if not ruleset_id:
        return LiveState(canonical=ABSENT)
    projected = api_get(client, ruleset_endpoint(control, target, ruleset_id), control.projection)
    if not projected.ok:
        return LiveState(ruleset_id=ruleset_id, error=projected.first_error_line())
    canonical, error = _canonical(projected.stdout)
    return LiveState(canonical=canonical, ruleset_id=ruleset_id, error=error)


def _read_status204(client: GhClient, control: Control, target: str) -> LiveState:
    # 204 = enabled, 404 = disabled; anything else (401/403/5xx) is a read
    # error and must not be mistaken for "disabled".
    result = api_get(client, endpoint_for(control.read_endpoint or "", target))
    if result.ok:
        return LiveState(canonical=canon({"enabled": True}))
    if "HTTP 404" in result.combined:
        return LiveState(canonical=canon({"enabled": False}))
    return LiveState(error=result.first_error_line())


def _read_json(client: GhClient, control: Control, target: str) -> LiveState:
    result = api_get(client, endpoint_for(control.read_endpoint or "", target), control.projection)
    if not result.ok:
        return LiveState(error=result.first_error_line())
    canonical, error = _canonical(result.stdout)
    return LiveState(canonical=canonical, error=error)


def probe_na(client: GhClient, control: Control, target: str) -> tuple[bool, str]:
    """(not applicable, error) for a control that declares a live applicability probe.

    Run before the state read and short-circuits it, so a target the control
    cannot govern costs one call rather than two. Anything the filter emits
    other than `true` or `false` is an error, never a guess: a probe that
    cannot be trusted must not decide between NA and drift.
    """
    result = api_get(client, endpoint_for(control.read_endpoint or "", target), control.na_when)
    if not result.ok:
        return False, result.first_error_line()
    answer = result.stdout.strip()
    if answer not in ("true", "false"):
        return False, f"applicability probe returned {answer[:40]!r}, expected true or false"
    return answer == "true", ""


def read_live(client: GhClient, control: Control, target: str) -> LiveState:
    """Read one control's live projected state, for a repository or an org."""
    if control.kind == "ruleset":
        return _read_ruleset(client, control, target)
    if control.kind == "status204":
        return _read_status204(client, control, target)
    return _read_json(client, control, target)


def fetch_ruleset(client: GhClient, endpoint: str) -> dict[str, object]:
    """Full live ruleset object, for the stricter-than-baseline guard.

    Raises RuntimeError when the read itself fails: a failed check must never
    read as "not stricter". Unparseable but successful output yields {}, which
    the guard treats as no extras, matching the reference implementation.
    """
    result = api_get(client, endpoint)
    if not result.ok:
        raise RuntimeError(result.first_error_line())
    try:
        parsed = json.loads(result.stdout)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _preserved_body(
    client: GhClient, control: Control, target: str, payload: dict[str, object]
) -> str | None:
    """Merge ungoverned-but-required fields, read live, into the request body.

    Returns None when the preserve read fails, is empty, unparseable, or carries
    a null value: the write is then refused rather than sending a partial body
    to a privileged endpoint.
    """
    result = api_get(
        client, endpoint_for(control.read_endpoint or "", target), control.apply_preserve
    )
    keep = result.stdout.strip()
    if not result.ok or not keep:
        return None
    try:
        parsed = json.loads(keep)
    except ValueError:
        return None
    # A null value means the API did not report the field: echoing it back would
    # send a partial body. Checked on the parsed value, not on the raw text, so a
    # legitimate string containing "null" does not refuse the write.
    if not isinstance(parsed, dict) or any(value is None for value in parsed.values()):
        return None
    merged: dict[str, object] = dict(parsed)
    merged.update(payload)
    return canon(merged)


def apply_control(client: GhClient, control: Control, target: str, ruleset_id: str) -> GhResult:
    """Run the corrective call. Assumes read_live ran first."""
    method = control.apply_method
    endpoint = endpoint_for(control.apply_endpoint, target)
    if control.kind == "ruleset" and ruleset_id:
        method = "PUT"
        endpoint = ruleset_endpoint(control, target, ruleset_id)
    body = canon(control.apply_payload) if control.apply_payload is not None else None
    if control.apply_preserve and control.apply_payload is not None:
        body = _preserved_body(client, control, target, control.apply_payload)
        if body is None:
            return GhResult(
                1,
                "",
                f"preserve read failed or empty ({control.apply_preserve}); refusing to write",
            )
    return api_write(client, method, endpoint, body)
