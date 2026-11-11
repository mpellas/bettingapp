# CFB game-line evidence (shadow/context only, UNTESTED; added 2026-10-17)
`python3 evidence/cfb_evidence.py --date YYYYMMDD` (PT game date; default today). 0 Odds API credits.
Reads the latest pre-game DK capture per game from `lines/snapshots.csv`, refits ratings from ESPN final scores
(cached in `evidence/cache/`, current season refreshed when older than 3 h), and writes
`evidence/out/cfb_evidence_<date>_<HHMM>.csv/.txt`: per side `sig_*` (+/-/0), `why_*`, `agrees_n` of K
(spreads K=4: power, form, home, move; totals K=3: power_total, form_total, move_total) and a one-line summary.
Rules and bands: docstring of `cfb_evidence.py`.

**Untested.** No historical CFB lines exist here (ESPN drops odds after the final), so nothing has been checked
against a market. The only check is market-free (`check_ratings.py`, `check_ratings.out`): walk-forward 2026
weeks 3-7, 239 FBS-vs-FBS games: margin MAE 12.58 vs 15.90 for home-field-only (-3.3 [-4.5, -2.2]); total MAE
12.90 vs 13.31 for a flat league average (-0.4 [-1.2, +0.4], i.e. the points model adds ~nothing on totals).
Typical closing-spread MAE in CFB is in the same 12-13 range, so expect the 'power' signal to mostly echo the line.
Home field is pulled toward last season's full-season estimate (3.9 pts) because early-season non-conference home
games inflate it (5.0 unpulled); this choice was made after seeing that number, disclosed here.
`lines/grade_lines.py` grades sides going forward; after ~150+ graded games, check hit vs no-vig and CLV by agrees_n.
