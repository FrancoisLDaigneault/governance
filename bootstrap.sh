#!/usr/bin/env bash
# Apply the governance baseline (governance/baseline.json) to one repository.
#
# Usage: governance/bootstrap.sh OWNER/REPO [--apply] [--force-normalize]
#
# Dry-run by default: prints one status line per control (OK / DRIFT / NA /
# ERR) plus the desired-vs-live diff for every drift, and exits 1 if any
# control drifts or errors. With --apply, corrective API calls are executed
# and each control is re-checked afterwards (APPLIED / FAIL). Re-running on a
# compliant repo makes zero changes and exits 0 (idempotent).
#
# This is DESIRED STATE, not a minimum floor: any difference from the baseline
# is drift in both directions, so applying it can lower a setting that was
# stricter locally. Rulesets are guarded against exactly that: a live ruleset
# carrying extra rule types, stricter review requirements, or a wider ref
# scope (more protected refs, or fewer exclusions) is reported
# STRICTER-THAN-BASELINE and skipped unless --force-normalize is passed. The
# guard covers rulesets only - the other controls are boolean or enum enable
# flags whose baseline value is already the strict one.
# Fields the baseline deliberately does not govern are never forced - where
# the API requires them in the request body they are read live and echoed back
# unchanged (see apply_preserve in baseline.json).
#
# Requirements: gh (authenticated, repo scope) and python 3 reachable as the
# command `python` (Git Bash on Windows is the supported environment).
# Machine-readable output: lines starting with "CTL " (used by audit.sh).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASELINE="$SCRIPT_DIR/baseline.json"

REPO="${1:-}"
[[ -z "$REPO" || "$REPO" == --* ]] && {
  echo "usage: $0 OWNER/REPO [--apply] [--force-normalize]" >&2
  exit 2
}
APPLY=false
FORCE_NORMALIZE=false
shift
for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=true ;;
    --force-normalize) FORCE_NORMALIZE=true ;;
    *)
      echo "unknown argument: $arg" >&2
      echo "usage: $0 OWNER/REPO [--apply] [--force-normalize]" >&2
      exit 2
      ;;
  esac
done

# Canonical JSON (sorted keys, compact) so projections compare as strings.
# tr strips the CR that Python text-mode stdout emits on Windows.
canon() {
  python -c 'import json,sys
raw = sys.stdin.read().strip()
print(json.dumps(json.loads(raw) if raw else None, sort_keys=True, separators=(",", ":")))' \
    | tr -d '\r'
}

# Print the manifest of one control, one field per line (fields never contain
# newlines: projections are single-line jq filters, payloads compact JSON).
manifest() {
  CID="$1" python -c '
import json, os, sys
cid = os.environ["CID"]
with open(sys.argv[1], encoding="utf-8") as fh:
    controls = json.load(fh)["controls"]
c = next(c for c in controls if c["id"] == cid)
dump = lambda v: json.dumps(v, sort_keys=True, separators=(",", ":"))
print(c["kind"])
print(c["applicability"])
print(c.get("read_endpoint", "-"))
print(c.get("projection", "-"))
print(c.get("ruleset_name", "-"))
print(c["apply_method"])
print(c["apply_endpoint"])
print(dump(c["apply_payload"]) if "apply_payload" in c else "-")
print(dump(c["desired"]))
print(c.get("apply_preserve", "-"))
' "$BASELINE" | tr -d '\r'
}

control_ids() {
  python -c '
import json, sys
with open(sys.argv[1], encoding="utf-8") as fh:
    print("\n".join(c["id"] for c in json.load(fh)["controls"]))
' "$BASELINE" | tr -d '\r'
}

# Read the live projected state of a control. Sets LIVE (canonical JSON) and,
# for rulesets, RULESET_ID (empty when the ruleset does not exist yet).
# A failed read sets READ_ERR instead: a read error is an error, never drift,
# and never falls through to a corrective write.
read_live() {
  LIVE=""
  RULESET_ID=""
  READ_ERR=""
  local out
  case "$KIND" in
    ruleset)
      # includes_parents=false: after the org migration a parent ruleset could
      # otherwise match by name and the repo-level follow-up call would 404.
      if ! out=$(gh api "${READ_EP/\{repo\}/$REPO}?includes_parents=false" \
        --jq "[.[] | select(.name==\"$RS_NAME\")][0].id // empty" 2>&1); then
        READ_ERR=$(echo "$out" | head -1)
        return 0
      fi
      RULESET_ID="$out"
      if [[ -z "$RULESET_ID" ]]; then
        LIVE='"absent"'
      elif ! out=$(gh api "repos/$REPO/rulesets/$RULESET_ID" --jq "$PROJECTION" 2>&1); then
        READ_ERR=$(echo "$out" | head -1)
      else
        LIVE=$(printf '%s' "$out" | canon)
      fi
      ;;
    status204)
      # 204 = enabled, 404 = disabled; anything else (401/403/5xx) is a read
      # error and must not be mistaken for "disabled".
      if out=$(gh api "${READ_EP/\{repo\}/$REPO}" 2>&1); then
        LIVE='{"enabled":true}'
      elif grep -q 'HTTP 404' <<< "$out"; then
        LIVE='{"enabled":false}'
      else
        READ_ERR=$(echo "$out" | head -1)
      fi
      ;;
    json)
      if ! out=$(gh api "${READ_EP/\{repo\}/$REPO}" --jq "$PROJECTION" 2>&1); then
        READ_ERR=$(echo "$out" | head -1)
        return 0
      fi
      LIVE=$(printf '%s' "$out" | canon)
      ;;
  esac
}

# Rule types, review parameters or ref scope that exist live but are stricter
# than the baseline asks for. Prints one "- ..." line per extra; empty output
# means the live ruleset is not stricter. Only called for an existing ruleset
# that drifts. A non-zero exit means the check itself failed (never "clean").
stricter_extras() {
  gh api "repos/$REPO/rulesets/$RULESET_ID" 2>/dev/null \
    | DESIRED_JSON="$DESIRED" python -c '
import json, os, sys
try:
    live = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
desired = json.loads(os.environ["DESIRED_JSON"])
extras = []
live_types = {r["type"] for r in live.get("rules", [])}
for t in sorted(live_types - set(desired.get("rule_types", []))):
    extras.append(f"- extra rule type: {t}")
# Ref scope: protecting more refs (or excluding fewer) is stricter, and
# normalizing would silently narrow that protection.
live_ref = live.get("conditions", {}).get("ref_name", {})
want_ref = desired.get("conditions", {}).get("ref_name", {})
for ref in sorted(set(live_ref.get("include", [])) - set(want_ref.get("include", []))):
    extras.append(f"- extra protected ref: {ref}")
for ref in sorted(set(want_ref.get("exclude", [])) - set(live_ref.get("exclude", []))):
    extras.append(f"- ref excluded by baseline but protected live: {ref}")
live_pr = next((r.get("parameters", {}) for r in live.get("rules", [])
                if r["type"] == "pull_request"), None)
wanted_pr = desired.get("pr")
if live_pr and wanted_pr:
    live_n = live_pr.get("required_approving_review_count", 0)
    want_n = wanted_pr.get("required_approving_review_count", 0)
    if live_n > want_n:
        extras.append(
            f"- required_approving_review_count: live {live_n} > baseline {want_n}")
    for flag in ("dismiss_stale_reviews_on_push", "require_code_owner_review",
                 "require_last_push_approval", "required_review_thread_resolution"):
        if live_pr.get(flag) and not wanted_pr.get(flag):
            extras.append(f"- {flag}: enabled live, not required by baseline")
print("\n".join(extras))
' | tr -d '\r'
}

# Run the corrective call for a control (assumes read_live ran before).
apply_control() {
  local method="$METHOD" endpoint="${APPLY_EP/\{repo\}/$REPO}" body="$PAYLOAD" keep
  if [[ "$KIND" == "ruleset" && -n "$RULESET_ID" ]]; then
    method="PUT"
    endpoint="repos/$REPO/rulesets/$RULESET_ID"
  fi
  # Fields the API requires in the body but the baseline does not govern:
  # read them live and echo them back unchanged instead of forcing a value.
  if [[ "$PRESERVE" != "-" && "$body" != "-" ]]; then
    # The preserved value must provably come from a successful read: a failed,
    # empty or null read refuses the write rather than sending a partial body
    # to a privileged endpoint.
    if ! keep=$(gh api "${READ_EP/\{repo\}/$REPO}" --jq "$PRESERVE") \
      || [[ -z "$keep" || "$keep" == *null* ]]; then
      echo "preserve read failed or empty ($PRESERVE); refusing to write" >&2
      return 1
    fi
    body=$(BODY="$body" KEEP="$keep" python -c '
import json, os
merged = dict(json.loads(os.environ["KEEP"]))
merged.update(json.loads(os.environ["BODY"]))
print(json.dumps(merged, sort_keys=True, separators=(",", ":")))' | tr -d '\r')
  fi
  if [[ "$body" == "-" ]]; then
    gh api -X "$method" "$endpoint" >/dev/null
  else
    printf '%s' "$body" | gh api -X "$method" "$endpoint" --input - >/dev/null
  fi
}

VISIBILITY=$(gh repo view "$REPO" --json visibility --jq '.visibility | ascii_downcase')
IS_ARCHIVED=$(gh repo view "$REPO" --json isArchived --jq '.isArchived')
if [[ "$IS_ARCHIVED" == "true" ]]; then
  echo "WARN: $REPO is archived (read-only) - nothing to do"
  exit 0
fi

MODE="dry-run"
$APPLY && MODE="apply"
echo "== governance bootstrap: $REPO (visibility: $VISIBILITY, mode: $MODE) =="

DRIFT_COUNT=0
FAIL_COUNT=0
ERROR_COUNT=0
SKIP_COUNT=0
for CID in $(control_ids); do
  {
    read -r KIND
    read -r APPLICABILITY
    read -r READ_EP
    read -r PROJECTION
    read -r RS_NAME
    read -r METHOD
    read -r APPLY_EP
    read -r PAYLOAD
    read -r DESIRED
    read -r PRESERVE
  } < <(manifest "$CID")

  if [[ "$APPLICABILITY" == "public" && "$VISIBILITY" != "public" ]]; then
    echo "CTL $CID NA"
    echo "     skipped: public-only control on a $VISIBILITY repo (needs a paid plan)"
    continue
  fi

  read_live
  if [[ -n "$READ_ERR" ]]; then
    echo "CTL $CID ERR"
    echo "     read failed: $READ_ERR"
    ERROR_COUNT=$((ERROR_COUNT + 1))
    continue
  fi

  if [[ "$LIVE" == "$DESIRED" ]]; then
    echo "CTL $CID OK"
    continue
  fi

  # Desired-state normalization would lower a stricter live ruleset: refuse
  # unless the operator explicitly asks for it.
  if [[ "$KIND" == "ruleset" && -n "$RULESET_ID" ]] && ! $FORCE_NORMALIZE; then
    # A failed check must never read as "not stricter": refuse to normalize.
    if ! EXTRAS=$(stricter_extras); then
      echo "CTL $CID ERR"
      echo "     stricter-than-baseline check failed; refusing to normalize"
      ERROR_COUNT=$((ERROR_COUNT + 1))
      continue
    fi
    if [[ -n "$EXTRAS" ]]; then
      echo "CTL $CID STRICTER-THAN-BASELINE"
      echo "     live ruleset is stricter than the baseline; skipped"
      while IFS= read -r extra; do
        echo "     $extra"
      done <<< "$EXTRAS"
      echo "     re-run with --force-normalize to overwrite it with the baseline"
      SKIP_COUNT=$((SKIP_COUNT + 1))
      continue
    fi
  fi

  if ! $APPLY; then
    echo "CTL $CID DRIFT"
    echo "     desired: $DESIRED"
    echo "     live:    $LIVE"
    DRIFT_COUNT=$((DRIFT_COUNT + 1))
    continue
  fi

  if ERR=$(apply_control 2>&1); then
    read_live
    if [[ -n "$READ_ERR" ]]; then
      echo "CTL $CID ERR"
      echo "     applied, but the re-check read failed: $READ_ERR"
      ERROR_COUNT=$((ERROR_COUNT + 1))
    elif [[ "$LIVE" == "$DESIRED" ]]; then
      echo "CTL $CID APPLIED"
    else
      echo "CTL $CID FAIL"
      echo "     applied but live state still differs"
      echo "     desired: $DESIRED"
      echo "     live:    $LIVE"
      FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
  else
    echo "CTL $CID FAIL"
    echo "     apply error: $(echo "$ERR" | head -2 | tr '\n' ' ')"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
done

SUMMARY_SUFFIX=""
[[ "$ERROR_COUNT" -gt 0 ]] && SUMMARY_SUFFIX+=", $ERROR_COUNT error(s)"
[[ "$SKIP_COUNT" -gt 0 ]] && SUMMARY_SUFFIX+=", $SKIP_COUNT stricter-than-baseline skip(s)"

if $APPLY; then
  echo "== done: $FAIL_COUNT failure(s)$SUMMARY_SUFFIX =="
  [[ "$FAIL_COUNT" -eq 0 && "$ERROR_COUNT" -eq 0 && "$SKIP_COUNT" -eq 0 ]] || exit 1
else
  echo "== done: $DRIFT_COUNT drift(s)$SUMMARY_SUFFIX =="
  [[ "$DRIFT_COUNT" -eq 0 && "$ERROR_COUNT" -eq 0 && "$SKIP_COUNT" -eq 0 ]] || exit 1
fi
