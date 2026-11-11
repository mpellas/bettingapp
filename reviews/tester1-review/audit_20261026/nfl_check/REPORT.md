# Tester1 cross-check of Yinzer section 1 (NFL), Oct 26 2026
Sources: nflverse stats_player_week_2026 (same sha256 18a093a4 as Yinzer's), nflverse snap_counts_2026, ESPN summary box scores, nfl-props lines C/D, track parquets.
1. Posted 15 sides 8-7; DK/Fliff 7 at 3-4 and -1.15u; PP 8 at 5-3: MATCH (all 15 results regraded from raw stats).
2. CLV: DIFFERENCE. Line values and n match (10/2/8), but the sign is inverted. audit_nfl.py clv() uses close-line for Unders and line-close for Overs, which is the opposite of "+ = moved our way". Correct means: all +1.50, DK/Fliff +0.50, PP +1.75 (wk6 +1.17, wk5 +2.0, wk7 +2.0). Example: Ray Davis O7.5 closed at 9.5, so +2, not -2. The "negative by design" note for PP is wrong too.
3. Paper track: DIFFERENCE. 328 sides, 185-143, 0 pushes, +25.18u at -110 (wk5 85-70 +7.27u; wk6 100-73 +17.91u). Yinzer dropped 3 sides with no nflverse row. Horton (wk5 O10.5 rec), Mumpfield (wk5 O5.5 rec) and Skattebo (wk6 O42.5 rush) aren't in the ESPN box scores, but snap counts show they played (11, 6 and 6 offensive snaps). By prereg rule (DNP needs no stat row AND no snap), they grade as 0 yds = 3 losses. track.py hit_main agrees on all 328. z_clv +0.0019, n=328: MATCH.
4. Hashes: prereg sha1 fc9961cf... MATCH. track.py sha1 0b5414dc... = prereg pin MATCH (git blob 9542b1a = de029ac also).
5. Thursday wk7 void game = 401873010 NE@CHI (24 D lines ~467 min out, 0 C lines), not TB@DAL.
6. Purdy O19.5 rush: in props-finder/bets_log.csv, status fail (EV 0.23% < 2% bar), not posted: MATCH.
7. Wk5 EVs (find.analyze on raw/20261011T1237, DK/Fliff): Willis U5.5 att Fliff +105 fair 0.5022, EV 2.94% (market only). Posted 4.02% = 5% model blend (0.95*0.5022+0.05*0.6061=0.5074). Croskey-Merritt U13.5 DK -116 market-only EV -0.23% (posted +0.62% with the blend). Both MATCH Yinzer's claims (recompute.py).
8. Wk6-7 recompute (pp_recompute.py, pickem.legs_from_raw on raw/20261018T1440 and 20261025T1432): all 7 PP legs fair diff 0.0000, book-only. Each clears break-even +1 pt for exactly its listed entry types. DK Hampton U5.5 rec -103 fair 0.5248, EV 3.44% >= 2%. MATCH.
9. Horton/Mumpfield/Skattebo dispute. Snaps from https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_2026.parquet (local snaps_2026.parquet; pfr ids):
   - HortTo00 Tory Horton, 2026_05_SF_SEA (202610110sea), offense_snaps 11
   - MumpKo00 Konata Mumpfield, 2026_05_BUF_LA (202610120ram), offense_snaps 6
   - SkatCa00 Cam Skattebo, 2026_06_NO_NYG (202610180nyg), offense_snaps 6
   track.py output (nfl-props/data/track/2026_wk05.parquet rows 234 and 279, 2026_wk06.parquet row 114): actual=0.0, void=False, void_reason=NaN, status=settled, in_scope=True, hit_main=0.0 (loss).
   "no_stat, 0u" is the `result`/`units` column in Yinzer's own sides.csv (audit_nfl.py), not a track.py grade. His `track_hit_main` column for the same rows is 0.0.
