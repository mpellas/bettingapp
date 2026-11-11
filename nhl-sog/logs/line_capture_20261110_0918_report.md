# NHL SOG morning line-capture report — Tuesday Nov 10, 2026 (9:12 AM PT pass)

Run time: ~9:18–9:21 AM PT (America/Los_Angeles, PST today).
Work dir: `/workspace/nhl-sog`
Paper only: no bets placed, no Betting App post, no agent messages, model left frozen at `c3ab760178` (`models/CURRENT`).
No `--rescore` was used. No custom Fliff credit cap was passed. Odds API credits spent this pass: 0.

## Already posted today (exclude from official lists)

Checked today's window-pass notes in `NOTES.md`, `wake_log.txt`, `picks/`, `sheets/`, and nearby logs.

- 2026-11-10 7:00 AM window pass (run 7:03 PT): NO_WINDOW_GAMES (7 games, earliest 4:00 PM PT ~537 min out). Nothing posted.
- 2026-11-10 7:30 AM window pass (run 07:33 PT): NO_WINDOW_GAMES (earliest 4:00 PM PT ~500 min out). Nothing posted.
- 2026-11-10 8:00 AM window pass (run 08:09 PT): NO_WINDOW_GAMES (earliest 4:00 PM PT ~470 min out). Nothing posted.
- 2026-11-10 8:30 AM window pass (run 08:39 PT): NO_WINDOW_GAMES (earliest 4:00 PM PT ~440 min out). Nothing posted.
- 2026-11-10 9:00/9:01 AM window pass (run 09:01 PT): NO_WINDOW_GAMES (earliest 4:00 PM PT ~420 min out). Nothing posted.

No `picks/20261110*`, no `sheets/20261110*`, no GATE/post/room files, no Betting App notes for scored sides today.

**Games already posted by an earlier pass today: none.** Do not exclude any of today's games from official lists for that reason. Official lists are empty because there are no D-window lines to score yet, not because of earlier posts.

## Today's slate (NHL api-web + ESPN scoreboard)

7 games, first puck drop 4:00 PM PT (~399 min out at capture time):

1. Colorado Avalanche at Toronto Maple Leafs — 4:00 PM PT (NHL 2026020286 / ESPN 401892683)
2. Minnesota Wild at Montreal Canadiens — 4:00 PM PT (NHL 2026020287 / ESPN 401892684)
3. Washington Capitals at Ottawa Senators — 4:00 PM PT (NHL 2026020288 / ESPN 401892685)
4. New Jersey Devils at Winnipeg Jets — 4:00 PM PT (NHL 2026020291 / ESPN 401892688)
5. Florida Panthers at Columbus Blue Jackets — 4:30 PM PT (NHL 2026020289 / ESPN 401892686)
6. Detroit Red Wings at St. Louis Blues — 5:00 PM PT (NHL 2026020290 / ESPN 401892687)
7. Nashville Predators at Los Angeles Kings — 7:00 PM PT (NHL 2026020292 / ESPN 401892689)

D snapshots are saved only 150–210 minutes before puck drop, so the first D window for the 4:00 PM PT games opens around 12:30 PM PT. No `*_D.json` files exist yet for any of today's events (the `captures/20261110/` D/C/CLOSE files are last night's NYR@EDM, PHI@VAN, NYI@SJS, stored by UTC date).

## STEP 0 — grading (this IS the 9:12 AM run)

**Result: succeeded.** Parent should mention grading in the room post only if it failed (it did not).

- `python3 grade.py 20261109` — exit 0.
  Output: `20261109: 48 lines, 0 graded picks; hits 0/0; units 0.00; mean zCLV nan; voids {'OK': 48}`
  All 48 rows have `status=OK` and filled `actual` SOG (e.g. Zach Hyman 1, Mattias Ekholm 2, J.T. Miller 3). `pick` is NaN on every row (D-file lists were built from the sheet, not the `pick` column), so grade.py's pick-hit/units line is 0 — that is expected, not a failure. Wrote `graded/20261109.csv`.
- Pending-day scan: no earlier graded file has `PENDING_no_box` (or any PENDING status). Existing graded statuses are OK / VOID_noC / VOID_dnp / VOID_pulled_before_close only. Did **not** re-run `grade.py` for 20261012 or 20261013. Nov 6–8 have no `picks/*_D.csv` to grade.
- `python3 grade_report.py` — exit 0. Primary score (z-CLV):
  - **all: 1845 OK lines with C, 116 games, mean z-CLV +0.0081** [+0.0046, +0.0115], verdict **positive CLV**. Lean hit 52.7% vs 50.8% no-vig fair (+1.9 ± 1.2).
  - 20261109: 48 lines, 3 games, mean z-CLV +0.0062 [−0.0013, +0.0161], too few games for a verdict; lean hit 43.8% vs 51.2% (−7.5 ± 7.2).
  - Model-only paper track (champion c3ab760178, edge ≥1 pt, flat 1u at captured DK price): **all 859-768, −54.44u**, ROI −3.3% (1627 bets / 117 g), z-CLV +0.0093. Nov 9: 19-23, −6.04u (42 bets / 3 g).
  - Fliff list as posted, all: 27-22, −1.77u (49 graded). Nov 9: 0-1, −1.00u.
- `python3 challenger/grade_shadow.py` — exit 0. Wrote `challenger/SHADOW_REPORT.md`.
  - 1428 OK lines with a challenger prediction (89 games, 15 slates).
  - Champion lean z-CLV +0.0091; challenger +0.0099.
  - Primary 1 (log-loss, challenger − champion): −0.0008 [−0.0029, +0.0012] over 89 games (pass needs upper bound < 0).
  - Primary 2 (lean z-CLV, challenger − champion): +0.0008 [−0.0009, +0.0027] (pass needs lower bound > 0).

## STEP 1 — capture and predict

- `ops/ensure_capture.sh` — exit 0. **Gap check OK** (did **not** print `GAP CHECK FAILED`).
  - Game logs were stale/missing → ran `fetch.py` (OK).
  - Printed: `game logs through 2026-11-09`
  - Supervisor pid 7731 and loop pid 456768 alive.
  - Next puck drop ~406 min at ensure time. Last loop (09:14 PT): NEXT_SLEEP 600 (406 min); Nov 9 CLOSE OK for NYR@EDM, PHI@VAN, NYI@SJS; close watch 3 started games, 0 missing close.
- Fetch freshness (verified on `data/s2026.pkl` after that refresh): **newest game date 2026-11-09** (yesterday). 10259 rows; last dates 2026-11-05 .. 2026-11-09. Not stale.
- `python3 shadow/gamelog.py` — exit 0. `10259 rows, 2026-09-29 .. 2026-11-09 -> /workspace/nhl-sog/shadow/s2026_live.pkl`
- `python3 capture.py` — exit 0. `NEXT_SLEEP 600 (next puck drop in 399 min)`
- `python3 predict.py 20261110` (no `--rescore`) — exit 0. Printed **`no lines to score`**. No `picks/20261110_D.csv` was written (there are no D-window captures for today's 7 games yet).
- `.venv/bin/python challenger/predict_challenger.py 20261110` — exit 1, `FileNotFoundError: picks/20261110_D.csv`. **Challenger skipped; no backfill** because there is no saved D file to score from (same as the Nov 2 and Nov 9 9:12 AM morning passes). No `challenger/shadow/20261110*` file exists.

## STEP 2 — shop gate

Not run: required input `picks/20261110_D.csv` does not exist. Veto counts are 0 because no sides were scored.

- Lineup vetoes skipped: 0
- Stale-lineup vetoes skipped: 0
- Role vetoes skipped: 0

## STEP 3 — DraftKings official list

**Empty.** No sides scored, so none meet `dk_listable_over` / `dk_listable_under` (or any other DK list gates).

## STEP 4 — Fliff check official list

**Empty.** No picks CSV, so `recent_form.py` was not run and no sides were ranked.

## STEP 5 — spreadsheet

Not built. `build_sheet.py` needs a picks CSV and a GATE CSV; neither exists.

The Nov 9 override (still build the sheet when both official lists are empty, so `evidence_extra` columns exist for the majority list) applies when sides were scored and lists came back empty. This pass scored **zero** sides, so there is nothing to build rows from. Same outcome as the Nov 9 9:12 AM pass.

- Spreadsheet path: none
- Puck-drop column: N/A (no spreadsheet; cannot be a single time on every row)
- `picks/20261110_post.txt`: does not exist (nothing to quote)

## STEP 5b — Fliff prices

**Skipped.** Both official lists are empty (Nov 9 empty-list override: skip the Fliff pull). Also no xlsx to pass in. 0 Odds API credits spent this pass. No `fliff_credits_20261110.csv`. Cap remains the default 10/day.

Fliff credits line: 0 this pass (both official lists empty, so no Fliff pull); 0 of 10 used today.

## Official pick writeups

DraftKings list: none.

Fliff check: none.

No same-game correlated sides (no picks).

## Majority of tests list

**List unavailable** — no sides were scored this pass (no DraftKings D-window SOG captures yet for today's 7 games), so there is no scored evidence to read. **New tests unavailable** (no sheet, so no `agrees_all_n` / `tests_all_n` / `evidence_all_summary` / `sig_x_*` columns).

Do not write “none qualified.” Scoring was blocked by missing D-window lines, not by a completed score that found zero majority sides.

When later window / 3:12 PM passes score today's games, post only sides for games that an earlier pass today hasn't already posted. As of this 9:12 AM pass, no game has been posted.

## Files written this pass

Written/updated:
- `graded/20261109.csv` (new; 48 lines, all OK)
- `graded/REPORT.md` (via `grade_report.py`)
- `challenger/SHADOW_REPORT.md` (via `grade_shadow.py`)
- `data/s2026.pkl` (refreshed by `fetch.py` through 2026-11-09)
- `shadow/s2026_live.pkl` (via `shadow/gamelog.py`)

Not written (no D-window lines):
- `picks/20261110_D.csv`
- `picks/20261110_D_GATE.csv`
- `picks/20261110_post.txt`
- `sheets/20261110_*_picks.xlsx`
- `challenger/shadow/20261110_D_3386583f18.csv`

## Flags summary

- GAP CHECK FAILED: no (gap check OK)
- Stale game logs: no (fresh through 2026-11-09)
- Grading failure: no
- Missing new-test columns: N/A / new tests unavailable (no sheet)
- Single puck-drop time on every row: N/A (no spreadsheet)
- Already-posted games: none
- Challenger file missing: yes, and could not backfill (no saved D file)
- Model still frozen at c3ab760178: yes

## Suggested room-post skeleton (parent writes/posts; this pass did not post)

Hold about 10 minutes for the testers' cross-check before betting.

Both official lists are empty. NHL shots on goal, Tue Nov 10 9:12 AM PT line-capture pass (run ~9:18–9:21 AM PT): DraftKings has no D-window shots-on-goal captures yet for today's 7 games — Colorado Avalanche at Toronto Maple Leafs (4:00 PM PT), Minnesota Wild at Montreal Canadiens (4:00 PM PT), Washington Capitals at Ottawa Senators (4:00 PM PT), New Jersey Devils at Winnipeg Jets (4:00 PM PT), Florida Panthers at Columbus Blue Jackets (4:30 PM PT), Detroit Red Wings at St. Louis Blues (5:00 PM PT), and Nashville Predators at Los Angeles Kings (7:00 PM PT). First puck drop is about 6.5 hours out; D snapshots are saved 150–210 minutes before puck drop. No earlier pass today scored them. Paper only. Later window passes and the 3:12 PM PT line-capture pass will pick them up when lines land in the D window.

DraftKings list: none.

Fliff check: none.
Fliff credits: 0 this pass (both official lists empty, so no Fliff pull); 0 of 10 used today.

Vetoes: 0 lineup, 0 stale-lineup, 0 role (no sides were scored, so no vetoes were applied).
No spreadsheet was built (no picks or GATE file; no D-window lines to score), so there is no path and the Excel/Google Sheets color note does not apply.

Majority of tests: list unavailable — no sides were scored this pass (no DraftKings D-window SOG captures yet), so there is no scored evidence to read. New tests unavailable.
