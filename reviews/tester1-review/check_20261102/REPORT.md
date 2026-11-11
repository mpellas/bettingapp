# Tester1 cross-checks, 2026-11-02 (paper only)
Copies made with cp -a and checked with diff -rq / diff -q (all identical): backtest-scope-20261102/, feature-audit-nhl-20261102/, nfl_real_lines_graded.csv, features.py, model_c3ab760178.json.

## (A) NFL 2025 backtest: PASS
My own code (rebuild.py, plain csv, no pandas or bt.py code) on prop-finder/output/backtest_2025/nfl_real_lines_graded.csv, using the locked rules: both prices present, win/loss only, pass/rush/rec yds, 1u at the listed opening price.
- R01 all: 2,760 sides, 177 games, 1405-1355, -151.82u, ROI -5.5%. This matches nfl2025_results.csv exactly.
- R01 band (+110 to -150): 1364-1336, -151.00u. This matches exactly.
- I re-graded every side from actual vs line instead of the result column, and there were 0 disagreements.
- Note on bt.py: the line `if k=='R18': pass` does nothing, but it's harmless because R18 is computed separately afterward. I found no bug that changes the numbers.

## (B) NHL ablate.py leakage audit: PASS (clean)
- Base 26 features (features.py:13-24): every rolling, expanding, cumcount and rest feature uses shift(1) on rows sorted by gameDate (features.py:6). merge(how='left') keeps that order, and opp_sa_r20 and team_sf_r20 are shifted before the merge.
- ablate.py:7 shtoi_r10 uses shift(1). Clean.
- ablate.py:8-18 team_roll (opp_sa_pos_r20, opp_aa_r20, team_af_r20, opp_af_r20) uses shift(1) within team after sorting by date. Clean. opp_thru (line 15) is a ratio of two lagged features. Clean.
- ablate.py:20-21: tm_toi and the raw pp_share come from the same game, but neither is a model input. Only pp_share_r5 (shift(1)) is used. Clean, though tm_toi is dead code.
- ablate.py:23 opp_b2b comes from the game's own date, but it's schedule info known before the game. Clean.
- ablate.py:27-34: the train/test split is by season (early stopping on 2024, refit through 2024, test 2025), and k is fit on train only. There are no closing lines, lineups, or season totals among the inputs.
- Caveat: this was a static code review. I did not rerun ablate.py, which is Tester2's part.
