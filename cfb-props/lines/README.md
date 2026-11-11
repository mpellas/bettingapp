# CFB free game-line track (ESPN DraftKings spread / total / moneyline; 0 Odds API credits)
- `ensure_lines.sh` — start the capture loop if not running (run first in the Saturday CFB routine; box restores kill it).
- `capture_lines.py [--loop]` — raw scoreboard -> raw/<date>/, one row per game -> snapshots.csv. Loop: every 30 min,
  every 4 min when a kickoff is <= 45 min away; exits when no game today/tomorrow is pre-game.
- `grade_lines.py YYYYMMDD` — open (first capture) vs close (last capture 0-30 min pre-kick), cover/total results,
  line moves, no-vig CLV; grades picks.csv (event_id, market, side, line, price, logged_utc) if present.
- ESPN removes odds once a game is final, so closes can only come from our own pre-kickoff captures.
- No CFB player props on ESPN (propBets 404 for provider 100); props need the Odds API.
