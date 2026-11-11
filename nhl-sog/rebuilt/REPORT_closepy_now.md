# NHL SOG REBUILT Oct 12-16 (strict re-grade with today's close.py; fewer closes on Oct 12-13)

Dates: 20261012, 20261013, 20261014, 20261015, 20261016. Lines 515; status {'OK': 330, 'VOID_noC': 169, 'VOID_pulled_before_close': 10, 'VOID_dnp': 6}.

| slice | n lines (OK, with C) | games | mean z-CLV | 95% CI (game-clustered) | share moved for / against | lean hit vs no-vig fair (pts ± 1 SE; not break-even) | verdict |
|---|---|---|---|---|---|---|---|
| 20261012 | 14 | 1 | +0.0202 | [+0.0202, +0.0202] | 50.0% / 28.6% | 28.6% vs 51.2% (-22.6 ± 13.4) | too few games for a verdict (<5) |
| 20261013 | 101 | 7 | +0.0011 | [-0.0058, +0.0084] | 20.8% / 27.7% | 56.4% vs 51.4% (+5.0 ± 5.0) | no evidence of edge (CI includes 0) |
| 20261014 | 6 | 1 | +0.0000 | [+0.0000, +0.0000] | 16.7% / 16.7% | 16.7% vs 51.2% (-34.6 ± 20.4) | too few games for a verdict (<5) |
| 20261015 | 173 | 11 | +0.0055 | [-0.0068, +0.0161] | 30.6% / 23.7% | 51.4% vs 51.4% (-0.0 ± 3.8) | no evidence of edge (CI includes 0) |
| 20261016 | 36 | 2 | -0.0149 | [-0.0149, -0.0149] | 22.2% / 47.2% | 52.8% vs 51.4% (+1.3 ± 8.3) | too few games for a verdict (<5) |
| **all** | 330 | 22 | +0.0025 | [-0.0049, +0.0095] | 27.3% / 27.6% | 51.5% vs 51.4% (+0.1 ± 2.8) | no evidence of edge (CI includes 0) |
| all, lean >= 5 pts | 112 | 22 | +0.0076 | [-0.0015, +0.0168] | 33.0% / 29.5% | 55.4% vs 52.2% (+3.1 ± 4.7) | no evidence of edge (CI includes 0) |
| all, lean < 5 pts | 218 | 22 | -0.0002 | [-0.0109, +0.0097] | 24.3% / 26.6% | 49.5% vs 51.0% (-1.4 ± 3.4) | no evidence of edge (CI includes 0) |

Picks carried in D files: 0 graded (lists were built from the sheet, not the D file; real bets live in props-finder/user_bets, kept separate).

Slices with < 5 games get no verdict: a game-clustered CI needs more clusters. Read the pooled rows. PENDING_no_box = box score not posted yet (re-run grade.py).

z-CLV is in logit units: +0.04 is about +1 point of probability near 50%. A sample this size cannot separate a 1-2 point edge from zero.

## Model-only paper track (raw model side, edge vs no-vig >= 1 pt, flat 1 u at the captured price; blend ignored)

| track | book | bets (games) | W-L | units | ROI (95% CI, game-clustered) | z-CLV of those sides (95% CI) | hit vs no-vig fair (not break-even) |
|---|---|---|---|---|---|---|---|
| champion c3ab760178, 20261012 | DK | 11 (1 g) | 3-8 | -6.12 u | -55.7% [-55.7%, -55.7%] | +0.0110 [+0.0110, +0.0110] | 27.3% vs 51.5% |
| champion c3ab760178, 20261013 | DK | 89 (7 g) | 51-38 | +5.43 u | +6.1% [-9.2%, +17.9%] | -0.0020 [-0.0086, +0.0041] | 57.3% vs 51.3% |
| champion c3ab760178, 20261014 | DK | 5 (1 g) | 1-4 | -3.26 u | -65.2% [-65.2%, -65.2%] | +0.0081 [+0.0081, +0.0081] | 20.0% vs 50.8% |
| champion c3ab760178, 20261015 | DK | 141 (11 g) | 71-70 | -11.23 u | -8.0% [-19.3%, +5.4%] | +0.0069 [-0.0017, +0.0157] | 50.4% vs 51.1% |
| champion c3ab760178, 20261016 | DK | 33 (2 g) | 19-14 | +1.17 u | +3.5% [-7.6%, +14.0%] | -0.0153 [-0.0159, -0.0148] | 57.6% vs 51.3% |
| **champion c3ab760178, all** | DK | 279 (22 g) | 145-134 | -14.02 u | -5.0% [-15.0%, +4.3%] | +0.0016 [-0.0039, +0.0075] | 52.0% vs 51.2% |
| champion c3ab760178, all | Fliff | not captured | | | | | |
| challenger 3386583f18, 20261012 | DK | 14 (1 g) | 5-9 | -5.77 u | -41.2% [-41.2%, -41.2%] | +0.0086 [+0.0086, +0.0086] | 35.7% vs 52.4% |
| challenger 3386583f18, 20261013 | DK | 92 (7 g) | 56-36 | +13.67 u | +14.9% [+0.7%, +29.3%] | -0.0019 [-0.0068, +0.0028] | 60.9% vs 51.0% |
| challenger 3386583f18, 20261014 | DK | 6 (1 g) | 2-4 | -2.65 u | -44.2% [-44.2%, -44.2%] | +0.0000 [+0.0000, +0.0000] | 33.3% vs 53.8% |
| challenger 3386583f18, 20261015 | DK | 143 (11 g) | 77-66 | -1.93 u | -1.4% [-11.5%, +10.5%] | +0.0119 [+0.0035, +0.0202] | 53.8% vs 51.0% |
| challenger 3386583f18, 20261016 | DK | 31 (2 g) | 18-13 | +1.41 u | +4.6% [-2.6%, +11.3%] | -0.0064 [-0.0144, +0.0010] | 58.1% vs 51.5% |
| **challenger 3386583f18, all** | DK | 286 (22 g) | 158-128 | +4.74 u | +1.7% [-8.2%, +11.0%] | +0.0051 [-0.0004, +0.0109] | 55.2% vs 51.2% |
| challenger 3386583f18, all | Fliff | not captured | | | | | |

Paper only: flat 1 unit per side at the DraftKings price captured in the D snapshot. Not bets placed; real bets live in props-finder/user_bets.
