#!/bin/bash
# Supervisor for scripts/snapshot_loop.sh. Exactly one instance (flock). Starts the worker in its own process group
# and restarts it if it dies or if logs/snapshot_loop.log has had no new "=== <time> ===" entry for > 20 min
# (empty passes are normal; a MISSING entry is the alert condition). Events go to logs/snapshot_supervisor.log.
#   start:  nohup setsid scripts/snapshot_supervisor.sh >/dev/null 2>&1 &
#   stop:   pkill -f '^/bin/bash (.*/)?scripts/snapshot_supervisor\.sh$'   (its TERM trap also stops the worker)
#   check:  pgrep -af 'snapshot_(supervisor|loop)'; tail logs/snapshot_supervisor.log
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
exec 9>logs/snapshot_supervisor.lock
flock -n 9 || { echo "$(date -Is) another supervisor holds the lock; exiting" >> logs/snapshot_supervisor.log; exit 1; }
LOG=logs/snapshot_loop.log
SLOG=logs/snapshot_supervisor.log
STALE=${STALE_SECONDS:-1200}
say() { echo "$(date -Is) $*" >> "$SLOG"; }
start_worker() {
  setsid scripts/snapshot_loop.sh 9>&- &
  WPID=$!
  say "started worker pid $WPID"
}
last_entry_age() {
  local t
  t=$(tail -c 400000 "$LOG" 2>/dev/null | grep -a '^=== ' | tail -1 | sed 's/^=== \(.*\) ===$/\1/')
  [ -z "$t" ] && { echo 999999; return; }
  echo $(( $(date +%s) - $(date -d "$t" +%s) ))
}
trap 'say "supervisor stopping; killing worker group $WPID"; kill -- -"$WPID" 2>/dev/null; exit 0' TERM INT
say "supervisor pid $$ starting (stale threshold ${STALE}s)"
if pkill -f '^/bin/bash (.*/)?scripts/snapshot_loop\.sh$' 2>/dev/null; then say "killed orphan worker(s) left by a previous supervisor"; sleep 1; fi
start_worker
while true; do
  sleep "${CHECK_SECONDS:-60}" & wait $!
  if ! kill -0 "$WPID" 2>/dev/null; then
    say "worker $WPID not running; restarting"; start_worker; continue
  fi
  age=$(last_entry_age)
  if [ "$age" -gt "$STALE" ]; then
    say "ALERT: no new log entry for ${age}s (> ${STALE}s); killing worker group $WPID and restarting"
    kill -- -"$WPID" 2>/dev/null; sleep 2; kill -9 -- -"$WPID" 2>/dev/null
    start_worker
  fi
done
