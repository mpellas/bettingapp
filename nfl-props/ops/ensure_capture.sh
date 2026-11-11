#!/bin/bash
# Idempotent capture guard (NOT part of the hashed prereg files; it only calls them).
# Run this FIRST in every NFL-props routine. Safe to run any number of times.
#   ops/ensure_capture.sh                     # ensure venv + supervisor, print health
#   ops/ensure_capture.sh --capture           # ...plus one immediate ESPN capture (free; no Odds API credits)
#   ops/ensure_capture.sh --capture --week 5  # ...plus snaplines (D/C files) for 2026 week 5
# Exit 0 = healthy; 2 = capture unhealthy after repair attempts (read the STATUS lines).
# Why: on Oct 7 the box was restored from a file-level copy taken ~Oct 5 19:27 PT. Running processes and the
# git-ignored .venv/ did not survive, so the supervisor was gone and (once restarted) every pass failed with
# exit 127 while still writing "===" heartbeats the supervisor treats as healthy.
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
LOG=logs/snapshot_loop.log; OLOG=logs/ensure_capture.log
CAPTURE=0; WEEK=""; SEASON=2026
while [ $# -gt 0 ]; do
  case "$1" in
    --capture) CAPTURE=1 ;;
    --week) WEEK="$2"; shift ;;
    --season) SEASON="$2"; shift ;;
    *) echo "unknown arg $1"; exit 1 ;;
  esac; shift
done
say() { echo "$(date -Is) $*" | tee -a "$OLOG"; }
say "ensure_capture start (capture=$CAPTURE week=${WEEK:-none})"

# 1) venv: the loop hard-codes .venv/bin/python
venv_ok() { .venv/bin/python -c 'import nflprops.snapshot, nflprops.snaplines, lightgbm' >/dev/null 2>&1; }
if ! venv_ok; then
  say "REPAIR: .venv missing/broken; rebuilding with uv"
  { uv venv .venv -q --python python3 --allow-existing && uv pip install -q --python .venv/bin/python -r requirements.txt \
    && uv pip install -q --python .venv/bin/python -e . ; } >>"$OLOG" 2>&1
  venv_ok && say "venv rebuilt OK" || say "ERROR: venv rebuild failed (see $OLOG)"
fi

# 2) supervisor + worker (exactly one each; the supervisor's own flock prevents duplicates)
SUP='^/bin/bash (.*/)?scripts/snapshot_supervisor\.sh$'; WRK='^/bin/bash (.*/)?scripts/snapshot_loop\.sh$'
if ! pgrep -f "$SUP" >/dev/null; then
  say "REPAIR: supervisor not running; starting"
  nohup setsid scripts/snapshot_supervisor.sh >/dev/null 2>&1 &
  sleep 3
fi
# A worker whose recent passes all fail (e.g. exit 127) still heartbeats; restart it after a venv repair.
if tail -n 40 "$LOG" 2>/dev/null | grep -q 'snapshot exit code' && venv_ok; then
  lastpass=$(grep -an '^=== ' "$LOG" | tail -1 | cut -d: -f1); lasterr=$(grep -an 'snapshot exit code' "$LOG" | tail -1 | cut -d: -f1)
  if [ -n "$lasterr" ] && [ "$lasterr" -gt "$lastpass" ]; then
    say "REPAIR: last loop pass failed; restarting supervisor so the worker re-runs now"
    pkill -f "$SUP"; sleep 2; pkill -f "$WRK"; sleep 1
    nohup setsid scripts/snapshot_supervisor.sh >/dev/null 2>&1 &
    sleep 3
  fi
fi

# 3) optional one-shot capture (same module/flags as the loop; ESPN only, free)
if [ "$CAPTURE" = 1 ]; then
  ( flock -w 120 8 || exit 1
    timeout 300 .venv/bin/python -m nflprops.snapshot --min-interval 1 --far-interval 9 --near-minutes 60 \
      > logs/ensure_capture_last.json 2>>"$OLOG" ) 8>logs/ensure_capture.lock
  rc=$?; say "one-shot capture exit $rc"
fi
if [ -n "$WEEK" ]; then
  .venv/bin/python -m nflprops.snaplines --season "$SEASON" --week "$WEEK" >>"$OLOG" 2>&1
  say "snaplines $SEASON wk$WEEK exit $?"
fi

# 4) health report
nsup=$(pgrep -fc "$SUP"); nwrk=$(pgrep -fc "$WRK")
hb=$(grep -a '^=== ' "$LOG" | tail -1 | sed 's/^=== \(.*\) ===$/\1/')
hb_age=$(( $(date +%s) - $(date -d "${hb:-1970-01-01}" +%s) ))
lastcap=$(tail -n 1 data/snapshots/capture_log.jsonl 2>/dev/null | .venv/bin/python -c 'import json,sys; print(json.loads(sys.stdin.read())["captured_at_pt"])' 2>/dev/null)
cap_age=$(( $(date +%s) - $(date -d "${lastcap:-1970-01-01}" +%s) ))
nextko=$(.venv/bin/python - <<'PY' 2>/dev/null
import json,re
t=open("logs/snapshot_loop.log",errors="ignore").read()[-200000:]
m=re.findall(r'"next_kickoff_min":\s*([0-9.]+|null)',t); print(m[-1] if m else "?")
PY
)
lastfail=$(tail -n 40 "$LOG" | grep -c 'snapshot exit code')
say "STATUS supervisors=$nsup workers=$nwrk last_heartbeat=$hb (${hb_age}s ago) last_capture=$lastcap (${cap_age}s ago) recent_failed_passes=$lastfail next_kickoff_min=$nextko"
ok=1
[ "$nsup" = 1 ] && [ "$nwrk" = 1 ] || ok=0
[ "$hb_age" -le 1500 ] || ok=0
venv_ok || ok=0
if [ "$ok" = 1 ]; then say "STATUS OK"; exit 0; else say "STATUS UNHEALTHY"; exit 2; fi
