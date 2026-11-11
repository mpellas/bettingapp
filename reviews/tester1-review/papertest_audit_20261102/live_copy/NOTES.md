# nhl-sog NOTES

## 2026-10-17: stale input data fixed (approved by yinzerduck, "Go")
- Bug: fetch.py hard-coded the 2026-27 window as 2026-10-01..2026-10-11, so data/s2026.pkl held games through
  2026-10-10 only. Every D file built Oct 12-16 (picks/20261012_D.csv .. 20261016_D.csv) used STALE inputs:
  the frozen model's features (sog60_r10, toi_r5, toi_r30, pptoi, opp_sa_r20, ...) and the recent-form filter
  missed every game after Oct 10. Paper-track rows for Oct 12-16 are kept as logged (not re-predicted) and are
  flagged here as stale-input days. Oct 11's D used data through Oct 10, which was current then.
- Fix: fetch.py now pulls the current season through yesterday (PT). Refreshed 2026-10-17 04:17 PT:
  4031 rows, 2026-10-01..2026-10-16 (was 2700 rows through 2026-10-10; backup logs/s2026_stale_backup_20261017.pkl).
- Check (model's own features.py, as of the Oct 16 games): Brent Burns sog60_r10 5.922 (stale) -> 5.028 (fresh),
  toi_r5 16.71 -> 17.51; Nazem Kadri sog60_r10 9.468 -> 8.753, toi_r5 16.15 -> 20.64.
- Model c3ab760178 (code, weights, k) unchanged: only the input data is fresher from D files on 2026-10-17 onward.
- Guard: ops/ensure_capture.sh runs fetch.py whenever data/s2026.pkl ends before yesterday.
- build_sheet.py: fresh_data_check / status_if_fresh_inputs columns show any side whose status changes when
  recent form uses fresh game logs (on the Oct 16 sheet: Toews O1.5 and Malinski U1.5 would have been Fliff checks).

## 2026-10-17: unapproved goalie-saves edits removed from capture.py
- `git checkout capture.py` (back to 79b6024). The diff is kept, uncommitted, at
  logs/capture_goalie_saves_unapproved_20261017.patch. close.py still tolerates saves_lines (s.get), so old captures grade.

## 2026-10-17 Evidence block (display only)
evidence.py adds 7 per-side signals (champion, challenger 3386583f18, shrunk form, TOI trend, opponent slot SA,
DFO lineup/PP, no-vig move since open), agrees_n / disagrees_n and evidence_summary to build_sheet.py, plus
`--post <file>` pick-post text. Status gating unchanged (verified: Oct 16 1512pass sheet statuses/reasons identical).
Lineup lookup searches captures/*/<event>_D.json because capture dirs are by UTC start date (late PT games land
in the next day's dir). Backtests: shadow/backtest_evidence.py (DK lines Oct 11-16) and
shadow/backtest_evidence_proxy.py (2025-26, synthetic lines, champion as reference); outputs in shadow/*.out.
Result: K=4 gate not distinguishable from the ungated list on Oct 11-16; proxy shows agreement tracks champion
miscalibration. Not adopted as a gate.

## 2026-10-17 NHL data gap audit + backfill (yinzerduck: "there should be no gaps in historic NHL data"; free sources only)
- Audit vs NHL schedule (api.nhle.com/stats/rest/en/game), all 6,680 completed regular-season games 2021-22..2026-27 to Oct 16.
- GAP 1: the 2026-27 season opened Sep 29; fetch.py started its window Oct 1, so 8 games (Sep 29: 5, Sep 30: 3; 288 skater rows)
  were missing from data/s2026.pkl and shadow/s2026_live.pkl. Fixed (window starts Sep 1); s2026 now 4,319 rows / 120 games.
  Pre-backfill copy: logs/s2026_pre_backfill_20261017.pkl (sha1 c287a89 = challenger prereg data sha1). team_games.pkl was complete.
- GAP 2: NHL realtime report has totalShotAttempts = null for all of 2021-22 (47,208 rows). Filled from free play-by-play
  (audit/attempts_pbp.py: goals+SOG+missed+blocked by shooter, shootout excluded; 99.93% exact vs the feed on 1,440 2022-23 rows).
  Backup logs/s2021_pre_attempts_backfill_20261017.pkl (sha1 2cdab91 = prereg). fetch.py re-applies it on any refetch.
  Affects att features of 7 current skaters whose last 30 games reach 2021-22 (1 Oct 12-16 line player: Formenton).
- Verified: all 240,410 stored skater rows match the official api-web boxscore SOG exactly (audit/box_compare.txt). 11 boxscore
  skaters dressed with 0:00 TOI are absent from the stats feed (did not play) - not gaps, not added. 4 TOI diffs (2021, seconds).
  ESPN spot check (audit/espn_spotcheck.csv): 144 rows, 143 match (3 name variants confirmed by hand); 1 differs
  (Kaprizov Oct 15: ESPN 5, NHL official 6 - ours = official).
- Logged graded/ actuals: 4 Oct 13/16 rows predate NHL stat corrections (Benson, Cozens, Skjei, Kindel). Logged files kept as is;
  rebuilt/ uses official actuals. Do NOT re-run grade.py for Oct 12-13: those captures have no archive, today's close.py finds
  fewer closes (events 401892486/492/493) than the original grading.
- Rebuilt Oct 12-16 (point-in-time, gap-free): rebuilt/ (see rebuilt/README.md). Stale marking above stays.
- Gap check: check_gaps.py (completed games in last N days must have >=30 rows, both teams; --box = shots vs official boxscore),
  run by ops/ensure_capture.sh (refetch once, then loud "GAP CHECK FAILED"). predict.py now cuts history at gameDate < slate.
- grade_report.py: model-only paper track (raw model side, edge >= 1 pt vs no-vig, flat 1 u at captured DK price; Fliff when captured)
  for champion and challenger, ROI with game-clustered CI; options --graded/--chal/--out/--title.

## 2026-10-17 Fliff NHL price capture (yinzerduck "Go" 08:27 PT: spend Odds API credits, cap 10/day)
- fliff_prices.py <YYYYMMDD> <sheet.xlsx | sheet csv | post text>: Fliff-check sides -> unique games -> free /events lookup ->
  ONE /events/{id}/odds call per game (markets=player_shots_on_goal, bookmakers=fliff,draftkings; same 1-credit cost, confirmed
  x-requests-last=1). Per-day log fliff_credits_<date>.csv checked before each call (stop if > 10). Captures < 30 min old are reused.
  Raw: captures/fliff_<date>_<HHMM>_<event>.json; table: fliff_prices/<date>_<HHMM>.csv.
- Test: mock json offline; 1 real call (NJD@WSH, 08:29 PT): DK SOG returned, Fliff had not posted that game yet. Oct 11 props-finder
  captures show Fliff does post player_shots_on_goal in this feed. 1 credit (236 left), logged in fliff_credits_20261017.csv.
- grade_report.py: 'Fliff list (as posted)' paper track at the captured Fliff price (dates >= 20261017) and
  'Your own betting results' from props-finder/user_bets/bets.csv (not a model test). Frozen models/preregs untouched.

## Window-only extra passes (2026-10-17)
- `predict.py <date> --window-only [--hhmm HHMM]`: scores only unscored games 150-210 min from puck drop (210-240 if a D snapshot exists, none newer than now), never pre-noon PT; merges into picks/<date>_D.csv (other games' rows byte-identical) and writes picks/<date>_D_<HHMM>.csv. Exit 3 + `NO_WINDOW_GAMES` if nothing qualifies.
- Default passes now keep rows of games already in picks/<date>_D.csv (and challenger shadow file) byte-identical and only append new games (`--rescore` = old full rewrite).
- Sequence (T=HHMM): python3 predict.py <date> --window-only --hhmm $T -> python3 challenger/predict_challenger.py <date> --window-only --picks picks/<date>_D_$T.csv -> shop_gate.py <date> D_$T -> recent_form.py picks/<date>_D_$T.csv -> build_sheet.py picks/<date>_D_$T.csv picks/<date>_D_${T}_GATE.csv sheets/<date>_D_${T}_picks.xlsx --post picks/<date>_${T}_post.txt -> fliff_prices.py <date> picks/<date>_${T}_post.txt
  (Fix 9, 2026-10-26: <date>=YYYYMMDD is a required positional arg for BOTH predict.py and predict_challenger.py; omitting it makes argparse exit 2.)

## 2026-10-17 — role-mismatch check in shop_gate (shop lists only)
- role_check.py + shop_gate.py: new column role_mismatch. Compares predict.py's history `slot` with today's DFO lineup
  (ev_now/pp_now). Forwards f1/f2=top6, f3=3rd, f4=4th; PP1 = pp_now=='pp1' vs '+PP1' in slot (either direction);
  D slots carry no pair, so D compares PP1 only. Missing lineup (no ev_now) = no flag. On mismatch shop_veto gets
  'role changed: history <slot>, today <ev>/<pp>' -> shop_ok False, dk_listable False.
- build_sheet.py: shop-gate Skipped reasons now show the veto text; role-changed sides are Skipped even with positive
  DK EV (not 'DK bet'). Other shop vetoes keep their old DK-bet behavior. Model, picks/*_D.csv, grading untouched.
- Trigger case: Samoskevich 20261017 D_1222, slot F_3rd but today f1/pp1. Back-check on stored GATE files:
  Oct 15 45/176 lines mismatch (22 not already vetoed), Oct 16 6/20 (2 new), Oct 17 D 5/31 (2 new), D_1222 7/13 (2 new).

## 2026-10-17 (later) — role check made directional
- role_check.role_change -> GATE columns role_change (promotion/demotion/mixed/''), role_veto_over, role_veto_under,
  role_reason (role_mismatch kept as bool). promotion (line up and PP1 not lost, or PP1 gained, line same) -> UNDER only;
  demotion (line down and PP1 not gained, or PP1 lost, line same) -> OVER only; mixed -> both, plus shop_veto
  (shop_ok False). Directional changes leave shop_ok alone. D and F/D position mismatch compare PP1 only; no lineup = no flag.
- New dk_listable_over / dk_listable_under (shop_ok & pick on that side & that side not role-vetoed);
  dk_listable = either. build_sheet Skips the vetoed side with 'role changed (<kind>: history X, today ev/pp), <side> skipped',
  checked first, including over DK bet. Pre-existing vetoes (below_recent_top6, off_pp1_now, line_down) still veto both sides.
- Stored GATE counts: Oct 15 promo 19 / demo 22 / mixed 4; Oct 16 promo 2 / demo 4; Oct 17 D promo 1 / demo 3 / mixed 1;
  D_1016 demo 1; D_1222 promo 2 (Samoskevich, Beniers -> UNDER skipped) / demo 5 (all already vetoed).

## 2026-10-17 (1:35 PM) — older lineup vetoes made directional; shop_ok redefined
- shop_ok now means "no BOTH-SIDES veto": injury/IR/DTD/questionable/GTD (DFO or ESPN), not_in_lineup, gate_unverified,
  or a mixed role change. It no longer goes False for one-sided lineup moves.
- line_down, below_recent_top6 and off_pp1_now are demotion signals -> OVER-only veto. Codes kept in new column
  lineup_veto_over; role_veto_over True; role_change 'demotion'. Older demotion + role_check promotion -> 'mixed'
  (both sides, shop_veto gets 'mixed: ...', shop_ok False). role_reason combines e.g.
  'lineup: off PP1, today pp2; role changed (demotion: ...)'; build_sheet shows '<role_reason>, over skipped'.
- List rule: a side is listable only if dk_listable_over / dk_listable_under (= shop_ok & lean on that side & not
  role_veto_<side>). evidence.py's lineup signal reads shop_veto, so it no longer sees one-sided lineup codes (display only).
- Back-check (stored GATE re-gated): Oct 15 demotion 23 / promotion 19 / mixed 4, 20 lines' UNDER newly eligible;
  only Easton Cowan UNDER 1.5 would join a list (Fliff check). Oct 16 demotion 4 / promotion 2, 4 unders freed
  (Novak, Necas, Hughes, Kindel), none listed. Oct 17 live: no list changes.

## 2026-10-17 evening: empty-pull guard + early-close tag (data integrity only; no model/grade.py/close.py change)
- BOS@LA 401892530 (6:00 PM PT): DK pulled every SOG line ~13 min before puck drop; the 5:47-5:59 PM C pulls had 0 lines
  and overwrote captures/20261018/401892530_C.json. Main file restored from archive/401892530_C_004318.json (5:43 PM PT,
  15 lines, 16.7 min out); the empty copy moved to captures/20261018/manual_backup/ (out of archive/, so close.py does not
  read it twice). The graded close (close.py, per line from archive) was never affected: CLOSE.json = 15 lines from 5:43.
- capture.py: a 0-line pull is still archived but never overwrites a main <eid>_C/_D.json that has lines (keep_main).
  Fewer-but-nonzero lines still replace it (single lines get pulled for real; main = latest snapshot).
- close_timing.py (new, read-only): per game, last close-window snapshot with lines; early_close if > 5 min out and
  later snapshots were empty (book pulled lines), capture_gap if > 5 min out and our capture simply stopped,
  legacy_unknown for pre-archive days. grade_report.py moves early_close rows' nv_over_C to nv_over_C_early, so every
  CLV figure excludes them, and lists them under '## Early closes'; win/loss/units unchanged. capture_gap = info line only.
  close.py/grade.py untouched because their sha1s are pinned in challenger/PREREG_3386583f18.md; challenger/grade_shadow.py
  (also pinned) therefore still counts early-close rows in its z-CLV.
- 2026-10-17 slate: BOS@LA early_close 16.7 min; EDM@UTA and PIT@VGK capture_gap 11.8 min (capture loop silent
  6:48-7:46 PM PT, no supervisor alert: looks like a box pause). Oct 16 BOS@ANA capture_gap 19.0 min.
- NFL (nfl-props): snapshot.py is append-only (never overwrites) and snaplines.py already skips empty passes; no guard
  needed (and both are hash-pinned in the published prereg). props-finder find.py writes a new raw/<timestamp>/ dir per run.

## 2026-10-19 stat overrides (official boxscore corrections)
- check_gaps --box flagged game 2026020129 (Oct 17 NYR @ CBJ): official boxscore now has Adam Fox (8479323) 3 SOG (ours 2), Braden Schneider (8482073) 4 SOG (ours 3); re-fetch from stats REST did not pick it up.
- Added data/stat_overrides.csv + apply_overrides.py; fetch.py applies overrides before writing data/s*.pkl, so re-fetches keep them. Applied to data/s2026.pkl (backup in data/backup_20261019_094626/).
- No regrade: Fox Oct 17 graded row (1.5 line, actual 2 -> 3) stays OVER; Schneider had no shots line Oct 17. Oct 17 graded files untouched.
- check_gaps.py --days 14 --box after patch: 97 games, 0 problems, OK.

## 2026-10-19 goalie saves capture re-enabled (USER-APPROVED: do not revert)
- yinzerduck approved capturing DraftKings goalie saves lines on 2026-10-15 and reconfirmed on 2026-10-19 (5:54 PM PT)
  in the Grok Bot chat. The Oct 17 revert (logs/capture_goalie_saves_unapproved_20261017.patch) happened because the approval
  was not recorded here. It is recorded now, so this change should NOT be reverted as unapproved.
- capture.py: also keeps 'Total Saves' + 'Goalkeeper Saves Milestones' rows from the same ESPN provider-100 propBets feed
  (rows go into raw). New output key saves_lines next to sog_lines, same fields, built by the same sides() pairing (milestone
  side check, falling back to listing order). sog_lines, the empty-pull guard (keep_main still checks sog_lines only), close.py and grade.py are unchanged.
- Gap: no saves were captured from Oct 17 to Oct 19. Known caveat: the feed's goalie-to-team matching looked off on Oct 15 (Bobrovsky
  showed up in BUF@TOR), so check it before building a model.

## List rule changes
- 2026-10-20 15:12 PT (commit 3f24324): 5.0-pt minimum model edge vs no-vig on DraftKings and Fliff-check lists (build_sheet.py assign_status). First list under it: 20261020_1513 (3:12 PM PT pass; dropped McCann, Seider, Finnie overs). Lists 20261020_1305/1406/1508 and earlier are pre-floor. Prereg scoring for champion c3ab760178 and challenger 3386583f18 unchanged.
- 2026-10-20 ~13:12 PT (commit d6cb300): TOI-down evidence vote uses this-season baseline, 1.0-min threshold. First list under it: 20261020_1406.

## Tolvanen 64.7% "recent form" (Oct 19 U1.5), audited 2026-10-21
- It is not a hit rate. recent_form.py: mu = sog60_r10 x toi_r5 / 60 = 5.995 x 12.447 / 60 = 1.244 shots;
  P(under 1.5) = Poisson P(X<=1) = e^-1.244 x (1 + 1.244) = 64.7%. No-vig under was 51.5%, so it "passed".
- Actual last 5 before Oct 19 (NHL API game log): Oct 17 CBJ 2, Oct 15 NJD 0, Oct 13 TBL 1, Oct 11 VAN 2, Oct 9 WSH 2
  -> 2 of 5 under 1.5 (40%), matching Hockey-Reference; last 10: 4 of 10 (l10_over_rate 0.5 in the D file).
- The feed's inputs are correct; the label is misleading. The rate (6.0 shots/60) times his low TOI (12.4 min) gives 1.24 expected
  shots, below the 1.4 he actually averaged over the last 5, and a Poisson fit has more mass at 0-1 than his recent games show.
  Next step: the room card shows the empirical last-5/last-10 under count next to the Poisson %, so the two can't be mixed up.
  (He took 1 shot Oct 19, so the under won.)

## 2026-10-24: outage backfill + display changes
- Outage: the box was suspended (no Grok Bot usage) from ~Oct 21 13:37 PT; capture_loop ran only Oct 22 09:27, Oct 23 04:58-05:58, Oct 24 00:17.
  Supervisor/loop processes survived; ensure_capture.sh re-run 2026-10-24 00:3x PT: game logs through 2026-10-23, gap check OK.
  Killed stale ADHOC loop (pid 538357, `for i in 1..7 sleep 1200 capture.py ADHOC`).
- Catch-up track: rebuilt/catchup/ (see graded/REPORT.md). run_type=catchup, separate from live lists.
- Fliff: 'not offered on Fliff ...' relabeled 'captured before Fliff posted ...' in fliff_prices/20261017-19 and
  graded/fliffcheck_list_20261017.csv (user slips show Fliff shots markets live Oct 19, e.g. Tolvanen U1.5 -140 1:00 PM).
- recent_form.py/build_sheet.py DISPLAY ONLY: last5_shots + recent_windows label; post text shows 'last 5: N of 5 <side>' next to
  model %. Status unchanged (20261020_1548 rebuilt to /tmp: identical statuses). Champion/challenger untouched.
- PROPOSAL (not implemented; changes the recent-form gate so it changes lists): recent_mu = sog60_r10 * toi_r10 (same window).
  D files carry toi_r5/toi_r30 only, so it needs a toi_r10 column; approve before switching. Until then cards label the windows.

- User bets Oct 24 (Fliff Cash, own results): Laferriere U2.5 -120 risk 0.10 WIN payout 0.18 (pick 701918164); Bratt O1.5 -200 risk 0.10 LOSS (pick 701918055). Net -0.02. Balance 5.66.
- User bets Oct 24 (DraftKings, own results): Bratt O1.5 -190 $0.10 LOSS (DK639284581623617245, 10:02 AM); Laferriere U2.5 -110 $0.10 WON paid $0.19. Net -$0.01. DK balance $1.45.
- User bet Oct 24 (Fliff, own result, OFF-LIST CFB near-miss, not a model pick): Northern Illinois +2.5 vs Hawaii +100, risk 0.10, LOSS (pick 701944042, 11:12 AM).
- Oct 24 user bet (off-list CFB, Fliff): Navy +3.5 (North Texas at Navy) -125, risk 0.10, LOSS (pick 701944043).
- Oct 24 user bet (off-list CFB, Fliff): Over 58.5 (San Diego State vs Colorado State) -125, risk 0.10, WIN paid 0.18 (pick 701944040). Off-list day net -0.12. Fliff balance 5.64 at 5:14 PM PT.
- Oct 24 user bet (DK, 1:07 list): Toffoli OVER 1.5 SOG (San Jose Sharks vs Boston Bruins) -120, $0.10, WIN paid $0.18 (DK639284699533632671). DK balance $1.43 at 5:15 PM PT. Another DK Over 2.5 +100 still open (player not visible).
- Oct 24 user bet (DK, 1:07 list): Aho OVER 2.5 SOG (Carolina Hurricanes vs St. Louis Blues) +100, $0.10, LOSS (1 shot; CAR led 4-0 late) (DK639284699535471483). Blowout flag: yes. DK Oct 24 net: Toffoli +0.08, Aho -0.10.
- Oct 24 user bets (Fliff, 1:07 list): Toffoli OVER 1.5 (SJ vs BOS) -125 WIN; Aho OVER 2.5 (CAR vs STL) -110 LOSS (pick 701987187); Tom Wilson UNDER 1.5 (BUF vs WSH) +125 LOSS (pick 701991506) - different line from card's UNDER 2.5, tag off-number. 0.10 each. Fliff balance 6.01 at 7:21 PM PT.
- Oct 24 user bet (DK, OFF-LIST - Hayton was a skip on 3:12 pass): Barrett Hayton UNDER 1.5 SOG (Tampa Bay Lightning vs Utah Mammoth) +105, $0.10, LOSS (DK639284832073848388, placed 5:00 PM). Another DK bet placed 5:02:56 PM (DK639284833769987855) not yet seen.
- Oct 24 user bet (DK, 4:09 card pick, own result): Emmitt Finnie OVER 1.5 SOG (Detroit Red Wings at Calgary Flames) -105, $0.10, LOSS (0 shots) (DK639284833769987855, 5:02:56 PM). Verified from DK video Oct 25. Oct 24 bets backfilled into props-finder/user_bets/bets.csv (Bratt/Laferriere = LA @ NJ).
- 2026-10-25 16:01 window pass (MIN@VAN 7:00 PM): NO BETS. DeBrusk U2.5 was build_sheet 'Fliff check' but skipped by the 2-of-7 agreement rule; original post kept in picks/20261025_1601_post_prerule.txt, posted post.txt empty. 0 Fliff credits.
- 2026-10-26 13:11 PT: ensure_capture gap check FAILED on game 2026020181 (Oct 25 NYI @ DAL): official boxscore has Simon Holmstrom (8481601) 1 SOG, ours 2. Added to data/stat_overrides.csv and applied to data/s2026.pkl (backup data/backup_20261026_131127/); recheck 98 games, 0 problems. No graded rows touched; NYI/DAL not on today's slate.
- 2026-10-26 1:00 PM window pass (fired late, run 13:11 PT; LA@NYR 4:00 PM): list 20261026_1311, Fliff check Moore O1.5 and Laferriere U2.5 (both 3 of 7), both Fliff (-165/-130) and DK (-145) worse than -123 shop-at. 1 Fliff credit.
- 2026-10-26 2:30 PM window pass (run 14:38 PT; TOR@CGY 5:30 PM): list 20261026_1438, Fliff check Raddysh U2.5 (3 of 7), Fliff -125 and DK -125 worse than -107 shop-at; no PrizePicks types. 1 Fliff credit (2 of 10 today).
- 2026-10-26 3:12 PM pass (run 15:16 PT; new game DET@EDM 6:30 PM): list 20261026_1516, DK none, Fliff check Kapanen U1.5 (4 of 7), Fliff -115 and DK -110 worse than +105 shop-at. 1 Fliff credit (3/10 today).
- 2026-10-26 3:30 PM window pass (fired 15:35, run 15:36 PT): NO_WINDOW_GAMES. DET@EDM (6:30 PM) was already scored and posted by the 3:12 PM pass (list 20261026_1516); predict.py keeps posted games byte-identical, so no re-score, no new list files, nothing posted. 0 Fliff credits (3/10 today).
- 2026-10-27 1:00 PM window pass (fired 13:05, run 13:06 PT; CBJ@PHI 4:00 PM): list 20261027_1305, Fliff check Sanheim O1.5 (4 of 7), Dvorak U1.5 and Bump U1.5 (3 of 7); Fliff not yet posted, DK worse than shop-at for all. Werenski U3.5 (build_sheet Fliff check) skipped in the room post because CBJ DFO lineup was ~27h old (approved 12h rule, not yet in code). 1 Fliff credit (1/10 today). Note: routine prompt text still describes Oct 26 games.
- 2026-10-27 1:30 PM window pass (fired 13:39, run 13:39 PT; 6 games at 5:00 PM: BOS@CAR, LA@CHI, MTL@STL, NYI@NSH, NJ@DAL, FLA@WPG): list 20261027_1339, Fliff check Stankoven O2.5 and Scheifele O1.5 (5 of 7); Fliff +105 worse than +125 on Stankoven, Scheifele not on Fliff yet, DK worse than shop-at for both. Meier/Bratt/Hughes (NJD) skipped in room post, NJD DFO lineup ~29h old (12h rule, not in code). fliff_prices run on picks/20261027_1339_post_fliffeligible.txt (2 credits, 3/10 today).
- 2026-10-27 2:30 PM window pass (fired 14:31, run 14:31 PT; MIN@UTA 6:00 PM): list 20261027_1432, Fliff check Guenther U2.5 (3 of 7; no-vig moved 16.1 pts toward over since open); Fliff not posted for the game, DK +120 worse than +133 shop-at. Coleman O1.5 (build_sheet Fliff check) skipped in room post, MIN DFO lineup ~31h old (12h rule, not in code). fliff_prices run on picks/20261027_1432_post_fliffeligible.txt (1 credit, 4/10 today).
- 2026-10-27 3:00 PM window pass (fired 15:06, run 15:06 PT): NO_WINDOW_GAMES. All 8 slate games already scored by earlier passes (latest MIN@UTA 6:00 PM, list 20261027_1432); no new list files, nothing posted. 0 Fliff credits (4/10 today).
- 2026-10-27 3:30 PM window pass (fired 15:33, run 15:33 PT; OTT@VGK and VAN@ANA 7:00 PM, D snapshots from the 3:12 line capture): list 20261027_1533, NO BETS. Fliff check Hertl U2.5 (5 of 7), LaCombe U1.5 and Gauthier U3.5 (4 of 7); Fliff -180/-115/+100 and DK all worse than shop-at. DeBrusk U2.5 and O'Connor U1.5 skipped in room post, VAN DFO lineup ~28h old (12h rule, not in code). fliff_prices run on picks/20261027_1533_post_fliffeligible.txt (2 credits, 6/10 today).
- 2026-10-27 4:00 PM window pass (fired 16:09, run 16:09 PT; BUF@SJ 7:30 PM): list 20261027_1609, NO BETS. Fliff check Quinn U2.5 (3 of 7); Fliff -125 and DK -105 worse than +109 shop-at. BUF/SJ DFO lineups fresh. fliff_prices run on picks/20261027_1609_post.txt (1 credit, 7/10 today).
- 2026-10-27 4:30 PM window pass (fired 16:39, run 16:40 PT): NO_WINDOW_GAMES. All 11 slate games already scored by earlier passes (latest BUF@SJ 7:30 PM, list 20261027_1609); no new list files, nothing posted. 0 Fliff credits (7/10 today).

## User real bet, Oct 27, 2026 (logged Oct 28 12:46 AM PT)
PrizePicks 2-pick Power Play, $1 to win $2.60: Scheifele (WPG) OVER 1.5 SOG, FLA@WPG — hit (3 SOG); Brunson (NYK) OVER 26.5 PRA (discounted from 34.5), DET@NYK — 28 with 5:24 left Q4, final pending. Screenshot user_bets/20261027_pp_scheifele_brunson.jpg. To do: confirm finals and grade; CLV for Scheifele vs our C/close capture.
Tag: Brunson leg is an off-card NBA promo leg; the entry counts toward real bets, only Scheifele counts toward the NHL card record.
- 2026-10-28 12:30 PM window pass (fired 12:30, run 12:30 PT): NO_WINDOW_GAMES. Slate is PHI@WSH 4:30, CGY@EDM 5:30, NJD@COL 6:00, TOR@SEA 7:00 PM; none 150-210 min out and no D snapshots for today yet. Nothing posted, 0 Fliff credits.
- 2026-10-28 1:00 PM window pass (fired 13:01, run 13:04 PT after the capture loop took the PHI@WSH D snapshot at 13:04, 205 min out): list 20261028_1304, NO BETS. Fliff check Sanheim O1.5 and Zegras O1.5 (4 of 7), Protas U1.5 (5 of 7); Fliff +110/-145/-115 and DK +115/-125/-120 all worse than shop-at +129/-107/-103. PHI/WSH DFO lineups fresh (7:22/9:52 AM). 6 role vetoes. fliff_prices run on picks/20261028_1304_post.txt (1 credit, 1/10 today).
- 2026-10-28 1:30 PM window pass (fired 13:37, run 13:37 PT): NO_WINDOW_GAMES. PHI@WSH (4:30 PM) already scored/posted by list 20261028_1304; CGY@EDM 5:30 PM is ~233 min out with no D snapshot yet. No new list files, nothing posted. 0 Fliff credits (1/10 today).
- 2026-10-28 3:00 PM window pass (fired 15:08, run 15:09 PT; NJD@COL 6:00 PM, 171 min out): list 20261028_1509, NO BETS. Fliff check Malinski U1.5 (4 of 7); Fliff -140 and DK -140 worse than -121 shop-at. NJD/COL DFO lineups fresh (7:44/10:25 AM). 5 role vetoes + 1 slot veto. CGY@EDM 5:30 PM never scored: 2:00-3:00 PM passes did not run (last run 1:37), 141 min out at 15:09, left off. fliff_prices run on picks/20261028_1509_post.txt (1 credit, 2/10 today).

## Missed window passes, Wed Oct 28, 2026 (investigated 3:15 PM PT)
- Missed: 2:00 PM and 2:30 PM PT runs of 'NHL SOG: daily window passes' left no trace (no picks/, captures/fliff, sheets, card_decisions or NOTES output). Runs seen: 13:37 and 15:08 (15:00 slot, 8 min late). No final-call runs/markers between 13:26 and 15:09.
- Missed game: CGY@EDM 5:30 PM PT never scored (window 2:00-3:00 PM PT); 141 min out at 15:09, left off card.
- Evidence: uptime since Oct 26 17:22 (no reboot; no journal available). No stale lock/pid files in nhl-sog or picks. Every box writer goes quiet 13:39-14:40: NFL snapshot manifest jumps 13:38:43 -> 14:41:14 (was every ~10-20 min before), next box file is captures/20261029/*_D.json at 14:40. Pattern matches the Oct 21 suspension note (box idle/suspended; uptime doesn't reset on suspend).
- Likely cause: box/agent suspended or wakes not delivered ~13:40-14:40 PT, so the scheduler skipped the 2:00 and 2:30 slots with no catch-up; not a run that started and died (no partial files). Not fully proven (no scheduler log on box).
- Side note: the 14:40 CGY@EDM D snapshot was filed under captures/20261029 (UTC game date), which may be why the 15:09 pass treated EDM as un-snapshotted; check the date-folder lookup.
- 2026-10-28 3:30 PM window pass (fired 15:34, run 15:35 PT; TOR@SEA 7:00 PM, 205 min out, D snapshot 209 min out): list 20261028_1535, NO BETS. Fliff check Nylander O2.5 (6 of 7) and Raddysh U2.5 (3 of 7); Fliff -130/-125 and DK -115/-130 worse than shop-at +101/-112. TOR DFO fresh (11:40 AM); SEA DFO ~2 days old (12h rule, all SEA sides skipped, none qualified). 11 role vetoes + 5 slot vetoes. fliff_prices run on picks/20261028_1535_post.txt (1 credit, 3/10 today). CGY@EDM 5:30 PM 115 min out, still unscored.
- 2026-10-28 4:00 PM window pass (fired 16:04, run 16:04 PT): NO_WINDOW_GAMES. PHI@WSH, NJD@COL, TOR@SEA already scored/posted (latest list 20261028_1535); next-day captures/20261029 holds only CGY@EDM/NJD@COL/TOR@SEA D snapshots, no later games. CGY@EDM already logged as missed (not re-reported). No new list files, nothing posted. 0 Fliff credits (3/10 today).
- 2026-10-28 4:30 PM window pass (fired 16:33 PT): NO_WINDOW_GAMES. No games 150-210 min out; PHI@WSH, NJD@COL, TOR@SEA already posted, CGY@EDM already logged missed. Nothing posted. 0 Fliff credits.
- Oct 28 REAL BET (Chalkboard 2-pick, placed 1:36 PM PT, $5 to win $15.65): Protas OVER 1.5 SOG (WSH vs PHI) + Maxey OVER 0.5 pts. WON (+$10.65). Tags: off-card (Protas is against model side UNDER, shop-at -103; excluded from card/model grading); Maxey = off-card promo leg. Screenshot user_bets/20261028_cb_protas_maxey.jpg
- 2026-10-29 12:00 PM window pass (fired 12:06, run 12:07 PT): NO_WINDOW_GAMES. Earliest games 4:00 PM PT (WPG@TBL, UTA@PIT, CBJ@CAR) ~233 min out; no D snapshots for today yet. Nothing posted, 0 Fliff credits.
- 2026-10-29 12:30 PM window pass (fired 12:33, run 12:33 PT; WPG@TBL, UTA@PIT, CBJ@CAR 4:00 PM, 206 min out, D snapshots 209 min out from the 12:31 capture): list 20261029_1233, NO BETS. Fliff check Goncalves U1.5 and Aho O2.5 (5 of 7), Weegar O1.5 and Ehlers O1.5 (4 of 7), Guenther U2.5 (3 of 7; no-vig moved 16.3 pts toward over). Fliff not posted for any of the 3 games; DK -155/-120/-120/-170/+115 all worse than shop-at. PIT DFO ~26h old (12h rule, all PIT sides skipped, none qualified); other 5 teams fresh. 11 role vetoes + 6 slot vetoes. fliff_prices run on picks/20261029_1233_post.txt (3 credits, 3/10 today). Room post picks/20261029_1233_room.txt. No missed games.
- Oct 27 PrizePicks SETTLED (graded Oct 31): Brunson final 23 pts/1 reb/7 ast = 31 PRA > 26.5, hit (NBA.com box, NYK 111-97). Entry WON, $1 -> $2.60 (+$1.60). Scheifele CLV vs our close: no-vig over 58.6% at pick -> 57.8% close = -0.8 pts (line 1.5 unchanged). Rows added to /workspace/props-finder/user_bets/bets.csv (backup bets.csv.bak_20261031).

2026-10-31 (Tester1): Gate-file mismatch found during enhancement #1.
The Oct 17 sides Kyrou and Chytil (promotion-vetoed unders) appear only in
picks/20261017_D_GATE.csv, and that file doesn't line up with its picks file.
Both sides were left out of the re-score (107 graded vs 109 promotion-only rows).
Note: Tester2 lists Kyrou among the 6 list sides, so the Kyrou row there may be
a different date or game; re-check.

## 2026-10-31 9:30 AM PT: missing-close fix moved to a reporting overlay (prereg pin respected)
- A no_close edit to grade.py (made 2026-10-31) was REVERTED: grade.py is back to sha1 5b8dcaa79429f8b34e4c612efc618cfe33d859c0 (pinned in challenger/PREREG_3386583f18.md).
  graded/{20261011,13,14,20,29}.csv, graded/REPORT.md, graded/three_records.* restored from *.bak_20261031 (= git HEAD for the date files); challenger/SHADOW_REPORT.md regenerated by the pinned grade_shadow.py from the restored inputs.
- New scripts/overlay_noclose.py -> graded_overlay/<date>.csv + REPORT.md (+ flips.csv, discrepancies.csv). Pinned grading still VOIDs lines with no close (VOID_noC / VOID_pulled_before_close);
  the overlay grades them as OK with clv_status no_close / pulled_before_close and blank CLV. It uses LOGGED shot counts only (no box substitution; Oct 12-13 rule above).
  Logged vs official on flipped rows (info only, not applied): Cozens 2026020096 logged 1 / official 2; J. Blake 2026020150 logged 5 / official 6.
- card_decisions.csv line 31 (20261026_1516 Kapanen) note quoted (unquoted comma broke three_records.py since Oct 26). Backup card_decisions.csv.bak_20261031.
  Line 54 (20261029_1233 NO BETS) has only 3 fields; pandas tolerates it, left as is.

## 2026-10-31 9:35 AM PT: PREREG_3386583f18 amendment (grade_shadow.py pin) + three_records (b) + overlay scope
- PREREG AMENDMENT: challenger/grade_shadow.py is pinned at sha1 8d974286624d7a8bc3772d4b3c5e3e97e6e06bd1 (prereg commit de51760, 2026-10-17 5:20 AM PT).
  It was changed in a71c495 (2026-10-17 9:27 AM PT), now sha1 9ac370abc6735c0c14e7b07cff7e8fdbf9731e8f, adding only the pre-noon PT puck-drop exclusion
  (game_starts.mark_pre_noon -> excluded_pre_noon, same rule as grade_report.py) and its report note, before any shadow slate was graded. Scoring math unchanged
  (git diff de51760 a71c495 -- challenger/grade_shadow.py touches only the docstring, the mark_pre_noon call and the note). No later change. 9ac370ab is the operative pin.
- three_records.py (not pinned in any prereg): (b) final card now counts only sides with a card play decision. Excluded to new buckets: no_decision
  (list has no card_decisions.csv row), no_bets (list-level NO BETS or side no_bets), held (hold_*, e.g. Scheifele 20261027_1339). Backup three_records.py.bak_20261031.
- overlay_noclose.py now flips only VOID_noC; VOID_pulled_before_close (10 Oct 14 + Rasmussen Oct 26) stays void. Backup scripts/overlay_noclose.py.bak_20261031.
- 2026-10-31 9:40 AM PT: card_decisions.csv += 20261024_0922 Bratt O1.5 / Laferriere U2.5 as card (FINAL CALL marker drafted 9:42 AM, card text only in chat; both bet by user per lines 164-165). Backup card_decisions.csv.bak2_20261031.
  three_records.py (backup .bak2_20261031) now reports (b)(i) card plays only and (b)(ii) plus no_decision lists (Oct 17 pre-FINAL-CALL lists + 20261020_1548: no marker, no decision row).
- 2026-10-31 9:45 AM PT (room rule): three_records.py (b)(i) official final card = sides from lists with picks/finalcall_done/<list>.txt OR an explicit card row; others -> no_marker (Oct 17 4:18 PM McNabb/Stone/Marner, Oct 18 Knies U1.5, Aho O2.5). (i) 17 sides 11-6 +2.71u; (ii) 44 sides 23-21 -2.66u kept. Label 20261017_AM -> 20261017_post. Matches tester1-review/audit_20261031/finalcard_check/mine.csv. Backup three_records.py.bak3.
- 2026-10-31 9:50 AM PT (room rule): explicit cleared hold rows (hold_*, e.g. Scheifele O1.5 20261027_1339 hold_prizepicks) count as card plays: (b)(i) 18 sides 12-6 +3.30u; (b)(ii) 45 sides 24-21 -2.07u. decision_src for list-level NO BETS sides (20261027_1533 Hertl/LaCombe/Gauthier, 20261029_1233 x5) now cites the list's NO BETS row. Backup three_records.py.bak4.
- 2026-10-31 Oct 31 early-window pass, 1 PM games (one-off routine fired 10:09, run 10:09 PT; BUF@LA and OTT@SJ 1:00 PM, 171 min out, D snapshots 178 min out from the 10:02 capture): list 20261031_1009, NO BETS. Fliff check Panarin O2.5 (4 of 7; DK -120 worse than -103 shop-at) and Chabot O1.5 (4 of 7; skipped, OTT DFO ~27h old, 12h rule; DK -140 worse than -118). Fliff not posted for either game. BUF/OTT/SJ DFO ~27-28h old (all their sides skipped); LA fresh. 4 role vetoes + 2 slot vetoes. fliff_prices run on picks/20261031_1009_post.txt (2 credits, 2/10 today). Room post picks/20261031_1009_room.txt. Note: picks/20261031_D.csv already held 4 earlier games (CHI@BOS, STL@DET, TB@NSH, EDM@NYI), kept byte-identical.
- 2026-10-31 12:00 PM window pass (fired 12:03, run 12:03 PT): NO_WINDOW_GAMES. Next games PIT@MTL and TOR@VAN 4:00 PM (~237 min out), CBJ@DAL 5:00, CGY@COL 7:00; BUF@LA and OTT@SJ 1:00 PM already posted (list 20261031_1009); morning games already in picks/20261031_D.csv. No missed games. Nothing posted, 0 Fliff credits (2/10 today).
- 2026-10-31 12:30 PM window pass (fired 12:31, run 12:32 PT; PIT@MTL and TOR@VAN 4:00 PM, 208 min out, D snapshots 208 min out): list 20261031_1232, NO BETS. Fliff check Newhook U1.5 (4 of 7), Rielly U1.5 and Raddysh U2.5 (3 of 7), all skipped by the 12h rule (MTL DFO ~29.5h, TOR ~24h); DK -120/-115/-135 also worse than shop-at -105/+101/-116. PIT DFO ~26h (all sides skipped), VAN fresh (~8h). Fliff not posted for either game. 8 role vetoes + 8 slot vetoes. fliff_prices run on picks/20261031_1232_post.txt (2 credits, 4/10 today). Room post picks/20261031_1232_room.txt. No missed games.
- 2026-10-31 (PT): idmap.json: added ESPN 4874734 (Zack Bolduc, MTL) -> NHL 8482737 (NHL lists him as 'Zachary Bolduc', so name-search cached null). 12:32 Bolduc O1.5 was dropped unscored; no rescore/list change. Backup: captures/idmap.json.bak_20261031_bolduc.
- 2026-10-31 (PT): idmap.json: set ESPN 5291946 (Roger McQueen, ANA) -> 8485400 and 3068087 (Damon Severson, CBJ) -> 8476923 (were cached null). Bobby Brink 4565257 already mapped to 8481553 (MIN), unchanged. No rescore/capture/list edits. Backup: captures/idmap.json.bak_20261031_mcq_sev.
- 2026-10-31 1:00 PM window pass (fired 13:02, run 13:03 PT): NO_WINDOW_GAMES. PIT@MTL and TOR@VAN 4:00 PM already posted (list 20261031_1232); CBJ@DAL 5:00 PM ~237 min out, CGY@COL 7:00 PM later. No missed games. Nothing posted, 0 Fliff credits (4/10 today).
- 2026-10-31 1:30 PM window pass (fired 13:31, run 13:32 PT; CBJ@DAL 5:00 PM, 208 min out): no D snapshot existed (the hourly capture wake starts at 2:35 PM), so ran the free capture.py, which saved captures/20261101/401892622_D.json (208 min out, 13 lines). List 20261031_1332, NO BETS. 0 sides with positive DK EV (best -5.9%), no Fliff checks, 0 Fliff credits (4/10 today). 1 role veto (Rantanen O1.5, demotion to PP2), 0 slot vetoes. DAL DFO ~27h, CBJ ~30.5h (12h rule would skip all). Room post picks/20261031_1332_room.txt. No missed games. Data oddity: Matthew Knies listed as CBJ (ESPN/DK feed) - check roster mapping later.
- 2026-10-31 1:36 PM PT: Tester1 check of 20261031_1332: Knies U1.5 (+5.4 pts) should have been a Fliff check (skip: CBJ lineup 30.5h, no Fliff market, DK -150 -6.6% EV). Known bug: role check takes PP2 when DailyFaceoff lists a player on both PP1 and PP2 (Rantanen, DAL Oct 30 10:26). Fix to draft after tonight, Tester2 to cross-check; live gate unchanged today. Knies team flag was a false alarm (traded to CBJ Sept 28).
- 2026-10-31 2:00 PM window pass (fired 14:02, run 14:02 PT): NO_WINDOW_GAMES. CBJ@DAL 5:00 PM already posted (list 20261031_1332); CGY@COL 7:00 PM ~298 min out. All earlier games scored. No missed games. Nothing posted, 0 Fliff credits (4/10 today).
- 2026-10-31 2:30 PM window pass (fired 14:33, run 14:33 PT): NO_WINDOW_GAMES. CBJ@DAL 5:00 PM already posted (list 20261031_1332); CGY@COL 7:00 PM ~267 min out. All earlier games scored. No missed games. Nothing posted, 0 Fliff credits (4/10 today).
- 2026-10-31 3:00 PM window pass (fired 15:09, run 15:09 PT): NO_WINDOW_GAMES. CGY@COL 7:00 PM ~231 min out (NHL schedule rechecked); all earlier games already scored/posted (latest list 20261031_1332). No missed games. Nothing posted, 0 Fliff credits (4/10 today).
- 2026-10-31 3:30 PM window pass (fired 15:37, run 15:37 PT; CGY@COL 7:00 PM, 202 min out, D snapshot 204 min out from the 3:36 capture): list 20261031_1537, NO BETS. Fliff check Backlund O1.5 (4 of 7) and Nelson O1.5 (5 of 7); Fliff not posted for the game, DK -145/-160 worse than shop-at -126/-134. CGY DFO fresh (2:16 PM), COL fresh (7:30 AM). 4 role vetoes + 0 slot vetoes. fliff_prices run on picks/20261031_1537_post.txt (1 credit, 5/10 today). Room post picks/20261031_1537_room.txt. No missed games; all of today's games now scored.

- 2026-10-31 4:00 PM PT: Item #7 (CLV on user NHL bets Oct 11-24) closed. Tester2 owner, Tester1 rebuilt = matches. 43/50 with DK close: DK +0.2, Fliff -1.1, all -0.3 pts implied (vig-in; ~-4.2 vs no-vig close). 7 missing closes are real (3 close-window snapshot misses + Cooley line move). Files: /workspace/tester1-review/check_item7_clv/.
- Correction: missing closes = 3 games on 2 dates. TB@NYR Oct 13 is a SEPARATE missed close outside the Oct 20-23 outage window; DET@SEA and BOS@DAL Oct 20 fall in it.
- 2026-11-01 7:34 AM PT: PENDING (user approved): remove pre-noon PT exclusion (predict.py window check + grade_report.py + challenger/grade_shadow.py mark_pre_noon). Yinzer drafts dated change, Tester2 cross-checks, live before next pre-noon game. Window passes now fire 7:00 AM-4:30 PM PT; early-game scheduler paused.
- 2026-11-01 7:30 AM window pass (fired 7:39, run 7:40 PT): NO_WINDOW_GAMES (next MIN@WSH 12:30 PM ~289 min out). MISSED: WPG@CAR 10:00 AM PT (gameId 2026020227), now ~139 min out, never scored; it was pre-noon-excluded under the live rule at the 7:08 pass (172 min out) and the approved removal of the pre-noon exclusion (7:34 AM) was not live in time. Not priced. 0 Fliff credits (0/10 today).
- 2026-11-01 9:00 AM window pass (fired 9:08, run 9:08 PT; MIN@WSH 12:30 PM, 202 min out, D snapshot 204 min out): list 20261101_0908, NO BETS. 0 leans (largest edge <1 pt), 0 sides with positive DK EV (best -5.4%, Chychrun U2.5), no Fliff checks, 0 Fliff credits (0/10 today). 2 role vetoes (Kyrou U promotion, Leonard O demotion), 0 slot vetoes. MIN/WSH DFO ~25h old (Oct 31 7:57 AM; 12h rule would skip all). Room post picks/20261101_0908_room.txt. No newly missed games (WPG@CAR already logged at 7:40).
- 2026-11-01 9:14 AM PT: Knies U1.5 (20261031_1332) reason corrected to thin edge (model +5.4, recent +0.4 vs no-vig); no floor bug (Ovechkin 0908 same recent-form skip). Tester2 to check.
- 2026-11-01 9:12 line-capture pass (fired 9:16, run 9:17 PT): graded 20261031 (0 graded picks, 154 OK + 1 VOID_dnp), grade_report + grade_shadow OK; logs through Oct 31; gap check OK. predict.py full-day added WPG@CAR 10:00 AM (2026020227, pre-noon, not listed). MIN@WSH already posted (0908). UTA@PHI/EDM@NYR/OTT@ANA no lines yet. Both lists empty; no sheet, 0 Fliff credits (0/10).
- 2026-11-01 9:30 AM window pass (fired 9:33, run 9:33 PT; UTA@PHI 1:00 PM, 206 min out, D snapshot 206.7 min out from the 9:33 capture): list 20261101_0933, NO BETS. 0 DK-listable. Fliff check Zegras O1.5 and Martone O1.5 (5 of 7), Trocheck O1.5 and Guenther U2.5 (3 of 7; Guenther no-vig moved 16.9 pts away), Sanheim O1.5 (2 of 7, skip). Fliff not posted for the game. PHI DFO ~24.5h (Oct 31 9:06 AM), UTA ~51h (Oct 30 6:54 AM); 12h rule skips all. 1 injury veto (Tippett), 3 role vetoes, 0 slot vetoes. fliff_prices run on picks/20261101_0933_post.txt (1 credit, 1/10 today). Room post picks/20261101_0933_room.txt. No newly missed games (WPG@CAR already logged; MIN@WSH posted 0908).
- 2026-11-01 10:00 AM window pass (fired 10:03, run 10:05 PT): NO_WINDOW_GAMES. MIN@WSH 12:30 (list 20261101_0908) and UTA@PHI 1:00 PM (list 20261101_0933) already posted; EDM@NYR 3:00 PM ~296 min out, OTT@ANA 5:00 PM later. WPG@CAR already logged missed. Nothing posted, 0 Fliff credits (1/10 today).
- 2026-11-01 10:30 AM window pass (fired 10:30, run 10:31 PT): NO_WINDOW_GAMES (NHL schedule rechecked, times unchanged). EDM@NYR 3:00 PM ~269 min out, OTT@ANA 5:00 PM later; MIN@WSH (0908) and UTA@PHI (0933) already posted; WPG@CAR already logged missed. Nothing posted, 0 Fliff credits (1/10 today).
- 2026-11-01 11:00 AM window pass (fired 11:03, run 11:04 PT): NO_WINDOW_GAMES (NHL schedule rechecked, times unchanged). EDM@NYR 3:00 PM ~236 min out, OTT@ANA 5:00 PM later; MIN@WSH (0908) and UTA@PHI (0933) already posted; WPG@CAR already logged missed. Nothing posted, 0 Fliff credits (1/10 today).
- 2026-11-01 11:30 AM window pass (fired 11:36, run 11:37 PT; EDM@NYR 3:00 PM, 203 min out): no D snapshot existed, so ran the free capture.py, which saved captures/20261101/401892627_D.json (203 min out, 15 lines). List 20261101_1137, NO BETS. 0 DK-listable (best DK EV -5.9%). Fliff check Podkolzin U1.5 (4 of 7) and Dorofeyev U2.5 (3 of 7); Fliff +110/+105 and DK +110/+110 worse than +125 shop-at. EDM DFO fresh (6:25 AM PT), NYR DFO ~26h (Oct 31 9:22 AM PT; 12h rule skips NYR sides). 0 injury vetoes, 1 demotion (Cuylle O), 3 promotions (Bjorkstrand/Kapanen/Kartye U), 1 gate_unverified (Perreault), 0 slot vetoes. fliff_prices run on picks/20261101_1137_post.txt (1 credit, 2/10 today). Room post picks/20261101_1137_room.txt. No newly missed games (OTT@ANA 5:00 PM later).
- 2026-11-01 12:00 PM window pass (fired 12:00, run 12:01 PT): NO_WINDOW_GAMES (NHL schedule rechecked, times unchanged). EDM@NYR 3:00 PM (179 min out) already posted (list 20261101_1137); OTT@ANA 5:00 PM ~299 min out; MIN@WSH (0908) and UTA@PHI (0933) posted; WPG@CAR already logged missed. Nothing posted, 0 Fliff credits (2/10 today).
- 2026-11-01 12:30 PM window pass (fired 12:30, run 12:31 PT): NO_WINDOW_GAMES (NHL schedule rechecked, times unchanged). OTT@ANA 5:00 PM ~269 min out; EDM@NYR (1137), MIN@WSH (0908), UTA@PHI (0933) posted; WPG@CAR already logged missed. Nothing posted, 0 Fliff credits (2/10 today).
- 2026-11-01 1:00 PM window pass (fired 13:09, run 13:10 PT): NO_WINDOW_GAMES (NHL schedule rechecked, times unchanged). OTT@ANA 5:00 PM ~230 min out; EDM@NYR (1137), MIN@WSH (0908), UTA@PHI (0933) posted; WPG@CAR already logged missed. Nothing posted, 0 Fliff credits (2/10 today).
- 2026-11-01 1:30 PM window pass (fired 13:33, run 13:34 PT; OTT@ANA 5:00 PM, 206 min out, D snapshot 209 min out from the 1:31 capture in captures/20261102): list 20261101_1334, NO BETS. 0 DK-listable (16 lines, 0 positive DK EV). Fliff check LaCombe U1.5 (4 of 7) and Sennecke U2.5 (5 of 7); Fliff not posted for the game, DK -150/-110 worse than shop-at -128/+105. ANA DFO ~27.5h (Oct 31 10:00 AM PT; 12h rule skips both), OTT fresh (6:26 AM PT). 0 injury vetoes, 2 demotions (Giroux/Greig O), 1 promotion (Zetterlund U), 1 mixed (Halliday), 0 slot vetoes. fliff_prices run on picks/20261101_1334_post.txt (1 credit, 3/10 today). Room post picks/20261101_1334_room.txt. No newly missed games; all of today's games now scored.
- 2026-11-01 2:00 PM window pass (fired 14:08, run 14:09 PT): NO_WINDOW_GAMES (NHL schedule rechecked, times unchanged). All of today's games already scored/posted (MIN@WSH 0908, UTA@PHI 0933, EDM@NYR 1137, OTT@ANA 1334); WPG@CAR already logged missed. Nothing posted, 0 Fliff credits (3/10 today).
- 2026-11-01 2:30 PM window pass (fired 14:36, run 14:37 PT): NO_WINDOW_GAMES (NHL schedule rechecked, times unchanged). All of today's games already scored/posted; WPG@CAR already logged missed. Nothing posted, 0 Fliff credits (3/10 today).

## 2026-11-02 — pre-noon PT exclusion removed (user approved Nov 1)
- window.py: pre_noon() now True only for puck drops on/before 2026-11-01 PT; games from Nov 2 on are eligible for window passes.
- game_starts.py: EXCLUDE_UNTIL=20261101; graders (grade_report.py, challenger/shadow_extra.py via mark_pre_noon) stop excluding pre-noon games after Nov 1. Historical Oct 17–Nov 1 exclusions unchanged.
- Backups: window.py.bak_20261102, game_starts.py.bak_20261102. Cross-check: Tester2.
- 2026-11-02 9:12 line-capture pass (fired 9:15, run 9:16 PT): graded 20261101 (80 lines, 0 graded picks, all OK), grade_report + grade_shadow OK; logs through Nov 1; gap check OK. predict.py 20261102: no lines to score (VGK@BOS, DET@FLA 4:00 PM, COL@CHI 5:00 PM, CGY@SJS 6:00 PM PT); no D file, so challenger skipped. Both lists empty; no sheet, 0 Fliff credits (0/10).
- 2026-11-02 12:00 PM window pass (fired 12:09, run 12:10 PT): NO_WINDOW_GAMES (NHL schedule rechecked, times unchanged). VGK@BOS and DET@FLA 4:00 PM ~230 min out, COL@CHI 5:00, CGY@SJS 6:00 later. No missed games. Nothing posted, 0 Fliff credits (0/10 today).
- 2026-11-02 12:30 PM window pass (fired 12:32, run 12:33 PT; VGK@BOS and DET@FLA 4:00 PM, 207 min out): no D snapshot existed, so ran the free capture.py, which saved captures/20261103/401892629_D.json (13 lines) and 401892630_D.json (15 lines). List 20261102_1232, NO BETS. 0 leans, 0 DK-listable. Fliff check Hertl U2.5 and Arvidsson U2.5 (4 of 7), Bennett O1.5 (3 of 7 after dropping 17.8-pt no-vig move), Faulk U1.5 (2 of 7, skip). Fliff not posted for either game; DK -170/-125/-190/-135 worse than shop-at -144/-108/-159/-116. All four DFO lineups fresh (BOS 7:38, VGK 8:27, FLA 12:07, DET 12:09 AM/PM PT). 0 injury vetoes, 3 demotions (Hertl/Lindholm/Lundell O), 2 promotions (Finnie/Brandsegg-Nygard U), 5 slot vetoes (O). fliff_prices run on picks/20261102_1232_post.txt (2 credits, 2/10 today). Room post picks/20261102_1232_room.txt. No missed games; COL@CHI 5:00 and CGY@SJS 6:00 PM later.
- 2026-11-02 1:30 PM window pass (fired 13:37, run 13:37 PT; COL@CHI 5:00 PM, 202 min out, D snapshot 210 min out from the 1:30 capture in captures/20261103): list 20261102_1337, NO BETS. 0 leans, 0 DK-listable (17 lines). Fliff check MacKinnon U3.5 and Frondell O1.5 (5 of 7), Schwartz U1.5 (3 of 7), Malinski U1.5 (2 of 7, skip). Fliff not posted for the game; DK +115/-165/-120 worse than shop-at +131/-139/-105. CHI DFO fresh (9:17 AM PT), COL fresh (12:16 PM PT). 0 injury vetoes, 4 demotions (Kane/Kadri/Schwartz/Nazar O), 3 promotions (Landeskog/Necas/Frondell U), 0 slot vetoes. fliff_prices run on picks/20261102_1337_post.txt (1 credit, 3/10 today). Room post picks/20261102_1337_room.txt. No missed games; CGY@SJS 6:00 PM later.
- 2026-11-02 2:00 PM window pass (fired 14:05, run 14:06 PT): NO_WINDOW_GAMES (NHL schedule rechecked, times unchanged). CGY@SJS 6:00 PM ~234 min out; VGK@BOS and DET@FLA (1232) and COL@CHI (1337) already posted. No missed games. Nothing posted, 0 Fliff credits (3/10 today).
- 2026-11-02 2:30 PM window pass (fired 14:37, run 14:38 PT; CGY@SJS 6:00 PM, 202 min out, D snapshot 210 min out from the 2:30 capture in captures/20261103): list 20261102_1438, NO BETS. 0 leans, 0 DK-listable (20 lines, best DK EV -5.8%). Fliff check Coronato U2.5 and Nemec U1.5 (3 of 7); Fliff -145/-140 and DK -135/-135 worse than shop-at -117/-116. CGY DFO fresh (10:51 AM PT), SJS fresh (10:52 AM PT). 0 injury vetoes, 4 demotions (Frost/Sharangovich/Graf/Stenberg O), 3 promotions (Toffoli/Strome/Misa U), 0 slot vetoes. fliff_prices run on picks/20261102_1438_post.txt (1 credit, 4/10 today). Room post picks/20261102_1438_room.txt. No missed games; all of today's games now scored.
- 2026-11-02 3:00 PM window pass (fired 15:10, run 15:10 PT): NO_WINDOW_GAMES (NHL schedule rechecked, times unchanged). All of today's games already scored/posted (VGK@BOS and DET@FLA 1232, COL@CHI 1337, CGY@SJS 1438). No missed games. Nothing posted, 0 Fliff credits (4/10 today).
- 2026-11-02 3:12 line-capture pass (fired 15:17, run 15:18 PT): gap check OK; logs through Nov 1; capture/predict/challenger: all 4 games kept unchanged (already posted 1232/1337/1438), no new lines. Both lists empty; no sheet, 0 Fliff credits (4/10 today). Room told.
- 2026-11-02 4:30 PM window pass (fired 16:39, run 16:39 PT): NO_WINDOW_GAMES (NHL schedule rechecked, times unchanged). All of today's games already scored/posted (VGK@BOS and DET@FLA 1232, COL@CHI 1337, CGY@SJS 1438). No missed games. Nothing posted, 0 Fliff credits (4/10 today).
- 2026-11-03 7:00 AM window pass (fired 7:07, run 7:08 PT): NO_WINDOW_GAMES (NHL schedule rechecked). Earliest games 4:00 PM PT (8 games, ~532 min out), EDM@NJD 4:30, CAR@NSH 5:00, ANA@VAN 6:00 later. No missed games. Nothing posted, 0 Fliff credits (0/10 today).
- 2026-11-03 7:30 AM window pass (fired 7:35, run 7:36 PT): NO_WINDOW_GAMES (NHL schedule rechecked, times unchanged). Earliest 8 games 4:00 PM PT (~504 min out), EDM@NJD 4:30, CAR@NSH 5:00, ANA@VAN 6:00 later. No missed games. Nothing posted, 0 Fliff credits (0/10 today).
- 2026-11-03 (Tester2): 12h stale-lineup skip now in code (approved rule, previously applied by hand in room posts). New lineup_age.py; shop_gate.py adds lineup_stale column and vetoes (shop_veto) any player whose live DailyFaceoff lineup updatedAt is >12h before gate/list build time, or has no/unparseable timestamp ("lineup timestamp missing" -> skip by choice). build_sheet.py skips those sides on BOTH the DK and Fliff lists with status_reason "lineup stale >12h (Nh old)" first; exactly 12h counts as fresh. Old GATE csvs without lineup_stale fall back to dfo_updated vs now, so re-running build_sheet on past lists will mark them stale. Frozen model, features, picks csv and --rescore untouched. Test: tests/test_stale_lineup.py.
