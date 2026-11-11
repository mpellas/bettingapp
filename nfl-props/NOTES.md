# nfl-props NOTES

## 2026-10-24: single-week summaries labeled INTERIM (labeling only; prereg untouched)
- Rule: a single week never gets PASS/FAIL. PASS/FAIL comes only from the pooled `track final --weeks 5-18`.
- src/nflprops/track.py is hash-pinned in prereg_2026_wk5-18_PUBLISHED_20261005.yaml (line 19), so it is NOT edited.
  Instead scripts/label_interim.py post-processes data/track/<S>_wkWW.summary.json (label -> INTERIM, raw label kept in
  decision_this_week_only.label_raw_week_only). Scores unchanged (wk6 re-run: only scored_at/label_note differ).
- Run weeks with scripts/track_week.sh --season 2026 --week N (track week + relabel), including the week 7 run.
- Test: tests/test_label_interim.py.

## 2026-10-24: track.py hash check + scope sidecar
- No mismatch: the prereg's file_sha1 is plain sha1 of file bytes (sha1sum = 0b5414dc...); 9542b1a2... is the git blob id
  (sha1 of "blob <len>\0"+bytes) of the same bytes. track.py has no commits after de029ac and is clean vs HEAD.
- Re-scored wk5 and wk6 with track.py extracted from de029ac in /tmp/pinned_track: summaries, parquets, voids identical to
  the repo outputs after re-scoring in order wk5 -> wk6 (the stacker for wk6 fits on settled wk5, so order matters).
  wk5 committed output was stale (Oct 16: 229 scored, 24 pending); now 253 scored, 0 pending, 27 void.
- scripts/add_scope_inputs.py (run by scripts/track_week.sh): data/track/<S>_wkWW_scope.csv with public_proj,
  is_proj_starter, position, scope_reason per line, from each line's pred_file. Backfilled wk5, wk6.
- wk6 out of scope 105 (direct): projection < 20 yds 73 (rec 56, rush 17); QB rushing 28; QB not projected starter 3;
  1 unexplained (Omar Cooper Jr. rec 16.5, public_proj 26.3 in its pred file yet out of scope) - to check.
- Omar Cooper Jr. (wk6 rec 16.5, public_proj 26.3): out of scope by markets.universe_mask's p_n_prior >= 2 (only wk1 played before wk6). track.py reads in_model_universe from the pred file, so it was right; the sidecar lacked the prior-games rule. Fixed: n_prior_games column + reason (wk6: 4 lines). No in-scope line has < 2 prior games.

- 2026-11-08 narrow recovery requested by user (no major audit): refreshed 2026 raw player stats, snap counts, schedules and player mapping via existing data loader; data_version 4dc36557. All saved model-led shadow files already have graded markers. Sunday and prime-time reporting now require a separate 4+/7 majority list using full current-pass evidence, with team/game/side/line and exclusion reason, even with NO BETS. No retroactive picks or closing prices. Current-week pregame prediction freeze remains a separate forward-input blocker; no week8 substitution.

- 2026-11-08 5:30 PM PT narrow backfill complete: ran existing scripts/track_week.sh for week8 using saved pregame files and actual results; 271 lines scored, 21 void, 0 pending. Retained original scope exclusions and INTERIM single-week labeling. No new picks, no major audit, no model or gate edits.

## 2026-11-09 new evidence tests (Yinzer; display only; cross-check: Tester1)
sidecars/evidence/nfl_evidence.py: x_hit (hit rate at line, this season >=4 g AND last 10, vs fair_prob; band 5 pts; no price when price_assumed) and
x_books (other books in the same input: median line diff >= max(1.5, 2%) or consensus no-vig vs this price > 2 pts). add_evidence.py writes sig_x_*, why_x_*,
agrees_all_n, tests_all_n, evidence_all_summary; agrees_n unchanged. Backups *.bak_20261109. Tester2 adds plays/game and rest via EXTRA_SIGS + add_evidence xs dict.
Found: builder all_sides CSVs have no player_id/game_id, so add_evidence scores 0 rows on them (tested nov02 1613); live analysis_*_live_*.csv works.

## Nov 9, 2026 fixes to display-only extra tests (Yinzer)
- x_books: de-vigs the same book's two sides at the same line before comparing to fair_prob (+/-2 pts); line-lean when median lines differ by >= max(1.5, 2%); 0 with no two-sided price.
- add_evidence: maps missing player_id/game_id from nflverse names+team and games.csv; prints "MAJORITY LIST UNAVAILABLE" when 0 rows score. Week-8 Nov 2 all_sides test: 371 of 419 rows scored.
- Tester2's x_pace and x_rest cross-checked by Yinzer (rebuilt from pbp/games.csv; matched). Data flag: NYJ@CHI week 4 shows only 32 Jets offensive plays; Tester2 confirmed it is real (all four quarters, matches player stats), and it lowers CHI plays-faced by about 4.
- Denominator: 7 existing tests + hit, books, pace, rest = 11.

## 2026-11-09 week-9 pregame file (Yinzer)
Root cause of the missing week-9 predictions: a capture outage, then the pregame step never ran. Snapshots stopped after Thu Nov 5 6:59 PM PT; there were none Fri or Sat, and Sunday captures did not resume until 3:56 PM PT, after every Sunday D window and the morning price-shop. Thu close (JAX@BAL) and almost all Sunday closes were missed (only TB@CHI has C). D lines were rebuilt Sunday 10:00 PM PT (243 then, later 246) but `python -m nflprops.pregame --season 2026 --week 9` was not run, so the Sun 4:14 PM PT pass failed on a missing week-9 pregame CSV (week 8 was not substituted).

Today (no model/track edits, no --rescore, no Odds API or Fliff credits, no retroactive picks): backed up snap_2026_wk9_{D,C,pulled}.csv, pred_log.jsonl, and the 2026 nflverse cache (*.bak_y_20261109); refreshed nflverse (free). I ran the normal pregame command at 12:37 PM PT as a safety file: data/predictions/2026_wk09/pregame_20261109T203732Z.csv. The Mon/Thu night-game capture routine later wrote the official file at 2:03 PM PT: pregame_20261109T220323Z.csv (244 predictions, data_cutoff 2026-11-05, BUF@MIN D captured 2:02:52 PM PT). I did not generate a third file. add_evidence --dlines --week 9 --no-net reads that official file and scored 488 of 492 sides. The 4:10 PM PT prime-time pass should now find data/predictions/2026_wk09/ and use the newest CSV.
