# The scheduled fleet audit

The audit runs weekly from a **local scheduled task**. The GitHub-hosted
workflow is kept, but dormant: it needs a credential that cannot be created
without a browser. The required scope is recorded below so the choice can be
revisited without being re-derived.

## The mechanism in use: a local scheduled task

| | |
| --- | --- |
| Task name | `governance-fleet-audit` |
| Schedule | Weekly, Wednesday 09:00 local time |
| Runs | `scripts/weekly-audit.ps1`, which calls `scripts/audit.py --all` |
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
  /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\Users\franc\governance\scripts\weekly-audit.ps1" ^
  /SC WEEKLY /D WED /ST 09:00 /F
```

The wrapper resolves `uv`, the repository and the log directory as absolute
paths, because a scheduled task inherits neither the user's `PATH` nor a useful
working directory. Those paths are this machine's layout; adjust them in
`scripts/weekly-audit.ps1` if the repository or `uv` moves.

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
organization carries two controls that only a human can clear, so the task would
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

## The dormant hosted workflow

`.github/workflows/fleet-audit.yml` is still in the repository, scheduled for
Wednesdays at 07:00 UTC and available through **Actions -> Fleet audit -> Run
workflow**. It is **not active**: it requires a repository secret named
`GOVERNANCE_AUDIT_TOKEN`, that secret does not exist, and the workflow fails
with a named error when it is missing. That failure is the design - an audit
that silently reports an empty fleet would read as a clean one.

It stays for the day cloud visibility is wanted: a run summary containing the
matrix, and a single tracking issue kept in step with organization drift.

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
