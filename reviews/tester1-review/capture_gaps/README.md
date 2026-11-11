# Item #2: capture-gap retries + missing-close alert (Tester1, Oct 26 2026). Checker: Yinzer.
Nothing in /workspace/nhl-sog was edited. Live use needs yinzerduck's okay.
- close_watch.py: read-only. For each started game on the ESPN schedule, flags no 0-30 min snapshot (NO_FILES / NO_IN_WINDOW_SNAPSHOT),
  prints '!!! CLOSE SNAPSHOT MISSING ...' and dedupes per game in <out>/close_alerts.log. Looks at date-1..date+1 dirs (capture files by UTC date).
- test_close_watch.py: simulated gaps (D only, C at 35 min, game with no files) all flagged, good game and future game not, alert posts once;
  retry wrapper survives 2 dropped connections and re-raises after the last try. Run: /workspace/nhl-sog/.venv/bin/python test_close_watch.py
- capture_retry_close_alert.patch (for Yinzer, apply with `patch -p1` from /workspace/nhl-sog): capture.py retries scoreboard + propBets 3x (3s/6s);
  a propBets failure logs 'CAPTURE GAP' and skips that game instead of killing the run; capture_loop.sh re-runs once after 30s on a failed run or gap,
  then runs close_watch for yesterday+today; ensure_capture.sh prints the last 24h of alerts for whoever posts to the room.
- Backtest Oct 17-26: 64 started games, 22 missing a close, all from Oct 20 evening to Oct 23 (the outage). None since Oct 24.
