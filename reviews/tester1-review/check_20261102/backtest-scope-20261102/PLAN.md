# Walk-forward backtest scope (2026-11-02, paper only)

## 1. Prop-line data already on the box
- NFL 2025 (`prop-finder/output/backtest_2025/nfl_real_lines_graded.csv`): 7,147 sides, weeks 2-13. One book, ESPN BET, from ESPN core API propBets (historical opening main line). Prices exist on 6,524 sides. By market: rec_yds 1,658, rush_yds 853, pass_yds 329, rush_rec 421, plus others. It has opening lines only, no close, and none of DK, Fliff or PrizePicks.
- NFL 2026: `props-finder/raw/` has about 14 snapshot folders (Oct 11 to Nov 2) from the Odds API, multi-book. `nfl-props/data/{lines,snapshots,evidence}`. `shadow_modelled_ledger.csv` has 115 graded sides from Nov 1. Price-shop xlsx files for weeks 6-8.
- NHL 2026: `nhl-sog/captures/` covers 22 dates (Oct 11 to Nov 2), about 454 files. Each game has D, C and CLOSE snapshots taken from 0 to 30 minutes before start, with open and close prices and no-vig. The book is ESPN-sourced. A `legacy/` folder holds early captures with no archive.
- NHL last season: no prop lines on the box. Stats for 2021-2026 are in `nhl-sog/data/s*.pkl`.

## 2. Sources for historical prop odds
- **The Odds API historical** (`/v4/historical/sports/{sport}/events/{id}/odds`). Player props are available from about May 2023. It covers DK, FanDuel and others, but not Fliff. PrizePicks shows up as a DFS "book" (us_dfs region) only for recent data.
  - Cost: 10 credits × markets × regions per event snapshot.
  - Historical data needs a paid plan. The free key has 461 of 500 credits left this month and cannot use it.
  - Paid tiers (verify on the site before buying): about $30/mo for 20K credits, $59 for 100K, $119 for 5M.
  - Estimate: NFL 2025 is about 285 games × 3 markets × 1 region × 10 = 8.6K credits per snapshot time. An open-plus-close pair is about 17K. NHL 2025-26 is about 1,312 games × 1 market × 10 = 13K per snapshot, or 26K for the pair. **Total is about 45K credits, so the $59 100K tier for one month covers everything, with retries.**
- **ESPN core API propBets**: free, and already used for the 2025 NFL data. It is the ESPN BET/theScore line only and may hold just one snapshot. Check whether the NHL 2025-26 SOG history is still served. Free, and a cheap first check.
- **Others**: OddsJam, SportsDataIO and BettingPros archives cost $100+/mo and are mostly behind a login. Free scraped GitHub datasets are patchy. None cover Fliff or PrizePicks history. **Fliff and PrizePicks cannot be backtested historically.** Use DK as the proxy and keep Fliff/PP to forward tracking only.

## 3. Outcome data
- NFL: nflverse weekly player stats for 2025 and 2026, plus the existing graded actuals.
- NHL: NHL.com box scores (`catchup_box`, and the grader already in use). The s2021-s2026 pkls hold game logs.

## 4. Plan
1. **Pulls.** Run the ESPN NHL feasibility check first (free). After the user approves $59, pull from the Odds API historical endpoint for NFL 2025 wk1-18 + 2026 wk1-8 (pass/rush/rec yds) and for the NHL 2025-26 season + 2026 to date (player_shots_on_goal). Use DK plus every us book, at two snapshots: T-3h (decision) and T-10min (close). Cache the raw JSON and never re-pull.
2. **Predictions.** Use the frozen models in a read-only backtest harness. Each game uses only features as of the day before; stats are rebuilt walk-forward from the pkls/nflverse with an as-of date cutoff. Never run `--rescore`, never edit the prereg or track.py, and write to a new folder only.
3. **Rules to test.** These are pre-registered in a new file, frozen before results are seen.
   - Edge thresholds 0/2/4/6%.
   - Fair price: DK no-vig, the median across all books, and the median excluding the bet book.
   - Price band +110 to -150, compared with all prices.
   - Overs vs unders.
   - Per market (pass/rush/rec yds, SOG).
   - Model probability buckets.
   - The model-only shadow rule.
   - The NHL edge-8, shrink-50 and promo-under variants.
   - Keep this to about 40 variants and apply a Bonferroni/holdout correction.
4. **Grading.** Settle at the decision-time DK price. Report CLV against the close as the main signal of edge. Pushes are void.
5. **Correlation.** Report per side and per game, with each game's net units as one observation. Use a cluster bootstrap by game and week for CIs. Also cap stakes at one side per player per game, and test a cap per team.
6. **Leakage safeguards.**
   - Use as-of feature timestamps, with no box score from the same day.
   - Use the decision snapshot, not the close, for selection.
   - Use only injury/inactive info known by T-3h; flag the cases where it is unknown.
   - Train/tune on 2025 and hold out 2026 untouched.
   - An automated test asserts that feature dates are earlier than game dates.
7. **Success bar.** Holdout ROI above 0 with the game-clustered CI lower bound near or above 0, a hit rate above break-even in the band, and positive CLV, on 1,000+ sides and 300+ games.

## Runtime and cost
- Pulls: about 45K credits, taking roughly 1-2 hours of throttled API calls. Box compute: under 30 minutes.
- Agent usage: a moderate 2-3 sessions. That is affordable now on Premium (~11% weekly).

## Decisions needed from the user
1. Approve buying the Odds API $59/mo 100K-credit plan (one month, then cancel), or stay ESPN-only and free (one book, NFL opens only, NHL unknown).
2. Accept that Fliff and PrizePicks can only be forward-tested, with DK as the historical proxy.
3. Agree that 2026 is the untouched holdout.
