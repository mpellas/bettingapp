#!/bin/bash
# Close-window capture that does NOT depend on the background loop (added Oct 26 2026).
# Root cause of the Oct 22 TNF failure: the box is suspended when no Grok Bot session is active, so the
# supervisor/loop freeze (Oct 22 09:28 -> Oct 23 04:59 PT, no pass) and nothing lands in [kickoff-30m, kickoff).
# Run this FROM the routine itself; it keeps the session (and box) awake and captures every 3 min until kickoff.
#   ops/close_window_capture.sh --week 7 [--kickoff 2026-10-26T17:15-07:00] [--dry-run]
# Without --kickoff it uses the next kickoff from a fresh ESPN snapshot. Free (ESPN only), no Odds API credits.
cd "$(dirname "$0")/.." || exit 1
WEEK=""; KO=""; DRY=0; STEP=180
while [ $# -gt 0 ]; do case "$1" in
  --week) WEEK="$2"; shift;; --kickoff) KO="$2"; shift;; --dry-run) DRY=1;; *) echo "unknown arg $1"; exit 1;; esac; shift; done
[ -n "$WEEK" ] || { echo "--week required"; exit 1; }
ops/ensure_capture.sh --capture --week "$WEEK" >/dev/null
if [ -z "$KO" ]; then
  KO=$(.venv/bin/python -c 'import json;d=json.load(open("logs/ensure_capture_last.json"));k=[e["kickoff_pt"] for e in d["events"]];print(min(k) if k else "")')
  [ -n "$KO" ] || { echo "could not infer kickoff (no due events in this capture); pass --kickoff"; exit 1; }
fi
ko=$(date -d "$KO" +%s); start=$((ko-28*60)); now=$(date +%s)
echo "$(date -Is) kickoff=$KO window_start=$(date -d @$start -Is) dry_run=$DRY"
if [ "$DRY" = 1 ]; then
  t=$start; [ $t -lt $now ] && t=$now
  while [ $t -lt $((ko-60)) ]; do echo "would capture at $(date -d @$t -Is)"; t=$((t+STEP)); done
  echo "would run snaplines --week $WEEK, then check C rows for kickoff $KO"; exit 0
fi
[ $now -ge $ko ] && { echo "kickoff passed; nothing to do"; exit 3; }
[ $now -lt $start ] && { echo "sleeping $((start-now))s until window"; sleep $((start-now)); }
n=0
while [ $(date +%s) -lt $((ko-60)) ]; do
  ops/ensure_capture.sh --capture --week "$WEEK" | grep -E "one-shot|snaplines|STATUS" ; n=$((n+1))
  sleep $STEP
done
echo "$(date -Is) done: $n captures in close window"
.venv/bin/python - "$WEEK" <<'PY'
import sys,pandas as pd
c=pd.read_csv(f"data/lines/snap_2026_wk{int(sys.argv[1])}_C.csv")
print("C rows by event:", c.groupby("event_id").size().to_dict())
PY
