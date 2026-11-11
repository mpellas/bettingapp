# Tester1 cross-check: NHL majority-list grader (Nov 5 and Nov 9)

Independent rebuild. Sources were copied with `cp -a` into this folder and checked with `diff -q`. His script was read, not rerun. Universe rebuilt from the pass sheets; shots graded from NHL API boxscores (`api-web.nhle.com` gamecenter), then checked against `graded/20261105.csv`, `shadow/s2026_live.pkl`, and the NHL stats summary API.

Convention: flat 1u *risked* (not to-win). Win at American price `a` pays `dec(a)-1`; loss is `-1`. `dec(a) = 1 + a/100` if `a>0`, else `1 + 100/(-a)`. Band: outside when posted price is worse than -150, i.e. in-band iff `price >= -150` (exactly -150 is inside).

## Verdict

**His record matches exactly.** No missing or extra sides, no wrong results, no wrong prices, no leakage of later-pass price or `agrees_n`.

| Claim | His figure | Independent rebuild |
|---|---|---|
| Unique 4+ of 7 sides (Nov 5 + Nov 9) | 94 | 94, same keys |
| Graded so far | 67 went 29-38 (43.3%), -15.65u | 29-38, **-15.6519u** (rounds to -15.65u) |
| Break-even | 54.8% | 54.8%, as `1 / mean(decimal odds)` (not the 55.8% mean of implied probabilities) |
| Inside -150 band | 17-25, -9.44u | 17-25, -9.44u (n=42) |
| Outside band | 12-13, -6.21u | 12-13, -6.21u (n=25) |
| 4 of 7 | 18-26, -12.59u | 18-26, -12.59u (n=44) |
| 5 of 7 | 10-9, -0.69u | 10-9, -0.69u (n=19) |
| 6 of 7 | 1-3 (units not stated) | 1-3, **-2.38u** (n=4) |
| Nov 6–8 skipped | no D files | confirmed: no sheets and no D CSVs |
| Tonight's 27 Nov 9 sides | not graded yet | all 27 pending; those games were still CRIT/LIVE at the check |
| Prices | DK except Heineman U1.5 at Fliff -115 | same; only Fliff-priced row, still pending |

Row-level: all 94 keys, `list_id`, `appeared_on`, `agrees_n`, `dk_price`, `price`, `price_source`, `in_band`, `gameId`, `nhl_id`, `actual`, `result`, and `game_finished` match his `graded_sides.csv`. The only units difference is cosmetic: pending rows are `NaN` in his file and `0.0` in my rebuild file. Decided-side units match to `1e-6` (he rounds to 6 decimals).

## 1. Universe

Sheets used (only these exist for Nov 5 and Nov 9):

| Pass | 4+ of 7 sides |
|---|---|
| 20261105_1239 | 67 |
| 20261109_1401 (Rangers at Oilers) | 11 |
| 20261109_1509 (Flyers at Canucks) | 8 |
| 20261109_1512 (both of those games combined) | 19 |
| 20261109_1537 (Islanders at Sharks) | 8 |

Raw total 113 before dedupe. Dedupe by `(date, game, player, side, line)` yields **94**. The 1512 sheet is a republish of 1401+1509: 11 + 8 = 19, no unique sides. After dedupe: 67 + 11 + 8 + 8 = 94.

`appeared_on` is correct:

- 67 sides: `20261105_1239`
- 11 sides: `20261109_1401,20261109_1512`
- 8 sides: `20261109_1509,20261109_1512`
- 8 sides: `20261109_1537`

Earliest pass keeps price, `list_id`, and `agrees_n`. Across 1401 vs 1512 and 1509 vs 1512, **no side changed `dk_price` or `agrees_n`**, so a keep-first vs keep-last choice would not have mattered on this sample, but the keep-first logic is implemented correctly and the earlier list id is the one stored.

Nov 5 late games (VAN@WPG 2026020259, ANA@EDM 2026020260, NSH@COL 2026020261) are **not on the 1239 sheet at all**. The sheet only has the eight earlier games. Those three games finished and have boxscores (and are in `s2026_live.pkl` and the stats API), but they contribute zero majority-list sides. His "never scored" note is true of `graded/20261105.csv` (those games are absent there); it does not change this 94-side universe.

## 2. Grading

All 67 Nov 5 sides are from finished games and were graded. All 27 Nov 9 sides are pending (NYR@EDM was CRIT, PHI@VAN and NYI@SJS were LIVE at this check). No voids and no pushes. Every line is a `.5` line, so a push is impossible.

Shots agree across four sources for all 67 graded sides:

- NHL `gamecenter/{id}/boxscore` (`sog`)
- NHL stats summary API (`shots`) — 0 diffs, 0 missing
- `graded/20261105.csv` (`actual`) — 0 diffs
- `shadow/s2026_live.pkl` — 0 diffs

Twelve 0-shot results were checked against TOI. All twelve played (TOI from 11:51 to 27:31). They are genuine 0-SOG games, not DNPs, so a loss on the OVER / a win on the UNDER is correct. No graded side was missing from the box (which would be a void). His DNP rule (finished game, no box row → void, not a loss) is right and did not fire on this set.

Spot-checks from the official boxscore (all OK):

| Game | Player | Box SOG | Line | Result |
|---|---|---|---|---|
| UTA@MTL | Clayton Keller | 1 | O2.5 | L |
| UTA@MTL | Lane Hutson | 3 | U1.5 | L |
| UTA@MTL | Cole Caufield | 6 | U2.5 | L |
| UTA@MTL | Zack Bolduc | 4 | U1.5 | L |
| UTA@MTL | Mikhail Sergachev | 0 (TOI 27:31) | O1.5 | L |
| VGK@DET | Moritz Seider | 2 | O1.5 | W |
| CHI@TBL | Tyler Bertuzzi | 0 (TOI 16:56) | U1.5 | W |
| PHI@NYR | Porter Martone | 1 | O1.5 | L |
| BOS@PIT | David Pastrnak | 4 | O3.5 | W |
| BOS@PIT | Pavel Zacha | 2 | O1.5 | W |
| BOS@PIT | Rickard Rakell | 3 | O2.5 | W |
| BOS@PIT | Charlie McAvoy | 1 | U1.5 | W |
| BOS@PIT | Evgeni Malkin | 1 | O1.5 | L |
| BOS@PIT | Sidney Crosby | 0 (TOI 17:15) | O2.5 | L |
| BOS@PIT | Ben Kindel | 0 (TOI 18:07) | U2.5 | W |

Utah at Montreal going **0-9** is real, not a grading bug. The four overs were low (Keller 1, Weegar 1, Trocheck 1, Sergachev 0) and the five unders were high (Caufield 6, Bolduc 4, Slafkovsky 4, Cooley 3, Hutson 3).

## 3. Units and splits

Units recomputed at the stated price with 1u risked match his -15.65u and every published band/count split.

Extra splits he did not publish:

| Split | Record | Units |
|---|---|---|
| OVER | 19-25 (43.2%) | **-9.29u** (n=44, break-even 53.2%) |
| UNDER | 10-13 (43.5%) | **-6.36u** (n=23, break-even 58.1%) |
| Nov 5 | 29-38 (43.3%) | **-15.65u** (all 67 decided sides) |
| Nov 9 | 0 decided, 27 pending | n/a |

Hit rate is almost the same on overs and unders. Unders were priced more juiced (58.1% break-even vs 53.2%). 6 of 7 went 1-3 for **-2.38u**: Seider O1.5 at -160 won (+0.625u); Martone O1.5 (Nov 5, PHI@NYR, -105), Keller O2.5 (+115), and Hutson U1.5 (-120) all lost.

Five sides were priced at exactly -150 and correctly marked in-band.

## 4. User-played sides

Of the five named plays:

| Play | In the 94? | In the 67 graded? | Paper grade |
|---|---|---|---|
| Pavel Zacha O1.5, Nov 5 BOS@PIT | yes, 5 of 7, -120 | **yes, W** (2 SOG) | W, +0.83u |
| David Pastrnak O3.5, Nov 5 BOS@PIT | yes, 5 of 7, +100 | **yes, W** (4 SOG) | W, +1.00u |
| Rickard Rakell O2.5, Nov 5 BOS@PIT | yes, 5 of 7, -110 | **yes, W** (3 SOG) | W, +0.91u |
| J.T. Miller O1.5, Nov 9 NYR@EDM | yes, 4 of 7, DK -140, first pass 1401 | no, still pending | game not final |
| Porter Martone O1.5, Nov 9 PHI@VAN | yes, 5 of 7, DK -150, first pass 1509 | no, still pending | game not final |

**3 of the 67 graded sides are user plays** (Zacha, Pastrnak, Rakell), all wins. Miller and Martone on Nov 9 are in the 94 but not in the 67, because those games were not official at grade time. (Miller already showed 2 SOG in-game; leaving him pending until the game is FINAL is correct.)

Also in the 67, but not one of the named Nov 9/Nov 5 user plays: **Porter Martone O1.5 on Nov 5** (PHI@NYR), 6 of 7 at -105, **L** with 1 SOG. That is a paper majority-list side, not the Nov 9 DraftKings play.

## 5. Leakage and under prices

No later-pass leakage. Price, `agrees_n`, and `list_id` come from the earliest pass. `appeared_on` is the only field that lists later passes.

Under prices are the listed side's price, not the over price, and results go the right way. Examples: McAvoy U1.5 at **+110** with 1 SOG is a win at **+1.10u**; Kindel U2.5 at -190 with 0 SOG is a win at +0.53u; Caufield U2.5 at +110 with 6 SOG is a loss. No inverted under pricing.

Heineman U1.5 on Nov 9 correctly uses Fliff -115 (offered at the listed line on the 1537 capture) instead of DK -105. A different Heineman U1.5 on Nov 5 (CAR@NYI) is DK -155, correctly graded W with 1 SOG, and is a separate side.

## Bugs and notes

1. **No discrepancy in the published 29-38 / -15.65u record.** The only omitted number is 6 of 7 units, which are **-2.38u**.

2. **Latent finished-flag fallback, did not fire here.** In `grade_majority.py` lines 466–471, if a date is treated as historically complete (`graded/<date>.csv` or the live log covers that date) but a `gameId` is not in `local_games`, the next branch still sets `is_fin = True` whenever `gameId` is present. A side from a late game missing from both `graded/` and the pkl would then be voided as a DNP instead of left pending. It did not affect this run: the late Nov 5 games are not on the majority list, and `s2026_live.pkl` actually has their shots anyway.

3. Utah 0-9 is a real slate result, not a source or side-inversion bug.

Files: rebuild in `rebuild/my_graded_sides.csv`; official boxes in `rebuild/nhl_api/`; this report.
