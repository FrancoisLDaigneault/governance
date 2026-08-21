"""The README controls-block renderer: deterministic, complete, surgical.

`render_block` must list every baseline control and nothing else, in
baseline order, marking the manual ones; `updated_text` must replace the
marker-delimited block and refuse unusable markers, so a hand-edited or
truncated README fails instead of being half-rewritten.
"""

import re
from pathlib import Path

import pytest

from governance_tools.baseline import load_controls, split_by_scope
from governance_tools.readme import BEGIN, END, main, render_block, updated_text


def test_block_lists_every_control_grouped_and_ordered() -> None:
    controls = load_controls()
    repo, org = split_by_scope(controls)
    block = render_block(controls)
    for group in (repo, org):
        positions = [block.index(f"- `{c.id}` - ") for c in group]
        assert positions == sorted(positions), "controls must render in baseline order"
    assert len(re.findall(r"^- `", block, re.MULTILINE)) == len(controls)
    assert f"### Repository controls ({len(repo)})" in block
    assert f"### Organization controls ({len(org)})" in block
    assert block.startswith(BEGIN)
    assert block.endswith(END)


def test_block_is_deterministic() -> None:
    assert render_block(load_controls()) == render_block(load_controls())


def test_manual_marker_tracks_manual_reason() -> None:
    controls = {c.id: c for c in load_controls()}
    for line in render_block(list(controls.values())).splitlines():
        if line.startswith("- `"):
            control = controls[line.split("`")[1]]
            assert line.endswith("*(manual)*") == control.is_manual, control.id


def test_updated_text_replaces_only_the_block_and_is_idempotent() -> None:
    text = f"before\n\n{BEGIN}\nold\n{END}\n\nafter\n"
    block = f"{BEGIN}\nnew\n{END}"
    replaced = updated_text(text, block)
    assert replaced == f"before\n\n{BEGIN}\nnew\n{END}\n\nafter\n"
    assert updated_text(replaced, block) == replaced


def test_updated_text_rejects_missing_or_duplicated_markers() -> None:
    block = f"{BEGIN}\nx\n{END}"
    bad = ("no markers", f"{END}\n{BEGIN}", f"{BEGIN}\n{END}\n{BEGIN}\n{END}")
    for text in bad:
        with pytest.raises(ValueError, match="markers"):
            updated_text(text, block)


def test_main_check_apply_cycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text(f"intro\n\n{BEGIN}\nstale\n{END}\n", encoding="utf-8")
    assert main(["--check"]) == 1
    assert main(["--apply"]) == 0
    assert main(["--check"]) == 0
    assert main([]) == 0


def test_main_reports_unusable_readme_and_bad_arguments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("no markers here\n", encoding="utf-8")
    assert main(["--check"]) == 1
    assert main(["--frobnicate"]) == 2
