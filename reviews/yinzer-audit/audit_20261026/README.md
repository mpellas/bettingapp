# Oct 26 2026 audit: NFL picks process + paper track (Yinzer). Paper only.
Run: `/workspace/nfl-props/.venv/bin/python audit_nfl.py` (read-only; stats from nflverse stats_player_week_2026.parquet downloaded 2026-10-26 9:10 AM PT).
- Posted picks: wk5 = analysis_2026_wk5_live_20261011T0538 + _20261012T1434 (in_final_list) + pickem_nfl_qualifying_20261012T1434; wk6/wk7 = status PASS in analysis/oct18|oct25 all_sides.
- EV/fair re-computed from props-finder/raw/{20261011T1237,20261012T2133,20261018T1440,20261025T1432} with find.analyze (DK/Fliff) and pickem.consensus_at (PP, book-only).
- Bar: DK/Fliff EV >= 2%; PP P(win) >= break-even + 1 pt for every listed entry type. Bar not in force on wk5 (Oct 11-12).
- CLV: ESPN DK C captures carry no prices (price_assumed=True on all wk5-7 rows), so posted-pick CLV is LINE CLV (close line vs posted line, + = moved our way). PP legs are compared to the DK close line, which is structurally negative (PP's number was off DK's). Paper-track CLV = prereg z_clv (voids excluded).
- Paper-track units use the D prices, which are assumed -110 (hypothetical).
- Hashes: prereg sha1 fc9961c... matches; track.py git blob = de029ac blob 9542b1a.
Files: sides.csv (one row per posted pick / paper-track side), summary.csv.
