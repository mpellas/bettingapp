# Item #4: over bias calibrated by direction (paper only)
Copy: `nhl-sog-copy/` (cp -a, diff -rq clean before running; later diffs are only live Oct 31 captures). Script: `analyze.py`. No credits; 47 results from free NHL.com box scores, 1199 from graded/.

Sample: 1633 gate rows -> 1246 player-games (latest pass >=150 min before puck drop, through Oct 30) -> 2492 sides (over+under each). Edge = p_model - break-even at the DK price (-110 if no price).
Note: over and under are complements, so Brier/log loss are identical by direction; direction only matters in bias and edge slices.

## 1. Scores (`scores_by_direction.csv`, `reliability_by_direction.csv`)
| prob | Brier | log loss |
|---|---|---|
| model | 0.2461 | 0.6853 |
| blend | 0.2450 | 0.6830 |
| DK no-vig | 0.2451 | 0.6833 |
Model minus no-vig Brier: 95% CI -0.0022 to +0.0044 (not separable).

## 2. Bias (`bias_by_direction.csv`), bias = mean pred - hit rate
- Overall: overs +0.5 pts (CI -2.4 to +3.3), unders -0.5. **No general over lean.**
- By line and F/D: all within ±4.4 pts, every CI spans 0.
- By edge: the bias is in the tails, both directions. Overs 2.5-5 edge +13.3 (CI +1.9 to +25), 5-10 edge +20.7 (n=23, CI -1.8 to +40). Unders 5-10 edge +12.7 (n=104, CI +3.1 to +22.2).
- All 5+ edge sides: overs 9-14 (39% vs 53% break-even) -5.02u; unders 73-66 (52.5% vs 55%) -8.62u.

## 3. Fix fit through Oct 22 (660), tested Oct 23-30 (586) (`fix_oos.csv`, `fix_params.json`)
| fix | test Brier | test log loss |
|---|---|---|
| raw | 0.2456 | 0.6847 |
| intercept shift (+0.005 logit) | 0.2457 | 0.6848 |
| Platt (a=-0.03, b=0.67) | 0.2450 | 0.6831 |
| shrink 52% toward no-vig (logit) | **0.2439** | **0.6810** |
| no-vig alone | 0.2439 | 0.6809 |
Shrink vs raw test Brier: CI -0.0040 to +0.0007 (includes 0).
5+ edge list on test with shrink (`edge5_list_changes_test.csv`): raw 65 sides -> 4 kept (unders 1-3, -2.17u). Dropped 61: overs 3-8 -4.81u, unders 26-24 -4.21u. No sides added.

## 4. Sample size
1246 graded player-games pass the ~100 rule for overall calibration, but no fix's Brier gain has a CI excluding 0. The 5+ over bucket is only 23. Tail overconfidence for unders at 5-10 is the only slice whose CI excludes 0.
