# NHL SOG REBUILT Oct 12-16, 2026 (retro-computed point-in-time on gap-free data; NOT live decisions; logged closes, official actuals)

Dates: 20261012, 20261013, 20261014, 20261015, 20261016. Lines 515; status {'OK': 401, 'VOID_noC': 98, 'VOID_pulled_before_close': 10, 'VOID_dnp': 6}.

| slice | n lines (OK, with C) | games | mean z-CLV | 95% CI (game-clustered) | share moved for / against | lean hit vs no-vig fair (pts ± 1 SE; not break-even) | verdict |
|---|---|---|---|---|---|---|---|
| 20261012 | 32 | 2 | +0.0412 | [+0.0202, +0.0575] | 65.6% / 25.0% | 43.8% vs 52.2% (-8.5 ± 8.8) | too few games for a verdict (<5) |
| 20261013 | 154 | 10 | +0.0011 | [-0.0070, +0.0088] | 22.7% / 27.9% | 56.5% vs 51.2% (+5.3 ± 4.0) | no evidence of edge (CI includes 0) |
| 20261014 | 6 | 1 | +0.0000 | [+0.0000, +0.0000] | 16.7% / 16.7% | 16.7% vs 51.2% (-34.6 ± 20.4) | too few games for a verdict (<5) |
| 20261015 | 173 | 11 | +0.0055 | [-0.0068, +0.0161] | 30.6% / 23.7% | 51.4% vs 51.4% (-0.0 ± 3.8) | no evidence of edge (CI includes 0) |
| 20261016 | 36 | 2 | -0.0149 | [-0.0149, -0.0149] | 22.2% / 47.2% | 52.8% vs 51.4% (+1.3 ± 8.3) | too few games for a verdict (<5) |
| **all** | 401 | 26 | +0.0047 | [-0.0027, +0.0131] | 29.4% / 27.4% | 52.4% vs 51.4% (+1.0 ± 2.5) | no evidence of edge (CI includes 0) |
| all, lean >= 5 pts | 147 | 26 | +0.0106 | [+0.0019, +0.0205] | 34.0% / 27.2% | 57.8% vs 52.1% (+5.7 ± 4.1) | positive CLV |
| all, lean < 5 pts | 254 | 26 | +0.0013 | [-0.0079, +0.0109] | 26.8% / 27.6% | 49.2% vs 51.0% (-1.8 ± 3.1) | no evidence of edge (CI includes 0) |

Picks carried in D files: 0 graded (lists were built from the sheet, not the D file; real bets live in props-finder/user_bets, kept separate).

Slices with < 5 games get no verdict: a game-clustered CI needs more clusters. Read the pooled rows. PENDING_no_box = box score not posted yet (re-run grade.py).

z-CLV is in logit units: +0.04 is about +1 point of probability near 50%. A sample this size cannot separate a 1-2 point edge from zero.

## Pre-noon PT exclusion (draft prereg)

Eligible graded-track games have puck drop at or after 12:00 PM America/Los_Angeles. From 20261017 on, earlier games are marked `excluded_pre_noon` and left out of every scored slice (CLV table, model-only paper track, Fliff list). Start times come from saved captures, else api-web.nhle.com.

No pre-noon games in the enforced window (no dates >= 20261017 in this report).

### Earlier days (before enforcement) — info only, logged files unchanged

- **20261012**: 0 pre-noon graded rows.
- **20261013**: 0 pre-noon graded rows.
- **20261014**: 0 pre-noon graded rows.
- **20261015**: 0 pre-noon graded rows.
- **20261016**: 0 pre-noon graded rows.

Headline champion numbers with pre-noon OK rows excluded: **unchanged** (no pre-noon OK rows in these dates).

## Model-only paper track (raw model side, edge vs no-vig >= 1 pt, flat 1 u at the captured price; blend ignored)

| track | book | bets (games) | W-L | units | ROI (95% CI, game-clustered) | z-CLV of those sides (95% CI) | hit vs no-vig fair (not break-even) |
|---|---|---|---|---|---|---|---|
| champion c3ab760178, 20261012 | DK | 28 (2 g) | 13-15 | -5.94 u | -21.2% [-55.7%, +1.1%] | +0.0386 [+0.0110, +0.0565] | 46.4% vs 52.8% |
| champion c3ab760178, 20261013 | DK | 135 (10 g) | 78-57 | +9.40 u | +7.0% [-2.7%, +15.6%] | -0.0000 [-0.0059, +0.0055] | 57.8% vs 50.9% |
| champion c3ab760178, 20261014 | DK | 5 (1 g) | 1-4 | -3.26 u | -65.2% [-65.2%, -65.2%] | +0.0081 [+0.0081, +0.0081] | 20.0% vs 50.8% |
| champion c3ab760178, 20261015 | DK | 141 (11 g) | 71-70 | -11.23 u | -8.0% [-19.3%, +5.4%] | +0.0069 [-0.0017, +0.0157] | 50.4% vs 51.1% |
| champion c3ab760178, 20261016 | DK | 33 (2 g) | 19-14 | +1.17 u | +3.5% [-7.6%, +14.0%] | -0.0153 [-0.0159, -0.0148] | 57.6% vs 51.3% |
| **champion c3ab760178, all** | DK | 342 (26 g) | 182-160 | -9.86 u | -2.9% [-11.8%, +5.3%] | +0.0047 [-0.0015, +0.0124] | 53.2% vs 51.2% |
| champion c3ab760178, all | Fliff | not captured | | | | | |
| challenger 3386583f18, 20261012 | DK | 27 (2 g) | 13-14 | -4.85 u | -17.9% [-41.2%, +7.1%] | +0.0312 [+0.0086, +0.0555] | 48.1% vs 52.8% |
| challenger 3386583f18, 20261013 | DK | 138 (10 g) | 83-55 | +16.89 u | +12.2% [+2.8%, +22.7%] | +0.0005 [-0.0042, +0.0052] | 60.1% vs 51.1% |
| challenger 3386583f18, 20261014 | DK | 6 (1 g) | 2-4 | -2.65 u | -44.2% [-44.2%, -44.2%] | +0.0000 [+0.0000, +0.0000] | 33.3% vs 53.8% |
| challenger 3386583f18, 20261015 | DK | 143 (11 g) | 77-66 | -1.93 u | -1.4% [-11.5%, +10.5%] | +0.0119 [+0.0035, +0.0202] | 53.8% vs 51.0% |
| challenger 3386583f18, 20261016 | DK | 31 (2 g) | 18-13 | +1.41 u | +4.6% [-2.6%, +11.3%] | -0.0064 [-0.0144, +0.0010] | 58.1% vs 51.5% |
| **challenger 3386583f18, all** | DK | 345 (26 g) | 193-152 | +8.87 u | +2.6% [-5.5%, +10.6%] | +0.0070 [+0.0013, +0.0134] | 55.9% vs 51.2% |
| challenger 3386583f18, all | Fliff | not captured | | | | | |

Paper only: flat 1 unit per side at the DraftKings price captured in the D snapshot. Not bets placed; real bets live in props-finder/user_bets.

## Fliff list (as posted): paper track at the real captured Fliff price (from Oct 17)

No Fliff price captures for these dates yet (fliff_prices.py starts Oct 17).

## Your own betting results (real bets you logged; not a model test)

| book / sport | bets | W-L-P | risked | profit | ROI |
|---|---|---|---|---|---|
| draftkings / nfl | 1 | 1-0-0 | $0.50 | $+0.49 | +98.0% |
| draftkings / nhl | 10 | 3-7-0 | $1.80 | $-1.30 | -72.2% |
| fliff / ncaaf | 4 | 3-1-0 | $0.40 | $+0.14 | +35.0% |
| fliff / nfl | 2 | 1-1-0 | $0.20 | $-0.01 | -5.0% |
| fliff / nhl | 4 | 3-1-0 | $0.40 | $+0.10 | +25.0% |
| **all** | 21 | 11-10-0 | $3.30 | $-0.58 | -17.6% |

These are the bets you chose and placed (some at DraftKings instead of Fliff, some from lists later found flawed, e.g. Oct 13 NHL). They show how your own betting is doing, not whether the model works; the model is judged by the paper tracks above.
