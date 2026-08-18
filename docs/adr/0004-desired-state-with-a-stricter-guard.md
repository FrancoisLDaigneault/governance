# ADR-0004: Desired state, not a minimum floor, with a stricter-than-baseline guard

- Status: accepted
- Date: 2026-08-18

## Context

A fleet baseline can mean two things: a *floor* (never weaken a repository, only
raise it) or a *desired state* (make every repository look like this). A floor
cannot detect a repository that is stricter than intended, and it silently
accumulates one-off configurations. A desired state can lower protections -
which is the dangerous half.

Two real incidents shaped this. An early baseline governed
`can_approve_pull_request_reviews` with the value the reference repository
happened to have (`true`), which is *looser* than GitHub's default: applying it
fleet-wide would have weakened repositories that did not need it. Separately, a
ruleset that protected more refs than the baseline was normalized down to the
default branch without any warning, because only rule *types* were compared.

## Decision

The baseline is desired state, and the blast radius is bounded explicitly:

- **The stricter guard.** Before overwriting a ruleset, the live object is
  compared to the baseline. Extra rule types, a higher approval count, extra
  review requirements, or a wider ref scope (protecting refs the baseline does
  not, or excluding fewer) are reported as `STRICTER-THAN-BASELINE` and the
  control is **skipped**, in dry-run and in `--apply` alike. `--force-normalize`
  is the only bypass. A guard that cannot run renders `ERR` and never
  normalizes.
- **No control may be looser than GitHub's default.** Where the API requires a
  field in the request body that the baseline deliberately does not govern,
  `apply_preserve` reads the live value and echoes it back unchanged.
- **Dry-run is the default**, and prints the full desired-vs-live diff.

## Consequences

`actions-workflow-permissions` governs only `default_workflow_permissions:
read` and carries `can_approve_pull_request_reviews` through untouched;
removing it from the governed set turned 7 fleet cells from "drift" into "not
our business", which is the correct reading - they were the baseline asking to
weaken security.

The guard covers rulesets only. The other controls are boolean or enum enable
flags whose baseline value is already the strict one, so there is nothing to
lower; if a future control breaks that property, it needs its own guard.
