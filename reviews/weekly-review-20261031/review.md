# Weekly betting review — Sun Oct 25 to Sat Oct 31, 2026 (PT)
Built Sat Oct 31, 10:10 AM PT. Read-only, using nhl-sog sheets, graded and graded_overlay, card_decisions.csv, finalcall_done markers, fliff_prices, three_records, nfl-props track files and user_bets. No existing file was changed. Scripts: load.py, analyze.py, week.py, stats.py, season.py, season2.py (all in this folder).
P/L is 1u flat. **"Shop-at" P/L is hypothetical**: no book offered the shop-at price on any of these sides. "DK" P/L uses the DraftKings price that was actually listed. Every candidate had a shop-at price, so I didn't need any fallback price.

## 1. Counts
| day | sport | lists posted | candidate sides | FINAL CALL cards | cards with a bet | NO BETS cards |
|---|---|---|---|---|---|---|
| Sun 10/25 | NHL | 5 (9:22, 12:02, 1:06 empty, 2:04, 4:01 emptied by 2-of-7) | 7 (6 posted + DeBrusk removed by the gate) | 5 | 0 (12:02 was conditional: Schenn O1.5 only at Fliff +109 or better, never reached) | 4 + 1 conditional |
| Sun 10/25 | NFL | 1 (7:34 AM; DK/Fliff list empty; 2 PrizePicks legs) | 2 | 1 (marker 7:54 AM; card text isn't on the box) | unknown | unknown |
| Mon 10/26 | NHL | 4 (9:23 empty, no DK lines; 1:11, 2:38, 3:16) | 4 | 4 | 0 | 4 |
| Tue 10/27 | NHL | 6 (9:24 empty; 1:05, 1:39, 2:32, 3:33, 4:09) | 17 | 6 | 1 conditional (1:39 Scheifele O1.5 hold for PrizePicks; you played it) | 5 |
| Wed 10/28 | NHL | 3 (1:04, 3:09, 3:35) | 6 | 3 | 0 | 3 |
| Thu 10/29 | NHL | 1 (12:33) | 5 | 1 | 0 | 1 |
| Fri 10/30 | NHL | 0 (pipeline failed) | 0 | 0 | 0 | 0 |
| Sat 10/31 | NHL | 0 so far (only the 20261031_D capture) | 0 | 0 | 0 | 0 |
| **Week** | | **20 (19 NHL + 1 NFL)** | **41 (39 NHL + 2 NFL)** | **20** | **0 unconditional; 2 conditional** | **17 NHL + NFL unknown** |

NHL coverage: 25 of 37 completed games were scored (10/25 5/5, 10/26 3/3, 10/27 11/11, 10/28 3/4, 10/29 3/11, 10/30 0/3). Today's 10 games (10/31) are not included.

## 2. Skip reasons: 38 skipped NHL sides (+1 card play)
Buckets overlap: **30 of 38 skipped sides had more than one reason** (marked "multi" in the table). "Sole" means it was the only reason.
| bucket | sides | sole reason | W-L | P/L @ shop-at | P/L @ DK |
|---|---|---|---|---|---|
| No edge / below edge floor | 0 at candidate level (graded at board level in §4) | — | — | — | — |
| Price worse than shop-at | **38 (all)** | 8 | 19-19 | -1.79 | -4.11 |
| Fliff not posted / not offered at the line | 12 | 0 | 5-7 | -2.30 | -2.90 |
| TOI-up on an under | 7 | 0 | 3-4 | -1.00 | -1.40 |
| Stale lineup (>12h) | 7 | 0 | 4-3 | +0.13 | -0.32 |
| 2-of-7 gate | 1 | 0 | 1-0 | +0.74 | +0.62 |
| Missing two-checker clears / checker split | 10 | 0 | 3-7 | -4.00 | -4.39 |
| Window timing / missed window (incl. box outage) | 0 sides (12 games never scored, see §6) | — | — | — | — |
| Other (checker veto on overs or TOI-down, market-move NO BETS) | 6 | 0 | 3-3 | +0.23 | -0.18 |

Price was the binding filter. Every one of the 107 season candidates had a DK price worse than shop-at, which follows from how the list is built (a Fliff check means "no positive blended EV at DK"). Across 100 season Fliff checks, Fliff beat shop-at **0 times**. When Fliff did offer the side (29 times), its implied probability was on average 1.7 pts worse than DK.

## 3. Grades
### NHL: every candidate side (graded from shots; 10/29 graded through graded_overlay because the pinned grade is VOID_noC)
| list | game | side | DK / Fliff / shop-at | SOG | result | P/L shop-at | P/L DK | reasons |
|---|---|---|---|---|---|---|---|---|
| 1025-0922 | Florida Panthers@Chicago Blackhawks | Roman Kantserov U1.5 | +100 / — / +115 | 2 | L | -1.00 | -1.00 | price, fliff_np (multi) |
| 1025-1202 | New York Islanders@Dallas Stars | Brayden Schenn O1.5 | -105 / -110 / +109 | 2 | W | +1.09 | +0.95 | price |
| 1025-1202 | New York Islanders@Dallas Stars | Roope Hintz U2.5 | -185 / -190 / -157 | 2 | W | +0.64 | +0.54 | price |
| 1025-1202 | New York Islanders@Dallas Stars | Miro Heiskanen U1.5 | +130 / +110 / +145 | 4 | L | -1.00 | -1.00 | price, toi_up (multi) |
| 1025-1404 | Colorado Avalanche@Nashville Predators | Roman Josi O1.5 | -195 / — (Fliff had 2.5 only) / -164 | 4 | W | +0.61 | +0.51 | price, fliff_np (multi) |
| 1025-1404 | Colorado Avalanche@Nashville Predators | Sam Malinski U1.5 | -105 / -115 / +109 | 0 | W | +1.09 | +0.95 | price |
| 1025-1601 | Minnesota Wild@Vancouver Canucks | Jake DeBrusk U2.5 | -160 / — / -136 | 0 | W | +0.74 | +0.62 | 2of7, price (multi) |
| 1026-1311 | Los Angeles Kings@New York Rangers | Trevor Moore O1.5 | -145 / -165 / -123 | 0 | L | -1.00 | -1.00 | price, other (multi) |
| 1026-1311 | Los Angeles Kings@New York Rangers | Alex Laferriere U2.5 | -145 / -130 / -123 | 2 | W | +0.81 | +0.69 | price, toi_up (multi) |
| 1026-1438 | Toronto Maple Leafs@Calgary Flames | Darren Raddysh U2.5 | -125 / -125 / -107 | 3 | L | -1.00 | -1.00 | price, other (multi) |
| 1026-1516 | Detroit Red Wings@Edmonton Oilers | Kasperi Kapanen U1.5 | -110 / -115 / +105 | 1 | W | +1.05 | +0.91 | price, toi_up (multi) |
| 1027-1305 | Columbus Blue Jackets@Philadelphia Flyers | Travis Sanheim O1.5 | +110 / — / +124 | 2 | W | +1.24 | +1.10 | price, fliff_np, checker (multi) |
| 1027-1305 | Columbus Blue Jackets@Philadelphia Flyers | Christian Dvorak U1.5 | -120 / — / -105 | 4 | L | -1.00 | -1.00 | price, fliff_np, checker, toi_up (multi) |
| 1027-1305 | Columbus Blue Jackets@Philadelphia Flyers | Zach Werenski U3.5 | -160 / — / -137 | 1 | W | +0.73 | +0.62 | stale, price, fliff_np (multi) |
| 1027-1305 | Columbus Blue Jackets@Philadelphia Flyers | Alex Bump U1.5 | -105 / — / +107 | 5 | L | -1.00 | -1.00 | price, fliff_np, checker (multi) |
| 1027-1339 | Boston Bruins@Carolina Hurricanes | Logan Stankoven O2.5 | +110 / +105 / +125 | 1 | L | -1.00 | -1.00 | price |
| 1027-1339 | New Jersey Devils@Dallas Stars | Timo Meier O2.5 | -105 / — / +109 | 0 | L | -1.00 | -1.00 | stale, price (multi) |
| 1027-1339 | New Jersey Devils@Dallas Stars | Jesper Bratt O1.5 | -140 / — / -121 | 0 | L | -1.00 | -1.00 | stale, price (multi) |
| 1027-1339 | New Jersey Devils@Dallas Stars | Jack Hughes O2.5 | -150 / — / -127 | 6 | W | +0.79 | +0.67 | stale, price (multi) |
| 1027-1339 | Florida Panthers@Winnipeg Jets | Mark Scheifele O1.5 | -170 / — / -143 | 3 | W | +0.70 | +0.59 | CARD PLAY (hold_prizepicks) |
| 1027-1432 | Minnesota Wild@Utah Mammoth | Blake Coleman O1.5 | -135 / — / -117 | 5 | W | +0.85 | +0.74 | stale, price (multi) |
| 1027-1432 | Minnesota Wild@Utah Mammoth | Dylan Guenther U2.5 | +120 / — / +133 | 4 | L | -1.00 | -1.00 | price, fliff_np, checker (multi) |
| 1027-1533 | Ottawa Senators@Vegas Golden Knights | Tomas Hertl U2.5 | -160 / -180 / -138 | 2 | W | +0.72 | +0.62 | price |
| 1027-1533 | Vancouver Canucks@Anaheim Ducks | Jake DeBrusk U2.5 | -135 / — / -117 | 3 | L | -1.00 | -1.00 | stale, price (multi) |
| 1027-1533 | Vancouver Canucks@Anaheim Ducks | Jackson LaCombe U1.5 | +100 / -115 / +114 | 1 | W | +1.14 | +1.00 | price, toi_up (multi) |
| 1027-1533 | Vancouver Canucks@Anaheim Ducks | Drew O'Connor U1.5 | -155 / — / -132 | 1 | W | +0.76 | +0.65 | stale, price (multi) |
| 1027-1533 | Vancouver Canucks@Anaheim Ducks | Cutter Gauthier U3.5 | +105 / +100 / +120 | 4 | L | -1.00 | -1.00 | price, toi_up (multi) |
| 1027-1609 | Buffalo Sabres@San Jose Sharks | Jack Quinn U2.5 | -105 / -125 / +109 | 3 | L | -1.00 | -1.00 | price, toi_up (multi) |
| 1028-1304 | Philadelphia Flyers@Washington Capitals | Travis Sanheim O1.5 | +115 / +110 / +129 | 0 | L | -1.00 | -1.00 | price, checker, other (multi) |
| 1028-1304 | Philadelphia Flyers@Washington Capitals | Trevor Zegras O1.5 | -125 / -145 / -107 | 4 | W | +0.93 | +0.80 | price, checker, other (multi) |
| 1028-1304 | Philadelphia Flyers@Washington Capitals | Aliaksei Protas U1.5 | -120 / -115 / -103 | 3 | L | -1.00 | -1.00 | price |
| 1028-1509 | New Jersey Devils@Colorado Avalanche | Sam Malinski U1.5 | -140 / -140 / -121 | 3 | L | -1.00 | -1.00 | price |
| 1028-1535 | Toronto Maple Leafs@Seattle Kraken | William Nylander O2.5 | -115 / -130 / +101 | 3 | W | +1.01 | +0.87 | price, other (multi) |
| 1028-1535 | Toronto Maple Leafs@Seattle Kraken | Darren Raddysh U2.5 | -130 / -125 / -112 | 1 | W | +0.89 | +0.77 | price |
| 1029-1233 | Winnipeg Jets@Tampa Bay Lightning | Gage Goncalves U1.5 | -140 / — / -121 | 1 | W | +0.83 | +0.71 | price, fliff_np, checker (multi) |
| 1029-1233 | Utah Mammoth@Pittsburgh Penguins | MacKenzie Weegar O1.5 | -120 / — / -103 | 1 | L | -1.00 | -1.00 | price, fliff_np, checker (multi) |
| 1029-1233 | Utah Mammoth@Pittsburgh Penguins | Dylan Guenther U2.5 | +115 / — / +129 | 0 | W | +1.29 | +1.15 | price, fliff_np, other (multi) |
| 1029-1233 | Columbus Blue Jackets@Carolina Hurricanes | Nikolaj Ehlers O1.5 | -170 / — / -145 | 0 | L | -1.00 | -1.00 | price, fliff_np, checker (multi) |
| 1029-1233 | Columbus Blue Jackets@Carolina Hurricanes | Sebastian Aho O2.5 | -120 / — / -103 | 1 | L | -1.00 | -1.00 | price, fliff_np, checker (multi) |

| group | n | W-L | P/L @ shop-at | P/L @ DK | P/L @ best available (Fliff if better, else DK) |
|---|---|---|---|---|---|
| Skipped sides | 38 | 19-19 | -1.79 (-4.7%) | -4.11 (-10.8%) | -4.00 (-10.5%) |
| Card play (Scheifele O1.5) | 1 | 1-0 | +0.70 | +0.59 | — |
| All 39 candidates | 39 | 20-19 | — | -3.52 (-9.0%) | — |
| Skipped, DK price in the +110/-150 band | 27 | 12-15 | — | -4.84 | — |
| Skipped, DK price outside the band | 11 | 7-4 | — | +0.72 | — |
| Price-only skips (no other reason) | 8 | 5-3 | +1.43 | +0.84 | — |
| Skipped overs / unders | 15 / 23 | 7-8 / 12-11 | — | -2.36 / -1.75 | — |

By day, skipped sides at DK: 10/25 5-2 +1.58; 10/26 2-2 -0.40; 10/27 7-9 -3.60; 10/28 3-3 -0.56; 10/29 2-3 -1.14. Cross-check: the as-posted totals by date match graded/three_records.md (10/25 +0.96 without DeBrusk, 10/27 -3.01 including Scheifele). three_records' "(c) skipped" column uses only `skip` decision rows, so it leaves out the `no_bets` rows from 10/27 3:33 PM onward. That is why its totals differ from mine.

### NFL (paper only)
- The 10/25 PrizePicks legs, NYG@HOU: Mooney UNDER 19.5 rec yds (actual 4) **W**; McCarthy UNDER 24.5 rush yds (actual 1) **W**. No 1u price applies because these were PrizePicks-only. At DK/Fliff they were worse than the +104 shop-at (DK -113/-111, Fliff -120/-125), so they correctly stayed off the DK/Fliff list. The PrizePicks multiplier isn't logged, so I can't compute P/L.
- Week-7 prereg paper track (scored 10/31 5:22 AM PT): 286 D lines, 255 scored, 31 void, **0 bet_track bets**. Status INTERIM, label_raw FAIL. Top-20% hit rate 51.5% (n=33) vs a 53.5% bar.

### Your real bets
| date | app | entry | legs | result | P/L |
|---|---|---|---|---|---|
| Tue 10/27 | PrizePicks 2-pick | $1 to win $2.60 | Scheifele O1.5 SOG, FLA@WPG (3 SOG, card play) + Brunson O26.5 PRA (31) | **W** | +$1.60 |
| Wed 10/28 | Chalkboard 2-pick | $5 to win $15.65 | Protas **OVER** 1.5 SOG, PHI@WSH (3 SOG; off-card, opposite the model's UNDER, which lost) + Maxey O0.5 pts promo leg | **W** | +$10.65 |
| **Week** | | $6 staked | | 2-0 | **+$12.25** |
Scheifele CLV was -0.8 pts. No CLV is logged for the Protas over.

## 4. Filters: value lost vs money saved (graded at DK)
"Wins forgone" is the units the skipped winners would have paid. "Losses avoided" is the number of skipped losers (1u each). A negative net means the filter saved money. Any row under 100 graded sides is labeled a small sample, and that includes every candidate-level row.

**Candidate-level filters this week**
| filter | n | W-L | wins forgone | losses avoided | net P/L of skipped @ DK | verdict |
|---|---|---|---|---|---|---|
| Price worse than shop-at | 38 | 19-19 | +14.89 | 19 | -4.11 | saved 4.11u (small sample) |
| Fliff not posted | 12 | 5-7 | +4.10 | 7 | -2.90 | saved (small sample) |
| TOI-up on an under | 7 | 3-4 | +2.60 | 4 | -1.40 | saved (small sample) |
| Stale lineup | 7 | 4-3 | +2.68 | 3 | -0.32 | about even (small sample) |
| 2-of-7 gate | 1 | 1-0 | +0.62 | 0 | +0.62 | cost (n=1) |
| Checker missing / split | 10 | 3-7 | +2.61 | 7 | -4.39 | saved 4.39u (small sample) |
| Other checker vetoes | 6 | 3-3 | +2.82 | 3 | -0.18 | about even (small sample) |

**Season to date (sheets 10/17–10/29; no NHL sheets exist for 10/21–10/23), 107 candidates**
| test | n | W-L | P/L @ DK | ROI | label |
|---|---|---|---|---|---|
| All candidates @ DK (what was actually available) | 107 | 57-50 | -5.07 | -4.7% | small sample |
| All candidates @ shop-at (hypothetical) | 107 | 57-50 | +1.94 | +1.8% | small sample |
| Official card plays (three_records b-i) | 18 | 12-6 | +3.30 | — | small sample |
| Stale lineup >12h vs fresh ≤12h (102 with a known age) | 40 / 62 | 20-20 / 34-28 | -4.26 / -0.96 | -10.7% / -1.5% | small sample; supports the rule |
| Agreement ≤2 of 7 vs ≥3 | 6 / 101 | 3-3 / 54-47 | -0.86 / -4.21 | -14.3% / -4.2% | small sample |
| Unders with TOI up vs other unders | 12 / 58 | 7-5 / 35-23 | +0.49 / +4.16 | +4.1% / +7.2% | small sample; weak support |
| Overs vs unders | 37 / 70 | 15-22 / 42-28 | -9.72 / +4.65 | -26.3% / +6.6% | small sample |
| Edge 0–5 / 5–8 / 8–12 pts | 21 / 43 / 43 | 7-14 / 20-23 / 30-13 | -7.43 / -8.10 / +10.45 | -35% / -19% / +24% | small sample |
| Edge ≥8 and DK in the +110/-150 band | 32 | 24-8 | +11.82 | +36.9% | small sample; **post-hoc** (only 7-7 -1.10u this week) |
| DK in band vs outside band | 73 / 34 | 40-33 / 17-17 | -0.04 / -5.03 | -0.1% / -14.8% | small sample |

**Board-level filters: sides that never became candidates, graded at their DK price**
| filter (status_reason) | week n, W-L, P/L | season n, W-L, P/L, ROI | label |
|---|---|---|---|
| Edge below 5-pt floor (from 10/20) | 60, 28-32, -9.10 | 99, 51-48, -6.83, -6.9% | saved; small sample |
| Thin edge (before the floor) | 27, 12-15, -5.70 | 56, 28-28, -4.62, -8.2% | saved; small sample |
| Recent form doesn't beat no-vig | 117, 72-45, +18.00 | 299, 160-139, -2.80, -0.9% | week cost; season about even (season n≥100) |
| Role / lineup veto | 100, 48-52, -11.24 | 243, 122-121, -18.68, -7.7% | saved (n≥100) |
| Side not from milestone prices | 74, 38-36, -4.48 | 176, 85-91, -21.30, -12.1% | saved (n≥100) |
| Slot veto | 27, 17-10, +3.46 | 65, 37-28, +2.15, +3.3% | slight cost; small sample |
| Passes all checks, outside top 5 | 5, 1-4, -3.20 | 50, 30-20, +6.60, +13.2% | season cost; small sample |
| Model >12 pts from no-vig | 6, 4-2, +1.15 | 28, 18-10, +5.04, +18.0% | cost; small sample |
| Shop gate failed | 3, 3-0, +3.15 | 20, 10-10, -1.17, -5.9% | small sample |
| (Model not above no-vig: not a bet) | 368, -47.80 | 929, -102.53, -11.0% | — |

## 5. Paper-track changes to test (shadow trackers only; frozen rules unchanged)
1. **Shadow "DK at edge ≥8 in band".** Rule: on every window pass, log a 1u shadow bet at the listed DK price for any Fliff-check side with model minus no-vig ≥ 8.0 pts and a DK price between -150 and +110, even though DK is worse than shop-at. Deciding metrics: ROI at DK, plus mean CLV in pts vs the closing no-vig. Adopt only if ROI > 0 **and** mean CLV > 0 at **n ≥ 100 graded** (about 30 per season so far, so roughly 5–6 weeks). This targets the price filter, which blocked all 38 skips. The season number (24-8) is post-hoc and this week went 7-7, so it has to be proven forward.
2. **Shadow "unders only" (direction calibration, approved upgrade #4).** Rule: track candidate overs and unders separately at DK and shop-at. The shadow rule drops all overs. Deciding metric: ROI difference between unders and overs at DK, with CLV by direction. Act only at **n ≥ 100 graded per direction** (the season so far has 37 overs across 10 slate days). Season so far: overs 15-22 -26.3%, unders 42-28 +6.6%.
3. **Shadow "no top-5 cap".** Rule: also log sides marked "passes all checks but outside top 5 by edge" as shadow 1u at DK and shop-at. Deciding metric: ROI at DK vs the top-5 candidates over the same passes. Adopt at **n ≥ 100 graded** if ROI is at least as good as the top-5 group. Season so far: 50 sides 30-20 +6.60u (small sample).

Rules I'd leave alone, because this week they saved money: the checker split/missing-clears rule (3-7, saved 4.39u), TOI-up on unders, Fliff-not-posted, and the edge floor (board level -9.10u). The stale-lineup rule was about even this week but is backed by the season split.

## 6. Data gaps and ungradable items
- **Box/pipeline outage, Thu 10/29 ~12:35 PM to Sat 10/31 9:16 AM PT.** wake_log goes straight from 10/29 12:35 to 10/31 09:16 ("20261030 FAILED (no picks/20261030_D.csv)"). The NHL hourly wake and daily window pass failed 10/30. **12 NHL games were never scored and can't be graded**: 10/28 CGY@EDM 5:30 PM (box suspended ~1:39–2:40 PM); 10/29 CHI@DET 4:30, BOS@STL, WSH@NSH, MTL@DAL, NYI@MIN 5:00, BUF@ANA, OTT@LAK, VAN@SJS 7:00 PM; 10/30 NJD@VGK 3:00, WPG@FLA 4:00, SEA@CGY 5:00 PM.
- 10/29 pinned grade.py = 47 VOID_noC (no closing capture). The 5 candidates were graded from logged shots in graded_overlay, **with no CLV**.
- **NFL Mon/Thu captures and close failed 10/29**: snapshots stop 10/28 6:01 PM PT. TNF CAR@GB (401873023) was logged STALE_SNAPSHOT (decision snapshot 23h before kickoff). snap_2026_wk8_pulled.csv is header-only, and there is no wk08 summary yet.
- The NFL 10/25 7:34 card text isn't on the box (marker only), so its bet/NO BETS content is unknown.
- Voids this week: 10/26 1 VOID_dnp + 1 VOID_pulled_before_close; 10/27 1 VOID_dnp. None were candidates.
- The 10/16 BOSANA sheet isn't in the season board (filename pattern), and there are no NHL sheets for 10/21–10/23.
- Lineup-age, edge and agreement numbers come from the sheets and GATE files at list time. TOI-up and checker reasons come from card_decisions and room notes, not from code (those rules aren't coded).
- No CLV for the Chalkboard bet. PrizePicks multipliers for the NFL legs aren't logged.

## 7. College football
On hold since 10/31 at your direction: no CFB picks or paper slates this week. The last CFB leans are dated 10/24. The power-rating model is idle at /workspace/cfb-model/ (paper only, no demonstrated edge: 2026 OOS ATS 77-73, 51.3%).
