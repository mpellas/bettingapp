# NHL SOG model feature audit (2026-11-02, read-only, paper only)
Frozen model c3ab760178 is a LightGBM Poisson model with a NegBin k of 21.9, trained through 2026-10-10. Live code was untouched, there was no --rescore, and all experiments retrain copies under this folder.

## 1. Features the model actually uses (26)
The source for all of them is the NHL.com skater game logs (data/s2021-s2026.pkl). Every feature is built strictly from prior games (shift(1)) and is guarded by the leakage test in model.py.
- Offense (player): shots, TOI, PP TOI and shot attempts (totalShotAttempts) as rolling means over the last 5, 10 and 30 games. Also SOG/60 and attempts/60 over 5, 10 and 30, career shots/game, and n_prior games.
- Defense (opponent): opp_sa_r20, the shots the opponent allowed per game over its last 20, all positions pooled.
- Team: team_sf_r20, the team's own shots per game over its last 20.
- Context: home, D (defenseman flag), rest days (capped at 10), b2b.
- NOT model inputs but used downstream:
  - The 0.95 DK no-vig blend.
  - The slot veto (opponent SOG allowed to the player's TOI/PP slot).
  - The DailyFaceoff lineup, used for the team/trade check and role_check promotion/demotion vetoes.
  - The 12h lineup freshness rule.
  - recent_form and shrink gates.
- Absent entirely:
  - Goalie, game total or score effects, linemate quality, and PP unit as a model input (only TOI is used).
  - Opponent suppression by position, Corsi against, shot-through/blocks, travel or time zone, opponent rest, injuries or teammates out, and ref or arena scorer bias.

## 2. Gaps and the cheap check
For each feature group I retrained the same recipe, training on 2021-24 with early stopping on 2024-25, and tested on the full 2025-26 season. That is 46,669 player-games: a stats-only SOG count prediction, not betting. The table shows the change in log-loss ×1000 (negative is better), with a 95% CI from a bootstrap over games.

| Added | Δ NLL×1000 | 95% CI |
|---|---|---|
| A: opponent shots allowed to F vs D (r20) | -0.31 | -0.55 to -0.08 (real) |
| C: opponent attempts allowed + shot-through ratio | -0.13 | -0.32 to +0.05 |
| D: pace (team and opponent attempts for) | -0.11 | -0.35 to +0.13 |
| B: PP share of team PP time + PK TOI | +0.03 | noise |
| E: opponent on a back-to-back | +0.05 | noise |
| All of the above | -0.62 | -0.92 to -0.30 (real) |

All of these improvements are real but tiny. About 0.04% of log-loss and roughly 0.0001 Brier at the 2.5 line is far smaller than the ~4.5% vig. Stats-derived features of this kind won't create a betting edge on their own. They mostly re-describe information the market already prices.

## 3. Ranked gaps (expected value × cheapness)
1. **Late lineup / PP1 and teammates-out at 30-45 min pre-game.** This has the highest value, because it is information the opening line may not have. The cost is low, since we already pull DailyFaceoff. Test: on the 3 weeks of captures, compare how D-snapshot to CLOSE line and price moves line up with lineup changes. Then grade sides where our re-pulled lineup disagrees with the D-snapshot. The sample is small, maybe a few dozen sides.
2. **Game total / implied team total (score effects).** Value is medium to high and cost is low, since ESPN odds carry game totals. Test: add the implied team total as a feature in this harness. History for it needs the totals archive; check ESPN or nflverse-style free odds for NHL.
3. **Opponent suppression by position (A).** It is proven in-sample and the cost is lowest. Test: a challenger shadow model, paper only, logged next to the frozen model for 4+ weeks.
4. **MoneyPuck free season files** (moneypuck.com/data.htm, skaters/teams CSVs and shots_YYYY.zip; credit MoneyPuck). These add on-ice xG, Corsi/Fenwick and linemate quality. Medium value, medium cost (join on playerId). Test: the same ablation using the prior-season and as-of rolling team xGA. Only season aggregates are leak-safe; per-game files would need date cuts.
5. **Goalie / ref / arena scorer bias.** Arena SOG counting bias can be built from home vs road shots in our pkls for free. Ref data isn't readily free. Low to medium value.
Also skipped: travel/time zone (needs arena coordinates; low expected value) and opponent b2b (no signal).

Sample limits: the 3 weeks of captures are about 22 slates. That is enough to detect only large effects (>5-10% ROI) and gives no reliable CLV read yet. Feature work should be judged on calibration first and then on forward CLV.

Files: ablate.py, ablation_2025_26.csv.
