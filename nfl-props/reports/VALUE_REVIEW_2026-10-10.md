# Value review: nfl-props (and cfb-props): 2026-10-10 PT
Read-only review. No code changes, no hashed files touched, no Odds API credits used. The locked wk5–18 prereg (de029ac) is untouched.

## Where things stand
- Champion (LightGBM, num_leaves=7): CRPS 20.42 and MAE 28.86 on 2019–24, slightly better than the naive and public baselines. On real 2025 lines its MAE is about 28.7 vs the line's 27.6, so **the market forecasts better**. On the 2025 history the stacker's model weights c ≈ 0.03–0.05 (SE ≈ 0.08), so the model adds about nothing.
- The 2025 real-line holdout: 18 bets, −6.7% [−45%, +34%]. That's a null result.
- 2026 track: week 4 had 40 D lines and 18 scored, mean z-CLV ≈ −0.002, corr(model, line move) −0.08 (n tiny). The week 5 D file has 233 lines, but there's **no wk5 C file and no wk5 track yet**. ESPN/DK lines carry no prices (assumed −110), so ROI can't be measured. The power estimate is about 2,500 lines for a CLV decision, which takes most of the season.
- Ops: the supervisor is running and the last capture was 07:33 PT today (week 6). There's no cron on the box, so the supervisor and `ensure_capture.sh` are the only safety net. The Oct 8 TNF miss shows one dead process costs a game's evidence.

## Biggest gap
**The inputs, not the model or the testing.** The model sees only lagged box-score usage. The market sees injuries, depth-chart and role changes, and news, which is why it beats us by about 1 yard of MAE. There are also no prices, so even a correct model can't be measured on ROI or CLV-in-price.

## Is more backtesting the most valuable thing?
**No, not on simulated lines.** Tester1 showed the simulator can be learned (a decoder with no football model earns +11% on simulated lines and loses on real ones), so simulated ROI is meaningless. CRPS-on-actuals backtests are still fine for ranking models, but the champion already wins on that axis and it hasn't turned into edge. A backtest **on real historical prop lines with prices** would be valuable. That needs a data source (below), and right now only the 2025 ESPN lines exist (no prices, uncertain timing, already used as the holdout and stacker history).

## Cheap historical prop sources (web check, unverified vendor claims)
- **EndzoneAPI**: claims NFL props for 2023–2025 from 7 books (DK, FD, MGM, ESPN BET, Pinnacle, Bovada, BetOnline), open and close, keyed to nflverse ids. 500 free credits = 50 games; a full season is about 2,850 credits (~$19/mo Starter). It's the best fit if real; verify on a free sample first.
- **ParlayAPI**: free 1,000 requests/month, closing-line CSV per day (1 credit). They claim an archive back to 2022. There's a free 50k-row GitHub sample (2026 only).
- Hugging Face/other free sets: game lines only, no props.
- These don't touch the Odds API budget. Any 2025 data is training only. 2026 scoring stays on later weeks.

## Ranked next work
1. **Keep Sunday capture clean (Tester input 1).** Ops: an external watchdog for the supervisor (for example a scheduled `ensure_capture.sh` 3 h and 45 min before each kickoff window), an alert when the gap since the last capture exceeds 20 min near kickoff, and generating the wk5 C file and track scoring. Why: it's the only real out-of-sample evidence, and every miss is permanent. Effort: about 1–2 h. Cost: 0 credits.
2. **Market-as-model plus price shopping (Tester inputs 3 and 4).** On a few all-book Odds API pulls per week, compute a no-vig consensus (Pinnacle if returned) and flag books whose price is off from it by more than the vig. Test it as a shadow track against the closing line using our 2026 captures. Why: this is the only path to value that doesn't need us to beat the market as a forecaster; line shopping is real edge even with no model. It also gives the stacker real p_mkt instead of 0.5. Effort: about half a day. Cost: about 1 credit per market per region per event; 1 pull × ~14 games × 3 markets ≈ 40 credits/week. That exceeds the remaining ~419 over 12 weeks, so limit it to the Sunday main slate or about 2 markets (about 20–30 credits/week).
3. **Injury, role and news features (Tester input 2).** Use nflverse injuries (official status, practice participation), weekly depth charts, and the snap-share trend. Also an "teammate out" usage-redistribution feature. Trained as a challenger on 2025 plus pre-freeze 2026, scored as a shadow track on later weeks. Why: this is the identified gap between our MAE and the line's. Effort: 1–2 days, plus a leakage check (injury reports must be as-of the D snapshot; Friday reports only). Cost: free (nflverse).
4. **A real historical prop source for a priced backtest.** Pull a free EndzoneAPI/ParlayAPI sample, check it against our 2025 ESPN lines and 2026 captures, and decide whether ~$19 for 2023–25 is worth it. Why: it turns "backtesting" into something meaningful (thousands of priced lines with open and close, plus Pinnacle as a sharp reference) and gives enough power to test challengers. Effort: 2–4 h to evaluate. Cost: free tier; a possible ~$19.
5. **Market line as a feature / residual model.** Model actual − line (or use the line as an input) instead of predicting yards from scratch, so the model only has to learn where the market is wrong. It needs a priced history (item 4) or 2026 captures to train on. Effort: about 1 day once the data exists. Cost: 0 credits.

Not recommended now: more simulated-line backtests; more hyperparameter loops (the n_estimators challengers gained about 0.002 CRPS and didn't clear the margin); count markets (deferred, as agreed); expanding cfb-props (fine as a toy, but the price scan is a different problem; the earlier 22–28 cent filter finds a book's lean, not edge).
