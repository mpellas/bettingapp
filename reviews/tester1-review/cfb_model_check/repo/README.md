# CFB power-rating model — PAPER ONLY (no bets placed, ever)
Built Oct 31, 2026. Does not touch NFL prereg/track.py or NHL models.

## Data
- CollegeFootballData.com API (free key, `$CFBD_API_KEY`): `/games` 2024–2026 (all levels; FBS+FCS+D2/D3 with classification) and `/lines` 2024–2026 (sportsbook lines per game: DraftKings preferred, then ESPN Bet, Bovada, consensus). Saved in `data/`.
- Live prices: The Odds API (`slate.py --live`, 2 credits/call; DK + Fliff spreads/totals). Today used 2 credits (92 remaining).
- CFBD `/lines` mostly gives the last posted number (treated as the closing line); not all games have DK, and FCS lines exist only for FBS-vs-FCS games mostly.

## Method (`model.py`)
- Spread: weighted ridge regression, margin = r_home − r_away + HFA (0 on neutral). Margin capped at ±40. Games weighted by half-life 90 days; previous season carried in (decayed) as prior. HFA 2.0, ridge 1.0.
- Total: points = mu + off_team − def_opp (ridge 6.0, points capped at 70); fair total = sum both sides.
- Level tags: P4 (SEC/B10/B12/ACC + Notre Dame), G5 (other FBS), FCS/mixed shown as e.g. `FCS/G5`.
- Parameters tuned on 2024 only (`tune.py`, MAE vs close); 2025 and 2026 are out-of-sample walk-forward (refit before each week using only prior games). Caveat: total ridge 6 picked after seeing 2024 results too.

## Backtest (`backtest.py` -> `backtest_results.txt`, `backtest_<year>.csv`)
Thresholds: 3 pts P4, 5 pts G5/FCS/mixed, scored at the closing number, pushes excluded. Break-even at -110 = 52.4%.
Both teams with ≥4 games that season:
| season | n | MAE spread vs close | MAE total vs close | ATS spread at thr | totals at thr |
|---|---|---|---|---|---|
| 2024 (in-sample) | 1068 | 4.25 | 2.78 | 203-188 (51.9%) | 112-93 (54.6%) |
| 2025 (OOS) | 1067 | 3.45 | 2.42 | 150-153 (49.5%) | 83-79 (51.2%) |
| 2026 to date (OOS) | 459 | 4.12 | 2.89 | 77-73 (51.3%) | 56-54 (50.9%) |
Model MAE vs actual results is always worse than the closing line (e.g. 2025: 12.63 vs 11.94).
**Verdict: no demonstrated edge.** Market beats the model; flagged sides are close to coin flips. Early-season (teams <4 games) is much worse (MAE 6–9 pts). Totals carry a +0.9 to +1.6 pt over bias vs close -> slate flags skew to OVERs.

## Daily slate (`slate.py`)
`python3 slate.py --live --refresh` (2 Odds API credits, refreshes CFBD results) or `--reuse <oddsapi json>` (0 credits). `--hours N` window (default 30). Writes `picks/slate_YYYYMMDD_HHMM.csv` with every DK/Fliff side, model fair, edge_pts, and `clears` (edge ≥ threshold and both teams ≥4 games). Edge is vs posted number; juice not priced.
