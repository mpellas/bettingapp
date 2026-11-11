# Review of `/workspace/nfl-props`: findings, diagnostics, and ranked recommendations

Reviewer: tester1. Written 2026-10-04 (PT). The project directory was **not modified**: I took SHA-1 checksums of every file outside `.venv` before and after, and they are identical (`project_checksums_before.txt` / `_after.txt`). All analysis code and outputs are in `/workspace/tester1-review/` (`diag1.py` … `diag7.py`, `out/*.txt`). It imports the builder's code read-only via `PYTHONPATH`, with `PYTHONDONTWRITEBYTECODE=1`, using its own venv.

Every number below comes from the builder's files or from my scripts. **Anything that selects a parameter on 2025 is IN-SAMPLE on the holdout and is labelled that way.**

---

## (a) Plain summary

The model forecasts yardage better than naive baselines, but its mean is less accurate than the real ESPN BET opening lines (2025 MAE 28.72 vs 27.59 on the 2,373 priced lines). Its raw over-probabilities are worse than the market's (log loss 0.7043 vs 0.6912). The +3.0% ± 5.9% ROI on 995 bets is statistically indistinguishable from zero:
- t-test p = 0.31
- clustered by game: 95% CI [−2.7%, +8.9%]
- clustered by week: [−5.2%, +10.7%]

It also comes from an untuned diagnostic policy. Part of it relies on features that were not known when the opening lines were posted: closing spread/total and game-day weather. Without them, the same policy goes to −0.1%. The improvement loop could not have promoted anything as built. It optimises log loss against **simulated** lines, on probabilities already shrunk 90% toward the market, so a 0.0005-nat margin there equals roughly 0.005–0.02 nats of raw model improvement. There is one encouraging sign. Where the model disagrees with the opening line, the line tends to move toward the model before the game (Spearman 0.18–0.24). That is worth building on, but it needs real, timestamped closing lines to confirm.

---

## (b) Bugs, leakage, and design flaws (file:line)

| # | Severity | Where | Problem | Evidence |
|---|---|---|---|---|
| B1 | **High (look-ahead vs opening lines)** | `features.py:144-145` (`team_spread`, `implied_tt` from nflverse `spread_line`/`total_line`), `:159` (`mkt_proj_*` uses `implied_tt`), `:176` (`wind`, `temp`), `:149-150` (`is_starting_qb` = the actual starter), and the docstring at `:5-7` | nflverse spread/total are **closing** lines and wind/temp are **observed** game-day values. The 2025 holdout bets against ESPN **opening** prop lines (`holdout.py:41-43`, `data/lines/espn_open.csv`). So the model sees information the opener didn't have. The docstring says "available at kickoff", which is only true if you bet at kickoff against closing prop lines. | Ablation `diag6.py`: removing the 8 late-information columns moves diagnostic-policy ROI from +3.02% to −0.12% (997 bets) and LL at w=0.3 from 0.6899 to 0.6913 (market 0.6912). |
| B2 | **High (promotion is near-impossible by construction)** | `improve.py:185-187`, `tuning.py:17-30`, `configs/default.yaml:63,66` | Champion and challenger are compared on **blended** probabilities, using each config's validation-tuned `market_blend`. That blend was 0.9 for **every** run, which is the edge of the grid (1.0 isn't offered). The fixed 0.0005-nat margin is then applied to differences shrunk by roughly 10–40×. | `diag7.py`. Selection-season gain of each logged challenger at blend 0.9 / 0.5 / 0.0: iter 1 (lr=0.015) +0.000066 / +0.00075 / **+0.00272**; iter 3 (min_child=20) +0.000105 / +0.00055 / **+0.00122**; iter 4 (leaves=7) +0.000071 / +0.00067 / **+0.00224**. All 4 challengers would have cleared 0.0005 on raw probabilities. Whether they *should* is another matter: they are improvements against a simulator (see B3). |
| B3 | **High (design)** | `improve.py` (whole loop), `lines.py:54-97` | Every candidate is scored against `SimulatedSharpLines` (a reference LightGBM on the same public features plus an oracle term built from **actual** in-game volume). So the loop measures closeness to the simulator, not edge against real books. The builder's own sensitivity table shows the verdict flips with `ref_share`. | REPORT.md sensitivity table (`ref_share` 0 → +5.3%, 1.0 → −29.2%) |
| B4 | Medium | `leakage.py:27-42` | The scramble test perturbs only player stats and snap shares. It never touches schedule-derived columns (spread/total/wind/temp/QB id), so it cannot detect B1. Its PASS is true but narrower than it reads. | Code |
| B5 | Medium | `import_espn_lines.py:50,56` | `timestamp` is the prop item's `lastUpdated`, not the time the line was observed. So "pre-kickoff" can't be verified, and `espn_current.csv` can't safely be used as a closing line. With multiple main over/under pairs, the last one silently wins (`:47-50`). | 99.3% of timestamps in both `espn_open.csv` and `espn_current.csv` are after kickoff (`schedules.parquet` gameday+gametime, ET). 26 athlete-markets have 2 main pairs. Example: Dak Prescott wk1 open 244.5, current 217.5. |
| B6 | Medium | `report.py:22-25` (`_ci`), `REPORT.md` | The ROI CI assumes independent bets. Bets cluster heavily: 5.16 bets per game on average (max 11); 246 QB-pass + same-team rec-yds pairs, 149 of them on the same side; 26 player-games with both a rush and a rec bet. | Game-cluster bootstrap 95% CI [−2.7%, +8.9%]; week-cluster [−5.2%, +10.7%], vs reported ±5.9% |
| B7 | Low-Med (silent staleness) | `backtest.py:79` (prediction cache keyed only on config hash), `features.py:199` (feature cache reused if the file exists) | If `features.py` / `model.py` code changes but the config doesn't, stale cached features and predictions are reused silently. Adding the new features below would appear to "do nothing". | Code |
| B8 | Low | `betting.py:31-38`, `default.yaml:67` | Edge is measured against the no-vig price, but the EV>0 filter at −115/−115 needs about 3.5 pp of edge. So the 0.02 and 0.03 thresholds in the grid are no-ops; at −110 sim pricing, 0.02 is too. | `diag2.py`: bets at 2% and 3% thresholds are nearly identical for every w (e.g. w=0.5: 1,145 vs 1,142) |
| B9 | Low | `model.py:46-51` | The scale model is fit in-sample on OOF \|res\|, then z = res/s on the same rows (slightly optimistic z). `z_mean` is computed and never used. The Z shape is one global distribution per market per season (see D4 for its conditional miscalibration). | Code + D4 |
| B10 | Low (process) | `summary.py:141-160` | Every `summary` run re-scores the holdout at blends 0 / 0.5 / 0.9. That is small repeated peeking at 2025, and it should stop once 2025 is used for decisions. | Code |

**Not a bug:** I checked the "mean vs median" worry. The model predicts a mean with L2, but `P(over)` comes from an **empirical** standardized-residual distribution. That distribution is skewed for rush/rec (P(z<0) ≈ 0.58, median z ≈ −0.25 in every training window). Out of sample, P(actual < model median) over 2019-2025 is 0.508 for pass, 0.499 for rec and 0.489 for rush. A symmetric normal on the same μ, s would give mean P(over) = 0.542 on the 2025 real lines, against 0.480 empirical and 0.472 observed. So the empirical residual is doing its job.

---

## (c) Diagnostics run (actual results)

All on the builder's cached 2025 real-line predictions (`data/cache/preds/preds_04cd0d349a_2025.parquet`), unless noted. I reproduced the headline exactly: 995 bets (363 over / 632 under), hit 54.87%, flat ROI +3.02% ± 5.85%, bankroll 1000 → 1052.1. I also re-ran the champion's 2025 walk-forward and got bit-identical μ (max |Δ| = 0).

### D1. Significance of the +3.0%
- t-test vs 0: t = 1.01, p = 0.313. Average break-even win probability at the actual prices is 0.5337; binomial P(hit ≥ 54.9% | break-even) = 0.178.
- Cluster bootstrap: by game (193 clusters) 95% CI [−2.7%, +8.9%], P(ROI>0) = 0.85. By week (13 clusters) [−5.2%, +10.7%], P = 0.77.
- Per-bet SD of flat profit is 0.942. Confirming a true +3% ROI at 80% power needs about **7,700 bets**; ±3% CI half-width needs about 3,800. For +5% ROI: about 2,800 and 1,400.

### D2. ROI breakdown (diagnostic policy, holdout)
| slice | n | hit | flat ROI | 95% CI (iid) |
|---|---|---|---|---|
| pass over / under | 104 / 59 | .548 / .525 | +5.2% / −1.3% | ±19.5 / ±24.2 |
| rec over / under | 183 / 368 | .563 / .562 | +5.3% / +5.3% | ±13.5 / ±9.5 |
| rush over / under | 76 / 205 | .487 / .541 | −8.6% / +1.3% | ±21.3 / ±12.8 |
| all overs / all unders | 363 / 632 | .543 / .552 | +2.4% / +3.4% | ±9.9 / ±7.3 |
| edge 4-5% / 5-6% / 6-8% / 8-10% / ≥10% | 252/190/267/136/150 | .544/.553/.566/.566/.507 | +3.5/+3.0/+5.8/+5.8/**−5.3%** | ±12-16 each |
| weeks 1-4 / 5-8 / 9-13 | 340/284/371 | .579/.592/.488 | +9.4% / +10.8% / **−8.8%** | ±10 each |

ROI is not monotonic in edge, and the largest "edges" do worst. That usually means the large disagreements are model errors (stale role or injury info), not edge. The result also decays over the season.

### D3. Is the under lean real market bias or model bias?
On all 2,373 priced real lines:

| | pass | rec | rush | all |
|---|---|---|---|---|
| observed over rate | .499 | .473 | .455 | .472 |
| market no-vig P(over), mean | .496 | .499 | .500 | .499 |
| model P(over), mean | .517 | .480 | .457 | .480 |
| always-under ROI at actual prices | −6.9% | −1.6% | +1.85% | −1.6% ± 3.8% |
| median(actual − line) | −0.5 | −2.5 | −2.5 | −2.5 |
| mean(actual − line) | −1.3 | +2.8 | +2.9 | +2.2 |
| mean(μ − line) | +3.0 | +4.2 | +2.5 | +3.6 |

Interpretation: in 2025, ESPN's rec/rush openers were set slightly high. That fits the well-known right-skew / mean>median under bias. The model's average P(over) matches the observed rates closely (rec .480 vs .473, rush .457 vs .455). So **the under lean mostly reflects real market bias correctly captured by the skewed residual, not a model bug.** Blanket unders still lost 1.6% after vig, and the model's unders (+3.4%) are not significantly better than its overs (+2.4%). The lean alone is not a demonstrated edge. One season and one book is too little to call this bias stable.

### D4. Calibration
- **Raw model P(over) vs observed (2025 real lines)** is badly over-confident. Bins with predicted .241 / .360 / .636 / .767 observed .423 / .445 / .587 / .508. LL 0.7043 vs market 0.6912 (every market worse: pass .7047, rec .6971, rush .7230 vs about .691).
- **Model − market disagreement vs outcome:** observed − market is −0.069 in the most-negative bin and only +0.085 in the +0.08..0.15 bin, then −0.037 at > +0.15. Direction is right on average, magnitude is far too large.
- **Logistic stacking, IN-SAMPLE 2025:** logit P(over) = −0.092 + 0.625·logit(p_mkt) + 0.191·logit(p_model). The model coefficient has p = 0.039. By market, the model coefficient is: rec **0.296 (p=0.03)**, pass 0.227 (p=0.33), rush **−0.009 (p=0.95)**. On this one season, the information is in receiving yards; rushing has none.
- **Out-of-sample distribution calibration (PIT, 2019-2025 walk-forward, 26k rows).** Marginal median and 50%/80% coverage are fine (e.g. rec .499 / .511 / .808). Conditional on projection level, they are not:
  - **Pass yds:** P(actual < model median) goes from .452 (lowest μ quintile) to .584 (highest). The mean model is too extreme. The OOS linear fit actual = 59.2 + **0.743**·μ on 2019-24 confirms it needs regression to the mean.
  - **Rec/rush:** 80%-interval coverage is .883/.889 in the lowest μ quintile (too wide) and .769/.776 in the highest (too narrow). The global Z shape doesn't fit both ends.
- **Player-specific variance:** a player's prior-season mean |z| does **not** predict this season's |z| beyond s(x) (r = −0.13, 0.035, 0.094 for pass/rec/rush; all p > 0.09). Player-level variance terms aren't worth building; condition on μ level / role instead.

### D5. Shrinking toward the market (IN-SAMPLE on 2025 unless noted)
p = w·model + (1−w)·market (w = weight on the model; the builder's `market_blend` = 1−w):

| w | LL (mkt .6912) | bets@4% | ROI@4% | under share |
|---|---|---|---|---|
| 0 | .6912 | 0 | – | – |
| 0.2 | **.6899** | 150 | −5.3% | 64% |
| 0.3 | **.6899** | 442 | +4.4% | 66% |
| 0.5 (diagnostic) | .6913 | 995 | +3.0% | 64% |
| 0.75 | .6959 | 1371 | +0.8% | 62% |
| 1 (raw) | .7043 | 1600 | −1.4% | 61% |

Best LL by model weight, per market: pass ≈ 0.2 (.6894 vs .6905), rec 0.3–0.4 (.6892 vs .6913), rush ≈ 0.1 (.6909 vs .6913, essentially none).

Median-shrink alternative (model median pulled toward the line, k = weight on model): k = 0.25–0.35 gives LL .6907–.6908, ROI +3.1% / +3.4% on 413 / 689 bets. Same story, slightly worse than probability blending.

**Pseudo-out-of-sample check** (pick w on weeks 1-6, test on weeks 7-13): the chosen w = 0.35 gives LL .6931 vs market .6926 (worse than market), ROI +1.8% on 310 bets. Per-market w (pass .45 / rush .25 / rec .40) gives −1.9% on 330 bets. **No demonstrated out-of-sample edge in the second half of the season.** In-sample optimal w is not evidence; it will overfit.

### D6. Alternative distributions at the real 2025 lines
- **Normal residual:** LL .7152 raw / .6925 at w=0.3. Worse; mean P(over) .542 makes it over-biased.
- **Z conditional on projection tercile** (from training OOF only, so out-of-sample for 2025): LL .7034 raw / .6897 at w=0.3, against .7043 / .6899 baseline. Tiny gain.
- **OOS μ recalibration** (actual = a + b·μ fit on 2019-24): LL .7032 raw / .6898 at w=0.3. Tiny gain. Fixes the pass-yds slope.

### D7. Line movement from open to "current" (CLV proxy; caveat B5: "current" = last listed value, timestamps after kickoff)
- MAE vs actual: open 27.56, current 27.21. Current is only slightly sharper, so it does not look like a fully in-game line, but this can't be verified.
- Diagnostic bets: line moved **our way 543, against 300** (sign test p = 4.7e-17), mean +1.68 yds. Same pattern for overs (+1.66) and unders (+1.69). Across all lines the average move was −0.15 yds, so this is not a general drift.
- Spearman(model − market P(over), current − open) over all lines: **0.235**. Without the closing-vegas/weather features: 0.176 (502 vs 330 our way, p = 2.7e-9), with ROI −0.1%.
- Reading: the model carries real information the market prices in later. Part of it is look-ahead (B1), and in this sample the remainder did not turn into ROI against the opener. This is the best lead in the project, and it needs real timestamped closing lines.

### D8. Coverage of the real lines
Of 3,457 ESPN opening lines, 2,373 were scored. Dropped:
- 683 because the public projection was under 20 yds (559 rec, 124 rush)
- 336 QB rushing lines (the market excludes QBs)
- 61 with fewer than 2 prior games
- 4 other

---

## (d) Ranked recommendations (by expected value; effort S < 1 day, M 1–3 days, L ≥ 1 week)

> These are written so they can be pasted to the builder.

### 1. Re-base evaluation on REAL, timestamped lines (open + pre-kickoff close) and track CLV. **EV: very high · Effort: M (+ data cost)**
- **What:** buy historical player-prop odds snapshots (e.g. The Odds API historical props) for as many seasons as possible. Store the opening line and a fixed pre-kickoff snapshot (e.g. T−30 min) with true observation timestamps. Start snapshotting 2026 now from `/workspace/prop-finder`; the 2026 season is in progress, so weeks 5-18 are a genuine forward holdout. Add `clv_yds` and `clv_prob` (no-vig prob at close minus at bet time) to every bet.
- **Why:** every 2019-2024 decision is currently made against a simulator (B3). One season of one book can't confirm a 3% edge (it needs about 7,700 bets, D1). CLV is far less noisy than ROI and already shows signal (D7).
- **Files:** `lines.py` (`CsvLines`: keep `timestamp`, support `open` and `close` columns), `import_espn_lines.py` (B5: record the real observation time; don't use `lastUpdated`), `metrics.py` (`bet_metrics`: add CLV), `report.py`.
- **Verify:** pre-register the policy before 2026 week 5. Report weekly CLV and ROI with a game-clustered CI. Success means mean CLV > 0 with game-cluster bootstrap P > 0.95 over ≥ 1,000 bets.

### 2. Make features "as-of" the bet time (fix B1). **EV: high (correctness) · Effort: S–M**
- **What:** add a `bet_time` mode.
  - **Opening-line mode:** replace `spread_line` / `total_line` with opening (or T−6 days) game lines; drop observed `wind` / `temp` or use a forecast; replace `is_starting_qb` with a *projected* starter (prior-week starter plus injury status).
  - **Closing mode:** keep closing game lines, but evaluate only against closing prop lines.
- Extend `leakage.py` to scramble schedule fields after the cutoff too, and test that features don't use values recorded after `bet_time` (B4).
- **Why:** the +3.0% falls to −0.1% without the late-information features (D6/`diag6.py`).
- **Files:** `features.py:144-159,176,149`, `data.py` (game-odds source with timestamps), `leakage.py:27-42`, `markets.py:17` (QB universe uses the actual starter).
- **Verify:** re-run the 2025 real-line holdout in opening mode. Report the LL gain vs market and ROI with a game-clustered CI. Expect the headline to shrink; that is the honest number.

### 3. Fix the promotion rule (B2), and promote on real-line value. **EV: high · Effort: S**
- **What:**
  - (a) Compare challenger vs champion on **raw** model probabilities, or at one *fixed* common blend. Never at each config's own tuned blend.
  - (b) Allow `market_blend` up to 1.0 (`default.yaml:66`) and treat "best blend = 1.0" as "model adds nothing".
  - (c) Express the margin relative to the bootstrap SE of the paired gain (e.g. require lower 90% bound > 0), not an absolute 0.0005.
  - (d) Require consistency: gain > 0 in at least 2 of 3 seasons, or in each market traded.
  - (e) Once real lines exist (#1), make the primary metric **LL gain vs the real no-vig market** plus **mean CLV**, scored with a paired **game-week** bootstrap. Keep simulated-line LL only as a sanity check.
  - (f) Log the number of candidates tried and apply a multiple-comparison haircut (e.g. Holm, or a fresh-season confirmation).
- **Why:** at blend 0.9 every logged challenger's raw gain (+0.0012 to +0.0027 nats) was shrunk to +0.00002 to +0.0001 (D/`diag7.py`), so nothing could pass. Simulated-line gains also may not transfer to real books.
- **Files:** `improve.py:183-191` (`bootstrap_gain`, `add_probs` call), `tuning.py:17-30`, `configs/default.yaml:63-66`.
- **Verify:** replay the 4 logged challengers with the new rule on 2023-24. On real lines, promote only if the 2025 / 2026-forward gain is also positive. Check that a deliberately broken challenger (e.g. features shuffled) is never promoted.

### 4. Shrink toward the market with a fitted stacker, per market, chosen on PRIOR data. **EV: medium-high · Effort: S**
- **What:** replace the linear blend with logistic stacking: `logit p = a_m + b_m·logit(p_mkt) + c_m·logit(p_model)` per market `m`. Fit on prior seasons' real lines (or on a rolling previous-N-weeks window within a season, strictly before the bet). Size Kelly off the stacked p.
- **Why:** the raw model is over-confident (D4). IN-SAMPLE on 2025 the model coefficient was 0.19 overall (rec 0.30, rush −0.01) and best w ≈ 0.2–0.35; the 0.5 diagnostic blend is too model-heavy. The pseudo-OOS test (D5) shows a w tuned on early weeks didn't hold up, so the weight must come from more data than one half-season.
- **Files:** `betting.py:18-25` (`add_probs`), `tuning.py:17-25` (`choose_blend` → `fit_stacker`), new `calibration.py`.
- **Verify:** rolling-origin evaluation on real lines. Fit on all data before week t, score week t. Report LL gain vs market with a paired game-week bootstrap.

### 5. Add the news features books actually move on. **EV: medium-high · Effort: M–L**
In expected-value order:
1. **Injury / inactive status** for the player *and* teammates: nflverse `load_injuries` (practice participation, game status) plus "vacated targets/carries" from teammates ruled out or questionable.
2. **Depth chart / role:** nflverse `load_depth_charts`, snap-share trend (already have EWMA; add the delta vs the 6-game average and a route-participation proxy if available).
3. **QB change:** projected starter differs from last week's; backup-QB indicator as a feature for WR/TE rec yds; career ypa of the projected starter.
4. **Opening implied team total and spread** (as-of, see #2).
5. **Opponent pace:** opponent plays/game and seconds/play allowed; neutral-situation pass rate. Note `opp_allowed_attempts/carries` exist but pace and situation don't.
6. **Weather forecast** at bet time (wind ≥ 15 mph matters most for pass/rec); dome already exists.

- **Why:** the model's biggest losses are its largest disagreements (edge ≥ 10% bucket −5.3% ROI, D2). That pattern usually means stale role or injury information. The model − market disagreement also predicts line moves (D7), which suggests news is what moves these markets.
- **Files:** `data.py` (new loaders), `features.py` (new `FEATURE_GROUPS` entries), `leakage.py` (`ALL_FEATS`). **Bump a code/feature version into the cache keys first (B7)**, or the new features silently won't be used.
- **Verify:** an ablation per group on the 2019-24 walk-forward (MAE/CRPS) and on real lines (LL gain vs market, CLV). Keep a group only if the gain holds across seasons.

### 6. Choose which markets to trade from evidence, and widen the real-line universe. **EV: medium · Effort: S**
- **What:**
  - Suspend `rush_yds` betting until it shows information. Stacker coefficient −0.009 (p=0.95), best w ≈ 0.1, ROI −1.4% (D4/D5).
  - Concentrate on `rec_yds`, the only market with a significant model coefficient (in-sample).
  - Score every player that has a real line instead of the `min_proj ≥ 20` filter (683 real lines dropped, D8). Low-volume props are where books are typically softest.
  - Consider a QB rushing market (336 lines dropped).
  - Set per-market edge thresholds from real-line validation only.
- **Files:** `markets.py:13-22` (`universe_mask`: when a real line exists, use it as the universe), `betting.py:28-42` (per-market `edge_threshold`).
- **Verify:** 2026-forward, per market, game-clustered ROI and CLV. This is an in-sample-derived choice, so treat it as a hypothesis to confirm.

### 7. Bet sizing and exposure. **EV: medium (mostly variance and ruin reduction) · Effort: S**
- **What:**
  - Kelly on stacked / shrunk p (#4), still fractional (≤ ¼).
  - **Per-game cap**: e.g. ≤ 3 bets or ≤ 3–4% of bankroll per game. Currently 5.2 bets per game on average, max 11.
  - **Per-team-side correlation:** QB pass and same-team WR/TE rec bets on the same side are positively correlated (149 of 246 such pairs were same-side). Either size them jointly (multivariate Kelly with an estimated correlation, e.g. from 2019-24 residual correlations) or count each same-direction team cluster as one bet.
  - **Per-player cap** (26 player-games had both rush and rec bets).
  - **Max-edge cap / manual-review flag** for edges ≥ 10% (they lost).
  - Drop no-op thresholds below the vig hurdle (B8).
  - Report ROI CIs clustered by game (B6).
- **Files:** `betting.py:28-62` (`select_bets`, `simulate_bankroll`), `report.py:22-25` (`_ci`), `metrics.py`.
- **Verify:** on the 2019-24 walk-forward (simulated lines are fine for *risk* metrics) and on 2025/2026 real lines, compare max drawdown and log-growth volatility at equal turnover. Expect lower drawdown and similar mean.

### 8. Distribution refinements (conditional calibration). **EV: low-medium · Effort: M**
- **What:**
  - (a) Recalibrate μ with an OOS linear or isotonic map fit on prior walk-forward seasons. Pass-yds slope is 0.743, i.e. too extreme; this is equivalent to stronger regularization or monotone constraints.
  - (b) Make the residual shape conditional on projection level / position. Bin Z by OOF-μ tercile, or use LightGBM quantile regression at about 20 levels, or a zero-inflated / gamma-type model for rec/rush. Low-μ players have point mass at 0: 22% of the lowest rec quintile had 0 yds.
  - (c) Skip player-specific variance; it isn't predictive (D4).
  - (d) Better still, once real lines exist: model `P(Y > line)` directly with the line as an input (a classifier on y − line), which targets exactly what is bet.
- **Why:** marginal PIT is fine, but conditional coverage drifts from .89 to .77 across μ quintiles, and pass medians are biased by projection level (D4). Measured gains at the 2025 lines were tiny (LL .7043 → .7032–.7034 raw, .6899 → .6897–.6898 at w=0.3, D6), hence the low rank.
- **Files:** `model.py:39-79` (`fit_dist`, `prob_over`, `quantiles`), `backtest.py:52-65`.
- **Verify:** PIT coverage by μ quintile on 2019-24 walk-forward (target .5 / .8 in every quintile), CRPS, and LL vs market on real lines.

### 9. Engineering hygiene. **EV: low-medium (prevents silent errors) · Effort: S**
- Put a code/feature-schema version in `chash(model_key(cfg))` and in the feature-cache filename (B7).
- Record real observation timestamps for lines (B5) and assert `timestamp < kickoff` on load in `CsvLines`.
- Log the number of candidate configs evaluated next to every promotion.
- Stop re-scoring the holdout in `summary.py` (B10). Freeze 2025 results and use 2026 as the next holdout.
- Fix `import_espn_lines.py:47-50` to pick the main pair explicitly instead of "last wins".

### 10. Stop spending improvement iterations on LightGBM hyper-parameters. **EV: low · Effort: none**
- All 16 candidates moved validation LL by under 0.0004 at blend 0.9. The raw gains on selection (0.001-0.003 nats) were against simulated lines. Point the loop's search space at #2, #4, #5 and #8 (feature groups, stacker form, distribution form) instead.

---

### Reproducing these diagnostics
```
cd /workspace/tester1-review && . .venv/bin/activate && export PYTHONDONTWRITEBYTECODE=1
python diag1.py   # repro + ROI breakdowns + clustering/significance  -> out/diag1.txt
python diag2.py   # base rates, under-lean, calibration, stacking, blend sweep -> out/diag2.txt
python diag3.py   # re-fit per-season empirical Z exactly as DistModel.fit_dist -> out/zfits.pkl
python diag4.py   # reproduction check, PIT 2019-2025, player-variance test -> out/diag4.txt
python diag5.py   # OOS mu recal, normal vs empirical, conditional Z, median shrink, pseudo-OOS blend, open->current -> out/diag5.txt
python diag6.py   # late-information ablation on 2025 real lines -> out/diag6.txt
python diag7.py   # promotion-gain dilution by market_blend -> out/diag7.txt
```
