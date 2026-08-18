# The scheduled fleet audit

`.github/workflows/fleet-audit.yml` runs `scripts/audit.py --all` every
Wednesday at 07:00 UTC, and on demand through **Actions -> Fleet audit -> Run
workflow**. It publishes the matrix to the run summary every time, and keeps a
single tracking issue in step with organization drift: opened or rewritten when
the organization drifts, closed by the workflow once it is clean again.

## Why it needs its own token

A workflow's `GITHUB_TOKEN` is scoped to the repository that runs it. The audit
reads *other* repositories' settings and the organization's own state, so that
token cannot do the job: it would produce an empty fleet, which is worse than no
audit at all because an empty fleet reads as a clean one.

The workflow therefore requires a repository secret named
**`GOVERNANCE_AUDIT_TOKEN`**, and fails with a named error when it is missing.
The token is **read-only**: nothing in this workflow corrects drift, it only
reports it. Corrections stay a deliberate `bootstrap.py ... --apply` run.

## Creating the token

Create it at **Settings -> Developer settings -> Personal access tokens**.

A **fine-grained** token is the least-privilege choice. Set the resource owner
to the organization, grant it **all repositories**, and give it read-only:

| Scope | Permission | What it is read for |
| --- | --- | --- |
| Repository | Metadata: Read | repository enumeration, visibility, archived flag |
| Repository | Administration: Read | rulesets, immutable releases, merge methods, branch cleanup, wiki/projects, web sign-off, Actions workflow permissions, private vulnerability reporting |
| Repository | Code scanning alerts: Read | CodeQL default-setup state |
| Repository | Secret scanning alerts: Read | secret scanning and push protection state |
| Repository | Dependabot alerts: Read | Dependabot alerts and security updates state |
| Organization | Administration: Read | organization rulesets, Actions policy and retention, member privileges, two-factor requirement, security configuration defaults |
| Organization | Custom properties: Read | the `tier` property schema |

The authoritative list of what is read is `read_endpoint` in
`src/governance_tools/baseline.json`; the table above maps those endpoints onto
permission names, and permission names are the part GitHub renames from time to
time.

**One call decides whether this works at all.** The fleet enumeration asks
`GET /user/orgs` for the organizations to audit. If the token cannot answer it,
the audit sees only personal repositories, the organization section disappears,
and the whole in-scope posture would silently read as clean. The workflow
refuses that outcome: it fails with a named error when the matrix carries no row
for the organization. If that error appears, use a **classic** token with the
`repo` and `read:org` scopes instead, which answers `/user/orgs` reliably.

Recommended expiry: **90 days**. Longer trades away the one thing a read-only
token still costs you if it leaks - a bounded lifetime - and the renewal is a
two-minute job the failing workflow will remind you about.

## Verifying it before you trust it

Store the token as the repository secret `GOVERNANCE_AUDIT_TOKEN`, then run the
workflow by hand (**Run workflow**) rather than waiting a week. A good run:

- publishes a matrix that contains a row for every organization repository and
  an `== organization controls ==` section;
- either reports `organization clean`, or opens the tracking issue.

To check the token from a shell before storing it:

```bash
GH_TOKEN=<token> gh api user/orgs --jq '.[].login'   # must list the organization
GH_TOKEN=<token> uv run python scripts/audit.py --all
```

## In scope versus informational

The audit enumerates every repository the token can see, including personal
ones. That is deliberate honest reporting, but only the organization is
governed: rows beginning with the organization login, plus the organization
section, decide whether the run fails and whether the tracking issue opens.
Repositories under any other owner appear in the matrix and are never acted on.

The workflow derives the organization from `github.repository_owner`, so nothing
here is hardcoded to one name.
