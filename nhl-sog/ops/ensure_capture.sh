#!/bin/bash
# Idempotent: (re)build .venv if broken, start supervisor if not running, print status.
cd "$(dirname "$0")/.." || exit 1; mkdir -p logs
if ! .venv/bin/python -c 'import requests' 2>/dev/null; then
  rm -rf .venv; python3 -m venv --system-site-packages .venv && .venv/bin/pip -q install requests >/dev/null 2>&1; echo "venv rebuilt"
fi
if ! pgrep -f 'ops/capture_supervisor\.sh' >/dev/null; then nohup setsid ops/capture_supervisor.sh >/dev/null 2>&1 </dev/null & disown; sleep 5; pgrep -f "ops/capture_supervisor\.sh" >/dev/null && echo "supervisor started" || echo "ERROR: supervisor failed to start"; fi
# Input freshness (added 2026-10-17): refresh this season's game logs if data/s2026.pkl stops before yesterday.
STALE=$(.venv/bin/python -c "import pandas as pd,datetime as dt;print(pd.read_pickle('data/s2026.pkl').gameDate.max()<(dt.date.today()-dt.timedelta(1)).isoformat())" 2>/dev/null)
if [ "$STALE" != "False" ]; then echo "game logs stale/missing -> fetch.py"; timeout 600 .venv/bin/python fetch.py >>logs/fetch.log 2>&1 && echo "fetch.py OK"; fi
.venv/bin/python -c "import pandas as pd;print('game logs through', pd.read_pickle('data/s2026.pkl').gameDate.max())"
# Gap check (added 2026-10-17): every completed game in the last 14 days must have box-score rows matching the official boxscore.
# On failure: refetch once, re-check; if still failing print a loud GAP CHECK FAILED line (routine must report it, not pick on stale data).
if ! timeout 300 .venv/bin/python check_gaps.py --days 14 --box >>logs/gap_check.log 2>&1; then
  echo "gap check failed -> fetch.py + recheck"; timeout 600 .venv/bin/python fetch.py >>logs/fetch.log 2>&1
  if ! timeout 300 .venv/bin/python check_gaps.py --days 14 --box 2>&1 | tee -a logs/gap_check.log; then echo "!!! GAP CHECK FAILED: NHL game logs have missing/mismatched box-score rows (logs/gap_check.log) !!!"; fi
else tail -n 1 logs/gap_check.log; fi
pgrep -af 'ops/capture_(supervisor|loop)\.sh'
grep -h '^20.*CLOSE SNAPSHOT MISSING' logs/close_alerts.log 2>/dev/null | awk -F'\t' -v c="$(date -u -d '-1 day' -Is)" '$1>c{print $3}'  # Tester1 item #2: post these to the room
echo "--- last loop entries"; tail -n 6 logs/capture_loop.log 2>/dev/null
echo "--- supervisor"; tail -n 3 logs/capture_supervisor.log 2>/dev/null
