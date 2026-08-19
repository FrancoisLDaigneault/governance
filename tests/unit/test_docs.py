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
    """The README states how many controls the baseline governs."""
    actual = len(load_controls())
    match = re.search(r"(\d+) controls", _flat("README.md"))
    assert match, "README.md: 'N controls' claim not found"
    assert int(match.group(1)) == actual, (
        f"README.md says {match.group(1)} controls, baseline.json defines {actual}"
    )
