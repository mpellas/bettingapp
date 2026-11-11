# nfl-props — NFL player-prop research pipeline (v2, after the Tester1 review)

Walk-forward research pipeline for **QB passing yards**, **RB/WR/TE rushing yards** and **RB/WR/TE receiving
yards** props: nflverse data → leakage-checked as-of-kickoff features → distributional LightGBM model → P(over/under)
→ per-market logistic stacker that shrinks toward the market → edge vs no-vig price → capped fractional Kelly →
walk-forward backtest → experiment loop with a statistically guarded promotion rule → markdown/PNG reports → one
frozen holdout.

> **Important:** no real historical prop odds exist in this repo for 2015-2024. All 2019-2024 betting results are
> against **SIMULATED** lines and **cannot show real-world profitability**. The only real-price check is the frozen 2025
> holdout against **ESPN BET lines of uncertain timing** (weeks 1-13, one book, 3,457 lines). ESPN's timestamps are
> last-update times, and 99.3% of them are after kickoff, so these are **not** clean opening lines.

## Quick start

```bash
cd /workspace/nfl-props
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && pip install -e .

python -m nflprops.data                 # download + cache nflverse data (2015-2025) to data/cache/
python -m nflprops.leakage              # leakage check on current features (must PASS)
python -m nflprops.leakage --legacy     # same check on the v1 features (must FAIL: shows the test catches look-ahead)
pytest tests                            # leakage (current passes / legacy fails), stacker no-look-ahead, exposure caps
python -m nflprops.improve --iterations 4   # experiment loop (validation 2019-22, promotion test on 2023-24)
python -m nflprops.summary              # reports/REPORT.md + charts; publishes the holdout policy + its sha1
python -m nflprops.holdout              # ONE-TIME scoring of the 2025 holdout (refuses to run twice)
python -m nflprops.run_backtest --champion --seasons 2019-2024     # ad-hoc walk-forward report (refuses 2025)
python -m nflprops.import_espn_lines    # rebuild data/lines/espn_bet_2025_open_uncertain_timing.csv from cached ESPN JSON
```
Runtime on this box (8 cores): features ~3 s, one season walk-forward for all 3 markets ~6-10 s, one improvement
iteration (4 candidates x 4 validation seasons, plus a promotion test if there is a challenger) ~2-3 min.

## v2 changes after the Tester1 review (`/workspace/tester1-review/RECOMMENDATIONS.md`)
I checked each claim before changing anything (`audit/verify_tester1_v1.py` → `audit/verify_tester1_v1.txt`, plus
re-runs of Tester1's diag6/diag7, which reproduced their outputs exactly).
* **B1 look-ahead (confirmed, fixed).** v1 used nflverse `spread_line`/`total_line` (filled in near game time:
  2026 week-5 games had no spread yet when checked), observed `wind`/`temp` (filled only after games are played), and the
  *actual* starting QB (differs from the previous game's starter in 12.5% of starts), all while betting against
  opening-type lines. Removing these columns took Tester1's diagnostic ROI from +3.0% to −0.1%. v2 removes them all:
  the spread/total are replaced by a pre-game proxy built only from each team's prior-game points for/against
  (EWMA, half-life 6, ±0.75 home field) → `proxy_spread`, `proxy_total`, `implied_tt` (the public projection uses it);
  weather is replaced by static `dome`/`retractable` from `roof`; the QB flag is a **projected starter** (the team's
  starter in its previous game). `FEATURE_VERSION = "v2-asof"`. The v1 feature code is kept in
  `src/nflprops/legacy/features_v1.py` (DO NOT USE) only so the leakage test can prove it catches it.
* **Leakage test extended (B4).** `leakage.py` now also scrambles post-cutoff **schedule/game-level** fields (spread,
  total, moneylines, wind, temp, scores/result, roof open↔closed, starting-QB ids). Current features: PASS (0 changed
  pre-cutoff values at 3 cutoffs). v1 features: FAIL (1,860 / 2,427 / 2,091 changed values; offending columns
  implied_tt, wind, temp, total_line, team_spread, mkt_proj_*, dome, is_starting_qb).
* **B2 promotion rule (confirmed, fixed).** v1 compared 0.9-market-blended probabilities (1.0 was not in the grid),
  which shrank real differences ~10-40x, and used a fixed 0.0005 margin. v2 ranks candidates by validation **raw**
  model log loss. A challenger must beat the champion overall **and** in ≥3 of the 4 validation seasons. On the
  selection seasons, its raw log-loss gain must exceed z_adj × SE, where SE comes from a paired **game-clustered
  bootstrap** and z_adj = Φ⁻¹(1 − α/m), α = 0.05, m = promotion tests so far (Bonferroni). The blend grid now
  includes 1.0 but is a diagnostic only.
* **Versioned caches (B7).** Prediction and reference caches are keyed on config hash **plus** a hash of the
  feature/model/line code (`features.code_version`), and the feature cache on the code version.
* **Out-of-sample residual scale (B9).** `model.py` cross-fits the scale model, so standardized residuals (and the
  empirical Z distribution) are fully out of fold.
* **Game-clustered CIs (B6).** All ROI CIs are game-clustered bootstraps (bets in one game are correlated: v1's
  995 holdout bets averaged 5.2 per game; the naive ±5.9% interval became [−2.6%, +8.6%]).
* **Frozen holdout (B10).** `summary.py` no longer scores 2025; it only reads `experiments/holdout_frozen.json`.
  `holdout.py` refuses to run unless the sha1 of `configs/holdout_policy.yaml` is already published in
  `reports/REPORT.md`, and it refuses a second run. `run_backtest.py` refuses the holdout season.
* **Stacker + capped Kelly (Tester1 #7).** `calibration.py`: per market,
  `logit p = a + b·logit(p_mkt) + c·logit(p_model)`, ridge prior toward (0, 1, 0) ("trust the market"; λ = 50).
  It is refit every week on strictly earlier weeks of the same line source, and returns the market price (no bet)
  until a market has 300 earlier lines. Kelly is applied to the stacked p, with caps: 2% per bet; 4% and 3 bets per
  game; 3% per team-game; 1 bet per player-game; 20% per week.
* **B8 (no-op edge thresholds, confirmed).** Thresholds below the vig hurdle (2%) were removed from the grid.
* **B5 (ESPN timestamps, confirmed).** 99.3% of `lastUpdated` values are after kickoff; 26 athlete-markets have >1 main
  over/under pair (the importer now picks the most balanced pair and records `n_main_pairs`; this changed 0 lines vs v1).
  The lines are labelled "ESPN BET lines of uncertain timing" everywhere; the column is `espn_last_updated`.
* **B3 (every 2019-24 decision is made against a simulator, confirmed, not fixable without real historical lines).**
  The loop's promotions are improvements *against the simulator*; real timestamped lines remain the #1 next step.
* **Line simulator fix (found while testing, not on Tester1's list).** The stacker found that v1's simulated line
  under-reacted to its noiseless "inside info" signal: it got 73% hits on 2019-20 by decoding (line − model).
  The simulated market now receives a *noisy* signal and weights it with the efficient regression coefficient
  (β); the noise level is solved so that MAE(line)/MAE(public projection) matches the ESPN ratios.
* Not done this pass (by instruction): news/injury features, buying historical odds.

## Results (run on 2026-10-04 PT — full numbers in `reports/REPORT.md`)
* **Improvement loop (SIMULATED lines):** 4 iterations, 16 candidates, 2 promotion tests, **1 promotion**
  (`lgbm.num_leaves=7`). Its selection raw-LL gain was 0.00149 ± 0.00078 SE, above the m=1 margin of 0.00128.
  The iteration-4 challenger (`n_estimators=200, use_market_proj=False`) had a gain of 0.00125 ± 0.00070 and was
  rejected at the m=2 margin of 0.00137. Champion `557e6ab3e4`.
* **Champion walk-forward 2019-2024, SIMULATED lines** (stacker, edge 4%, ¼ Kelly, caps): 804 bets, hit 56.0%,
  flat ROI +6.9% [+0.3%, +13.2%] (game-clustered 95% CI); bankroll 1000 → 1997; max drawdown −22.9%. Nearly all
  bets are rec yds (766). Log loss: raw model 0.7107, stacked 0.6923, market 0.6931. Selection seasons 2023-24
  only: 456 bets, +2.6% [−5.9%, +11.1%]. The result depends on the simulator: with ref_share 0 / 0.5 / 1.0 the
  selection ROI is +11.3% / +2.6% / +9.8%. **Simulated: not evidence of real profitability.**
* **Frozen 2025 holdout, ESPN BET lines of uncertain timing (real prices), pre-declared policy, scored once:**
  2,363 priced lines in the universe, **18 bets** (all rush yds), hit 50.0%, flat ROI **−6.7% [−45.4%, +34.2%]**,
  bankroll 1000 → 981. No pass bets: the stacker never reached 300 earlier pass lines. No rec bets: the stacker's
  out-of-sample model weight stayed small (c = 0.04). Log-loss gain vs the market: raw model −0.0181
  [−0.0269, −0.0091] nats/line (worse than the market); stacked +0.0002 [−0.0009, +0.0013] (indistinguishable).
  **Evidence of a real edge: none.**
* Real 2025 lines sit 2.7-4.6 yds *above* the simulated ones and go over only 46-49% of the time (the simulator assumes
  50%).

## Layout

| path | what |
|---|---|
| `src/nflprops/data.py` | nflverse download + parquet cache (nflreadpy; falls back to nflverse-data GitHub release files) |
| `src/nflprops/features.py` | player/team/opponent/game-proxy/static-context features, as of kickoff (`FEATURE_VERSION`, `code_version`) |
| `src/nflprops/legacy/features_v1.py` | v1 features with look-ahead — DO NOT USE; kept only for the leakage regression test |
| `src/nflprops/leakage.py`, `tests/` | scramble-the-future leakage test (player + schedule fields), legacy must-fail test, stacker and caps tests |
| `src/nflprops/markets.py` | market definitions + pre-game "would a book post this line" universe filter |
| `src/nflprops/model.py` | `DistModel`: LightGBM mean + cross-fitted LightGBM scale + empirical out-of-fold standardized-residual distribution |
| `src/nflprops/calibration.py` | rolling per-market logistic stacker (shrink toward market, fit on earlier weeks only) |
| `src/nflprops/reference.py` | fixed reference model used only to build the simulated market |
| `src/nflprops/lines.py` | pluggable line sources: `SimulatedSharpLines`, `CsvLines` (real lines) |
| `src/nflprops/betting.py` | no-vig, edge threshold, fractional Kelly with per-bet/game/team/player/week caps, week-by-week bankroll |
| `src/nflprops/backtest.py` | expanding-window walk-forward engine (prediction cache in `data/cache/preds/`, keyed on config + code version) |
| `src/nflprops/metrics.py`, `tuning.py` | metrics (hit rate, ROI, drawdown, Brier, log loss, reliability, MAE, CRPS); validation-only tuning of post-model params |
| `src/nflprops/improve.py` | experiment loop, `experiments/runs.jsonl` + `runs.csv`, `experiments/champion.json` |
| `src/nflprops/holdout.py`, `configs/holdout_policy.yaml` | one-time frozen holdout with the pre-declared policy → `experiments/holdout_frozen.json` |
| `src/nflprops/summary.py`, `report.py`, `run_backtest.py` | reports (game-clustered CIs), CLI |
| `audit/` | my verification of Tester1's claims against v1 |
| `configs/default.yaml` | every knob (periods, model, simulated-market parameters, betting, search settings) |
| `reports/` | `REPORT.md` (summary), per-run folders with `report.md`, `bankroll_curve.png`, `calibration.png`, `roi_by_market.png` |

## Data
nflverse weekly player stats, snap counts (PFR ids mapped to GSIS via the nflverse players table) and schedules
(since v2 only rest days, roof, home/away, division and the previous games' starting QBs and scores are used — no
spread/total/weather/actual-starter), seasons 2015-2025 (2025 = most recent complete
season as of 2026-10-04). REG+POST games are used as feature history; bets are evaluated on REG weeks only.
Players with an offensive snap but no stat line are added with 0s (otherwise 0-yard games vanish and overs look better).

## Features (pre-game only)
Per player, from prior games only (`shift(1)` before every EWMA, half-lives 2 and 6 games, carrying across seasons):
attempts, completions, pass/rush/rec yards, air yards, carries, targets, receptions, target share, air-yards share,
carry share, snap share; yards per attempt/carry/target, catch rate, aDOT; last-game values; games played,
days since last game, team-changed flag, position, **projected**-starting-QB flag (= the team's starter in its
previous game). Team (prior games): pass attempts, carries, pass rate, plays, yards. Opponent defense (prior games):
passing yards allowed to QBs, rushing yards allowed to RBs, receiving yards allowed to WR/TE/RB, attempts/carries
faced. Game proxy (prior games only): team/opponent points-for/against EWMAs → `proxy_spread`, `proxy_total`,
`implied_tt`. Static context: home/away, rest days, dome, retractable roof, division game, week. A simple "public
projection" (usage EWMA x proxy implied-team-total factor, fixed constants) is a feature and a baseline. The QB
universe is projected starters (a backup who only becomes the starter on game day is not scored).

**Leakage check** (`python -m nflprops.leakage`): for several cutoff dates, every player stat/snap share **and every
schedule/game-level field** (spread, total, moneylines, wind, temp, scores, roof open/closed, starting-QB ids) on or
after the cutoff is replaced with random noise, all features are rebuilt, and every feature for games on/before the cutoff must
be bit-identical (it also verifies the scramble did change later features, so the test is not vacuous), plus a check
that no feature is a near-copy of a target. `--legacy` runs it on the v1 features, which must FAIL (they do).

## Model
`Y = mu(x) + s(x) * Z`: LightGBM regression for the mean, a smaller LightGBM fit to |out-of-fold residual| for the
scale (OOF via season-grouped 3-fold CV *inside the training window*; since v2 the scale model is itself cross-fitted
so each row's s is predicted by a fold that did not see it), and Z = the empirical distribution of those fully
out-of-fold standardized residuals (keeps the right skew of yardage; `dist: normal` is the Gaussian alternative). `P(over L) = 1 -
F_Z((L - mu)/s)`. One model per market.

## Walk-forward backtest
For each test season, train on everything before each block of `retrain_every_weeks` weeks (default 4) and predict
the block; the residual/scale model is refit once per test season. Per-week retraining is possible
(`retrain_every_weeks: 1`) but ~4x slower; the search space includes 2/4/8.

## Betting logic
`p_used` = the rolling per-market **stacker** (`calibration.py`): `logit p = a + b·logit(p_novig) + c·logit(p_model)`,
ridge prior toward (0, 1, 0) with strength λ = 50, fit on all priced lines of that market and line source in
strictly earlier weeks; the market probability (no bet) until 300 earlier lines exist. Pick the side with the larger
edge `p_used − p_novig`; bet if edge ≥ `edge_threshold` and EV > 0 at the actual price. Stake = `kelly_fraction` ×
full Kelly on `p_used`, applied greedily by edge within each week with caps: `max_bet_frac` 2%, `max_game_frac` 4%,
`max_bets_per_game` 3, `max_team_frac` 3% per team-game, `max_bets_per_player` 1 per player-game,
`max_week_exposure` 20%; stakes are sized from the start-of-week bankroll. Reported: bets, hit rate, flat-stake ROI
with a **game-clustered** bootstrap 95% CI, Kelly ROI, bankroll curve, max drawdown, log loss of P(over) on every
priced line (raw model / stacked / no-vig market), Brier, reliability, MAE vs naive EWMA / public projection / line,
CRPS. The linear `market_blend` survives only as a validation diagnostic (1.0 = "model adds nothing").

## Simulated lines (and why they are built this way)
`SimulatedSharpLines` — **simulated, not real odds**, priced -110/-110:

    base   = r·ref_median + (1-r)·c·public_proj
    signal = c·(info_proj − public_proj) + σ_m·ε          (ε ~ N(0,1), deterministic per row)
    line   = floor(base + β_m·signal + small noise) + 0.5

* `ref_median`: out-of-sample median of a **fixed reference LightGBM model** on public data (`reference.py`).
  `r = ref_share` (default 0.5; REPORT.md shows 0 / 0.5 / 1.0).
* `info_proj` = the player's **actual in-game volume** x his pre-game efficiency: a stand-in for injury/role/game-plan
  news the market has and public data doesn't (excludes realised per-touch efficiency luck).
* **v2 fix:** the market now receives the inside info with noise σ_m and weights it with the *efficient* regression
  coefficient β_m (fit on 2017-18). σ_m is solved so that MAE(line)/MAE(public projection) matches the ratios on the
  ESPN 2025 lines (pass 0.82, rush/rec 0.93); it came out at pass β=0.41, σ=59.6; rush β=0.08, σ=73.4; rec β=0.09,
  σ=60.5. In v1 the line under-reacted to a noiseless signal, and the stacker learned to decode it (73% hit rate in
  a smoke test). Disclosure: three aggregate ratios from the 2025 real lines informed the *simulator* only.
* `c` = median multiplier so the over-rate is 50% on 2016-18. Real 2025 ESPN lines actually go over only 46-49% of the
  time and sit 2.7-4.6 yds above the simulated ones on the same player-games.

## Plugging in real historical lines
Put a CSV in `data/lines/` with this schema (header required; one row per player/game/market/book):

| column | type | notes |
|---|---|---|
| `season` | int | e.g. 2025 |
| `week` | int | regular-season week 1-18 |
| `player_id` | str | nflverse GSIS id (e.g. `00-0033873`); optional if `player_name` is given |
| `player_name` | str | used when `player_id` is blank (case/punctuation/suffix-insensitive match) |
| `team` | str | optional nflverse team abbreviation (disambiguates name matches) |
| `market` | str | `pass_yds` \| `rush_yds` \| `rec_yds` |
| `line` | float | e.g. 254.5 (integer lines are fine — pushes are handled) |
| `over_price`, `under_price` | int | American odds, e.g. -115 / -105 |
| `book`, `timestamp` | str | optional; timestamp should be the **observation time, pre-kickoff** (ESPN's `lastUpdated` is not: it is kept as `espn_last_updated`) |

If several rows match one player-game-market the first row wins (pre-sort by book preference). Then either set
`lines.source: csv` and `lines.csv_path` in a config, or run
`python -m nflprops.run_backtest --champion --lines-csv data/lines/your_file.csv --seasons 2023-2025`.
Only player-games in the model's universe (starting QBs; RB/WR/TE with public projection ≥ 20 yds) are scored.
`data/lines/espn_bet_2025_open_uncertain_timing.csv` (ESPN BET lines of uncertain timing, 2025 weeks 1-13) is an example in this schema; v1 files are in `data/lines/archive_v1/`.
**Where to get more:** The Odds API sells historical player-prop odds snapshots (paid plan; not signed up for here);
other options are your own daily snapshots going forward (the sibling `/workspace/prop-finder` project already
snapshots ESPN/DraftKings lines) or a commercial historical props dataset.

## Anti-overfitting design ("gets better with each backtest", done honestly)
* **Strict time order everywhere**: as-of-kickoff features (tested against player *and* schedule scrambles),
  expanding-window training, out-of-fold residual distribution and scale, a stacker fit only on earlier weeks.
* **Three disjoint periods**: validation 2019-2022 (candidate comparison, betting-parameter tuning), selection
  2023-2024 (promotion test only), holdout 2025 (**frozen**: scored once by `holdout.py` with the policy in
  `configs/holdout_policy.yaml`, whose sha1 had to be published in REPORT.md first; `summary.py` only reads the result).
* **Proper scoring rule on raw probabilities**: candidates are compared on raw model log loss at the line, not on
  market-blended probabilities (which hid differences in v1).
* **Promotion rule**: better overall *and* in ≥3/4 validation seasons; then a selection-season gain > Φ⁻¹(1−α/m) × SE,
  where SE is from a paired game-clustered bootstrap (α = 0.05, m = promotion tests so far, Bonferroni).
* **Everything is logged** (`experiments/runs.jsonl`/`runs.csv`, `champion.json` with `n_candidates_tried` and
  `n_promotion_tests`).
* **Versioned caches**: features, predictions and reference forecasts are keyed on code version + config.
* The line simulator and the reference model are part of the *environment* and are never tuned by the loop. Promotions
  are still improvements *against the simulator* (Tester1 B3).

## Limitations
* Simulated lines decide every 2019-2024 betting number; real-price evidence is one book, 13 weeks, timing uncertain.
* With min_n = 300 and only in-season real history, the real-line stacker could not bet pass yds at all and rec yds
  only from week 4 (it placed no rec bets); the 2025 real test therefore placed just 18 bets.
* No injury reports, depth charts, weather forecasts at bet time or line movement (not added this pass by instruction).
  The projected starter is simply last game's starter.
* -110 pricing in the simulation vs typical -115/-115 at ESPN BET (real CSV prices are used when present).
* Next steps: real timestamped open + close lines and CLV tracking; news/injury features; 2026 as the next frozen holdout.
