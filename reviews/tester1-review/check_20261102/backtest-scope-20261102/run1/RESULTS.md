# Run1 results (2026-11-02, paper only)
## NHL: ESPN free history check
Sampled 57 games, about 3 every 10 days from Oct 2025 to Jun 2026. DK propBets (with SOG) came back for only 9 of them, all playoff dates (Apr 18 to May 18). A separate spot check of one Jan 15, 2026 game did return 30 SOG items. The October pulls (74 games) returned 0. Regular-season coverage is mostly missing, so there are not enough NHL games for a backtest, and NHL was not included. The partial raw pull is in nhl_raw/ (empty Oct files), and pull_nhl.py was stopped.
## NFL 2025 (tuning set; rules locked in rules_locked.md before results)
Full table: nfl2025_results.csv. The yards universe is 2,760 priced sides across 177 games, and every stat combined is 5,163.
No rule was profitable. All 36 Bonferroni lower bounds are negative, and only R07, R08, R09, R11 and R18 have 95% CIs that include 0.
The model's edge adds nothing: edge>=2% is -5.7% ROI, and always-under is -4.1%.
Caveats: one book (ESPN BET), opening prices only, so no CLV. This is the prop-finder 2025 model (pre-backtest settings), not the frozen props-finder v2. The file had already been inspected in October's report.
