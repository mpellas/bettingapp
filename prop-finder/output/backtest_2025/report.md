# Prop Finder: 2025 full-season walk-forward backtest
_Generated 2026-10-04 12:03 PM PT._

**Read this first.** Real historical prop lines were found **for NFL weeks 1-13 only** (ESPN BET opening lines, ESPN core API). There are no usable real lines for NFL weeks 14-18 (ESPN serves only DraftKings there and its propBets return 404) or for **any FBS game** (ESPN serves only unpriced alternate-line ladder rungs for college, so the main line can't be identified). Every result marked **SYNTHETIC** is graded against a proxy line (floor(trailing-5-game average) + 0.5 at -110). That isn't a market line, and SYNTHETIC hit rates/ROI are not betting results.

## Bottom line
- **Real lines (NFL weeks 2-13, 7095 graded bets, pre-backtest settings):** every line: 51.9% hit, -1.0% ROI at -110 (-5.5% at the listed prices). Always betting the under (no model) gave 52.7% / +0.6%.
- **Top 25/week:** 55.0%, +5.0% over weeks 2-13. All of the profit came from weeks 2-9 (+12.6%); held-out weeks 10-13 were -10.3%. The model shows no reliable edge over the opening market. Its probabilities are worse than the no-vig market's (Brier 0.25896 vs 0.24606).
- **Calibration:** the pre-backtest P(side) was strongly overconfident (picks rated 60-65% won ~50%). Calibrated P_SHRINK 0.2 cut held-out log-loss 0.7144 -> 0.69196.
- **After tuning (held-out real lines, weeks 10-13):** top-25 47.0%/-10.3% -> 49.5%/-5.5%; top-10 -33.2% -> -4.5%. That's about 100 bets, which is within noise (1 SE of hit rate is about 5 pts), so it's still negative ROI.
- **FBS:** no real lines exist, so only projection accuracy and the SYNTHETIC proxy are available. Tuning improved held-out normalized MAE. Ablations (held-out normalized MAE change if removed): the portal-aware 2024 prior +0.0082, the SP+ opponent adjustment +0.0045, the level-jump factor +0.0000. Positive means removing it hurts, so the level-jump showed no measurable effect.

## Method
- Walk-forward: for week W the live code (`analysis.build_projections` + `analysis.rank_props`, and for FBS `cfb_context.make_ctx`) sees only current-season games before W, the full 2024 season, team scoring before W, the week-W official NFL injury report (nflverse), and closing spread/total implied team totals (NFL: nflverse; FBS: median of CFBD /lines providers). No weather adjustment (no archived forecasts).
- NFL weeks 2-18 (week 1 has no current-season game, which the live model needs). FBS weeks 2-16 (CFBD week numbering; week 1 includes week-0 games).
- FBS: 2024 player stats are the prior. CFBD/ESPN athlete IDs and the CFBD 2025 transfer portal carry each player's 2024 production to his 2025 school, with the live level-jump, opponent-strength (SP+) and role/opportunity-share logic. **SP+ as-of: 2024 final SP+ is used as the 2025 rating all season** (CFBD's 2025 SP+ is end-of-season, which would leak). Conference strength = 2025 membership x 2024 ratings.
- Real-line grading uses the **opening** main line and opening prices. ESPN's 'current' line has lastUpdated stamps after kickoff (e.g. DAL@PHI week 1: Hurts pass yds opened 214.5 and was last listed at 186.5), so it may include in-game moves. It's shown only as a sensitivity check.
- Grading: actual > line = over. A player with no stat row in that game is a void (refund). ROI is per 1-unit bet at -110 unless noted; `roi_price` uses the listed opening prices.
- Tuning protocol: knobs are chosen on weeks 2-9 only and applied only if they also improve weeks 10+ (held-out). Projection knobs use normalized MAE (model MAE / trailing-season-average MAE, averaged over stats). P(over) shrink uses log-loss on real NFL lines (tune weeks 2-9, held-out weeks 10-13).

## Data coverage
| item | value |
|---|---|
| NFL games (weeks 2-18 projected) | 256 |
| NFL games with ESPN BET historical props (weeks 1-13) | 193 |
| NFL main O/U lines parsed (all weeks, opening line present) | 8626 |
| NFL real lines matched to a projection (weeks 2-13) | 7147 |
| NFL real-line bets graded (win/loss) | 7095 |
| NFL real-line voids (no stat row: inactive/DNP) | 52 |
| NFL players projected (unique) | 373 |
| NFL player-stat projections | 22120 |
| FBS games (weeks 2-16, >=1 FBS team) | 792 |
| FBS games with implied totals (CFBD /lines) | 792 |
| FBS games where ESPN serves historical prop items | 304 |
| FBS prop items (alternate-ladder rungs, unpriced) | 54347 |
| FBS priced main O/U lines found | 0 |
| FBS players projected (unique) | 2456 |
| FBS player-stat projections | 85288 |
| FBS projections with a 2024 prior | 66458 |
| FBS projections for 2024->2025 school movers | 24385 |
| CFBD network calls (all time, data/cfbd/calls.log) | 52 |
| CFBD calls remaining this month (from /info) | 953 |


## Headline results (live settings)
| set | bets | wins | losses | voids | hit_rate | roi_110 | roi_price | units_110 |
|---|---|---|---|---|---|---|---|---|
| REAL NFL: all lines | 7095 | 3680 | 3415 | 52 | 51.9% | -1.0% | -5.5% | -69.55 |
| REAL NFL: top 10/week | 120 | 62 | 58 | 0 | 51.7% | -1.4% | +0.9% | -1.64 |
| REAL NFL: top 25/week | 300 | 165 | 135 | 0 | 55.0% | +5.0% | +7.0% | 15 |
| REAL NFL: rank_score >= 0 | 5254 | 2662 | 2592 | 39 | 50.7% | -3.3% | -5.4% | -172 |
| REAL NFL: rank_score >= 5 | 2869 | 1457 | 1412 | 23 | 50.8% | -3.0% | -3.9% | -87.45 |
| REAL NFL: rank_score >= 10 | 1228 | 630 | 598 | 9 | 51.3% | -2.1% | -1.9% | -25.27 |
| REAL NFL: rank_score >= 15 | 451 | 251 | 200 | 0 | 55.6% | +6.2% | +7.9% | 28.18 |
| REAL NFL: rank_score >= 20 | 152 | 87 | 65 | 0 | 57.2% | +9.3% | +12.0% | 14.09 |
| REAL NFL: NAIVE always UNDER (no model) | 7095 | 3740 | 3355 | 52 | 52.7% | +0.6% | -1.8% | 45 |
| REAL NFL: NAIVE always OVER (no model) | 7095 | 3355 | 3740 | 52 | 47.3% | -9.7% | -10.4% | -690 |
| SYNTHETIC NFL: all lines | 16840 | 10303 | 6537 | 5280 | 61.2% | +16.8% | +16.8% | 2829 |
| SYNTHETIC NFL: top 10/week | 152 | 124 | 28 | 18 | 81.6% | +55.7% | +55.7% | 84.73 |
| SYNTHETIC NFL: top 25/week | 389 | 328 | 61 | 36 | 84.3% | +61.0% | +61.0% | 237.2 |
| SYNTHETIC NFL: rank_score >= 0 | 14439 | 9175 | 5264 | 3291 | 63.5% | +21.3% | +21.3% | 3077 |
| SYNTHETIC NFL: rank_score >= 5 | 9140 | 6259 | 2881 | 1457 | 68.5% | +30.7% | +30.7% | 2809 |
| SYNTHETIC NFL: rank_score >= 10 | 5410 | 3908 | 1502 | 665 | 72.2% | +37.9% | +37.9% | 2051 |
| SYNTHETIC NFL: rank_score >= 15 | 3038 | 2307 | 731 | 280 | 75.9% | +45.0% | +45.0% | 1366 |
| SYNTHETIC NFL: rank_score >= 20 | 1554 | 1225 | 329 | 103 | 78.8% | +50.5% | +50.5% | 784.6 |
| SYNTHETIC NFL: NAIVE always UNDER (no model) | 16840 | 10244 | 6596 | 5280 | 60.8% | +16.1% | +16.1% | 2717 |
| SYNTHETIC NFL: NAIVE always OVER (no model) | 16840 | 6596 | 10244 | 5280 | 39.2% | -25.2% | -25.2% | -4248 |
| SYNTHETIC FBS: all lines | 60698 | 37049 | 23649 | 24590 | 61.0% | +16.5% | +16.5% | 1.003e+04 |
| SYNTHETIC FBS: top 10/week | 128 | 108 | 20 | 22 | 84.4% | +61.1% | +61.1% | 78.18 |
| SYNTHETIC FBS: top 25/week | 309 | 261 | 48 | 66 | 84.5% | +61.3% | +61.3% | 189.3 |
| SYNTHETIC FBS: rank_score >= 0 | 52508 | 33328 | 19180 | 20412 | 63.5% | +21.2% | +21.2% | 1.112e+04 |
| SYNTHETIC FBS: rank_score >= 5 | 33412 | 22606 | 10806 | 9432 | 67.7% | +29.2% | +29.2% | 9745 |
| SYNTHETIC FBS: rank_score >= 10 | 19725 | 13964 | 5761 | 4637 | 70.8% | +35.1% | +35.1% | 6934 |
| SYNTHETIC FBS: rank_score >= 15 | 11333 | 8377 | 2956 | 2301 | 73.9% | +41.1% | +41.1% | 4659 |
| SYNTHETIC FBS: rank_score >= 20 | 5964 | 4563 | 1401 | 985 | 76.5% | +46.1% | +46.1% | 2747 |
| SYNTHETIC FBS: NAIVE always UNDER (no model) | 60698 | 37331 | 23367 | 24590 | 61.5% | +17.4% | +17.4% | 1.057e+04 |
| SYNTHETIC FBS: NAIVE always OVER (no model) | 60698 | 23367 | 37331 | 24590 | 38.5% | -26.5% | -26.5% | -1.609e+04 |
| SENSITIVITY NFL last-listed line: all lines | 7092 | 3588 | 3504 | 52 | 50.6% | -3.4% | -7.1% | -242.2 |
| SENSITIVITY NFL last-listed line: top 10/week | 120 | 57 | 63 | 0 | 47.5% | -9.3% | -8.7% | -11.18 |
| SENSITIVITY NFL last-listed line: top 25/week | 297 | 153 | 144 | 3 | 51.5% | -1.7% | -2.2% | -4.91 |
| SENSITIVITY NFL last-listed line: rank_score >= 0 | 5248 | 2625 | 2623 | 42 | 50.0% | -4.5% | -6.9% | -236.6 |
| SENSITIVITY NFL last-listed line: rank_score >= 5 | 2839 | 1453 | 1386 | 25 | 51.2% | -2.3% | -3.9% | -65.09 |
| SENSITIVITY NFL last-listed line: rank_score >= 10 | 1190 | 606 | 584 | 9 | 50.9% | -2.8% | -3.2% | -33.09 |
| SENSITIVITY NFL last-listed line: rank_score >= 15 | 415 | 210 | 205 | 3 | 50.6% | -3.4% | -3.6% | -14.09 |
| SENSITIVITY NFL last-listed line: rank_score >= 20 | 112 | 57 | 55 | 0 | 50.9% | -2.8% | -2.3% | -3.18 |
| SENSITIVITY NFL last-listed line: NAIVE always UNDER (no model) | 7092 | 3736 | 3356 | 52 | 52.7% | +0.6% | -1.5% | 40.36 |
| SENSITIVITY NFL last-listed line: NAIVE always OVER (no model) | 7092 | 3356 | 3736 | 52 | 47.3% | -9.7% | -11.2% | -685.1 |

At the listed opening prices (all real NFL lines): 7095 bets, hit 51.9%, ROI -5.5%.

Probability quality on real NFL lines with both opening prices (6476 rows): model Brier 0.25896 vs no-vig market 0.24606; log-loss 0.71366 vs 0.68484 (lower is better).

### Calibration (model probability of the picked side vs actual hit rate)
| bucket | bets | mean_pred | hit_rate | set |
|---|---|---|---|---|
| [0.5, 0.525) | 1077 | 51.3% | 51.2% | REAL NFL |
| [0.525, 0.55) | 1040 | 53.7% | 50.4% | REAL NFL |
| [0.55, 0.575) | 992 | 56.2% | 50.0% | REAL NFL |
| [0.575, 0.6) | 859 | 58.7% | 50.5% | REAL NFL |
| [0.6, 0.65) | 1371 | 62.2% | 50.3% | REAL NFL |
| [0.65, 0.7) | 910 | 67.3% | 54.3% | REAL NFL |
| [0.7, 0.8) | 677 | 73.8% | 56.6% | REAL NFL |
| [0.8, 1.0) | 169 | 83.6% | 63.3% | REAL NFL |
| [0.5, 0.525) | 2447 | 51.2% | 50.0% | SYNTHETIC NFL |
| [0.525, 0.55) | 2393 | 53.7% | 54.3% | SYNTHETIC NFL |
| [0.55, 0.575) | 2278 | 56.2% | 54.2% | SYNTHETIC NFL |
| [0.575, 0.6) | 1893 | 58.6% | 59.1% | SYNTHETIC NFL |
| [0.6, 0.65) | 3216 | 62.3% | 62.8% | SYNTHETIC NFL |
| [0.65, 0.7) | 2192 | 67.3% | 69.3% | SYNTHETIC NFL |
| [0.7, 0.8) | 2183 | 74.3% | 77.2% | SYNTHETIC NFL |
| [0.8, 1.0) | 238 | 81.4% | 84.9% | SYNTHETIC NFL |
| [0.5, 0.525) | 7934 | 51.2% | 50.2% | SYNTHETIC FBS |
| [0.525, 0.55) | 7540 | 53.7% | 52.2% | SYNTHETIC FBS |
| [0.55, 0.575) | 6833 | 56.2% | 54.1% | SYNTHETIC FBS |
| [0.575, 0.6) | 6360 | 58.7% | 57.5% | SYNTHETIC FBS |
| [0.6, 0.65) | 10592 | 62.4% | 60.4% | SYNTHETIC FBS |
| [0.65, 0.7) | 8325 | 67.4% | 66.4% | SYNTHETIC FBS |
| [0.7, 0.8) | 10863 | 74.4% | 74.1% | SYNTHETIC FBS |
| [0.8, 1.0) | 2251 | 83.0% | 80.1% | SYNTHETIC FBS |
| [0.5, 0.525) | 4146 | 51.2% | 49.8% | REAL NFL (tuned) |
| [0.525, 0.55) | 2065 | 53.5% | 52.0% | REAL NFL (tuned) |
| [0.55, 0.575) | 656 | 55.9% | 55.6% | REAL NFL (tuned) |
| [0.575, 0.6) | 218 | 58.5% | 63.8% | REAL NFL (tuned) |
| [0.6, 0.65) | 10 | 60.0% | 60.0% | REAL NFL (tuned) |


### By side (over / under)
| set | pick | bets | hit_rate | roi_110 |
|---|---|---|---|---|
| REAL NFL all | OVER | 3886 | 49.2% | -6.0% |
| REAL NFL all | UNDER | 3209 | 55.1% | +5.1% |
| REAL NFL top25/wk | OVER | 158 | 53.2% | +1.5% |
| REAL NFL top25/wk | UNDER | 142 | 57.0% | +8.9% |
| SYNTHETIC NFL all | OVER | 6921 | 50.4% | -3.7% |
| SYNTHETIC NFL all | UNDER | 9919 | 68.7% | +31.1% |
| SYNTHETIC FBS all | OVER | 21804 | 49.4% | -5.8% |
| SYNTHETIC FBS all | UNDER | 38894 | 67.6% | +29.0% |
| SYNTHETIC FBS top25/wk | OVER | 1 | 0.0% | -100.0% |
| SYNTHETIC FBS top25/wk | UNDER | 308 | 84.7% | +61.8% |


### By stat
| set | stat | bets | hit_rate | roi_110 |
|---|---|---|---|---|
| REAL NFL all | attempts | 331 | 52.9% | +0.9% |
| REAL NFL all | carries | 598 | 53.8% | +2.8% |
| REAL NFL all | completions | 331 | 51.7% | -1.4% |
| REAL NFL all | interceptions | 331 | 55.3% | +5.5% |
| REAL NFL all | pass_rush_yds | 298 | 52.3% | -0.1% |
| REAL NFL all | pass_tds | 330 | 51.5% | -1.7% |
| REAL NFL all | pass_yds | 329 | 51.7% | -1.4% |
| REAL NFL all | rec_yds | 1632 | 51.0% | -2.7% |
| REAL NFL all | receptions | 1642 | 51.7% | -1.3% |
| REAL NFL all | rush_rec_yds | 421 | 51.8% | -1.1% |
| REAL NFL all | rush_yds | 852 | 50.9% | -2.8% |
| REAL NFL top25/wk | attempts | 29 | 44.8% | -14.4% |
| REAL NFL top25/wk | carries | 57 | 57.9% | +10.5% |
| REAL NFL top25/wk | completions | 20 | 25.0% | -52.3% |
| REAL NFL top25/wk | interceptions | 4 | 100.0% | +90.9% |
| REAL NFL top25/wk | pass_rush_yds | 7 | 28.6% | -45.5% |
| REAL NFL top25/wk | pass_tds | 1 | 0.0% | -100.0% |
| REAL NFL top25/wk | pass_yds | 7 | 42.9% | -18.2% |
| REAL NFL top25/wk | rec_yds | 33 | 57.6% | +9.9% |
| REAL NFL top25/wk | receptions | 88 | 58.0% | +10.6% |
| REAL NFL top25/wk | rush_rec_yds | 25 | 56.0% | +6.9% |
| REAL NFL top25/wk | rush_yds | 29 | 72.4% | +38.2% |
| SYNTHETIC NFL all | attempts | 517 | 63.6% | +21.5% |
| SYNTHETIC NFL all | carries | 1369 | 60.0% | +14.5% |
| SYNTHETIC NFL all | completions | 517 | 63.6% | +21.5% |
| SYNTHETIC NFL all | interceptions | 517 | 59.2% | +13.0% |
| SYNTHETIC NFL all | pass_rush_yds | 517 | 60.4% | +15.2% |
| SYNTHETIC NFL all | pass_tds | 517 | 64.6% | +23.3% |
| SYNTHETIC NFL all | pass_yds | 517 | 58.0% | +10.8% |
| SYNTHETIC NFL all | rec_yds | 2916 | 56.6% | +8.2% |
| SYNTHETIC NFL all | receptions | 2916 | 59.2% | +13.1% |
| SYNTHETIC NFL all | rush_rec_tds | 2916 | 73.8% | +41.0% |
| SYNTHETIC NFL all | rush_rec_yds | 2252 | 56.5% | +7.8% |
| SYNTHETIC NFL all | rush_yds | 1369 | 56.1% | +7.1% |
| SYNTHETIC FBS all | attempts | 1691 | 54.6% | +4.3% |
| SYNTHETIC FBS all | carries | 5307 | 58.3% | +11.3% |
| SYNTHETIC FBS all | completions | 1691 | 56.4% | +7.7% |
| SYNTHETIC FBS all | interceptions | 1691 | 62.0% | +18.3% |
| SYNTHETIC FBS all | pass_rush_yds | 1691 | 58.6% | +11.9% |
| SYNTHETIC FBS all | pass_tds | 1691 | 62.2% | +18.8% |
| SYNTHETIC FBS all | pass_yds | 1691 | 57.5% | +9.8% |
| SYNTHETIC FBS all | rec_yds | 10364 | 55.2% | +5.4% |
| SYNTHETIC FBS all | receptions | 10364 | 59.4% | +13.3% |
| SYNTHETIC FBS all | rush_rec_tds | 10364 | 75.8% | +44.7% |
| SYNTHETIC FBS all | rush_rec_yds | 8846 | 58.2% | +11.0% |
| SYNTHETIC FBS all | rush_yds | 5307 | 59.2% | +13.0% |


### Weekly (REAL NFL, all lines and top 25)
| week | bets_all | hit_rate_all | roi_110_all | bets_top25 | hit_rate_top25 | roi_110_top25 |
|---|---|---|---|---|---|---|
| 2 | 629 | 52.3% | -0.1% | 25 | 40.0% | -23.6% |
| 3 | 632 | 52.1% | -0.6% | 25 | 52.0% | -0.7% |
| 4 | 626 | 52.2% | -0.3% | 25 | 60.0% | +14.5% |
| 5 | 566 | 50.9% | -2.9% | 25 | 64.0% | +22.2% |
| 6 | 594 | 52.4% | -0.1% | 25 | 48.0% | -8.4% |
| 7 | 615 | 54.0% | +3.1% | 25 | 84.0% | +60.4% |
| 8 | 519 | 47.2% | -9.9% | 25 | 64.0% | +22.2% |
| 9 | 588 | 52.9% | +1.0% | 25 | 60.0% | +14.5% |
| 10 | 557 | 49.0% | -6.4% | 25 | 20.0% | -61.8% |
| 11 | 602 | 51.0% | -2.6% | 25 | 52.0% | -0.7% |
| 12 | 560 | 54.8% | +4.7% | 25 | 60.0% | +14.5% |
| 13 | 607 | 52.9% | +1.0% | 25 | 56.0% | +6.9% |


## Projection accuracy (all projected player-stats that played, live settings)
| league | stat | n | mean_actual | model_mae | model_bias | season_avg_mae | l5_avg_mae | mae_vs_season_avg_pct |
|---|---|---|---|---|---|---|---|---|
| nfl | attempts | 517 | 29.51 | 7.863 | 1.758 | 8.236 | 8.24 | -4.5 |
| nfl | carries | 1369 | 8.43 | 3.268 | 0.043 | 3.334 | 3.332 | -2 |
| nfl | completions | 517 | 19.02 | 5.422 | 1.206 | 5.776 | 5.764 | -6.1 |
| nfl | interceptions | 517 | 0.65 | 0.664 | -0.015 | 0.707 | 0.708 | -6.1 |
| nfl | pass_rush_yds | 517 | 226 | 67.06 | 10.72 | 70.1 | 70.84 | -4.3 |
| nfl | pass_tds | 517 | 1.42 | 0.968 | 0.035 | 1.021 | 1.023 | -5.2 |
| nfl | pass_yds | 517 | 210 | 65.78 | 8.942 | 68.45 | 69.28 | -3.9 |
| nfl | rec_yds | 2916 | 32.56 | 20.18 | 1.246 | 20.91 | 20.82 | -3.4 |
| nfl | receptions | 2916 | 2.93 | 1.52 | 0.159 | 1.565 | 1.57 | -2.9 |
| nfl | rush_rec_tds | 2916 | 0.34 | 0.454 | -0.004 | 0.448 | 0.442 | 1.3 |
| nfl | rush_rec_yds | 2252 | 51.79 | 27.19 | 1.393 | 27.99 | 27.93 | -2.9 |
| nfl | rush_yds | 1369 | 37.16 | 20.52 | 0.167 | 20.73 | 20.92 | -1 |
| ncaaf | attempts | 1691 | 25.71 | 8.532 | 0.693 | 8.525 | 8.546 | 0.1 |
| ncaaf | carries | 5307 | 8.7 | 3.872 | -0.129 | 3.938 | 3.948 | -1.7 |
| ncaaf | completions | 1691 | 16.11 | 5.641 | 0.161 | 5.689 | 5.708 | -0.8 |
| ncaaf | interceptions | 1691 | 0.65 | 0.703 | -0.022 | 0.735 | 0.727 | -4.4 |
| ncaaf | pass_rush_yds | 1691 | 209.2 | 77.38 | 3.762 | 80.63 | 81.19 | -4 |
| ncaaf | pass_tds | 1691 | 1.27 | 0.94 | 0.014 | 1.022 | 1.003 | -8 |
| ncaaf | pass_yds | 1691 | 188.1 | 71.45 | 1.858 | 74.55 | 74.73 | -4.2 |
| ncaaf | rec_yds | 10364 | 28.55 | 19.28 | -0.375 | 20.11 | 19.71 | -4.2 |
| ncaaf | receptions | 10364 | 2.42 | 1.325 | -0.044 | 1.329 | 1.325 | -0.3 |
| ncaaf | rush_rec_tds | 10364 | 0.34 | 0.458 | -0.009 | 0.467 | 0.457 | -1.9 |
| ncaaf | rush_rec_yds | 8846 | 48.56 | 28.54 | -0.941 | 30.21 | 29.72 | -5.5 |
| ncaaf | rush_yds | 5307 | 38.2 | 26.14 | -0.467 | 28.13 | 27.61 | -7 |


### Model vs the opening line as a point forecast (NFL rows with real lines)
| stat | n | model_mae | open_line_mae | model_bias | open_line_bias |
|---|---|---|---|---|---|
| attempts | 331 | 6.966 | 6.693 | 0.142 | 0.588 |
| carries | 598 | 3.659 | 3.363 | -0.338 | 0.221 |
| completions | 331 | 4.843 | 4.666 | 0.236 | 0.461 |
| interceptions | 331 | 0.659 | 0.708 | -0.069 | -0.101 |
| pass_rush_yds | 298 | 58.97 | 55.08 | -0.987 | 0.067 |
| pass_tds | 330 | 0.954 | 0.952 | -0.038 | -0.073 |
| pass_yds | 329 | 58.02 | 54.3 | -2.234 | 1.239 |
| rec_yds | 1632 | 21.96 | 20.56 | 0.803 | -3.477 |
| receptions | 1642 | 1.642 | 1.588 | 0.101 | -0.057 |
| rush_rec_yds | 421 | 32.69 | 30.84 | -4.443 | -4.186 |
| rush_yds | 852 | 21.22 | 20.05 | -0.636 | -2.745 |


## Guards and discounts
Flagged vs unflagged hit rates, and top-25/week with each guard's discount removed (counterfactual re-rank through rank_props), at the tuned projection/probability settings.
| set | guard | discount | flagged_bets | hit_rate_flagged | roi_flagged | hit_rate_unflagged | roi_unflagged | top25_live_hit | top25_live_roi | top25_guard_off_hit | top25_guard_off_roi |
|---|---|---|---|---|---|---|---|---|---|---|---|
| REAL NFL | far_line | 0.35 | 667 | 55.0% | +5.0% | 51.0% | -2.6% | 0.5805 | 0.1083 | 0.5788 | 0.1049 |
| REAL NFL | teammate_out | 0.35 | 364 | 47.8% | -8.7% | 51.6% | -1.5% | 0.5805 | 0.1083 | 0.5805 | 0.1083 |
| REAL NFL | missed_last | 0.6 | 295 | 51.9% | -1.0% | 51.4% | -1.9% | 0.5805 | 0.1083 | 0.5772 | 0.1019 |
| REAL NFL | small_sample | 0.6 | 783 | 52.4% | -0.0% | 51.3% | -2.1% | 0.5805 | 0.1083 | 0.5872 | 0.1211 |
| SYNTHETIC NFL | far_line | 0.35 | 386 | 67.6% | +29.1% | 62.5% | +19.3% | 0.8278 | 0.5803 | 0.8231 | 0.5713 |
| SYNTHETIC NFL | teammate_out | 0.35 | 708 | 65.7% | +25.4% | 62.5% | +19.3% | 0.8278 | 0.5803 | 0.8208 | 0.5669 |
| SYNTHETIC NFL | missed_last | 0.6 | 1127 | 58.9% | +12.5% | 62.9% | +20.0% | 0.8278 | 0.5803 | 0.8519 | 0.6263 |
| SYNTHETIC NFL | small_sample | 0.6 | 1383 | 61.6% | +17.6% | 62.7% | +19.7% | 0.8278 | 0.5803 | 0.8303 | 0.5852 |
| SYNTHETIC FBS | far_line | 0.35 | 4546 | 64.4% | +23.0% | 61.2% | +16.9% | 0.8442 | 0.6116 | 0.8618 | 0.6453 |
| SYNTHETIC FBS | teammate_out | 0.35 | 0 |  |  | 61.5% | +17.3% | 0.8442 | 0.6116 | 0.8442 | 0.6116 |
| SYNTHETIC FBS | missed_last | 0.6 | 6777 | 62.9% | +20.0% | 61.3% | +17.0% | 0.8442 | 0.6116 | 0.8421 | 0.6077 |
| SYNTHETIC FBS | small_sample | 0.6 | 8239 | 64.4% | +22.9% | 61.0% | +16.4% | 0.8442 | 0.6116 | 0.8312 | 0.5869 |


### Guard discounts: tune vs held-out (top 25/week, at the tuned settings)
| set | variant | tune_top25_bets | tune_top25_hit | tune_top25_roi | holdout_top25_bets | holdout_top25_hit | holdout_top25_roi | better_on_both |
|---|---|---|---|---|---|---|---|---|
| REAL NFL | live guards | 199 | 0.6281 | 0.1992 | 99 | 0.4848 | -0.0744 | False |
| REAL NFL | far_line discount OFF | 193 | 0.6269 | 0.1969 | 99 | 0.4848 | -0.0744 | False |
| REAL NFL | teammate_out discount OFF | 199 | 0.6332 | 0.2088 | 99 | 0.4747 | -0.0937 | False |
| REAL NFL | missed_last discount OFF | 199 | 0.6332 | 0.2088 | 99 | 0.4646 | -0.1129 | False |
| REAL NFL | small_sample discount OFF | 199 | 0.6332 | 0.2088 | 99 | 0.4949 | -0.0551 | True |
| REAL NFL | ALL guard discounts OFF | 193 | 0.5803 | 0.1079 | 100 | 0.52 | -0.0073 | False |
| SYNTHETIC NFL | live guards | 185 | 0.7946 | 0.517 | 204 | 0.8578 | 0.6377 | False |
| SYNTHETIC NFL | far_line discount OFF | 185 | 0.7946 | 0.517 | 205 | 0.8488 | 0.6204 | False |
| SYNTHETIC NFL | teammate_out discount OFF | 185 | 0.8162 | 0.5582 | 200 | 0.84 | 0.6036 | False |
| SYNTHETIC NFL | missed_last discount OFF | 172 | 0.8314 | 0.5872 | 178 | 0.8708 | 0.6624 | True |
| SYNTHETIC NFL | small_sample discount OFF | 184 | 0.7989 | 0.5252 | 205 | 0.8585 | 0.639 | True |
| SYNTHETIC NFL | ALL guard discounts OFF | 170 | 0.8176 | 0.561 | 173 | 0.8613 | 0.6442 | True |
| SYNTHETIC FBS | live guards | 171 | 0.8187 | 0.563 | 141 | 0.8652 | 0.6518 | False |
| SYNTHETIC FBS | far_line discount OFF | 164 | 0.8537 | 0.6297 | 142 | 0.8732 | 0.6671 | True |
| SYNTHETIC FBS | teammate_out discount OFF | 171 | 0.8187 | 0.563 | 141 | 0.8652 | 0.6518 | False |
| SYNTHETIC FBS | missed_last discount OFF | 153 | 0.817 | 0.5597 | 134 | 0.8731 | 0.6669 | False |
| SYNTHETIC FBS | small_sample discount OFF | 173 | 0.8208 | 0.567 | 142 | 0.8592 | 0.6402 | False |
| SYNTHETIC FBS | ALL guard discounts OFF | 117 | 0.8889 | 0.697 | 105 | 0.8667 | 0.6545 | True |

Guard changes are reported only. They are applied to the live code only if they improve top-25 ROI on both tune and held-out REAL lines.

## Tuning (tune weeks 2-9, validate weeks 10+)
### Projection knobs (one at a time from live settings)
| league | config | tune_norm_mae | holdout_norm_mae | delta_tune_vs_live | delta_holdout_vs_live | applied_candidate |
|---|---|---|---|---|---|---|
| nfl | baseline | 0.9429 | 0.9841 | 0 | 0 | False |
| ncaaf | baseline | 0.9536 | 0.982 | 0 | 0 | False |
| nfl | blend 0.55/0.25/0.20 | 0.9423 | 0.9811 | -0.00065 | -0.00293 | False |
| nfl | blend 0.40/0.30/0.30 | 0.9367 | 0.9833 | -0.00623 | -0.00075 | False |
| nfl | blend 0.50/0.20/0.30 | 0.936 | 0.981 | -0.00693 | -0.00305 | True |
| nfl | blend 0.35/0.45/0.20 | 0.9443 | 0.9884 | 0.00132 | 0.00434 | False |
| nfl | matchup 0.0 | 0.9446 | 0.9874 | 0.00169 | 0.00332 | False |
| nfl | matchup 0.3 | 0.942 | 0.9839 | -0.0009 | -0.00011 | True |
| nfl | matchup 1.0 | 0.9463 | 0.9876 | 0.00339 | 0.00357 | False |
| nfl | env 0.0 | 0.9449 | 0.9845 | 0.00201 | 0.00045 | False |
| nfl | env 0.5 | 0.9412 | 0.9834 | -0.00171 | -0.00065 | True |
| nfl | env 1.5 | 0.9453 | 0.9858 | 0.00241 | 0.00174 | False |
| nfl | pos-shrink k=0 | 0.9495 | 0.9851 | 0.0066 | 0.00105 | False |
| nfl | pos-shrink k=1.5 | 0.9367 | 0.9849 | -0.00625 | 0.00083 | False |
| ncaaf | cfb season/L3 0.40 | 0.9555 | 0.9864 | 0.00187 | 0.00431 | False |
| ncaaf | cfb season/L3 0.70 | 0.9524 | 0.9799 | -0.00127 | -0.0021 | True |
| ncaaf | cfb prior fade slower (decay 0.08) | 0.9501 | 0.9802 | -0.00353 | -0.00181 | True |
| ncaaf | cfb prior fade faster (decay 0.20) | 0.9569 | 0.9837 | 0.00325 | 0.00161 | False |
| ncaaf | cfb no prior (ablation) | 0.9661 | 0.9902 | 0.01245 | 0.00817 | False |
| ncaaf | cfb opp-adj BETA 0 (ablation) | 0.9575 | 0.9865 | 0.00385 | 0.00448 | False |
| ncaaf | cfb opp-adj BETA 0.018 | 0.9555 | 0.9836 | 0.0019 | 0.00155 | False |
| ncaaf | cfb level-jump off (ablation) | 0.9534 | 0.982 | -0.00024 | 0 | False |
| ncaaf | matchup 0.0 | 0.9526 | 0.9826 | -0.00105 | 0.00054 | False |
| ncaaf | matchup 1.0 | 0.9587 | 0.9876 | 0.00507 | 0.00556 | False |
| ncaaf | env 0.0 | 0.9521 | 0.9832 | -0.00153 | 0.00111 | False |
| ncaaf | env 1.5 | 0.9558 | 0.9839 | 0.00216 | 0.00189 | False |

### Combined tuned config
| league | combined_settings | tune_norm_mae_live | tune_norm_mae_combined | holdout_norm_mae_live | holdout_norm_mae_combined | accepted |
|---|---|---|---|---|---|---|
| nfl | {"W_SEASON": 0.5, "W_L3": 0.2, "W_PRIOR": 0.3, "ENV_STRENGTH": 0.5, "MATCHUP_STRENGTH": 0.3} | 0.9429 | 0.9343 | 0.9841 | 0.9805 | True |
| ncaaf | {"CFB_W_SEASON": 0.7, "CFB_PRIOR_DECAY": 0.08} | 0.9536 | 0.949 | 0.982 | 0.9782 | True |

### P(over) shrink toward 50% (real NFL lines)
| P_SHRINK | tune_logloss | holdout_logloss | tune_brier | holdout_brier |
|---|---|---|---|---|
| 0.1 | 0.6918 | 0.6921 | 0.2493 | 0.2495 |
| 0.15 | 0.6915 | 0.6919 | 0.2492 | 0.2494 |
| 0.2 | 0.6915 | 0.692 | 0.2492 | 0.2494 |
| 0.25 | 0.6917 | 0.6923 | 0.2493 | 0.2496 |
| 0.3 | 0.6923 | 0.6929 | 0.2495 | 0.2499 |
| 0.4 | 0.6941 | 0.6948 | 0.2505 | 0.2508 |
| 0.5 | 0.6972 | 0.698 | 0.2519 | 0.2523 |
| 0.6 | 0.7015 | 0.7023 | 0.2539 | 0.2542 |
| 0.75 | 0.7109 | 0.7117 | 0.2578 | 0.2581 |
| 1 | 0.7411 | 0.7442 | 0.2671 | 0.2671 |

Chosen P_SHRINK: 0.2 (was 0.75). Rule: best tune-week log-loss, applied only if held-out log-loss also improves.

### Ranking layer: RANK_SHRINK (edge term inside rank_score) x AGREE_W (weight on last-10 hit-rate agreement)
In v1 one shrink set both the displayed probability and the ranking. Calibrating it (0.75 -> 0.2) made rank_score mostly negative and let the hit-rate term dominate, which hurt top-N picks on the tune weeks. The two are now separate: P_SHRINK calibrates the displayed P(over) and model_p_side, and RANK_SHRINK orders picks.
| RANK_SHRINK | AGREE_W | tune_top10_hit | tune_top10_roi | tune_top25_hit | tune_top25_roi | holdout_top10_hit | holdout_top10_roi | holdout_top25_hit | holdout_top25_roi |
|---|---|---|---|---|---|---|---|---|---|
| 0.4 | 0 | 0.55 | 0.05 | 0.5327 | 0.0169 | 0.4103 | -0.2168 | 0.4747 | -0.0937 |
| 0.4 | 5 | 0.55 | 0.05 | 0.5427 | 0.0361 | 0.3846 | -0.2657 | 0.4747 | -0.0937 |
| 0.4 | 10 | 0.5823 | 0.1116 | 0.5427 | 0.0361 | 0.4103 | -0.2168 | 0.4343 | -0.1708 |
| 0.4 | 20 | 0.6456 | 0.2325 | 0.5578 | 0.0649 | 0.359 | -0.3147 | 0.4343 | -0.1708 |
| 0.6 | 0 | 0.6625 | 0.2648 | 0.53 | 0.0118 | 0.4615 | -0.1189 | 0.4646 | -0.1129 |
| 0.6 | 5 | 0.7 | 0.3364 | 0.56 | 0.0691 | 0.4359 | -0.1678 | 0.4646 | -0.1129 |
| 0.6 | 10 | 0.7125 | 0.3602 | 0.5729 | 0.0937 | 0.4359 | -0.1678 | 0.4747 | -0.0937 |
| 0.6 | 20 | 0.6875 | 0.3125 | 0.608 | 0.1608 | 0.3846 | -0.2657 | 0.4646 | -0.1129 |
| 0.75 | 0 | 0.675 | 0.2886 | 0.56 | 0.0691 | 0.5 | -0.0455 | 0.4545 | -0.1322 |
| 0.75 | 5 | 0.7 | 0.3364 | 0.58 | 0.1073 | 0.5 | -0.0455 | 0.4848 | -0.0744 |
| 0.75 | 10 | 0.7125 | 0.3602 | 0.605 | 0.155 | 0.475 | -0.0932 | 0.4646 | -0.1129 |
| 0.75 | 20 | 0.6875 | 0.3125 | 0.6212 | 0.186 | 0.45 | -0.1409 | 0.4848 | -0.0744 |
| 1 | 0 | 0.6875 | 0.3125 | 0.59 | 0.1264 | 0.5 | -0.0455 | 0.4949 | -0.0551 |
| 1 | 5 | 0.725 | 0.3841 | 0.605 | 0.155 | 0.5 | -0.0455 | 0.4949 | -0.0551 |
| 1 | 10 | 0.7375 | 0.408 | 0.6181 | 0.18 | 0.5 | -0.0455 | 0.4848 | -0.0744 |
| 1 | 20 | 0.7125 | 0.3602 | 0.6281 | 0.1992 | 0.475 | -0.0932 | 0.4848 | -0.0744 |

Chosen RANK_SHRINK 1.0 (was 0.75), AGREE_W 20.0 (was 10.0). Rule: best tune-week top-25 ROI, applied only if held-out top-25 ROI beats the live pair.

Guard discounts switched off (better top-25 ROI on both tune and held-out real lines): {'GUARD_SMALL_F': 1.0}.

### Held-out before vs after
| set | version | holdout_weeks | all_bets | all_hit | all_roi | top10_bets | top10_hit | top10_roi | top25_bets | top25_hit | top25_roi | logloss | brier | norm_mae |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| REAL lines (NFL, ESPN BET opening) | before (live settings) | 10-13 | 2326 | 0.5193 | -0.0085 | 40 | 0.35 | -0.3318 | 100 | 0.47 | -0.1027 | 0.7144 | 0.2593 | 0.9841 |
| REAL lines (NFL, ESPN BET opening) | tuned projections only (live ranking/prob.) | 10-13 | 2326 | 0.5125 | -0.0217 | 40 | 0.475 | -0.0932 | 99 | 0.4646 | -0.1129 | 0.7117 | 0.2581 | 0.9805 |
| REAL lines (NFL, ESPN BET opening) | after (all tuned settings) | 10-13 | 2326 | 0.5125 | -0.0217 | 40 | 0.5 | -0.0455 | 99 | 0.4949 | -0.0551 | 0.692 | 0.2494 | 0.9805 |
| SYNTHETIC proxy NFL | before (live settings) | 10-18 | 9192 | 0.6179 | 0.1797 | 80 | 0.8375 | 0.5989 | 207 | 0.8696 | 0.6601 | 0.6461 | 0.2276 | 0.9841 |
| SYNTHETIC proxy NFL | after (all tuned settings) | 10-18 | 9192 | 0.628 | 0.199 | 82 | 0.8415 | 0.6064 | 205 | 0.8585 | 0.639 | 0.6738 | 0.2404 | 0.9805 |
| SYNTHETIC proxy FBS | before (live settings) | 10-16 | 23937 | 0.6076 | 0.16 | 59 | 0.8475 | 0.6179 | 144 | 0.875 | 0.6705 | 0.6499 | 0.2294 | 0.982 |
| SYNTHETIC proxy FBS | after (all tuned settings) | 10-16 | 23937 | 0.6119 | 0.1681 | 60 | 0.8333 | 0.5909 | 142 | 0.8592 | 0.6402 | 0.6742 | 0.2406 | 0.9782 |


## Limitations and leakage notes
- **Missing real lines:** NFL weeks 14-18 and all FBS games are proxy-only. Held-out real-line validation is therefore weeks 10-13 only (4 weeks).
- **Opening vs closing:** opening lines are softer than closing lines, so real-line ROI here is probably better than betting closer to kickoff would give. The last-listed line can't be used safely because it may include in-game updates.
- **One book:** ESPN BET only (n_books = 1). No line shopping.
- **SP+ as-of proxy:** FBS opponent strength all season uses 2024 final SP+, not in-season ratings, so there's no leak but early-season accuracy is lower than live use would get. CFBD /teams 2025 conference membership is end-of-season (realignment is known preseason, so this is negligible).
- **Transfer portal list:** the CFBD 2025 portal file is the final list (includes spring-window moves). That's known before the season, so no in-season leak.
- **Implied totals** use closing spread/total (known pregame; slightly sharper than what's available early in the week).
- **Injuries:** the NFL uses the official week-W final injury report (published pregame). FBS has no historical injury data, so there are no injury guards.
- **No weather adjustment** in the backtest (historical forecasts not archived). Live runs use forecasts.
- **Voids:** players without a stat row are voided. A receiver who played but drew no target has no row in nflverse/CFBD box scores, so some winning unders become voids. That biases under hit rate slightly in both directions of uncertainty.
- **FBS positions** come from the CFBD 2025 roster (~2% inferred from usage when missing).
- **Correlated picks:** top-N lists can hold several props for the same player (e.g. rush yds and rush+rec yds), so effective sample sizes are smaller than bet counts.
- **Synthetic proxy line:** floor(trailing-5 avg)+0.5 is mechanically related to the model's own inputs. It tests whether the model's departures from a naive average are directionally right. It doesn't test profitability.