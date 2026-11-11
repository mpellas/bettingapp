# Stale-lineup impact, 12:39 PM PT pass, Nov 3 2026 (read-only on nhl-sog)
Files: gate_nostale.csv (GATE copy with lineup_stale blanked and the stale reason stripped from shop_veto, shop_ok/dk_listable recomputed as in shop_gate.py), nostale.xlsx (build_sheet.py rerun on that copy), baseline.xlsx (rerun on the real GATE file; matches the live sheet), would_clear.csv, lineup_compare.csv (+ lineup_compare2.py).
## 1) Lineups
- DFO now: none of the 10 pages has updated since the 12:39 pull (same updatedAt). Every player slot in the GATE file matches DFO today.
- MIN, PHI, UTA (48h): DFO skaters match the Nov 1 boxscore exactly. X projections today (@32HockeyUpdates) match DFO lines. PHI L2/L3 are labelled the other way around (Martone-Cates-Michkov is 2nd on X, Foerster-Barkey-Tippett is 2nd on DFO).
- TOR, DAL, WSH, CBJ, NYR, WPG, TBL (25-27h): these DFO pages were updated Nov 2, after the last game. Differences:
  - TOR: matches the box and X (D pairs the same, order 1/2 swapped). Tavares is DTD in a non-contact jersey, so no change.
  - DAL: lines match X except Perron and Steel swapped (3rd vs 4th line). Faksa is in for Blackwell compared with Oct 31.
  - WSH: same trios, but X lists Tuch-Strome-Kyrou as L1 and A.Protas-Dubois-Wilson as L2 (DFO has them the other way). Liljegren is back from a maintenance day.
  - CBJ: forwards match X. X has Fabbro on D3 instead of Gudbranson.
  - NYR: matches X. Optional skate attendance is consistent.
  - WPG: CHANGED. X has Niederreiter-Rosen on the 4th line, where DFO has Koepke and Lambert, and Bauer is the extra D. The D pairs differ too: Ferraro-DeMelo and Fleury-Salomonsson on X, against Ferraro-Salomonsson and Fleury-DeMelo on DFO.
  - TBL: CHANGED on D. Crozier is scratched (DFO had him on D1). X pairs are Moser-Carlson, McDonagh-Cernak and Hedman-Lilleberg, with D'Astous extra. DFO had Carlson on D3 with PP2, D'Astous on D3 with PP1, and Hedman as D4.
- PP units: none of the X posts showed PP units, so they are not verified for any team.
## 2) Sides that clear every other gate with the stale check removed
Result: no DK bets (0, same as the live run). Two new sides enter the Fliff top 5, and they push out Snuggerud and Hanifin.
| side | game | edge | agree | DK | shop-at | role change? | after the second-pull gates (a0c77c3) |
|---|---|---|---|---|---|---|---|
| Oliver Bonk U1.5 | MIN at PHI | +9.8 | 4/7 | -160 | -134 | no (York-Bonk D2) | skipped: outside the -150 band |
| Wyatt Johnston U2.5 | DAL at WSH | +9.4 | 3/7 | -110 | +105 | no (L1, PP1 on DFO) | pull candidate: DK worse than shop-at, Fliff not posted |
Stale-team sides that pass every gate but fall outside the top 5 (edge, agreement, DK/shop-at): Sanheim O1.5 PHI (+8.0, 4, +115/+129), N.Paul U1.5 TOR (+6.9, 4, -130/-111), Trocheck O1.5 UTA (+6.7, 5, -135/-116), A.Protas U1.5 WSH (+6.4, 5, -125/-109; X shows him moving from L1 to L2), Dvorak U1.5 PHI (+5.6, 4, -125/-107), Rantanen U2.5 DAL (+5.3, 4, -170/-143), Point U2.5 TBL (+5.0, 4, -140/-120). No WPG or TBL defenceman made the list.
