#!/usr/bin/env bash
# Governance drift audit: compare repositories against governance/baseline.json.
#
# Usage: governance/audit.sh [--all | OWNER/REPO ...]
#
# --all enumerates every non-archived repository owned by the authenticated
# user. Each repository is checked with bootstrap.sh in dry-run mode; the
# result is a per-repo / per-control compliance matrix (OK / DRIFT / NA / ERR
# / STRICT). Exit 1 when any control drifts, errors or is skipped anywhere -
# this is the drift detector that closes the hand-maintained
# docs/repo-settings.md gap when run regularly.
#
# A repository whose check aborts or returns fewer controls than the baseline
# defines is rendered as an ERR row (never silently dropped) and its captured
# output is printed under the matrix, so the audit can never exit 0 with a
# repository unaudited or half-audited.
#
# Requirements: gh (authenticated, repo scope) and python 3 reachable as the
# command `python` (Git Bash on Windows is the supported environment).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REPOS=()
if [[ "${1:-}" == "--all" ]]; then
  OWNER=$(gh api user --jq .login)
  while IFS= read -r repo; do
    REPOS+=("$repo")
  done < <(gh repo list "$OWNER" --limit 200 \
    --json nameWithOwner,isArchived \
    --jq '.[] | select(.isArchived | not) | .nameWithOwner' | sort)
elif [[ $# -ge 1 ]]; then
  REPOS=("$@")
else
  echo "usage: $0 [--all | OWNER/REPO ...]" >&2
  exit 2
fi

# Every control the baseline defines: used to detect a half-audited repo.
ALL_CONTROLS=$(python -c '
import json, sys
with open(sys.argv[1], encoding="utf-8") as fh:
    print("\n".join(c["id"] for c in json.load(fh)["controls"]))
' "$SCRIPT_DIR/baseline.json" | tr -d '\r')
EXPECTED_COUNT=$(printf '%s\n' "$ALL_CONTROLS" | grep -c .)

RESULTS=""
ERROR_LOG=""
for repo in "${REPOS[@]}"; do
  echo "auditing $repo ..." >&2
  set +e
  OUTPUT=$("$SCRIPT_DIR/bootstrap.sh" "$repo" 2>&1)
  STATUS=$?
  set -e

  SEEN=""
  COUNT=0
  while IFS= read -r line; do
    if [[ "$line" == CTL\ * ]]; then
      RESULTS+="$repo ${line#CTL }"$'\n'
      SEEN+="${line#CTL }"$'\n'
      COUNT=$((COUNT + 1))
    fi
  done <<< "$OUTPUT"

  # An archived repo is read-only: bootstrap reports it and exits 0 without
  # emitting any control. That is a clean skip, not a half-audited repo.
  # (--all filters archived repos; this covers an explicitly named one.)
  if [[ "$STATUS" -eq 0 && "$COUNT" -eq 0 ]] \
    && grep -q ' is archived (read-only)' <<< "$OUTPUT"; then
    echo "skipping archived $repo" >&2
    continue
  fi

  # bootstrap exits 0 (clean) or 1 (drift/error/skip); anything else, or a
  # short control list, means the run aborted - surface it, never drop it.
  if [[ "$STATUS" -gt 1 || "$COUNT" -lt "$EXPECTED_COUNT" ]]; then
    while IFS= read -r control; do
      [[ -z "$control" ]] && continue
      grep -q "^$control " <<< "$SEEN" || RESULTS+="$repo $control ERR"$'\n'
    done <<< "$ALL_CONTROLS"
    ERROR_LOG+="--- $repo (exit $STATUS, $COUNT/$EXPECTED_COUNT controls) ---"$'\n'
    ERROR_LOG+="$(printf '%s\n' "$OUTPUT" | tail -5)"$'\n\n'
  fi
done

set +e
printf '%s' "$RESULTS" | python -c '
import sys

rows: dict[str, dict[str, str]] = {}
controls: list[str] = []
for line in sys.stdin:
    parts = line.split()
    if len(parts) != 3:
        continue
    repo, control, status = parts
    rows.setdefault(repo, {})[control] = status
    if control not in controls:
        controls.append(control)

if not rows:
    print("no results collected")
    sys.exit(2)

codes = {c: f"C{i + 1}" for i, c in enumerate(controls)}
mark = {"OK": "OK", "DRIFT": "DRIFT", "NA": "-",
        "STRICTER-THAN-BASELINE": "STRICT"}
repo_w = max(len(r) for r in rows)
col_w = max(6, *(len(codes[c]) for c in controls))

print("legend: " + ", ".join(f"{codes[c]}={c}" for c in controls))
print("cells: OK = compliant, DRIFT = differs from baseline, - = not applicable,")
print("       ERR = could not be checked, STRICT = live is stricter (skipped)")
print()
header = "repo".ljust(repo_w) + "  " + "  ".join(codes[c].ljust(col_w) for c in controls)
print(header)
print("-" * len(header))
drift = 0
bad = 0
for repo in sorted(rows):
    cells = []
    for c in controls:
        status = rows[repo].get(c, "?")
        drift += status == "DRIFT"
        bad += status not in ("OK", "DRIFT", "NA")
        cells.append(mark.get(status, status).ljust(col_w))
    print(repo.ljust(repo_w) + "  " + "  ".join(cells))
print()
print(f"total drift cells: {drift}")
if bad:
    print(f"total unchecked/skipped cells: {bad}")
sys.exit(1 if drift or bad else 0)
'
AUDIT_STATUS=$?
set -e

if [[ -n "$ERROR_LOG" ]]; then
  echo
  echo "== repositories that could not be fully audited =="
  printf '%s' "$ERROR_LOG"
fi

exit "$AUDIT_STATUS"
