# Weekly fleet audit, for the local Windows scheduled task.
#
# Runs the drift audit, records the whole matrix with a timestamp, and keeps a
# bounded history. Paths are absolute because a scheduled task inherits neither
# the user's PATH nor a useful working directory.
#
# Exit-code policy. The audit exits 1 when it finds drift; that is a finding,
# not a malfunction. This wrapper therefore reports success for 0 (clean) and 1
# (drift) alike, and fails only for 2 and above (usage error, or the audit
# refusing to report a partial fleet). Mapping drift to a failing task would
# make it look permanently broken - the organization carries two controls that
# only a human can clear - and a genuinely broken audit would then be
# indistinguishable from an ordinary drifting one. What the run FOUND is in the
# log; whether it RAN is the task's Last Result.

$repo = 'C:\Users\franc\governance'
$uv = 'C:\Users\franc\.local\bin\uv.exe'
$logs = 'C:\Users\franc\governance-audit'
$keep = 12  # weekly cadence, so about a quarter of history

New-Item -ItemType Directory -Force -Path $logs | Out-Null
$log = Join-Path $logs ('{0}.log' -f (Get-Date -Format 'yyyy-MM-dd_HHmmss'))

# Stream merging is delegated to cmd on purpose. PowerShell 5.1 turns a native
# command's stderr into ErrorRecord objects, which arrive decorated with the
# calling script and line number; the audit writes its progress lines there, so
# the log would carry that noise instead of the report. Merging before
# PowerShell sees it keeps every line a plain string.
$command = '"{0}" run --directory "{1}" python scripts/audit.py --all 2>&1' -f $uv, $repo
$output = & cmd.exe /c $command
$code = $LASTEXITCODE

# One write, one encoding: Tee-Object would default to UTF-16 here and leave a
# log that is half UTF-8 header, half UTF-16 body.
@("fleet audit started $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')") +
    $output +
    @("audit exit code: $code") |
    Set-Content -Path $log -Encoding UTF8

# Bounded history: drop the oldest beyond $keep. Names sort chronologically.
Get-ChildItem -Path $logs -Filter '*.log' |
    Sort-Object Name -Descending |
    Select-Object -Skip $keep |
    Remove-Item -Force

if ($code -ge 2) { exit $code }
exit 0
