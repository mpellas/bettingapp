# Second review (v2) of `/workspace/nfl-props`
Tester1 (Grok Bot), Sunday 2026-10-04, PT. Scripts and outputs: `/workspace/tester1-review/v2/` (`*.py`, `out/`).

**Read-only check.** I took sha1 checksums of all 298 project files (excluding `.venv`) before and after the review (`v2/project_checksums_{before,after}.txt`). They are **identical**, and no file in the project is newer than the "before" snapshot. All runs used a tar copy at `v2/proj` with `PYTHONDONTWRITEBYTECODE=1`. The original project was only read, e.g. the 2025 lines CSV, read through its original path so the builder's prediction cache key would match.

**Holdout caveat.** Every analysis below marked **[holdout-exploratory]** touches the frozen 2025 real lines. Those results are diagnostics of the metric and the policy only. They must not be used to choose a model or policy.

---
## (a) Plain summary
- **v2 fixed most of what v1 found.** As far as I can find, the look-ahead features are gone. Caches are versioned. The residual scale is fit out of sample. CIs are game-clustered. The holdout is frozen with a sha1 guard. The promotion rule now compares raw probabilities using a game-clustered SE margin and a Bonferroni correction.
- **The headline 2025 result reproduces exactly:** 2,363 priced lines and 18 bets, all of them **rush_yds unders in weeks 8–10**. Hit rate 50%, flat ROI **−6.7%**, game-clustered 95% CI [−45.4%, +34.2%]. A fresh run with no cache is bit-identical. The result is a null: 18 bets tell you almost nothing.
- **Those 18 bets come mostly from the stacker's intercept, not from the model.** The mean logit contributions are a = −0.126 and c·logit(p_model) = −0.058. The receiving weight c is 0.036, and rush c is 0.012. In practice the policy says "bet rush unders when the price is favourable".
- **The simulator fix removed the specific decoding path but not the problem.** A decoder that sees only the line's construction inputs, with no football model, still beats simulated lines: pass +11.0% ROI on 234 bets in simulated 2023–24, and +11.75% on 328 bets in simulated 2025. The same decoders lose on real 2025 lines. Simulated-line ROI, LL gain vs market, and stacker weights are still artefacts.
- **For ranking model configs only, the simulated-line raw-LL metric does track real accuracy.** Its rank correlation with CRPS on actual yards is 0.975, and 0.949 with real-2025 raw LL. So the `num_leaves=7` promotion was not misled. But the metric adds nothing over CRPS. My recommendation is to promote on projection accuracy (CRPS/PIT), use real-line LL and CLV as gates, and drop simulated lines from promotion and policy tuning.
- **The 300-line minimum barely matters.** The λ=50 ridge prior dominates: any minimum from 50 to 300 gives the same 18 bets. A hierarchical or Bayesian stacker with an explicit intercept prior, using 2025 real lines as history, is the better design.
- **For 2026 the current policy will make very few bets.** I estimate about 0–50 over weeks 5–18, which gives roughly 7–12% power to detect a true +3–5% ROI. A paper track that scores every line on CLV against a pre-kick close is the only test that can reach a decision this season. It can (about 80% power for a 0.05 correlation over about 2,500 lines). The pipeline also **cannot yet score a game before it is played** (new bug N2).

---
## (b) Verdicts on the v1 findings
| v1 | Finding | Verdict | Evidence |
|---|---|---|---|
| B1 | Look-ahead: closing spread/total, observed weather, actual starting QB | **Fixed** | `features.py:185-186` drops spread/total/wind/temp and the actual QB fields. Game context now comes from EWMAs of earlier scores with `shift(1)` (`:113-136`). `proj_starter_id` is the previous game's starter (`:126`). `retractable` (`:182`) is static: in 2015–2026 the only stadiums whose `roof` varies (ATL, DAL, HOU, IND, ARI) switch only between open and closed, and both map to `retractable=1`. Remaining design limitation: a new starter is only recognised after his first start (0.125 of starts, per the audit). |
| B2 | Promotion on blended probabilities; blend at the grid edge; fixed margin | **Fixed** | Promotion uses raw probabilities. The selection gain must exceed z·SE from a game-clustered bootstrap (`improve.py:136-147, 216-222`), with z = Φ⁻¹(1−α/m). The blend grid includes 1.0, but the blend is now diagnostic only. Note: the code requires **3 of 4** validation seasons (`default.yaml:70`, `improve.py:212`, `REPORT.md:98`), not "4/4" as the builder's summary says. The promoted challenger happened to win 4/4. |
| B3 | Promotion is measured against a simulator | **Not fixed** (lessened) | The selection metric is still raw LL against `SimulatedSharpLines`, and the simulator is still decodable (see (d)(1)). The saving grace: the ranking it produces agrees with CRPS on actuals. |
| B4 | The leakage test didn't touch schedule/QB fields | **Fixed** | `leakage.py:28-53` scrambles schedule fields, swaps roof open/closed and randomises QB ids. Current features pass; `legacy/features_v1.py` fails. |
| B5 | ESPN timestamps are last-update times; duplicate main pairs | **Partial** | Labels are now honest (`espn_bet_2025_open_uncertain_timing.csv`; the policy states 99.3% of timestamps are after kickoff). Duplicate pairs: the importer now keeps the most balanced pair and records `n_main_pairs` (`import_espn_lines.py:57-71`). The timing itself can't be fixed retroactively, which is why the 2026 snapshot capture below matters. |
| B6 | ROI CI assumed independent bets | **Fixed** | `metrics.cluster_bootstrap_roi` is game-clustered and is used in REPORT and the holdout; `summary.py` adds a week-clustered CI. |
| B7 | Silent stale caches | **Fixed** for code (new data issue: N3) | The prediction key is config hash + `code_version(CODE_FILES)` (`backtest.py:74-79`). The feature cache key includes `code_version(data.py, features.py)` (`features.py:245-253`). The reference cache is also versioned. The keys do not include a hash of the **data** (N3). |
| B8 | Edge thresholds below the vig were no-ops | **Fixed** (residual nit) | The grid starts at 0.03 (`default.yaml:74`). At −115/−115 the break-even no-vig edge is 0.0349, so 0.03 is still a no-op on typical real prices. That's harmless because the frozen value is 0.04. |
| B9 | Scale model fit in-sample | **Fixed** | Cross-fitted `s_oof` (`model.py:46-54`), so z is out of sample. |
| B10 | `summary` re-scored the holdout | **Fixed** | `summary.py` reads `experiments/holdout_frozen.json`. `holdout.py` refuses a second run and checks the policy sha1. Policy timing (PT): file mtime 13:32:32, loop finished 13:42:26, declared in REPORT 13:42:47, holdout scored 13:45:13. The declaration came after the loop finished, but the policy names "whatever champion" generically and was written before the loop finished. Acceptable. |

v1 recommendations: #2 (as-of features), #3 (promotion), #4 (stacker), #7 (exposure caps) and #9 (hygiene) were done. #1 (real timestamped lines and CLV) was not done; it is the core of (d)(2). #5 (news/injury features) and #6 (wider real-line universe) were not done.

---
## (c) New bugs and issues (file:line)
| # | Severity | Where | Issue | Evidence |
|---|---|---|---|---|
| N1 | **High (design)** | `lines.py:54-106` (`line = floor(base + β·signal + noise)+0.5`, `base = 0.5·ref_med + 0.5·c·pub`); used by `improve.py` and the sim sections of `REPORT.md` | The simulated line's fixed base recipe can be exploited by anything that estimates ref_med or the public projection better than the 50/50 mix. Simulated ROI, LL-vs-market and stacker weights overstate real edge. | `v2/out/s1_sim_structure.txt`: the T1 structure-only decoder wins on simulated lines and loses on real ones. T2b: on the same 2025 player-games, the stacker weight c is 0.413 against simulated lines vs 0.122 against real (rec), and 0.643 vs −0.009 (rush). See (d)(1). |
| N2 | **High for 2026** | `features.py:44-54` (`assemble_player_games`) | Rows exist only for players with post-game stats or snaps, and nothing builds pre-game rows. The pipeline **cannot produce a prediction for an unplayed game**, so live betting is impossible as shipped. Backtests are fine because the conditioning matches book void rules. | Code. A grep found no roster, depth-chart or upcoming-game path. |
| N3 | Medium (live) | `data.py:78-91` (the `schedules` cache name has no season or date; a cached file is reused unless `--refresh`); `features.py:245-253` (key = seasons + code only) | During the season the data and feature caches go silently stale. A refresh rebuilds everything, and a stale feature cache would be reused under the same key. | Code. The cached `schedules.parquet` already contains 2026 with scores through week 4 (50 games). |
| N4 | Medium | `calibration.py:26-35` (the same λ penalises a, b and c); `lines.py:84,106` (constant −110/−110) | (i) The intercept a learns the season's over/under base rate and drives the bets, so the "model" bets are a base-rate bet. (ii) b is **unidentified** on simulated lines, where p_mkt is always 0.5 and b stays at its prior of 1, and weakly identified on real lines, where it varies only through price skew. The stacker never sees the line itself, so it can't learn "market right on the median, wrong on the level". | `v2/out/s3_stacker.txt`: for the 18 bets, mean a = −0.126, (b−1)·logit(p_mkt) ≈ 0, c·logit(p_model) = −0.058. |
| N5 | Low-Med | `calibration.py:57` + `default.yaml:55-56` | λ=50 and min_n=300 shrink twice, and λ dominates (see (d)(1)). min_n only stops pass from ever betting and delays rush to week 8. | `v2/out/s3_stacker_grid.csv` |
| N6 | Low | `improve.py:216-218` | Sequential Bonferroni with m = tests so far bounds the family-wise error rate by α·H_m (0.075 at m=2), not α. Negligible now; pre-declaring a fixed m would fix it. | Code |
| N7 | Low | `lines.py:84` | Simulated prices of −110 make simulated ROI easier than real lines, which are typically −115/−115 (break-even edge 0.0238 vs 0.0349). | Code + `audit/verify_tester1_v1.txt` |
| N8 | Low | `lines.py` pass calibration | Simulated pass lines are unrealistic. Their correlation with real lines is 0.476 (v1: 0.744). Real 2025 pass lines are compressed toward the mean (OLS: 114.1 + 0.228·ref + 0.278·c·pub) while the simulator follows ref (0.850·ref + 0.123·c·pub). | `s1` T4 |
| N9 | Low (portability) | backtest config → prediction key | The prediction cache key includes the absolute lines-CSV path, so a moved project recomputes rather than reusing. Not a staleness bug. | With the copy's own path the key is `0678d5e331_f9247893` instead of `e075c913fb_f9247893`. |
| N10 | Low (reporting) | `REPORT.md` sim sections | The simulated walk-forward and simulated 2025 ROI figures, and the non-monotonic ref_share sensitivity (+11.3% / +2.6% / +9.8% at 0 / 0.5 / 1.0), are presented next to the real result. Given N1 they should be labelled "simulator artefact, not evidence" or removed. | REPORT |

Other checks the builder asked for:
- **Leakage:** none found in `features.py` or `data.py`, including the schedule, weather, QB and roof fields (B1 row above).
- **Promotion rule:** game-level bootstrap ✔, correction applied ✔ (N6 nit), blend not capped ✔.
- **Caches:** versioned by code ✔ but not by data (N3).
- **Residual scale:** out of sample ✔.
- **CIs:** game-clustered ✔.
- **18 bets / −6.7%:** **reproduced exactly**, both cached and fresh (`v2/out/r1_repro.txt`).

---
## (d) Answers

### (1) The simulator fix, simulated lines in promotion, and the 300-line minimum
**Can the construction still be extracted? Yes.** `v2/s1_sim_structure.py` trains a decoder on the simulator's own inputs only (line, ref_med, c·pub), with no player model, on simulated 2019–22:

| Market / test set | Decoder | LL gain vs line | Bets | Hit | ROI |
|---|---|---|---|---|---|
| pass, simulated 2023–24 | logit | +0.0014 | 234 | 58.1% | +11.0% |
| rec, simulated 2023–24 | logit | +0.0026 | 482 | 55.6% | +6.2% |
| pass, simulated 2025 | LightGBM | +0.0120 | 328 | — | +11.75% |
| **real 2025, all decoders** | | **−0.0007 to −0.0176** | | | pass −12.0%, rush −20.5%, rec (LGBM) −8.5%; the one positive (rec logit +6.0%, 167 bets) still has negative LL gain |

- In logit(over) ~ logit(p_model) + structure terms on simulated 2019–24, the structure terms are strongly significant. For rec, ref_minus_cpub has z = 7.0 and line_minus_ref has z = 5.4. On real 2025 they are insignificant, except pass ref_minus_cpub (z = 2.6), which has the **opposite sign**.
- On the same 2025 player-games, the raw-model LL gain is rec −0.0026 against simulated lines vs −0.0118 against real lines, and rush **+0.0055 vs −0.0306**.
- The simulator's information term is roughly efficient: OLS of (actual − base) on (line − base) gives a slope of 1.02 for rec, 1.07/1.16 for pass and 1.06/0.82 for rush (2019–22 / 2023–25). The exploitable part is the fixed **base** mix and its deviation from how real books blend.
- The staleness hypothesis (simulated gains growing within a season) is **not** supported (T3).

**Do simulated-line results reflect anything real?** Only the *ranking* of model configs does.
- **[holdout-exploratory]** `v2/out/s2_metric_validity.txt` gives Spearman rank correlations over the 17 logged configs:
  - simulated-validation raw LL vs CRPS on actuals: **+0.975**;
  - vs real-2025 raw LL: **+0.949**;
  - selection raw LL vs real-2025 raw LL: +0.880;
  - within the 11 non-normal-distribution configs: +0.936, +0.855 and +0.764 respectively.
- The champion (`num_leaves=7`) also improves real-2025 raw LL by 0.0008 and CRPS by 0.040 over the initial config, so the one promotion was directionally right.
- The rejected challenger (n_est=200, no market proj) is better still on real 2025 (−0.0013 LL). I'm noting that for information only; it is not grounds to switch, because that would be choosing on the holdout.
- **Levels** are not real: the edge vs market, ROI, Kelly growth, and stacker weights tuned on simulated lines.

**Recommendation:** drop simulated lines from promotion and from all betting-policy tuning.
- Promote on CRPS, PIT calibration and pinball loss of the predictive distribution against actual yards, using the same paired game-clustered bootstrap, Bonferroni correction and 3-of-4 season consistency. Test whether to require 4 of 4.
- Add a real-line gate (raw and stacked LL vs no-vig market, plus CLV) whenever real lines exist for the period.
- Keep the simulator only as a plumbing smoke test.

**The 300-line minimum.**
- **Where:** `calibration.py:57`. For each week t and market it counts strictly earlier, non-push, priced lines (history + current season). If the count is below `min_n`, it returns p_mkt, which means no bet. Configured at `default.yaml:56` and `holdout_policy.yaml:15`. In the real holdout `history=None`, so only earlier 2025 weeks count.
- **Effect in 2025:** rec becomes bettable at week 4 (363 earlier lines), rush at week 8 (305), and pass never (293 by week 13).
- **Rationale and its limits:** at n=300 the unpenalised standard error of c is about 0.29–0.31 for pass and rec and 0.22 for rush, which is larger than any plausible c, so an unshrunk fit at 300 is noise. But the λ=50 ridge adds curvature 100 to each coefficient, equivalent to a N(1, 0.1²) prior on b and N(0, 0.1²) priors on a and c.
  - At n=300 that prior outweighs the data 5–10× (shrink factor 0.10–0.17).
  - It still dominates at season end: shrink factor 0.37 for rec (n=1,487) and 0.29 for rush (n=559).
- **[holdout-exploratory]** grid from `v2/out/s3_stacker_grid.csv`:

| λ | min_n | Bets | Flat ROI (95% game-clustered CI) | Stacked LL gain vs market |
|---|---|---|---|---|
| 0 (unpenalised) | 50 | 457 | −10.1% [−18.2%, −1.9%] | −0.0083 |
| 0 | 300 | 318 | −8.0% [−18.3%, +2.5%] | −0.0021 |
| 10 | 300 | 183 | −10.0% [−22.7%, +2.1%] | −0.0003 |
| **50** | **50, 100, 200 or 300** | **18** (same bets) | −6.7% [−45.4%, +34.2%] | +0.0002 to +0.0006 |
| 50 | 500 | 0 | — | +0.0005 |
| 200 | any | 0 | — | +0.0003 to +0.0004 |
| 50, pooled across markets | 100 or 300 | 31 (1 pass, 12 rec, 18 rush) | +8.1% [−24.8%, +42.6%] | +0.0005 to +0.0007 |

- **Reading the grid:**
  - Less shrinkage loses money, so the shrinkage is justified.
  - With λ=50, bet count is set by λ; the hard cutoff only ever removes whole markets.
  - LL is not hurt at min_n 50, though this is exploratory.
  - The pooled +8.1% is noise.
- **Better design (pre-register it before using it):** a hierarchical Bayesian logistic stacker.
  - Model: logit p = a_m + b·logit(p_mkt) + c_m·logit(p_model).
  - Priors: c_m ~ N(c₀, τ²) with c₀ ~ N(0, 0.1²) pooled across markets; a_m has a **separate, tighter** prior, or is fixed at 0, depending on whether you actually want to bet base rates.
  - History: the 2025 real lines, plus earlier 2026 weeks.
  - No min_n. Use the posterior uncertainty in the bet rule instead, e.g. bet only if P(edge > 0.04) is high enough.
  - Get prices (N4) so that b is identified.

### (2) Pre-registration for 2026 weeks 5–18
A draft YAML is saved at `v2/prereg_2026_wk5-18_DRAFT.yaml` (sha1 `bea5258d4b17e88fec832da9ed5542b8e60a8693`). It is binding only once the builder fills the TODOs and publishes its sha1 **before the first week-5 kickoff (Thu 2026-10-08, 5:15 PM PT)**. Today's games (Oct 4) are week 4 in the nflverse schedule. Weeks 5–18 have **208 games**.

- **Frozen procedure.**
  - Code version `f9247893`; features `v2-asof` (code_version `164a4150`).
  - Champion `557e6ab3e4` (`experiments/champion.json` sha1 `c539240700933753f142d7dee1d0f79c4fd9e13f`).
  - Bet-track policy `holdout_policy.yaml` sha1 `c6e4aba2a15a01dbeda7bca75c49c97184932226`, verbatim except for the line source.
  - Retraining follows the config (every 4 weeks, on data strictly before the scored week). Data is refreshed weekly into a new cache directory with file hashes logged (N3).
  - Because of N2, choose one of: (a) build and hash a pre-game row builder before week 5, required for any money; or (b) score each week after its games, with as-of features, against line snapshots hashed before kickoff. (b) is valid for the paper track.
- **Markets:** pass_yds, rush_yds, rec_yds; full-game including OT; no first-half, first-quarter, milestone or combo props.
- **Lines and snapshots.**
  - Source: ESPN core propBets, provider 100 (DraftKings). Fields: `open.target`, `current.target`, `lastUpdated`. **It has no prices.**
  - Prices: The Odds API (`player_pass_yds`, `player_rush_yds`, `player_reception_yds`, DraftKings, region us). Using the README's cost formula, that is 3 credits per event per pull, so 2 pulls × 208 events ≈ 1,250 credits, about 380 a month. That fits the 500-credit free tier only if nothing else uses it.
  - **D (decision) line:** the last snapshot at or before kickoff − 3 h. This is the line any bet is placed at.
  - **C (close):** the last snapshot before kickoff, valid only within 30 min of kickoff.
  - **O (open):** the `open` field from the first snapshot containing the prop.
  - Storage: append-only raw JSON per event per pull, named `<event>_<UTC ISO>_p<page>.json`. This is the scheme `/workspace/prop-finder/data/snapshots/nfl/` already uses. Add a daily sha256 manifest. Report times in PT.
  - Feasibility, from today's week-4 snapshots (14 events, 9:20 AM–12:00 PM PT): 172 rec, 83 rush and 27 pass full-game lines, about 20 per game. 81–85% had moved from open to current, with mean |move| of 2.3 / 2.1 / 3.8 yds (rec / rush / pass). Because there is real movement, CLV is measurable.
- **Universe:** the model universe (min projection 20 yds; QB = projected starter from prior weeks) intersected with lines present at both D and C. Expected size: about 2,500 lines (the 2025 rate of 182 per week × 14) up to about 4,000 (today's DraftKings density of ~20 per game × 208 games, before matching).
- **Paper track (primary, confirmatory).** Scores every line.
  - **Primary metric: z-CLV.** s = sign(P_model(over | D) − 0.5); z-CLV = s·(line_C − line_D) / sd_m, where sd_m is the champion's predictive SD for that player-game. Report the mean over all lines with a 95% game-clustered bootstrap (4,000 resamples, seed 0), plus the correlation between logit(P_model(over|D)) and the move.
  - **Secondary metrics:** raw-model LL at line C vs ln 2 (and vs no-vig market where prices exist); stacked LL; PIT/CRPS on actuals; model-side hit rate vs line C.
- **Bet track (secondary, descriptive, notional bankroll of 1,000 units, no real money).**
  - The frozen stacker (λ 50, min_n 300, history = earlier 2026 lines from this source); edge ≥ 0.04 vs no-vig, with EV > 0 at the captured price (or an assumed −110, flagged).
  - Quarter-Kelly. Caps: bet 2%, game 4% and 3 bets, team 3%, one bet per player-game, week 20%.
  - Report flat ROI with a game-clustered CI, the bankroll path, and the bets' z-CLV.
- **Being realistic about bet counts.**
  - The 2025 analogue made 18 bets in 13 weeks.
  - In 2026 the stacker starts from zero history at week 5. At today's density, rec reaches 300 lines after roughly 2 weeks, rush after roughly 4, and pass not until roughly week 15. That is an approximation.
  - λ=50 then lets bets through only where the intercept or price skew is large.
  - **Expect about 0–50 bets, quite possibly in the low tens or zero.**
- **Power** (`v2/out/s5_power.txt`; per-bet SD 0.94; independent bets, so clustering makes it worse):

| Bets | SE(ROI) | Power at true +3% | Power at true +5% |
|---|---|---|---|
| 18 | 0.222 | 0.07 | 0.08 |
| 50 | 0.133 | 0.08 | 0.10 |
| 80 | 0.105 | 0.09 | 0.12 |
| 300 | 0.054 | 0.14 | 0.23 |

  - 80% power needs about **6,100 bets at +3%** or about **2,200 at +5%**.
  - The paper z-CLV correlation over 2,500 lines has SE ≈ 0.020 (0.024 with design effect 1.5). That gives about 80% (65%) power at ρ=0.05 and ≈100% (99%) at ρ=0.10.
  - The stacked LL gain had SE ≈ 0.00056 over 2,363 lines in 2025, and the raw LL gain ≈ 0.0045.
- **Decision rule.** One final analysis after week 18, plus a futility-only interim after week 11.
  - **Success:** paper z-CLV mean > 0 with one-sided game-clustered p < 0.05, **and** raw LL at line C not worse than ln 2 (CI upper bound ≥ 0). Success leads to a *new* pre-registration for small real stakes. The bet track never decides go/no-go by itself.
  - **Failure:** point estimate ≤ 0, or upper bound < +0.01. No betting; go back to modelling with real-line metrics.
- **Kill criteria.**
  - **Data:** a week with more than 20% of universe lines lacking a valid C snapshot is flagged; two flagged weeks means stop and fix the capture.
  - **Futility at week 11:** z-CLV < 0 with upper bound < +0.02 means stop the bet track; the paper track continues.
  - **Drawdown:** a notional drawdown above 25% stops the bet track.
  - **Integrity:** any edit to the frozen code, config or policy, or a week whose snapshot hash wasn't logged before kickoff, means that week is excluded and reported.
  - Nothing is re-tuned on 2026 data during the tracking period.
- **Paper track: yes, definitely.** It is the primary track, because it is the only one with power this season. It also builds the timestamped real-line history that the stacker and promotion rule need.

---
## (e) Next steps, ranked by expected value
1. **Start timestamped snapshot capture and the paper track before Thu Oct 8, 5:15 PM PT.** This is time-critical: every missed week is lost evidence. Run a scheduler around each kickoff (D at −3 h, C at ≤ −15 min), keep the append-only JSON plus manifest, and publish the pre-registration sha1. Effort S–M. The prop-finder snapshot code already does most of this.
2. **Remove simulated lines from promotion and policy tuning.** Promote on CRPS/PIT/pinball vs actuals, with a real-line LL and CLV gate. Label or remove the simulated ROI results in REPORT (N1, N10). Effort S.
3. **Build a pre-game scoring path and data-hashed caches (N2, N3)**, with the projected starter taken from injury reports and depth charts rather than the previous game. This is a prerequisite for any real-money bet, and it fixes the 12.5% starter lag. Effort M.
4. **Replace λ + min_n with a pre-registered hierarchical stacker** (pooled c, an explicit intercept prior, 2025 real lines as history), and capture prices so b is identified (N4, N5). Validate on 2026 paper data only after the tracking period, or on a pre-declared split. Effort S–M.
5. **Add more real lines and the news features books move on:** purchased historical props with timestamps; injury, inactive and vacated-volume features; opening implied totals captured as-of. Effort M–L. This is the only route to an edge large enough to survive the vig.

### Artefacts
- `v2/r1_repro.py` → `out/r1_repro.txt`: reproduction of the 18 bets / −6.7%.
- `v2/s0_build.py`: frame builders.
- `v2/s1_sim_structure.py` → `out/s1_sim_structure.txt`, `out/T1_structure_decoders.csv`: simulator decoders.
- `v2/s2_metric_validity.py` → `out/s2_metric_validity.{txt,csv}`: metric rank validity [holdout-exploratory].
- `v2/s3_stacker.py` → `out/s3_stacker.txt`, `out/s3_stacker_grid.csv`: stacker and min_n [holdout-exploratory].
- `out/s4_misc.txt`: simulator efficiency, roof staticness, 2026 schedule.
- `out/s5_power.txt`: power.
- `prereg_2026_wk5-18_DRAFT.yaml`.
- `project_checksums_{before,after}.txt` (identical).
