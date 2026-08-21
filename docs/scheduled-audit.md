# The scheduled fleet audit

The audit runs weekly from two mechanisms that read the same baseline: a
**local scheduled task** on the maintainer's machine, and the **hosted
workflow** `.github/workflows/fleet-audit.yml`. The local task writes a log;
the hosted workflow publishes the matrix in its run summary and keeps a single
drift tracking issue in step with organization drift.

## The local scheduled task

| | |
| --- | --- |
| Task name | `governance-fleet-audit` |
| Schedule | Weekly, Wednesday 09:00 local time |
| Runs | `scripts/weekly_audit.py`, which runs the audit as `--all` in-process |
| Log | `C:\Users\franc\governance-audit\<yyyy-MM-dd_HHmmss>.log` |
| History | the newest 12 logs, about a quarter at a weekly cadence |

The hour is deliberate. The hosted workflow was scheduled for 07:00 UTC, which
is the middle of the night locally; a local task has to run when the machine is
plausibly on, so it moved into working hours.

### Re-creating it

The task is machine state, not a file, so it is not restored by cloning this
repository. After a machine rebuild, clone the repository and run:

```bat
schtasks /Create /TN "governance-fleet-audit" ^
  /TR "C:\Users\franc\.local\bin\uv.exe run --directory C:\Users\franc\governance python scripts/weekly_audit.py" ^
  /SC WEEKLY /D WED /ST 09:00 /F
```

The task command carries the absolute paths of `uv` and of the repository,
because a scheduled task inherits neither the user's `PATH` nor a useful
working directory. The wrapper itself hard-codes nothing: it derives the log
directory (a repository sibling named `governance-audit`) from its own
location, so only the `schtasks` command needs adjusting if `uv` or the
repository moves.

Prove it without waiting a week:

```bat
schtasks /Run /TN "governance-fleet-audit"
schtasks /Query /TN "governance-fleet-audit" /FO LIST /V
```

A healthy run leaves `Last Result: 0` and a new log file whose tail carries the
organization section, the drift total and the audit's own exit code.

### Drift is a finding, not a failure

The audit exits 1 when it finds drift. The wrapper reports success for both 0
(clean) and 1 (drift), and fails only for 2 and above - a usage error, or the
audit refusing to report a partial fleet.

Mapping drift to a failing task would be worse than useless here: the
organization carries four controls that only a human can clear, so the task would
sit permanently red, and a genuinely broken audit would be indistinguishable
from an ordinary drifting one. `Last Result` answers whether the audit **ran**;
the log answers what it **found**.

### What it does not do

- It runs only while the machine is on and the user session exists - the same
  limitation as the daily configuration backup task.
- It reports; it never corrects. Corrections stay a deliberate
  `bootstrap.py OWNER/REPO --apply`.
- The result stays local. There is no issue, no notification: reading the log is
  the interface.

## The hosted workflow

`.github/workflows/fleet-audit.yml` runs Wednesdays at 07:00 UTC and on demand
through **Actions -> Fleet audit -> Run workflow**. It authenticates with the
repository secret `GOVERNANCE_AUDIT_TOKEN` and fails with a named error when
that secret is missing. That failure is the design - an audit that silently
reports an empty fleet would read as a clean one.

Every run publishes the matrix to the run summary. Organization drift opens a
single tracking issue, rewritten by every run and closed automatically once the
organization is clean again; the run itself then fails so the Actions tab shows
red. A red hosted run therefore means either real drift to correct with
`bootstrap.py --apply`, or a credential problem named in the log - check with
`gh run list --workflow=fleet-audit.yml`.

### Credential scope

The fleet is fixed to `fld-forge`; enumeration does not call `/user` or
`/user/orgs`. A fine-grained personal access token scoped read-only to all
repositories in that organization can therefore run the audit without gaining
access to repositories under any other owner.

The workflow fails with a named error when the matrix carries no row for
`fld-forge`, so a missing or insufficient credential produces a red run rather
than a false all-clear.

### What the audit reads

The authoritative list is `read_endpoint` in
`src/governance_tools/baseline.json`. Whatever the credential, it only ever
needs to **read**: nothing in the audit path writes.

## Scope

The audit enumerates non-archived repositories owned by `fld-forge` and the
`fld-forge` organization controls. Repositories under every other owner are out
of scope and never appear in the matrix.
