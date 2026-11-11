# NFL evidence block (sidecar, shadow/context only; added 2026-10-17)
Outside `src/nflprops` and the pinned prereg code. Reads nfl-props caches/snapshots read-only, keeps its own nflverse
copies in `cache/` (gitignored; the 2026 files re-download when older than 6 h). Writes only `*_evidence.csv/.txt`
next to the input analysis CSV, or `data/evidence/` for `--dlines`. No Odds API calls. Changes no verdict, list,
gate or paper-track number.

Signals and bands: docstring of `nfl_evidence.py` (fixed before any backtest). 7 signals, `agrees_n` of 7.

Sunday use (after the price-shop run, 0 credits):
    cd /workspace/nfl-props && .venv/bin/python sidecars/evidence/add_evidence.py --analysis latest --week 6
`latest` = newest `props-finder/analysis/analysis_2026_wk6_live_*.csv` by name stamp; with no live CSV it falls back
to `--dlines` (DK D lines + pregame predictions). Runtime ~30 s (ESPN summaries + Open-Meteo wind per outdoor game).

## Backtest results (see *.out; rows in *_rows.csv)
* `backtest_2026.py` real DK lines, 2026 wk4-5 settled in-scope (141 sides, 14 games, no prices, -110 assumed):
  agrees >= 4 of 7: 10 sides, hit 50% [-27, +36 pts], z-CLV -0.017 [-0.067, +0.007]; agrees < 4: 131 sides, hit
  55.7%. No sign the gate helps; sample far too small to say anything.
* `backtest_proxy.py` 2024-2025 PROXY (synthetic line = public-projection proxy, NOT a market; reference = champion
  walk-forward P). >= 3 of 5 market-free signals agree: 335 sides, hit - P_champ +6.8 pts [+1.7, +11.5] vs -0.0 for
  the rest. Says agreement flags where the champion is miscalibrated; it does NOT say the market misprices it -
  script, injuries and weather are exactly what real lines already price. Weather uses recorded game weather
  (hindsight) and the script uses nflverse closing spreads/totals.
Not adopted as a gate.
