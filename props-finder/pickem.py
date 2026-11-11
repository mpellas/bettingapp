#!/usr/bin/env python3
"""PrizePicks entry mode (NFL props + NHL shots on goal). 0 credits: reads saved raw Odds API pulls.
  python3 pickem.py --raw raw/<nfl_dir> --sport nfl      python3 pickem.py --raw raw/<nhl_dir> --sport nhl
Per PrizePicks STANDARD line (goblins/demons = *_alternate markets are excluded):
 1. Every sportsbook with both sides at ANY line for that player/market is de-vigged at its own line. A distribution
    (NB for counts with the model's dispersion k; normal for yards with the model's s) is mean-refitted so it matches
    that book's no-vig P(over its line); P(over), P(push), P(under) are then read at PrizePicks' exact number.
    Consensus = median across books (Pinnacle x3). <3 books -> leg flagged and not used.
 2. blend = 0.95*books + 0.05*model (model P at PP's number; book-only if the player isn't modelled, flagged).
 3. Vetoes from data-first mode (NFL: form/matchup/usage/injury from today's analysis CSV; NHL: slot veto + l10 form).
 4. Per entry type, per-leg break-even = iid win prob p* making entry EV 0 given that leg's push prob. A leg qualifies
    for a type only if blended P(win) >= that p*. Entries are built only from qualifying legs, max one leg per game
    (same-game legs blocked; no pair is treated as 'clearly positively correlated' automatically) and EV is computed
    exactly by enumerating win/loss/push for every leg. Push: the leg is removed and the entry pays as the next smaller
    entry of the same type (Power 2->1 or Flex 2->1 = refund 1x)."""
import argparse, glob, itertools, json, math, os, statistics, sys
import numpy as np, pandas as pd
from scipy import stats, optimize
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import find as F
# Standard PrizePicks Player Pick payouts (prizepicks.com/help-center/payouts, last updated 2026-09-09; checked 2026-10-11)
POWER = {2: {2: 3}, 3: {3: 6}, 4: {4: 10}, 5: {5: 20}, 6: {6: 37.5}}
FLEX = {2: {2: 2, 1: .5}, 3: {3: 3, 2: 1}, 4: {4: 6, 3: 1.5}, 5: {5: 10, 4: 2, 3: .4}, 6: {6: 25, 5: 2, 4: .4}}
TYPES = {"power2": (POWER, 2), "power3": (POWER, 3), "flex3": (FLEX, 3), "flex4": (FLEX, 4), "flex5": (FLEX, 5), "flex6": (FLEX, 6)}
W_MODEL = 0.05; MIN_BOOKS = 3
COUNT_MK = {"player_receptions", "player_pass_completions", "player_rush_attempts", "player_shots_on_goal"}
DEF_S = {"player_pass_yds": 65.0, "player_rush_yds": None, "player_reception_yds": None}  # None -> 0.55*line, min 12

def payout(table, n, k):
    if n <= 1: return 1.0                          # all-but-one pushed: refund
    return table[n].get(k, 0.0)

def entry_ev(legs, table):
    """legs: list of (p_win, p_push). Exact enumeration of 3^n outcomes. Returns expected return per 1 unit staked - 1."""
    ev = 0.0
    for outc in itertools.product((0, 1, 2), repeat=len(legs)):   # 0 loss,1 win,2 push
        pr = 1.0
        for (pw, pp), o in zip(legs, outc): pr *= (pw if o == 1 else pp if o == 2 else 1 - pw - pp)
        if pr == 0: continue
        n = sum(o != 2 for o in outc); k = sum(o == 1 for o in outc)
        ev += pr * payout(table, n, k)
    return ev - 1

def breakeven(tname, push=0.0):
    table, n = TYPES[tname]
    # p* in terms of P(win); legs iid with P(push)=push
    f = lambda p: entry_ev([(p, push)] * n, table)
    return optimize.brentq(f, 1e-6, 1 - push - 1e-9)

# ---------- distributions ----------
def nb_cdf(x, mu, k): return stats.nbinom.cdf(x, k, k / (k + mu))
def nb_pmf(x, mu, k): return stats.nbinom.pmf(x, k, k / (k + mu))
def probs_at(dist, mu, par, line):
    """(P over, P push, P under) at line."""
    if dist == "nb":
        if line == int(line):
            pp = float(nb_pmf(int(line), mu, par)); po = 1 - float(nb_cdf(int(line), mu, par))
        else: pp = 0.0; po = 1 - float(nb_cdf(math.floor(line), mu, par))
        return po, pp, 1 - po - pp
    po = 1 - stats.norm.cdf(line, mu, par)      # continuous yards: push mass ~0 (integer yards; ignore)
    return po, 0.0, 1 - po
def fit_mu(dist, par, line, p_over_nv):
    """mean such that P(over line) == book no-vig P(over). For whole-number book lines no-vig is conditional on no push."""
    def g(mu):
        po, pp, pu = probs_at(dist, mu, par, line)
        return po / (po + pu) - p_over_nv
    lo, hi = (1e-3, max(5, line * 6) + 30) if dist == "nb" else (line - 20 * par, line + 20 * par)
    try: return optimize.brentq(g, lo, hi)
    except ValueError: return None

def consensus_at(book_lines, dist, par, pp_line):
    per, used = {}, []
    for b, ln, po_nv in book_lines:
        mu = fit_mu(dist, par, ln, po_nv)
        if mu is None: continue
        per.setdefault(b, []).append(probs_at(dist, mu, par, pp_line)); used.append(f"{b}@{ln}")
    vals = []
    for b, v in per.items(): vals += [tuple(np.mean(v, axis=0))] * F.SHARP.get(b, 1)   # one vote per book (x3 Pinnacle)
    if not vals: return None
    a = np.array(vals); med = np.median(a, axis=0)
    return med / med.sum(), used

# ---------- model + vetoes ----------
def nfl_model(analysis_dir=os.path.join(HERE, "analysis")):
    cp = max(glob.glob(os.path.join(analysis_dir, "count_preds_*.csv")), key=os.path.getmtime)
    C = pd.read_csv(cp); M = {}
    for r in C.itertuples(): M[(r.player_display_name, r.odds_api_key)] = ("nb", float(r.mu), 1 / float(r.alpha))
    A = pd.read_csv(max(glob.glob(os.path.join(analysis_dir, "analysis_*_live_*.csv")), key=os.path.getmtime))
    inv = {"pass_yds": "player_pass_yds", "rush_yds": "player_rush_yds", "reception_yds": "player_reception_yds", "rec_yds": "player_reception_yds"}
    V = {}
    for r in A.to_dict("records"):
        mk = inv.get(r["market"], "player_" + str(r["market"]))
        if mk in inv.values() and pd.notna(r.get("model_mu")) and pd.notna(r.get("model_s")) and r.get("model_in_universe"):
            M[(r["player"], mk)] = ("norm", float(r["model_mu"]), float(r["model_s"]))
        V.setdefault((r["player"], mk), r)
    return M, V, os.path.basename(cp)

def nfl_vetoes(V, player, mk, side, line):
    r = V.get((player, mk))
    if r is None: return None, "vetoes n/a (player not in today's analysis run)"
    import analyze as A
    r = dict(r, side=side); r.update({k: ("" if not isinstance(r.get(k), str) else r[k]) for k in ("inj_self", "inj_team_out")})
    sg = A.df_vetoes(r)
    bad = [k for k, v in sg.items() if v[0]]
    return bool(bad), ("VETO " + ",".join(bad) + ": " if bad else "") + " | ".join(f"{k}: {v[1]}" for k, v in sg.items())

def nhl_model():
    import unicodedata, re
    norm = lambda x: re.sub(r"[^a-z]", "", unicodedata.normalize("NFKD", x or "").encode("ascii", "ignore").decode().lower())
    meta = json.load(open(f"/workspace/nhl-sog/models/model_{open('/workspace/nhl-sog/models/CURRENT').read().strip()}.json"))
    fs = sorted(glob.glob("/workspace/nhl-sog/picks/*.csv"), key=os.path.getmtime)
    P = pd.concat([pd.read_csv(f) for f in fs]).drop_duplicates("player", keep="last")
    return {norm(r["player"]): r for r in P.to_dict("records")}, meta["k"], norm

# ---------- main ----------
def legs_from_raw(rawdir, sport):
    events = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(rawdir, "*.json")))]
    if sport == "nfl": M, V, src = nfl_model()
    else: NM, K, norm = nhl_model()
    out = []
    now = pd.Timestamp.now(tz="UTC")
    for ev in events:
        if pd.Timestamp(ev["commence_time"]) <= now: continue          # started
        game = f"{ev['away_team']} @ {ev['home_team']}"
        books, pp = {}, {}
        for b in ev.get("bookmakers", []):
            for m in b["markets"]:
                if m["key"].endswith("_alternate"): continue          # goblins/demons and book alts: standard only
                pr = {}
                for o in m["outcomes"]:
                    if o.get("point") is None: continue
                    pr.setdefault((o["description"], float(o["point"])), {})[o["name"]] = o["price"]
                for (pl, ln), sd in pr.items():
                    if b["key"] == "prizepicks": pp[(pl, m["key"])] = ln
                    elif b["key"] not in F.DFS and "Over" in sd and "Under" in sd:
                        po, pu = F.imp(sd["Over"]), F.imp(sd["Under"])
                        books.setdefault((pl, m["key"]), []).append((b["key"], ln, po / (po + pu)))
        for (pl, mk), ln in pp.items():
            bl = books.get((pl, mk), [])
            nb = len({b for b, _, _ in bl})
            row = dict(game=game, event_id=ev["id"], kickoff_pt=pd.Timestamp(ev["commence_time"]).tz_convert("America/Los_Angeles").strftime("%-I:%M %p PT"),
                       player=pl, market=mk.replace("player_", ""), pp_line=ln, n_books=nb, book_lines=",".join(f"{b}@{l}" for b, l, _ in bl))
            # distribution + model
            if sport == "nhl":
                r = NM.get(norm(pl)); dist, par = "nb", K
                mdl = ("nb", float(r["mu"]), K) if r is not None else None
            else:
                mdl = M.get((pl, mk))
                if mk in COUNT_MK: dist, par = "nb", (mdl[2] if mdl else 30.0)
                else:
                    dist = "norm"; par = mdl[2] if mdl else (DEF_S.get(mk) or max(12.0, 0.55 * ln))
            row["dist"] = f"{dist}({'k' if dist=='nb' else 's'}={par:.1f}{'' if mdl else ',default'})"
            if nb < MIN_BOOKS:
                row["flag"] = f"<{MIN_BOOKS} books"; out.append(row); continue
            c = consensus_at(bl, dist, par, ln)
            if c is None: row["flag"] = "fit failed"; out.append(row); continue
            (po, ppush, pu), used = c
            row.update(books_over=round(po, 4), books_push=round(ppush, 4), books_under=round(pu, 4),
                       same_line_books=sum(1 for _, l, _ in bl if l == ln))
            if mdl:
                mo, mp, mu_ = probs_at(mdl[0], mdl[1], mdl[2], ln); row["model_mu"] = round(mdl[1], 2)
            else: mo = mp = mu_ = None
            for side, bp, mp_side in (("Over", po, mo), ("Under", pu, mu_)):
                r2 = dict(row, side=side)
                r2["model_p"] = None if mp_side is None else round(mp_side, 4)
                r2["blend_win"] = round(bp if mp_side is None else (1 - W_MODEL) * bp + W_MODEL * mp_side, 4)
                r2["push"] = round(ppush if mp is None else (1 - W_MODEL) * ppush + W_MODEL * mp, 4)
                r2["flag"] = "" if mdl else "book-only (no model)"
                if sport == "nfl": v, txt = nfl_vetoes(V, pl, mk, side, ln)
                else:
                    rr = NM.get(norm(pl))
                    if rr is None: v, txt = None, "vetoes n/a (not in NHL picks file)"
                    else:
                        sv = str(rr.get("slot_veto") or "") if pd.notna(rr.get("slot_veto")) else ""
                        l10 = rr.get("l10_over_rate"); fl = (l10 if side == "Over" else 1 - l10) if pd.notna(l10) and rr["line"] == ln else None
                        bad = (sv.upper() == side.upper()) or (fl is not None and fl < 0.40)
                        v, txt = bad, f"slot {rr.get('slot')} opp ratio {rr.get('opp_slot_ratio')}{' VETO' if sv.upper()==side.upper() else ''}; l10 hit {'n/a' if fl is None else f'{fl:.0%}'}"
                r2["veto"], r2["signals"] = v, txt
                out.append(r2)
    return pd.DataFrame(out)

def build(L, top):
    rows, entries = [], []
    ok = L[L.get("blend_win").notna() & (L["veto"] != True)] if "blend_win" in L else L.iloc[0:0]
    for t in TYPES:
        q = []
        for r in ok.to_dict("records"):
            be = breakeven(t, r["push"])
            if r["blend_win"] >= be: q.append(dict(r, type=t, breakeven=round(be, 4)))
        rows += q
        table, n = TYPES[t]
        q = sorted(q, key=lambda r: -(r["blend_win"] - r["breakeven"]))
        # one leg per game (same-game blocked), best legs first; enumerate combos among top candidates
        best = {}
        for r in q: best.setdefault(r["event_id"], r)
        cand = list(best.values())[:12]
        for combo in itertools.combinations(cand, n):
            ev = entry_ev([(r["blend_win"], r["push"]) for r in combo], table[0] if False else TYPES[t][0])
            entries.append(dict(type=t, ev_pct=round(ev * 100, 2), legs=" + ".join(f"{r['player']} {r['market']} {r['side']} {r['pp_line']} ({r['blend_win']:.1%})" for r in combo)))
    E = pd.DataFrame(entries)
    if len(E): E = E[E.ev_pct > 0].sort_values("ev_pct", ascending=False).groupby("type").head(top)
    return pd.DataFrame(rows), E

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--raw", required=True); ap.add_argument("--sport", choices=["nfl", "nhl"], required=True)
    ap.add_argument("--top", type=int, default=5); a = ap.parse_args()
    print("Per-leg break-even (no push):", {t: f"{breakeven(t):.1%}" for t in TYPES})
    L = legs_from_raw(a.raw, a.sport)
    if L.empty: print("no PrizePicks standard lines in un-started games"); return
    Q, E = build(L, a.top)
    os.makedirs(os.path.join(HERE, "analysis"), exist_ok=True)
    stamp = pd.Timestamp.now().strftime("%Y%m%dT%H%M")
    L.to_csv(os.path.join(HERE, "analysis", f"pickem_{a.sport}_legs_{stamp}.csv"), index=False)
    s = L[L.get("blend_win").notna()] if "blend_win" in L else L.iloc[0:0]
    print(f"{L.player.nunique()} PP standard props, {len(s)} priced sides (>= {MIN_BOOKS} books), {int((L['veto']==True).sum()) if 'veto' in L else 0} vetoed, {L.flag.str.startswith('<').sum()} flagged <{MIN_BOOKS} books")
    if len(s):
        top = s.sort_values("blend_win", ascending=False).head(12)
        print("\nTop sides by blended P(win) (shifted P at PP number):")
        for r in top.to_dict("records"):
            print(f"  {r['blend_win']:.1%} (push {r['push']:.1%}) {r['player']} {r['market']} {r['side']} {r['pp_line']} | books {r['n_books']} [{r['book_lines']}] model {r['model_p']} {r['dist']} {r['flag']} veto={r['veto']} | {r['kickoff_pt']} {r['game']}")
    print(f"\nQualifying legs by type: {Q.groupby('type').size().to_dict() if len(Q) else 'none'}")
    for r in Q.to_dict("records") if len(Q) else []:
        print(f"  [{r['type']}] {r['player']} {r['market']} {r['side']} {r['pp_line']} blend {r['blend_win']:.1%} >= BE {r['breakeven']:.1%}  {r['signals']}")
    print(f"\nEntries with EV>0 (one leg per game): {len(E)}")
    for r in E.to_dict("records") if len(E) else []: print(f"  {r['type']} EV {r['ev_pct']:+.1f}%: {r['legs']}")
    if len(Q): Q.to_csv(os.path.join(HERE, "analysis", f"pickem_{a.sport}_qualifying_{stamp}.csv"), index=False)

if __name__ == "__main__": main()
