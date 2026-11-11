# Enhancement #1: drop the promotion veto on UNDERs (NHL SOG). Paper re-score, Oct 15-29, 2026
Method: a verified `cp -a` copy (nhl-sog_copy/), with diff -rq clean before running. I re-ran build_sheet.build_rows on every pass from Oct 15-29 twice, once as-is and once with role_veto_under cleared **only** where the role change is a promotion (mixed changes keep both vetoes). The other gates are unchanged: the sheet gates (model>no-vig, 5-pt floor, within 12, slot veto, milestone, shop/lineup, recent form, top-5), the 7-signal tally (<=2 skips), the 12h stale DFO lineup and the 20+ pt move. I kept the latest pass per player-game. Grades come from graded/ plus the NHL.com boxscore API for Oct 29.
The role veto first appears on Oct 17, so Oct 15-16 have no sides.

(a) 107 promotion-vetoed unders. **Only 6 would have made a list** (all as Fliff checks; none a DK bet). The other 101 were blocked by another gate. The first blockers: model not above no-vig 32, recent form 20, not milestone 13, >12 pts from no-vig 11, slot veto 9, 5-pt floor 7, outside top-5 4, stale lineup 3, thin edge 1, move 1.
(b) The 6 listed went **2-4, -2.87u at DK, -2.65u at shop-at**, with avg CLV +0.60 pts and 0 missing a close.
    All 107: 62-44 (1 ungraded), +4.65u DK (+4.4% ROI), +12.81u shop-at, avg CLV -0.97 pts, 1 missing a close.
    The 101 blocked: 60-40, +7.52u DK. That is where the "veto is costing us" money sits, and other gates would have stopped those sides anyway.
(c) Splits (all 107): edge <=0 23-10 +8.61u; 0-5 14-13 -1.11u; 5-10 22-9 +6.32u; 10+ 3-12 -9.16u.
    TOI rise (r5-r30) <=0 40-25 +5.44u; 0-1 10-7 +1.20u; 1-2 8-3 +3.80u; **2+ 4-9 -5.79u**.
    Periods: Oct 15-25 38-29 -0.05u and Oct 26-29 24-15 +4.71u. **They do not agree.** The listed 6 are 0-4 for Oct 15-25 and 2-0 for Oct 26-29. Per-date figures are in summary.txt.
(d) Bootstrap 95% CI on ROI (20k resamples). The listed 6: DK -47.9% [-100%, +5.1%]. All 107: DK +4.4% [-12.7%, +21.4%] and shop-at +12.1% [-6.3%, +30.3%]. **Every CI includes 0.** Only 6 sides would change the card, far short of ~100.
(e) Yinzer counted 116 graded (117 rows) at +9.93u. I get 109 promotion-only player-games plus 8 mixed = 117, so the counts match.
    The differences: (1) his count includes 8 mixed-change sides, whose under veto this change does not remove. (2) He took the first pass's price per date and I took the latest pass. (3) 2 sides (Kyrou, Chytil, Oct 17) appear only in 20261017_D_GATE.csv, whose picks file doesn't line up (build_sheet KeyError), so I dropped them.
    The key point is that his +9.93u counts every vetoed under as if it were bet. Only 6 would have passed the other gates.
(f) **Recommendation: keep the veto and shadow-track it.** Dropping it adds about 6 list sides in 2 weeks (2-4, -2.87u). The headline +9.93u comes from sides other gates already block.

Files: promo_under_sides.csv (one row per side, with blockers), raw_pass_rows.csv, summary.txt, rescore.py, analyze.py, and shadow_no_promo_under.py (shadow scorer, not scheduled).
