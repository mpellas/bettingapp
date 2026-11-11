# prop-finder — NFL + college (FBS) player-prop bet finder (v1)

Pulls player game logs, sportsbook player-prop lines, and matchup context, then ranks props by
model edge and writes CSVs plus a Markdown/HTML report.

```bash
cd /workspace/prop-finder
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt   # first time only
python run.py --league nfl      # or: ncaaf | all   (default: all)
#   --top 25                     rows in the "top props" table
#   --odds-max-events 8          cap on The Odds API events per league (credits!)
#   --no-espn-props              skip ESPN/DraftKings lines
```

Output: `output/<YYYY-MM-DD_HHMM PT>/` (and the `output/latest` symlink)

| file | contents |
|---|---|
| `<lg>_<season>_wk<N>_ranked_props.csv` | every prop line matched to a projection, ranked by `rank_score` |
| `<lg>_..._projections.csv` | projection + trends for every relevant player/stat on the slate (no line needed) |
| `<lg>_..._prop_lines_raw.csv` | the raw prop lines pulled |
| `<lg>_..._defense_vs_position.csv` | allowed-per-game by defense × position group × stat, with rank |
| `report.md` / `report.html` | readable report: data status, top props, projections, matchups, method |

## Data sources

| Source | Used for | Key? |
|---|---|---|
| nflverse release files (GitHub `nflverse/nflverse-data`) | NFL weekly player stats (current + previous season), schedule, injury reports, ESPN↔GSIS id map | no |
| ESPN site API (`site.api.espn.com`) | NFL + FBS scoreboards/slates, spreads/totals (DraftKings), college box scores, rosters, game-day weather (AccuWeather), NFL game-day injuries | no |
| ESPN core API `.../odds/100/propBets` | **DraftKings player O/U lines** (no prices). Snapshotted to `data/snapshots/` so a started game is graded against its last *pregame* line | no |
| The Odds API (`ODDS_API_KEY`) | multi-book player props with prices (`/events/{id}/odds`) | yes, free tier 500 credits/mo, signup https://the-odds-api.com/#get-access |
| CollegeFootballData (`CFBD_API_KEY`) | college v2 model: 2025 player game logs (`/games/players`, 17 weekly calls), SP+ 2025/2026 (`/ratings/sp`), 2026 transfer portal (`/player/portal`), returning production (`/player/returning`), team/conference map (`/teams`) | yes, free tier 1,000 calls/mo, signup https://collegefootballdata.com/key |

Keys are only read from env vars; with no key the module is skipped and the report says so.
Odds API cost: event-odds = (#markets returned) × (#regions) per event; the `/events` list is free.
One NFL slate at 11 markets × 1 region ≈ up to 11 credits/game, so the free tier covers ~2–3 full slates/month —
use `--odds-max-events` to cap.

## College model v2 (when `CFBD_API_KEY` is set)
- **CFBD usage:** about 23 calls for a cold cache; everything is cached under `data/cfbd/` (2025 data forever, SP+/portal
  for 1 day, teams/returning for 7 days), so repeat runs make **0** calls. Every network call is logged to
  `data/cfbd/calls.log`. CFBD team/athlete ids are ESPN ids, so players link across schools by id; when they don't,
  portal records are matched by name and destination school.
- **Opponent strength:** each game × (1 + 0.012 × SP+ points the opponent defense is better than FBS average), capped
  0.8–1.25. Non-FBS opponents count as 15 points below average and get half weight. Defense-vs-position is adjusted
  the same way for the offense faced, and only FBS defenses are ranked.
- **Prior season, followed across schools:** opponent-adjusted 2025 per-game numbers × level jump
  (1 − 0.006 × change in conference average SP+, capped 0.85–1.08; non-FBS origin = −25) × opportunity change
  (2026 share ÷ 2025 share of team attempts/carries/receptions, capped 0.1–10; when the change is over 3×, the prior's
  reliability is cut by 3/ratio). Prior weight = (0.70 − 0.13 × 2026 games, min 0.05) × reliability.
- **Vacated roles:** the share of each team's 2025 volume that no longer shows up for that team in 2026, CFBD's
  returning-usage figures, and a per-player flag when a player's share rose ≥10 points into a ≥40% vacancy.
- `--no-cfbd` runs the v1 college model for comparison. Extra outputs: `ncaaf_..._transfers.csv`,
  `ncaaf_..._vacated_roles_by_team.csv`.

## Model (deliberately simple and transparent; settings tuned by the 2025 backtest, see below)
- base = 50% season avg + 20% last-3 + up to 30% previous season (NFL), shrunk slightly toward the position
  mean (strongly for TD/INT rates). QB games with <10 attempts are dropped (early exits).
- × matchup (opponent allowed-to-position vs league, shrunk by sample, ±20% cap; strength 0.3 NFL / 0.6 college)
- × game environment (implied team total vs team scoring average, ±12% cap; strength 0.5 NFL / 1.0 college)
- College current-season blend = 70% season / 30% last-3 (opponent-adjusted); prior weight 0.70 − 0.08·games (floor 0.05).
- × weather (outdoor gusts/precip, passing & receiving only)
- P(over) via normal (player SD blended with a CV floor) or Poisson (TDs/INTs). The displayed `p_over` / `model_p_side`
  is calibrated: raw edge × 0.2 (`P_SHRINK`). On 2025 real lines the raw model was strongly overconfident.
- Rank score (ordering heuristic) = 100×(raw P(side) − breakeven)×sample-confidence + 20×(L10 hit-rate on side − 50%),
  then discounted (×0.35/×0.6; negative scores are pushed further down) for: player missing his team's last game,
  a teammate at the position being Out (unders), and lines far from the player's history. Small samples are flagged only.
- Breakeven = −110 (52.4%) for ESPN/DraftKings lines (no prices); real implied probability for Odds API prices.

## 2025 backtest (`python backtest.py && python backtest_report.py`)
Walk-forward over the 2025 NFL (weeks 2-18) and FBS (weeks 2-16) regular seasons through the live code paths. For week W it uses
only data before W; FBS uses 2024 priors carried through the 2025 transfer portal and 2024 final SP+ as the as-of rating.
- Stage 1 (`backtest.py`, about 40 min with 3 workers) projects every week for the pre-backtest settings plus a one-knob-at-a-time grid, then
  writes `data/backtest/` (per-config parquet, `projections.pkl`, `actuals.pkl`). Stage 2 (`backtest_report.py`, about 3 min with
  checkpoints) grades, tunes (weeks 2-9) and validates (weeks 10+). Tuned reruns are checkpointed as `data/backtest/tuned_*.pkl`.
- Real historical lines: ESPN core API propBets, ESPN BET (provider 58), **opening** main line, NFL weeks 1-13 only
  (`prop_finder/hist_lines.py`, cache `data/hist_props/`). No priced main lines exist there for FBS, so FBS uses a SYNTHETIC proxy only.
- Output: `output/backtest_2025/report.md|html` + CSVs. Comparisons are always against `backtest.PRE_BACKTEST`.

## Known limitations
- College: ESPN box scores omit players with zero stats in a category, so "games" means games with a recorded
  stat line; no official injury feed (roster "out" group + "missed last game" flag only). Without a CFBD key there is
  no previous-season data and no opponent adjustment.
- CFBD free tier exposes SP+ overall/offense/defense only (no pass/rush splits, no adjusted metrics), so opponent
  adjustment uses one defensive rating for every stat. True freshmen and players with no 2025 FBS/FCS box-score
  stats have no prior. Opponent-adjustment and level-jump coefficients are hand-set. The 2025 backtest found BETA 0.012 better than 0 or 0.018, and no measurable level-jump effect.
- ESPN/DraftKings college props usually appear only close to kickoff (none were posted for week 6 on Sun 10/4).
- No targets/snap share/air-yards modeling, no backup-promotion projection (only a flag) in v1.
- Weather is ESPN's AccuWeather feed (temperature, gusts, precip %), not sustained wind.
- 2025 backtest: no reliable edge over opening ESPN BET lines. Treat picks as research, not betting advice.
