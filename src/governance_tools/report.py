"""Result types, rendering and exit codes.

Kept apart from the orchestration so the presentation layer stays pure and
directly testable.
"""

import io
import sys
from dataclasses import dataclass, field

OK, DRIFT, NA, ERR = "OK", "DRIFT", "NA", "ERR"
STRICT, APPLIED, FAIL = "STRICTER-THAN-BASELINE", "APPLIED", "FAIL"
# A control the API cannot correct: it audits, reports drift, and says so
# instead of claiming a write that would silently change nothing.
MANUAL = "MANUAL"
CLEAN_STATUSES = (OK, NA, APPLIED)


@dataclass(frozen=True)
class Mode:
    """How a run behaves: dry-run unless apply, guard on unless force."""

    apply: bool = False
    force: bool = False


@dataclass(frozen=True)
class ControlResult:
    """Outcome for one control, rendered as a `CTL <id> <status>` line."""

    control_id: str
    status: str
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class RepoReport:
    """Outcome for one repository; `error` marks a repo that could not be read."""

    repo: str
    visibility: str = ""
    archived: bool = False
    error: str = ""
    results: list[ControlResult] = field(default_factory=list)


@dataclass(frozen=True)
class OrgReport:
    """Outcome for one organization; `error` marks an org that could not be read."""

    org: str
    error: str = ""
    results: list[ControlResult] = field(default_factory=list)


def use_unix_newlines() -> None:
    """Emit LF, never CRLF.

    Python text-mode stdout translates to CRLF on Windows; the `CTL` lines are a
    machine-readable contract, so a stray carriage return would end up in any
    consumer's parsed value.
    """
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(newline="\n")


def _summary(results: list[ControlResult], *, apply: bool) -> str:
    tracked = (DRIFT, FAIL, ERR, STRICT, MANUAL)
    counts = {s: sum(1 for r in results if r.status == s) for s in tracked}
    head = f"{counts[FAIL]} failure(s)" if apply else f"{counts[DRIFT]} drift(s)"
    suffix = ""
    if counts[ERR]:
        suffix += f", {counts[ERR]} error(s)"
    if counts[STRICT]:
        suffix += f", {counts[STRICT]} stricter-than-baseline skip(s)"
    if counts[MANUAL]:
        suffix += f", {counts[MANUAL]} manual step(s)"
    return f"== done: {head}{suffix} =="


def summary_line(report: RepoReport, *, apply: bool) -> str:
    return _summary(report.results, apply=apply)


def _control_lines(results: list[ControlResult]) -> list[str]:
    """One `CTL <id> <status>` line per control, with its indented details."""
    lines: list[str] = []
    for result in results:
        lines.append(f"CTL {result.control_id} {result.status}")
        lines += [f"     {detail}" for detail in result.details]
    return lines


def render(report: RepoReport, *, apply: bool) -> list[str]:
    """Human and machine readable output: one `CTL` line per control."""
    if report.archived:
        return [f"WARN: {report.repo} is archived (read-only) - nothing to do"]
    mode = "apply" if apply else "dry-run"
    header = f"visibility: {report.visibility}, mode: {mode}"
    lines = [f"== governance bootstrap: {report.repo} ({header}) =="]
    lines += _control_lines(report.results)
    lines.append(_summary(report.results, apply=apply))
    return lines


def render_org(report: OrgReport, *, apply: bool) -> list[str]:
    """Same `CTL` contract as render, for an organization target."""
    mode = "apply" if apply else "dry-run"
    lines = [f"== governance bootstrap: organization {report.org} (mode: {mode}) =="]
    lines += _control_lines(report.results)
    lines.append(_summary(report.results, apply=apply))
    return lines


def statuses_for(results: list[ControlResult], control_ids: list[str]) -> dict[str, str]:
    """One status per control id; anything the run never reported becomes ERR.

    This is what stops a half-finished target from quietly shrinking a matrix
    into a clean-looking row.
    """
    seen = {result.control_id: result.status for result in results}
    return {control_id: seen.get(control_id, ERR) for control_id in control_ids}


def results_exit_code(results: list[ControlResult]) -> int:
    """0 when every control is clean, 1 on any drift, error, skip or failure."""
    return 1 if any(r.status not in CLEAN_STATUSES for r in results) else 0


def exit_code(report: RepoReport) -> int:
    """0 when every control is clean, 1 on any drift, error, skip or failure."""
    if report.archived:
        return 0
    return results_exit_code(report.results)
