"""Result types, rendering and exit codes.

Kept apart from the orchestration so the presentation layer stays pure and
directly testable.
"""

import io
import sys
from dataclasses import dataclass, field

OK, DRIFT, NA, ERR = "OK", "DRIFT", "NA", "ERR"
STRICT, APPLIED, FAIL = "STRICTER-THAN-BASELINE", "APPLIED", "FAIL"
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


def use_unix_newlines() -> None:
    """Emit LF, never CRLF.

    Python text-mode stdout translates to CRLF on Windows; the `CTL` lines are a
    machine-readable contract, so a stray carriage return would end up in any
    consumer's parsed value.
    """
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(newline="\n")


def summary_line(report: RepoReport, *, apply: bool) -> str:
    tracked = (DRIFT, FAIL, ERR, STRICT)
    counts = {s: sum(1 for r in report.results if r.status == s) for s in tracked}
    head = f"{counts[FAIL]} failure(s)" if apply else f"{counts[DRIFT]} drift(s)"
    suffix = ""
    if counts[ERR]:
        suffix += f", {counts[ERR]} error(s)"
    if counts[STRICT]:
        suffix += f", {counts[STRICT]} stricter-than-baseline skip(s)"
    return f"== done: {head}{suffix} =="


def render(report: RepoReport, *, apply: bool) -> list[str]:
    """Human and machine readable output: one `CTL` line per control."""
    if report.archived:
        return [f"WARN: {report.repo} is archived (read-only) - nothing to do"]
    mode = "apply" if apply else "dry-run"
    header = f"visibility: {report.visibility}, mode: {mode}"
    lines = [f"== governance bootstrap: {report.repo} ({header}) =="]
    for result in report.results:
        lines.append(f"CTL {result.control_id} {result.status}")
        lines += [f"     {detail}" for detail in result.details]
    lines.append(summary_line(report, apply=apply))
    return lines


def exit_code(report: RepoReport) -> int:
    """0 when every control is clean, 1 on any drift, error, skip or failure."""
    if report.archived:
        return 0
    return 1 if any(r.status not in CLEAN_STATUSES for r in report.results) else 0
