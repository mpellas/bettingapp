# nfl-props — NFL player-prop research pipeline (v3, after Tester1's second review)

Walk-forward research pipeline for **QB passing yards**, **RB/WR/TE rushing yards** and **RB/WR/TE receiving
yards** props: nflverse data → leakage-checked as-of-kickoff features → distributional LightGBM model (predictive
quantiles) → projection-accuracy (CRPS) experiment loop with a fixed-Bonferroni promotion test → free 2026 line
snapshots (DraftKings via ESPN) → pre-game predictions for every snapshot line → paper z-CLV tracking with void
accounting, plus a diagnostic bet track (hierarchical stacker, capped fractional Kelly).

> **Important.** No real historical prop odds exist here for 2015-2024, and the line simulator turned out to be
> learnable (Tester1 N1). Since v3, **simulated lines are used for nothing**: no promotion, no tuning, no reported
> ROI. `--simulated` in `run_backtest` is an optional diagnostic only. The only real-price result is the frozen 2025
> holdout against **ESPN BET lines of uncertain timing** (scored once, null result). 2025 is now used **only as
> training history for the stacker**: it is never re-scored and nothing is selected on it. The 2026 snapshots are
> free and have **no prices** (−110/−110 is assumed and flagged).

## Quick start

```bash
cd /workspace/nfl-props
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && pip install -e .

python -m nflprops.data                 # download + cache nflverse data; refreshes the current season/schedules if >12 h old
python -m nflprops.leakage              # leakage check on current features (must PASS)
pytest tests                            # leakage, stacker, cache keys, snapshot parsing, pre-game as-of, track voids
python -m nflprops.improve --iterations 4 --init-from experiments/archive_v2/champion.json   # v3 loop (CRPS, no lines)
python -m nflprops.summary              # reports/REPORT.md + charts

# 2026 out-of-sample workflow
nohup setsid scripts/snapshot_supervisor.sh >/dev/null 2>&1 &   # capture loop (10 min; 3 min within 45 min of a kickoff)
pgrep -af '^/bin/bash (.*/)?scripts/snapshot_(supervisor|loop)\.sh$'   # must show exactly 1 supervisor + 1 worker
python -m nflprops.snapshot             # (one manual capture) ESPN/DraftKings props for this + next week
python -m nflprops.snaplines --season 2026 --week 5      # derive D (last capture >=3 h pre-kick) and C (<=30 min)
python -m nflprops.pregame --season 2026 --week 5        # pre-game predictions for every D line (prior data only)
python -m nflprops.track stacker                         # fit the hierarchical stacker on its history (2025 real lines)
python -m nflprops.track week --season 2026 --week 5     # score a week: z-CLV, voids report, diagnostic bets
python -m nflprops.track final --season 2026 --weeks 5-18  # pre-registered decision on all tracked weeks
```
Runtime on this box (8 cores, nothing else running): features ~3 s, one season walk-forward ~6 s, one loop
iteration ~2-3 min, `pregame` ~15 s, `track week` ~15 s, `snapshot` ~6 s. Two LightGBM jobs at once slow each other
down ~10x (thread oversubscription), so run them one at a time.

## v3 changes after Tester1's second review (`/workspace/tester1-review/RECOMMENDATIONS_v2.md`)
I checked each claim before acting:
* **N1 simulator learnable — verified.** I re-ran Tester1's `s1_sim_structure.py` and got identical output: a
  structure-only decoder (no football model) earns +11.0% ROI on 234 simulated 2023-24 pass bets and loses on real
  2025 lines. → Simulated lines are removed from promotion, tuning and reporting (`tuning.py` deleted; the loop runs
  with `lines.source: none`). The simulator code stays as an optional diagnostic (`run_backtest --simulated`).
* **N2 no pre-game rows — confirmed** (`assemble_player_games` built rows only from post-game stats/snaps). → New
  `pregame.py`. The universe is **every line in the decision snapshot D** (last capture ≥ 3 h before kickoff), not
  the players who later appear in stats/snaps. Rows are built from data before the week's first game day only.
  The projected starter is the previous game's starter. Output is timestamped (UTC) and sha256-hashed and logged in
  `data/predictions/pred_log.jsonl`. As-of check: pre-game features equal the post-game build for the same
  player-games (2025 wk10: 330 matched rows × 78 features, 0 differences; also a pytest on 2024 wk7).
* **Voids (reviewers' addition).** A D line is VOID, with a reason, if it has no matching player row (no GSIS
  match / event not in schedule / no prior NFL data / player's last team not in the game), no pre-game prediction
  created before kickoff, **no closing snapshot C**, or the **player was inactive/DNP** (completed game, no stat row
  and no offensive snap). Voids are written to `data/predictions/<S>_wkWW/pregame_*_voids.csv` and
  `data/track/<S>_wkWW_voids.csv` and counted; nothing is dropped silently. The primary metric (mean z-CLV) and bet
  ROI are reported two ways: **voids excluded** and **voids counted as zero**. Lines outside the pre-registered
  model scope (public projection < 20 yds, non-projected-starter QB, QB rushing) are predicted, listed in
  `<S>_wkWW_out_of_scope.csv` and excluded from the primary metric and bets (week 4: 13 of 38).
* **N3 stale caches — confirmed.** The schedules cache never refreshed; the 2026 schedule already had week-4 scores.
  → Raw data is cached per season (`data/cache/raw/`). The current season, schedules and players are refreshed when
  older than 12 h, with every download logged in `download_log.tsv` with sha256. Feature and prediction cache keys
  include a **content hash of the data actually used** (`data_version`). **N9:** the absolute CSV path in the model key is now
  project-relative plus the file's sha1.
* **Promotion rule (N6, 3/4).** The score is the per-market relative CRPS gain over the champion on actual yards
  (validation 2019-22; no lines). A challenger must gain overall **and in ≥ 3 of the 4 validation seasons** (the v2
  README's wording was right: 3/4; Tester1 confirmed the code). On selection seasons 2023-24 it must clear
  z × SE (paired game-clustered bootstrap) with **z = Φ⁻¹(1 − 0.05/10) = 2.576 fixed**. This is a Bonferroni over a
  pre-declared maximum of 10 tests; v2's growing-m sequential bound gave α·H_m (0.075 at m = 2, N6). A real-line
  gate is wired in but "not applicable": no real lines exist outside the frozen holdout.
* **N4/N5 stacker.** The ridge stacker (one λ on a, b and c; min_n 300) is replaced by a **hierarchical** MAP
  stacker: `logit p = a_m + b·logit(p_mkt) + c_m·logit(p_model)`, a_m ~ N(0, 0.02²) (explicit, tight intercept
  prior, so it cannot bet the base rate), shared b ~ N(1, 0.1²), c_m ~ N(c0, 0.05²) pooled across markets,
  c0 ~ N(0, 0.1²). There is **no minimum line count**. History = the 2025 real lines (training history only) plus
  earlier tracked 2026 weeks. The v2 ridge stacker is kept as `stacker_v2_ridge` only so the frozen holdout stays
  reproducible.
* **N5 (λ dominates min_n)** was not re-run: Tester1's grid is holdout-exploratory and I did not want to search on 2025.
  The code supports it; it is moot now that both are gone.
* Prices: provider 100 (DraftKings) is the only provider ESPN lists, and its propBets carry targets only (open and
  current line), **no prices**. Providers 58, 1004 and 2000 return 404. ESPN `lastUpdated` can be later than our own capture
  time, so it is not an observation time; we use our own capture timestamps.

## v2 changes after the first Tester1 review (`/workspace/tester1-review/RECOMMENDATIONS.md`) — history
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
* **v3 loop (CRPS on actual yards, no lines):** started from the v2 champion's model. 4 iterations, 16 candidates,
  2 promotion tests, **0 promotions → champion unchanged** (`aa4d70b859`; same model settings as v2's
  `557e6ab3e4`, num_leaves 7; the hash differs only because the line/betting config changed). Both challengers were
  `n_estimators=200` variants that improved validation CRPS in 4/4 seasons:
  * selection gain 0.00178 ± 0.00075 SE vs a margin of 0.00192;
  * selection gain 0.00186 ± 0.00088 SE vs a margin of 0.00227.

  Under v2's growing-m margin (z = 1.645 at m = 1) the first would have been promoted; under the fixed Bonferroni
  it was not.
* **Champion projection accuracy, walk-forward 2019-2024:** CRPS 20.42. MAE 28.86 vs 30.46 for a naive EWMA and
  30.22 for the public projection. 80% interval coverage 81.1%; mean PIT 0.501.
* **Frozen 2025 holdout** (v2 policy, scored once, ESPN BET lines of uncertain timing): 18 bets, all rush yds, flat
  ROI −6.7% [−45.4%, +34.2%]. **Null result.** Not re-scored in v3.
* **v3 stacker on the 2025 history (2,363 lines):** b = 0.98; c_pass = 0.03, c_rec = 0.05, c_rush = 0.04 (posterior
  SE ≈ 0.08 each), so the model weight is indistinguishable from 0 and stacked p ≈ market. With no prices in the
  2026 snapshots, p_mkt = 0.5 everywhere, so expect very few or no diagnostic bets.
* Simulated-line ROIs from v1/v2 are no longer reported (see the REPORT appendix for why).

## Layout

| path | what |
|---|---|
| `src/nflprops/data.py` | nflverse download + per-season parquet cache in `data/cache/raw/` (refresh of current season/schedules/players when stale; `download_log.tsv`; `data_version`) |
| `src/nflprops/features.py` | player/team/opponent/game-proxy/static-context features, as of kickoff (`FEATURE_VERSION`, `code_version`) |
| `src/nflprops/legacy/features_v1.py` | v1 features with look-ahead — DO NOT USE; kept only for the leakage regression test |
| `src/nflprops/leakage.py`, `tests/` | scramble-the-future leakage test (player + schedule fields), legacy must-fail test, stacker, caps, cache-key, snapshot, pre-game as-of and track-void tests |
| `src/nflprops/markets.py` | market definitions + pre-game "would a book post this line" universe filter |
| `src/nflprops/model.py` | `DistModel`: LightGBM mean + cross-fitted LightGBM scale + empirical out-of-fold standardized-residual distribution |
| `src/nflprops/calibration.py` | hierarchical MAP stacker `hier_stacker` (default) + legacy `stacker_v2_ridge` (frozen-holdout reproduction only) |
| `src/nflprops/reference.py` | fixed reference model used only by the (diagnostic-only) simulated market |
| `src/nflprops/lines.py` | line sources: `NoLines` (default, `source: none`), `CsvLines` (real lines), `SimulatedSharpLines` (diagnostic only) |
| `src/nflprops/betting.py` | no-vig, edge threshold, fractional Kelly with per-bet/game/team/player/week caps, week-by-week bankroll |
| `src/nflprops/backtest.py` | expanding-window walk-forward engine (prediction cache in `data/cache/preds/`, keyed on config + code + data version) |
| `src/nflprops/metrics.py` | metrics (CRPS, PIT, MAE, hit rate, ROI, drawdown, Brier, log loss, reliability) |
| `src/nflprops/snapshot.py`, `snaplines.py` | free ESPN/DraftKings prop snapshots (raw JSON, capture log, daily sha256 manifest) → D/C line files |
| `src/nflprops/pregame.py` | pre-game predictions for every D line (prior data only; timestamped + hashed; void report) |
| `src/nflprops/track.py` | 2026 paper z-CLV + diagnostic bet track, weekly void and out-of-scope reports, two result versions |
| `src/nflprops/improve.py` | v3 experiment loop (CRPS, no lines), `experiments/runs.jsonl` + `runs.csv`, `experiments/champion.json`; v2 loop in `experiments/archive_v2/` |
| `src/nflprops/holdout.py`, `configs/holdout_policy.yaml` | one-time frozen holdout with the pre-declared policy → `experiments/holdout_frozen.json` |
| `src/nflprops/summary.py`, `report.py`, `run_backtest.py` | reports (game-clustered CIs), CLI |
| `audit/` | my verification of Tester1's claims against v1 |
| `data/snapshots/`, `data/lines/snap_*`, `data/predictions/`, `data/track/` | 2026 captures, D/C lines, pre-game predictions, tracked weeks |
| `configs/default.yaml` | every knob (periods, model, lines source, stacker prior, betting, loop settings) |
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

## Betting logic (diagnostic bet track only)
`p_used` = the **hierarchical stacker** (`calibration.py`, see v3 changes), fit on the history (2025 real lines) plus
strictly earlier tracked 2026 weeks. Pick the side with the larger edge `p_used − p_novig`; bet if edge ≥ 4% and
EV > 0 at the price (−110 assumed and flagged when the snapshot has no price). Stake = ¼ Kelly on `p_used`, applied
greedily by edge within each week with caps: 2% per bet, 4% and 3 bets per game, 3% per team-game, 1 bet per
player-game, 20% per week. Only in-scope, non-void lines can be bet; a bet on a line that is later voided is
refunded. Reported: flat ROI and hit rate with game-clustered CIs, voids excluded and voids counted as zero. The
bet track is descriptive; the confirmatory metric is paper z-CLV.

## 2026 tracking: snapshots, D/C, pre-game, voids
* `snapshot`: ESPN scoreboard (this + next week) → per-event odds list → propBets pages for every listed provider.
  Raw response bytes are saved unmodified to `data/snapshots/<PT date>/` with our own UTC capture time in the filename.
  Each run adds a `capture_log.jsonl` record per event and rewrites the day's `MANIFEST.sha256`. Hash changes are
  appended to `manifest_log.txt`. Games that have started are skipped, events captured < 5 min ago are skipped
  (idempotent), and files are never overwritten.
* Capture schedule: `scripts/snapshot_supervisor.sh` runs `scripts/snapshot_loop.sh`. The worker runs a pass every
  10 min, or every 3 min while any game kicks off within 45 min. Games within 60 min of kickoff are re-captured if
  their last capture is ≥ 2 min old, others if ≥ 9 min old. Every pass writes a `=== <time> ===` entry to
  `logs/snapshot_loop.log` (empty passes are normal). The supervisor holds a lock, so only one runs. It restarts the
  worker if it dies or if the log has no new entry for > 20 min, and records events in `logs/snapshot_supervisor.log`.
  `logs/` is gitignored.
* `snaplines`: D = the last capture at or before (the kickoff reported in that capture − 3 h), i.e. the decision as
  it could have been made in real time. The **actual kickoff** is the earliest kickoff reported by any capture or by
  the nflverse schedule. C = ONLY the last capture before the actual kickoff, valid if it is within 30 min of it
  (otherwise no C for the game: a capture failure, the only thing counted in the 20% data kill rule). A D line missing
  from that capture is VOID `pulled_before_close` (never filled from an earlier capture; when it disappeared is written
  to `snap_<S>_wk<W>_pulled.csv`) and reported separately. Diagnostic bets on pulled lines follow DraftKings rules:
  they stand and settle on the stat if the player played, and are refunded only if he did not.
  Empty passes (zero yardage lines for the game) are skipped for both D and C: each is the last NON-EMPTY capture in
  its window; only if every capture in the window is empty is it a capture failure.
* Decision (`track final`, pre-registered):
  * **Signal check:** mean D→C z-CLV > 0, with a one-sided game-clustered p < 0.05.
  * **Log loss at the close:** raw-model LL gain vs ln 2 at line_C, with the CI upper bound ≥ 0.
  * **Break-even:**
    * With prices: the price rule (unchanged).
    * Without prices (PRIMARY): each week's top 20% of lines by |mu − line_D|/sd; model-side hit rate at line_D
      ≥ 53.5% with game-clustered 95% lower bound > 50%; must beat a matched control vs blanket per-market side rates (LB on mean Δ
      > 0). Over/under counts in the top-20% group are reported (no 25% floor). PROVISIONAL only when skill bars pass
      but prices are missing. Full-board 53.5%/LB>50% is diagnostic only. Blanket unders is reported and does not void
      the model PASS.
  * **Adverse case for pulled lines:** OVER picks −0.25 SD, UNDER picks 0. For hit rate, a pulled line is scored at
    line_D if the player played and is void if he did not. Passing the main rule but failing the adverse case gives
    PROVISIONAL.
  Snapshot-level voids are written in a `void_reason` column:
  * `kickoff_moved`: D is < 3 h before the actual kickoff; D is never re-picked from an older capture.
  * `duplicate_line`: a player+market has more than one line in the snapshot. ESPN/DraftKings items carry no
    main-line flag, so all of them are voided; there is no keep-first `drop_duplicates`.

  It also re-verifies file hashes, maps ESPN athlete ids to GSIS, and writes `data/lines/snap_<S>_wk<W>_{D,C}.csv`.
* `pregame`: universe = every D line. Run it after the D capture and before kickoff, once per game slot. Without a
  D file it runs as a labelled DRY RUN (recent-appearance candidates) that tracking ignores.
* `track week`: per game, uses the latest snapshot-mode pre-game file created before kickoff.
  `z-CLV = sign(P_model(over | line_D) − 0.5) · (line_C − line_D) / sd`, with sd = (q84 − q16)/2. Lines end up
  settled, pending, void (with reason) or out of scope. Mean z-CLV gets a 95% game-clustered bootstrap CI
  (4,000 resamples) and is reported with voids excluded and voids counted as zero. Outputs:
  `data/track/<S>_wkWW.parquet`, `.summary.json`, `_voids.csv`, `_out_of_scope.csv`, `_bets.parquet`.

## Simulated lines (diagnostic only since v3 — not used for promotion, tuning or reported results)
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

## Anti-overfitting design
* **Strict time order everywhere**: as-of-kickoff features (tested against player *and* schedule scrambles, and a
  pre-game vs post-game equivalence check), expanding-window training, out-of-fold residual distribution and scale,
  stacker fit only on earlier lines.
* **Periods**: validation 2019-2022 (candidate comparison), selection 2023-2024 (promotion test only), 2025 frozen
  holdout (scored once in v2; since v3 it is stacker training history only, never re-scored or used for selection),
  2026 weeks 5-18 = the next out-of-sample test (pre-registration pending).
* **Proper scoring on actual yards**: candidates are compared on CRPS of the full predictive distribution.
* **Promotion rule**: better overall *and* in ≥ 3/4 validation seasons, then a selection gain > 2.576 × SE (fixed
  Bonferroni, α = 0.05 over a pre-declared maximum of 10 tests; paired game-clustered bootstrap).
* **Everything is logged** (`experiments/runs.jsonl`/`runs.csv`, `champion.json` with `n_candidates_tried` and
  `n_promotion_tests`; prediction log; snapshot manifests).
* **Versioned caches**: features and predictions are keyed on code version + config + data content hash.

## Limitations
* No real historical lines before 2025; the 2025 real lines are one book, 13 weeks, timing uncertain.
* The free 2026 snapshots have **no prices**: −110/−110 is assumed (flagged per line), so b is unidentified and
  price-only moves are invisible. Bet-track results are provisional.
* The stacker's model weight on 2025 history is ~0.03-0.05 ± 0.08: stacked p ≈ market, so few or no bets are expected.
* No injury reports, inactives, depth charts or weather forecasts at decision time. The projected starter is last
  game's starter, and inactives are only known afterwards (they become voids).
* D/C capture depends on someone running `snapshot` on a schedule (nothing is scheduled here); a missing C makes
  a line void.
* QB rushing lines are outside the model scope (the rush model covers RB/WR/TE).
* Next steps: run the 2026 tracking with a frozen pre-registration; capture prices (needs a paid source or another
  free book); news/injury features.

## 2026 pre-registration (candidate, not binding)
`prereg/prereg_2026_wk5-18_CANDIDATE.yaml` updates Tester1's draft and their `candidate_suggestions.yaml`:
* it pins the **full git commit** of the code tree, with file sha1s as a cross-check;
* it describes the capture schedule (supervised loop);
* data checks: `kickoff_moved` and `duplicate_line` voids, and the week-4 snapshot-mode `pregame --check` result
  hash;
* a break-even rule **with prices**, which needs captured, non-flat prices at D and C for ≥ 80% of scored lines.
  It is computed in `track` as `break_even_with_prices`; otherwise the provisional without-prices bar applies.

`scripts/update_prereg_hashes.py [--check-file reports/pregame_asof_check_2026_wk04.json]` refills the hash
fields from a clean HEAD. It does not commit or publish anything. The file is binding only after yinzerduck reviews
it, commits it and publishes its sha1 before the first week-5 kickoff (Thu 2026-10-08 17:15 PT; the TNF D deadline
is 14:15 PT).
