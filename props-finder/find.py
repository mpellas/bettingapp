#!/usr/bin/env python3
"""Props finder: market-as-the-model + price shopping.
Fair prob = median no-vig prob across books (Pinnacle weighted x3 if present), same exact line only.
EV = fair_prob * decimal_payout - 1.  Lists only EV>0 bets priced by >=3 books (no padding)."""
import argparse, csv, datetime as dt, glob, json, os, statistics, sys, urllib.request
from zoneinfo import ZoneInfo
PT = ZoneInfo("America/Los_Angeles")
SPORTS = {"nfl": "americanfootball_nfl", "ncaaf": "americanfootball_ncaaf", "cfb": "americanfootball_ncaaf"}
BASE_MKTS = ["player_pass_yds", "player_rush_yds", "player_reception_yds"]
COUNT_MKTS = ["player_receptions", "player_pass_completions", "player_rush_attempts"]
SHARP = {"pinnacle": 3}
DFS = {"prizepicks","underdog","pick6","dabble_us_dfs","betr_us_dfs"}  # lines only, not real odds: excluded from consensus
DEFAULT_BOOKS = "draftkings,fliff"
# 10 books = billed as 1 region. williamhill_us (Caesars) is paid-plan only, so betrivers instead.
DEFAULT_BOOKMAKERS = "draftkings,fanduel,betmgm,betrivers,pinnacle,fliff,prizepicks,betonlineag,bovada,espnbet"
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "bets_log.csv")
LOG_COLS = ["logged_at_utc","sport","event_id","game","kickoff_pt","player","market","line","side","book","price","fair_prob","fair_price","ev_pct","n_books","close_price","close_fair_prob","clv_pct"]

def key():
    k = os.environ.get("ODDS_API_KEY")
    if not k:
        k = open("/workspace/nfl-props/data/secrets/odds_api_key").read().strip()
    return k

def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        h = {k.lower(): v for k, v in r.headers.items()}
        return json.load(r), h

def dec(a): return 1 + (a / 100 if a > 0 else 100 / -a)
def imp(a): return 1 / dec(a)
def amer(p):
    if p <= 0 or p >= 1: return None
    return round(-100 * p / (1 - p)) if p >= .5 else round(100 * (1 - p) / p)

def analyze(events, books_allow=None, min_books=3, pick=None):
    rows = []
    pick = [] if pick is None else pick
    for ev in events:
        game = f"{ev['away_team']} @ {ev['home_team']}"
        ko = dt.datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00")).astimezone(PT)
        props = {}  # (player, market, line) -> {book: {Over: price, Under: price}}
        dfs = {}  # (player, market, line) -> {dfs_book: set(sides)}
        for b in ev.get("bookmakers", []):
            if b["key"] in DFS:
                for m in b["markets"]:
                    if m["key"].endswith("_alternate"): continue  # goblins/demons
                    for o in m["outcomes"]:
                        if o.get("point") is not None:
                            dfs.setdefault((o.get("description"), m["key"], float(o["point"])), {}).setdefault(b["key"], set()).add(o["name"])
                continue
            for m in b["markets"]:
                for o in m["outcomes"]:
                    if o.get("point") is None: continue
                    k = (o.get("description"), m["key"], float(o["point"]))
                    props.setdefault(k, {}).setdefault(b["key"], {})[o["name"]] = o["price"]
        lines_per = {}
        for (pl, mk, ln) in props: lines_per.setdefault((pl, mk), set()).add(ln)
        for (pl, mk, ln), bk in props.items():
            two = {b: s for b, s in bk.items() if "Over" in s and "Under" in s}
            if len(two) < min_books: continue
            fair = []
            for b, s in two.items():
                po, pu = imp(s["Over"]), imp(s["Under"])
                fair += [po / (po + pu)] * SHARP.get(b, 1)
            fo = statistics.median(fair)
            for db in dfs.get((pl, mk, ln), {}):
                for side, fp in (("Over", fo), ("Under", 1 - fo)):
                    pick.append(dict(event_id=ev["id"], game=game, kickoff_pt=ko.strftime("%a %-I:%M %p PT"), player=pl,
                        market=mk.replace("player_", ""), line=ln, side=side, book=db, price="", fair_prob=round(fp, 4),
                        fair_price=amer(fp), ev_pct="", n_books=len(two), alt_lines=""))
            alts = sorted(lines_per[(pl, mk)] - {ln})
            for side, fp in (("Over", fo), ("Under", 1 - fo)):
                cands = [(b, s[side]) for b, s in two.items() if not books_allow or b in books_allow]
                if not cands: continue
                b, pr = max(cands, key=lambda x: dec(x[1]))
                rows.append(dict(event_id=ev["id"], game=game, kickoff_pt=ko.strftime("%a %-I:%M %p PT"),
                    player=pl, market=mk.replace("player_", ""), line=ln, side=side, book=b, price=pr,
                    fair_prob=round(fp, 4), fair_price=amer(fp), ev_pct=round((fp * dec(pr) - 1) * 100, 2),
                    n_books=len(two), alt_lines=",".join(map(str, alts))))
    return sorted(rows, key=lambda r: -r["ev_pct"])

def cents(p): return abs(p) - 100 if p < 0 else 100 - p

def tilt_filter(events, books_allow=None, lo=22, hi=28, min_p=-150, max_p=100):
    """Mode (a), the user's original filter: one side priced between -150 and +100 and |cents(over)-cents(under)| in
    [lo, hi], triggered at ANY sportsbook. Every listed bet is re-priced at the user's own books (books_allow, default
    DraftKings/Fliff): the best user-book line for that side (Over: lowest line, Under: highest; then best price).
    Dropped if no user book has the player/market or the user-book line is worse for that side than the trigger line."""
    allow = books_allow or set(DEFAULT_BOOKS.split(","))
    out, seen = [], set()
    for ev in events:
        game = f"{ev['away_team']} @ {ev['home_team']}"
        ko = dt.datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00")).astimezone(PT)
        mine = {}  # (player, market) -> [(book, line, {Over, Under})]
        trig = []
        for b in ev.get("bookmakers", []):
            if b["key"] in DFS: continue
            for m in b["markets"]:
                pr = {}
                for o in m["outcomes"]:
                    if o.get("point") is None: continue
                    pr.setdefault((o.get("description"), float(o["point"])), {})[o["name"]] = o["price"]
                for (pl, ln), sd in pr.items():
                    if "Over" not in sd or "Under" not in sd: continue
                    if b["key"] in allow: mine.setdefault((pl, m["key"]), []).append((b["key"], ln, sd))
                    gap = abs(cents(sd["Over"]) - cents(sd["Under"]))
                    if not lo <= gap <= hi: continue
                    for side in ("Over", "Under"):
                        if min_p <= sd[side] <= max_p:
                            trig.append((pl, m["key"], side, b["key"], ln, sd[side], gap))
        for pl, mk, side, tb, tl, tp, gap in trig:
            opts = mine.get((pl, mk), [])
            if not opts: continue                                   # neither DK nor Fliff has it
            key = (lambda x: (x[1], -dec(x[2][side]))) if side == "Over" else (lambda x: (-x[1], -dec(x[2][side])))
            ub, ul, us = min(opts, key=key)
            if (side == "Over" and ul > tl) or (side == "Under" and ul < tl): continue   # user line worse for this side
            k = (ev["id"], pl, mk, side, ub, ul)
            if k in seen: continue
            seen.add(k)
            out.append(dict(event_id=ev["id"], game=game, kickoff_pt=ko.strftime("%a %-I:%M %p PT"), player=pl,
                market=mk.replace("player_", ""), line=ul, side=side, book=ub, price=us[side],
                other_price=us["Under" if side == "Over" else "Over"], cents_gap=gap, source="filter_a",
                trigger_book=tb, trigger_line=tl, trigger_price=tp))
    return out

def fmt(a): return "n/a" if a is None else (f"+{a}" if a > 0 else str(a))

def show(rows, top):
    pos = [r for r in rows if r["ev_pct"] > 0][:top]
    print(f"{len([r for r in rows if r['ev_pct']>0])} bets with EV>0 out of {len(rows)} priced sides; showing {len(pos)} (no padding)\n")
    print(f"{'EV%':>6} {'Kickoff':<16} {'Player':<22} {'Market':<14} {'Line':>6} {'Side':<5} {'Best':>5} {'Book':<12} {'Fair':>5} {'#Bk':>3}  Game / alt lines")
    for r in pos:
        print(f"{r['ev_pct']:>6.2f} {r['kickoff_pt']:<16} {str(r['player'])[:22]:<22} {r['market']:<14} {r['line']:>6} {r['side']:<5} {fmt(r['price']):>5} {r['book']:<12} {fmt(r['fair_price']):>5} {r['n_books']:>3}  {r['game']}" + (f"  [alts: {r['alt_lines']}]" if r['alt_lines'] else ""))
    return pos

def show_pickem(pick, be, top, allow_dfs):
    p = sorted([r for r in pick if r["fair_prob"] > be and r["book"] in allow_dfs], key=lambda r: -r["fair_prob"])[:top]
    print(f"\nPICK'EM legs (fair prob > break-even {be:.1%}, same exact line at 3+ books): {len(p)}")
    for r in p:
        r["ev_pct"] = round((r["fair_prob"] / be - 1) * 100, 2)  # edge vs break-even
        print(f"{r['fair_prob']:.1%} {r['kickoff_pt']:<16} {str(r['player'])[:22]:<22} {r['market']:<14} {r['line']:>6} {r['side']:<5} {r['book']:<11} {r['n_books']:>2} books  {r['game']}")
    return p

def log(pos, sport, path=LOG):
    new = not os.path.exists(path)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, LOG_COLS, extrasaction="ignore")
        if new: w.writeheader()
        for r in pos: w.writerow({**r, "logged_at_utc": now, "sport": sport})
    print(f"\nLogged {len(pos)} bets to {path}")

def fill_close(raw_dir, path=LOG):
    """Hook: fill close_price / close_fair_prob / clv_pct from a near-kickoff capture (raw event JSONs)."""
    evs = {}
    for f in glob.glob(os.path.join(raw_dir, "*.json")):
        e = json.load(open(f)); evs[e["id"]] = e
    rows = list(csv.DictReader(open(path)))
    n = 0
    for r in rows:
        if r["close_price"] or r["event_id"] not in evs: continue
        for c in analyze([evs[r["event_id"]]], books_allow={r["book"]}, min_books=1):
            if (c["player"], c["market"], c["line"], c["side"]) == (r["player"], r["market"], float(r["line"]), r["side"]):
                r["close_price"], r["close_fair_prob"] = c["price"], c["fair_prob"]
                r["clv_pct"] = round((c["fair_prob"] * dec(float(r["price"])) - 1) * 100, 2); n += 1
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, LOG_COLS); w.writeheader(); w.writerows(rows)
    print(f"Filled closing data for {n} rows")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sport", default="nfl", choices=SPORTS)
    ap.add_argument("--hours", type=float, default=6, help="events kicking off within N hours")
    ap.add_argument("--max-credits", type=int, default=0, help="hard cap for this run (0 = estimate only)")
    ap.add_argument("--floor", type=int, default=330, help="never let remaining credits drop below this")
    ap.add_argument("--bookmakers", default=DEFAULT_BOOKMAKERS, help="Odds API bookmakers param (each 10 books bill as 1 region); set '' to use --regions")
    ap.add_argument("--regions", default="us,us2,us_dfs", help="add ,eu for Pinnacle (+1 credit per market per event)")
    ap.add_argument("--pickem-breakeven", type=float, default=0.542, help="per-leg break-even: 6-pick flex ~0.542, 2-pick power 0.577")
    ap.add_argument("--dfs", default="prizepicks", help="pick'em sites to list legs for")
    ap.add_argument("--receptions", action="store_true", help="also pull player_receptions")
    ap.add_argument("--counts", action="store_true", help="also pull count markets: player_receptions, player_pass_completions, player_rush_attempts (keys verified vs the-odds-api.com betting-markets page 10/10)")
    ap.add_argument("--books", default=DEFAULT_BOOKS, help="comma allowlist of bookmaker keys you can bet at")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--offline", help="dir of raw event JSONs (0 credits)")
    ap.add_argument("--no-log", action="store_true")
    ap.add_argument("--fill-close", help="dir of raw close-capture JSONs to fill closing prices in the log")
    a = ap.parse_args()
    if a.fill_close: return fill_close(a.fill_close)
    allow = set(filter(None, a.books.split(","))) or None
    sport = SPORTS[a.sport]
    mkts = BASE_MKTS + (COUNT_MKTS if a.counts else (["player_receptions"] if a.receptions else []))
    if a.offline:
        events = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(a.offline, "*.json")))]
    else:
        k = key()
        evs, h = get(f"https://api.the-odds-api.com/v4/sports/{sport}/events?apiKey={k}")  # free endpoint
        rem = int(h.get("x-requests-remaining", 0))
        now = dt.datetime.now(dt.timezone.utc)
        evs = [e for e in evs if 0 <= (dt.datetime.fromisoformat(e["commence_time"].replace("Z","+00:00")) - now).total_seconds() <= a.hours * 3600]
        bms = [x for x in a.bookmakers.split(",") if x]
        nreg = -(-len(bms) // 10) if bms else len(a.regions.split(","))
        sel = f"bookmakers={','.join(bms)}" if bms else f"regions={a.regions}"
        per = len(mkts) * nreg
        print(f"{len(evs)} events in next {a.hours}h; est cost {per}/event = {per*len(evs)} credits max (markets x regions; events with no props may cost less). Remaining: {rem}, floor {a.floor}")
        budget = min(a.max_credits, rem - a.floor)
        if a.max_credits <= 0 or budget < per:
            print("Not pulling (set --max-credits, or budget/floor too low)."); return
        events, spent = [], 0
        rawdir = os.path.join(HERE, "raw", now.strftime("%Y%m%dT%H%M"))
        os.makedirs(rawdir, exist_ok=True)
        for e in sorted(evs, key=lambda e: e["commence_time"]):
            if spent + per > budget: print(f"Stopping: budget reached ({spent} spent)"); break
            d, h = get(f"https://api.the-odds-api.com/v4/sports/{sport}/events/{e['id']}/odds?apiKey={k}&{sel}&markets={','.join(mkts)}&oddsFormat=american")
            spent += int(h.get("x-requests-last", per)); events.append(d)
            json.dump(d, open(os.path.join(rawdir, e["id"] + ".json"), "w"))
        print(f"Spent {spent} credits; remaining {h.get('x-requests-remaining')}; raw saved in {rawdir}")
    pick = []
    rows = analyze(events, allow, pick=pick)
    books = sorted({b["key"] for e in events for b in e.get("bookmakers", [])})
    if allow and not allow & set(books): print(f"WARNING: none of your books ({', '.join(sorted(allow))}) appear in this data")
    print(f"Books seen: {', '.join(books)}; Pinnacle present: {'pinnacle' in books}; bettable: {', '.join(sorted(allow)) if allow else 'all'}")
    pos = show(rows, a.top)
    legs = show_pickem(pick, a.pickem_breakeven, a.top, set(a.dfs.split(",")))
    pos = pos + legs
    fa = tilt_filter(events, allow)
    print(f"\nFILTER (a) (one side +100..-150, sides 22-28 cents apart at any book; shown/scored at your book's line+price): {len(fa)}")
    for r in fa[:a.top * 2]:
        print(f"{r['kickoff_pt']:<16} {str(r['player'])[:22]:<22} {r['market']:<14} {r['line']:>6} {r['side']:<5} {fmt(r['price']):>5} (other {fmt(r['other_price'])}) at {r['book']:<11} [trigger {r['trigger_book']} {r['trigger_line']} {fmt(r['trigger_price'])}, gap {r['cents_gap']}]  {r['game']}")
    if not a.no_log and not a.offline: log(pos, a.sport)
    elif a.offline and not a.no_log: log(pos, a.sport, os.path.join(HERE, "bets_log_offline_test.csv"))

if __name__ == "__main__": main()
