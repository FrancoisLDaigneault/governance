# ADR-0011: uv-native dependency audit

- Status: accepted
- Date: 2026-08-20
- Amends: [ADR-0009](0009-required-status-checks-per-repository.md)

## Context

The CI dependency audit exported `uv.lock` to a temporary requirements file
and passed that projection to a separately installed scanner. The export adds
an intermediate representation and a second audit executable even though uv
0.11.19 can audit the locked dependency graph directly against OSV.

`uv audit` is experimental in uv 0.11.19. Its interface may change without a
major-version transition, so adopting it without a pinned uv release would
make the required check unpredictable. A plain frozen audit also accepts a
lockfile that is stale relative to `pyproject.toml`, which is inappropriate for
a blocking supply-chain check.

## Decision

Replace the active dependency scanner with the uv-native command:

```text
uv audit --locked
```

The GitHub Actions job and required context are named `uv-audit`. The existing
`astral-sh/setup-uv` action and uv `0.11.19` pins stay unchanged. `--locked`
refuses to update `uv.lock` and fails if the lockfile needs to change, so the
scan cannot silently audit a stale or regenerated graph. No audit package is
added to the project dependencies or lockfile.

The `main-protection` baseline continues to require exactly five sorted
contexts: `CodeQL`, `quality`, `secrets-scan`, `uv-audit`, and `zizmor`, with
strict status checks enabled. The `.github` repository override remains
checks-free.

Activation follows the safe order from ADR-0009: merge the workflow, observe a
successful `uv-audit` check on the pull request and `main`, then run
`bootstrap.py OWNER/REPO --apply` without force normalization and confirm the
result with the fleet audit. At decision time the live repository rulesets had
no required-status-check rule, so no compatibility context is needed.

## Consequences

CI removes the export step and the separately resolved scanner environment.
The audit now reads the same lockfile used by installation and release SBOM
generation. It still requires OSV network availability, and changes to the
experimental command must arrive through a reviewed uv pin update.

Rollback uses the same no-gap order in reverse: restore the previous scanner
job and prove its context green, change and apply the baseline required
context, then remove `uv-audit`. Never require a context before its workflow
has produced a successful check.
