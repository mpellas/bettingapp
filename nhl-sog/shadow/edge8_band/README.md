# Edge-8 price-band shadow (paper only)
Started 2026-10-31 at the user's request. **Forward-only from Oct 31.** The pre-Oct 31 record (24-8, +11.82u at DK, from
/workspace/weekly-review-20261031/review.md) was found after the fact and is **in-sample**; it is not part of this tally.

Rule (weekly review sec. 5 item 1): on each window pass, a Fliff-check candidate side (status_reason starts "model +") with
model minus no-vig >= 8.0 pts and captured DK price between -150 and +110 inclusive gets a 1u shadow bet at that DK price.
Uses the latest pass captured >= 150 min before the NHL.com start per player-game. A secondary "board" column logs any side
(any status) passing the same edge/price test. Adopt only if ROI > 0 and mean CLV > 0 at n >= 100 graded (CLV not yet computed).

Files: `edge8_band.py YYYYMMDD` (log + grade + summary), `nhlbox.py` (NHL.com box-score grader, shared with the other
two nightly trackers), `tally.csv` (running sides), `summary.csv`, `box_cache/`. `run_nightly.sh YYYYMMDD` runs all three trackers.
Never places bets, never edits live rules/models, never runs --rescore, no Odds API credits.
