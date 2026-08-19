"""Scheduled fleet audit: run, log with a timestamp, keep a bounded history.

The audit runs in-process - `audit.main` is a plain function - so no subprocess
is needed and the IO boundary stays inside `gh.py`. Stdout and stderr are
merged into one buffer because the progress lines (stderr) only make sense
interleaved with the matrix (stdout), the way a terminal would show them.

Exit-code policy. The audit exits 1 when it finds drift; that is a finding,
not a malfunction. This module therefore reports success for 0 (clean) and 1
(drift) alike, and fails only for 2 and above (usage error, or the audit
refusing to report a partial fleet). Mapping drift to a failing task would
make it look permanently broken - the organization carries two controls that
only a human can clear - and a genuinely broken audit would then be
indistinguishable from an ordinary drifting one. What the run FOUND is in the
log; whether it RAN is the task's Last Result.
"""

import contextlib
import io
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from governance_tools.audit import main as audit_main

KEEP = 12  # weekly cadence, so about a quarter of history
MALFUNCTION = 2  # below this the audit ran; from here on it could not report


def default_log_dir() -> Path:
    """The log directory: a sibling of the repository named `<repo>-audit`.

    Derived from this file's location rather than hard-coded, so the wrapper
    keeps working if the repository moves; the scheduled task only needs the
    absolute path of `uv` and of the repository, both in its own command line.
    """
    repo = Path(__file__).resolve().parents[2]
    return repo.parent / f"{repo.name}-audit"


def capture_audit(run: Callable[[list[str]], int]) -> tuple[int, str]:
    """Run the fleet audit with stdout and stderr merged into one string."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        code = run(["--all"])
    return code, buffer.getvalue()


def write_log(log_dir: Path, started: datetime, code: int, output: str) -> Path:
    """One UTF-8 log per run, named so that names sort chronologically."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / f"{started:%Y-%m-%d_%H%M%S}.log"
    body = output if not output or output.endswith("\n") else output + "\n"
    header = f"fleet audit started {started:%Y-%m-%d %H:%M:%S %z}".rstrip()
    log.write_text(f"{header}\n{body}audit exit code: {code}\n", encoding="utf-8")
    return log


def rotate(log_dir: Path, keep: int = KEEP) -> list[Path]:
    """Drop the oldest logs beyond `keep`; names sort chronologically."""
    stale = sorted(log_dir.glob("*.log"), reverse=True)[keep:]
    for log in stale:
        log.unlink()
    return stale


def task_exit_code(audit_code: int) -> int:
    """Success for clean (0) and drift (1); the audit's own code for 2+."""
    return audit_code if audit_code >= MALFUNCTION else 0


def main(
    run: Callable[[list[str]], int] = audit_main,
    log_dir: Path | None = None,
    now: Callable[[], datetime] = lambda: datetime.now().astimezone(),
) -> int:
    """Run, log, rotate; the return value is the scheduled task's Last Result."""
    started = now()
    code, output = capture_audit(run)
    directory = log_dir if log_dir is not None else default_log_dir()
    write_log(directory, started, code, output)
    rotate(directory)
    return task_exit_code(code)
