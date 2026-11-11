# Rules locked — 2026-11-02 06:49:31 PST — written BEFORE any rule results were computed
Data: prop-finder/output/backtest_2025/nfl_real_lines_graded.csv. These are walk-forward predictions at pre-backtest settings (NOT the _tuned file). ESPN BET opening lines and prices, NFL 2025 weeks 2-13. Sides missing either price are dropped. Voids are excluded.
Definitions:
- fair_p(side) = no-vig from the opening over/under prices.
- edge = model_p_side - fair_p.
- Grading is at the listed opening price, 1u stakes.
- Band: price between +110 and -150 inclusive.
- Universe U = pass_yds, rush_yds, rec_yds (the QB/RB/WR yards markets). U_all = every stat (secondary).
Rules (each reported for ALL prices and for the BAND):
R01 all model picks (U)
R02-R05 edge >= 0 / 2 / 4 / 6% (U)
R06 edge >= 2%, overs only; R07 edge >= 2%, unders only
R08-R10 edge >= 2% by market: pass_yds / rush_yds / rec_yds
R11-R13 model_p_side buckets: <55, 55-60, >=60 (U)
R14 50% shrink: p = 0.5*model + 0.5*fair, edge >= 2% (U)
R15 naive: always under, no model (U); R16 naive: always over (U)
R17 edge >= 2% in U_all (all stats)
R18 top 10 per week by edge (U)
That is 18 rules x 2 price filters = 36 tests. Multiple-testing threshold: Bonferroni alpha 0.05/36, i.e. a one-sided game-clustered bootstrap lower bound at the 99.86% level. 95% CIs are also shown.
CI: 5,000 bootstrap resamples of games (event_id), with units summed per game.
2026 is held out and is not evaluated.
