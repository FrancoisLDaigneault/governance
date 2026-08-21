"""Render the README controls block from the validated baseline.

`baseline.json` is the single source of truth for what is governed; this
module renders the marker-delimited block inside the README `## Controls`
section from the parsed controls, so the public list can never drift from
the baseline again: the documentation gate (`tests/unit/test_docs.py`)
fails whenever the block and the baseline disagree.

Rendering is deterministic: controls appear in baseline order, grouped by
scope, each as its id plus the first sentence of its description, with
`*(manual)*` marking the controls no API call can correct. The markers
stay in the file, so the prose around the block remains human-owned.
"""

import sys
from pathlib import Path

from governance_tools.baseline import load_controls, split_by_scope
from governance_tools.control import Control

README = Path("README.md")
BEGIN = (
    "<!-- controls:begin - generated from src/governance_tools/baseline.json; "
    "regenerate with: uv run python scripts/render_readme.py --apply -->"
)
END = "<!-- controls:end -->"
USAGE = "usage: render_readme.py [--check | --apply]"
STALE = "README.md controls block is stale: run 'uv run python scripts/render_readme.py --apply'"


def _entry(control: Control) -> str:
    """One bullet: the id, the first description sentence, a manual mark."""
    summary = control.description.split(". ")[0].removesuffix(".")
    manual = " *(manual)*" if control.is_manual else ""
    return f"- `{control.id}` - {summary}.{manual}"


def render_block(controls: list[Control]) -> str:
    """The generated block, markers included, controls in baseline order."""
    repo, org = split_by_scope(controls)
    lines = [BEGIN, "", f"### Repository controls ({len(repo)})", ""]
    lines += [_entry(c) for c in repo]
    lines += ["", f"### Organization controls ({len(org)})", ""]
    lines += [_entry(c) for c in org]
    lines += ["", END]
    return "\n".join(lines)


def updated_text(text: str, block: str) -> str:
    """The README text with its block replaced; raises on unusable markers."""
    begin, end = text.find(BEGIN), text.find(END)
    if begin == -1 or end == -1 or end < begin:
        raise ValueError("README.md: controls markers missing or out of order")
    if BEGIN in text[begin + len(BEGIN) :] or END in text[end + len(END) :]:
        raise ValueError("README.md: controls markers must appear exactly once")
    return text[:begin] + block + text[end + len(END) :]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args not in ([], ["--check"], ["--apply"]):
        print(USAGE, file=sys.stderr)
        return 2
    text = README.read_text(encoding="utf-8")
    try:
        wanted = updated_text(text, render_block(load_controls()))
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    if wanted == text:
        print("README controls block: up to date")
        return 0
    if args == ["--apply"]:
        README.write_text(wanted, encoding="utf-8", newline="\n")
        print("README controls block: rewritten")
        return 0
    print(STALE, file=sys.stderr)
    return 1
