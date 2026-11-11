# Nov 10, 2026 NHL SOG majority-list tally

Graded independently from the NHL public API (api-web.nhle.com boxscores; gameState FINAL/OFF). Work folder: `tester1-review/majority_tally_20261110/`. Report generated 2026-11-10 8:21 PM PT.

Sources: majority sides are rows with `agrees_n >= 4` on the frozen sheets `20261110_D_1304` (35), `_1339` (15), and `_1535` (10). Units are 1u risk at the **DK list price** and, separately, at `fliff_shop_at`. The price band uses **DK price** (inside if DK >= −150). Official SOG and game states are from the NHL gamecenter boxscore. `team_dfo` comes from the matching GATE files.

## Overall (tonight)

- **26-24**, 10 pending on 60 majority sides.
- Units at DK: **-1.49u** on 50 priced decided sides (hit 52.0%, 95% Wilson CI 38.5–65.2%).
- Units at shop-at: **+2.04u** on 50 priced decided sides.
- **NSH@LA is not final** (gameState LIVE, period 2 REG, clock 14:00). Its 10 sides are pending. The six earlier games are final.

## Price band (DK >= −150 is inside)

- Inside: 18-17, 4 pending (35 decided, hit 51.4%, 95% Wilson CI 35.6–67.0%; +0.97u) at DK; shop-at +3.59u.
- Outside (DK worse than −150): 8-7, 6 pending (15 decided, hit 53.3%, 95% Wilson CI 30.1–75.2%; -2.46u) at DK; shop-at -1.56u.

## By agrees_n (of 7)

- 4 of 7 (45 sides): 22-15, 8 pending (37 decided, hit 59.5%, 95% Wilson CI 43.5–73.7%; +4.28u) at DK; shop-at +7.28u.
- 5 of 7 (13 sides): 4-7, 2 pending (11 decided, hit 36.4%, 95% Wilson CI 15.2–64.6%; -3.77u) at DK; shop-at -3.25u.
- 6 of 7 (2 sides): 0-2 (2 decided, hit 0.0%, 95% Wilson CI 0.0–65.8%; -2.00u) at DK; shop-at -2.00u.
- 7 of 7: no sides.

## Over vs under

- OVER: 13-15, 6 pending (28 decided, hit 46.4%, 95% Wilson CI 29.5–64.2%; -3.72u) at DK; shop-at -1.92u.
- UNDER: 13-9, 4 pending (22 decided, hit 59.1%, 95% Wilson CI 38.7–76.7%; +2.23u) at DK; shop-at +3.96u.

## Per game

- Colorado Avalanche at Toronto Maple Leafs (9 sides): 4-5 (9 decided, hit 44.4%, 95% Wilson CI 18.9–73.3%; -1.83u) at DK; shop-at -1.27u.
- Minnesota Wild at Montreal Canadiens (8 sides): 3-5 (8 decided, hit 37.5%, 95% Wilson CI 13.7–69.4%; -1.84u) at DK; shop-at -1.39u.
- Washington Capitals at Ottawa Senators (8 sides): 6-2 (8 decided, hit 75.0%, 95% Wilson CI 40.9–92.9%; +3.63u) at DK; shop-at +4.45u.
- New Jersey Devils at Winnipeg Jets (10 sides): 7-3 (10 decided, hit 70.0%, 95% Wilson CI 39.7–89.2%; +2.12u) at DK; shop-at +2.95u.
- Florida Panthers at Columbus Blue Jackets (10 sides): 3-7 (10 decided, hit 30.0%, 95% Wilson CI 10.8–60.3%; -3.75u) at DK; shop-at -3.29u.
- Detroit Red Wings at St. Louis Blues (5 sides): 3-2 (5 decided, hit 60.0%, 95% Wilson CI 23.1–88.2%; +0.19u) at DK; shop-at +0.58u.
- Nashville Predators at Los Angeles Kings (10 sides): 0-0, 10 pending (0 decided, hit n/a; units n/a).

## Comparison with Yinzer's `majority/graded_sides.csv`

Yinzer's file has 60 Nov 10 rows (35+15+10). Results on the 50 decided sides from the six finished games **match this grade on result and actual SOG for every side.**

**Pending sides:** all 10 of Yinzer's pending rows are the 10 NSH@LA sides from the 1535 sheet (4 inside the band, 6 outside). None are from other games, none are missing or void, and none were deduped away. The 1535 sheet's 10 majority sides are exactly those 10 pending rows. A split of '6 NSH@LA plus 4 from other games' would be a misread of that 6-outside / 4-inside split; other games tonight are already settled in his file.

**Differences vs this grade:**

- Darren Raddysh UNDER 2.5 (Colorado Avalanche at Toronto Maple Leafs): units DK +0.800000 vs Yinzer +0.714286 (Yinzer price -140 from fliff; DK -125)

The only units difference is pricing, not the grade: this tally uses DK for units and the band; Yinzer's grader uses a posted Fliff price when Fliff offered the side, otherwise DK. Shop-at never sets his price or the band.

## Why results varied by game (n=50 decided; keep small)

Team expected SOG is each team's season-to-date shots-for per game **before Nov 10**, from the NHL stats API game-by-game team summary (`api.nhle.com/stats/rest/en/team/summary`, 2026–27 regular season). Listed-player `model_mu` sums are only the unique names on that game's sheet, not a full-team projection. Sample is 50 sides in 6 games; this is descriptive, not a rule change.

**Colorado Avalanche at Toronto Maple Leafs** — COL 6-3 TOR, SOG COL 28-31 TOR (combined 59), blowout; EN 6-3 at 17:30 3rd; PP 0/2 / 0/1; PIM 2-4. Majority record 4-5, -1.83u DK.
- Colorado Avalanche: 28 SOG vs 30.6 SF/G pre-game (-2.6 vs 30.6 SF/G pre), under-shot. volume down: overs 2-4, unders 1-1. listed players (n=8) model_mu sum 17.12 vs their actual SOG 14.
- Toronto Maple Leafs: 31 SOG vs 27.9 SF/G pre-game (+3.1 vs 27.9 SF/G pre), over-shot. volume up: overs 0-0, unders 1-0. listed players (n=1) model_mu sum 2.34 vs their actual SOG 2.

**Minnesota Wild at Montreal Canadiens** — MIN 2-1 MTL, SOG MIN 24-28 MTL (combined 52), OT; no empty-net goals; PP 1/3 / 0/2; PIM 6-8. Majority record 3-5, -1.84u DK.
- Minnesota Wild: 24 SOG vs 29.7 SF/G pre-game (-5.7 vs 29.7 SF/G pre), under-shot. volume down: overs 1-4, unders 0-0. listed players (n=5) model_mu sum 12.48 vs their actual SOG 10.
- Montreal Canadiens: 28 SOG vs 27.6 SF/G pre-game (+0.4 vs 27.6 SF/G pre), about average. volume near average: overs 1-0, unders 1-1. listed players (n=3) model_mu sum 6.00 vs their actual SOG 7.

**Washington Capitals at Ottawa Senators** — WSH 3-2 OTT, SOG WSH 17-26 OTT (combined 43), OT; no empty-net goals; PP 0/4 / 0/3; PIM 6-8. Majority record 6-2, +3.63u DK.
- Washington Capitals: 17 SOG vs 27.8 SF/G pre-game (-10.8 vs 27.8 SF/G pre), under-shot. volume down: overs 0-0, unders 5-0. listed players (n=5) model_mu sum 9.37 vs their actual SOG 3.
- Ottawa Senators: 26 SOG vs 25.7 SF/G pre-game (+0.3 vs 25.7 SF/G pre), about average. volume near average: overs 0-1, unders 1-1. listed players (n=3) model_mu sum 6.20 vs their actual SOG 4.

**Florida Panthers at Columbus Blue Jackets** — FLA 4-1 CBJ, SOG FLA 28-38 CBJ (combined 66), blowout; EN 4-1 at 17:44 3rd; PP 1/1 / 0/1; PIM 14-14. Majority record 3-7, -3.75u DK.
- Florida Panthers: 28 SOG vs 29.5 SF/G pre-game (-1.5 vs 29.5 SF/G pre), under-shot. volume down: overs 2-2, unders 0-0. listed players (n=4) model_mu sum 7.78 vs their actual SOG 6.
- Columbus Blue Jackets: 38 SOG vs 25.8 SF/G pre-game (+12.2 vs 25.8 SF/G pre), over-shot. volume up: overs 1-1, unders 0-4. listed players (n=6) model_mu sum 9.42 vs their actual SOG 13.

**Detroit Red Wings at St. Louis Blues** — DET 2-3 STL, SOG DET 32-33 STL (combined 65), one-goal; no empty-net goals; PP 0/1 / 0/1; PIM 7-7. Majority record 3-2, +0.19u DK.
- Detroit Red Wings: 32 SOG vs 28.8 SF/G pre-game (+3.2 vs 28.8 SF/G pre), over-shot. volume up: overs 2-0, unders 1-1. listed players (n=4) model_mu sum 6.95 vs their actual SOG 12.
- St. Louis Blues: 33 SOG vs 27.1 SF/G pre-game (+5.9 vs 27.1 SF/G pre), over-shot. volume up: overs 0-0, unders 0-1. listed players (n=1) model_mu sum 1.62 vs their actual SOG 3.

**New Jersey Devils at Winnipeg Jets** — NJD 2-4 WPG, SOG NJD 21-25 WPG (combined 46), 2-goal; EN 2-4 at 19:02 3rd; PP 0/4 / 2/4; PIM 10-8. Majority record 7-3, +2.12u DK.
- New Jersey Devils: 21 SOG vs 33.7 SF/G pre-game (-12.7 vs 33.7 SF/G pre), under-shot. volume down: overs 4-2, unders 1-0. listed players (n=7) model_mu sum 16.15 vs their actual SOG 12.
- Winnipeg Jets: 25 SOG vs 27.6 SF/G pre-game (-2.6 vs 27.6 SF/G pre), under-shot. volume down: overs 0-1, unders 2-0. listed players (n=3) model_mu sum 6.26 vs their actual SOG 1.

**Do wins track team shot volume?** In the two games where one team was clearly volume-starved, the unders on that team did the work: WSH took 17 SOG (vs ~pre-game SF/G below) and Washington unders went well; NJ took 21 at Winnipeg and Devil overs were mixed. CBJ *over*-shot (38) and still had mixed/losing overs among the majority sides, so volume alone does not explain every game. n=50 is too small and clustered by game to treat this as a missing defensive metric you can bet.

### Tester2's SOG figures

- WSH 17 SOG at OTT: official boxscore is WSH 17 (OTT 26). Matches.
- NJ 21 SOG at WPG: official boxscore is NJD 21 (WPG 25). Matches.
- CBJ 38 SOG vs FLA: official boxscore is CBJ 38 (FLA 28). Matches.
- DET@STL 65 combined: official boxscore is DET 32-33 STL = 65. Matches.

### Tonight's 50 decided sides: sig_opp, sig_lineup, sig_toi

'+' = the test agreed with the side, '−' = disagreed, '0' = neutral. Units at DK. n=50. Tonight `sig_lineup` is inverted (agreed 6-12, disagreed 12-3); that is still a small, game-clustered split and is not a rule.

**sig_opp**
- agreed: 14-15 (29 decided, hit 48.3%, 95% Wilson CI 31.4–65.6%; -2.34u) (rows=29).
- disagreed: 5-3 (8 decided, hit 62.5%, 95% Wilson CI 30.6–86.3%; +0.44u) (rows=8).
- neutral/0: 7-6 (13 decided, hit 53.8%, 95% Wilson CI 29.1–76.8%; +0.41u) (rows=13).

**sig_lineup**
- agreed: 6-12 (18 decided, hit 33.3%, 95% Wilson CI 16.3–56.3%; -6.97u) (rows=18).
- disagreed: 12-3 (15 decided, hit 80.0%, 95% Wilson CI 54.8–93.0%; +7.54u) (rows=15).
- neutral/0: 8-9 (17 decided, hit 47.1%, 95% Wilson CI 26.2–69.0%; -2.06u) (rows=17).

**sig_toi**
- agreed: 7-7 (14 decided, hit 50.0%, 95% Wilson CI 26.8–73.2%; -1.06u) (rows=14).
- disagreed: 4-2 (6 decided, hit 66.7%, 95% Wilson CI 30.0–90.3%; +2.72u) (rows=6).
- neutral/0: 15-15 (30 decided, hit 50.0%, 95% Wilson CI 33.2–66.8%; -3.15u) (rows=30).

### CBJ lineup was 28.7h stale — TOI vs recent average

All six Columbus majority sides (Coyle, Nichushkin, Olivier, Knies inside the band; Monahan and Kent Johnson outside). Last-5 / last-30 TOI are `toi_r5` / `toi_r30` from the 1339 GATE file; actual TOI is from the official boxscore.

- Charlie Coyle UNDER 1.5: actual TOI 15:15 (15.25 min) vs toi_r5 20.76 (-5.51), toi_r30 19.47 (-4.22); SOG 2.0, L  ** TOI differs from last-5 avg by 3+ min **
- Kent Johnson OVER 1.5: actual TOI 16:45 (16.75 min) vs toi_r5 19.08 (-2.33), toi_r30 14.78 (+1.97); SOG 0.0, L
- Mathieu Olivier UNDER 1.5: actual TOI 14:45 (14.75 min) vs toi_r5 16.09 (-1.34), toi_r30 14.37 (+0.38); SOG 2.0, L
- Matthew Knies UNDER 1.5: actual TOI 16:08 (16.13 min) vs toi_r5 18.18 (-2.05), toi_r30 18.43 (-2.29); SOG 2.0, L
- Sean Monahan UNDER 1.5: actual TOI 17:01 (17.02 min) vs toi_r5 14.99 (+2.03), toi_r30 16.12 (+0.89); SOG 3.0, L
- Valeri Nichushkin OVER 1.5: actual TOI 18:47 (18.78 min) vs toi_r5 17.90 (+0.88), toi_r30 16.46 (+2.32); SOG 4.0, W

Players whose actual TOI was 3+ minutes off the last-5 average are flagged above. A stale lineup can miss a role change, but a TOI miss of that size is still just a handful of skaters in one game.

## Cumulative (all majority-list decided sides in `graded_sides.csv`)

This uses Yinzer's official grader file for settled sides (price = Fliff if offered, else DK). **144 decided sides** (tonight's 50 finished plus Nov 5 and Nov 9). NSH@LA's 10 sides are not in this split. Sample is still modest and game-clustered; intervals are wide. No rule change is implied.

Overall official-price record on those 144: 71-73 (144 decided, hit 49.3%, 95% Wilson CI 41.3–57.4%; -15.09u).

Nick Robertson (BOS at PIT, Nov 5) had a blank `team_dfo` in the GATE file; his team was filled as Pittsburgh Penguins from the official boxscore (home team, nhl_id 8481582, 2 SOG). Accent-folded team names so Montreal / Montréal match the stats API.

### Overs split by opponent shots-allowed / game (season-to-date before game date)

86 decided overs; 86 have a pre-game opponent SA/G. Buckets are equal-count tertiles of those over sides (ties broken by rank). 'High SA' = more generous opponent (higher shots allowed). Units at the official grader price.

- low_SA (stingy): opponent SA/G 22.29–27.67 (n=29 sides): 16-13 (29 decided, hit 55.2%, 95% Wilson CI 37.5–71.6%; +1.55u).
- mid_SA: opponent SA/G 27.67–28.61 (n=28 sides): 13-15 (28 decided, hit 46.4%, 95% Wilson CI 29.5–64.2%; -3.47u).
- high_SA (generous): opponent SA/G 28.61–31.16 (n=29 sides): 11-18 (29 decided, hit 37.9%, 95% Wilson CI 22.7–56.0%; -10.35u).

Same overs, by whether `sig_opp` agreed with the side:

- Overs, sig_opp agreed (+): 12-25 (37 decided, hit 32.4%, 95% Wilson CI 19.6–48.5%; -15.02u).
- Overs, sig_opp disagreed (-): 9-9 (18 decided, hit 50.0%, 95% Wilson CI 29.0–71.0%; -2.60u).
- Overs, sig_opp neutral (0): 19-12 (31 decided, hit 61.3%, 95% Wilson CI 43.8–76.3%; +5.35u).

All decided sides (overs and unders), sig_opp:

- agreed (+): 25-41 (66 decided, hit 37.9%, 95% Wilson CI 27.1–49.9%; -20.28u).
- disagreed (-): 16-13 (29 decided, hit 55.2%, 95% Wilson CI 37.5–71.6%; -1.49u).
- neutral (0): 30-19 (49 decided, hit 61.2%, 95% Wilson CI 47.2–73.6%; +6.68u).

Point estimates go the **opposite** way of a simple 'overs do better against generous defenses' story: overs vs stingier opponents were better than overs vs more generous ones, and overs where `sig_opp` agreed were worse than disagreed or neutral. The 95% CIs still overlap across buckets, so this does not establish a reliable pattern. It also does not support adding or trusting a defensive-metric rule at this sample size.

### Pre-game team shot-volume projection (with vs against the side)

For each side, projection = average of (shooter's team season SOG/game) and (opponent's season SOG-allowed/game), both strictly before that game's date. It **points OVER** if the projection is above the league-average SOG/game through the prior day, and **UNDER** if below. 'With' means the side matches that direction. Units at the official grader price.

- Projection **with** the side (95 sides): 44-51 (95 decided, hit 46.3%, 95% Wilson CI 36.6–56.3%; -17.30u). Overs: 26-31 (57 decided, hit 45.6%, 95% Wilson CI 33.4–58.4%; -10.02u). Unders: 18-20 (38 decided, hit 47.4%, 95% Wilson CI 32.5–62.7%; -7.28u).
- Projection **against** the side (49 sides): 27-22 (49 decided, hit 55.1%, 95% Wilson CI 41.3–68.1%; +2.21u). Overs: 14-15 (29 decided, hit 48.3%, 95% Wilson CI 31.4–65.6%; -2.24u). Unders: 13-7 (20 decided, hit 65.0%, 95% Wilson CI 43.3–81.9%; +4.45u).
- Sides with no direction (missing rates or projection exactly equal to the league average): 0.

Sides that went with the projection were not better than sides that went against it (CIs overlap). Same caution as above: this is descriptive, not a filter.

## Full side list (tonight)

| List | Game | Player | Team (DFO) | Side | Line | DK | Shop-at | Band | n/7 | Actual SOG | Result | u DK | u shop |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 20261110_1304 | Colorado Avalanche at Toronto Maple Leafs | Brent Burns | Colorado Avalanche | OVER | 1.5 | -130 | -110 | in | 4 | 1 | L | -1.00 | -1.00 |
| 20261110_1304 | Colorado Avalanche at Toronto Maple Leafs | Brock Nelson | Colorado Avalanche | OVER | 1.5 | -135 | -115 | in | 4 | 1 | L | -1.00 | -1.00 |
| 20261110_1304 | Colorado Avalanche at Toronto Maple Leafs | Cale Makar | Colorado Avalanche | OVER | 2.5 | -155 | -128 | out | 4 | 1 | L | -1.00 | -1.00 |
| 20261110_1304 | Colorado Avalanche at Toronto Maple Leafs | Darren Raddysh | Toronto Maple Leafs | UNDER | 2.5 | -125 | -107 | in | 4 | 2 | W | +0.80 | +0.93 |
| 20261110_1304 | Colorado Avalanche at Toronto Maple Leafs | Devon Toews | Colorado Avalanche | OVER | 1.5 | -150 | -124 | in | 4 | 2 | W | +0.67 | +0.81 |
| 20261110_1304 | Colorado Avalanche at Toronto Maple Leafs | Martin Necas | Colorado Avalanche | UNDER | 2.5 | -120 | -103 | in | 4 | 2 | W | +0.83 | +0.97 |
| 20261110_1304 | Colorado Avalanche at Toronto Maple Leafs | Nazem Kadri | Colorado Avalanche | OVER | 2.5 | -115 | 102 | in | 4 | 5 | W | +0.87 | +1.02 |
| 20261110_1304 | Colorado Avalanche at Toronto Maple Leafs | Sam Malinski | Colorado Avalanche | UNDER | 1.5 | 115 | 131 | in | 4 | 2 | L | -1.00 | -1.00 |
| 20261110_1304 | Colorado Avalanche at Toronto Maple Leafs | T.J. Hughes | Colorado Avalanche | OVER | 2.5 | 125 | 143 | in | 5 | 0 | L | -1.00 | -1.00 |
| 20261110_1304 | Minnesota Wild at Montreal Canadiens | Alexandre Texier | Montreal Canadiens | UNDER | 1.5 | -125 | -106 | in | 4 | 3 | L | -1.00 | -1.00 |
| 20261110_1304 | Minnesota Wild at Montreal Canadiens | Blake Coleman | Minnesota Wild | OVER | 1.5 | -145 | -123 | in | 4 | 1 | L | -1.00 | -1.00 |
| 20261110_1304 | Minnesota Wild at Montreal Canadiens | Bobby Brink | Minnesota Wild | OVER | 1.5 | 130 | 147 | in | 4 | 5 | W | +1.30 | +1.47 |
| 20261110_1304 | Minnesota Wild at Montreal Canadiens | Joel Eriksson Ek | Minnesota Wild | OVER | 2.5 | -130 | -110 | in | 5 | 2 | L | -1.00 | -1.00 |
| 20261110_1304 | Minnesota Wild at Montreal Canadiens | Juraj Slafkovsky | Montreal Canadiens | UNDER | 2.5 | -180 | -150 | out | 4 | 1 | W | +0.56 | +0.67 |
| 20261110_1304 | Minnesota Wild at Montreal Canadiens | Kirill Kaprizov | Minnesota Wild | OVER | 2.5 | -175 | -147 | out | 5 | 1 | L | -1.00 | -1.00 |
| 20261110_1304 | Minnesota Wild at Montreal Canadiens | Nick Suzuki | Montreal Canadiens | OVER | 2.5 | 130 | 147 | in | 4 | 3 | W | +1.30 | +1.47 |
| 20261110_1304 | Minnesota Wild at Montreal Canadiens | Quinn Hughes | Minnesota Wild | OVER | 2.5 | 120 | 137 | in | 5 | 1 | L | -1.00 | -1.00 |
| 20261110_1304 | New Jersey Devils at Winnipeg Jets | Cole Perfetti | Winnipeg Jets | UNDER | 2.5 | -130 | -115 | in | 4 | 0 | W | +0.77 | +0.87 |
| 20261110_1304 | New Jersey Devils at Winnipeg Jets | Dougie Hamilton | New Jersey Devils | OVER | 2.5 | 140 | 157 | in | 4 | 1 | L | -1.00 | -1.00 |
| 20261110_1304 | New Jersey Devils at Winnipeg Jets | Evan Rodrigues | New Jersey Devils | OVER | 1.5 | 100 | 114 | in | 4 | 2 | W | +1.00 | +1.14 |
| 20261110_1304 | New Jersey Devils at Winnipeg Jets | Gabriel Vilardi | Winnipeg Jets | UNDER | 1.5 | 115 | 131 | in | 4 | 1 | W | +1.15 | +1.31 |
| 20261110_1304 | New Jersey Devils at Winnipeg Jets | Jesper Bratt | New Jersey Devils | OVER | 1.5 | -190 | -158 | out | 5 | 2 | W | +0.53 | +0.63 |
| 20261110_1304 | New Jersey Devils at Winnipeg Jets | Luke Evangelista | New Jersey Devils | OVER | 1.5 | -190 | -158 | out | 4 | 3 | W | +0.53 | +0.63 |
| 20261110_1304 | New Jersey Devils at Winnipeg Jets | Luke Hughes | New Jersey Devils | OVER | 1.5 | -195 | -160 | out | 4 | 0 | L | -1.00 | -1.00 |
| 20261110_1304 | New Jersey Devils at Winnipeg Jets | Mark Scheifele | Winnipeg Jets | OVER | 1.5 | -195 | -160 | out | 5 | 0 | L | -1.00 | -1.00 |
| 20261110_1304 | New Jersey Devils at Winnipeg Jets | Nico Hischier | New Jersey Devils | UNDER | 2.5 | -185 | -152 | out | 4 | 1 | W | +0.54 | +0.66 |
| 20261110_1304 | New Jersey Devils at Winnipeg Jets | Timo Meier | New Jersey Devils | OVER | 2.5 | -165 | -141 | out | 5 | 3 | W | +0.61 | +0.71 |
| 20261110_1304 | Washington Capitals at Ottawa Senators | Aliaksei Protas | Washington Capitals | UNDER | 1.5 | -135 | -116 | in | 4 | 1 | W | +0.74 | +0.86 |
| 20261110_1304 | Washington Capitals at Ottawa Senators | Drake Batherson | Ottawa Senators | UNDER | 2.5 | -180 | -152 | out | 4 | 1 | W | +0.56 | +0.66 |
| 20261110_1304 | Washington Capitals at Ottawa Senators | Dylan Strome | Washington Capitals | UNDER | 1.5 | 110 | 126 | in | 4 | 0 | W | +1.10 | +1.26 |
| 20261110_1304 | Washington Capitals at Ottawa Senators | Jakob Chychrun | Washington Capitals | UNDER | 2.5 | -120 | -103 | in | 4 | 2 | W | +0.83 | +0.97 |
| 20261110_1304 | Washington Capitals at Ottawa Senators | Jordan Kyrou | Washington Capitals | UNDER | 1.5 | 140 | 155 | in | 4 | 0 | W | +1.40 | +1.55 |
| 20261110_1304 | Washington Capitals at Ottawa Senators | Ridly Greig | Ottawa Senators | UNDER | 1.5 | -125 | -106 | in | 4 | 2 | L | -1.00 | -1.00 |
| 20261110_1304 | Washington Capitals at Ottawa Senators | Tim Stutzle | Ottawa Senators | OVER | 2.5 | 135 | 150 | in | 4 | 1 | L | -1.00 | -1.00 |
| 20261110_1304 | Washington Capitals at Ottawa Senators | Tom Wilson | Washington Capitals | UNDER | 1.5 | 100 | 115 | in | 5 | 0 | W | +1.00 | +1.15 |
| 20261110_1339 | Detroit Red Wings at St. Louis Blues | Andrew Copp | Detroit Red Wings | UNDER | 1.5 | -125 | -107 | in | 4 | 3 | L | -1.00 | -1.00 |
| 20261110_1339 | Detroit Red Wings at St. Louis Blues | Emmitt Finnie | Detroit Red Wings | OVER | 1.5 | -155 | -129 | out | 4 | 2 | W | +0.65 | +0.78 |
| 20261110_1339 | Detroit Red Wings at St. Louis Blues | Michael Brandsegg-Nygard | Detroit Red Wings | UNDER | 1.5 | -105 | 110 | in | 4 | 1 | W | +0.95 | +1.10 |
| 20261110_1339 | Detroit Red Wings at St. Louis Blues | Moritz Seider | Detroit Red Wings | OVER | 1.5 | -170 | -141 | out | 4 | 6 | W | +0.59 | +0.71 |
| 20261110_1339 | Detroit Red Wings at St. Louis Blues | Pavel Buchnevich | St. Louis Blues | UNDER | 1.5 | -110 | 106 | in | 4 | 3 | L | -1.00 | -1.00 |
| 20261110_1339 | Florida Panthers at Columbus Blue Jackets | Aaron Ekblad | Florida Panthers | OVER | 1.5 | 135 | 150 | in | 4 | 0 | L | -1.00 | -1.00 |
| 20261110_1339 | Florida Panthers at Columbus Blue Jackets | Carter Verhaeghe | Florida Panthers | OVER | 2.5 | 110 | 126 | in | 5 | 4 | W | +1.10 | +1.26 |
| 20261110_1339 | Florida Panthers at Columbus Blue Jackets | Charlie Coyle | Columbus Blue Jackets | UNDER | 1.5 | 100 | 115 | in | 4 | 2 | L | -1.00 | -1.00 |
| 20261110_1339 | Florida Panthers at Columbus Blue Jackets | Gustav Forsling | Florida Panthers | OVER | 1.5 | 120 | 136 | in | 4 | 2 | W | +1.20 | +1.36 |
| 20261110_1339 | Florida Panthers at Columbus Blue Jackets | Kent Johnson | Columbus Blue Jackets | OVER | 1.5 | -165 | -135 | out | 4 | 0 | L | -1.00 | -1.00 |
| 20261110_1339 | Florida Panthers at Columbus Blue Jackets | Mathieu Olivier | Columbus Blue Jackets | UNDER | 1.5 | -120 | -102 | in | 5 | 2 | L | -1.00 | -1.00 |
| 20261110_1339 | Florida Panthers at Columbus Blue Jackets | Matthew Knies | Columbus Blue Jackets | UNDER | 1.5 | -120 | -106 | in | 5 | 2 | L | -1.00 | -1.00 |
| 20261110_1339 | Florida Panthers at Columbus Blue Jackets | Sean Monahan | Columbus Blue Jackets | UNDER | 1.5 | -175 | -147 | out | 6 | 3 | L | -1.00 | -1.00 |
| 20261110_1339 | Florida Panthers at Columbus Blue Jackets | Seth Jones | Florida Panthers | OVER | 1.5 | -155 | -131 | out | 6 | 0 | L | -1.00 | -1.00 |
| 20261110_1339 | Florida Panthers at Columbus Blue Jackets | Valeri Nichushkin | Columbus Blue Jackets | OVER | 1.5 | -105 | 109 | in | 4 | 4 | W | +0.95 | +1.09 |
| 20261110_1535 | Nashville Predators at Los Angeles Kings | Adam Wilsby | Nashville Predators | UNDER | 1.5 | -180 | -154 | out | 4 |  | pending |  |  |
| 20261110_1535 | Nashville Predators at Los Angeles Kings | Adrian Kempe | Los Angeles Kings | UNDER | 3.5 | -170 | -141 | out | 4 |  | pending |  |  |
| 20261110_1535 | Nashville Predators at Los Angeles Kings | Alex Laferriere | Los Angeles Kings | OVER | 2.5 | -165 | -136 | out | 4 |  | pending |  |  |
| 20261110_1535 | Nashville Predators at Los Angeles Kings | Artemi Panarin | Los Angeles Kings | OVER | 2.5 | -175 | -147 | out | 5 |  | pending |  |  |
| 20261110_1535 | Nashville Predators at Los Angeles Kings | Brandt Clarke | Los Angeles Kings | UNDER | 1.5 | 110 | 124 | in | 4 |  | pending |  |  |
| 20261110_1535 | Nashville Predators at Los Angeles Kings | Corey Perry | Los Angeles Kings | OVER | 1.5 | -130 | -109 | in | 4 |  | pending |  |  |
| 20261110_1535 | Nashville Predators at Los Angeles Kings | Mavrik Bourque | Nashville Predators | UNDER | 2.5 | -155 | -135 | out | 5 |  | pending |  |  |
| 20261110_1535 | Nashville Predators at Los Angeles Kings | Quinton Byfield | Los Angeles Kings | OVER | 2.5 | -105 | 112 | in | 4 |  | pending |  |  |
| 20261110_1535 | Nashville Predators at Los Angeles Kings | Scott Laughton | Los Angeles Kings | OVER | 1.5 | 145 | 161 | in | 4 |  | pending |  |  |
| 20261110_1535 | Nashville Predators at Los Angeles Kings | Trevor Moore | Los Angeles Kings | OVER | 1.5 | -155 | -133 | out | 4 |  | pending |  |  |

CSV: `tonight_majority_graded.csv`.

