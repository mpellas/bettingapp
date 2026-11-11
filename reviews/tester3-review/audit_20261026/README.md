# Tester3 Oct 26 audit (read-only)
Job A: audit_nhl_rules.py -> gates_table.csv (196 rows: 74 posted + 1 sheet-only DeBrusk + 121 near-misses), card_classification.csv, near_miss_skip_reasons.csv, run_output.txt
Sources: nhl-sog/sheets/*_picks.xlsx, picks/*_GATE.csv, picks/*_post.txt, data/s2026.pkl, game_starts.py (puck drop).
Assumptions: huge-move threshold not codified -> HUGE_MOVE=5 pts (results identical for any threshold 4-22 pts);
2-of-7 rule applied to all passes (effective date not found in repo); TOI vote compared only from 20261020_1406 on (commit d6cb300).
Job B: see final report (nfl-props commit 39c332c, logs/snapshot_supervisor.log, data/lines/snap_2026_wk7_{D,C}.csv).
