"""Trend analysis, projections and prop ranking."""
from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd

STATS_BY_POS = {
    "QB": ["pass_yds", "completions", "attempts", "pass_tds", "interceptions", "rush_yds", "pass_rush_yds", "carries"],
    "RB": ["rush_yds", "carries", "receptions", "rec_yds", "rush_rec_yds", "rush_rec_tds"],
    "WR": ["receptions", "rec_yds", "rush_rec_yds", "rush_rec_tds"],
    "TE": ["receptions", "rec_yds", "rush_rec_tds"],
}
POISSON_STATS = {"pass_tds", "interceptions", "rush_tds", "rec_tds", "rush_rec_tds"}
CV = {"pass_yds": 0.28, "completions": 0.22, "attempts": 0.18, "rush_yds": 0.45, "carries": 0.32,
      "receptions": 0.40, "rec_yds": 0.50, "rush_rec_yds": 0.40, "pass_rush_yds": 0.27}
MIN_SD = {"pass_yds": 30, "completions": 3, "attempts": 4, "rush_yds": 12, "carries": 2.5,
          "receptions": 1.2, "rec_yds": 14, "rush_rec_yds": 16, "pass_rush_yds": 32}
PASS_GAME = {"pass_yds", "completions", "attempts", "pass_tds", "interceptions", "receptions", "rec_yds", "pass_rush_yds"}
LABEL = {"pass_yds": "Pass Yds", "completions": "Completions", "attempts": "Pass Att", "pass_tds": "Pass TDs",
         "interceptions": "INTs", "rush_yds": "Rush Yds", "carries": "Carries", "receptions": "Receptions",
         "rec_yds": "Rec Yds", "rush_rec_yds": "Rush+Rec Yds", "pass_rush_yds": "Pass+Rush Yds",
         "rush_rec_tds": "Rush+Rec TDs"}
# minimum season per-game volume to be considered a real role for the stat
ROLE_MIN = {"QB": ("attempts", 12), "RB": ("carries", 4), "WR": ("receptions", 1.5), "TE": ("receptions", 1.5)}
OUT_STATUSES = {"Out", "Doubtful", "Injured", "Suspended"}
SHRINK_K = 0.4           # pseudo-games of position-average added to yardage/volume stats
SHRINK_K_POISSON = 5.0   # pseudo-games for TD / INT rates
P_SHRINK = 0.2           # displayed/calibrated P(over) = 0.5 + P_SHRINK * (raw - 0.5)  [2025 backtest: was 0.75]
RANK_SHRINK = 1.0        # edge scale inside rank_score (ordering heuristic, separate from calibration) [backtest: was 0.75 via P_SHRINK]
BREAKEVEN_NO_PRICE = 110 / 210
AGREE_W = 20.0          # rank_score weight on the player's last-10 hit rate for the picked side [backtest: was 10]
# guard discounts on rank_score (a discount never improves a pick: negative scores are pushed further down)
GUARD_FAR_F, GUARD_MATE_UNDER_F, GUARD_MISSED_F, GUARD_SMALL_F = 0.35, 0.35, 0.6, 1.0   # small-sample: flag only [backtest: was 0.6]


def _discount(score: float, f: float) -> float:
    return score * f if score > 0 else score * (2 - f)


# blend / adjustment strengths (module-level so the backtest can evaluate alternatives)
W_SEASON, W_L3, W_PRIOR = 0.50, 0.20, 0.30     # NFL: season avg / last-3 / previous season [backtest: was .45/.35/.20]
CFB_W_SEASON = 0.70                             # college: season vs last-3 split of the current-season blend [backtest: was 0.55]
CFB_PRIOR_START, CFB_PRIOR_DECAY, CFB_PRIOR_FLOOR = 0.70, 0.08, 0.05   # [backtest: decay was 0.13]
MATCHUP_STRENGTH = 0.3                          # NFL: share of the (shrunk) DVP ratio deviation applied [backtest: was 0.6]
CFB_MATCHUP_STRENGTH = 0.6                      # college (backtest: no better value found)
ENV_STRENGTH = 0.5                              # NFL: scales the implied-team-total adjustment [backtest: was 1.0]
CFB_ENV_STRENGTH = 1.0                          # college (backtest: no better value found)


def _phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _pois_cdf(k: int, lam: float) -> float:
    lam = max(lam, 1e-6)
    return sum(math.exp(-lam) * lam ** i / math.factorial(i) for i in range(0, k + 1))


def p_over(stat: str, proj: float, sd: float, line: float) -> float:
    if stat in POISSON_STATS:
        return 1 - _pois_cdf(int(math.floor(line)), proj)
    return 1 - _phi((line - proj) / max(sd, 1e-6))


def implied_prob(american) -> float | None:
    if american is None or (isinstance(american, float) and math.isnan(american)):
        return None
    a = float(american)
    return 100 / (a + 100) if a > 0 else -a / (-a + 100)


def ordinal(n: int) -> str:
    return f"{n}{'tsnrhtdd'[(n // 10 % 10 != 1) * (n % 10 < 4) * n % 10::4]}"


# --------------------------------------------------------------- defense vs position
def defense_vs_position(logs_cur: pd.DataFrame) -> pd.DataFrame:
    """Per-game production allowed by each defense to each position group.
    If the logs carry CFBD annotations (dvp_adj / dvp_gw / opp_is_fbs), each game is adjusted for the
    quality of the offense faced, games vs non-FBS offenses are down-weighted, and only FBS defenses are ranked."""
    stats = sorted({s for v in STATS_BY_POS.values() for s in v})
    adj = "dvp_adj" in logs_cur.columns
    L = logs_cur.copy()
    if adj:
        L[stats] = L[stats].mul(L["dvp_adj"].fillna(1.0), axis=0)
    g = L.groupby(["game_id", "opp", "pos_group"])[stats].sum().reset_index()
    extra = ["dvp_gw", "opp_is_fbs"] if adj else []
    games = L[["game_id", "opp"] + extra].drop_duplicates(["game_id", "opp"])
    full = games.merge(pd.DataFrame({"pos_group": ["QB", "RB", "WR", "TE"]}), how="cross")
    g = full.merge(g, on=["game_id", "opp", "pos_group"], how="left")
    g[stats] = g[stats].fillna(0.0)
    g["_w"] = g["dvp_gw"].fillna(1.0) if adj else 1.0
    if adj:
        g = g[g["opp_is_fbs"].fillna(False).astype(bool)]
    wsum = g.groupby(["opp", "pos_group"])["_w"].sum()
    per = g[stats].mul(g["_w"], axis=0).groupby([g["opp"], g["pos_group"]]).sum().div(wsum, axis=0)
    n = g.groupby(["opp", "pos_group"]).size().rename("def_games")
    lg = g[stats].mul(g["_w"], axis=0).groupby(g["pos_group"]).sum().div(g.groupby("pos_group")["_w"].sum(), axis=0)
    rows = []
    for (team, pg), r in per.iterrows():
        for s_ in stats:
            base = lg.loc[pg, s_]
            rows.append({"def_team": team, "pos_group": pg, "stat": s_, "allowed_pg": r[s_],
                         "lg_avg": base, "ratio": (r[s_] / base) if base > 0 else 1.0,
                         "def_games": int(n.loc[(team, pg)]), "opp_adjusted": adj})
    d = pd.DataFrame(rows)
    # rank only among teams with a real sample (drops FCS opponents seen once or twice in college)
    d = d[d["def_games"] >= max(1, int(0.6 * d["def_games"].max()))].copy()
    d["rank_most_allowed"] = d.groupby(["pos_group", "stat"])["allowed_pg"].rank(ascending=False, method="min").astype(int)
    d["n_teams"] = d.groupby(["pos_group", "stat"])["def_team"].transform("count")
    return d


# --------------------------------------------------------------- projections
def build_projections(logs: pd.DataFrame, season: int, slate: list[dict], team_pts: pd.DataFrame,
                      injuries: dict, weather: dict, league: str, ctx: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """logs: standardized logs (may include prior season). slate games carry 'home'/'away' in log team space."""
    logs = logs.sort_values(["game_date", "game_id"])
    cur = logs[logs["season"] == season]
    dvp = defense_vs_position(cur)
    dvp_idx = dvp.set_index(["def_team", "pos_group", "stat"])
    tp = team_pts[team_pts["season"] == season].groupby("team")["pts"].mean()

    # each player's most recent team in the current season
    last_team = cur.groupby("player_id").tail(1).set_index("player_id")["team"]
    team_last_game = cur.groupby("team")["game_date"].max()
    by_player = dict(tuple(logs.groupby("player_id")))
    pos_means = position_means(cur)
    # injury status for every player who has logged stats this season (for teammate-out detection)
    role_avg = {}
    out_by_team_pos: dict[tuple, list] = {}
    for pid, pc0 in cur.groupby("player_id"):
        pg0 = pc0["pos_group"].iloc[-1]
        if pg0 not in ROLE_MIN:
            continue
        rs = ROLE_MIN[pg0][0]
        role_avg[pid] = pc0[rs].mean()
        inf = pc0.iloc[-1]
        st = (injuries.get(str(pid)) or injuries.get(str(inf.get("espn_id"))) or {}).get("status")
        if isinstance(st, str) and st.split(" ")[0] in OUT_STATUSES:
            out_by_team_pos.setdefault((inf["team"], pg0), []).append((pid, inf["player"], st, role_avg[pid]))
    rows = []
    for g in slate:
        if g.get("completed"):
            continue
        for side, team, opp in (("home", g["home"], g["away"]), ("away", g["away"], g["home"])):
            ha = "N" if g.get("neutral") else ("H" if side == "home" else "A")
            pids = last_team[last_team == team].index
            implied = g.get(f"{side}_implied")
            avg_pts = tp.get(team)
            wx = weather.get(g["event_id"], {})
            for pid in pids:
                pl = by_player[pid]
                pg = pl[pl["season"] == season]["pos_group"].iloc[-1]
                if pg not in STATS_BY_POS:
                    continue
                if pg == "QB":  # drop games a QB clearly didn't play through (injury exit / mop-up)
                    full = pl[pl["attempts"] >= 10]
                    if (full["season"] == season).any():
                        pl = full
                pc = pl[pl["season"] == season]
                role_stat, role_min = ROLE_MIN[pg]
                if pc[role_stat].mean() < role_min:
                    continue
                info = pc.iloc[-1]
                inj = injuries.get(str(pid)) or injuries.get(str(info.get("espn_id")))
                missed_last = team_last_game.get(team) is not None and pc["game_date"].max() < team_last_game.get(team)
                prior = pl[pl["season"] < season]
                mates = [f"{n} ({st})" for (opid, n, st, ra) in out_by_team_pos.get((team, pg), [])
                         if opid != pid and ra >= 0.6 * role_avg.get(pid, 0)]
                for stat in STATS_BY_POS[pg]:
                    r = _project_one(stat, pl, pc, prior, pg, info, g, team, opp, ha, implied, avg_pts,
                                     wx, inj, missed_last, dvp_idx, league, pos_means, ctx)
                    if r:
                        r["teammate_out"] = "; ".join(mates)
                        rows.append(r)
    proj = pd.DataFrame([r for r in rows if r])
    return proj, dvp


def position_means(cur: pd.DataFrame) -> dict:
    """Per-game mean of each stat among role players at each position group (current season)."""
    out = {}
    for pg, (rs, mn) in ROLE_MIN.items():
        d = cur[cur["pos_group"] == pg]
        roles = d.groupby("player_id")[rs].mean()
        d = d[d["player_id"].isin(roles[roles >= mn].index)]
        for stat in STATS_BY_POS[pg]:
            out[(pg, stat)] = float(d[stat].mean()) if len(d) else 0.0
    return out


def college_prior_weight(n_cur: int) -> float:
    """Prior-season weight before reliability scaling: heavy early, ~gone by week 5-6."""
    return float(np.clip(CFB_PRIOR_START - CFB_PRIOR_DECAY * n_cur, CFB_PRIOR_FLOOR, CFB_PRIOR_START))


def _project_one(stat, pl, pc, prior, pg, info, g, team, opp, ha, implied, avg_pts, wx, inj, missed_last,
                 dvp_idx, league, pos_means, ctx=None):
    vals_cur = pc[stat].to_numpy(float)
    vals_all = pl[stat].to_numpy(float)
    n_cur = len(vals_cur)
    if n_cur == 0:
        return None
    season_avg = vals_cur.mean()
    l5 = vals_all[-5:].mean()
    extra = {}
    if ctx is not None:  # college + CFBD: opponent-adjusted current season blended with a transfer-aware prior
        from .cfb_context import FAMILY, role_note
        l3 = vals_cur[-3:].mean()
        a = pc["adj"].fillna(1.0).to_numpy(float)
        w8 = pc["gw"].fillna(1.0).to_numpy(float)
        av = vals_cur * a
        season_adj = float(np.average(av, weights=w8))
        l3_adj = float(np.average(av[-3:], weights=w8[-3:]))
        cur_blend = CFB_W_SEASON * season_adj + (1 - CFB_W_SEASON) * l3_adj
        pinfo = ctx["priors"].get(info["player_id"])
        wp, prior_val = 0.0, None
        if pinfo:
            prior_val = pinfo["prior"][stat]
            wp = college_prior_weight(n_cur) * pinfo["rel"][stat]
        base = wp * prior_val + (1 - wp) * cur_blend if prior_val is not None else cur_blend
        prior_avg = pinfo["raw"][stat] if pinfo else np.nan
        n_prior = pinfo["n_prev"] if pinfo else 0
        fam = FAMILY[stat]
        note, vac_flag = role_note(pinfo, ctx["vacated"].get(info.get("team_id")), fam,
                                   ctx["share26"].get(info["player_id"]))
        extra = {
            "season_avg_oppadj": round(season_adj, 2), "prior_oppadj": round(pinfo["oppadj"][stat], 2) if pinfo else None,
            "prior_final": round(prior_val, 2) if prior_val is not None else None, "prior_weight": round(wp, 3),
            "transfer_from": (pinfo["team25"] if pinfo and pinfo["moved"] else None),
            "level_factor": round(pinfo["level"], 3) if pinfo and pinfo["moved"] else None,
            "role_ratio": round(pinfo["ratio"][fam], 2) if pinfo else None,
            "role_note": note, "vacated_role": vac_flag,
        }
        n_eff = n_cur + 6 * wp
    else:
        l3 = vals_all[-3:].mean()
        prior_avg = prior[stat].mean() if len(prior) else np.nan
        n_prior = len(prior)
        w = {"season": W_SEASON, "l3": W_L3, "prior": W_PRIOR * min(1.0, n_prior / 8) if n_prior else 0.0}
        if n_cur <= 2 and n_prior >= 6:
            w["prior"] = 2 * W_PRIOR
        base = (w["season"] * season_avg + w["l3"] * l3 + (w["prior"] * prior_avg if w["prior"] else 0)) / sum(w.values())
        n_eff = n_cur + 0.5 * min(n_prior, 8)
    # empirical-Bayes style shrinkage toward the position mean (strong for TD/INT counts)
    k = SHRINK_K_POISSON if stat in POISSON_STATS else SHRINK_K
    pm = pos_means.get((pg, stat))
    if pm is not None:
        base = (n_eff * base + k * pm) / (n_eff + k)

    # matchup: opponent defense vs this position group
    m_mult, m_note, dvp_rank, dvp_ratio = 1.0, "", None, None
    try:
        d = dvp_idx.loc[(opp, pg, stat)]
        k = d["def_games"] / (d["def_games"] + 4)
        ms = CFB_MATCHUP_STRENGTH if league == "ncaaf" else MATCHUP_STRENGTH
        m_mult = float(np.clip(1 + ms * k * (d["ratio"] - 1), 0.8, 1.2))
        dvp_rank, dvp_ratio = int(d["rank_most_allowed"]), round(float(d["ratio"]), 2)
        m_note = f"{opp} allows {d['allowed_pg']:.1f}/g to {pg}s ({ordinal(dvp_rank)} most of {int(d['n_teams'])}, x{dvp_ratio:.2f} lg avg)"
    except KeyError:
        pass
    # game environment: implied team total vs season scoring average
    e_mult = 1.0
    if implied and avg_pts and avg_pts > 0 and stat != "interceptions":
        r = implied / avg_pts
        f = 0.7 if stat in POISSON_STATS else (0.35 if stat not in ("attempts",) else 0.15)
        es = CFB_ENV_STRENGTH if league == "ncaaf" else ENV_STRENGTH
        e_mult = float(np.clip(1 + es * f * (r - 1), 0.88, 1.12))
    # weather (outdoor only)
    w_mult, w_note = 1.0, ""
    gust, prc = wx.get("gust_mph"), wx.get("precip_pct")
    if stat in PASS_GAME and stat != "interceptions" and wx.get("weather") not in (None, "Indoor", "n/a"):
        if gust is not None and gust >= 30:
            w_mult *= 0.92
        elif gust is not None and gust >= 22:
            w_mult *= 0.96
        if prc is not None and prc >= 60:
            w_mult *= 0.97
        if w_mult < 1:
            w_note = f"weather: {wx.get('weather')}"
    proj = base * m_mult * e_mult * w_mult

    recent = vals_all[-10:]
    if stat in POISSON_STATS:
        sd = math.sqrt(max(proj, 0.05))
    else:
        sd_s = recent.std(ddof=1) if len(recent) >= 4 else 0
        sd = max(0.5 * sd_s + 0.5 * CV[stat] * proj, CV[stat] * proj * 0.8, MIN_SD[stat])

    h = pl[pl["home_away"] == "H"][stat]
    a = pl[pl["home_away"] == "A"][stat]
    trend = "flat"
    if n_cur >= 2 and season_avg > 0:
        if l3 > season_avg * 1.15:
            trend = "up"
        elif l3 < season_avg * 0.85:
            trend = "down"
    return {
        "league": league, "event_id": g["event_id"], "game": g["name"], "kickoff_utc": g["date_utc"],
        "game_state": g["state"], "player_id": info["player_id"], "espn_id": info.get("espn_id"),
        "player": info["player"], "pos": info.get("position"), "pos_group": pg, "team": team, "opp": opp,
        "home_away": ha, "stat": stat, "stat_label": LABEL[stat],
        "projection": round(proj, 2), "base_proj": round(base, 2),
        "season_avg": round(season_avg, 2), "games_season": n_cur,
        "l3_avg": round(l3, 2), "l5_avg": round(l5, 2),
        "prior_season_avg": None if np.isnan(prior_avg) else round(prior_avg, 2), "games_prior": n_prior,
        "home_avg": round(h.mean(), 2) if len(h) else None, "home_n": len(h),
        "away_avg": round(a.mean(), 2) if len(a) else None, "away_n": len(a),
        "last5_values": ",".join(f"{v:g}" for v in vals_all[-5:]),
        "trend": trend, "sd": round(sd, 2),
        "matchup_mult": round(m_mult, 3), "env_mult": round(e_mult, 3), "weather_mult": round(w_mult, 3),
        "opp_dvp_rank": dvp_rank, "opp_dvp_ratio": dvp_ratio, "matchup_note": m_note,
        "implied_team_total": implied, "team_avg_pts": None if avg_pts is None else round(avg_pts, 1),
        "weather": wx.get("weather"), "weather_note": w_note,
        "injury_status": (inj or {}).get("status"), "injury_detail": (inj or {}).get("detail"),
        "missed_team_last_game": bool(missed_last),
        "p_anytime_td": round(1 - math.exp(-proj), 3) if stat == "rush_rec_tds" else None,
        "vals_cur": vals_cur, "vals_all": vals_all, **extra,
    }


# --------------------------------------------------------------- ranking vs lines
def _name_norm(s):
    s = re.sub(r"[^a-z0-9 ]", "", (s or "").lower())
    return re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", s).strip()


def rank_props(proj: pd.DataFrame, lines: pd.DataFrame) -> pd.DataFrame:
    if proj.empty or lines.empty:
        return pd.DataFrame()
    p = proj.copy()
    p["espn_id"] = p["espn_id"].astype(str)
    p["player_norm"] = p["player"].map(_name_norm)
    out = []
    by_espn = {(r.espn_id, r.event_id, r.stat): r for r in p.itertuples()}
    by_name = {(r.player_norm, r.event_id, r.stat): r for r in p.itertuples()}
    for ln in lines.itertuples():
        r = None
        if isinstance(ln.espn_id, str) and ln.espn_id:
            r = by_espn.get((ln.espn_id, ln.event_id, ln.stat))
        if r is None and isinstance(getattr(ln, "player_norm", None), str):
            r = by_name.get((ln.player_norm, ln.event_id, ln.stat))
        if r is None:
            continue
        line = float(ln.line)
        po_raw = p_over(r.stat, r.projection, r.sd, line)
        po = 0.5 + P_SHRINK * (po_raw - 0.5)
        vc, va = r.vals_cur, r.vals_all
        hit_season = float((vc > line).mean()) if len(vc) else np.nan
        hit_l5 = float((va[-5:] > line).mean()) if len(va) else np.nan
        hit_l10 = float((va[-10:] > line).mean()) if len(va) else np.nan
        side = "OVER" if po >= 0.5 else "UNDER"
        p_side = po if side == "OVER" else 1 - po
        price = ln.over_price if side == "OVER" else ln.under_price
        be = implied_prob(price) or BREAKEVEN_NO_PRICE
        hs = lambda h: h if side == "OVER" else 1 - h  # noqa: E731
        n_tot = len(va)
        conf = min(1.0, n_tot / 6)
        agree = hs(hit_l10) if not np.isnan(hit_l10) else 0.5
        p_rank = 0.5 + RANK_SHRINK * abs(po_raw - 0.5)
        score = 100 * (p_rank - be) * conf + AGREE_W * (agree - 0.5)
        raw_score = score
        g_far = g_mate = g_missed = g_small = False
        flags = []
        hist_hi, hist_lo = max(r.season_avg, r.l3_avg), min(r.season_avg, r.l3_avg)
        far = line >= 1.5 and ((side == "UNDER" and line > 1.5 * max(hist_hi, 0.1)) or
                               (side == "OVER" and line < 0.67 * hist_lo))
        g_far = bool(far)
        if far:
            flags.append("line far from player's history -> market likely pricing a role change; edge discounted")
            score = _discount(score, GUARD_FAR_F)
        mates = r.teammate_out if isinstance(r.teammate_out, str) else ""
        g_mate = bool(mates)
        if mates:
            flags.append(f"teammate out at {r.pos_group}: {mates} (usage may rise)")
            if side == "UNDER":
                score = _discount(score, GUARD_MATE_UNDER_F)
        inj_s = r.injury_status if isinstance(r.injury_status, str) else ""
        inj_d = r.injury_detail if isinstance(r.injury_detail, str) else ""
        if inj_s:
            flags.append(f"injury: {inj_s}{' (' + inj_d + ')' if inj_d else ''}")
        g_missed = bool(r.missed_team_last_game)
        g_small = bool(r.games_season < 2)
        if r.missed_team_last_game:
            flags.append("no stats in team's last game")
            score = _discount(score, GUARD_MISSED_F)
        if r.games_season < 2:
            flags.append("small sample")
            score = _discount(score, GUARD_SMALL_F)
        if r.game_state != "pre":
            flags.append("game already started (pregame line shown)")
        if r.weather_note:
            flags.append(r.weather_note)
        out.append({
            "rank_score": round(score, 2), "raw_score": round(raw_score, 2), "p_over_raw": round(po_raw, 4),
            "p_over": round(po, 4), "player_id": r.player_id, "event_id": r.event_id,
            "guard_far_line": g_far, "guard_teammate_out": g_mate, "guard_missed_last": g_missed,
            "guard_small_sample": g_small, "sd": r.sd, "base_proj": r.base_proj, "matchup_mult": r.matchup_mult,
            "env_mult": r.env_mult, "weather_mult": r.weather_mult,
            "league": r.league, "game": r.game, "kickoff_utc": r.kickoff_utc,
            "game_state": r.game_state, "bettable_now": r.game_state == "pre" and inj_s not in ("Out", "Doubtful"),
            "player": r.player, "pos": r.pos, "team": r.team, "opp": r.opp, "home_away": r.home_away,
            "prop": r.stat_label, "stat": r.stat, "line": line, "line_open": ln.line_open, "book": ln.book,
            "source": ln.source, "line_note": ln.line_note, "over_price": ln.over_price, "under_price": ln.under_price,
            "pick": side, "projection": r.projection, "edge": round(r.projection - line, 2),
            "edge_pct": round((r.projection - line) / line * 100, 1) if line else None,
            "model_p_side": round(p_side, 3), "breakeven": round(be, 3),
            "hit_rate_season_side": None if np.isnan(hit_season) else round(hs(hit_season), 2),
            "hit_rate_l5_side": None if np.isnan(hit_l5) else round(hs(hit_l5), 2),
            "hit_rate_l10_side": None if np.isnan(hit_l10) else round(hs(hit_l10), 2),
            "season_avg": r.season_avg, "games_season": r.games_season, "l3_avg": r.l3_avg, "l5_avg": r.l5_avg,
            "prior_season_avg": r.prior_season_avg, "home_avg": r.home_avg, "away_avg": r.away_avg,
            "last5_values": r.last5_values, "trend": r.trend, "matchup_note": r.matchup_note,
            "teammate_out": mates or None,
            "opp_dvp_rank": r.opp_dvp_rank, "implied_team_total": r.implied_team_total,
            "weather": r.weather, "injury_status": inj_s or None, "flags": "; ".join(flags),
        })
    df = pd.DataFrame(out)
    if df.empty:
        return df
    # an injured-out player's line is not actionable
    df.loc[df["injury_status"].isin(["Out", "Doubtful"]), "rank_score"] -= 100
    return df.sort_values("rank_score", ascending=False).reset_index(drop=True)
