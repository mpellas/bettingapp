#!/bin/bash
# Worker: free ESPN/DraftKings prop snapshots. Normally every 10 min; every 3 min while any game kicks off within
# 45 min (so the C window, kickoff-30min..kickoff, gets several captures). Games within 60 min of kickoff are
# re-captured if their last capture is >= 2 min old; games further out only if >= 9 min old. Empty passes (nothing
# posted / nothing due) are normal and still write a "=== <time> ===" entry, which the supervisor watches.
# Run via scripts/snapshot_supervisor.sh (restarts this worker if the log has no new entry for > 20 min).
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
LOG=logs/snapshot_loop.log
while true; do
  echo "=== $(date -Is) ===" >> "$LOG"
  out=$(timeout 300 .venv/bin/python -m nflprops.snapshot --min-interval 2 --far-interval 9 --near-minutes 60 2>>"$LOG")
  rc=$?
  printf '%s\n' "$out" >> "$LOG"
  [ $rc -ne 0 ] && echo "snapshot exit code $rc" >> "$LOG"
  nap=$(printf '%s' "$out" | .venv/bin/python -c '
import json, sys
try:
    k = json.load(sys.stdin).get("next_kickoff_min")
except Exception:
    k = None
print(180 if k is not None and k <= 45 else 600)' 2>/dev/null)
  echo "next pass in ${nap:-600}s" >> "$LOG"
  sleep "${nap:-600}"
done
