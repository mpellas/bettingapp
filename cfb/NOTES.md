# CFB price_check.py notes

## Off-number conversion (added Oct 24, 2026)

price_check.py now scores two kinds of sides from the same single `spreads,totals` Odds API call (no extra credits):
- `match_type=same_number`: Fliff and DK at the same number (unchanged math).
- `match_type=off_number_converted`: same team/side but a different number. DK's no-vig fair probability at its number is moved to Fliff's number with the empirical CFB landing table below, then edge = converted fair - Fliff break-even. Same gaps: 3 pts Power 4, 5 pts Group of 5/FCS.

Every side considered goes in `leans/<date>_<hhmm>.csv` with `dk_line, fliff_line, line_diff, conv_anchor, conv_integers, conv_shift_pts, dk_fair_at_fliff_line`. Qualifying off-number sides are appended to `/workspace/cfb-props/lines/picks.csv` with `track=cfb_offnum` (live runs only, not `--reuse`); grade_lines.py now prints W-L-P/units/CLV per track. The room section text is in `leans/<date>_<hhmm>_offnum_post.txt`, headed "OFF-NUMBER (CONVERTED), SEPARATE TRACK".

### Method
Tables are CFB-only and empirical (tester request: not NFL key-number values).
- Sample: FBS games (ESPN scoreboard groups=80, finals only), seasons [2019, 2021, 2022, 2023, 2024, 2025] (2020 excluded, COVID season). Pregame lines from ESPN core API `/events/{id}/competitions/{id}/odds` (first non-live provider: ESPN BET 1786, Caesars Sportsbook 1624, Caesars Sportsbook (Colorado) 1217, Betradar 599, CG Technology 319, DraftKings 147, Caesars Sportsbook (New Jersey) 31, Caesars 5, Westgate 2, Unibet 1, Caesars Sportsbook (Pennsylvania) 1). Spread sample 5682 games, totals 5266. Scripts: `hist/pull.py`, `hist/pull_odds.py`, `hist/build_tables.py` -> `hist/landing_tables.json`.
- Spreads: h(k) = P(favorite final margin == k | closing |spread| within +/-3 of the DK number). Moving a side from DK line Ld to Fliff line Lf shifts its win probability by the mass of the side's margin between -Lf and -Ld; an integer endpoint counts half (a push there is split). Example: dog +3 -> +2.5 loses 0.5 x h(3).
- Totals: h(k) = P(final total == k | closing total within +/-4 of the DK total), same crossing rule.
- Caveats: single-integer rates carry ~+/-0.5 pt sampling noise; closing lines are from one consensus provider per game, not DK; FCS-vs-FCS games are not in the sample (FCS sides use the FBS table). Untested vs market: this is a separate paper track until it has a record.

### Spread landing rates P(favorite margin == k), % (conditioned on |spread| anchor)

| anchor |spread| | n | 1 | 2 | 3 | 4 | 6 | 7 | 8 | 10 | 11 | 13 | 14 | 17 | 21 | 24 | 28 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.5 | 1532 | 2.0 | 2.0 | 7.3 | 2.5 | 2.5 | 4.8 | 2.1 | 3.2 | 1.9 | 0.7 | 2.7 | 2.5 | 2.5 | 1.6 | 0.7 |
| 3 | 1838 | 2.0 | 1.7 | 7.7 | 2.6 | 2.3 | 5.1 | 1.9 | 3.2 | 1.7 | 0.7 | 2.8 | 2.6 | 2.5 | 1.7 | 1.1 |
| 4.5 | 2382 | 1.8 | 1.7 | 7.1 | 2.6 | 2.3 | 5.7 | 2.0 | 3.2 | 1.8 | 1.0 | 3.1 | 2.6 | 2.8 | 1.7 | 1.3 |
| 6.5 | 1880 | 1.8 | 2.0 | 6.8 | 2.5 | 2.0 | 6.1 | 2.0 | 3.4 | 2.0 | 1.5 | 3.3 | 2.3 | 2.8 | 1.9 | 1.5 |
| 7 | 1639 | 1.7 | 1.9 | 6.6 | 2.6 | 1.8 | 5.7 | 1.9 | 3.8 | 1.7 | 1.3 | 3.5 | 2.3 | 3.0 | 1.8 | 1.8 |
| 9.5 | 1469 | 1.9 | 2.0 | 5.2 | 2.7 | 2.1 | 5.9 | 1.9 | 3.7 | 1.8 | 1.8 | 3.5 | 2.7 | 2.9 | 2.1 | 1.9 |
| 10 | 1252 | 2.5 | 1.9 | 5.2 | 2.8 | 2.2 | 5.8 | 1.8 | 3.9 | 1.6 | 2.0 | 3.2 | 3.3 | 2.7 | 2.3 | 1.9 |
| 13.5 | 1083 | 2.1 | 1.8 | 6.1 | 1.8 | 2.6 | 6.1 | 1.7 | 3.0 | 1.8 | 1.8 | 3.6 | 3.8 | 3.4 | 2.9 | 2.7 |
| 14 | 978 | 2.2 | 2.0 | 6.0 | 1.9 | 2.7 | 6.2 | 1.5 | 3.1 | 1.9 | 1.8 | 3.6 | 3.5 | 3.6 | 3.1 | 2.6 |
| 17 | 841 | 1.6 | 2.1 | 4.6 | 1.3 | 2.0 | 6.1 | 1.3 | 3.1 | 1.7 | 1.7 | 4.2 | 3.6 | 4.6 | 3.8 | 3.5 |
| 21 | 572 | 1.8 | 1.2 | 2.8 | 1.6 | 1.2 | 4.5 | 1.9 | 2.6 | 0.9 | 1.4 | 3.7 | 4.7 | 6.5 | 3.7 | 5.1 |
| 24.5 | 534 | 1.1 | 0.9 | 3.2 | 1.5 | 0.9 | 2.4 | 1.9 | 2.8 | 0.8 | 1.3 | 2.8 | 3.4 | 5.1 | 3.8 | 5.1 |
| 28 | 376 | 0.5 | 0.5 | 2.1 | 1.3 | 1.3 | 1.9 | 1.3 | 2.4 | 1.6 | 0.8 | 2.1 | 2.4 | 2.4 | 4.3 | 5.1 |

Implied half-point value: e.g. at |spread| 3, +2.5 <-> +3 is 0.5 x 7.7 = 3.8 pts and +3 <-> +3.5 another 3.8; at 7, +6.5 <-> +7 is 2.9 pts; off-key half-points (e.g. 5 <-> 5.5) about 1 pt. No NFL values are used anywhere.

### Total landing rates P(total == k), % (conditioned on DK total anchor, +/-4)

- anchor 42.5 (n=881): 37: 3.9, 44: 3.9, 48: 3.8, 41: 3.5, 51: 3.3, 49: 3.2, 34: 3.1, 38: 3.1  (all others lower; full table in hist/landing_tables.json)
- anchor 48.5 (n=1945): 55: 3.9, 45: 3.8, 51: 3.7, 41: 3.5, 48: 3.3, 44: 3.2, 38: 2.9, 37: 2.9  (all others lower; full table in hist/landing_tables.json)
- anchor 52.5 (n=2258): 55: 4.5, 45: 3.8, 48: 3.3, 51: 3.3, 59: 3.1, 44: 2.9, 49: 2.8, 41: 2.8  (all others lower; full table in hist/landing_tables.json)
- anchor 55.5 (n=2213): 55: 4.6, 45: 3.5, 48: 3.4, 59: 3.2, 51: 3.1, 61: 2.9, 65: 2.8, 58: 2.6  (all others lower; full table in hist/landing_tables.json)
- anchor 58.5 (n=1876): 55: 4.4, 59: 4.1, 48: 3.3, 51: 3.1, 61: 3.1, 65: 2.9, 45: 2.9, 58: 2.8  (all others lower; full table in hist/landing_tables.json)
- anchor 62.5 (n=1205): 59: 4.2, 55: 3.6, 51: 3.1, 66: 3.1, 65: 3.0, 52: 2.9, 58: 2.9, 61: 2.7  (all others lower; full table in hist/landing_tables.json)
- anchor 66.5 (n=652): 55: 4.5, 51: 4.0, 69: 3.8, 65: 3.5, 66: 3.4, 52: 2.9, 59: 2.9, 41: 2.8  (all others lower; full table in hist/landing_tables.json)

### Verification
`CFB_DATE=20261024 python3 price_check.py 1102 --reuse oddsapi_20261024_1102.json` (no API call; `--reuse` evaluates the window as of the run time and never writes picks.csv). Same-number rows reproduce the original 11:02 run exactly (64/64 edges and shop-at prices identical); 16 off-number sides scored, 0 qualified, best -1.7 pts (SDSU@CSU OVER 58.5 vs DK 59.5). Test: `tests/test_offnum.sh`.
