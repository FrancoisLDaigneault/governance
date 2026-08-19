"""Organization-scope orchestration: the same control machinery, keyed by org.

Organization state is the half of the posture no repository can report on: the
rulesets that cover every repository present and future, the property the strict
tier selects on, the security configuration new repositories inherit. Anything
not audited here is a one-time setting that rots unnoticed.
"""

import sys

from governance_tools.check import check_control
from governance_tools.control import Control
from governance_tools.gh import GhClient, api_get
from governance_tools.report import Mode, OrgReport, statuses_for


def org_facts(client: GhClient, org: str) -> str:
    """Empty string when the organization reads back; the error line otherwise."""
    result = api_get(client, f"orgs/{org}", ".login")
    return "" if result.ok else result.first_error_line()


def check_org(
    client: GhClient, controls: list[Control], org: str, mode: Mode | None = None
) -> OrgReport:
    """Check every organization control of one organization."""
    run = mode or Mode()
    error = org_facts(client, org)
    if error:
        return OrgReport(org, error=error)
    # Organization controls are plan-gated rather than visibility-gated, and
    # loading enforces applicability "all" on them, so the visibility argument
    # never excludes one.
    results = [check_control(client, c, org, "", run) for c in controls]
    return OrgReport(org, results=results)


def audit_orgs(
    client: GhClient, controls: list[Control], orgs: list[str]
) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Check every organization; returns the matrix rows and the error log."""
    rows: dict[str, dict[str, str]] = {}
    errors: list[str] = []
    control_ids = [control.id for control in controls]
    for org in orgs:
        print(f"auditing organization {org} ...", file=sys.stderr)
        report = check_org(client, controls, org)
        rows[org] = statuses_for(report.results, control_ids)
        checked = len(report.results)
        if report.error or checked < len(controls):
            errors.append(f"--- {org} ({checked}/{len(controls)} controls) ---")
            errors.append(report.error or "run did not report every control")
    return rows, errors
