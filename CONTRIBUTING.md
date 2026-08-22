# Contributing

## Setup

```bash
uv sync --locked   # creates .venv/ and installs the package + dev tools
uv run pre-commit install --install-hooks   # installs the framework hooks
```

That installs the `pre-commit` and `pre-merge-commit` hook types, because
`.pre-commit-config.yaml` declares both in `default_install_hook_types`: a merge
that commits on its own runs the second one, and would otherwise bring in
changes no gate ever saw.

With [just](https://just.systems) installed, `just setup` runs both commands in
one step and clears any legacy `core.hooksPath` setting (optional -- the
commands above remain the baseline).

Running the tool also needs [`gh`](https://cli.github.com/) authenticated. The
test suite does not: it drives the real code through a fake `gh` layer and never
touches the network.

## Contribution flow

`main` is protected: direct pushes are rejected and every change lands through
a pull request. Work on a branch, let the pre-commit hooks run the gates at
each commit (`uv run pre-commit run --all-files` replays them on demand), push
the branch, open a PR, and merge (squash) once the checks are green. The
secrets gate is the one exception to that replay: gitleaks reads the staged
diff, so it has nothing to scan when nothing is staged. Use
`gitleaks git --redact -v .` for the full-history scan CI runs.

## Quality gates

Before any PR, these commands must pass without errors (the pre-commit hooks
and the CI quality job run them too):

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check --error-on-warning src scripts tests
uv run mypy
uv run deptry src
uv run lint-imports
uv run pytest -q
```

The full pytest run enforces a 90% branch-coverage floor; subset runs
(e.g. `uv run pytest tests/unit`) need `--no-cov`. CI additionally installs
with `uv sync --locked` to prove the lockfile is reproducible.

## Standards enforced by tooling

- Cyclomatic complexity (McCabe) <= 8
- <= 30 statements per function, <= 5 arguments
- Lines <= 100 characters
- Complementary static typing gates: ty warnings fail and mypy runs in strict mode
- Import boundaries with Import Linter contracts plus Ruff TID251
- <= 200 lines per module, <= 20 per script - checked by `tests/unit/test_standards.py`
- English only in code, comments and docs. `tests/unit/test_language.py`
  enforces this with an accent heuristic over a defined file set (generated
  files such as `CHANGELOG.md` are excluded); the rule itself applies to
  everything you write.

## Rules specific to this tool

It changes repository settings across a fleet, so two habits are not optional:

- **Keep the IO in `gh.py`.** Every other module takes a `GhClient`, which is
  what makes the whole tool testable without the network. A new `subprocess`
  call anywhere else breaks that property.
- **A behaviour worth relying on needs a test that fails without it.** The
  dry-run default, the stricter-than-baseline guard, the read-error handling
  and the exit codes each have named tests; treat them as the contract.

Try changes against `governance-canary` (a public scratch repository) before
pointing them at a real one, and read the dry-run diff before every `--apply`.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)
are mandatory. The type drives the release: `feat:` bumps the minor version,
`fix:` and `docs:` bump the patch (`docs:` commits appear in a Documentation
changelog section), and a breaking change bumps the major; `ci:`, `chore:`,
`refactor:` and `test:` do not trigger a release by themselves.
release-please opens and updates the release PR from these commits; merging
that PR creates the tag and the GitHub release and uploads the release assets
(wheel, sdist, SBOM, checksums, attestations).
