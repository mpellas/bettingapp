# betting-app

Paper-tracked sports-prop research: NHL shots-on-goal, NFL yards props, and
college-football work that is currently on hold, plus a log of real bets the
owner actually placed. This repository is a public snapshot of the pipelines,
frozen models, captures, paper tracks, review folders, and what could be
documented about the scheduled processes, staged on 2026-11-11
(America/Los_Angeles) from the working box.

**This is a paper-tracking and review corpus. Nothing here places a bet.**

The GitHub remote this tree is meant for is <https://github.com/mpellas/bettingapp>
(public, branch `main`). This copy was staged locally only.

## What this is

- **NHL shots-on-goal (`nhl-sog/`)** — a frozen champion model and a set of
  shadow / challenger / evidence tools. Lists are produced on a *window-pass*
  schedule around puck drop, shopped against DraftKings and (credit-capped)
  Fliff, and posted to a "Betting App" room. A 4-of-7 evidence "majority list"
  is informational only.
- **NFL yards props (`nfl-props/`)** — a pre-registered 2026 weeks 5–18 paper
  track of pass / rush / receiving yards. Decision snapshot **D** is the last
  non-empty capture at least 3 hours before kickoff; close snapshot **C** is
  the last non-empty capture in the final 30 minutes. Official line source is
  ESPN's DraftKings feed (targets, no prices). `track.py` and the published
  prereg YAML are frozen.
- **Real-bets log (`props-finder/user_bets/bets.csv`)** — the owner's actual
  Fliff / DraftKings / Chalkboard / PrizePicks results, maintained separately
  from the model paper tracks.
- **Price-shopping helpers (`props-finder/`, older `prop-finder/`)** — "market
  as the model" consensus shopping and PrizePicks helpers. Sunday NFL
  price-shop workbooks are under `analysis/`.
- **CFB (`cfb/`, `cfb-model/`, `cfb-props/`)** — a power-rating model and a
  Fliff-vs-DraftKings price-check / off-number paper track. The CFB Saturday
  routine is paused. The model's own README reports no demonstrated edge.
- **Independent reviews (`reviews/`)** — Tester1, Tester2, Tester3, and
  owner-side audits and cross-checks.

## Directory map

```
nhl-sog/                 NHL SOG model, captures, window-pass outputs, graders
  prereg/                NHL prereg draft (not a published NFL-style binding YAML)
  captures/              D / C / Fliff raw JSON by date
  picks/                 Per-pass D CSVs, GATE files, room/post text, final-call markers
  sheets/                Per-pass workbooks (*_picks.xlsx) used by the majority grader
  majority/              grade_majority.py + graded_sides.csv
  card_decisions.csv     FINAL CALL / skip decisions per list
  graded/                Official-list grader outputs
  shadow/, challenger/   Shadow trackers and challenger model
  fliff_prices/, fliff_credits_*.csv
  NOTES.md               Run log and process changes
  user_bets/             Bet-slip stills that passed the public-repo screen
nfl-props/               NFL yards research pipeline (v3) and 2026 paper track
  prereg/                BINDING prereg_2026_wk5-18_PUBLISHED_20261005.yaml + sha1
  src/nflprops/track.py  Frozen tracker (do not edit)
  data/snapshots/        Per-day .tar.gz of ESPN capture JSON (see README there)
  data/predictions/, data/track/, data/cache/, data/lines/
  scripts/, ops/         snapshot_loop / supervisor, close-window capture
  reports/, experiments/, configs/
props-finder/            Market-consensus shopper + user_bets/bets.csv
prop-finder/             Older / larger research tree (backtests, CFBD, caches)
cfb/                     CFB price_check.py, leans, Odds API reuse JSON, notes
cfb-model/               Power-rating model, slate.py, backtest_* (paper only)
cfb-props/               Line archives and evidence
nfl-props-counts/        Small helper for counting / scoring user-log lines
nhl-sog-papertests/      Late-lineup re-pull + position-defense challenger tests
reviews/                 tester1-review, tester2-review, tester3-review, yinzer-*
                         weekly-review-20261031, feature and backtest audits
routines/                What could be documented about scheduled jobs
analysis/                Sunday NFL price-shop workbooks (weeks 6–8)
EXCLUDED.md              Everything left out, with sizes and reasons
REDACTIONS.md            Secret handling
```

## Pipeline / process flow

### Standing rules (verified from notes, prereg text, and grader docstrings)

- Paper only. Pipelines do not place bets.
- **Frozen NFL model:** do not edit `nfl-props/prereg/prereg_2026_wk5-18_PUBLISHED_20261005.yaml` or `nfl-props/src/nflprops/track.py`, and do not use `--rescore`.
- Do not invent or backfill prices, closes, or CLV, and do not make retroactive picks.
- Fliff Odds API use is capped at **10 credits a day**. The official NFL paper track does not spend Odds API credits (the published prereg says prices are not used; -110/-110 is assumed and flagged).
- The posted **price band is enforced only at the -150 end** (a posted price worse than -150 is outside the band). See `nhl-sog/majority/grade_majority.py` (`in_band`: `int(price) >= -150`).
- Majority lists (4 or more of 7 evidence tests) are informational only. Reports should show the real denominator (for example "4 of 7").
- Prop mentions in room posts are supposed to name the player's team, the game (both teams), over or under, and the line.

### NHL SOG

1. **Line capture.** `capture.py` plus `ops/capture_loop.sh` / `capture_supervisor.sh` / `ensure_capture.sh` write snapshots under `captures/`. The **D window** is 150-210 minutes before puck drop (extended to 210-240 if a D snapshot already exists). The **C window** is the last ~30 minutes (in-window close snaps are typically taken around 28 minutes out and refreshed until puck drop). Helpers are in `window.py` (`WIN_LO, WIN_HI, WIN_MAX = 150, 210, 240`). Until 2026-11-01, games with a puck drop before noon PT were excluded from window mode; from 2026-11-02 that exclusion was removed (`PRE_NOON_LAST_DATE` in `window.py`).
2. **Window pass / line-capture pass.** `predict.py --window-only` scores only unscored games in the D window, merges into `picks/<date>_D.csv` without rewriting already-posted games (unless `--rescore`, which is not used on the official track). Then challenger scoring, `shop_gate.py`, `recent_form.py`, `build_sheet.py` (workbook + post text), and `fliff_prices.py` (no more than 10 Fliff credits/day). Room text is written to `picks/<list>_room.txt`.
3. **Hold + FINAL CALL.** After a list is posted, a final-call routine waits (the approved hold is 10 minutes) and records a decision in `card_decisions.csv`. Marker files live under `picks/finalcall_done` when present.
4. **Majority list.** Sides with `agrees_n >= 4` of 7 evidence tests are listed for information, always with the real denominator. They are graded separately by `nhl-sog/majority/grade_majority.py`.
5. **Grading and shadows.** `grade.py` / `grade_report.py` grade official lists. Nightly shadow trackers (promo-under, 50% shrink, edge-8 price band) write under `shadow/`. A game-night close-capture safety net and an hourly capture wake watch D/C completeness and alert only on new misses.
6. **Fliff second pull.** For sides marked not offered, a later Fliff pull about an hour before puck drop is allowed (1 credit per game, still inside the 10-credit cap), approved 2026-11-03.

### NFL yards (frozen paper track)

Documented in `nfl-props/README.md` and the binding prereg:

1. `scripts/snapshot_supervisor.sh` runs `snapshot_loop.sh`: a capture every 10 minutes, every 3 minutes when a kickoff is within 45 minutes.
2. `snaplines` derives **D** (last capture at least 3 hours pre-kick with lines) and **C** (last capture in `[kickoff-30min, kickoff)` with lines). Missing C voids the line. Empty captures are skipped; a line present at D but missing from the last non-empty C is `pulled_before_close`.
3. `pregame` writes one row per D line using only data from before the week's first game day.
4. `track.py` scores the week (z-CLV, voids, diagnostic bets). This file is frozen.
5. Scheduled Grok Bot routines (not box cron) pad D and C around Mon/Thu night games and Sunday slates — times are listed in the prereg `capture_schedule` block and in `routines/README.md`.

### CFB (on hold)

`cfb-model` is a paper-only power-rating model (`slate.py` can spend 2 Odds API credits for a live pull). `cfb/price_check.py` compares Fliff vs DraftKings at the same number and, since 2026-10-24, an off-number converted track. The Saturday price-check + free line-capture routine is **paused** as of the 2026-11-11 usage report. The model README's verdict is "no demonstrated edge."

## Frozen-model rules

Binding NFL pre-registration (do not edit):

- File: `nfl-props/prereg/prereg_2026_wk5-18_PUBLISHED_20261005.yaml`
- Pointer + sha1: `nfl-props/prereg/LATEST_PUBLISHED.txt`
  (`fc9961cfe3c5dd0075a89173393e5d88e67f3cd1`, published 2026-10-05 1:50:20 PM PT)
- Frozen git commit named in the prereg: `de029ac361a28973aba1689606ca27fdf8a83736`
- Frozen tracker: `nfl-props/src/nflprops/track.py` (sha1 listed in the prereg `file_sha1` block at publish time: `0b5414dceb0585c3a469c6ef439ef7a609554a02`)
- Scope: 2026 regular season weeks 5-18, markets `pass_yds`, `rush_yds`, `rec_yds`
- `--rescore` is the old full-rewrite path on the NHL side and is not used for official lists. Do not backfill prices, closes, or CLV. Do not make retroactive picks.

NHL model weights / champion id are recorded in `nhl-sog/NOTES.md` (champion model `c3ab760178` is described as unchanged when input data was refreshed on 2026-10-17). There is a draft NHL prereg at `nhl-sog/prereg/prereg_nhl_sog_DRAFT.md`, not a published binding YAML of the NFL kind.

## Key result files and how to recompute records

Figures below were recomputed from the exported CSVs on 2026-11-11 PT. Re-run the commands to confirm.

### Real bets (owner log)

File: `props-finder/user_bets/bets.csv` (88 rows, 2026-10-10 through 2026-11-10).

```bash
python3 -c 'import pandas as pd; df=pd.read_csv("props-finder/user_bets/bets.csv"); print(df["result"].value_counts().to_string()); print("rows", len(df), "from", df["date"].min(), "to", df["date"].max())'
```

As of this snapshot: **48 wins, 38 losses, 1 cash-out, 1 void.** Books in the log: Fliff 43, DraftKings 33, Chalkboard 10, PrizePicks 2.

This log is not a model test (also stated in `nhl-sog/NOTES.md`). Some days still have open questions noted in process notes (for example duplicate Fliff tickets on 2026-10-18).

### NHL majority list (informational, 4+ of 7)

File: `nhl-sog/majority/graded_sides.csv` (154 graded sides, 2026-11-05 through 2026-11-10). Recompute:

```bash
cd nhl-sog && python3 majority/grade_majority.py
python3 -c 'import pandas as pd; m=pd.read_csv("majority/graded_sides.csv");
def wl(s):
    return f"{(s.result==\"W\").sum()}-{(s.result==\"L\").sum()}", round(s.units.sum(), 2)
print("all", *wl(m), "n", len(m))
print("in_band", *wl(m[m.in_band==True]))
print("out_of_band", *wl(m[m.in_band==False]))'
```

As of this snapshot, all 154 sides are finished: **76-78, -16.82u** overall; **48-53, -7.62u** inside the band; **28-25, -9.19u** outside. `agrees_n` in the file ranges from 4 to 6. Price source is almost all DraftKings (152) vs Fliff (2), because the grader uses the captured Fliff price only when Fliff offered that side on the earliest list. Shop-at quotes and later re-pulls are never used.

Official (non-majority) paper tracks and shadow trackers have their own outputs under `nhl-sog/graded/` and `nhl-sog/shadow/`. See `grade_report.py` and `NOTES.md`.

### NFL paper track

Follow `nfl-props/README.md`. After creating a virtualenv and installing `requirements.txt` plus the package (`pip install -e .`):

```bash
cd nfl-props
python -m nflprops.track week --season 2026 --week 9
```

Do not pass `--rescore`. Snapshot JSON is packed as `data/snapshots/YYYY-MM-DD.tar.gz`. Unpack a day with `tar -xzf YYYY-MM-DD.tar.gz` from that directory. Set `ODDS_API_KEY` only if you are running optional Odds API sidecars; the official track does not use it.

### CFB

- Model backtests: `cfb-model/backtest_results.txt` and `backtest_20XX.csv`; rerun `python3 backtest.py` in `cfb-model/`.
- Price-check leans: `cfb/leans/` and `cfb-props/lines/`.

## Routines (scheduled processes)

Live Grok Bot routine **prompt text is not in this repo** — it was not present as files on the box. Schedules, enabled/paused state, and behavior that could be verified are in [routines/README.md](routines/README.md). Those jobs are Grok Bot scheduled routines, not crontab on the box. Time zone is **America/Los_Angeles**.

Box-side loops that the routines check on (and that a reviewer can run) include:

- `nhl-sog/ops/capture_loop.sh` + `capture_supervisor.sh` + `ensure_capture.sh`
- `nfl-props/scripts/snapshot_loop.sh` + `snapshot_supervisor.sh`
- `nfl-props/ops/close_window_capture.sh` + `ensure_capture.sh`

## Secret scanning / credentials

See `REDACTIONS.md` and `EXCLUDED.md`. There is no usable Odds API key in this tree. After cloning, copy `nfl-props/.env.example` to a local `.env` (gitignored) if you need one.

Scanners run on this snapshot (2026-11-11, America/Los_Angeles):

- **gitleaks v8.30.1** (`dir` mode) scanned about 2.31 GB and reported 28 `generic-api-key` hits:
  - 22 were X (Twitter) API `meta.next_token` pagination cursors in `nhl-sog/shadow/xlineup/raw/` captures from 2026-11-03. Those values were replaced with `REDACTED_X_NEXT_TOKEN`. They are not account bearer tokens.
  - 6 were public ESPN boxscore fields named `publishedkey` (recap content ids) in `nhl-sog/audit/20261031_yinzer/cfb/espn/` and `prop-finder/data/cache/`. Left unchanged; they are not API credentials.
- **Custom sweeps** over text files (including `key=`, `token`, `apiKey`, `Authorization`, `Bearer`, `@gmail`, and `password`) found no live Odds API keys, GitHub PATs, Slack tokens, PEM keys, or email addresses. Apparent `AKIA` hits in name searches were player-name substrings, not AWS keys. Official NFL snapshot tarballs were byte-scanned for leftover key needles with no hits after the key files were replaced by placeholders.
- **trufflehog** was not installed and was not run.

Source that reads `ODDS_API_KEY` or interpolates `apiKey={key()}` was left intact so a reviewer can supply a key via the environment or a local gitignored `.env`.

## Known caveats

- **Paper vs real money.** Model and majority records are paper. `props-finder/user_bets/bets.csv` is the real-money log and is a different series.
- **Stale NHL inputs, 2026-10-12 through 2026-10-16.** `nhl-sog/NOTES.md` records that `fetch.py` had hard-coded a too-short 2026-27 window, so D files those days used stale features. Rows were kept as logged and flagged; they were not re-predicted. Fixed 2026-10-17.
- **Missing captures.** Several notes and `nhl-sog/logs/missed_windows.csv` / `nfl-props/logs/missed_games.csv` record D or C windows that closed without a file (including a Nov 5-8 NHL window-pass outage described in process notes). Missing C voids NFL lines rather than inventing a close.
- **Majority coverage starts 2026-11-05** (`FROM_DATE` in `grade_majority.py`), which is the first day 4-of-7 lists were posted that way.
- **CFB is paused** and the power-rating model did not show an edge in its own backtest write-up.
- **Sportsbook account recordings were omitted** from this public copy. The CSV log remains.
- **Duplicate 5-16G Tester1 working copies** of `nfl-props` / `nhl-sog` were omitted; unique reports and scripts were kept.
- **Per-project `.gitignore` files** (especially `nfl-props/.gitignore`) still describe the *original* project conventions and would ignore snapshot JSON if you unpacked it and ran `git add` only inside that subfolder. The files are in this repo as compressed archives.

- **Upstream `.gitignore` files** were renamed to `.gitignore.original` in this snapshot so `git add` keeps captures, caches, logs, and evidence that those project ignores would have dropped. The root `.gitignore` still excludes live `.env` files, venvs, and bytecode.
- Routines can drift from the notes. The table in `routines/` is what could be verified on 2026-11-11, not a dump of the live prompt store.

## License / use

Data and code are published so the work can be independently reviewed. Bookmakers' official data remains subject to their terms. Do not treat any list in this repo as a recommendation to place a bet.
