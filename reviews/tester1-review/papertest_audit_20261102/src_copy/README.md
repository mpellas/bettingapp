# NHL SOG paper tests (PAPER ONLY; never touches /workspace/nhl-sog live files, predict.py, frozen models, --rescore, or pick cards)
Set up 2026-11-02 3:10 PM PT by the first run of routine "NHL SOG: paper tests (late lineup re-pull + position-defense challenger)".

Each run (every 15 min, 3:00-7:45 PM PT):
1. `python3 run.py` -> games 30-45 min out. Re-pulls DailyFaceoff vs the D-snapshot lineup in /workspace/nhl-sog/captures/*/<event>_D.json
   (the lineup the window pass used) -> lineup_repull_log.csv; Reddit public RSS (/r/<team>/new/.rss and r/hockey, past 3h, cached per run)
   -> social_log.csv; lineup-changed frozen sides with current DK price (latest capture archive) -> lineup_changed_sides.csv;
   challenger A picks (edge >= 5 pts vs current no-vig, DK price +110..-150) -> challenger_picks.csv. Last stdout line = JSON summary.
   `PT_OUT=/tmp/x python3 run.py --lo 30 --hi 60` = dry run to a temp dir.
2. X (x connector search_posts_all, read-only): ONE combined query per game, past ~3h (start_time), second only if needed.
   Log calls: `python3 log_x.py calls N "note"`; relevant posts: write JSON list and `python3 log_x.py posts file.json`
   (fields gameId, source=x, author, time_pt, url, text, players_named, dfo_reflected true/false). Stop X if day total nears 800.
   X day window resets 00:00 UTC (4 PM PST). If X/Reddit news names a player whose frozen side is on a D line, append a row to
   lineup_changed_sides.csv with sources x/reddit (combine with dailyfaceoff if both).
3. After the last game (first run after 7:30 PM or next morning's first run): `python3 grade.py` -> grade_summary.md.
   Message the user only on an error or when either test reaches 100 graded sides.
Challenger model: models/chal_A.txt (+json), base frozen features + opp_sa_pos_r20, trained on seasons <=2025 (through 2026-04-16),
early stopping on 2025 then refit; train_challenger.py. Feature code chal_common.py (copy of ablate.py variant A).
Notes: reddit .json returns 403 from the box; RSS works but rate-limits (429) if hit repeatedly.
