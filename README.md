# Governance baseline as code

[![CI](https://img.shields.io/github/actions/workflow/status/fld-forge/governance/ci.yml?branch=main&logo=githubactions&logoColor=white&label=CI)](https://github.com/fld-forge/governance/actions/workflows/ci.yml)
[![CodeQL](https://github.com/fld-forge/governance/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/fld-forge/governance/security/code-scanning)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/fld-forge/governance/badge)](https://scorecard.dev/viewer/?uri=github.com/fld-forge/governance)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/14182/badge)](https://www.bestpractices.dev/projects/14182)
[![Release](https://img.shields.io/github/v/release/fld-forge/governance?logo=github)](https://github.com/fld-forge/governance/releases)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue?logo=python&logoColor=white)](pyproject.toml)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Coverage](https://img.shields.io/badge/coverage-%E2%89%A590%25%20(branch)-brightgreen)](pyproject.toml)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](.pre-commit-config.yaml)
[![License](https://img.shields.io/github/license/fld-forge/governance)](LICENSE)

This repository governs GitHub **repository and organization settings** for the
`fld-forge` fleet from a single machine-readable baseline. Repositories outside
that organization are out of scope.

| File | Role |
| --- | --- |
| `src/governance_tools/baseline.json` | Machine-readable desired state: 26 controls (14 repository-scope, 12 organization-scope), each with its read endpoint, a jq projection, the desired value and the corrective API call; a control may carry per-repository `overrides` when one target's desired state legitimately differs (`.github` requires its own `CodeQL` and `validation` contexts instead of the complete Python-profile context set). Every desired value was frozen from a live, verified reference state rather than written from memory. It ships inside the package so an installed wheel can find it. |
| `scripts/bootstrap.py` | Applies the baseline to one repository, or to one organization with `--org`. Dry-run by default; `--apply` executes. Idempotent: re-running on a compliant target changes nothing and exits 0. |
| `scripts/audit.py` | Compliance matrix for `fld-forge` (`--all` = every non-archived repository plus the organization section). Exit 1 on any drift, error or skip. |
| `src/governance_tools/` | The package: `control` (the checked control value and its per-target overrides), `identifiers` (target validation), `baseline` (load and validate), `gh` (the only network IO), `compare` (pure comparison and the stricter guard), `controls` (per-control read/apply), `check` (per-control classification), `repository` (shared repository checks), `bootstrap`, `org` and `audit` (orchestration), `matrix` and `report` (rendering), `readme` (the generated README controls block), `scheduled_audit` (the scheduled-task wrapper; writes only its own log files). |

## Setup

```bash
uv sync --locked
uv run pre-commit install --install-hooks   # installs the framework hooks (.pre-commit-config.yaml)
```

Or `just setup`. Requirements: `gh` authenticated with the `repo` scope,
[uv](https://docs.astral.sh/uv/) and Python 3.12+ (uv downloads it
automatically via `.python-version`). A fleet audit costs roughly 3 seconds
per repository (a dozen API calls each).

## Usage

```bash
# See what a repo would need (no changes made):
uv run python scripts/bootstrap.py OWNER/REPO

# Apply the baseline to a repo:
uv run python scripts/bootstrap.py OWNER/REPO --apply

# Overwrite a ruleset the guard flagged as stricter than the baseline:
uv run python scripts/bootstrap.py OWNER/REPO --apply --force-normalize

# Audit the whole fleet (or specific repos):
uv run python scripts/audit.py --all
uv run python scripts/audit.py OWNER/REPO1 OWNER/REPO2

# See what an organization would need, and apply it:
uv run python scripts/bootstrap.py --org ORG
uv run python scripts/bootstrap.py --org ORG --apply
```

## Scopes

A control is keyed by a repository (the default) or by an organization. The two
groups never mix: loading validates that a control's endpoints carry the
placeholder its scope requires, so an organization control cannot aim at a
repository endpoint. `--all` renders the `fld-forge` repository matrix first,
then the `fld-forge` organization section; explicit `OWNER/REPO` arguments audit
exactly what was asked for.

Four organization controls are **manual** (`org-security-configuration`,
`org-member-privileges-manual`, `org-outside-collaborator-invitations`,
`org-two-factor-requirement`). The
REST API either accepts a write and silently keeps the old value, or needs a
multi-step operation this baseline deliberately does not automate. They are
audited like any other control and report `MANUAL` under `--apply`, with the
reason and the web-UI path, instead of claiming a correction that never landed.

## Quality gates

`uv run ruff check .`, `uv run ruff format --check .`,
`uv run ty check --error-on-warning src scripts tests`, `uv run mypy`,
`uv run deptry src` (the package must stay stdlib-only),
`uv run lint-imports` (the architectural seams) and `uv run pytest -q`
(90% branch-coverage floor). All seven run in the CI quality job and via
`just check`; the pre-commit framework
(`.pre-commit-config.yaml`) runs them at each commit, plus hygiene checks
and ruff autofix through its pinned mirror hooks. The
suite never touches the network: every test drives the real code through a
fake `gh` layer, so mutations are recorded and "no write without `--apply`"
is provable. Import Linter keeps `audit` and `bootstrap` independent and keeps
the desired-state loader from depending on the GitHub adapter. Ruff TID251
confines process and network APIs to `gh.py` and prevents production modules
from importing tests or command wrappers.

CI adds a locked install (`uv sync --locked`), gitleaks over the full git
history, Semgrep CE over `src` and `scripts`, both `uv audit --locked` and
pip-audit over the locked dependency graph, PR dependency review, zizmor and a
weekly scheduled run; CodeQL and OpenSSF Scorecard analyse the repository on
their own cadence.

## Project documents

| Document | Purpose |
| --- | --- |
| [`AGENTS.md`](AGENTS.md) | Operating manual for coding agents: blast radius, invariants, hard rules |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Setup, contribution flow, gates, commit conventions |
| [`GOVERNANCE.md`](GOVERNANCE.md) | Who decides, and what changing the baseline requires |
| [`SECURITY.md`](SECURITY.md) | Threat model, reporting, release-asset verification |
| [`NORTHSTAR.md`](NORTHSTAR.md) | Measured steering KPIs, one per axis |
| [`docs/adr/`](docs/adr/README.md) | Architecture decision records |
| [`docs/scheduled-audit.md`](docs/scheduled-audit.md) | The weekly drift audit: how it is scheduled, and what it gates |

## Controls

<!-- controls:begin - generated from src/governance_tools/baseline.json; regenerate with: uv run python scripts/render_readme.py --apply -->

### Repository controls (14)

- `ruleset-main-protection` - Default branch ruleset: PR required (0 approvals), force-push and deletion blocked, signed commits required, no bypass actors, and the CI quality gates (CodeQL, dependency-review, pip-audit, quality, secrets-scan, semgrep, uv-audit, zizmor) required to pass before merge with the branch up to date.
- `ruleset-release-tags` - Tag ruleset for refs/tags/v*: deletion, update and force-update blocked; creation stays allowed for release automation.
- `immutable-releases` - Published releases and their assets can no longer be modified or deleted.
- `codeql-default-setup` - CodeQL code scanning, GitHub-managed default setup, default query suite, weekly schedule.
- `dependabot-alerts` - Dependabot vulnerability alerts enabled.
- `dependabot-security-updates` - Dependabot security updates (automated security fixes) enabled.
- `secret-scanning` - GitHub secret scanning enabled.
- `secret-scanning-push-protection` - Secret scanning push protection enabled.
- `private-vulnerability-reporting` - Private vulnerability reporting enabled (the SECURITY.md reporting path).
- `actions-workflow-permissions` - Default GITHUB_TOKEN permissions read-only.
- `merge-methods-squash-only` - Squash is the only merge method.
- `delete-branch-on-merge` - Merged pull-request branches are deleted automatically, so a stale branch cannot be revived and re-merged later.
- `unused-collaboration-surfaces` - Wiki and projects disabled.
- `web-commit-signoff` - Commits authored through the GitHub web editor must carry a sign-off.

### Organization controls (12)

- `org-ruleset-floor-no-destruction` - Organization floor for every repository, present and future: force-push and deletion blocked on the default branch.
- `org-ruleset-floor-release-tags` - Organization floor for every repository: version tags cannot be deleted, moved or force-updated.
- `org-ruleset-mature-discipline` - Strict tier: repositories carrying the custom property tier=mature require a pull request (0 approvals, matching the single-maintainer model), signed commits, and squash as the only merge method.
- `org-custom-property-tier` - The tier custom property that the strict ruleset selects on.
- `org-security-configuration` - The fld-forge-baseline security configuration is the organization default for every new repository and is enforced, so a repository administrator cannot disable the features it controls. *(manual)*
- `org-actions-policy` - Actions must reference a full commit SHA, organization-wide.
- `org-actions-workflow-permissions` - Default GITHUB_TOKEN permissions read-only across the organization.
- `org-actions-retention` - Workflow artifacts and logs are kept 30 days, matching the retention-days the fleet's CI already declares on its uploads so one number governs both.
- `org-member-privileges` - Member privileges the REST API can both read and write: members cannot create repositories or teams, base permission on organization repositories is read, private forks are off, issue deletion is off, and web-editor commits carry a sign-off.
- `org-member-privileges-manual` - Member privileges the REST API reports but refuses to change: deleting repositories and changing repository visibility are always owner-only. *(manual)*
- `org-outside-collaborator-invitations` - Repository administrators cannot invite outside collaborators. *(manual)*
- `org-two-factor-requirement` - Two-factor authentication required for every member. *(manual)*

<!-- controls:end -->

Public-only controls (rulesets, CodeQL, secret scanning, push protection,
private vulnerability reporting) are skipped with `NA` on private repos:
a free personal plan only gets them on public repositories. Machine-local
commit-signing configuration is out of scope: it lives in a clone's
`.git/config`, not in the platform API this baseline governs.

Comparison is projection-based: only the fields the baseline governs are
compared (canonical JSON), so server-added defaults never produce false
drift.

### Desired state, not a minimum floor

The baseline describes the state a repository should be in, in both
directions: a setting that is *stricter* than the baseline is still drift,
and applying the baseline would lower it. Three things bound that blast
radius:

- **Rulesets are guarded.** Before overwriting an existing ruleset,
  `bootstrap.py` compares it to the baseline; extra rule types, a higher
  `required_approving_review_count`, extra review requirements, or a wider
  ref scope (protecting refs the baseline does not, or excluding fewer)
  are reported as `STRICTER-THAN-BASELINE` and the control is **skipped**
  (in dry-run *and* in `--apply`). Overwriting it is opt-in, via
  `--force-normalize`. If the check itself cannot run, the control renders
  `ERR` and is never normalized. The guard covers rulesets only: the other
  controls are boolean or enum enable flags whose baseline value is already
  the strict one.
- **Nothing is written without `--apply`.** Dry-run issues GET requests
  only; this is enforced by tests that assert no mutating call was made.
- **Ungoverned fields are preserved, never forced.** Where the API demands
  a field in the request body that the baseline deliberately does not
  govern, `apply_preserve` reads the live value and echoes it back
  unchanged. That is how `actions-workflow-permissions` governs only
  `default_workflow_permissions: read` (strictly security-positive) while
  leaving `can_approve_pull_request_reviews` exactly as it was: forcing it
  true would loosen GitHub's stricter default on every repo. Repositories
  running release-please need it `true` - set that per repo; the baseline
  never loosens it.
- **Dry-run is the default**, and prints the full desired-vs-live diff
  before anything is written.

Read failures are never silently treated as drift or as "disabled": a
failed read renders `ERR`, counts toward a non-zero exit, and never
triggers a corrective write.

## Drift detection for a single repository

Running `uv run python scripts/audit.py OWNER/REPO` verifies that one
repository's live platform settings still match the baseline. Run it after any
settings change, or on a schedule.

A repository whose check aborts (bad name, auth failure, transient API
error) is rendered as a row of `ERR` cells with its output printed under the
matrix - never dropped from the report. A fleet audit therefore cannot exit
0 with a repository unaudited or half-audited.

## Scheduled audit

The audit runs weekly from a **local scheduled task** (`governance-fleet-audit`,
Wednesdays at 09:00 local), which calls `scripts/weekly_audit.py`. It writes the
whole matrix to a timestamped log under `governance-audit/` and keeps the newest
twelve. Drift is a finding, not a failure: the wrapper succeeds whether the audit
reports clean or drifting, and fails only when the audit itself could not run.

`.github/workflows/fleet-audit.yml` is kept but **dormant**. It requires a
repository secret that does not exist and fails loudly without it, by design - an
audit that silently reported an empty fleet would read as a clean one. A
fine-grained token scoped read-only to `fld-forge` can enumerate the fixed fleet.
The re-create command, exit-code policy and credential guidance are in
[`docs/scheduled-audit.md`](docs/scheduled-audit.md).

## Org-migration note

This baseline is Step 1 of the multi-repo enforcement path. On a personal
account it is a continuously *audited* desired state, not platform-enforced:
repository settings can still drift between audits. Under a GitHub Team
organization, the same content becomes actual enforcement objects:
organization rulesets targeting all repos (the two ruleset controls),
a default/enforced security configuration (the security controls), and an
organization Actions policy (the workflow-permissions control). At migration
time, `uv run python scripts/audit.py --all` is the acceptance test that the
org objects reproduce this baseline.

## Permanent test bed

`governance-canary` (public scratch repo outside `fld-forge`) can exercise an
explicit bootstrap target without touching real repos; `--all` never includes
it. Keep it, or delete it and recreate it with `gh repo create governance-canary --public
--add-readme` (plus one committed Python file so CodeQL default setup has a
supported language) next time a live proof is needed.
