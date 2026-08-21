# ADR-0016: Plan-aware outside collaborator control

- Status: accepted
- Date: 2026-08-20

## Context

GitHub reports three organization member privileges through `GET /orgs/{org}`.
Changing repository visibility and deleting repositories can be restricted on
all plans. Restricting repository administrators from inviting outside
collaborators is available only to Enterprise Cloud organizations. The
`fld-forge` organization is on the Team plan, so its unavoidable live value is
`true`.

Treating all three fields as one unconditional desired object left the fleet
permanently in drift even after every setting available on the current plan was
secured. Removing the invitation control would instead hide drift after a plan
upgrade.

GitHub documents the plan restriction at
<https://docs.github.com/en/organizations/managing-organization-settings/setting-permissions-for-adding-outside-collaborators>.

## Decision

Keep repository visibility changes and repository deletion disabled
unconditionally in their existing manual control. Audit outside-collaborator
invitations as a separate manual control whose desired value remains `false`.

When the desired value differs, evaluate a baseline-declared allowance against
the same organization endpoint. Accept `true` only when `.plan.name` is exactly
`free` or `team`, and report the plan limitation in the audit matrix. An
Enterprise plan, an unknown plan, a missing plan, or a failed probe does not
match the allowance and therefore cannot silently pass.

## Consequences

Team and Free organizations can be clean while the audit still states why the
weaker value is accepted. Visibility and deletion drift remain independent and
cannot be masked by the plan allowance. The audit performs one additional GET
only when the invitation value differs from the secure desired value.

The allowance mechanism is validated at baseline load time and applies only to
JSON controls. A failed or non-boolean allowance probe is an error, never an
acceptance.

## Reversibility

No migration or stored state is involved. Upgrading the organization plan to
Enterprise Cloud stops the exact `free`/`team` allowance from matching, which
re-arms the `false` requirement automatically. The owner can then disable
repository-admin invitations in the web UI; the control becomes compliant
without changing the baseline.
