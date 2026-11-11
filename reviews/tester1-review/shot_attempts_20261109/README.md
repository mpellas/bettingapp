# Shot-attempts signal ('att') — Tester1 review, PAPER ONLY

Written 2026-11-09 (PT) BEFORE any backtest result was looked at. The definition and bands below are fixed;
any later change must be logged here with a date and a reason.

## What this is
An 8th evidence signal shown BESIDE the existing 7 (champ, chal, shrunk, toi, opp, lineup, move).
It never changes `agrees_n` (the "of 7" count the user reads). It adds two display columns:
`att` (+ / - / 0) and `agrees_n_plus_att` ("of 8"). Nothing in /workspace/nhl-sog reads these files.

## Data
Per-game skater logs already cached in /workspace/nhl-sog/data/s20*.pkl (read only). Column
`totalShotAttempts` = shots on goal (incl. goals) + missed + blocked attempts by the shooter (individual
Corsi, NHL realtime report; 2021-22 filled from play-by-play per nhl-sog NOTES.md). No new fetch needed.
Only games with gameDate strictly before the slate date are used (no leakage).

## Definition (fixed before results)
For a player before the game:
- RECENT = his last 10 games played (any season). BASE = up to 82 games played immediately before RECENT.
- Rates are pooled sums (TOI-weighted): att60 = attempts / TOI-hours; acc = SOG / attempts.
- a = att60_RECENT / att60_BASE - 1      (attempt volume trend)
- b = acc_BASE / acc_RECENT - 1          (accuracy regression: > 0 when recent SOG-per-attempt is below his own
                                          long-run rate, i.e. SOG should come back up at the same volume)
- Votes: va = +1 if a >= +0.10, -1 if a <= -0.10, else 0. vb same with b and the same 0.10 band.
- OVER side: att = sign(va + vb)  (one supporting + one neutral -> that sign; conflicting -> 0).
  UNDER side: the opposite sign.
- Minimums (otherwise att = 0): 10 RECENT games, >= 30 BASE games, >= 15 attempts in RECENT, TOI > 0 in both.
- Also reported (numbers behind it): att60_r10, att60_base, acc_r10, acc_base, sog60_r10, sog60_base, a, b,
  proj_sog60 = att60_r10 * acc_base.

## Majority columns
- `agrees_n` (of 7): copied unchanged from the sheet.
- `agrees_n_plus_att` (of 8) = agrees_n + (att == '+'). Majority of 8 = 5 or more. The 4-of-7 list stays the list.

## Backtest plan (fixed before results)
1. Live DK lines: every graded line in /workspace/nhl-sog/graded/2026*.csv with a final shot count,
   excluding VOID_dnp and VOID_pulled_before_close (pinned-grader convention). Both sides graded at the D-capture
   DK price, flat 1 unit risked. Report hit rate (Wilson 95% CI) and units/ROI (game-clustered bootstrap 95% CI)
   for att '+', '-', '0'; also over and under separately.
2. Majority comparison where the sheet `agrees_n` can be matched (sheets/*.xlsx, plus
   shadow/backtest_evidence_rows.csv for Oct 11-16): 4+ of 7 vs 5+ of 8, and 4+ of 7 split by att.
3. Past-season proxy (2025-26 logs, NO prices, clearly labeled): line = floor(recent_mu) + 0.5 with
   recent_mu = sog60_r10 * toi_r5 / 60 (the same 'recent form' number the feeds use). Over-hit rate and mean
   (actual - recent_mu) by att vote on the over side. Shows whether the signal carries information, not profit.
Small samples will be called small.

## Files
- att_signal.py   — signal + sample output for one pass (sheet or GATE csv)
- backtest.py     — backtests above
- out/            — CSV outputs; REPORT.md — results in plain words

---------------------------------------------------------------------------------------------------------
# Scope update 2026-11-09 ~8:06 AM PT: two more signals (written BEFORE any backtest result for them)
Owner: Tester1. Paper only. Drop-in module `tester1_extra.py` matches /workspace/nhl-sog/evidence_extra.py
(`f(r, side, ctx) -> (sign, why)`; `EXTRA_T1 = {'att':…, 'rest':…, 'total':…}`), so Yinzer can install with
`EXTRA.update(tester1_extra.EXTRA_T1)` -> columns sig_x_att, sig_x_rest, sig_x_total, and 'X of 12'.
Note for the att backtest above: before writing this section I had seen only the Nov 5 SAMPLE att output
(no backtest numbers); the att definition was not changed.

## rest (fixed before results)
- Team schedule from the cached game logs (gameDate < slate date). Arena of a game = home team's city.
- b2b = the player's team played the previous calendar day (PT game dates as stored).
- travel = previous team game was within the last 3 days AND (great-circle distance between the previous arena and
  tonight's arena > 1500 miles OR the time-zone difference is >= 2 hours). A 1-hour zone change alone does NOT count
  (it is too common to mean anything; chosen now, before results).
- OVER side: '-' if b2b or travel, else 0.  UNDER side: '+' if b2b or travel, else 0. Never '+' for an over.
- Team = the player's team in his most recent logged game. Tonight's arena = home team in the D row's game name.

## total (fixed before results)
- The game's posted DraftKings total from ESPN's public odds feed (sports.core.api.espn.com .../competitions/<event>/odds,
  provider DraftKings), using the OPEN total (posted before our decision snapshot, so no look-ahead). If open is
  missing, current/close is used and flagged `total_src=close` (possible small look-ahead). nhl-sog captures hold no
  game totals (only SOG + saves props), checked.
- OVER: '+' if total >= 6.5, '-' if total <= 5.5, else 0 (6.0). UNDER: the opposite. No total -> 0.
- Expect nearly every game to vote (NHL totals are mostly 5.5 or 6.5); that is a known property, not tuned.
- Fetched totals are cached in cache/espn_totals.csv (our folder), ~1 request/0.5 s.

## Backtests for rest and total: same as att (live DK lines Oct 11-Nov 5 at D price, hit rate Wilson CI,
units with game-clustered bootstrap CI; majority of 7 vs adding each signal; 2025-26 proxy with synthetic lines,
no prices). For total's proxy, 2025-26 DK open totals from the same ESPN feed (if the feed has them).

---------------------------------------------------------------------------------------------------------
# Scope change 2026-11-09 8:15 AM PT: rest signal DROPPED (Tester2 owns it)
- Removed from tester1_extra.py and from all backtests/sample. Final module: EXTRA_T1 = {'att', 'total'}.
- Counts reported: 'X of 7' (sheet), 'X of 9' (Yinzer's evidence_extra: hit, books), 'X of 11' (+ att, total).
  Majority = 4+ of 7, 5+ of 9, 6+ of 11.
- (A first live backtest run that still included rest was done before this change; its rest rows are not reported.)
- 2025-26 proxy data note (before any proxy result): ESPN's feed has no DraftKings odds for early 2025-26 games;
  the proxy uses DraftKings when present, else ESPN BET (provider 58), labeled per game in cache/espn_totals.csv.
  Live (2026-27) lines use DraftKings only.

---------------------------------------------------------------------------------------------------------
# Scope change 2026-11-09 ~8:17 AM PT: live EXTRA is now 'X of 10'
- Tester2's rest is now in /workspace/nhl-sog/evidence_extra.py EXTRA (hit, books, rest). Yinzer rewrote books
  (raw two-sided Fliff pulls at or before the pass; no-vig comparison). Vendored copy:
  vendor/evidence_extra.py (cp -a, identical to live file). Older copy: vendor/evidence_extra_v1_superseded.py.
- Counts: 'X of 7' (sheet, never changed), 'X of 10' (current EXTRA), 'X of 12' (+ Tester1 att, total).
  Majority = 4+ of 7, 6+ of 10, 7+ of 12.
- Drop-in is still EXTRA.update(tester1_extra.EXTRA_T1) -> sig_x_att, sig_x_total.
- UNAVAILABLE DATA (fixed in README before any re-run of the n/a-split tables): the EXTRA interface only
  allows sign +1 / -1 / 0, so a test that cannot score still returns sign 0, BUT the why text always starts
  with 'n/a (...)' (never a silent 0). tester1_extra.status / display show 'n/a' on the sheet. Insufficient
  history (under 10 recent / 30 base / 15 attempts) is also marked n/a, not a true 0. A true 0 is a scored
  neutral (enough data, both pieces inside the 10% band, or they cancel).
- annotate() now takes asof_hhmm (books leak guard). Our annotate calls pass it through automatically
  because we call evidence_extra.annotate unchanged.
