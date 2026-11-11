# Routines

Scheduled Grok Bot jobs that drive captures, window passes, final calls, and
graders. **Time zone: America/Los_Angeles (PT).** These are not crontab entries
on the box.

## Source limitation (please read)

On 2026-11-11 the box had:

- `/home/box/sand-data/agents/*/automations/` — empty
- `/home/box/sand-data/workflows/` — empty

Saved UpdateRoutine prompt text and official cron strings were therefore **not
available to copy**. This folder is an inventory of what could be verified from:

1. A Grok Bot usage report pulled 2026-11-11, covering 2026-10-12 through 2026-11-11 (UTC), which names each routine, whether it is paused, and about how many times it ran per week.
2. The binding NFL prereg (`nfl-props/prereg/prereg_2026_wk5-18_PUBLISHED_20261005.yaml`, `capture_schedule` block).
3. `nhl-sog/NOTES.md`, `nfl-props/NOTES.md`, `nhl-sog/logs/wake_log.txt`, and process memory/profile notes (for example the 15-minute final-call cadence and the 9:12 / 3:12 PM line-capture slots).

Where a cron expression is given below, it is a **reconstruction** from those sources, labeled as such — not an export of the live scheduler. Prompt bodies are not reproduced because they were not on disk.

Unrelated paused 90Strong / workout-app routines are omitted (see [EXCLUDED.md](../EXCLUDED.md)).

## Schedule table

"Enabled" vs "paused" is from the 2026-11-11 usage report. Run counts are that report's "about N runs a week" figures over the last 30 days (they mix game days and off days).

| Display name (usage report) | Known slug | Reconstructed schedule (America/Los_Angeles) | State | What it does (verified) |
|---|---|---|---|---|
| Betting: final call after each list's hold | `betting-final-call-after-each-list-s-hold` | Every 15 minutes 7:00 AM-7:45 PM daily. Reconstruction: `0,15,30,45 7-19 * * *` (includes 19:45). ~364 runs/week matches 52 fires/day x 7. An earlier note also mentioned daily ~9:35 AM and 3:35 PM / Sunday ~8:00 AM before it was changed to the 15-minute check. | enabled | After a pick list is at least ~12 minutes old (10-minute hold plus slack) and has no final-call marker, draft a FINAL CALL card (including `FINAL CALL: NO BETS`). Posts go to the Betting App room and a copy to the owner's DM. Writes `nhl-sog/card_decisions.csv` and markers under `picks/finalcall_done`. Stays silent when nothing is new. |
| NHL SOG: daily window passes | `nhl-sog-oct-26-window-passes` | About every 30 minutes 7:00 AM-4:30 PM daily. Reconstruction: `0,30 7-16 * * *` (20 fires/day = 140/week). NOTES show fires from 7:00 AM through 4:30 PM on game days. | enabled | For games in the D window (150-210 min, or 210-240 if a D snapshot already exists): capture if needed, `predict.py --window-only`, challenger, shop gate, sheet, Fliff check (no more than 10 credits/day), write `picks/<date>_<hhmm>_room.txt`. Log misses when a game is already inside 150 minutes and was never scored. Catch-up / `wake_log` start-end lines were added 2026-10-28. Quiet when `NO_WINDOW_GAMES`. |
| NHL SOG: line captures | (slug not confirmed; usage name as shown) | About twice daily, observed in NOTES at **9:12 AM** and **3:12 PM** PT. Reconstruction: `12 9,15 * * *`. ~14 runs/week. | enabled | Grade prior day if due, refresh game logs / gap check, `capture` + `predict` for unpublished games, produce official lists when new D lines exist. |
| NHL SOG: hourly capture wake | (slug not confirmed) | Usage: ~42 runs/week (does not match a simple 24x7 hourly cron; likely limited to game-day / evening hours). `wake_log.txt` shows roughly hourly starts on game afternoons and evenings (about 2:40-7:45 PM PT and some late-morning checks). Official cron not verified. | enabled | Confirm the capture loop/supervisor is alive; ensure in-window D and C files exist; run `close.py` when C lands; alert the Betting App room only on **new** missed D/C windows. |
| NHL SOG: paper tests (late lineup re-pull + position-defense challenger) | (slug not confirmed) | Usage ~140 runs/week, same order of magnitude as the window-pass cadence. Exact cron not verified. Code/output live in `nhl-sog-papertests/`. | enabled | Paper tests only: late lineup re-pull and a position-defense challenger, not the official frozen list. |
| NHL SOG: nightly shadow trackers (no-promo-under + 50% shrink + edge8 price band) | (slug not confirmed) | Usage ~7 runs/week (about daily). Notes show a run near **11:30-11:40 PM PT**. Reconstruction tentatively `30 23 * * *` (minute not confirmed). | enabled | Grade shadow variants for the day's passes. A Betting App note is sent only when a tracker hits a pre-set side count (journals say 100 graded sides); otherwise silent. |
| NHL SOG: game-night close-capture safety net | (slug not confirmed) | Usage ~21 runs/week. Journals show multiple evening slots on game nights (examples: 6:15, 6:35, 6:50 PM PT on 2026-11-10). Exact cron not verified. | enabled | Re-check tonight's games for in-window C / CLOSE; stay silent when nothing is missing; do not spend Fliff credits. |
| nhl-fliff-second-pull | `nhl-fliff-second-pull` | Usage ~336 runs/week (= 48/day). Compatible with every 30 minutes around the clock, or every 15 minutes over 12 hours; **exact cron not verified**. Approved 2026-11-03. | enabled | Second Fliff price pull about 1 hour before puck drop for sides marked not offered (1 credit per game, inside the 10-credit daily cap). |
| NFL props: Sunday D and C captures | (slug not confirmed) | Usage ~22 runs/week. Prereg `capture_schedule`: Sundays ~6:55 AM, 10:00 AM, 10:20 AM, 2:15 PM PT (D) and before 10:00 AM / 1:05-1:25 PM / 5:20 PM PT kickoffs (C). | enabled | Pad official D (~3 h pre-kick) and C (last 30 min) ESPN snapshots. Complements `snapshot_loop.sh` on the box. |
| NFL props: Mon/Thu night game captures | (slug not confirmed) | Usage ~14 runs/week. Prereg: Mon/Thu 2:10 PM PT (D). | enabled | Night-game D capture and pregame file (example official file 2026-11-09 2:03 PM PT in `nfl-props/NOTES.md`). |
| NFL props: Mon/Thu in-window close | (slug not confirmed) | Usage ~4 runs/week. Prereg: Mon/Thu 4:47 / 4:58 / 5:09 PM PT (C). | enabled | In-window C captures for MNF/TNF. Alerts only if C comes back empty. |
| NFL props: Sunday night close and summary | (slug not confirmed) | Usage ~9 runs/week. Exact cron not verified. | enabled | Sunday night close capture and summary for the paper track. |
| NFL Sunday price-shop passes | `nfl-sunday-price-shop-passes` | Profile note (2026-11-01): every Sunday at **8:50 and 11:50 AM PT**. Reconstruction: `50 8,11 * * 0`. Not a named line in the usage report (may be folded into "other" or into Sunday D/C). | enabled (per 2026-11-01 profile; not separately listed in the 2026-11-11 usage table) | Post NFL prop price-shop lists with FINAL CALL cards. Requires a real market edge (2%) and model backing; NO BETS cards are expected often. |
| CFB: Saturday price check + free line capture | (slug not confirmed) | Saturday cadence; exact cron not verified. | **paused** | CFB Fliff/DK price check and free line capture. On hold. |
| Betting: Saturday Oct 31 weekly review | (one-off / dated name) | Dated 2026-10-31. | **paused** | Weekly review job for that Saturday. |
| NHL SOG: Oct 25 window passes | (dated name) | Dated 2026-10-25; superseded in practice by `nhl-sog-oct-26-window-passes`. | **paused** | Older window-pass routine. |
| NFL: Sunday Oct 18 price-shop pull | (dated name) | Dated 2026-10-18. | **paused** | Older Sunday price-shop pull (see `analysis/nfl_wk6_oct18_priceshop.xlsx`). |

The usage report also has a **Deleted routines** bucket (about 2% of Grok Bot usage in the window) whose names are not listed here, and an **Other routines** bucket (about 1%).

## Box loops the routines expect to be running

These *are* in the repo and can be inspected independently of Grok Bot:

- `nhl-sog/ops/capture_loop.sh`, `capture_supervisor.sh`, `ensure_capture.sh`, `close_watch.py`
- `nfl-props/scripts/snapshot_loop.sh`, `snapshot_supervisor.sh`, `ops/close_window_capture.sh`, `ops/ensure_capture.sh`

NHL wake starts and ends are appended to `nhl-sog/logs/wake_log.txt`.
