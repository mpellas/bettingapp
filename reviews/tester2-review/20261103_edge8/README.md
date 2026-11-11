# Edge 8+ investigation (Tester2, 2026-11-03)
Script: `edge8.py` (only reads /workspace/nhl-sog, box scores cached in box_cache/). Outputs: `posted_sides.csv` (127 posted Fliff-check sides Oct 17–Nov 2, first posting per date/player/side/line), `all_lean_sides.csv` (1,893 model lean sides from the final D file each day Oct 11–Nov 2), `tables.md` (all splits).
Edge = p_model(side) − DK no-vig(side) at the D snapshot; recomputed edge matches the posted "model +X pts" on all 127 rows. Units = 1u flat at DK list price. Close = latest DK line 0–30 min before puck drop (close.py rule, re-implemented without writing CLOSE.json).

## Key findings
1. Posted 8+ sides are NOT losing: 36-17 (67.9%), +10.9u (n=53, all 8–12 because of the 12-pt cap). The <8 posted sides are what lost: 33-41, −13.1u (n=74). Post-Oct 31, 8+ went 5-4, −0.2u (n=9, too small to tell).
2. On all model leans (n=1,893), 8+ sides lose a little: 173-154 (52.9%), −16.4u. The model says they should hit 62.8%. That's overconfidence; the market's no-vig (51.7%) is the better guess.
3. Most of that loss comes from `order_fallback` lines, where capture.py guessed which price is the over from the listing order instead of confirming it with the milestone price. 8+ order_fallback went 29-40 (42.0%), −16.6u, n=69; the model implied 62.7% (binomial p=0.0007). 8+ milestone lines went 144-114 (55.8%), +0.2u, n=258, against a model 62.8% (p=0.02). So most of the "big edges" on fallback lines are probably over/under labels swapped, not real edges. Posted lists already require milestone sides, which explains why posted 8+ looks fine.
4. Even on milestone lines the model is overconfident above 8 pts. 8–12: hit 56.0% vs model 61.5% (n=191). 12+: 55.2% vs 66.5% (n=67). Under 8 it's calibrated: <5 is 53.9% vs 52.6%, and 5–8 is 57.7% vs 57.6%.
5. Ruled out or not testable:
   - **Stale prices:** every posted side was priced from a snapshot taken at that pass (age at most a few minutes), so staleness doesn't explain anything.
   - **DailyFaceoff lineup age over 12h:** 8+ hit 70% when the lineup was older than 12h and 67% when it wasn't, so no effect.
   - **CLV:** 8+ sides whose close moved against us went 3-2 (n=5, too small). Across all leans, 8+ hit about 51% whether the close moved against us or not.
   - **Overs vs unders:** posted 8+ splits 8-4 overs and 28-13 unders, about the same. All-lean 8+ is 50% on overs (n=62) and 53.6% on unders (n=265).
   - **Line levels:** posted 8+ went 25-9 at 1.5 and 8-8 at 2.5 (n=16). All-lean 8+ is 51% at 1.5 and 56% at 2.5. No consistent pattern.
   - **D vs F:** posted 8+ went 12-2 for D and 24-15 for F. All-lean 8+ is 62% for D (+7.4u, n=69) and 50% for F (−23.8u, n=258). That points to the F leans, but it overlaps with the fallback effect.
   - **Low TOI (<14 min):** n=4, too small.
   - **Role change:** 8+ with a demotion went 4-1. Too small.
   - **Off-market:** can't really test. Every capture is DraftKings only (books=1), so "blended no-vig" is DK's own no-vig and there's no consensus line. The only second book is Fliff on 33 posted rows. 8+ where Fliff had the same line went 11-2. No posted 8+ side had a Fliff line different from DK's.

## Suggested next steps (not done, model untouched)
- Leave order_fallback lines out of any edge-based stat, or confirm their sides before trusting them.
- Shrink edges above 8 pts toward no-vig (a calibration cap). This needs the room's approval.
- Kane O1.5 at 17.7 was a paper-challenger pick, not a posted list side, so it's outside this table. The challenger's 8+ record is 0-1 (n=1).

## Caveats
- The samples are small and the sides aren't independent (same game, same night).
- 29 of 53 posted 8+ sides have no same-line close, because of the Oct 20–23 outage, Oct 29 VOID_noC, and pulled lines.
- Nov 2 results come from the live NHL.com API pull on Nov 3. Posted rows were deduplicated per date, and the first pass's prices were used.
- Bucket units are at DK list prices. Fliff checks were Fliff-price targets, so real units would differ.
