# Extra NHL paper models (points, puckline, saves)

Data-only, paper only, off the real SOG card until ~100 graded in-band sides.

- Train: 2021-2025. 2026 is out of sample.
- Free data only: NHL stats API (same as `fetch.py` / `challenger/fetch_team.py`), existing `data/s20xx.pkl` (PP TOI / attempts), DK extra-market captures from Nov 15 2026 on, and DK game-line captures from Nov 22 2026 on.
- Units/ROI are reported only at real captured DraftKings prices. Nothing is invented or backfilled.
- Price band is enforced only at the −150 end (−155 or worse is outside).
- Nightly shadow grading is hooked at the end of `extra_markets/grade_extra_nhl.py` and writes `models_extra/shadow/`. No new routines.

## Layout

- `fetch_extra_stats.py` — writes `data/skater_points.pkl`, `data/goalie_saves.pkl`, `data/team_games.pkl` (does not touch SOG season pkls).
- `train_and_backtest.py` — leakage tests, walk-forward, 2026 OOS, priced backtest where prices exist.
- `grade_shadow.py` — idempotent shadow log.
- `backtest_results.json` — last training run.

Puckline prices did not exist before the Nov 22 2026 game-line capture. Until those grade, puckline is outcome-only.
