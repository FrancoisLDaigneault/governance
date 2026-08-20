# ADR-0012: Standalone Semgrep CE gate

- Status: accepted
- Date: 2026-08-20
- Amends: [ADR-0009](0009-required-status-checks-per-repository.md), [ADR-0011](0011-uv-native-dependency-audit.md)

## Context

CodeQL and Ruff security rules already provide broad static analysis, but a
Semgrep CE pass gives pull requests a separate pattern-based signal. The gate
must not require a Semgrep account, token, cloud service, SARIF upload, project
dependency, or deprecated GitHub Action wrapper.

Semgrep 1.173.0 supports the Python Registry configuration `p/python`. The CLI
version can be pinned, but that Registry alias is remote and mutable: rules can
change without a repository commit. This is an accepted availability and
reproducibility risk for the initial gate and must be reviewed if it produces
new findings unexpectedly.

## Decision

Run standalone Semgrep CE in a separate Ubuntu job named `semgrep`:

```text
uvx semgrep==1.173.0 scan --config p/python --metrics=off --error src scripts
```

The scan covers first-party production and script code while excluding tests
and synchronized third-party snapshots. `--metrics=off` disables Semgrep
metrics, and `--error` makes any finding fail the job. The job has only
`contents: read`, reuses the pinned checkout and setup-uv Actions, and adds no
cache, secret, token, SARIF upload, Semgrep Action, or project dependency.

The `main-protection` baseline requires six sorted contexts: `CodeQL`,
`quality`, `secrets-scan`, `semgrep`, `uv-audit`, and `zizmor`, with strict
status checks enabled. The `.github` repository override remains checks-free.

Activation follows ADR-0009: prove a clean local scan, merge the workflow only
after its pull-request check succeeds, observe `semgrep` on `main` and on open
release pull requests, then apply the reviewed baseline without force
normalization. Never require the context before every affected pull request
can produce it.

## Consequences

Semgrep adds a blocking network-dependent Registry scan without increasing the
project lock graph or local pre-commit latency. CodeQL and Ruff remain enabled;
the controls overlap by design but fail independently.

A Semgrep CLI update or Registry-caused finding requires explicit triage. Fix a
real issue or narrow a rule locally with review; do not add a global ignore to
make the gate green. If Registry drift becomes operationally noisy, replace the
remote alias with reviewed local rules in a later ADR.

Rollback preserves mergeability: restore and prove the five-context baseline
without `semgrep`, apply it live, and only then remove the workflow job. Release
pull requests remain open throughout activation and rollback.
