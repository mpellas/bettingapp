#!/bin/bash
# Idempotent: start the free CFB line-capture loop if it is not running; print status. 0 credits.
cd "$(dirname "$0")" || exit 1; mkdir -p logs
if ! pgrep -f 'capture_lines\.py --loop' >/dev/null; then
  nohup setsid python3 -u capture_lines.py --loop >>logs/capture_lines.log 2>&1 </dev/null & disown; sleep 3
  pgrep -f 'capture_lines\.py --loop' >/dev/null && echo "cfb line loop started" || echo "ERROR: cfb line loop failed to start"
fi
pgrep -af 'capture_lines\.py --loop'; tail -n 3 logs/capture_lines.log
