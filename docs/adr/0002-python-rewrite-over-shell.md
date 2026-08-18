# ADR-0002: Python rewrite of the shell reference implementation

- Status: accepted
- Date: 2026-08-18

## Context

The first implementation was two bash scripts (~380 lines). They worked and
were proven by hand on a canary repository, but they had **zero automated
tests**: the ten controls, the stricter-than-baseline guard, the preserve
merge, the read-error and 404 handling and the exit codes were all verified by
running them once and reading the output. A review flagged this as the
remaining gap for privileged, fleet-mutating code.

Shell also made the failure modes coarse: string comparison depended on
stripping carriage returns, and error handling rested on `set -euo pipefail`
plus careful assignment forms.

## Decision

Rewrite in Python 3.12 with the standard project shape used across the fleet
(uv, src layout, ruff, mypy --strict, pytest with a branch-coverage floor). Keep
`baseline.json` unchanged: the control semantics are the asset, the language is
not.

## Consequences

Tests went from 0 to 133, at 99.51% branch coverage, all driving the real code
through a fake `gh` layer - so "no write without `--apply`" is asserted rather
than assumed. Byte-identical output against the shell was verified across eight
live repositories before the scripts were deleted.

The rewrite also fixed a defect in the reference: `bootstrap.sh` emitted LF
while `audit.sh` emitted CRLF (its matrix came from an embedded Python
one-liner). The `CTL` lines are a machine-readable contract, so the port emits
LF everywhere.

One property was given up deliberately: the shell ran a subprocess per
repository, which isolated a malformed response to one row. The in-process
rewrite had to earn that back explicitly - see the read-path handling in
ADR-0003 - and a fleet test now proves one bad repository costs one cell, not
the run.
