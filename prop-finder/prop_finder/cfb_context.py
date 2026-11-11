"""College context from CollegeFootballData: prior-season game logs, SP+ ratings, transfer portal,
returning production. Turns them into opponent adjustments, transfer priors and role flags.

CFBD team ids and athlete ids are ESPN ids, so CFBD rows join directly onto the ESPN box-score logs.
"""
from __future__ import annotations

import re
import sys

import numpy as np
import pandas as pd

from . import cfbd
from .stats_common import add_derived

BETA = 0.012          # production multiplier per SP+ point of opponent quality
FCS_GAP = 15.0        # unrated (non-FBS) opponents treated as 15 SP+ points below FBS average
FCS_WEIGHT = 0.5      # weight of a game vs a non-FBS opponent in averages
FCS_CONF_RATING = -25.0
LEVEL_BETA = 0.006    # residual level-jump scaling per point of conference-strength change
FAMILY = {  # stat -> opportunity family used for role scaling
    "pass_yds": "pass", "completions": "pass", "attempts": "pass", "pass_tds": "pass", "interceptions": "pass",
    "pass_rush_yds": "pass", "rush_yds": "rush", "carries": "rush", "rush_tds": "rush",
    "receptions": "rec", "rec_yds": "rec", "rec_tds": "rec", "rush_rec_yds": "touch", "rush_rec_tds": "touch",
}
FAMILY_COL = {"pass": "attempts", "rush": "carries", "rec": "receptions"}


def norm_name(s: str) -> str:
    s = re.sub(r"[^a-z0-9 ]", "", (s or "").lower())
    return re.sub(r"\s+", " ", re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", s)).strip()


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


class Context:
    def __init__(self, season: int, asof_ratings: bool = False):
        """asof_ratings=True (backtests): use the previous season's final SP+ as the current-season rating,
        because CFBD's current-season SP+ for a completed season is end-of-season (lookahead)."""
        self.season = season
        self.asof_ratings = asof_ratings
        prev = season - 1
        self.teams = {y: cfbd.get("/teams", {"year": y}, ttl=None if y < season else 7 * 86400) for y in (prev, season)}
        sp_years = (prev,) if asof_ratings else (prev, season)
        self.sp = {y: cfbd.get("/ratings/sp", {"year": y}, ttl=None if y < season else 86400) for y in sp_years}
        if asof_ratings:
            self.sp[season] = self.sp[prev]
        self.portal = cfbd.get("/player/portal", {"year": season}, ttl=86400)
        self.returning = cfbd.get("/player/returning", {"year": season}, ttl=7 * 86400)
        self.name2id = {y: self._name_map(self.teams[y]) for y in self.teams}
        self.team_info = {y: {str(t["id"]): t for t in self.teams[y]} for y in self.teams}
        self.ratings = {y: self._ratings(y) for y in self.sp}
        if asof_ratings:
            self.ratings[season] = self.ratings[prev]
        self.conf_strength = {y: self._conf_strength(y) for y in self.sp}
        self.logs_prev = self._prev_logs(prev)
        self.ret_by_id = {}
        for r in self.returning:
            tid = self.name2id[season].get(r["team"])
            if tid:
                self.ret_by_id[tid] = r

    # ---------------------------------------------------------------- lookups
    @staticmethod
    def _name_map(teams):
        m = {}
        for t in teams:
            for n in [t["school"]] + list(t.get("alternateNames") or []):
                m.setdefault(n, str(t["id"]))
        return m

    def _ratings(self, year):
        rows = {}
        for r in self.sp[year]:
            tid = self.name2id[year].get(r.get("team"))
            if not tid or (r.get("offense") or {}).get("rating") is None:
                continue
            rows[tid] = {"overall": r.get("rating"), "off": r["offense"]["rating"], "def": r["defense"]["rating"],
                         "conference": r.get("conference")}
        df = pd.DataFrame(rows).T
        self_avg = {"off": float(df["off"].mean()), "def": float(df["def"].mean())}
        return {"by_id": rows, "avg": self_avg}

    def _conf_strength(self, year):
        rat = self.ratings[year]["by_id"]
        conf = {}
        for tid, r in rat.items():
            c = (self.team_info[year].get(tid) or {}).get("conference") or r.get("conference")
            conf.setdefault(c, []).append(r["overall"])
        return {c: float(np.mean(v)) for c, v in conf.items()}

    def is_fbs(self, tid, year) -> bool:
        return str(tid) in self.ratings[year]["by_id"]

    def def_quality(self, tid, year) -> float:
        """SP+ points better than an average defense (positive = good defense)."""
        R = self.ratings[year]
        r = R["by_id"].get(str(tid))
        return (R["avg"]["def"] - r["def"]) if r else -FCS_GAP

    def off_quality(self, tid, year) -> float:
        R = self.ratings[year]
        r = R["by_id"].get(str(tid))
        return (r["off"] - R["avg"]["off"]) if r else -FCS_GAP

    def team_conf(self, tid, year):
        return (self.team_info[year].get(str(tid)) or {}).get("conference")

    def conf_rating(self, tid, year) -> float:
        if not self.is_fbs(tid, year):
            return FCS_CONF_RATING
        return self.conf_strength[year].get(self.team_conf(tid, year), 0.0)

    # ---------------------------------------------------------------- prior-season logs
    def _prev_logs(self, year) -> pd.DataFrame:
        reqs = [("regular", w) for w in range(1, 17)] + [("postseason", 1)]
        rows = []
        for st, wk in reqs:
            try:
                games = cfbd.get("/games/players", {"year": year, "week": wk, "seasonType": st}, ttl=None)
            except Exception as e:  # noqa: BLE001
                print(f"[cfbd] games/players {year} {st} wk{wk} failed: {e}", file=sys.stderr)
                continue
            order = wk if st == "regular" else 20
            for g in games:
                rows.extend(self._parse_game(g, year, order))
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        df = df.drop_duplicates(subset=["game_id", "player_id", "team_id"])
        return add_derived(df)

    def _parse_game(self, g, year, order):
        teams = g.get("teams", [])
        out = {}
        for t in teams:
            tid = self.name2id[year].get(t["team"])
            opp = next((o for o in teams if o is not t), {})
            oid = self.name2id[year].get(opp.get("team"))
            ha = "H" if t.get("homeAway") == "home" else "A"
            for cat in t.get("categories", []):
                cname = cat["name"]
                if cname not in ("passing", "rushing", "receiving"):
                    continue
                for ty in cat["types"]:
                    for a in ty["athletes"]:
                        aid = str(a["id"])
                        if aid.startswith("-"):
                            continue
                        r = out.setdefault((aid, tid), {
                            "league": "ncaaf", "season": year, "week": order, "game_id": str(g["id"]),
                            "game_date": f"{year}-W{order:02d}", "player_id": aid, "espn_id": aid,
                            "player": a["name"], "team": t["team"], "team_id": tid, "opp": opp.get("team"),
                            "opp_id": oid, "home_away": ha, "conference": t.get("conference")})
                        v, n = a["stat"], ty["name"]
                        if cname == "passing":
                            if n == "C/ATT":
                                ca = str(v).split("/")
                                r["completions"], r["attempts"] = _f(ca[0]), _f(ca[1] if len(ca) > 1 else 0)
                            elif n == "YDS": r["pass_yds"] = _f(v)
                            elif n == "TD": r["pass_tds"] = _f(v)
                            elif n == "INT": r["interceptions"] = _f(v)
                        elif cname == "rushing":
                            if n == "CAR": r["carries"] = _f(v)
                            elif n == "YDS": r["rush_yds"] = _f(v)
                            elif n == "TD": r["rush_tds"] = _f(v)
                        elif cname == "receiving":
                            if n == "REC": r["receptions"] = _f(v)
                            elif n == "YDS": r["rec_yds"] = _f(v)
                            elif n == "TD": r["rec_tds"] = _f(v)
        return list(out.values())

    # ---------------------------------------------------------------- adjustments
    def annotate(self, logs: pd.DataFrame) -> pd.DataFrame:
        """Add opponent-quality columns: adj (production multiplier), gw (game weight),
        dvp_adj / dvp_gw (for defense-vs-position, based on the offense faced), opp_is_fbs."""
        logs = logs.copy()
        def per_row(r):
            y = int(r["season"])
            qd = self.def_quality(r["opp_id"], y)
            qo = self.off_quality(r["team_id"], y)
            return pd.Series({
                "adj": float(np.clip(1 + BETA * qd, 0.8, 1.25)),
                "gw": 1.0 if self.is_fbs(r["opp_id"], y) else FCS_WEIGHT,
                "dvp_adj": float(np.clip(1 - BETA * qo, 0.8, 1.25)),
                "dvp_gw": 1.0 if self.is_fbs(r["team_id"], y) else FCS_WEIGHT,
                "opp_is_fbs": self.is_fbs(r["opp_id"], y),
            })
        keys = logs[["season", "opp_id", "team_id"]].drop_duplicates()
        ann = pd.concat([keys.reset_index(drop=True), keys.apply(per_row, axis=1).reset_index(drop=True)], axis=1)
        return logs.merge(ann, on=["season", "opp_id", "team_id"], how="left")

    # ---------------------------------------------------------------- shares / roles
    @staticmethod
    def shares(logs: pd.DataFrame) -> pd.DataFrame:
        """Per (player, team): share of team attempts/carries/receptions/touches in games he appeared."""
        tt = logs.groupby(["game_id", "team_id"])[["attempts", "carries", "receptions"]].sum().add_suffix("_team")
        m = logs.join(tt, on=["game_id", "team_id"])
        g = m.groupby(["player_id", "team_id"]).agg(
            player=("player", "last"), team=("team", "last"), games=("game_id", "nunique"),
            attempts=("attempts", "sum"), carries=("carries", "sum"), receptions=("receptions", "sum"),
            attempts_team=("attempts_team", "sum"), carries_team=("carries_team", "sum"),
            receptions_team=("receptions_team", "sum"))
        for fam, col in FAMILY_COL.items():
            g[f"share_{fam}"] = (g[col] / g[f"{col}_team"]).where(g[f"{col}_team"] > 0, 0.0)
        g["share_touch"] = ((g["carries"] + g["receptions"]) /
                            (g["carries_team"] + g["receptions_team"]).where(lambda x: x > 0, np.nan)).fillna(0.0)
        return g.reset_index()

    def portal_index(self):
        idx = {}
        for p in self.portal:
            nm = norm_name(f"{p.get('firstName', '')} {p.get('lastName', '')}")
            dest = self.name2id[self.season].get(p.get("destination")) if p.get("destination") else None
            idx.setdefault(nm, []).append({**p, "dest_id": dest,
                                           "origin_id": self.name2id[self.season - 1].get(p.get("origin"))
                                           or self.name2id[self.season].get(p.get("origin"))})
        return idx


def build_priors(ctx: Context, logs_cur: pd.DataFrame):
    """Per-player prior (prior-season, opponent-adjusted, level-jump and role scaled) + role/transfer info.

    Returns (priors: dict[player_id] -> dict, transfers: DataFrame, vacated: DataFrame)."""
    season, prev = ctx.season, ctx.season - 1
    lp = ctx.annotate(ctx.logs_prev) if not ctx.logs_prev.empty else ctx.logs_prev
    sh_prev = ctx.shares(ctx.logs_prev)
    sh_cur = ctx.shares(logs_cur)
    portal = ctx.portal_index()
    cur_team = logs_cur.sort_values("game_date").groupby("player_id").tail(1).set_index("player_id")
    prev_by_pid = dict(tuple(lp.groupby("player_id"))) if not lp.empty else {}
    # name index for prior-season fallback matching (team, name) -> player_id
    prev_name = {}
    if not lp.empty:
        for (pid, tid), nm in lp.groupby(["player_id", "team_id"])["player"].last().items():
            prev_name.setdefault((norm_name(nm), tid), pid)
    stats = list(FAMILY)
    priors, transfers = {}, []
    for pid, info in cur_team.iterrows():
        tid26 = info["team_id"]
        nm = norm_name(info["player"])
        prow = prev_by_pid.get(pid)
        p_rec = None
        for cand in portal.get(nm, []):
            if cand["dest_id"] == tid26:
                p_rec = cand
                break
        if prow is None and p_rec and p_rec.get("origin_id"):
            alt = prev_name.get((nm, p_rec["origin_id"]))
            if alt is not None:
                prow = prev_by_pid.get(alt)
        if prow is None or prow.empty:
            if p_rec:
                transfers.append(_transfer_row(ctx, info, p_rec, None, None, None))
            continue
        tid25 = prow.sort_values("game_date")["team_id"].iloc[-1]
        moved = str(tid25) != str(tid26)
        level = 1.0
        if moved:
            d = ctx.conf_rating(tid26, season) - ctx.conf_rating(tid25, prev)
            level = float(np.clip(1 - LEVEL_BETA * d, 0.85, 1.08))
        w = prow["gw"].to_numpy(float)
        a = prow["adj"].to_numpy(float)
        raw = {s: float(prow[s].mean()) for s in stats}
        oppadj = {s: float(np.average(prow[s].to_numpy(float) * a, weights=w)) for s in stats}
        # role: share now vs share last season (per opportunity family)
        s25 = sh_prev[(sh_prev.player_id == prow["player_id"].iloc[0]) & (sh_prev.team_id == tid25)]
        s26 = sh_cur[(sh_cur.player_id == pid) & (sh_cur.team_id == tid26)]
        ratio, rel = {}, {}
        for fam in ("pass", "rush", "rec", "touch"):
            a25 = float(s25[f"share_{fam}"].iloc[0]) if len(s25) else 0.0
            a26 = float(s26[f"share_{fam}"].iloc[0]) if len(s26) else 0.0
            raw_ratio = a26 / a25 if a25 > 0 else np.inf
            # prior = last season's per-opportunity production x this season's opportunity share
            ratio[fam] = float(np.clip(raw_ratio, 0.1, 10.0)) if a25 > 0 else 1.0
            rel[fam] = min(1.0, a25 / 0.10) if a25 > 0 else 0.0
            # a role change bigger than the cap (e.g. backup QB -> starter) makes last season's per-game
            # numbers uninformative: fade the prior instead of extrapolating it
            if a25 > 0 and raw_ratio > 3.0:
                rel[fam] *= 3.0 / raw_ratio
            elif a25 > 0 and raw_ratio < 1 / 3:
                rel[fam] *= raw_ratio * 3.0
        n_prev = int(prow["game_id"].nunique())
        prior = {s: oppadj[s] * level * ratio[FAMILY[s]] for s in stats}
        priors[pid] = {
            "prior": prior, "raw": raw, "oppadj": oppadj, "level": level, "ratio": ratio, "n_prev": n_prev,
            "rel": {s: min(1.0, n_prev / 6) * rel[FAMILY[s]] for s in stats},
            "moved": moved, "team25": prow.sort_values("game_date")["team"].iloc[-1], "team25_id": tid25,
            "share25": {f: float(s25[f"share_{f}"].iloc[0]) if len(s25) else 0.0 for f in ("pass", "rush", "rec", "touch")},
            "share26": {f: float(s26[f"share_{f}"].iloc[0]) if len(s26) else 0.0 for f in ("pass", "rush", "rec", "touch")},
            "portal": p_rec,
        }
        if moved or p_rec:
            transfers.append(_transfer_row(ctx, info, p_rec, prow, priors[pid], tid25))
    vac = vacated_roles(ctx, sh_prev, sh_cur, logs_cur, portal)
    return priors, pd.DataFrame(transfers), vac


def _transfer_row(ctx, info, p_rec, prow, pr, tid25):
    season = ctx.season
    t25 = pr["team25"] if pr else (p_rec or {}).get("origin")
    c25 = ctx.team_conf(tid25, season - 1) if tid25 else None
    if c25 is None and p_rec and p_rec.get("origin_id"):
        c25 = ctx.team_conf(p_rec["origin_id"], season - 1)
    return {
        "player_id": info.name, "player": info["player"], "team_2026": info["team"],
        "conf_2026": ctx.team_conf(info["team_id"], season), "team_2025": t25,
        "conf_2025": c25 or ("non-FBS" if tid25 and not ctx.is_fbs(tid25, season - 1) else None),
        "portal_listed": bool(p_rec), "stars": (p_rec or {}).get("stars"), "portal_pos": (p_rec or {}).get("position"),
        "games_2025": pr["n_prev"] if pr else 0, "level_factor": round(pr["level"], 3) if pr else None,
    }


def vacated_roles(ctx, sh_prev, sh_cur, logs_cur, portal) -> pd.DataFrame:
    """Team-level: share of last season's carries/receptions/attempts by players not on the 2026 team."""
    season = ctx.season
    on_team_26 = set(zip(sh_cur.player_id, sh_cur.team_id))
    where_now = sh_cur.sort_values("games").groupby("player_id").tail(1).set_index("player_id")["team"]
    portal_out = {}
    for nm, recs in portal.items():
        for r in recs:
            if r.get("origin_id"):
                portal_out[(nm, r["origin_id"])] = r.get("destination") or "portal (uncommitted)"
    rows = []
    for tid in sorted(set(sh_cur.team_id.dropna())):
        prev = sh_prev[sh_prev.team_id == tid]
        if prev.empty:
            continue
        gone = prev[[(p, tid) not in on_team_26 for p in prev.player_id]]
        row = {"team_id": tid, "team": sh_cur[sh_cur.team_id == tid]["team"].iloc[0]}
        for fam, col in FAMILY_COL.items():
            tot = prev[col].sum()
            row[f"vacated_{fam}"] = float(gone[col].sum() / tot) if tot > 0 else 0.0
        top = gone.assign(v=gone["carries"] + gone["receptions"] + gone["attempts"] * 0.5).sort_values("v", ascending=False).head(3)
        notes = []
        for r in top.itertuples():
            dest = where_now.get(r.player_id) or portal_out.get((norm_name(r.player), tid))
            notes.append(f"{r.player} ({int(r.carries)} car, {int(r.receptions)} rec, {int(r.attempts)} att"
                         f"{'; now ' + dest if dest else ''})")
        row["top_departed"] = "; ".join(notes)
        ret = ctx.ret_by_id.get(tid) or {}
        row["cfbd_returning_usage"] = ret.get("usage")
        row["cfbd_returning_rush_usage"] = ret.get("rushingUsage")
        row["cfbd_returning_rec_usage"] = ret.get("receivingUsage")
        row["cfbd_returning_pass_usage"] = ret.get("passingUsage")
        rows.append(row)
    return pd.DataFrame(rows)


def role_note(pr: dict | None, vac_row: dict | None, fam: str, share26: dict | None = None) -> tuple[str, bool]:
    """Human-readable role change note + 'stepping into vacated role' flag for a stat family.
    Players with no prior-season FBS/FCS stats count as 0% share last season."""
    fam_v = "rush" if fam == "touch" else fam
    lab = {"pass": "pass-att", "rush": "carry", "rec": "reception"}[fam_v]
    if pr:
        s26, s25 = pr["share26"].get(fam_v), pr["share25"].get(fam_v)
    else:
        s26, s25 = (share26 or {}).get(fam_v), 0.0
        pr = {"team25": None, "moved": False}
    vac = (vac_row or {}).get(f"vacated_{fam_v}")
    flag = False
    parts = []
    if s26 is not None and s25 is not None and (s26 > 0 or s25 > 0):
        prefix = (f"{lab} share {s25:.0%} (2025{', ' + pr['team25'] if pr.get('moved') else ''}) -> {s26:.0%}"
                  if pr.get("team25") or s25 > 0 else f"{lab} share {s26:.0%} (no 2025 stats)")
        parts.append(prefix)
        if vac is not None and vac >= 0.40 and s26 >= s25 + 0.10 and s26 >= 0.15:
            flag = True
    if vac is not None and vac >= 0.40:
        plural = {"pass-att": "pass attempts", "carry": "carries", "reception": "receptions"}[lab]
        parts.append(f"team vacated {vac:.0%} of 2025 {plural}")
    return "; ".join(parts), flag


def make_ctx(c: Context, logs_cur: pd.DataFrame):
    """Build the projection context dict + annotated (current + prior season) logs. Shared by live run and backtest."""
    priors, transfers, vac = build_priors(c, logs_cur)
    sh26 = c.shares(logs_cur).sort_values("games").groupby("player_id").tail(1).set_index("player_id")
    ctx = {"priors": priors, "transfers": transfers, "vacated_df": vac,
           "vacated": {r["team_id"]: r for r in vac.to_dict("records")},
           "share26": {pid: {f: r[f"share_{f}"] for f in ("pass", "rush", "rec", "touch")} for pid, r in sh26.iterrows()}}
    logs = pd.concat([c.annotate(logs_cur), c.annotate(c.logs_prev)], ignore_index=True)
    return ctx, logs
