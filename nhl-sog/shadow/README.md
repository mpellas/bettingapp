# shadow/ — challenger tracks (do not feed the frozen model c3ab760178 or any routine status)
- gamelog.py: fresh 2026-27 game logs -> shadow/s2026_live.pkl. Found 2026-10-16: fetch.py's 2026 window ends
  2026-10-11, so data/s2026.pkl (and the model features/recent-form inputs in every D file since Oct 12) stop at
  Oct 10 games. Fixing fetch.py changes the frozen model's inputs -> needs yinzerduck's approval; not changed.
- ../shrink.py: gamma-Poisson shrunk recent form (extra columns only).
- backtest_shrink.py: raw r10 vs shrunk vs model vs market on graded days.
