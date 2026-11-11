#!/bin/bash
# Worker: runs capture.py (hard 120s timeout); waits 600s normally, 180s when a game is within 45 min.
# Waits by WALL CLOCK in 15s slices so a VM pause/CPU stall can't stretch a sleep; writes logs/next_sleep for the watchdog.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
while true; do
  touch logs/heartbeat; echo "=== $(date -Is) ===" >> logs/capture_loop.log
  out=$(timeout -k 10 120 "$PY" capture.py 2>&1); rc=$?; echo "$out" >> logs/capture_loop.log
  [ $rc -ne 0 ] && echo "capture.py exit $rc" >> logs/capture_loop.log
  # Tester1 item #2: a failed/timed-out run (or a propBets gap) gets one quick re-run after 30s instead of waiting 180-600s.
  if [ $rc -ne 0 ] || echo "$out" | grep -q '^CAPTURE GAP'; then
    sleep 30; touch logs/heartbeat; echo "=== $(date -Is) retry ===" >> logs/capture_loop.log
    out=$(timeout -k 10 120 "$PY" capture.py 2>&1); rc=$?; echo "$out" >> logs/capture_loop.log
    [ $rc -ne 0 ] && echo "capture.py exit $rc (retry)" >> logs/capture_loop.log
  fi
  # Missing-close alert: dedupes per game in logs/close_alerts.log; '!!! CLOSE SNAPSHOT MISSING' lines are relayed to the room.
  "$PY" ops/close_watch.py --out logs $(date -d yesterday +%Y%m%d) $(date +%Y%m%d) >> logs/capture_loop.log 2>&1
  s=$(echo "$out" | awk '/^NEXT_SLEEP/{print $2}'); s=${s:-180}; echo "$s" > logs/next_sleep
  until=$(( $(date +%s) + s )); while [ "$(date +%s)" -lt "$until" ]; do touch logs/heartbeat; sleep 15; done
done
