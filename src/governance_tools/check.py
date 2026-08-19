"""Classify one control against its live state, and run the corrective call.

Shared by both orchestrators: `bootstrap` keys this by OWNER/REPO and `org` keys
it by an organization login. Nothing here knows which, because a control already
carries its own endpoints and the target is substituted into them.
"""

from governance_tools.compare import canon, stricter_extras
from governance_tools.control import Control
from governance_tools.controls import (
    LiveState,
    apply_control,
    fetch_ruleset,
    probe_na,
    read_live,
    ruleset_endpoint,
)
from governance_tools.gh import GhClient
from governance_tools.report import (
    APPLIED,
    DRIFT,
    ERR,
    FAIL,
    MANUAL,
    NA,
    OK,
    STRICT,
    ControlResult,
    Mode,
)


def _stricter_guard(
    client: GhClient, control: Control, target: str, ruleset_id: str
) -> ControlResult | None:
    """Refuse to lower a live ruleset that is stricter than the baseline."""
    try:
        live_ruleset = fetch_ruleset(client, ruleset_endpoint(control, target, ruleset_id))
    except RuntimeError:
        return ControlResult(
            control.id, ERR, ("stricter-than-baseline check failed; refusing to normalize",)
        )
    extras = stricter_extras(live_ruleset, control.desired)
    if not extras:
        return None
    return ControlResult(
        control.id,
        STRICT,
        (
            "live ruleset is stricter than the baseline; skipped",
            *extras,
            "re-run with --force-normalize to overwrite it with the baseline",
        ),
    )


def _apply_and_recheck(
    client: GhClient, control: Control, target: str, ruleset_id: str, desired: str
) -> ControlResult:
    result = apply_control(client, control, target, ruleset_id)
    if not result.ok:
        message = " ".join(result.combined.strip().splitlines()[:2])
        return ControlResult(control.id, FAIL, (f"apply error: {message}",))
    after = read_live(client, control, target)
    if after.error:
        return ControlResult(
            control.id, ERR, (f"applied, but the re-check read failed: {after.error}",)
        )
    if after.canonical == desired:
        return ControlResult(control.id, APPLIED)
    return ControlResult(
        control.id,
        FAIL,
        (
            "applied but live state still differs",
            f"desired: {desired}",
            f"live:    {after.canonical}",
        ),
    )


def _resolve_drift(
    client: GhClient, control: Control, target: str, live: LiveState, mode: Mode
) -> ControlResult:
    """Live differs from the baseline: guard it, report it, or correct it."""
    desired = canon(control.desired)
    drift = (f"desired: {desired}", f"live:    {live.canonical}")
    if control.kind == "ruleset" and live.ruleset_id and not mode.force:
        guard = _stricter_guard(client, control, target, live.ruleset_id)
        if guard is not None:
            return guard
    if not mode.apply:
        return ControlResult(control.id, DRIFT, drift)
    # Never claim an APPLIED the API would not honour: these fields accept the
    # write and keep the old value, so a corrective call would report success
    # while changing nothing.
    if control.is_manual:
        return ControlResult(control.id, MANUAL, (*drift, f"manual: {control.manual_reason}"))
    return _apply_and_recheck(client, control, target, live.ruleset_id, desired)


def check_control(
    client: GhClient, control: Control, target: str, visibility: str, mode: Mode
) -> ControlResult:
    """Classify one control, applying the corrective call when asked."""
    if not control.applies_to(visibility):
        detail = f"skipped: public-only control on a {visibility} repo (needs a paid plan)"
        return ControlResult(control.id, NA, (detail,))
    # Visibility is a static gate; some controls also need a live property of the
    # target to be governable at all. A failed probe is an error, never NA: the
    # baseline must not stop governing a repository because a read hiccuped.
    if control.na_when:
        not_applicable, error = probe_na(client, control, target)
        if error:
            return ControlResult(control.id, ERR, (f"applicability probe failed: {error}",))
        if not_applicable:
            return ControlResult(control.id, NA, (f"skipped: {control.na_reason}",))
    live = read_live(client, control, target)
    if live.error:
        return ControlResult(control.id, ERR, (f"read failed: {live.error}",))
    if live.canonical == canon(control.desired):
        return ControlResult(control.id, OK)
    return _resolve_drift(client, control, target, live, mode)
