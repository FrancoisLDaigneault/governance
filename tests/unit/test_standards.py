"""The module size limit is a test, not a promise."""

from pathlib import Path

import governance_tools

MAX_MODULE_LINES = 200
MAX_SCRIPT_LINES = 20

SRC = Path(governance_tools.__file__).resolve().parent
REPO = SRC.parents[1]
SCRIPTS = REPO / "scripts"


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def test_src_modules_max_200_lines() -> None:
    modules = sorted(SRC.glob("*.py"))
    assert modules, f"no module found under {SRC}"
    for module in modules:
        n = _line_count(module)
        assert n <= MAX_MODULE_LINES, f"{module.name}: {n} lines (max {MAX_MODULE_LINES})"


def test_scripts_max_20_lines() -> None:
    scripts = sorted(SCRIPTS.glob("*.py"))
    assert scripts, f"no script found under {SCRIPTS}"
    for script in scripts:
        n = _line_count(script)
        assert n <= MAX_SCRIPT_LINES, f"{script.name}: {n} lines (max {MAX_SCRIPT_LINES})"
