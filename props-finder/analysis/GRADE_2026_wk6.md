# NFL 2026 week 6 list: graded (paper; actual stats from nfl-props track, data/track/2026_wk06.parquet, rescored 2026-10-21 11:07 AM PT)

| pick (as listed) | book / entry | line | side | actual | result |
|---|---|---|---|---|---|
| Omarion Hampton rec yds (LAC @ KC) | DraftKings -103 | 5.5 | Under | 21 | LOSS |
| Omarion Hampton rec yds (LAC @ KC) | PrizePicks (power3) | 6.5 | Under | 21 | LOSS |
| Ray Davis rush yds (BUF @ LV) | PrizePicks (power3) | 7.5 | Over | 4 | LOSS |
| Darren Waller rec yds (CAR @ PHI) | PrizePicks (power3) | 26.5 | Under | 0 | WIN |
| Tyler Higbee rec yds (ARI @ LA) | PrizePicks (power3) | 34.5 | Under | 22 | WIN |
| Dak Prescott rush yds (DAL @ GB) | PrizePicks (flex5/flex6 qualifying) | 10.5 | Under | 7 | WIN |

- Hampton line-value test (Tester3): he finished with 21 rec yds, so U5.5 and U6.5 both lost; the extra yard didn't matter this time (it would only matter at exactly 6).
  The user's DK U5.5 bet was cashed out at Q3 for 0.01 (logged as cashout, -0.09).
- The user's PrizePicks 2-pick Power Play (Hampton U6.5 + Dak U10.5, $10): Hampton leg lost, so the entry lost (-$10). Off-list entry type.
- PrizePicks legs: 3-2 (Davis over was the only Over on the list and missed).

## Void accounting (Tester1)
- Week 6 summary rescored: 287 D lines, 261 scored, 9 void, 17 pending. Voids: **7 pulled_before_close** (3 model-over, 4 model-under; all 7 rows in snap_2026_wk6_pulled.csv),
  2 no-player-row. The old summary (0 voids from pulled lines) was the Oct 16 interim run, made before Sunday's lines were pulled; no prereg rule changed.
- Week 5 reconciliation: bad0fdb's 27 voids = 20 TB @ DAL (no pregame prediction file before kickoff: all TB@DAL lines) + 6 pulled_before_close
  (MIN @ NO 2, BAL @ ATL, BUF @ LA, DEN @ LAC, DET @ ARI) + 1 no-player-row (PHI @ JAX). Calling TB@DAL "the only void" was wrong: it is the only void *game*, 20 of 27 lines.
