#!/usr/bin/env python3
"""Analyze candidate prop bets (NFL) with everything we have. Run with the nfl-props venv:
    /workspace/nfl-props/.venv/bin/python analyze.py --raw latest            # Odds API pull saved by find.py (0 credits)
    /workspace/nfl-props/.venv/bin/python analyze.py --espn-dryrun           # stand-in: DraftKings-via-ESPN wk-5 D lines
Per candidate: frozen champion model (READ-ONLY import of /workspace/nfl-props; nothing there is written) ->
Monte Carlo 10k draws from mu + s*z (z = the model's own out-of-fold standardized residuals) = model P(hit);
2026 form + last-16 hit rate; opponent yards allowed to the position + implied team total; week injury report;
no-vig market consensus; blended P = (1-w)*market + w*model with w=0.05 (2025 stacker: model weight c~0.03-0.05,
SE~0.08, i.e. statistically zero). The model does NOT beat the market on real 2025 lines: its P is a sanity check."""
import argparse, datetime as dt, glob, json, math, os, statistics, sys, time
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
NFLP = "/workspace/nfl-props"
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(NFLP, "src"))
import find as F
from nflprops.pregame import champion_cfg, pregame_features
from nflprops.config import deep_update
from nflprops.features import feature_columns
from nflprops.markets import MARKETS, universe_mask
from nflprops.model import DistModel

TEAMS = {"Arizona Cardinals":"ARI","Atlanta Falcons":"ATL","Baltimore Ravens":"BAL","Buffalo Bills":"BUF","Carolina Panthers":"CAR",
"Chicago Bears":"CHI","Cincinnati Bengals":"CIN","Cleveland Browns":"CLE","Dallas Cowboys":"DAL","Denver Broncos":"DEN","Detroit Lions":"DET",
"Green Bay Packers":"GB","Houston Texans":"HOU","Indianapolis Colts":"IND","Jacksonville Jaguars":"JAX","Kansas City Chiefs":"KC",
"Las Vegas Raiders":"LV","Los Angeles Chargers":"LAC","Los Angeles Rams":"LA","Miami Dolphins":"MIA","Minnesota Vikings":"MIN",
"New England Patriots":"NE","New Orleans Saints":"NO","New York Giants":"NYG","New York Jets":"NYJ","Philadelphia Eagles":"PHI",
"Pittsburgh Steelers":"PIT","San Francisco 49ers":"SF","Seattle Seahawks":"SEA","Tampa Bay Buccaneers":"TB","Tennessee Titans":"TEN",
"Washington Commanders":"WAS"}
MKMAP = {"pass_yds":"pass_yds","rush_yds":"rush_yds","reception_yds":"rec_yds","rec_yds":"rec_yds",
         "receptions":"receptions","pass_completions":"pass_completions","rush_attempts":"rush_attempts"}
YDS = {"pass_yds":"passing_yards","rush_yds":"rushing_yards","rec_yds":"receiving_yards"}
COUNTS = {"receptions":"receptions","pass_completions":"completions","rush_attempts":"carries"}
STAT = {**YDS, **COUNTS}
VOL = {"pass_yds":"attempts","rush_yds":"carries","rec_yds":"targets","receptions":"targets","pass_completions":"attempts","rush_attempts":"carries"}
# Count-model shrink toward 0.5: p' = 0.5 + K*(p-0.5), clipped to [0.25, 0.75]. Justification (out/calibration_2025.csv):
# n-weighted slope of (actual-0.5) on (pred-0.5) = 1.00 receptions, 0.96 rush_attempts, 0.80 pass_completions, but the top
# bins are overconfident (receptions 0.64->0.58, 0.74->0.64; rush_attempts 0.75->0.61). K=0.8 + clip matches those bins.
COUNT_K = 0.8; COUNT_CLIP = (0.25, 0.75)
W_MODEL = 0.05; DISAGREE = 0.08; NSIM = 10000
INJ_URL = "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{s}.csv"
OUT = os.path.join(HERE, "analysis")

def wilson(k, n, z=1.96):
    if n == 0: return (float("nan"),) * 2
    p = k / n; d = 1 + z*z/n; c = (p + z*z/(2*n)) / d; h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return max(0, c-h), min(1, c+h)

def load_readonly(first, last):
    raw = f"{NFLP}/data/cache/raw"
    d = {k: pd.concat([pd.read_parquet(f"{raw}/{k}_{s}.parquet") for s in range(first, last + 1)], ignore_index=True)
         for k in ("player_stats", "snap_counts")}
    for k in ("schedules", "players"): d[k] = pd.read_parquet(f"{raw}/{k}.parquet")
    return d

# ---------------------------------------------------------------- candidates
def cands_from_raw(rawdir, books):
    events = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(rawdir, "*.json")))]
    allow = set(books.split(","))
    pick = []; rows = F.analyze(events, allow, pick=pick)
    c = [dict(r, source="ev_best_price") for r in rows if r["ev_pct"] > 0]
    c += [dict(r, source="prizepicks_leg") for r in pick if r["fair_prob"] > 0.542 and r["book"] == "prizepicks"]
    c += F.tilt_filter(events, allow)
    # market consensus for every (player, market, line): reuse find.analyze with all books, min 1 book
    cons = {}
    for r in F.analyze(events, None, min_books=1):
        cons[(r["event_id"], r["player"], r["market"], r["line"], r["side"])] = (r["fair_prob"], r["n_books"])
    ev = {e["id"]: e for e in events}
    for r in c:
        fp, nb = cons.get((r["event_id"], r["player"], r["market"], r["line"], r["side"]), (None, 0))
        r["mkt_p"], r["n_books"] = fp, nb
        e = ev[r["event_id"]]; r["home"], r["away"] = TEAMS.get(e["home_team"]), TEAMS.get(e["away_team"])
    seen = {}
    for r in c:   # one row per bet; keep every source that produced it
        k = (r["event_id"], r["player"], r["market"], r["line"], r["side"], r["book"])
        if k in seen: seen[k]["source"] += "+" + r["source"]
        else: seen[k] = r
    return list(seen.values())

def cands_from_espn(season, week):
    L = pd.read_csv(f"{NFLP}/data/lines/snap_{season}_wk{week}_D.csv", dtype={"player_id": str, "event_id": str})
    L = L[L["void_reason"].isna()] if "void_reason" in L else L
    out = []
    for r in L.itertuples():
        for side in ("Over", "Under"):
            pr = r.over_price if side == "Over" else r.under_price
            po, pu = F.imp(r.over_price), F.imp(r.under_price)
            out.append(dict(event_id=r.event_id, espn=r.event_id, player=r.player_name, player_id=r.player_id, market=r.market,
                line=float(r.line), side=side, book="draftkings(espn)", price=int(pr), mkt_p=(po/(po+pu)) if side=="Over" else pu/(po+pu),
                n_books=1, source="espn_dryrun", price_assumed=bool(r.price_assumed)))
    return out

# ---------------------------------------------------------------- model (in-memory replica of pregame.score; writes nothing)
def model_block(d, season, week, C):
    cfg, champ = champion_cfg()
    cfg = deep_update(cfg, {"data": {"last_season": max(season, cfg["data"]["last_season"])}})
    lines = pd.DataFrame([{"player_id": c["player_id"], "event_id": str(c["espn"]), "player_name": c["player"], "market": c["mk"],
                           "line": c["line"], "void_reason": np.nan} for c in C if c.get("player_id") and c["mk"] in YDS])
    if lines.empty: return {}, {}, champ, "n/a (no model-matched candidates)"
    lines = lines.drop_duplicates(["player_id", "market"])
    f, dt_, extra, cutoff, voids = pregame_features(d, season, week, 2, lines)
    sch = d["schedules"]; mc = cfg["model"]
    cols = feature_columns(mc["feature_set"], mc.get("use_snaps", True), mc.get("use_market_proj", True))
    k = int(mc.get("retrain_every_weeks", 4)); blk_first = 1 + ((week - 1) // k) * k
    reg = sch[(sch["season"] == season) & (sch["game_type"] == "REG")]
    season_start = pd.to_datetime(reg["gameday"]).min()
    blk_start = pd.to_datetime(reg[reg["week"] == blk_first]["gameday"]).min()
    res = {}; rng = np.random.default_rng(20261011)
    for mk in cfg["markets"]:
        stat = MARKETS[mk]["stat"]
        u = f[universe_mask(f, mk, cfg.get("universe", {}).get("min_proj", 20.0))]; real = u[u["is_pregame_row"] == 0]
        te = f[(f["is_pregame_row"] == 1) & (f["season"] == season) & (f["week"] == week)]
        te = te[te["player_id"].isin(lines.loc[lines["market"] == mk, "player_id"])]
        if te.empty: continue
        m = DistModel(mc.get("lgbm", {}), mc.get("dist", "empirical"), mc.get("n_folds", 3))
        trd = real[real["gameday"] < season_start]; m.fit_dist(trd[cols], trd[stat].values, trd["season"].values)
        trm = real[real["gameday"] < blk_start]; m.fit_mean(trm[cols], trm[stat].values)
        mu, s = m.predict(te[cols])
        for pid, a, b, inu in zip(te["player_id"], mu, s, te.index.isin(u.index)):
            draws = np.maximum(a + b * rng.choice(m.z_sorted, NSIM), 0 if mk != "rush_yds" else -20)
            res[(pid, mk)] = dict(mu=float(a), s=float(b), draws=draws, in_universe=bool(inu))
    vo = {} if voids is None or not len(voids) else {(r.player_id, r.market): r.void_reason for r in voids.itertuples()}
    return res, vo, champ, str(cutoff.date())

def count_block(season, week):
    """One counts.predict() call per run (NEW_UNVALIDATED_CHALLENGER). Returns {(player_id, market): (mu, alpha)}."""
    sys.path.insert(0, "/workspace/nfl-props-counts"); import counts
    P = counts.predict(week=week, season=season, max_age_h=1e9)   # 1e9: never refresh nfl-props caches
    os.makedirs(OUT, exist_ok=True)
    P.to_csv(os.path.join(OUT, f"count_preds_{season}_wk{week}_{dt.datetime.now():%Y%m%dT%H%M}.csv"), index=False)
    return {(r.player_id, r.market): (float(r.mu), float(r.alpha)) for r in P.itertuples()}, counts.p_over

def cands_from_espn_counts(season, week):
    sys.path.insert(0, "/workspace/nfl-props-counts"); import counts
    L = counts.espn_lines(); L = L[(L["kind"] == "D") & (L["season"] == season) & (L["week"] == week)]
    out = []
    for r in L.itertuples():
        op = int(r.over_price) if pd.notna(r.over_price) else -110; up = int(r.under_price) if pd.notna(r.under_price) else -110
        po, pu = F.imp(op), F.imp(up)
        for side, pr in (("Over", op), ("Under", up)):
            out.append(dict(event_id=r.event_id, espn=r.event_id, player=r.player_name, player_id=r.player_id, market=r.market,
                line=float(r.line), side=side, book="draftkings(espn)", price=pr, mkt_p=po/(po+pu) if side == "Over" else pu/(po+pu),
                n_books=1, source="espn_dryrun", price_assumed=pd.isna(r.over_price)))
    return out

# ---------------------------------------------------------------- context
def context(d, season, week):
    ps = pd.concat([pd.read_parquet(f"{NFLP}/data/cache/raw/player_stats_{s}.parquet") for s in (season-1, season)])
    ps = ps[ps["season_type"] == "REG"] if "season_type" in ps else ps
    ps = ps[(ps["season"] < season) | (ps["week"] < week)]
    sn = pd.read_parquet(f"{NFLP}/data/cache/raw/snap_counts_{season}.parquet"); sn = sn[sn["week"] < week]
    pl = pd.read_parquet(f"{NFLP}/data/cache/raw/players.parquet")
    try:
        inj = pd.read_csv(INJ_URL.format(s=season)); inj = inj[inj["week"] == week]
    except Exception as e:
        print("injury report unavailable:", e); inj = pd.DataFrame(columns=["gsis_id", "team", "position", "full_name", "report_status", "practice_status"])
    sch = d["schedules"]; wk = sch[(sch["season"] == season) & (sch["week"] == week)]
    return dict(ps=ps, sn=sn, pl=pl, inj=inj, wk=wk)

def form(ctx, pid, mk, line, side, season):
    g = ctx["ps"][ctx["ps"]["player_id"] == pid].sort_values(["season", "week"])
    st, vol = STAT[mk], VOL[mk]
    cur = g[g["season"] == season]; l16 = g.tail(16)
    hit = (lambda x: (x[st] > line) if side == "Over" else (x[st] < line))
    k26, n26 = int(hit(cur).sum()), len(cur); k16, n16 = int(hit(l16).sum()), len(l16)
    trend = float(np.polyfit(cur["week"], cur[st], 1)[0]) if n26 >= 3 else float("nan")
    vtrend = float(np.polyfit(cur["week"], cur[vol], 1)[0]) if n26 >= 3 else float("nan")
    pfr = ctx["pl"].loc[ctx["pl"]["gsis_id"] == pid, "pfr_id"]
    snap = ctx["sn"][ctx["sn"]["pfr_player_id"].isin(pfr)]["offense_pct"].mean() if len(pfr) else float("nan")
    lo, hi = wilson(k16, n16)
    return dict(team=(g["team"].iloc[-1] if len(g) else None), pos=(g["position"].iloc[-1] if len(g) else None),
        y26=" ".join(str(int(v)) for v in cur[st]), avg26=float(cur[st].mean()) if n26 else float("nan"),
        vol26=float(cur[vol].mean()) if n26 else float("nan"), snap26=snap, trend=trend,
        hit26=f"{k26}/{n26}", hit16=f"{k16}/{n16}", hit16_rate=(k16/n16 if n16 else float("nan")), n16=n16, n26=n26, hit26_rate=(k26/n26 if n26 else float("nan")), vol_trend=vtrend, hit16_ci=f"{lo:.0%}-{hi:.0%}" if n16 else "")

def matchup(ctx, team, opp, pos, mk, season):
    ps = ctx["ps"]; cur = ps[ps["season"] == season]; st = STAT[mk]
    grp = cur if mk in ("pass_yds", "pass_completions") else cur[cur["position"] == pos]
    pg = grp.groupby(["opponent_team", "week"])[st].sum().groupby("opponent_team").mean()
    rank = pg.rank(ascending=False)  # 1 = allows most
    g = ctx["wk"][((ctx["wk"]["home_team"] == team) | (ctx["wk"]["away_team"] == team))]
    itt = float("nan")
    if len(g) and pd.notna(g["spread_line"].iloc[0]):
        r = g.iloc[0]; sp = r["spread_line"] if r["home_team"] == team else -r["spread_line"]  # nflverse: + = home favoured
        itt = (r["total_line"] + sp) / 2
    return dict(lg_avg=float(pg.mean()), opp_allowed=float(pg.get(opp, float("nan"))), opp_rank=(int(rank.get(opp)) if opp in rank else None), n_teams=len(pg), implied_tt=itt)

def injuries(ctx, pid, team, season=2026):
    """Player's own status + teammates Out/Doubtful who were meaningful contributors in 2026: avg offensive snap
    share >= 50% (last 3 games) or top-3 at their position on the team in targets/g or carries/g. Facts only."""
    inj = ctx["inj"]; me = inj[inj["gsis_id"] == pid]
    mine = "" if me.empty else f"{me['report_status'].fillna('').iloc[0] or '-'}/{me['practice_status'].fillna('').iloc[0]}"
    out = inj[(inj["team"] == team) & inj["report_status"].isin(["Out", "Doubtful"]) & inj["position"].isin(["QB", "RB", "WR", "TE"]) & (inj["gsis_id"] != pid)]
    ps = ctx["ps"]; cur = ps[(ps["season"] == season) & (ps["team"] == team)]
    pg = cur.groupby(["player_id", "position"]).agg(tgt=("targets", "mean"), car=("carries", "mean")).reset_index()
    sn = ctx["sn"]; sn = sn[sn["team"] == team].sort_values("week")
    pl = ctx["pl"]; notes = []
    for r in out.itertuples():
        pfr = pl.loc[pl["gsis_id"] == r.gsis_id, "pfr_id"]
        snap = sn[sn["pfr_player_id"].isin(pfr)].groupby("pfr_player_id").tail(3)["offense_pct"].mean() if len(pfr) else float("nan")
        u = pg[pg["player_id"] == r.gsis_id]
        tgt = float(u["tgt"].iloc[0]) if len(u) else 0.0; car = float(u["car"].iloc[0]) if len(u) else 0.0
        same = pg[pg["position"] == r.position]
        top_t = tgt > 0 and (same["tgt"] > tgt).sum() < 3
        top_c = car > 0 and (same["car"] > car).sum() < 3 and r.position in ("RB", "QB")
        snap_ok = pd.notna(snap) and snap >= 0.5
        if not (snap_ok or top_t or top_c): continue
        use = [f"{snap:.0%} snaps" if pd.notna(snap) else "snaps n/a"]
        if r.position in ("WR", "TE", "RB") and tgt: use.append(f"{tgt:.1f} tgt/g")
        if r.position in ("RB", "QB") and car: use.append(f"{car:.1f} car/g")
        notes.append(f"{r.full_name} {r.position} {r.report_status} ({', '.join(use)})")
    return mine, "; ".join(notes)

def name_to_pid(ctx, name, teams):
    pl = ctx["pl"]; ps = ctx["ps"]
    ids = pl.loc[pl["display_name"].str.lower() == str(name).lower(), "gsis_id"]
    if len(ids) > 1:
        last = ps[ps["player_id"].isin(ids)].sort_values(["season", "week"]).groupby("player_id").tail(1)
        ids = last.loc[last["team"].isin(teams), "player_id"]
    return ids.iloc[0] if len(ids) else None

# ---------------------------------------------------------------- verdict
def verdict(r):
    if r["model_p"] is None or (isinstance(r["model_p"], float) and math.isnan(r["model_p"])):
        return "neutral", "no model coverage (" + str(r.get("model_note") or "market not modelled") + "); market price only"
    tag = " [new count model (unvalidated)]" if r["market"] in COUNTS else ""
    gap = r["model_p"] - r["mkt_p"]
    if abs(gap) > DISAGREE:
        return "neutral", f"likely model miss (model {r['model_p']:.0%} vs market {r['mkt_p']:.0%}); not a find"
    good_price = r["ev_pct"] > 0
    model_ok = r["model_p"] > r["breakeven"]
    form_ok = (r["hit16_rate"] >= 0.5) if not math.isnan(r["hit16_rate"]) else False
    if r["opp_rank"] is None or not r["n_teams"]: mu_ok = None
    else:
        soft = r["opp_rank"] <= r["n_teams"] / 2
        mu_ok = soft if r["side"] == "Over" else not soft
    agree = [model_ok, form_ok, bool(mu_ok)]
    if good_price and all(agree):
        return "supports", "good price, and model, form and matchup all point the same way"
    if not good_price and sum(agree) <= 1:
        return "against", "no price edge and the model/form/matchup mostly point the other way"
    if not good_price:
        return "neutral", "no price edge at the offered price; " + ("signals lean this way" if sum(agree) >= 2 else "mixed signals")
    return "neutral", f"price edge, but signals mixed (model {'Y' if model_ok else 'N'}, form {'Y' if form_ok else 'N'}, matchup {'Y' if mu_ok else 'N'})"

def corr_key(r):
    """same-game correlation group: everything in one game shares a key; finer tags describe the link."""
    return r["game_id"]

RECV = {"rec_yds", "reception_yds", "receptions"}; RUSH = {"rush_yds", "rush_attempts"}; PASS = {"pass_yds", "pass_completions"}
def df_vetoes(r):
    """Signals are VETOES (fixed before any results): each returns (veto: bool, text). Drop the bet if any clearly
    points the other way. form: last-16 hit rate at this line < 40% with n>=6. matchup: opponent allows >10% less
    (Over) / more (Under) than league avg to the position. usage: volume trend against the side by >10% of avg/week.
    injury: Over with player Questionable/Doubtful; Under with a starter-level same-unit teammate out."""
    ov = r["side"] == "Over"; out = {}
    n16, h16 = r.get("n16", 0) or 0, r.get("hit16_rate")
    out["form"] = (bool(n16 >= 6 and pd.notna(h16) and h16 < 0.40), f"hit {r.get('hit26')} 2026, {r.get('hit16')} last16 (CI {r.get('hit16_ci')})")
    la, oa = r.get("lg_avg"), r.get("opp_allowed")
    if la is None or oa is None or pd.isna(oa) or not la: out["matchup"] = (False, "n/a")
    else:
        rel = oa / la - 1
        out["matchup"] = (bool(rel < -0.10) if ov else bool(rel > 0.10), f"{r.get('opp')} allows {oa:.0f}/g vs lg {la:.0f} ({rel:+.0%})")
    vt, vol, sn = r.get("vol_trend"), r.get("vol26"), r.get("snap26")
    if vt is None or pd.isna(vt): out["usage"] = (False, "trend n/a (<3 games)")
    else:
        rel = vt / max(vol or 0, 1)
        out["usage"] = (bool(rel < -0.10) if ov else bool(rel > 0.10),
                        f"volume {vol:.1f}/g, trend {vt:+.1f}/wk" + (f", snaps {sn:.0%}" if pd.notna(sn) else ""))
    inj = r.get("inj_team_out") or ""; me = r.get("inj_self") or ""
    unit = ("RB",) if r["market"] in RUSH else ("WR", "TE")
    hit = [x for x in inj.split("; ") if x and any(f" {u} " in x for u in unit)]
    selfq = any(x in me for x in ("Questionable", "Doubtful"))
    if r["market"] in PASS: v = ov and bool(hit)
    else: v = (ov and selfq) or ((not ov) and bool(hit))
    out["injury"] = (bool(v), ("same-unit starters out: " + "; ".join(hit)) if hit else (f"self {me}" if me else "no relevant injuries"))
    return out

def data_first(df, a, champ, cutoff, t0):
    d = df[df["model_p"].notna()].copy()
    d["edge_be"] = d["model_p"] - d["breakeven"]; d["gap_mkt"] = (d["model_p"] - d["mkt_p"]).abs()
    keep, why = [], {"edge<5": 0, "gap>12/no books": 0, "veto": 0}
    for i, r in d.iterrows():
        if r["edge_be"] < 0.05: why["edge<5"] += 1; continue
        if not pd.notna(r["mkt_p"]) or r["gap_mkt"] > 0.12: why["gap>12/no books"] += 1; continue
        sg = df_vetoes(r)
        if any(v[0] for v in sg.values()): why["veto"] += 1; continue
        keep.append((i, sg))
    K = d.loc[[i for i, _ in keep]].assign(signals=[" | ".join(f"{k}: {v[1]}" for k, v in sg.items()) for _, sg in keep])
    K = K.sort_values("edge_be", ascending=False).drop_duplicates("game_id").head(a.top)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"datafirst_{a.season}_wk{a.week}_{dt.datetime.now():%Y%m%dT%H%M}.csv"); K.to_csv(path, index=False)
    print(f"DATA-FIRST: {len(d)} model-covered sides; dropped {why}; {len(keep)} pass -> {len(K)} listed (one per game, no padding)\n")
    for r in K.to_dict("records"):
        print(f"{r['player']} | {r['game_id']} {r['kick']} | {r['market']} {r['side']} {r['line']} @ {F.fmt(int(r['price']))} {r['book']}")
        print(f"   model {r['model_p']:.1%} [{r.get('model_label')}] vs break-even {r['breakeven']:.1%} (+{r['edge_be']*100:.1f} pts) | books no-vig {r['mkt_p']:.1%} ({r['n_books']} bk)")
        print(f"   {r['signals']}\n")
    print(f"Wrote {path}. Runtime {time.time()-t0:.0f}s")

def current_week(sch, season, today=None):
    """First regular-season week of `season` with a game on/after today (PT). Replaces the old hardcoded default of 5."""
    today = today or pd.Timestamp.now(tz="America/Los_Angeles").strftime("%Y-%m-%d")
    s = sch[(sch["season"] == season) & (sch["game_type"] == "REG")] if "game_type" in sch else sch[sch["season"] == season]
    up = s[s["gameday"].astype(str) >= today]
    return int(up["week"].min()) if len(up) else int(s["week"].max())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", help="dir of raw Odds API event JSONs from find.py, or 'latest'")
    ap.add_argument("--espn-dryrun", action="store_true")
    ap.add_argument("--season", type=int, default=2026); ap.add_argument("--week", type=int, default=None, help="default: current week from the schedule (first week with a game today or later, PT)")
    ap.add_argument("--books", default=F.DEFAULT_BOOKS)
    ap.add_argument("--w-model", type=float, default=W_MODEL)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--data-first", action="store_true", help="list bets the DATA says are likely to hit; price is only a final check")
    ap.add_argument("--counts", action="store_true", help="use the new count models for receptions/completions/rush attempts")
    ap.add_argument("--show", type=int, default=25)
    a = ap.parse_args(); t0 = time.time()
    if a.raw == "latest":
        a.raw = max((p for p in glob.glob(os.path.join(HERE, "raw", "2*")) if os.path.isdir(p)), key=os.path.getmtime)
    d = load_readonly(2015, a.season)   # reads the cached parquet files directly: never downloads or writes
    if a.week is None: a.week = current_week(d["schedules"], a.season); print(f"--week not given: using week {a.week} from the schedule")
    ctx = context(d, a.season, a.week)
    wk = ctx["wk"]
    C = (cands_from_espn(a.season, a.week) + (cands_from_espn_counts(a.season, a.week) if a.counts else [])) if a.espn_dryrun \
        else cands_from_raw(a.raw, a.books)
    print(f"{len(C)} candidates from {'ESPN D lines (dry run)' if a.espn_dryrun else a.raw}")
    for c in C:
        c["mk"] = MKMAP.get(c["market"], c["market"])
        if not a.espn_dryrun:
            g = wk[((wk["home_team"] == c["home"]) & (wk["away_team"] == c["away"]))]
            c["espn"] = str(g["espn"].iloc[0]) if len(g) else None
            c["player_id"] = name_to_pid(ctx, c["player"], [c["home"], c["away"]])
        g = wk[wk["espn"].astype(str) == str(c["espn"])]
        c["game_id"] = g["game_id"].iloc[0] if len(g) else c.get("event_id")
        c["kick"] = (f"{g['gameday'].iloc[0]} {g['gametime'].iloc[0]} ET") if len(g) else c.get("kickoff_pt", "")
    # drop started games
    now_et = pd.Timestamp.now(tz="America/New_York").tz_localize(None)
    C = [c for c in C if not c["kick"].endswith("ET") or pd.Timestamp(c["kick"][:-3]) > now_et]
    print(f"{len(C)} candidates in games not yet started")
    M, voids, champ, cutoff = model_block(d, a.season, a.week, C)
    CM, p_over = count_block(a.season, a.week) if (a.counts and any(c["mk"] in COUNTS for c in C)) else ({}, None)
    rows = []
    for c in C:
        pid, mk = c.get("player_id"), c["mk"]
        r = {k: c.get(k) for k in ("source", "game_id", "kick", "player", "player_id", "market", "line", "side", "book", "price", "n_books",
                                  "trigger_book", "trigger_line", "trigger_price")}
        r["price_assumed"] = c.get("price_assumed", False)
        r["breakeven"] = (1 / F.dec(c["price"])) if c.get("price") not in ("", None) else 0.542
        r["mkt_p"] = c.get("mkt_p") if c.get("mkt_p") is not None else float("nan")
        m = M.get((pid, mk))
        if mk in COUNTS:
            cm = CM.get((pid, mk))
            if cm is None:
                r.update(model_mu=None, model_s=None, model_p=float("nan"), model_in_universe=False,
                         model_note="no model coverage" if not a.counts else "outside count-model universe")
            else:
                po = float(p_over(np.array([cm[0]]), cm[1], c["line"])[0])
                raw = po if c["side"] == "Over" else 1 - po
                sh = min(max(0.5 + COUNT_K * (raw - 0.5), COUNT_CLIP[0]), COUNT_CLIP[1])
                r.update(model_mu=round(cm[0], 2), model_s=round(cm[1], 3), model_p=sh, model_p_raw=round(raw, 4),
                         model_in_universe=True, model_label="new count model (unvalidated)")
        elif m is not None and not m["in_universe"]:
            r.update(model_mu=round(m["mu"], 1), model_s=round(m["s"], 1), model_p=float("nan"), model_in_universe=False,
                     model_note="outside pre-registered model scope (e.g. QB rushing, non-starter, proj<20)")
        elif m is not None:
            ov = float((m["draws"] > c["line"]).mean())
            r.update(model_mu=round(m["mu"], 1), model_s=round(m["s"], 1), model_p=ov if c["side"] == "Over" else 1 - ov,
                     model_in_universe=m["in_universe"], model_label="champion yards model")
        else:
            r.update(model_mu=None, model_s=None, model_p=float("nan"), model_in_universe=False,
                     model_note=voids.get((pid, mk), "no model coverage" if mk not in STAT else "player not matched"))
        if pid and mk in STAT:
            fm = form(ctx, pid, mk, c["line"], c["side"], a.season); r.update(fm)
            gg = wk[wk["game_id"] == r["game_id"]]
            opp = None
            if len(gg): opp = gg["away_team"].iloc[0] if gg["home_team"].iloc[0] == fm["team"] else gg["home_team"].iloc[0]
            r["opp"] = opp; r.update(matchup(ctx, fm["team"], opp, fm["pos"], mk, a.season))
            r["inj_self"], r["inj_team_out"] = injuries(ctx, pid, fm["team"], a.season)
        else:
            r.update(hit16_rate=float("nan"), opp_rank=None, n_teams=0)
        mp = r["mkt_p"]; md = r["model_p"]
        r["blend_p"] = mp if math.isnan(md) else (1 - a.w_model) * mp + a.w_model * md
        r["ev_pct"] = round((r["blend_p"] / r["breakeven"] - 1) * 100, 2) if not math.isnan(r["blend_p"]) else float("nan")
        r["verdict"], r["why"] = verdict(r)
        if r.get("model_label") == "new count model (unvalidated)": r["why"] = "[new count model (unvalidated)] " + r["why"]
        if r.get("inj_self") and any(s in r["inj_self"] for s in ("Out", "Doubtful", "Questionable")):
            r["why"] += f"; PLAYER LISTED {r['inj_self']}"
            if r["verdict"] == "supports": r["verdict"] = "neutral"
        rows.append(r)
    df = pd.DataFrame(rows).sort_values("ev_pct", ascending=False)
    if a.data_first:
        return data_first(df, a, champ, cutoff, t0)
    # correlation flags: >1 candidate in a game (same-game legs are correlated; e.g. QB pass over + his WR rec over)
    df["same_game_n"] = df.groupby("game_id")["player"].transform("count")
    tm = df.get("team")
    def link(r):
        o = df[(df["game_id"] == r["game_id"]) & (df["player"] != r["player"])]
        tags = []
        for x in o.itertuples():
            same = getattr(x, "team", None) == r.get("team")
            if same and {r["market"], x.market} <= {"pass_yds", "rec_yds", "reception_yds"} and r["side"] == x.side: tags.append(f"+{x.player}")
            elif same and {r["market"], x.market} == {"rush_yds", "pass_yds"} and r["side"] != x.side: tags.append(f"+{x.player}")
        return ",".join(sorted(set(tags))[:4])
    df["correlated_with"] = df.apply(link, axis=1)
    # final list: positive blended EV, one per game, no 'likely model miss', no padding
    fin = df[(df["ev_pct"] > 0) & ~df["why"].str.startswith("likely model miss")].drop_duplicates("game_id").head(a.top)
    df["in_final_list"] = df.index.isin(fin.index)
    os.makedirs(OUT, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M")
    tag = "dryrun" if a.espn_dryrun else "live"
    path = os.path.join(OUT, f"analysis_{a.season}_wk{a.week}_{tag}_{stamp}.csv")
    df.assign(analyzed_at_pt=dt.datetime.now().isoformat(timespec="seconds"), w_model=a.w_model, champion=champ,
              data_cutoff=cutoff, result_yds="", close_price="", close_fair_p="", graded="").to_csv(path, index=False)
    log = os.path.join(OUT, f"analysis_log_{tag}.csv")
    df.assign(analyzed_at_pt=dt.datetime.now().isoformat(timespec="seconds"), w_model=a.w_model, result_yds="", close_price="").to_csv(
        log, mode="a", header=not os.path.exists(log), index=False)
    pct = lambda x: "  -- " if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:5.1%}"
    print(f"\nModel weight in blend: {a.w_model} (2025 stacker: c~0.03-0.05, SE~0.08 -> model adds ~nothing; market dominates)")
    print(f"Data cutoff {cutoff}; champion {champ}; MODEL P = the champion model's own hit probability (10k MC draws), not extra evidence.\n")
    show = df.head(a.show)
    for r in show.to_dict("records"):
        print(f"[{r['verdict'].upper():8}] EV {r['ev_pct']:+.1f}%  {r['player']} {r['market']} {r['side']} {r['line']} @ {F.fmt(r['price'])} {r['book']}"
              f"{(' [tilt trigger ' + str(r['trigger_book']) + ' ' + str(r['trigger_line']) + ' ' + F.fmt(int(r['trigger_price'])) + ']') if isinstance(r.get('trigger_book'), str) else ''}"
              f"{' (price ASSUMED -110)' if r['price_assumed'] else ''}  {r['kick']}  {'*FINAL LIST*' if r['in_final_list'] else ''}")
        print(f"    market no-vig {pct(r['mkt_p'])} ({r['n_books']} bk) | model {pct(r['model_p'])} [{r.get('model_label') or 'none'}] (mu {r['model_mu']}, {'alpha' if r['market'] in COUNTS else 's'} {r['model_s']}) | blend {pct(r['blend_p'])} | break-even {r['breakeven']:.1%}")
        if r.get("hit16"):
            print(f"    form 2026 [{r['y26']}] avg {r['avg26']:.0f}, vol {r['vol26']:.1f}, snap {r['snap26']:.0%}, trend {r['trend']:+.1f}/wk | hits 2026 {r['hit26']}, last16 {r['hit16']} (95% CI {r['hit16_ci']}; small sample)")
            print(f"    matchup vs {r['opp']}: allows {r['opp_allowed']:.0f}/g to pos, rank {r['opp_rank']}/{r['n_teams']} (1=most) | implied team total {r['implied_tt']:.1f} | injury: self {r['inj_self'] or 'not listed'}; key teammates out: {r['inj_team_out'] or 'none'}")
        print(f"    -> {r['why']}" + (f" | correlated in-game: {r['correlated_with']}" if r['correlated_with'] else "") + "\n")
    print(f"FINAL LIST (blended EV>0, max one per game, no padding): {len(fin)}")
    for r in fin.to_dict("records"):
        print(f"  {r['ev_pct']:+.1f}%  [{r['verdict']}] {r['player']} {r['market']} {r['side']} {r['line']} @ {F.fmt(r['price'])} {r['book']}")
    print(f"\nWrote {path} ({len(df)} rows) and appended {log}.  Runtime {time.time()-t0:.0f}s")

if __name__ == "__main__": main()
