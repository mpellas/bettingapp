# Tester1 cross-check of Yinzer's extra evidence tests (hit, books), 2026-11-09
Work copies only (cp -a + diff -rq verified). Originals untouched.
1 hit rate   NHL PASS 250/250 sides (Nov 5 12:39) match independent rebuild; NFL PASS 39/39 (wk8 0909 + wk7 0732 live).
             No leakage: NHL max gameDate used 2026-11-04; NFL week < W (38/39 sides had later games in data, all excluded).
             Uses DK NO-VIG (vig-implied would change 36/250 NHL, 3/39 NFL). Strict >/< ; all lines are half-lines.
             'This season': NHL gameDate >= Sep 1 (all regular-season ids); NFL season==2026 REG. Last 10 spans last season
             (NHL 6/250, NFL 32/39). Min games: NHL 5, NFL 4. 8 NHL players' logs match NHL API exactly.
2 books      NHL logic PASS (direction, side/player match, missing -> 0; 23 historic non-zero sides match my rebuild; Nov 5 = 0 for all 250).
             Bias: vig-vs-vig compare -> 22 of 23 non-zero are '+' (Fliff juicier = 'agrees'). Fliff key ignores line and pull time.
             NFL FAIL: same-line branch compares no-vig fair_prob to a vigged price -> '-' on BOTH Over and Under (48/48 on nov02 all_sides).
             In practice NFL books is always 0: live analysis has 1 row per side (39/39 'no other book'), and lacks fair_prob.
3 counts     PASS: X of 7 unchanged 250/250 NHL vs original sheet; NFL agrees_n identical old vs new code 39/39.
             X of N arithmetic 0 failures. NHL N=9; NFL N=11 now (Tester2 added pace+rest 08:09 PT).
4 NFL IDs    CONFIRMED: all_sides CSV has no player_id/game_id -> 0 of 419 scored, .txt has header only, no 'unavailable' text.
             No code fix in add_evidence.py; routine-side fix not visible on disk.
Files: nhl_hit_compare.csv nhl_count_compare.csv nhl_books_compare.csv nfl_hit_books_compare.csv out/ their_nhl_20261105_1239_extra.csv
