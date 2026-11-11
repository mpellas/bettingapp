#!/bin/bash
# One instance (flock). Restarts worker if it dies or logs/heartbeat is quiet > 8 min (4 min when a game is within 45 min; capture itself is capped at 130s).
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs; exec 9>logs/capture_supervisor.lock
flock -n 9 || exit 0
LOG=logs/capture_loop.log; SLOG=logs/capture_supervisor.log; stale(){ [ "$(cat logs/next_sleep 2>/dev/null)" = 180 ] && echo 240 || echo 480; }  # 4 min near puck drop, else 8 min
say(){ echo "$(date -Is) $*" >> "$SLOG"; }
start_worker(){ setsid ops/capture_loop.sh 9>&- & WPID=$!; say "started worker $WPID"; }
age(){ [ -f logs/heartbeat ] && echo $(( $(date +%s) - $(stat -c %Y logs/heartbeat) )) || echo 999999; }  # heartbeat touched every 15s by worker (and before each capture)
trap 'say "stopping"; kill -- -"$WPID" 2>/dev/null; exit 0' TERM INT
say "supervisor $$ starting"; pkill -f 'ops/capture_loop\.sh' 2>/dev/null && sleep 1
start_worker
while true; do
  sleep 30 & wait $!
  if ! kill -0 "$WPID" 2>/dev/null; then say "worker died; restarting"; start_worker; continue; fi
  a=$(age); ST=$(stale); if [ "$a" -gt "$ST" ]; then say "ALERT stale ${a}s (>${ST}s); restarting"; kill -- -"$WPID" 2>/dev/null; sleep 2; kill -9 -- -"$WPID" 2>/dev/null; start_worker; fi
done
