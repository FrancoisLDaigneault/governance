# ADR-0010: alignment on the fleet repository standard

- Status: accepted
- Date: 2026-08-19

## Context

pi-config, the fleet's reference repository, hardened its tooling first:
deptry guards the stdlib-only invariant, ruff's S rules (the flake8-bandit
port) cover the security-lint surface, the release job exports a CycloneDX
SBOM from `uv.lock` and removes the stray `dist/.gitignore` that `uv build`
creates before attesting `dist/*` (this repository's v0.7.0 attestation
carries that stray subject), and the uv binary is pinned in every setup-uv
step. The fleet standard says the mature repositories converge on the same
gates rather than each negotiating its own.

## Decision

Adopt the same standard here: deptry as a fifth quality command (dev
dependency, CI step, local pre-commit hook - amending the hook set of
ADR-0008), ruff `S` rules with `S101` exempted for tests only, MIT license
metadata with a bounded hatchling, uv pinned to the same version in all five
setup-uv steps, a CI concurrency group, and the release flow of pi-config:
clean `dist/`, export the CycloneDX SBOM alongside the SPDX one, then
checksum, attest and upload everything.

## Consequences

The quality gate count is five everywhere it is documented; the drift gate
(`tests/unit/test_docs.py`) enforces the wording. A single `# noqa: S603`
marks the one deliberate subprocess call in `gh.py`, the repository's IO
boundary. Release assets gain `sbom.cdx.json`, and attestation subjects are
exactly the published artifacts. Bumping uv now means updating the setup-uv
`version:` pins together with the uv-pre-commit `rev:`.
