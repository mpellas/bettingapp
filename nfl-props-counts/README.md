# nfl-props-counts — NEW, UNVALIDATED challenger count models
Receptions (`player_receptions`), pass completions (`player_pass_completions`), rush attempts (`player_rush_attempts`).
NOT part of the locked nfl-props paper track. Imports /workspace/nfl-props/src read-only; never writes there.

Features: exactly the yards models' as-of path (`nflprops.features.build_features` via `nflprops.pregame.pregame_features`,
feature set "full"). Leakage scramble test re-run: PASS (out/leakage.log).
Model: LightGBM Poisson-objective mean + negative-binomial dispersion alpha (var = mu + alpha*mu^2), alpha fit by MLE on
out-of-season-fold predictions. P(over x.5) = 1 - NB_CDF(floor(line)).

## Interface (for props-finder/analyze.py)
```python
import sys; sys.path[:0] = ["/workspace/nfl-props-counts", "/workspace/nfl-props/src"]
import counts
P = counts.predict(week=5, season=2026)            # or lines=DataFrame[event_id, player_id, player_name, market, line, void_reason]
# columns: season, week, game_id, player_id (GSIS), player_display_name, team, opponent, position,
#          market in {receptions, pass_completions, rush_attempts}, odds_api_key, mu, alpha, baseline_mu,
#          n_prior_games, model_status="NEW_UNVALIDATED_CHALLENGER", cutoff
p = counts.p_over(P.mu, P.alpha.iloc[0], 4.5)        # P(X > line), vectorized; alpha is per market
```
Fitted models are cached in out/models_<season>_wk<week>.pkl (delete to refit). Run with the nfl-props venv python.
Universe: receptions = WR/TE/RB with >=1.5 targets EWMA; completions = projected starting QB (last game's starter);
rush attempts = RB with >=3 carries EWMA + projected starting QB. Players outside it get no row.
Out files: backtest_summary.csv, calibration_2025.csv, espn_line_scoring_rows.csv, pred_2026_wk5_dryrun.csv.
Caveat: the 2019–2025 backtest measures projection accuracy vs actual stats only — no historical lines for these markets.
