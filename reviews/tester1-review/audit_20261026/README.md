# Tester1 Oct 26 2026 audit: NHL posted lists and final cards vs box scores
Script: audit_nhl_lists.py (read-only over /workspace/nhl-sog; run with /workspace/nhl-sog/.venv/bin/python).
Outputs: sides.csv (one row per posted side), summary.csv, run_output.txt.
- Sides: every 'Fliff check' line in picks/<date>[_HHMM]_post.txt, Oct 17-25 (DK list was empty on every pass). 20261017_post.txt is the Oct 17 morning list (list id 20261017_AM).
- Final cards: every posted side also appears on its room card (74 of 74). Oct 25 4:01 PM DeBrusk U2.5 was dropped before posting (2-of-7 rule) and is not counted.
- Shots: fresh from api-web.nhle.com /v1/gamecenter/<id>/boxscore; every gameId confirmed in /v1/score/<date>. All games final.
- Units: flat 1u at the posted shop-at price (worst acceptable Fliff price, hypothetical) and at the DK price on the list.
- CLV: side no-vig points, list snapshot to CLOSE.json, same line only. Excluded: capture_gap, early_close, games with no close-window lines, and lines that moved.
## Reconciliation with the earlier audit (42 sides, 25-17, +2.55u through Oct 24; post-floor 15 sides 7-8, -2.80u)
- Oct 18-24 scope reproduces exactly: 42 sides, 25-17, +2.55u at DK. All 68 previously graded shot counts match the fresh box scores. No changes.
- Added Oct 17 (26 sides, 6 lists): the earlier audit started Oct 18; list_track's glob also skips 20261017_post.txt.
- Added Oct 25 (6 sides): not graded before (no graded/20261025.csv yet).
- Post-floor moves to 21 sides, 11-10, -1.84u only because Oct 25 (4-2, +0.96u) is added.

## v2 (Oct 26 ~9:15 AM PT): three records (records_v2.py -> sides_v2.csv, summary_v2.csv, run_output_v2.txt)
v1's on_card=True for all 74 was wrong (loose name match; Oct 25 room posts list Fliff-check sides that were then skipped).
Final-card membership: Oct 25 from picks/finalcall_done markers + room NO BETS cards (all 6 skipped; Schenn's marker says conditional "Fliff +109 or better", Fliff stayed -110, treated as skipped).
Oct 24: final-call text not on disk; bets.csv used as proxy -> Wilson U2.5, Samuelsson, Raddysh, Coronato, Dunn skipped.
Oct 17-20: no final-call text on disk; posted = card (unverified).
Tester2 variant (only Oct 25 moved): 68 sides 37-31; post-floor 15 sides 7-8, -2.80u DK = the earlier baseline exactly.
