# Results audit Part A (Yinzer) — NHL lists & FINAL CALL cards, Oct 26 → Oct 29 12:30 PM PT pass
Sources: picks/*_post.txt, picks/finalcall_done, card_decisions.csv, graded/20261026-28.csv; Oct 29 from api-web.nhle.com boxscores (2026020204-206, all OFF). Detail: card_grades.csv. Skip-side rebuild: t1_rebuild.csv (rebuild.py).

## Cards
Every list in the window was **NO BETS** (Oct 26 x4, Oct 27 x6, Oct 28 x3, Oct 29 x1). graded/ `pick` column empty on all 304 rows. Card record: 0 bets, 0.00u.

## Sides that would have cleared at shop-at (never reached price)
| side | shop-at | SOG | result | u @shop | CLV (no-vig, pick→close) |
|---|---|---|---|---|---|
| Protas U1.5 (Oct 28) | -103 | 3 | L | -1.00 | -2.5 |
| Malinski U1.5 (Oct 28) | -121 | 3 | L | -1.00 | +2.5 |
| Raddysh U2.5 (Oct 28 TOR@SEA) | -112 | 1 | W | +0.893 | 0.0 |
| Scheifele O1.5 (Oct 27, PrizePicks hold; user played) | -143 | 3 | W | +0.699 | -0.8 |
Hypothetical at shop-at: 2-2, -0.41u (avg CLV -0.2). Excluding Scheifele (not a card bet): 1-2, -1.11u. Not posting these at DK prices saved money.

## Gaps
- CGY@EDM Oct 28 missed (box suspended); not graded.
- Shot mismatch 2026020195 / 8476874 = Olli Maatta (MIN D): RESOLVED. Our s2026.pkl now = 1 SOG = NHL boxscore (feed refetch Oct 29 09:21 PT; gap check since reports 0 problems; no override needed). He had no prop line, so no grade affected.
- Taylor Hall Oct 27 ungraded (actual missing) — skip side only.
- Usage stop after the Oct 29 12:30 pass: nothing later graded.

## Integrity check (Oct 31, 5:30 AM PT)
- All 304 graded rows (Oct 26-28, 17 games) + 47 Oct 29 lined players checked vs api-web.nhle.com boxscores: 1 mismatch -> fixed: graded/20261027.csv Rasmus Dahlin (BUF@SJ, 2026020198) actual 1 -> 2 (U2.5 still wins; no list/skip grade changed). Backup graded_20261027.bak.csv; logged in fixes.csv.
- Maxey Oct 28 final = 27 pts (in-game "5" was partial). Brunson 31 PRA, Scheifele 3, Protas 3 SOG confirmed.
- 14 posted lists = 14 finalcall_done markers = card_decisions entries; all NO BETS.
- No lists after Oct 29 12:33 PM PT; no captures/20261030. Only 12:57 PM Oct 29 D snapshots for the 4:00 PM games exist (no pass ran on them).

## Skipped sides that hit: see t1_rebuild.csv / summary in chat.

## Enhancement 3 (2026-10-31, Yinzer; Tester1 checks)
- NHL 5 ungraded sides -> VOID_DNP (no result change; were already excluded): Taylor Hall O/U1.5 Oct27 (2026020189), Kulich (020108), Voronkov (020129), Wennberg (020141). Absent from api-web boxscore (box_*.json here) and player game logs.
- NFL 30 ungraded sides (6 players) -> VOID_INACTIVE: Judkins, DJ Moore, T. Warren (wk6); Zaccheaus, Spears, Ridley (wk7). No nflverse player_week/snap_counts row while team played; all Questionable in nflverse injuries. Sources in enh3_src/.
- Totals unchanged: NHL skip tallies, NFL 45/91 -6.25u, Week 7 91-73.
- fixes.csv appended; backups in bak_enh3/.
- Catch-up: nhl-sog/scripts/catchup.py -> logs/missed_windows.csv (48 windows MISSED: Oct29 8D/11C/11CLOSE, Oct30 3/3/3); 18 boxscores backfilled to data/catchup_box/. nfl-props/ops/catchup.py -> logs/missed_games.csv (CAR@GB Oct29 TNF MISSED).
