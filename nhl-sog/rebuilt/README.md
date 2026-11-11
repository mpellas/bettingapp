# rebuilt/ — Oct 12-16, 2026 NHL SOG, retro-computed (separate record)

The logged D files for Oct 12-16 used stale inputs (game logs through Oct 10; see NOTES.md). This folder re-scores the
SAME captured DraftKings lines point-in-time on gap-free data (2026-10-17, audit/rebuild_stale.py):
- inputs = game logs with gameDate < slate date only (no lookahead), from the backfilled data/ (Sep 29-30 games included);
- champion c3ab760178 via predict.py; challenger 3386583f18 via challenger/predict_challenger.py (frozen files, unchanged);
- graded/<date>.csv: logged status / close (nv_over_C, line_C) kept, official actuals (4 stat corrections; actual_logged kept);
- graded_closepy_now/: strict re-grade with today's close.py (Oct 12-13 have no snapshot archive, so fewer closes);
- REPORT.md (logged closes) and REPORT_closepy_now.md.

These are RETRO-COMPUTED, NOT live decisions, and are not what was posted or bet that week (that record is graded/ +
props-finder/user_bets). The champion was trained through Oct 10, so its rebuilt lines are out-of-sample and count as clean
evaluation data. The challenger was trained through Oct 16, so its Oct 12-16 numbers are IN-SAMPLE: report only, never
part of its shadow test (prereg window starts Oct 17).
