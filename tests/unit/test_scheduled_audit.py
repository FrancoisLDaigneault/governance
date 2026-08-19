"""The scheduled wrapper: capture, log format, rotation and exit mapping.

The invariant under test: drift (exit 1) is a finding the task reports as
success, while a malfunction (exit 2+) must surface as the task's own failure.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

import governance_tools
from governance_tools.scheduled_audit import (
    KEEP,
    capture_audit,
    default_log_dir,
    main,
    rotate,
    task_exit_code,
    write_log,
)

STARTED = datetime(2026, 8, 19, 9, 0, 0, tzinfo=timezone.utc)


def fake_audit(argv: list[str]) -> int:
    print("== matrix ==")
    print("auditing fld-forge/pi-config ...", file=sys.stderr)
    return 1


def test_capture_merges_stdout_and_stderr_in_order() -> None:
    code, output = capture_audit(fake_audit)
    assert code == 1
    assert output == "== matrix ==\nauditing fld-forge/pi-config ...\n"


def test_capture_passes_all_flag() -> None:
    seen: list[list[str]] = []

    def record(argv: list[str]) -> int:
        seen.append(argv)
        return 0

    capture_audit(record)
    assert seen == [["--all"]]


def test_write_log_names_header_and_footer(tmp_path: Path) -> None:
    log = write_log(tmp_path, STARTED, 1, "row\n")
    assert log.name == "2026-08-19_090000.log"
    text = log.read_text(encoding="utf-8")
    assert text.startswith("fleet audit started 2026-08-19 09:00:00 +0000\n")
    assert text.endswith("row\naudit exit code: 1\n")


def test_write_log_terminates_unterminated_output(tmp_path: Path) -> None:
    text = write_log(tmp_path, STARTED, 0, "no newline").read_text(encoding="utf-8")
    assert "no newline\naudit exit code: 0\n" in text


def test_write_log_creates_the_directory(tmp_path: Path) -> None:
    target = tmp_path / "governance-audit"
    write_log(target, STARTED, 0, "")
    assert target.is_dir()


def _seed_logs(log_dir: Path, count: int) -> list[Path]:
    logs = [log_dir / f"2026-01-{day:02d}_090000.log" for day in range(1, count + 1)]
    for log in logs:
        log.write_text("x", encoding="utf-8")
    return logs


def test_rotate_keeps_the_newest_and_removes_the_oldest(tmp_path: Path) -> None:
    logs = _seed_logs(tmp_path, KEEP + 3)
    removed = rotate(tmp_path)
    assert sorted(removed) == logs[:3]
    assert sorted(tmp_path.glob("*.log")) == logs[3:]


def test_rotate_below_the_cap_removes_nothing(tmp_path: Path) -> None:
    _seed_logs(tmp_path, KEEP)
    assert rotate(tmp_path) == []
    assert len(list(tmp_path.glob("*.log"))) == KEEP


@pytest.mark.parametrize(("audit_code", "expected"), [(0, 0), (1, 0), (2, 2), (3, 3)])
def test_task_exit_code_maps_drift_to_success(audit_code: int, expected: int) -> None:
    assert task_exit_code(audit_code) == expected


def test_default_log_dir_is_a_repo_sibling() -> None:
    directory = default_log_dir()
    repo = Path(governance_tools.__file__).resolve().parents[2]
    assert directory == repo.parent / f"{repo.name}-audit"


def test_main_runs_logs_rotates_and_maps(tmp_path: Path) -> None:
    _seed_logs(tmp_path, KEEP)
    code = main(run=fake_audit, log_dir=tmp_path, now=lambda: STARTED)
    assert code == 0  # drift is a finding, not a task failure
    assert len(list(tmp_path.glob("*.log"))) == KEEP  # rotation ran after the write
    newest = tmp_path / "2026-08-19_090000.log"
    text = newest.read_text(encoding="utf-8")
    assert "== matrix ==" in text
    assert "audit exit code: 1" in text


def test_main_logs_a_crash_as_a_malfunction(tmp_path: Path) -> None:
    def crashing(argv: list[str]) -> int:
        raise RuntimeError("baseline exploded")

    assert main(run=crashing, log_dir=tmp_path, now=lambda: STARTED) == 2
    text = (tmp_path / "2026-08-19_090000.log").read_text(encoding="utf-8")
    assert "Traceback (most recent call last):" in text
    assert "RuntimeError: baseline exploded" in text
    assert "audit exit code: 2" in text


def test_main_surfaces_a_malfunction(tmp_path: Path) -> None:
    def broken(argv: list[str]) -> int:
        print("usage: audit.py [--all | OWNER/REPO ...]", file=sys.stderr)
        return 2

    assert main(run=broken, log_dir=tmp_path, now=lambda: STARTED) == 2
    text = (tmp_path / "2026-08-19_090000.log").read_text(encoding="utf-8")
    assert "audit exit code: 2" in text
