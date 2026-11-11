# Tester1 results audit: skipped NHL SOG sides, Oct 26 – Oct 29, 2026

Scope: every skipped side from the Oct 26–29 passes. Routines stopped about 1 PM PT on Oct 29, so 12:30 PM PT (20261029_1233) was the last pass graded.
Sign convention: units = the result if we HAD bet the skipped side, 1u risked at the DK price at pick time. **Negative = the skip saved money.**
CLV = no-vig move from the pick capture to the close, in the skipped side's favor (in pts). Positive means the market moved toward the side we skipped.
Sources: picks/*_room.txt, *_GATE.csv, card_decisions.csv, graded/2026102[6-8].csv (actuals + nv_over_C), captures/*/_CLOSE.json. Oct 29 actuals come from api-web.nhle.com boxscores.
Excluded: Scheifele O1.5 Oct 27 (card/PrizePicks hold). **Flames at Oilers Oct 28 was missed and is not graded** (box suspended, no list). Gap: no passes after 12:30 PM PT Oct 29, so none of Oct 29's later games were listed or graded, and the 1233 Fliff sides Goncalves and Ehlers have no close capture.
Taylor Hall (BOS@CAR Oct 27, role veto, 2 rows) is ungraded because his result is missing.

## Bucket tables
| Bucket | n | W-L | Units at DK (1u) | Shop-at n / units | CLV n / avg pts | No close |
|---|---|---|---|---|---|---|
| 1_fliff_skip | 24 | 10-14 | -5.37 | 21 / -4.94 | 22 / +0.5 | 2 |
| 2_stale_lineup | 7 | 4-3 | -0.32 | 7 / +0.13 | 7 / +0.7 | 0 |
| 3_role_slot_veto | 137 | 69-66 | -7.83 | 0 / +0.00 | 133 / +0.3 | 4 |
| 3: role_demotion | 50 | 18-31 | -14.32 | 0 / +0.00 | 48 / +0.9 | 2 |
| 3: role_promotion | 40 | 25-15 | +5.58 | 0 / +0.00 | 39 / -1.2 | 1 |
| 3: slot | 47 | 26-20 | +0.91 | 0 / +0.00 | 46 / +0.8 | 1 |
| 3: vetoed with blend edge>=5 | 0 | 0-0 | +0.00 | 0 / +0.00 | 0 / +0.0 | 0 |
| 3: vetoed with blend edge>0 | 79 | 45-33 | +4.59 | 0 / +0.00 | 76 / +0.4 | 3 |
| 1: rising_toi_under | 7 | 4-3 | +0.31 | 5 / +0.69 | 6 / -0.9 | 1 |
| 1: over_bias | 8 | 2-6 | -4.10 | 8 / -3.83 | 7 / +2.7 | 1 |
| 1: falling_toi_over | 1 | 1-0 | +0.87 | 1 / +1.01 | 1 / +2.9 | 0 |
| 1: market_move | 2 | 1-1 | +0.15 | 2 / +0.29 | 2 / -1.6 | 0 |
| 1: cleared_unpriced | 3 | 1-2 | -1.23 | 3 / -1.11 | 3 / +0.0 | 0 |
| 1: other | 3 | 1-2 | -1.38 | 2 / -2.00 | 3 / -0.5 | 0 |

Bucket 1 tags: rising_toi_under and over_bias are the tester rule-of-thumb skips (bucket 4). cleared_unpriced = sides cleared by the checkers that never reached the shop-at price (Protas, Malinski, Raddysh 10/28). market_move = Guenther x2. other = Raddysh 10/26, Bump, Hertl.
Bucket 1 was verified against the room files. Compared with the brief's list, it adds Oct 27 Sanheim O1.5, Dvorak U1.5, Bump U1.5 and Hertl U2.5. Werenski was moved to bucket 2.
Bucket 3 is deduped per player, game, side and veto type (latest pass). No vetoed side had a blend edge of 5 pts or more, so none of them would have been a pick.

## Per-side detail
See skipped_sides.csv (168 rows). Reproduce with `python3 audit.py && python3 summ.py`.
| 20261026_1311 | Trevor Moore OVER 1.5 | -145 | shop -123 | 0.0 L -1 | CLV 3.8 | over_bias |
| 20261026_1311 | Alex Laferriere UNDER 2.5 | -145 | shop -123 | 2.0 W 0.69 | CLV -8.3 | rising_toi_under |
| 20261026_1438 | Darren Raddysh UNDER 2.5 | -125 | shop -107 | 3.0 L -1 | CLV 0.0 | other |
| 20261026_1516 | Kasperi Kapanen UNDER 1.5 | -110 | shop +105 | 1.0 W 0.909 | CLV 1.0 | rising_toi_under |
| 20261027_1305 | Travis Sanheim OVER 1.5 | +110 | shop +124 | 2.0 W 1.1 | CLV 0.0 | over_bias |
| 20261027_1305 | Christian Dvorak UNDER 1.5 | -120 | shop -105 | 4.0 L -1 | CLV -1.5 | rising_toi_under |
| 20261027_1305 | Alex Bump UNDER 1.5 | -105 | shop +107 | 5.0 L -1 | CLV -1.8 | other |
| 20261027_1339 | Logan Stankoven OVER 2.5 | +110 | shop +125 | 1.0 L -1 | CLV 0.0 | over_bias |
| 20261027_1432 | Dylan Guenther UNDER 2.5 | +120 | shop +133 | 4.0 L -1 | CLV -1.1 | market_move |
| 20261027_1533 | Tomas Hertl UNDER 2.5 | -160 | shop  | 2.0 W 0.625 | CLV 0.3 | other |
| 20261027_1533 | Jackson LaCombe UNDER 1.5 | +100 | shop  | 1.0 W 1.0 | CLV 3.5 | rising_toi_under |
| 20261027_1533 | Cutter Gauthier UNDER 3.5 | +105 | shop  | 4.0 L -1 | CLV 0.0 | rising_toi_under |
| 20261027_1609 | Jack Quinn UNDER 2.5 | -105 | shop +109 | 3.0 L -1 | CLV 0.0 | rising_toi_under |
| 20261028_1304 | Travis Sanheim OVER 1.5 | +115 | shop +129 | 0.0 L -1 | CLV 2.8 | over_bias |
| 20261028_1304 | Trevor Zegras OVER 1.5 | -125 | shop -107 | 4.0 W 0.8 | CLV 5.2 | over_bias |
| 20261028_1304 | Aliaksei Protas UNDER 1.5 | -120 | shop -103 | 3.0 L -1 | CLV -2.5 | cleared_unpriced |
| 20261028_1509 | Sam Malinski UNDER 1.5 | -140 | shop -121 | 3.0 L -1 | CLV 2.5 | cleared_unpriced |
| 20261028_1535 | William Nylander OVER 2.5 | -115 | shop +101 | 3.0 W 0.87 | CLV 2.9 | falling_toi_over |
| 20261028_1535 | Darren Raddysh UNDER 2.5 | -130 | shop -112 | 1.0 W 0.769 | CLV 0.0 | cleared_unpriced |
| 20261029_1233 | Gage Goncalves UNDER 1.5 | -140 | shop -121 | 1.0 W 0.714 | CLV  | rising_toi_under |
| 20261029_1233 | MacKenzie Weegar OVER 1.5 | -120 | shop -103 | 1.0 L -1 | CLV 7.0 | over_bias |
| 20261029_1233 | Dylan Guenther UNDER 2.5 | +115 | shop +129 | 0.0 W 1.15 | CLV -2.0 | market_move |
| 20261029_1233 | Nikolaj Ehlers OVER 1.5 | -170 | shop -145 | 0.0 L -1 | CLV  | over_bias |
| 20261029_1233 | Sebastian Aho OVER 2.5 | -120 | shop -103 | 1.0 L -1 | CLV 0.0 | over_bias |
| 20261027_1305 | Zach Werenski UNDER 3.5 | -160 | shop -137 | 1.0 W 0.625 | CLV -0.9 | stale_12h |
| 20261027_1339 | Timo Meier OVER 2.5 | -105 | shop +109 | 0.0 L -1 | CLV 1.5 | stale_12h |
| 20261027_1339 | Jesper Bratt OVER 1.5 | -140 | shop -121 | 0.0 L -1 | CLV 0.0 | stale_12h |
| 20261027_1339 | Jack Hughes OVER 2.5 | -150 | shop -127 | 6.0 W 0.667 | CLV -0.3 | stale_12h |
| 20261027_1432 | Blake Coleman OVER 1.5 | -135 | shop -117 | 5.0 W 0.741 | CLV 0.4 | stale_12h |
| 20261027_1533 | Jake DeBrusk UNDER 2.5 | -135 | shop -117 | 3.0 L -1 | CLV 4.0 | stale_12h |
| 20261027_1533 | Drew O'Connor UNDER 1.5 | -155 | shop -132 | 1.0 W 0.645 | CLV 0.3 | stale_12h |

## Summary
- Fliff-check skips (24 sides): 10-14, -5.37u at DK (-4.94u at shop-at on 21). Skipping them saved about 5 units.
- The over-bias over skips were the big saver: 2-6, -4.10u. Rising-TOI under skips were roughly a wash at 4-3, +0.31u, so they slightly cost us.
- Nylander (skipped for falling TOI on an over) won, +0.87u. The cleared-but-unpriced sides went 1-2, -1.23u, so not getting a price helped.
- Stale-lineup skips (7) went 4-3, -0.32u at DK and +0.13u at shop-at, which is a wash. The 12h rule neither cost nor saved money.
- Role/slot vetoes (137, 2 ungraded) went 69-66, -7.83u. Demotion vetoes on overs saved the most (18-31, -14.32u). Promotion vetoes on unders cost +5.58u (25-15), and slot vetoes cost +0.91u.
- No vetoed side had a blend edge of 5 pts or more, so the vetoes never blocked an actual pick.
- CLV is near zero everywhere: +0.5 pts for Fliff skips, but +2.7 for the over-bias skips. The market drifted toward those overs and they still lost, so that's a small sample, not proof.
- 6 graded sides have no close (Oct 29 Goncalves and Ehlers, 4 vetoes). Flames at Oilers Oct 28 was missed. Nothing after 12:30 PM PT Oct 29 is graded.
