# Tester1 cross-check of Yinzer's Nov 9 fixes (books + NFL IDs + NHL n/a)

Work copies only (`cp -a` + `diff -rq` verified). Ran from `/workspace/tester1-review/xcheck_fixes_20261109/`. Re-copied `nhl-sog/evidence_extra.py` after the bak_y3 edit (restored schedule + `n/a:` note). Independently rebuilt signals from raw Fliff JSON / all_sides / nflverse; did not just re-run Yinzer's code (also compared to it).

## 1. NFL book agreement — PASS

Claim: de-vig this book's own over/under before comparing to `fair_prob`; no two-sided price → 0.

On `nfl_wk8_nov02_1613_all_sides.csv` (419 rows), independent rebuild matches Yinzer's `x_books` **0 mismatches**.

| | old (vig vs fair_prob) | new (de-vig vs fair_prob) |
|--|--|--|
| sign dist | −1: 48, 0: 371 | +1: 1, −1: 1, 0: 417 |
| props with both O and U minus | **24** | **0** |
| nonzero O/U pairs opposite sign | n/a (broken) | OK=1 FAIL=0 |

- Over/under of the same prop no longer both get minus.
- Same-line DK rows all score 0: `fair_prob` is already the consensus no-vig and sits within 2 pts of DK's own de-vigged price (expected on this file).
- The only nonzeros are one Fliff line-lean pair (+/−). PrizePicks (one-sided) → 0 on the same-line branch.
- No lookahead: books only reads other rows in the same input frame (no time dimension).

**Display trust:** OK to show. It will be 0 on most same-line DK consensus rows; that is the math, not a leftover bug.

## 2. NFL missing IDs — PASS (with residual name gaps + one new bug)

Claim: map missing `player_id`/`game_id` from nflverse name+team; 371/419 on Nov 2 wk8 all_sides; print `MAJORITY LIST UNAVAILABLE` when nothing scores.

- **371 / 419 scorable — exact match** (371 name+team, 11 name-unique with `team` NaN that still get a pid but no game_id → not scorable, 37 name-miss).
- Spot-check ~20 scored mappings (incl. shared-surname risks: Wilson, Williams, Allen, Jackson, Lawrence, Washington, etc.): **0 wrong-player matches**. `name+team` key holds when the slate team is present.
- `MAJORITY LIST UNAVAILABLE` string is in `add_evidence.py` and the `agrees_n.notna().sum()==0` branch fires in a dry harness (all-NA / missing col). Not re-run end-to-end through nfl-props (read-only).

### 48 unscored

**37 name-miss** (slate short name ≠ nflverse display name; Jr./III/Daniel/Michael):

| slate name | team | nflverse match |
|--|--|--|
| brian thomas | JAX | Brian Thomas Jr. |
| chris godwin | TB | Chris Godwin Jr. |
| chris rodriguez | JAX | Chris Rodriguez Jr. |
| dan bellinger | TEN | Daniel Bellinger |
| dan jones | IND | Daniel Jones |
| harold fannin | CLE | Harold Fannin Jr. |
| luther burden | CHI | Luther Burden III |
| mike carter | TEN | Michael Carter |
| mike mayer | LV | Michael Mayer |
| mike penix | ATL | Michael Penix Jr. |
| mike washington | LV | Mike Washington Jr. |
| mike wilson | ARI | Michael Wilson |
| omar cooper | NYJ | Omar Cooper Jr. |
| ted hurst | TB | Ted Hurst III |

**11 name-unique with `team` NaN** (pid filled, game_id not): eric saubert, will mallory, brock wright, olamide zaccheaus, jack bech, isaiah williams, chimere dike, keon coleman (some O+U).

### NEW BUG — `e2g` scope regression (`nfl_add_evidence.py`)

`e2g = {...}` was moved **inside** the `if 'player_id' not in A or 'game_id' not in A` block (line 129). Live analysis CSVs already have both IDs, so that branch is skipped, then line 140 `espn_injuries(ev, e2g)` → **NameError** unless `--no-net`.

- bak_20261109 had `e2g` always set on the `D = E.load()` line.
- Confirmed live files (`analysis_2026_wk*_live_*.csv`) have `player_id` and `game_id`.
- all_sides path (missing IDs) still sets `e2g` and is fine.

**Before trusting live NFL evidence runs:** move `e2g = ...` back above the if (always). Optional: strip Jr./II/III and map Mike→Michael / Dan→Daniel to recover the 37 name-miss rows.

## 3. NHL book agreement — PASS

Claim: Fliff vs DK no-vig at same line; line-lean when lines differ; only Fliff pulls at or before pass; Nov 4 = 6 for / 6 against.

Independent rebuild from `captures/fliff_20261104_1532_*.json` vs `20261104_D_1531.csv`:

- **asof ≥ 1532: exactly +6 / −6** (12 nonzero). Matches Yinzer's code 0 mismatches. Players: Kempe (lean), Marchment, Byfield, Celebrini, Eberle (lean), Parekh.
- **Leak guard:** D capture asof **1531** → Fliff 1532 excluded → **0 nonzero**. Live sheet-time books=0 is expected.
- Same-line and line-lean both flip O vs U (0 pair failures).
- Vig-bias gone on this slate: old single-side vig compare was **+14 / −3** on Nov 4 same-line sides; new no-vig is **+4 / −4**. Historic eod across saved passes: +81 / −81.

Honest note: scoring **both** sides with antisymmetric rules makes any even slate split +/− by construction. The real fix proof is the old +14/−3 vig bias disappearing and the timestamp filter working.

**Display trust:** OK. Live passes will usually show books=0 (Fliff pulled after the sheet); that is documented and correct.

## 4. Restored NHL rest + n/a note — PASS

- Current `EXTRA = {hit, books, rest}` → **tests_all_n = 10**. Present in current and bak_y3; bak_t2 (Tester2) lacked rest (the deletion Yinzer said he restored).
- CHI @ TBL Nov 5 (`gameId` 2026020253): visitor teamId 16 on back-to-back (played Nov 4), home 14 rested — matches Yinzer's spot check / schedule API.
- Simulated `_schedule` → `TimeoutError`: summary contains `n/a: hit, books, rest n/a (schedule: simulated timeout)`. **n/a note fires.**

## 5. Counts / card / denominator — PASS (unchanged)

- Nov 5 12:39 sheet: **67 sides at 4+ of 7** (unchanged). Status still 245 Skipped / 5 Fliff check. No `sig_x_*` on the saved sheet (extras merge at build time; sheet predates them).
- `build_sheet.py`: `assign_status` / `agrees_n` / `MIN_AGREE` run **before** `evidence_extra.annotate`; extras only add `sig_x_*`, `agrees_all_n`, `tests_all_n`, `evidence_all_summary`. Card gates untouched.
- Denominators in code/NOTES: NHL **N of 7** plus **N of 10 with new tests** (hit+books+rest); NFL **N of 11** (hit+books+pace+rest). Post text appends `evidence_all_summary` next to the of-7 line.

## Bottom line

| Fix | Verdict |
|--|--|
| NFL books de-vig | PASS — both-sides-minus gone |
| NFL ID fill 371/419 + UNAVAILABLE | PASS count; **fix e2g on live inputs before trusting** |
| NHL books no-vig + leak guard + Nov4 6/6 | PASS |
| NHL rest restored + n/a note | PASS |
| 4-of-7 / card / denominators | PASS unchanged |

Do not treat the new tests as gates. Fix the `e2g` NameError before the next live NFL evidence run without `--no-net`. Jr./Mike/Dan name normalization would recover 37 more all_sides rows but is optional for display.

Artifacts: `nhl_books_nov4.csv`, `nhl_books_historic.csv`, `nfl_books_compare.csv`, `nfl_id_map.csv`, `nfl_unscored.csv`, `scripts/`.
