# props-finder
Market-as-the-model + price shopping. Fair prob = median no-vig prob across sportsbooks (Pinnacle x3), exact same line only, >=3 books.
Bets listed only if EV>0 at your books (--books, default draftkings,fliff); all books feed consensus; DFS sites never feed consensus.
Pick'em: PrizePicks legs where the fair prob on the identical book line > --pickem-breakeven (0.542 6-flex; 0.577 2-power).
Estimate only (free):  python find.py --sport nfl --hours 6
Live pull:             python find.py --sport nfl --hours 6 --max-credits 80   (never goes below --floor 330)
Offline:               python find.py --sport ncaaf --offline /workspace/cfb-props/raw
Close hook:            python find.py --fill-close raw/<close_capture_dir>   -> fills close_price/clv_pct in bets_log.csv
Cost (verified 10/10, x-requests-last=1): 1 credit per market per event with the 10-book --bookmakers list. 3 markets = 3/event; --receptions = 4/event.

## analyze.py (added 10/10)
Sunday one-liner: `/workspace/props-finder/run_sunday.sh 5 76 --counts`  (floor 250; --counts = 6 credits/event)
Dry run, 0 credits: `/workspace/nfl-props/.venv/bin/python analyze.py --espn-dryrun`
find.py now also prints FILTER (a): one side between +100 and -150 with the two sides 22-28 cents apart (DK/Fliff).
analyze.py imports /workspace/nfl-props read-only (no refresh, nothing written there). Outputs analysis/*.csv + analysis_log_<tag>.csv.

## pickem.py: PrizePicks entry mode (added 10/11)
0 credits, reads saved raw pulls. NFL: `/workspace/nfl-props/.venv/bin/python pickem.py --raw raw/<dir> --sport nfl`; NHL: `python3 pickem.py --raw raw/<dir> --sport nhl`
(NHL pull: player_shots_on_goal + _alternate, 10-book list = 2 credits/event.) Standard lines only (goblins/demons skipped).
Books' no-vig at their own lines -> NB (counts, model k) / normal (yards, model s) mean-refit per book -> P(over/push/under) at PP's number;
median across books (one vote/book, Pinnacle x3), >=3 books else flagged. Blend 0.95 books / 0.05 model. Data-first vetoes.
Per-type break-even uses the leg's push prob; entry EV by exact 3^n enumeration; push = drop leg, pay next-smaller entry (1 left = refund).
Same-game legs blocked (one leg per game). Payouts: Power 2=3x,3=6x; Flex 3=3x/1x, 4=6x/1.5x, 5=10x/2x/.4x, 6=25x/2x/.4x (PP help center, 9/9/2026).
