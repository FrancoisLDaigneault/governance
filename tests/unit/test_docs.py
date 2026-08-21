"""Documentation drift gate.

The docs state facts that the tooling also defines: test counts, quality-gate
commands, size caps, the coverage floor, the Python version. Each fact has a
machine-readable source of truth; this gate fails when a doc claim and its
source disagree, naming the file and both values. Only anchored patterns are
checked, never prose wording, so rephrasing stays free while numbers cannot
silently rot.
"""

import re
import tomllib

import test_standards

from governance_tools.baseline import load_controls
from governance_tools.readme import render_block, updated_text

REPO = test_standards.REPO
DOCS = ("README.md", "CONTRIBUTING.md", "AGENTS.md")
TIERS = ("unit", "integration")


def _text(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def _flat(rel: str) -> str:
    """Whitespace-collapsed text, so wrapped lines still match one pattern."""
    return " ".join(_text(rel).split())


def _count_tests(tier: str) -> int:
    files = sorted((REPO / "tests" / tier).rglob("*.py"))
    pattern = re.compile(r"^def test_", re.MULTILINE)
    return sum(len(pattern.findall(p.read_text(encoding="utf-8"))) for p in files)


def test_northstar_test_counts() -> None:
    unit, integration = (_count_tests(tier) for tier in TIERS)
    total = unit + integration
    text = _flat("NORTHSTAR.md")
    row = re.search(r"(\d+) \((\d+) unit / (\d+) integration\)", text)
    assert row, "NORTHSTAR.md: green-tests row 'N (U unit / I integration)' not found"
    found = tuple(int(g) for g in row.groups())
    assert found == (total, unit, integration), (
        f"NORTHSTAR.md green-tests row says {found}, actual is ({total}, {unit}, {integration})"
    )
    duration = re.search(r"\((\d+) tests\)", text)
    assert duration, "NORTHSTAR.md: suite-duration row '(N tests)' not found"
    assert int(duration.group(1)) == total, (
        f"NORTHSTAR.md suite-duration row says {duration.group(1)} tests, actual is {total}"
    )


def test_northstar_module_count() -> None:
    """The network-IO row states the package's module total; the total must
    track the modules on disk (the '1' itself is enforced by Import Linter)."""
    modules = [
        p
        for p in sorted((REPO / "src" / "governance_tools").glob("*.py"))
        if p.name != "__init__.py"
    ]
    row = re.search(r"Modules performing network IO \| \d+ of (\d+)", _flat("NORTHSTAR.md"))
    assert row, "NORTHSTAR.md: 'Modules performing network IO | N of M' row not found"
    assert int(row.group(1)) == len(modules), (
        f"NORTHSTAR.md network-IO row says 'of {row.group(1)}' modules, "
        f"src/governance_tools has {len(modules)}"
    )


def _gate_commands() -> list[str]:
    """The quality commands of the justfile `check` recipe (source of truth)."""
    lines = _text("justfile").splitlines()
    start = lines.index("check:") + 1
    block = []
    for line in lines[start:]:
        if not line.startswith(" "):
            break
        block.append(line.strip())
    return [cmd for cmd in block if cmd.startswith("uv run ")]


def test_gate_commands_documented() -> None:
    commands = _gate_commands()
    assert commands, "justfile check recipe: no 'uv run ...' command found"
    for doc in DOCS:
        text = _text(doc)
        missing = [cmd for cmd in commands if cmd not in text]
        assert not missing, f"{doc}: gate commands not quoted verbatim: {missing}"
    ci = _text(".github/workflows/ci.yml")
    missing = [cmd for cmd in commands if f"- run: {cmd}" not in ci]
    assert not missing, f"ci.yml quality job: gate commands missing: {missing}"


def test_gate_commands_in_precommit_hooks() -> None:
    """Ruff runs through its pinned mirror hooks; the venv-bound gate
    commands must stay wired as local-hook entries, or a deleted hook
    would silently drop a local gate."""
    commands = [cmd for cmd in _gate_commands() if not cmd.startswith("uv run ruff")]
    assert commands, "justfile check recipe: no venv-bound 'uv run ...' command found"
    config = _text(".pre-commit-config.yaml")
    missing = [cmd for cmd in commands if f"entry: {cmd}" not in config]
    assert not missing, f".pre-commit-config.yaml: local-hook entries missing: {missing}"


def test_size_caps_documented() -> None:
    module_cap = test_standards.MAX_MODULE_LINES
    script_cap = test_standards.MAX_SCRIPT_LINES
    claims = {
        "CONTRIBUTING.md": r"<= (\d+) lines per module, <= (\d+) per script",
        "AGENTS.md": r"modules <= (\d+) lines, scripts <= (\d+) lines",
    }
    for doc, pattern in claims.items():
        match = re.search(pattern, _flat(doc))
        assert match, f"{doc}: size-cap claim matching {pattern!r} not found"
        found = (int(match.group(1)), int(match.group(2)))
        assert found == (module_cap, script_cap), (
            f"{doc} says caps {found}, test_standards enforces ({module_cap}, {script_cap})"
        )


def _coverage_floor() -> int:
    with (REPO / "pyproject.toml").open("rb") as fh:
        addopts = tomllib.load(fh)["tool"]["pytest"]["ini_options"]["addopts"]
    match = re.search(r"--cov-fail-under=(\d+)", addopts)
    assert match, "pyproject.toml: --cov-fail-under not found in pytest addopts"
    return int(match.group(1))


def test_coverage_floor_documented() -> None:
    floor = _coverage_floor()
    for doc in DOCS:
        claims = re.findall(r"(\d+)% (?:branch-)?coverage floor", _flat(doc))
        assert claims, f"{doc}: no coverage-floor claim found"
        wrong = [c for c in claims if int(c) != floor]
        assert not wrong, f"{doc} claims floor(s) {wrong}%, pyproject enforces {floor}%"
    northstar = re.search(r">= (\d+)% \(enforced floor\)", _flat("NORTHSTAR.md"))
    assert northstar, "NORTHSTAR.md: '>= N% (enforced floor)' row not found"
    assert int(northstar.group(1)) == floor, (
        f"NORTHSTAR.md floor row says {northstar.group(1)}%, pyproject enforces {floor}%"
    )


def test_python_version_documented() -> None:
    with (REPO / "pyproject.toml").open("rb") as fh:
        requires = tomllib.load(fh)["project"]["requires-python"]
    version = requires.removeprefix(">=")
    badge = re.search(r"python-(\d+\.\d+)%2B", _text("README.md"))
    assert badge, "README.md: python version badge not found"
    assert badge.group(1) == version, (
        f"README.md badge says {badge.group(1)}+, pyproject requires {requires}"
    )
    agents = re.search(r"Python (\d+\.\d+)\+", _text("AGENTS.md"))
    assert agents, "AGENTS.md: 'Python N.NN+' claim not found"
    assert agents.group(1) == version, (
        f"AGENTS.md says Python {agents.group(1)}+, pyproject requires {requires}"
    )


def test_controls_count_documented() -> None:
    """The README and NORTHSTAR state how many controls the baseline governs,
    split by scope; the split must track baseline.json, not memory."""
    controls = load_controls()
    actual = (
        len(controls),
        sum(1 for c in controls if c.scope == "repo"),
        sum(1 for c in controls if c.scope == "org"),
    )
    match = re.search(
        r"(\d+) controls \((\d+) repository-scope, (\d+) organization-scope\)",
        _flat("README.md"),
    )
    assert match, "README.md: 'N controls (R repository-scope, O organization-scope)' not found"
    found = tuple(int(g) for g in match.groups())
    assert found == actual, f"README.md says controls {found}, baseline.json defines {actual}"
    row = re.search(
        r"Governed controls \| (\d+) \((\d+) repository, (\d+) organization\)",
        _flat("NORTHSTAR.md"),
    )
    assert row, "NORTHSTAR.md: 'Governed controls | N (R repository, O organization)' row not found"
    found = tuple(int(g) for g in row.groups())
    assert found == actual, (
        f"NORTHSTAR.md governed-controls row says {found}, baseline.json defines {actual}"
    )


def test_controls_section_generated() -> None:
    """The README controls list is generated from baseline.json; a stale,
    hand-edited or marker-less block fails here until the renderer is rerun."""
    text = _text("README.md")
    hint = "run 'uv run python scripts/render_readme.py --apply'"
    try:
        wanted = updated_text(text, render_block(load_controls()))
    except ValueError as exc:
        raise AssertionError(f"{exc} - {hint}") from exc
    assert wanted == text, f"README.md controls block is stale - {hint}"


_NUMBER_WORDS = {
    word: value
    for value, word in enumerate(
        ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine"),
        start=1,
    )
}


def test_manual_controls_documented() -> None:
    """The README counts and lists the manual controls; both must track
    which baseline controls actually carry a `manual_reason`."""
    manual = sorted(c.id for c in load_controls() if c.is_manual)
    scopes = {c.scope for c in load_controls() if c.is_manual}
    assert scopes == {"org"}, (
        f"manual controls now span scopes {scopes}; the README sentence "
        "'organization controls are manual' needs rewording"
    )
    claim = re.search(r"(\w+) organization controls are \*\*manual\*\*", _flat("README.md"))
    assert claim, "README.md: 'N organization controls are **manual**' claim not found"
    assert _NUMBER_WORDS.get(claim.group(1).lower()) == len(manual), (
        f"README.md says {claim.group(1)} manual controls, baseline.json defines {len(manual)}"
    )
    listed = re.search(r"are \*\*manual\*\* \(([^)]*)\)", _flat("README.md"))
    assert listed, "README.md: manual controls are not listed by id after the claim"
    ids = sorted(re.findall(r"`([^`]+)`", listed.group(1)))
    assert ids == manual, f"README.md lists manual controls {ids}, baseline.json defines {manual}"


def test_scheduled_audit_manual_count() -> None:
    """The scheduled-audit rationale counts the controls only a human can
    clear; that is exactly the baseline's manual set."""
    actual = sum(1 for c in load_controls() if c.is_manual)
    claim = re.search(
        r"carries (\w+) controls that only a human can clear",
        _flat("docs/scheduled-audit.md"),
    )
    assert claim, (
        "docs/scheduled-audit.md: 'carries N controls that only a human can clear' not found"
    )
    assert _NUMBER_WORDS.get(claim.group(1).lower()) == actual, (
        f"docs/scheduled-audit.md says {claim.group(1)} human-only controls, "
        f"baseline.json defines {actual}"
    )
