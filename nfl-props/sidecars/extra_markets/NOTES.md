# Extra NFL markets (data only, paper)

`grade_extra_nfl.py` grades extra DraftKings-via-ESPN player props (targets only, no prices) and, from 2026-11-22, the game point spread. Outputs go to `graded/nfl_<market>.csv` and `graded/nfl_summary.csv`. This work never changes the frozen yards track (`track.py`, the published prereg).

## `nfl_spread.csv` grades both sides — not a model result

`nfl_spread.csv` grades **both sides of every game** (home and away) against the same final margin.

Because both sides are always written:

- Cover and loss counts are always symmetric. They add up to the number of graded sides, and they can differ only when some rows are still pending or ungraded (not because one side was selected).
- The units total is just the juice on a two-sided book. A 96-96-2 style record with a negative unit total is the vigorish, not an edge.

This file is **raw ATS data, not a model result**. It does not tell us anything about a spread model. A real test needs a model that picks **one side** per game; we do not have one yet. Do not read the two-sided record or unit total as performance.

Player-prop CSVs (`nfl_receptions.csv`, `nfl_pass_att.csv`, kicker points, etc.) are separate: those are over/under at the line, with no prices and no units.
