"""Matrix rendering and cell counting for the fleet audit.

Pure presentation: it takes rows of statuses and returns lines, so the audit
orchestration stays free of formatting and both sections (repositories and
organizations) render through the same code.
"""

from governance_tools.baseline import Control
from governance_tools.report import DRIFT, ERR, NA, OK, STRICT

MARKS = {OK: "OK", DRIFT: "DRIFT", NA: "-", STRICT: "STRICT"}
CLEAN_CELLS = (OK, DRIFT, NA)


def _cell(statuses: dict[str, str], control_id: str, width: int) -> str:
    """One matrix cell; a status the row never recorded renders as ERR."""
    status = statuses.get(control_id, ERR)
    return MARKS.get(status, status).ljust(width)


def render_matrix(
    rows: dict[str, dict[str, str]], controls: list[Control], label: str = "repo"
) -> list[str]:
    """The status matrix: targets down the side, controls across the top."""
    codes = {control.id: f"C{i + 1}" for i, control in enumerate(controls)}
    name_width = max(len(name) for name in [*rows, label])
    col_width = max(6, *(len(code) for code in codes.values()))
    legend = ", ".join(f"{codes[c.id]}={c.id}" for c in controls)
    header = (
        label.ljust(name_width) + "  " + "  ".join(codes[c.id].ljust(col_width) for c in controls)
    )
    lines = [
        f"legend: {legend}",
        "cells: OK = compliant, DRIFT = differs from baseline, - = not applicable,",
        "       ERR = could not be checked, STRICT = live is stricter (skipped)",
        "",
        header,
        "-" * len(header),
    ]
    for name in sorted(rows):
        cells = [_cell(rows[name], control.id, col_width) for control in controls]
        lines.append(name.ljust(name_width) + "  " + "  ".join(cells))
    return lines


def count_cells(rows: dict[str, dict[str, str]]) -> tuple[int, int]:
    """Drift cells, and cells that could not be checked or were skipped."""
    drift = sum(1 for statuses in rows.values() for s in statuses.values() if s == DRIFT)
    bad = sum(1 for statuses in rows.values() for s in statuses.values() if s not in CLEAN_CELLS)
    return drift, bad


def print_totals(drift: int, bad: int, errors: list[str]) -> int:
    """Print the totals and the error log; returns the process exit code."""
    print(f"\ntotal drift cells: {drift}")
    if bad:
        print(f"total unchecked/skipped cells: {bad}")
    if errors:
        print("\n== targets that could not be fully audited ==")
        print("\n".join(errors))
    return 1 if drift or bad else 0
