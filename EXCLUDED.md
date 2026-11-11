# Excluded from this public export

Original files on the box were not modified. This list is everything that was
intentionally left out of `/workspace/bettingapp-export` (and therefore out of
the staged git repo). Sizes are from the box at export time (2026-11-11,
America/Los_Angeles).

## Unrelated projects (not the betting app)

The box also holds a separate workout / "90Strong" / iron-log project, comparable-app
audits, browser profiles, and agent runtime data. Those were not copied:

- `/workspace/iron-log/`, `iron-log-ro/`, `iron-log-test/`, and the many `ironlog-*` folders and `iron-log-*-code-review.*` files
- `/workspace/90strong-audit-*`, `90strong-issues-*.csv`, and related audit HTML
- `/workspace/comparable-apps-report.*`
- `/workspace/w2-oct12/`, `/workspace/w2-oct7/` (workout-app screenshots)
- `/workspace/t1-oct6/`, `/workspace/il1019/`
- `/home/box/chrome-profile/`, `/home/box/.config/google-chrome*`, `/workspace/.playwright-mcp/`, `/workspace/.mdenv/`
- `/home/box/sand-data/` agent stores, `store.db`, cookie seed files, and other runtime secrets
- Skills, caches, and unrelated tooling under `/home/box`

90Strong / workout **routines** that appear in Grok Bot usage (paused "Daily 90Strong test window", "Daily 30-min app test", "90Strong daily test pass") are not part of this repo.

## Venvs, git metadata, caches, and bytecode

Every copy skipped `.venv/`, `venv/`, `__pycache__/`, `.git/`, `node_modules/`, `.pytest_cache/`, and `*.pyc`. Notable omitted sizes:

| Path | Size | Why |
|---|---|---|
| `/workspace/nfl-props/.venv` | 735M | Python virtualenv |
| `/workspace/nhl-sog/.venv` | 13M | Python virtualenv |
| `/workspace/tester1-review/xcheck_extra_20261109/venv` | 338M | Review working venv |
| `*/.git` under `nhl-sog`, `nfl-props`, `props-finder`, `cfb-props`, `iron-log` | various | Per-project git history; this export is a new repo |

`nfl-props/.gitignore` in the original project also omits `data/snapshots/**/*.json`, `data/cache/`, `logs/`, and some evidence caches. Those data dirs **are included here** (snapshots as per-day `.tar.gz`) so a reviewer can inspect the live pipeline outputs.

## Duplicate working copies of the main trees

Tester1 review folders contained full extra checkouts of `nfl-props` and `nhl-sog` used to rerun checks. They duplicate the top-level trees (including snapshot JSON and, in some cases, live `.env` / `odds_api_key` files). They were omitted:

| Path | Size | Why |
|---|---|---|
| `/workspace/tester1-review/enh3_check/` (`nfl-props/`, `nhl-sog/`) | 5.3G | Duplicate working copies only; no top-level report in that folder |
| `/workspace/tester1-review/enh3_recheck/` (`nfl-props/`, `nhl-sog/`, `synth/`) | 11G | Duplicate copies plus a 5.2G synth rerun |
| `/workspace/tester1-review/enh3_recheck2/` (`nfl-props/`, `synth/`) | 16G | Duplicate copies plus an 11G synth rerun |
| `/workspace/tester1-review/xcheck_extra_20261109/nfl-props/` | 1.2G | Duplicate `nfl-props` tree |
| `/workspace/tester1-review/xcheck_extra_20261109/nhl-sog/` | 240M | Duplicate `nhl-sog` tree |
| `/workspace/tester1-review/item4_overbias/nhl-sog-copy/` | 189M | Duplicate `nhl-sog` tree (unique CSVs/REPORT kept) |
| `/workspace/tester1-review/enh1_promo_under/nhl-sog_copy/` | (part of 152M folder) | Duplicate `nhl-sog` tree (unique reports/scripts kept) |
| `/workspace/tester1-review/audit_20261031/nfl_wk07/repo/` | 5.1G | Duplicate `nfl-props` tree including snapshots; `orig/` and `run.log` kept |
| `/workspace/tester1-review/audit_20261031/nfl_wk07_rerun/repo/` | 5.1G | Same; `orig/` kept |

Placeholder notes were left in those review folders (`OMITTED_WORKING_COPIES.md` or `repo/OMITTED_WORKING_COPY.md`).

## Secrets (replaced, not published)

| Path | Size | Why |
|---|---|---|
| `/workspace/nfl-props/.env` | 46B | Live `ODDS_API_KEY`. Replaced in the export with `nfl-props/.env.example` (`ODDS_API_KEY=REDACTED_ODDS_API_KEY`) |
| `/workspace/nfl-props/data/secrets/odds_api_key` | 33B | Live Odds API key. The export file of the same name contains only the placeholder `REDACTED_ODDS_API_KEY` |
| The same `.env` / `odds_api_key` files inside the omitted Tester1 working copies | 33–46B each | Never copied |

A `CFBD_API_KEY` environment variable is documented in `cfb-model/README.md` for the CollegeFootballData.com API. No live CFBD key file was found in the copied trees.

## Sportsbook screenshots and recordings (account identifiers or balances)

Included only when the image is a bet slip with no account balance, username, or wallet chrome. The following were omitted after visual review of the stills and of sampled video frames:

| Path | Size | Why |
|---|---|---|
| `/workspace/nhl-sog/user_bets/20261103_cb_crosby_johnston.jpg` | 276K | Chalkboard slip also shows a $36.08 account balance in the header |
| `/workspace/chalkboard/f_01.png` … `f_06.png` | ~330K each | Chalkboard lobby/promo screens, not bet slips, with a personal notification name in the status bar |
| `/workspace/chalkboard/cb_20261102.mp4` | 1.3M | Same lobby, plus account promo state |
| `/workspace/bets_oct15.mp4` | 966K | DraftKings My Activity recording (bet IDs / history UI) |
| `/workspace/bets_oct16.mp4` | 1.3M | Sportsbook bet-history recording |
| `/workspace/fliff_oct20.mp4` | 1.3M | Fliff recording |
| `/workspace/slips_1025.mp4` | 3.2M | DraftKings My Activity; sampled frames show cash and bonus balances |
| `/workspace/vids/room_0947.mp4` | 3.2M | Byte-identical to `slips_1025.mp4` |
| `/workspace/uploads/bets_oct18.mp4` | 2.5M | Sportsbook bet-history recording |
| `/workspace/uploads/bets_oct19.mp4` | 1.9M | Sportsbook bet-history recording |
| `/workspace/videos/bets_20261109.mp4` | 4.8M | Chalkboard entries; sampled frames show a $42.58 account balance |
| `/workspace/videos/bets_scroll_20261018.mp4` | 3.8M | Sportsbook bet-history scroll |
| `/workspace/videos/dk_bets_20261109.mp4` | 2.6M | DraftKings My Activity; sampled frames show $1.39 cash and $13.83 bonus |
| `/workspace/videos/fliff_bets_20261109.mp4` | 3.1M | Fliff My Picks; sampled frames show 6.25 Fliff Cash |

Bet-slip stills that did **not** show a balance or account id were kept at `nhl-sog/user_bets/`:

- `20261027_pp_scheifele_brunson.jpg` (PrizePicks 2-pick entry)
- `20261028_cb_protas_maxey.jpg`
- `20261104_cb_sga_reinhart.jpg`
- `20261105_cb_zacha_pastrnak_rakell_henry.jpg`

The actual-bet log itself is in `props-finder/user_bets/bets.csv` (and backups), which is included.

## Large files that were compressed rather than excluded

No remaining file in the export exceeds GitHub's 100MB hard limit. These were gzipped in the export only (originals on the box are unchanged):

| Original path | Original size | Export path |
|---|---|---|
| `prop-finder/data/backtest/projections.pkl` | 203.5MB | `prop-finder/data/backtest/projections.pkl.gz` (27.2MB) |
| `prop-finder/data/backtest/tuned_ncaaf_308d826005.pkl` | 69.1MB | `prop-finder/data/backtest/tuned_ncaaf_308d826005.pkl.gz` (8.2MB) |
| `nfl-props/data/snapshots/YYYY-MM-DD/` (32 day directories, 6.6G of JSON) | 6.6G | `nfl-props/data/snapshots/YYYY-MM-DD.tar.gz` (178M total) plus `capture_log.jsonl` and a short README |

## Live Grok Bot routine prompts

`/home/box/sand-data/agents/*/automations/` and `/home/box/sand-data/workflows/` were empty. Saved UpdateRoutine prompt text is not stored as files on this box. See `routines/README.md`. What could be verified from notes, the frozen NFL prereg, and a 2026-11-11 usage report is documented there; the live prompt bodies themselves could not be exported.

## Other

- `manual_pull.py` and `shot.sh` were copied into `analysis/` because they sat at `/workspace/` alongside the betting trees. Reviewers should treat them as ad-hoc helpers, not as the main pipeline.
