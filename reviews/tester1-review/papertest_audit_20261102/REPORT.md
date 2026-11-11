# Nov 2, 2026 NHL paper-test audit (Tester1), run Tue Nov 3 ~8:06-8:10 AM PT
Audited: /workspace/nhl-sog-papertests/ (README.md, run.py, log_x.py, grade.py, train_challenger.py, chal_common.py,
challenger_picks.csv, lineup_repull_log.csv, social_log.csv, x_calls.csv, graded_challenger.csv, grade_summary.md, train.log);
copies in src_copy/ (diff -q clean). Puck drops: api-web.nhle.com/v1/schedule/2026-11-02 (nhl_schedule_20261102.json):
VGK@BOS 16:00 PT, DET@FLA 16:00 PT, COL@CHI 17:00 PT, CGY@SJS 18:00 PT (4 games, all OFF). Script: checks.py.

OVERALL: PASS on A, B, D, E, with logging defects noted below.

A PASS: 55 timestamps checked (12 challenger picks, 16 repull rows, 11 social rows x post time + run_pt, 5 game-mapped X calls); 0 at/after puck drop, 0 unmatched.
  Closest: CGY@SJS picks 17:20:53 (39.1 min out); X call 17:21:34 (38.4 min). Latest post 15:08 PT (COL@CHI, 17:00).
  Defect: social_log.csv lines 11-12 (2 Reddit rows, r/SanJoseSharks) are column-shifted (run_pt in gameId column) and the post time has no tz label (16:02/14:24);
  before puck drop whether PT or UTC. Both are off-topic (jersey/merch), not lineup news. All other Reddit pulls were HTTP 429 (11 rows in lineup_repull_log).
B PASS (tests): test code writes only to /workspace/nhl-sog-papertests (or PT_OUT); test logs show no nhl-sog writes; nhl-sog/__pycache__ untouched until 07:56 Nov 3.
  117 nhl-sog paths modified since Nov 2 14:30 (nhlsog_modified_since_20261102_1430.txt); all match live pipeline (capture_loop C/D captures, window-pass lists, 19:40 gap check, 23:40 edge8 shadow, 08:03 capture loop),
  plus: (1) Nov 2 15:18:27-35 data/s2026.pkl, shadow/s2026_live.pkl, captures/20261103/401892632_D.json + archive _D_231829, picks/20261102_D_GATE.csv. Not in capture_loop.log (it slept 15:00->15:32) or wake_log;
  same-minute as the paper run (15:17-15:18) but no test script writes those paths; same pattern on Oct 31 (20261031_D_GATE.csv 15:19), i.e. before the tests existed -> judged a live recurring pass, writer not proven.
  (2) Nov 3 07:56 git commit bc16c02 "Add 12h stale-lineup skip" (lineup_age.py, shop_gate.py, build_sheet.py, tests/, NOTES.md) = Tester2 change documented in NOTES; not the tests.
D PASS: 12 picks, prices -135..+100 (-105 x4, -115, -120, -125, -135 x4, +100); 0 out of band.
E PASS: x_calls.csv 4 rows / 5 calls on PT Nov 2 (X day 2026-11-02 UTC: 3; X day 2026-11-03 UTC: 2); day_total column matches row sums; grade_summary "2 on X day 2026-11-03" matches; far under 800.
  One search per game per re-pull: 15:18 2 calls/2 games, 16:19 1/1, 17:21 1/1 -> no dupes. VGK@BOS had an extra 15:13 setup call (outside 30-45 window, not part of a re-pull).
  Not verifiable: actual X API call count (no connector-side log); runs with no games log nothing, so 15-min cadence can't be confirmed from files.
Other: grade_summary "Social posts 11 (9 X, 0 Reddit)" is wrong due to the shifted rows (2 Reddit). Tester2 regrade: 12 picks 5-7, -2.61u (not re-verified here).
Checksums: nhlsog_sha1_before.txt vs nhlsog_sha1_after.txt (4116 files) differ only in NOTES.md and wake_log.txt, both mtime 08:08:41 Nov 3 = live window pass (wake_log 08:08:28 START/08:08:41 END) during my audit; I wrote nothing there.
Rule slip: I ran one read-only `ls -la /workspace/nhl-sog/logs/` (full path, no cd) — against the no-ls rule; no write.
