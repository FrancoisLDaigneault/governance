"""English-only language gate.

Pragmatic heuristic: French text virtually always carries accented characters,
so scanning for Latin diacritics catches regressions cheaply without NLP.
Deliberately excluded: .venv and tool caches (not tracked source).
"""

from pathlib import Path

import governance_tools

REPO = Path(governance_tools.__file__).resolve().parents[2]

# Latin accented letters (A-grave through y-umlaut, skipping the multiplication
# and division signs) plus OE ligatures, built from code points so this file
# itself stays accent-free.
_RANGES = ((0x00C0, 0x00D6), (0x00D8, 0x00F6), (0x00F8, 0x00FF), (0x0152, 0x0153))
ACCENTED = {chr(c) for lo, hi in _RANGES for c in range(lo, hi + 1)}


def _explicit_files() -> list[Path]:
    return [
        REPO / "hooks" / "pre-commit",
        REPO / "justfile",
        REPO / ".editorconfig",
        REPO / ".gitattributes",
        REPO / ".gitignore",
        REPO / "README.md",
        REPO / "baseline.json",
        REPO / "pyproject.toml",
    ]


def _scanned_files() -> list[Path]:
    files = _explicit_files()
    for tree in ("src", "scripts", "tests"):
        files += sorted((REPO / tree).rglob("*.py"))
    return files


def _accented_lines(path: Path) -> list[str]:
    rel = path.relative_to(REPO).as_posix()
    lines = path.read_text(encoding="utf-8").splitlines()
    return [
        f"{rel}:{lineno}"
        for lineno, line in enumerate(lines, start=1)
        if any(ch in ACCENTED for ch in line)
    ]


def test_all_text_is_english() -> None:
    # Globbed trees are inherently existence-checked; the explicit list is not,
    # so a renamed/moved target must fail loudly instead of shrinking the scan.
    missing = [p.relative_to(REPO).as_posix() for p in _explicit_files() if not p.is_file()]
    assert not missing, (
        "language-gate scan targets missing (renamed or moved? update _explicit_files):\n  "
        + "\n  ".join(missing)
    )
    files = _scanned_files()
    assert files, f"no file to scan under {REPO}"
    offenders: list[str] = []
    for path in files:
        if path.is_file():
            offenders += _accented_lines(path)
    assert not offenders, (
        "accented (non-English) characters found - translate to English:\n  "
        + "\n  ".join(offenders)
    )
