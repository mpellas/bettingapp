# Shot-attempts and game-total signals — Tester1, paper only (Nov 9, 2026)

Nothing in /workspace/nhl-sog was written. The 4-of-7 count is copied, never recomputed. These two tests sit beside it.

## Already in the champion model?
Yes, attempt *features* are already in champion c3ab760178: att_r5/10/30 and att60_r5/10/30 sit next to the SOG versions (see models/model_c3ab760178.json). The challenger also uses shr_att60. So the model already sees recent attempt volume. What it does *not* do is turn that into a stand-alone + / - vote, or use SOG-per-attempt regression as its own test. `totalShotAttempts` is already in every s20*.pkl (goals + SOG + missed + blocked by the shooter; 2021-22 filled from play-by-play). No new NHL fetch was needed for att.

Game totals are *not* in the captures (those hold only SOG and saves props). Live totals here are DraftKings open totals from ESPN's public odds feed, all 143 graded games, cached in cache/espn_totals.csv.

## Definitions (fixed in README.md before results; not changed after looking)
**att.** Last 10 games vs the 82 before that (need 10 / 30 / 15 attempts). Volume a = att/60 last-10 ÷ base − 1. Accuracy b = base SOG/att ÷ last-10 SOG/att − 1 (positive when recent finishing is *below* the player's own long-run rate). Each votes at a 10% band; over takes the sign of (va + vb), under flips. Conflicting or in-band = 0. Too little history, or a missing NHL id, is **n/a**, not a silent 0.

**total.** DraftKings open total: over '+' if ≥ 6.5, '−' if ≤ 5.5, 0 at 6.0. Under flips. A missing or failed feed is **n/a** (why text starts with "n/a"). Every live game in this sample had an open DK total; 90 were 6.5, 53 were 5.5, none were 6.0, so every live side voted.

**Install.** Copy tester1_extra.py next to evidence_extra.py and run `EXTRA.update(tester1_extra.EXTRA_T1)`. It matches the current interface (`f(r, side, ctx) -> (sign, why)`; sign in {+1, 0, −1}). Because the interface has no fourth value, unavailable rows still return sign 0, but the why always starts with `n/a (...)` and `tester1_extra.display` prints `n/a` on a sheet. Never a silent 0.

## Nov 5 12:39 sample (250 sides, 125 lines)
Sheet: 67 sides at 4+ of 7 (unchanged). Current EXTRA (hit, books, rest) makes an 'X of 10'. Adding att and total makes an 'X of 12'.

| count | sides (all 250) | of the 67 (4+ of 7) |
|---|---|---|
| 4+ of 7 | 67 | 67 |
| 6+ of 10 | 15 | 15 |
| 7+ of 12 | 17 | 17 |

Among the 67: att + 27, − 20, 0 15, **n/a 5**. total + 35, − 32, none n/a. books was 0 on every side (no Fliff pull before that pass, which is usual at sheet time). The four 6-of-7 sides: Keller O2.5 6 / 7 / 8 (att −, total +); Hutson U1.5 6 / 6 / 6 (att −, total −); Seider O1.5 6 / 7 / 7 (att −, total −); Martone O1.5 6 / 6 / 7 (att n/a — only 16 base games, total +). The five n/a sides on the 4+ list (not enough base games): Brandsegg-Nygard O, Kantserov U, Frondell O, Bonk U, Martone O. Full table: out/20261105_D_1239_of7_of10_of12.csv.

## Live backtest (DK decision prices, Oct 11–Nov 5)
2,265 posted lines / 4,530 sides, 143 games, final shots present, VOID_dnp and VOID_pulled_before_close dropped. VOID_noC is kept (has a shot count; no close is irrelevant to a D-price grade). Flat 1 unit at the captured DK price. Hit-rate CIs are Wilson 95%. Unit/ROI CIs are game-clustered bootstrap 95% (2,000 draws). The all-sides baseline is 50.0% hits and −0.070 ROI (vig). of_7 is known for 4,142 sides (all dates that have a sheet or the Oct 11–16 evidence file).

**att** (n/a split out; 133 of 2,265 lines / 5.9% were short of the 10 / 30 / 15 floors — mostly mid-season call-ups):

| group | sides | hit | 95% CI | ROI | 95% CI |
|---|---|---|---|---|---|
| att + | 1,443 | 51.7% | 49.1–54.3 | −0.045 | −0.093 to +0.006 |
| att − | 1,443 | 48.3% | 45.7–50.9 | −0.099 | −0.151 to −0.051 |
| att 0 (true neutral) | 1,378 | 50.0% | 47.4–52.6 | −0.068 | −0.076 to −0.059 |
| att n/a | 266 | 50.0% | 44.0–56.0 | −0.069 | −0.088 to −0.048 |
| att + overs | 693 | 48.2% | 44.5–51.9 | −0.092 | −0.165 to −0.022 |
| att − overs | 750 | 45.1% | 41.5–48.6 | −0.144 | −0.214 to −0.076 |
| att + unders | 750 | 54.9% | 51.4–58.5 | −0.001 | −0.066 to +0.069 |
| att − unders | 693 | 51.8% | 48.1–55.5 | −0.049 | −0.122 to +0.021 |

The + vs − gap is about 3.1 hit points on both the over and the under (game-clustered bootstrap CI roughly −2 to +8.5 pts; it crosses zero). Direction is the one the definition hoped for, but this is a small sample and not distinguishable from noise at 95%. Adding att to the 4-of-7 list does not help: 4+ of 7 is 53.8% / −0.029 ROI (1,057 sides); 4+ and att + is 53.6% / −0.035 (366); 5+ of 8 (7 + att) is 53.9% / −0.030 (547) — all overlapping.

**total** (every live game voted; 90 at 6.5, 53 at 5.5):

| group | sides | hit | 95% CI | ROI | 95% CI |
|---|---|---|---|---|---|
| total + | 2,265 | 49.1% | 47.0–51.1 | −0.084 | −0.125 to −0.043 |
| total − | 2,265 | 50.9% | 48.9–53.0 | −0.057 | −0.095 to −0.017 |
| total + overs (total ≥ 6.5) | 1,466 | 47.0% | 44.5–49.6 | −0.110 | −0.157 to −0.062 |
| total − overs (total ≤ 5.5) | 799 | 47.2% | 43.7–50.7 | −0.110 | −0.183 to −0.035 |
| 4+ of 7 & total + | 520 | 51.3% | 47.1–55.6 | −0.064 | −0.144 to +0.014 |
| 4+ of 7 & total − | 537 | 56.2% | 52.0–60.4 | +0.005 | −0.071 to +0.083 |
| 5+ of 8 (7 + total) | 661 | 53.1% | 49.3–56.9 | −0.039 | −0.113 to +0.033 |

On its own, total does nothing useful (overs hit 47.0% in high-total games and 47.2% in low-total games; the + vs − hit gap is −0.2 pts, CI covers zero). On the 4-of-7 list the *against*-the-total sides actually did a bit better (56.2% vs 51.3%), but that split is small and the CIs overlap. I would not add total to a majority from this.

**Majority counts, same 4,142 sides:**

| rule | sides | hit | 95% CI | ROI | 95% CI |
|---|---|---|---|---|---|
| 4+ of 7 | 1,057 | 53.8% | 50.8–56.8 | −0.029 | −0.086 to +0.029 |
| 6+ of 10 (current EXTRA) | 191 | 56.0% | 48.9–62.9 | +0.012 | −0.113 to +0.152 |
| 7+ of 12 (10 + att, total) | 223 | 52.9% | 46.4–59.4 | −0.035 | −0.154 to +0.091 |

The 6-of-10 and 7-of-12 lists are small (191 and 223 sides). Their CIs are wide and overlap the 4-of-7 list. This does not support changing the 4-of-7 list, or treating 7 of 12 as a new card rule.

## 2025-26 proxy (no prices; information only)
Line = floor(recent_mu) + 0.5, recent_mu = last-10 SOG per 60 × last-5 TOI / 60, as-of before the game. Over-hit rate and mean (actual − recent_mu). Eligible skater-games with enough att history: 40,218 in 1,312 games.

| att (over vote) | rows | over-hit | 95% CI | mean residual | 95% CI |
|---|---|---|---|---|---|
| + | 13,552 | 44.7% | 43.8–45.5 | −0.012 | −0.036 to +0.011 |
| 0 | 13,464 | 44.7% | 43.8–45.5 | −0.013 | −0.037 to +0.011 |
| − | 13,202 | 42.4% | 41.5–43.2 | −0.047 | −0.070 to −0.023 |

(The synthetic line sits a half-shot above recent_mu, so all over-hit rates sit under 50%. That is expected.) A − vote does go with slightly fewer shots than recent form (−0.047 residual, CI does not include 0). A + vote is not above recent form. So att is a weak, one-sided signal in a large sample: it flags a *down* attempt/finishing stretch a little better than an *up* one. It is not a pricing edge.

**total, same 2025-26 proxy.** 1,313 regular-season games pulled. 937 had a DraftKings total, 376 used ESPN BET (early season, labeled per game), 3 had no total (89 skater rows, marked n/a). Open totals: 685 at 6.5, 625 at 5.5, none at 6.0. Over-hit was 44.0% on high-total games and 43.9% on low-total games; mean residual −0.024 vs −0.023. No information. File: out/backtest_proxy_summary.csv.

## Caveats
- Small live sample (one month, 143 games). CIs are wide; nothing here is a basis for a live rule change.
- att overlaps the champion (and challenger) features, so some of its information is already in 'champ' / 'chal' / 'shrunk'.
- total almost never stays 0 (NHL totals are 5.5 or 6.5). It is a blunt, always-on vote.
- VOID_noC lines are graded at the D price only; there is no CLV in this test, on purpose.
- n/a is shown as 'n/a' in the sample file (att_show / total_show). In evidence_extra's sig_x_* column it still has to be '0' because of the interface; read the why text or the _show column.
- Bands and floors were written in README.md before any backtest number was computed. They were not retuned.

## Files
- /workspace/tester1-review/shot_attempts_20261109/README.md — definitions, frozen first
- tester1_extra.py — drop-in (`EXTRA_T1 = {att, total}`)
- att_signal.py, backtest.py, sample_nov5.py, fetch_totals.py, teams.py
- vendor/evidence_extra.py — current nhl-sog file, copied read-only
- out/20261105_D_1239_of7_of10_of12.csv — Nov 5 sample
- out/20261105_D_1239_att.csv — earlier att-only sample
- out/backtest_live_sides.csv, backtest_live_summary.csv, backtest_live_contrasts.csv
- out/backtest_proxy_att.csv — 2025-26 att proxy
- cache/espn_totals.csv — DK (or ESPN BET) open/close totals
