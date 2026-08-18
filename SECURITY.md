# Security Policy

## Supported versions

Only the latest [GitHub release](https://github.com/FrancoisLDaigneault/governance/releases)
is supported. `main` is the development branch; fixes land there first and ship
with the next release.

## Reporting a vulnerability

Do not open a public issue. Use GitHub's private reporting:
**Security** tab -> **Report a vulnerability**
([GitHub Security Advisories](https://github.com/FrancoisLDaigneault/governance/security/advisories/new)).

You will receive an initial response within 7 business days.

## Threat model of this tool

This tool holds credentials that can change repository settings across a whole
fleet, so its blast radius is wider than its size suggests. Three properties
bound it, each enforced by tests rather than by convention:

- **Dry-run is the default.** `--apply` is required for any mutation; the test
  suite asserts that no mutating call is issued without it.
- **Repository names are shape-checked** before they reach an API path
  template, so a crafted name cannot redirect a write to another endpoint.
- **A failed read is never treated as drift** and never falls through to a
  corrective write; it renders `ERR` and fails the run.

The tool never stores a token: it shells out to `gh`, which owns the
credential. Grant it the narrowest scopes that still let it read and set the
governed settings.

## Automated controls

Every PR and every push to `main` (plus a weekly scheduled run) is scanned by
gitleaks (full git history), pip-audit and zizmor; weekly CodeQL analysis,
GitHub secret scanning with push protection, and weekly Dependabot updates run
on top.

## Verifying release assets

Each release ships the wheel, the sdist, an SPDX SBOM (`sbom.spdx.json`),
SHA-256 checksums (`SHA256SUMS`) and GitHub build-provenance attestations.
To verify a downloaded asset:

```bash
gh attestation verify governance_tools-<version>-py3-none-any.whl \
  --repo FrancoisLDaigneault/governance
sha256sum --check SHA256SUMS   # inside the folder holding the downloaded assets
```
