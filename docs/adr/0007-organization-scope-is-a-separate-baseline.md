# 7. Organization scope is a separate baseline, not a control kind

Status: accepted
Date: 2026-08-18

## Context

The baseline governs repository settings, keyed by `OWNER/REPO`: every control
carries a `read_endpoint` containing a `{repo}` placeholder, `bootstrap.py`
takes one repository, and `audit.py` renders a repository-by-control matrix.

Organization state is now a material part of the fleet's posture, and none of it
is audited:

| Organization setting | Live value |
| --- | --- |
| `floor-no-destruction` ruleset (`~ALL`, default branch) | active |
| `floor-release-tags` ruleset (`~ALL`, `refs/tags/v*`) | active |
| `mature-discipline` ruleset (`tier=mature`) | active |
| `tier` custom-property schema | single-select, required, default `sandbox` |
| `fld-forge-baseline` security configuration | default for all new repos, enforced |
| Actions `sha_pinning_required` | true |
| Actions `default_workflow_permissions` | read |
| Artifact and log retention | 30 days |
| `members_can_create_repositories` / `_teams` | false |
| `web_commit_signoff_required` | true |
| Two-factor requirement | false (owner enables it in the web UI) |

Anything not in a baseline is a one-time setting that rots unnoticed, which is
precisely what this tool exists to prevent. Three options were considered.

**(a) A separate `org-baseline.json` and an `audit-org.py` entry point.**
Cleanly separated, but duplicates the loader, the comparison and the reporting
for a second document, and gives the operator two commands to remember.

**(b) A `scope` field in the existing baseline** distinguishing `repo` from
`org`, with `audit.py` running the organization controls once per organization
it already enumerates. Fewest moving parts at the end state, and one command.

**(c) Out of scope for now, with the design recorded.**

## Decision

**(c) for this change: repository-level controls only. (b) is the recorded
target for the follow-up.**

The reason is not budget alone, it is that (b) has an unresolved design question
that deserves its own change rather than being improvised inside another one:
**the matrix has no shape for an organization row.** `render_matrix` prints
repositories down the side and controls across the top, and every cell is one
repository-control pair. Organization controls share no columns with repository
controls, so they would need either a second table, a pseudo-row whose cells
mean something different from every other row, or a reworked renderer. Choosing
badly there would make the audit output harder to trust, which costs more than
the delay.

The follow-up should:

1. add `"scope": "repo" | "org"` to each control, defaulting to `repo` so the
   existing file stays valid;
2. teach `load_controls` to split the two groups;
3. give the organization group its own endpoint template (`orgs/{org}`), its own
   applicability rule (plan-gated rather than visibility-gated), and its own
   section in the audit output rather than a row in the repository matrix;
4. reuse `read_live`, `canon` and the comparison unchanged — they are already
   keyed on an endpoint template and a projection, not on the notion of a
   repository.

Two organization settings are known to be unwritable through the REST API
(`two_factor_requirement_enabled`, and three of the member-privilege flags): the
API accepts the `PATCH` and silently keeps the old value. Those must be audited
as read-only observations that report drift and never claim to correct it,
otherwise the tool would report a successful apply that changed nothing.

## Update, 2026-08-18: the follow-up landed

Option (b) is implemented and the gap below is closed. Every row of the table
above is now a control in `baseline.json` with `"scope": "org"`. Two details
turned out to matter more than expected once written:

- Loading validates that a control's endpoints carry the placeholder its scope
  requires (`{repo}` or `{org}`, never both). Substituting a target into a
  template is the one place a scope confusion would aim a corrective write at
  the wrong endpoint, so it is checked when the baseline is read, not later.
- The unwritable settings became `manual_reason` controls rather than being
  left out. They audit like any other control and render `MANUAL` under
  `--apply`, which turns three lines of a hand-kept checklist into an audited
  item that keeps reporting until someone actually clears it.

The matrix question that justified deferring is answered: organization controls
render as their own section under the repository matrix, through the same
renderer with a different label, so no cell ever means two different things.

## Consequences

- Organization state stayed unaudited until the follow-up landed. This was a
  known, written gap rather than an assumption that someone would remember; the
  table above was the checklist that follow-up had to cover.
- The repository baseline keeps a single meaning: every control is a repository
  setting, and every `{repo}` template resolves. No control needs a conditional
  endpoint shape.
- `docs/org-settings.md` in the organization's `.github` repository remains the
  hand-maintained inventory of organization state in the meantime, with the same
  drift risk any hand-maintained inventory carries.
