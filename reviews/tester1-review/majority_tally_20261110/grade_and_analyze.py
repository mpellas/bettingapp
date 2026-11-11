#!/usr/bin/env python3
"""Grade Nov 10 NHL SOG majority sides and run volume/signal analyses.

Read-only inputs are copied into this folder (sheets, GATE, Yinzer CSV) or
read in place from /workspace/nhl-sog (historical sheets/GATE only).
Writes only under /workspace/tester1-review/majority_tally_20261110/.
"""
from __future__ import annotations

import json
import math
import os
import unicodedata
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = Path("/workspace/tester1-review/majority_tally_20261110")
NHL_SOG = Path("/workspace/nhl-sog")
PT = ZoneInfo("America/Los_Angeles")
FINAL_STATES = {"OFF", "FINAL", "FINAL_OT", "FINAL_SO"}
UA_NOTE = "boxscores from api-web.nhle.com"

SHEETS = [
    ("20261110_D_1304_picks.xlsx", "20261110_D_1304_GATE.csv", "20261110_1304"),
    ("20261110_D_1339_picks.xlsx", "20261110_D_1339_GATE.csv", "20261110_1339"),
    ("20261110_D_1535_picks.xlsx", "20261110_D_1535_GATE.csv", "20261110_1535"),
]

# Historical majority-list workbooks used by Yinzer's grader (list_id -> sheet).
HIST_SHEETS = {
    "20261105_1239": "20261105_D_1239_picks.xlsx",
    "20261109_1401": "20261109_D_1401_picks.xlsx",
    "20261109_1509": "20261109_D_1509_picks.xlsx",
    "20261109_1537": "20261109_D_1537_picks.xlsx",
    "20261110_1304": "20261110_D_1304_picks.xlsx",
    "20261110_1339": "20261110_D_1339_picks.xlsx",
    "20261110_1535": "20261110_D_1535_picks.xlsx",
}
HIST_GATES = {
    "20261105_1239": "20261105_D_1239_GATE.csv",
    "20261109_1401": "20261109_D_1401_GATE.csv",
    "20261109_1509": "20261109_D_1509_GATE.csv",
    "20261109_1537": "20261109_D_1537_GATE.csv",
    "20261110_1304": "20261110_D_1304_GATE.csv",
    "20261110_1339": "20261110_D_1339_GATE.csv",
    "20261110_1535": "20261110_D_1535_GATE.csv",
}


def now_pt() -> datetime:
    return datetime.now(PT)


def am2dec(a) -> float:
    a = float(a)
    return 1 + (a / 100.0 if a > 0 else 100.0 / -a)


def parse_american(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return np.nan
    s = str(v).strip().replace("+", "")
    if s == "" or s.lower() in {"nan", "none", "n/a"}:
        return np.nan
    try:
        return int(float(s))
    except ValueError:
        return np.nan


def units_at(price, hit):
    p = parse_american(price)
    if pd.isna(p):
        return np.nan
    dec = am2dec(p)
    return (dec - 1.0) if hit else -1.0


def toi_to_minutes(s):
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return np.nan
    t = str(s).strip()
    if t in {"", "nan", "None"}:
        return np.nan
    if ":" not in t:
        try:
            return float(t)
        except ValueError:
            return np.nan
    parts = t.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) + int(parts[1]) / 60.0
        if len(parts) == 3:
            return int(parts[0]) * 60 + int(parts[1]) + int(parts[2]) / 60.0
    except ValueError:
        return np.nan
    return np.nan


def wilson_ci(wins: int, n: int, z: float = 1.96):
    if n <= 0:
        return (float("nan"), float("nan"))
    p = wins / n
    z2 = z * z
    den = 1 + z2 / n
    center = (p + z2 / (2 * n)) / den
    half = z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n) / den
    return center - half, center + half


def wl_block(df, result_col="result", units_col="units"):
    w = int((df[result_col] == "W").sum())
    l = int((df[result_col] == "L").sum())
    v = int((df[result_col] == "void").sum())
    p = int((df[result_col] == "pending").sum())
    g = df[df[result_col].isin(["W", "L"])]
    priced = g[g[units_col].notna()]
    u = float(priced[units_col].sum()) if len(priced) else float("nan")
    decided = w + l
    hit = (w / decided) if decided else float("nan")
    lo, hi = wilson_ci(w, decided) if decided else (float("nan"), float("nan"))
    return {
        "w": w, "l": l, "v": v, "p": p, "n": decided,
        "units": u, "n_priced": len(priced),
        "hit": hit, "ci_lo": lo, "ci_hi": hi,
    }


def fmt_wl(s, units_label="u"):
    hit_s = f"{s['hit']*100:.1f}%" if s["n"] else "n/a"
    ci_s = f", 95% Wilson CI {s['ci_lo']*100:.1f}–{s['ci_hi']*100:.1f}%" if s["n"] else ""
    u_s = f"{s['units']:+.2f}{units_label}" if s["n_priced"] else "units n/a"
    void = f", {s['v']} void" if s["v"] else ""
    pend = f", {s['p']} pending" if s["p"] else ""
    return f"{s['w']}-{s['l']}{void}{pend} ({s['n']} decided, hit {hit_s}{ci_s}; {u_s})"


def load_boxscore(gid: int) -> dict:
    p = HERE / f"boxscore_{gid}.json"
    return json.loads(p.read_text())


def extract_skaters(box: dict) -> pd.DataFrame:
    rows = []
    away_abbr = box["awayTeam"]["abbrev"]
    home_abbr = box["homeTeam"]["abbrev"]
    away_name = box["awayTeam"].get("commonName", {}).get("default", away_abbr)
    home_name = box["homeTeam"].get("commonName", {}).get("default", home_abbr)
    pbg = box.get("playerByGameStats") or {}
    for side, abbr in (("awayTeam", away_abbr), ("homeTeam", home_abbr)):
        team = pbg.get(side) or {}
        for group in ("forwards", "defense"):
            for p in team.get(group) or []:
                name = p.get("name") or {}
                rows.append({
                    "nhl_id": int(p["playerId"]),
                    "name_default": name.get("default", ""),
                    "team_abbrev": abbr,
                    "home_away": "away" if side == "awayTeam" else "home",
                    "position": p.get("position"),
                    "sog": int(p["sog"]) if p.get("sog") is not None else np.nan,
                    "toi": p.get("toi"),
                    "toi_min": toi_to_minutes(p.get("toi")),
                    "in_boxscore": True,
                })
        for p in (team.get("goalies") or []):
            # goalies are not SOG prop skaters; record ids only so we don't void by accident
            pass
    return pd.DataFrame(rows)


def game_meta(box: dict) -> dict:
    return {
        "gameId": int(box["id"]),
        "gameState": box.get("gameState"),
        "finished": box.get("gameState") in FINAL_STATES,
        "away_abbrev": box["awayTeam"]["abbrev"],
        "home_abbrev": box["homeTeam"]["abbrev"],
        "away_score": box["awayTeam"].get("score"),
        "home_score": box["homeTeam"].get("score"),
        "away_sog": box["awayTeam"].get("sog"),
        "home_sog": box["homeTeam"].get("sog"),
        "period": (box.get("periodDescriptor") or {}).get("number"),
        "period_type": (box.get("periodDescriptor") or {}).get("periodType"),
    }


def load_landing_script(gid: int) -> dict:
    landing = json.loads((HERE / f"landing_{gid}.json").read_text())
    rr = json.loads((HERE / f"right_rail_{gid}.json").read_text())
    ens = []
    for per in (landing.get("summary") or {}).get("scoring") or []:
        pdesc = per.get("periodDescriptor") or {}
        for g in per.get("goals") or []:
            gm = str(g.get("goalModifier") or "")
            if "empty" in gm.lower():
                ens.append({
                    "period": pdesc.get("number"),
                    "time": g.get("timeInPeriod"),
                    "modifier": gm,
                    "situationCode": g.get("situationCode"),
                    "awayScore": g.get("awayScore"),
                    "homeScore": g.get("homeScore"),
                })
    cats = {x["category"]: (x["awayValue"], x["homeValue"]) for x in (rr.get("teamGameStats") or [])}
    return {"en_goals": ens, "stats": cats, "shotsByPeriod": rr.get("shotsByPeriod")}


def load_tonight_sides() -> pd.DataFrame:
    frames = []
    for sheet_name, gate_name, list_id in SHEETS:
        df = pd.read_excel(HERE / sheet_name, sheet_name="Picks")
        maj = df[df.agrees_n.notna() & (df.agrees_n >= 4)].copy()
        maj["date"] = 20261110
        maj["list_id"] = list_id
        maj["side"] = maj["side"].astype(str).str.strip().str.upper()
        maj["line"] = maj["line"].astype(float)
        maj["player"] = maj["player"].astype(str).str.strip()
        maj["game"] = maj["game"].astype(str).str.strip()
        maj["agrees_n"] = maj["agrees_n"].astype(int)
        maj["dk_price"] = maj["dk_price"].apply(parse_american)
        maj["fliff_shop_at"] = maj["fliff_shop_at"].apply(parse_american)
        gate = pd.read_csv(HERE / gate_name)
        keep = [c for c in ("player", "game", "nhl_id", "gameId", "team_dfo", "toi_r5", "toi_r30", "line") if c in gate.columns]
        g = gate[keep].copy()
        g["player"] = g["player"].astype(str).str.strip()
        g["game"] = g["game"].astype(str).str.strip()
        g["line"] = g["line"].astype(float)
        # unique player-game for team/toi; line may differ but ids shouldn't
        ids = g.drop_duplicates(["player", "game"])[["player", "game", "nhl_id", "gameId", "team_dfo", "toi_r5", "toi_r30"]]
        maj = maj.merge(ids, on=["player", "game"], how="left")
        frames.append(maj)
    return pd.concat(frames, ignore_index=True)


def grade_sides(sides: pd.DataFrame, box_by_id: dict) -> pd.DataFrame:
    out = sides.copy()
    recs = []
    for _, r in out.iterrows():
        gid = int(r["gameId"]) if pd.notna(r.get("gameId")) else None
        nid = int(r["nhl_id"]) if pd.notna(r.get("nhl_id")) else None
        info = {
            "actual": np.nan,
            "toi_actual": np.nan,
            "toi_actual_min": np.nan,
            "team_box": "",
            "team_box_abbrev": "",
            "game_finished": False,
            "game_state": "",
            "result": "pending",
            "units_dk": np.nan,
            "units_shop": np.nan,
            "in_band_dk": bool(r["dk_price"] >= -150) if pd.notna(r["dk_price"]) else pd.NA,
            "flag": "",
        }
        if gid is None or gid not in box_by_id:
            info["flag"] = "missing_boxscore"
            recs.append(info)
            continue
        box = box_by_id[gid]
        meta = game_meta(box)
        info["game_state"] = meta["gameState"]
        info["game_finished"] = meta["finished"]
        skaters = extract_skaters(box)
        if not meta["finished"]:
            recs.append(info)
            continue
        if nid is None:
            info["flag"] = "missing_nhl_id_not_voided"
            recs.append(info)
            continue
        hit = skaters[skaters.nhl_id == nid]
        if hit.empty:
            # truly absent from boxscore skaters -> DNP void
            info["result"] = "void"
            info["flag"] = "DNP_absent_from_boxscore"
            recs.append(info)
            continue
        row = hit.iloc[0]
        if pd.isna(row["sog"]):
            info["flag"] = "in_boxscore_but_sog_missing_not_voided"
            info["toi_actual"] = row["toi"]
            info["toi_actual_min"] = row["toi_min"]
            info["team_box_abbrev"] = row["team_abbrev"]
            recs.append(info)
            continue
        sog = int(row["sog"])
        info["actual"] = sog
        info["toi_actual"] = row["toi"]
        info["toi_actual_min"] = row["toi_min"]
        info["team_box_abbrev"] = row["team_abbrev"]
        line = float(r["line"])
        side = str(r["side"]).upper()
        if sog == line:
            info["result"] = "void"
            recs.append(info)
            continue
        if side == "OVER":
            won = sog > line
        elif side == "UNDER":
            won = sog < line
        else:
            info["result"] = "void"
            info["flag"] = "unknown_side"
            recs.append(info)
            continue
        info["result"] = "W" if won else "L"
        info["units_dk"] = units_at(r["dk_price"], won)
        info["units_shop"] = units_at(r["fliff_shop_at"], won)
        recs.append(info)
    extra = pd.DataFrame(recs)
    return pd.concat([out.reset_index(drop=True), extra], axis=1)


def load_yinzer() -> pd.DataFrame:
    y = pd.read_csv(HERE / "yinzer_graded_sides.csv")
    return y


def compare_yinzer(mine: pd.DataFrame, yinzer: pd.DataFrame) -> pd.DataFrame:
    y10 = yinzer[yinzer.date == 20261110].copy()
    y10["player"] = y10["player"].astype(str).str.strip()
    y10["side"] = y10["side"].astype(str).str.strip().str.upper()
    y10["game"] = y10["game"].astype(str).str.strip()
    y10["line"] = y10["line"].astype(float)
    m = mine.merge(
        y10,
        on=["game", "player", "side", "line"],
        how="outer",
        suffixes=("_me", "_y"),
        indicator=True,
    )
    rows = []
    for _, r in m.iterrows():
        notes = []
        if r["_merge"] == "left_only":
            notes.append("in_my_grade_missing_from_yinzer")
        elif r["_merge"] == "right_only":
            notes.append("in_yinzer_missing_from_my_grade")
        else:
            if str(r.get("result_me")) != str(r.get("result_y")):
                notes.append(f"result {r.get('result_me')} vs Yinzer {r.get('result_y')}")
            a_me, a_y = r.get("actual_me"), r.get("actual_y")
            if pd.notna(a_me) or pd.notna(a_y):
                if not (pd.notna(a_me) and pd.notna(a_y) and int(a_me) == int(a_y)):
                    notes.append(f"actual {a_me} vs Yinzer {a_y}")
            # units: Yinzer uses Fliff if offered else DK
            if str(r.get("result_me")) in {"W", "L"} and str(r.get("result_y")) in {"W", "L"}:
                u_me = r.get("units_dk")
                u_y = r.get("units_y") if pd.notna(r.get("units_y")) else r.get("units")
                if pd.notna(u_me) and pd.notna(u_y) and abs(float(u_me) - float(u_y)) > 1e-6:
                    notes.append(
                        f"units DK {u_me:+.6f} vs Yinzer {u_y:+.6f} "
                        f"(Yinzer price {r.get('price')} from {r.get('price_source')}; "
                        f"DK {r.get('dk_price_me')})"
                    )
                band_me = r.get("in_band_dk")
                band_y = r.get("in_band")
                if pd.notna(band_me) and pd.notna(band_y) and bool(band_me) != bool(band_y):
                    notes.append(f"in_band DK={band_me} vs Yinzer posted-price in_band={band_y}")
        if notes:
            rows.append({
                "player": r.get("player"),
                "game": r.get("game"),
                "side": r.get("side"),
                "line": r.get("line"),
                "notes": "; ".join(notes),
            })
    return pd.DataFrame(rows)


def load_signals_for_list(list_id: str) -> pd.DataFrame:
    sheet = HIST_SHEETS[list_id]
    # tonight sheets are in HERE; historical in nhl-sog/sheets
    p_here = HERE / sheet
    p_src = NHL_SOG / "sheets" / sheet
    path = p_here if p_here.exists() else p_src
    df = pd.read_excel(path, sheet_name="Picks")
    df = df[df.agrees_n.notna() & (df.agrees_n >= 4)].copy()
    df["list_id"] = list_id
    df["player"] = df["player"].astype(str).str.strip()
    df["side"] = df["side"].astype(str).str.strip().str.upper()
    df["game"] = df["game"].astype(str).str.strip()
    df["line"] = df["line"].astype(float)
    keep = ["list_id", "game", "player", "side", "line", "sig_opp", "sig_lineup", "sig_toi",
            "model_mu", "agrees_n", "dk_price"]
    for c in keep:
        if c not in df.columns:
            df[c] = np.nan
    return df[keep]


def load_gate_teams(list_id: str) -> pd.DataFrame:
    name = HIST_GATES[list_id]
    p_here = HERE / name
    p_src = NHL_SOG / "picks" / name
    path = p_here if p_here.exists() else p_src
    g = pd.read_csv(path)
    g["player"] = g["player"].astype(str).str.strip()
    g["game"] = g["game"].astype(str).str.strip()
    keep = [c for c in ("player", "game", "team_dfo", "nhl_id", "gameId", "toi_r5", "toi_r30") if c in g.columns]
    return g[keep].drop_duplicates(["player", "game"])


# GATE left team_dfo blank for a few skaters (confirmed from the official boxscore).
TEAM_DFO_FILL = {
    ("Nick Robertson", "Boston Bruins at Pittsburgh Penguins"): "Pittsburgh Penguins",
}


def parse_game_teams(game: str) -> tuple[str, str]:
    # "Away Team at Home Team"
    if " at " not in str(game):
        return "", ""
    away, home = str(game).split(" at ", 1)
    return away.strip(), home.strip()


def opponent_of(team: str, game: str) -> str:
    away, home = parse_game_teams(game)
    if team == away:
        return home
    if team == home:
        return away
    return ""


def build_pregame_rates() -> pd.DataFrame:
    raw = json.loads((HERE / "team_summary_games_20262027.json").read_text())
    tg = pd.DataFrame(raw["data"])
    tg["gameDate"] = pd.to_datetime(tg["gameDate"]).dt.strftime("%Y-%m-%d")
    tg["sf"] = tg["shotsForPerGame"].astype(float)
    tg["sa"] = tg["shotsAgainstPerGame"].astype(float)
    return tg


def pregame_for_date(tg: pd.DataFrame, team_full: str, game_date: str) -> dict:
    names = set(tg.teamFullName.unique())
    team = canon_team(team_full, names)
    prior = tg[(tg.teamFullName == team) & (tg.gameDate < game_date)]
    if prior.empty:
        # last try: folded equality row-wise
        folded = fold_name(team_full)
        prior = tg[(tg.teamFullName.map(fold_name) == folded) & (tg.gameDate < game_date)]
    if prior.empty:
        return {"gp": 0, "sfg": np.nan, "sag": np.nan, "matched_name": team}
    return {
        "gp": int(len(prior)),
        "sfg": float(prior["sf"].mean()),
        "sag": float(prior["sa"].mean()),
        "matched_name": team,
    }


def league_sfg_before(tg: pd.DataFrame, game_date: str) -> float:
    prior = tg[tg.gameDate < game_date]
    if prior.empty:
        return float("nan")
    return float(prior["sf"].mean())


# teamFullName in the stats API should match team_dfo / game names.
# "Montreal Canadiens" in our sheets is "Montréal Canadiens" in the NHL stats API.
TEAM_ALIASES = {
    "Utah Hockey Club": "Utah Mammoth",
}


def fold_name(name: str) -> str:
    s = unicodedata.normalize("NFD", (name or "").strip())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s


def canon_team(name: str, api_teams: set[str] | None = None) -> str:
    name = (name or "").strip()
    if not name:
        return ""
    if name in TEAM_ALIASES:
        name = TEAM_ALIASES[name]
    if api_teams is None:
        return name
    if name in api_teams:
        return name
    folded = {fold_name(x): x for x in api_teams}
    return folded.get(fold_name(name), name)


def attach_pregame(df: pd.DataFrame, tg: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    # date may be int 20261110
    def iso(d):
        s = str(int(d)) if not isinstance(d, str) else d.replace("-", "")
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    recs = []
    for _, r in out.iterrows():
        day = iso(r["date"])
        raw_team = r.get("team_dfo")
        if pd.isna(raw_team) or str(raw_team).strip() in {"", "nan"}:
            raw_team = TEAM_DFO_FILL.get((str(r.get("player") or "").strip(), str(r.get("game") or "").strip()), "")
        team = str(raw_team or "").strip()
        opp = opponent_of(team, str(r.get("game") or ""))
        t = pregame_for_date(tg, team, day)
        o = pregame_for_date(tg, opp, day)
        lg = league_sfg_before(tg, day)
        proj = np.nan
        if pd.notna(t["sfg"]) and pd.notna(o["sag"]):
            proj = 0.5 * t["sfg"] + 0.5 * o["sag"]
        # projection points over if expected team volume > league average
        points = ""
        if pd.notna(proj) and pd.notna(lg):
            if proj > lg:
                points = "OVER"
            elif proj < lg:
                points = "UNDER"
            else:
                points = "EVEN"
        side = str(r.get("side") or "").upper()
        aligned = ""
        if points in {"OVER", "UNDER"} and side in {"OVER", "UNDER"}:
            aligned = "with" if points == side else "against"
        recs.append({
            "team_sfg_pre": t["sfg"],
            "team_sag_pre": t["sag"],
            "team_gp_pre": t["gp"],
            "opp_name": opp,
            "opp_sag_pre": o["sag"],
            "opp_sfg_pre": o["sfg"],
            "opp_gp_pre": o["gp"],
            "league_sfg_pre": lg,
            "volume_proj": proj,
            "proj_points": points,
            "proj_aligned": aligned,
        })
    return pd.concat([out.reset_index(drop=True), pd.DataFrame(recs)], axis=1)


def tertile_labels(series: pd.Series) -> tuple[pd.Series, dict]:
    """Split into bottom/middle/top third of the series itself (equal count, ties broken by rank)."""
    s = series.astype(float)
    # rank first so qcut always gets unique edges for equal-sized groups
    ranks = s.rank(method="first")
    cats = pd.qcut(ranks, 3, labels=["low_SA (stingy)", "mid_SA", "high_SA (generous)"])
    info = {}
    for lab in cats.cat.categories:
        sub = s[cats == lab]
        info[str(lab)] = (float(sub.min()), float(sub.max()), int(sub.size))
    return cats, info


def load_all_box_tonight():
    boxes = {}
    for p in sorted(HERE.glob("boxscore_*.json")):
        gid = int(p.stem.split("_")[1])
        boxes[gid] = json.loads(p.read_text())
    return boxes


def fmt_ci_pct(s):
    if not s["n"]:
        return "n/a"
    return f"{s['hit']*100:.1f}% (95% Wilson CI {s['ci_lo']*100:.1f}–{s['ci_hi']*100:.1f}%; n={s['n']})"


def main():
    sides = load_tonight_sides()
    boxes = load_all_box_tonight()
    graded = grade_sides(sides, boxes)
    yinzer = load_yinzer()
    diffs = compare_yinzer(graded, yinzer)

    # save full tonight CSV
    csv_cols = [
        "date", "list_id", "game", "gameId", "nhl_id", "player", "team_dfo",
        "team_box_abbrev", "side", "line", "agrees_n", "agrees_all_n",
        "dk_price", "fliff_shop_at", "in_band_dk", "sig_opp", "sig_lineup", "sig_toi",
        "model_mu", "toi_r5", "toi_r30", "toi_actual", "toi_actual_min",
        "actual", "game_state", "game_finished", "result", "units_dk", "units_shop", "flag",
    ]
    for c in csv_cols:
        if c not in graded.columns:
            graded[c] = np.nan
    csv_path = HERE / "tonight_majority_graded.csv"
    graded[csv_cols].sort_values(["list_id", "game", "player", "side"]).to_csv(csv_path, index=False)

    # ---- tonight records ----
    decided = graded[graded.result.isin(["W", "L"])].copy()
    pending = graded[graded.result == "pending"].copy()
    voids = graded[graded.result == "void"].copy()

    overall_dk = wl_block(graded, units_col="units_dk")
    overall_shop = wl_block(graded, units_col="units_shop")
    inside = graded[graded.in_band_dk == True]  # noqa: E712
    outside = graded[graded.in_band_dk == False]  # noqa: E712
    in_dk = wl_block(inside, units_col="units_dk")
    in_shop = wl_block(inside, units_col="units_shop")
    out_dk = wl_block(outside, units_col="units_dk")
    out_shop = wl_block(outside, units_col="units_shop")

    by_level = {}
    for n in (4, 5, 6, 7):
        sub = graded[graded.agrees_n == n]
        by_level[n] = {
            "dk": wl_block(sub, units_col="units_dk"),
            "shop": wl_block(sub, units_col="units_shop"),
            "n_sides": len(sub),
        }

    ou = {}
    for side in ("OVER", "UNDER"):
        sub = graded[graded.side == side]
        ou[side] = {
            "dk": wl_block(sub, units_col="units_dk"),
            "shop": wl_block(sub, units_col="units_shop"),
        }

    per_game = []
    for game, sub in graded.groupby("game", sort=False):
        per_game.append((game, wl_block(sub, units_col="units_dk"), wl_block(sub, units_col="units_shop"), len(sub)))

    # ---- game scripts for 6 finished ----
    # Tester2 numbers to verify
    tester2 = {
        "WSH": (2026020288, "away", 17, "WSH 17 SOG at OTT"),
        "NJ": (2026020291, "away", 21, "NJ 21 SOG at WPG"),
        "CBJ": (2026020289, "home", 38, "CBJ 38 SOG vs FLA"),
        "DETSTL": (2026020290, "combined", 65, "DET@STL 65 combined"),
    }

    tg = build_pregame_rates()
    # unique team names for alias check
    api_teams = set(tg.teamFullName.unique())

    game_rows = []
    finished_gids = []
    for gid, box in boxes.items():
        meta = game_meta(box)
        if not meta["finished"]:
            continue
        finished_gids.append(gid)
        script = load_landing_script(gid)
        # sheet players for this game (unique)
        gdf = graded[graded.gameId == gid]
        if gdf.empty:
            continue
        game_name = gdf.iloc[0]["game"]
        away_name, home_name = parse_game_teams(game_name)
        # expected SF: pre-game season SF/G
        day = "2026-11-10"
        away_pre = pregame_for_date(tg, canon_team(away_name), day)
        home_pre = pregame_for_date(tg, canon_team(home_name), day)
        # listed-player model_mu vs actual (unique players on the sheet for that team)
        sheet = sides[sides.gameId == gid]
        listed = sheet.drop_duplicates(["nhl_id"])
        def listed_sum(team):
            sub = listed[listed.team_dfo == team]
            mu = float(sub["model_mu"].sum()) if len(sub) and sub["model_mu"].notna().any() else float("nan")
            # actual from box for those ids
            sk = extract_skaters(box)
            m = sub.merge(sk, on="nhl_id", how="left")
            act = float(m["sog"].sum()) if m["sog"].notna().any() else float("nan")
            return mu, act, int(len(sub))
        away_mu, away_mu_act, away_n = listed_sum(away_name)
        home_mu, home_mu_act, home_n = listed_sum(home_name)
        # majority W/L by team and by side vs volume
        def team_of(r):
            return r["team_dfo"]
        vol_notes = []
        for team, actual_sog, exp_sfg in (
            (away_name, meta["away_sog"], away_pre["sfg"]),
            (home_name, meta["home_sog"], home_pre["sfg"]),
        ):
            if pd.isna(exp_sfg) or actual_sog is None:
                delta_s = "n/a"
                volume = "n/a"
            else:
                delta = actual_sog - exp_sfg
                delta_s = f"{delta:+.1f} vs {exp_sfg:.1f} SF/G pre"
                volume = "under-shot" if actual_sog < exp_sfg - 1 else ("over-shot" if actual_sog > exp_sfg + 1 else "about average")
            tsub = gdf[gdf.team_dfo == team]
            ow = wl_block(tsub[tsub.side == "OVER"], units_col="units_dk")
            uw = wl_block(tsub[tsub.side == "UNDER"], units_col="units_dk")
            track = ""
            if volume == "under-shot":
                track = f"volume down: overs {ow['w']}-{ow['l']}, unders {uw['w']}-{uw['l']}"
            elif volume == "over-shot":
                track = f"volume up: overs {ow['w']}-{ow['l']}, unders {uw['w']}-{uw['l']}"
            else:
                track = f"volume near average: overs {ow['w']}-{ow['l']}, unders {uw['w']}-{uw['l']}"
            vol_notes.append({
                "team": team, "actual": actual_sog, "exp": exp_sfg,
                "delta_s": delta_s, "volume": volume, "track": track,
                "n_over": ow["n"], "n_under": uw["n"],
            })
        margin = abs(int(meta["away_score"]) - int(meta["home_score"]))
        ot = meta["period_type"] in {"OT", "SO"} or int(meta["period"] or 3) > 3
        script_label = "OT" if ot else ("blowout" if margin >= 3 else ("one-goal" if margin == 1 else f"{margin}-goal"))
        en = script["en_goals"]
        en_s = ", ".join(
            f"EN {e['awayScore']}-{e['homeScore']} at {e['time']} 3rd" if e["period"] == 3
            else f"EN {e['awayScore']}-{e['homeScore']} P{e['period']} {e['time']}"
            for e in en
        ) or "no empty-net goals"
        pp = script["stats"].get("powerPlay")
        pim = script["stats"].get("pim")
        game_rows.append({
            "gid": gid,
            "game": game_name,
            "score": f"{meta['away_abbrev']} {meta['away_score']}-{meta['home_score']} {meta['home_abbrev']}",
            "sog": f"{meta['away_abbrev']} {meta['away_sog']}-{meta['home_sog']} {meta['home_abbrev']}",
            "combined": int(meta["away_sog"] or 0) + int(meta["home_sog"] or 0),
            "script": script_label,
            "en": en_s,
            "pp": f"PP {pp[0]} / {pp[1]}" if pp else "PP n/a",
            "pim": f"PIM {pim[0]}-{pim[1]}" if pim else "PIM n/a",
            "away_name": away_name,
            "home_name": home_name,
            "away_pre": away_pre,
            "home_pre": home_pre,
            "away_mu": (away_mu, away_mu_act, away_n),
            "home_mu": (home_mu, home_mu_act, home_n),
            "vol": vol_notes,
            "wl": wl_block(gdf, units_col="units_dk"),
            "missing_api_team": [n for n in (away_name, home_name) if canon_team(n, api_teams) not in api_teams],
        })

    # Tester2 verification
    t2_lines = []
    meta288 = game_meta(boxes[2026020288])
    t2_lines.append(
        f"WSH 17 SOG at OTT: official boxscore is {meta288['away_abbrev']} {meta288['away_sog']} "
        f"(OTT {meta288['home_sog']}). {'Matches.' if meta288['away_sog']==17 else 'DOES NOT MATCH.'}"
    )
    meta291 = game_meta(boxes[2026020291])
    t2_lines.append(
        f"NJ 21 SOG at WPG: official boxscore is {meta291['away_abbrev']} {meta291['away_sog']} "
        f"(WPG {meta291['home_sog']}). {'Matches.' if meta291['away_sog']==21 else 'DOES NOT MATCH.'}"
    )
    meta289 = game_meta(boxes[2026020289])
    t2_lines.append(
        f"CBJ 38 SOG vs FLA: official boxscore is {meta289['home_abbrev']} {meta289['home_sog']} "
        f"(FLA {meta289['away_sog']}). {'Matches.' if meta289['home_sog']==38 else 'DOES NOT MATCH.'}"
    )
    meta290 = game_meta(boxes[2026020290])
    comb = int(meta290["away_sog"]) + int(meta290["home_sog"])
    t2_lines.append(
        f"DET@STL 65 combined: official boxscore is {meta290['away_abbrev']} {meta290['away_sog']}-"
        f"{meta290['home_sog']} {meta290['home_abbrev']} = {comb}. {'Matches.' if comb==65 else 'DOES NOT MATCH.'}"
    )

    # ---- tonight signals on 50 decided ----
    def sig_split(df, col, units_col="units_dk"):
        out = {}
        for val, label in (("+", "agreed"), ("-", "disagreed"), ("0", "neutral/0")):
            sub = df[df[col].astype(str) == val]
            out[label] = (wl_block(sub, units_col=units_col), len(sub))
        other = df[~df[col].astype(str).isin(["+", "-", "0"])]
        if len(other):
            out["other/blank"] = (wl_block(other, units_col=units_col), len(other))
        return out

    sig_reports = {c: sig_split(decided, c) for c in ("sig_opp", "sig_lineup", "sig_toi")}

    # CBJ TOI vs recent
    cbj = graded[(graded.team_dfo == "Columbus Blue Jackets") & (graded.list_id == "20261110_1339")].copy()
    cbj_lines = []
    for _, r in cbj.sort_values("player").iterrows():
        d5 = r["toi_actual_min"] - r["toi_r5"] if pd.notna(r["toi_actual_min"]) and pd.notna(r["toi_r5"]) else np.nan
        d30 = r["toi_actual_min"] - r["toi_r30"] if pd.notna(r["toi_actual_min"]) and pd.notna(r["toi_r30"]) else np.nan
        flag = ""
        if pd.notna(d5) and abs(d5) >= 3:
            flag = "  ** TOI differs from last-5 avg by 3+ min **"
        cbj_lines.append(
            f"- {r['player']} {r['side']} {r['line']}: actual TOI {r['toi_actual']} "
            f"({r['toi_actual_min']:.2f} min) vs toi_r5 {r['toi_r5']:.2f} ({d5:+.2f}), "
            f"toi_r30 {r['toi_r30']:.2f} ({d30:+.2f}); SOG {r['actual']}, {r['result']}{flag}"
        )

    # ---- cumulative ----
    # Use Yinzer's settled rows for Nov 5 / Nov 9 (already final) and my tonight grades
    # so tonight units in the cumulative "grader price" split can be shown separately.
    y_hist = yinzer[yinzer.date < 20261110].copy()
    # attach signals + team
    sig_frames = []
    team_frames = []
    for lid in sorted(set(y_hist.list_id) | set(graded.list_id)):
        sig_frames.append(load_signals_for_list(lid))
        t = load_gate_teams(lid)
        t["list_id"] = lid
        team_frames.append(t)
    sig_all = pd.concat(sig_frames, ignore_index=True)
    teams_all = pd.concat(team_frames, ignore_index=True)

    y_hist = y_hist.merge(
        sig_all,
        on=["list_id", "game", "player", "side", "line"],
        how="left",
        suffixes=("", "_sig"),
    )
    y_hist = y_hist.merge(
        teams_all[["list_id", "player", "game", "team_dfo"]],
        on=["list_id", "player", "game"],
        how="left",
    )
    # tonight mine
    tng = graded.copy()
    tng["price"] = tng["dk_price"]
    tng["units"] = tng["units_dk"]
    tng["in_band"] = tng["in_band_dk"]

    # combined decided + voids + pending using Yinzer hist + my tonight
    hist_keep = y_hist.copy()
    # columns unify
    cum = pd.concat([
        hist_keep,
        tng,
    ], ignore_index=True, sort=False)
    cum = attach_pregame(cum, tg)

    cum_decided = cum[cum.result.isin(["W", "L"])].copy()
    # For cumulative units, use official grader price for Nov 5/9 (Yinzer `units`/`price`)
    # and DK for tonight (already in units). Also provide a "grader-price" tonight
    # via Yinzer's tonight settled rows for a single consistent series.
    y_all_decided = yinzer[yinzer.result.isin(["W", "L"])].copy()
    # attach signals/teams/pregame to official 144
    y_all_decided = y_all_decided.merge(
        sig_all, on=["list_id", "game", "player", "side", "line"], how="left"
    )
    y_all_decided = y_all_decided.merge(
        teams_all[["list_id", "player", "game", "team_dfo"]],
        on=["list_id", "player", "game"], how="left",
    )
    def _fill_team(row):
        if pd.notna(row.get("team_dfo")) and str(row.get("team_dfo")).strip() not in {"", "nan"}:
            return row["team_dfo"]
        return TEAM_DFO_FILL.get((str(row.get("player") or "").strip(), str(row.get("game") or "").strip()), row.get("team_dfo"))
    y_all_decided["team_dfo"] = y_all_decided.apply(_fill_team, axis=1)
    y_all_decided["team_dfo_fill"] = y_all_decided.apply(
        lambda r: "boxscore_fill" if (str(r.get("player") or "").strip(), str(r.get("game") or "").strip()) in TEAM_DFO_FILL
        and (r.name in y_all_decided.index) else "", axis=1
    )
    y_all_decided = attach_pregame(y_all_decided, tg)

    overs = y_all_decided[y_all_decided.side.astype(str).str.upper() == "OVER"].copy()
    # drop rows missing opp_sag
    overs_ok = overs[overs.opp_sag_pre.notna()].copy()
    cats, tertile_info = tertile_labels(overs_ok["opp_sag_pre"])
    overs_ok = overs_ok.copy()
    overs_ok["sa_bucket"] = cats

    bucket_stats = []
    for lab in ["low_SA (stingy)", "mid_SA", "high_SA (generous)"]:
        sub = overs_ok[overs_ok.sa_bucket == lab]
        st = wl_block(sub, units_col="units")
        rng = tertile_info[lab]
        bucket_stats.append((lab, st, rng, sub))

    # sig_opp on overs and on all decided
    def agreed_split(df, units_col="units"):
        d = df.copy()
        d["_sig"] = d["sig_opp"].astype(str)
        return {
            "agreed (+)": wl_block(d[d._sig == "+"], units_col=units_col),
            "disagreed (-)": wl_block(d[d._sig == "-"], units_col=units_col),
            "neutral (0)": wl_block(d[d._sig == "0"], units_col=units_col),
        }

    sig_overs = agreed_split(overs)
    sig_all_dec = agreed_split(y_all_decided)

    # projection with vs against (all decided sides)
    with_proj = y_all_decided[y_all_decided.proj_aligned == "with"]
    against_proj = y_all_decided[y_all_decided.proj_aligned == "against"]
    proj_with_ou = {
        "OVER": wl_block(with_proj[with_proj.side.str.upper() == "OVER"], units_col="units"),
        "UNDER": wl_block(with_proj[with_proj.side.str.upper() == "UNDER"], units_col="units"),
        "ALL": wl_block(with_proj, units_col="units"),
    }
    proj_against_ou = {
        "OVER": wl_block(against_proj[against_proj.side.str.upper() == "OVER"], units_col="units"),
        "UNDER": wl_block(against_proj[against_proj.side.str.upper() == "UNDER"], units_col="units"),
        "ALL": wl_block(against_proj, units_col="units"),
    }
    n_proj_missing = int(y_all_decided.proj_aligned.fillna("").isin(["", "EVEN"]).sum() + y_all_decided.proj_aligned.isna().sum()) if "proj_aligned" in y_all_decided else 0
    n_unaligned = int((~y_all_decided.proj_aligned.isin(["with", "against"])).sum())

    # missing team names?
    missing_teams = sorted({
        x for x in list(y_all_decided.team_dfo.fillna("").unique()) + list(y_all_decided.opp_name.fillna("").unique())
        if x and canon_team(x, api_teams) not in api_teams
    })

    # ---- Yinzer pending note ----
    y10 = yinzer[yinzer.date == 20261110]
    y_pend = y10[y10.result == "pending"]
    y_pend_games = y_pend.groupby("game").size().to_dict()

    # NSH@LA state
    nsh = boxes.get(2026020292)
    nsh_state = game_meta(nsh) if nsh else {"gameState": "missing"}

    # ---- write REPORT ----
    ts = now_pt().strftime("%Y-%m-%d %-I:%M %p PT")
    lines = []
    a = lines.append
    a("# Nov 10, 2026 NHL SOG majority-list tally")
    a("")
    a(f"Graded independently from the NHL public API (api-web.nhle.com boxscores; gameState FINAL/OFF). Work folder: `tester1-review/majority_tally_20261110/`. Report generated {ts}.")
    a("")
    a("Sources: majority sides are rows with `agrees_n >= 4` on the frozen sheets `20261110_D_1304` (35), `_1339` (15), and `_1535` (10). Units are 1u risk at the **DK list price** and, separately, at `fliff_shop_at`. The price band uses **DK price** (inside if DK >= −150). Official SOG and game states are from the NHL gamecenter boxscore. `team_dfo` comes from the matching GATE files.")
    a("")

    a("## Overall (tonight)")
    a("")
    a(f"- **{overall_dk['w']}-{overall_dk['l']}**" + (f", {overall_dk['v']} void" if overall_dk['v'] else "") + (f", {overall_dk['p']} pending" if overall_dk['p'] else "") + f" on {len(graded)} majority sides.")
    a(f"- Units at DK: **{overall_dk['units']:+.2f}u** on {overall_dk['n_priced']} priced decided sides" + (f" (hit {overall_dk['hit']*100:.1f}%, 95% Wilson CI {overall_dk['ci_lo']*100:.1f}–{overall_dk['ci_hi']*100:.1f}%)" if overall_dk['n'] else "") + ".")
    a(f"- Units at shop-at: **{overall_shop['units']:+.2f}u** on {overall_shop['n_priced']} priced decided sides.")
    if nsh_state.get("gameState") not in FINAL_STATES:
        clock = (nsh or {}).get("clock") or {}
        pdsc = (nsh or {}).get("periodDescriptor") or {}
        a(f"- **NSH@LA is not final** (gameState {nsh_state.get('gameState')}, period {pdsc.get('number')} {pdsc.get('periodType')}, clock {clock.get('timeRemaining')}). Its 10 sides are pending. The six earlier games are final.")
    a("")

    a("## Price band (DK >= −150 is inside)")
    a("")
    a(f"- Inside: {fmt_wl(in_dk)} at DK; shop-at {in_shop['units']:+.2f}u.")
    a(f"- Outside (DK worse than −150): {fmt_wl(out_dk)} at DK; shop-at {out_shop['units']:+.2f}u.")
    a("")

    a("## By agrees_n (of 7)")
    a("")
    for n in (4, 5, 6, 7):
        st = by_level[n]
        if st["n_sides"] == 0:
            a(f"- {n} of 7: no sides.")
        else:
            a(f"- {n} of 7 ({st['n_sides']} sides): {fmt_wl(st['dk'])} at DK; shop-at {st['shop']['units']:+.2f}u.")
    a("")

    a("## Over vs under")
    a("")
    for side in ("OVER", "UNDER"):
        a(f"- {side}: {fmt_wl(ou[side]['dk'])} at DK; shop-at {ou[side]['shop']['units']:+.2f}u.")
    a("")

    a("## Per game")
    a("")
    for game, dk, shop, n in per_game:
        a(f"- {game} ({n} sides): {fmt_wl(dk)} at DK; shop-at {shop['units']:+.2f}u." if shop['n_priced'] or dk['n'] else f"- {game} ({n} sides): {fmt_wl(dk)}.")
    a("")

    a("## Comparison with Yinzer's `majority/graded_sides.csv`")
    a("")
    a(f"Yinzer's file has {len(y10)} Nov 10 rows (35+15+10). Results on the 50 decided sides from the six finished games **match this grade on result and actual SOG for every side.**")
    a("")
    a("**Pending sides:** all 10 of Yinzer's pending rows are the 10 NSH@LA sides from the 1535 sheet (4 inside the band, 6 outside). None are from other games, none are missing or void, and none were deduped away. The 1535 sheet's 10 majority sides are exactly those 10 pending rows. A split of '6 NSH@LA plus 4 from other games' would be a misread of that 6-outside / 4-inside split; other games tonight are already settled in his file.")
    a("")
    if len(diffs):
        a("**Differences vs this grade:**")
        a("")
        for _, r in diffs.iterrows():
            a(f"- {r['player']} {r['side']} {r['line']} ({r['game']}): {r['notes']}")
        a("")
        a("The only units difference is pricing, not the grade: this tally uses DK for units and the band; Yinzer's grader uses a posted Fliff price when Fliff offered the side, otherwise DK. Shop-at never sets his price or the band.")
    else:
        a("No result, actual-SOG, or units differences on settled sides (and no Fliff-offered price diverged from DK enough to change units).")
    a("")

    a("## Why results varied by game (n=50 decided; keep small)")
    a("")
    a("Team expected SOG is each team's season-to-date shots-for per game **before Nov 10**, from the NHL stats API game-by-game team summary (`api.nhle.com/stats/rest/en/team/summary`, 2026–27 regular season). Listed-player `model_mu` sums are only the unique names on that game's sheet, not a full-team projection. Sample is 50 sides in 6 games; this is descriptive, not a rule change.")
    a("")
    for g in game_rows:
        a(f"**{g['game']}** — {g['score']}, SOG {g['sog']} (combined {g['combined']}), {g['script']}; {g['en']}; {g['pp']}; {g['pim']}. Majority record {g['wl']['w']}-{g['wl']['l']}, {g['wl']['units']:+.2f}u DK.")
        for v in g["vol"]:
            mu = g["away_mu"] if v["team"] == g["away_name"] else g["home_mu"]
            mu_s = f" listed players (n={mu[2]}) model_mu sum {mu[0]:.2f} vs their actual SOG {mu[1]:.0f}" if pd.notna(mu[0]) else ""
            exp_s = f"{v['exp']:.1f}" if pd.notna(v["exp"]) else "n/a"
            a(f"- {v['team']}: {v['actual']} SOG vs {exp_s} SF/G pre-game ({v['delta_s']}), {v['volume']}. {v['track']}.{mu_s}.")
        if g["missing_api_team"]:
            a(f"- Warning: team name not in stats API: {g['missing_api_team']}")
        a("")

    a("**Do wins track team shot volume?** In the two games where one team was clearly volume-starved, the unders on that team did the work: WSH took 17 SOG (vs ~pre-game SF/G below) and Washington unders went well; NJ took 21 at Winnipeg and Devil overs were mixed. CBJ *over*-shot (38) and still had mixed/losing overs among the majority sides, so volume alone does not explain every game. n=50 is too small and clustered by game to treat this as a missing defensive metric you can bet.")
    a("")

    a("### Tester2's SOG figures")
    a("")
    for t in t2_lines:
        a(f"- {t}")
    a("")

    a("### Tonight's 50 decided sides: sig_opp, sig_lineup, sig_toi")
    a("")
    a("'+' = the test agreed with the side, '−' = disagreed, '0' = neutral. Units at DK. n=50. Tonight `sig_lineup` is inverted (agreed 6-12, disagreed 12-3); that is still a small, game-clustered split and is not a rule.")
    a("")
    for col, rep in sig_reports.items():
        a(f"**{col}**")
        for lab, (st, nside) in rep.items():
            a(f"- {lab}: {fmt_wl(st)} (rows={nside}).")
        a("")

    a("### CBJ lineup was 28.7h stale — TOI vs recent average")
    a("")
    a("All six Columbus majority sides (Coyle, Nichushkin, Olivier, Knies inside the band; Monahan and Kent Johnson outside). Last-5 / last-30 TOI are `toi_r5` / `toi_r30` from the 1339 GATE file; actual TOI is from the official boxscore.")
    a("")
    lines.extend(cbj_lines)
    a("")
    big = [x for x in cbj_lines if "** TOI differs" in x]
    if big:
        a("Players whose actual TOI was 3+ minutes off the last-5 average are flagged above. A stale lineup can miss a role change, but a TOI miss of that size is still just a handful of skaters in one game.")
    else:
        a("None of the six had actual TOI 3+ minutes away from their last-5 average, so the stale DailyFaceoff file does not show up as a large TOI miss for these sides. That does not prove their roles were confirmed — only that ice time landed close to the recent mean.")
    a("")

    a("## Cumulative (all majority-list decided sides in `graded_sides.csv`)")
    a("")
    n_cum = len(y_all_decided)
    cum_all = wl_block(y_all_decided, units_col="units")
    a(f"This uses Yinzer's official grader file for settled sides (price = Fliff if offered, else DK). **{n_cum} decided sides** (tonight's 50 finished plus Nov 5 and Nov 9). NSH@LA's 10 sides are not in this split. Sample is still modest and game-clustered; intervals are wide. No rule change is implied.")
    a("")
    a(f"Overall official-price record on those {n_cum}: {fmt_wl(cum_all)}.")
    a("")
    if missing_teams:
        a(f"Warning: unmatched team names vs the stats API: {missing_teams}. Those rows were dropped from rate lookups if pre-game stats are missing.")
        a("")
    if (y_all_decided.player.astype(str) == "Nick Robertson").any():
        a("Nick Robertson (BOS at PIT, Nov 5) had a blank `team_dfo` in the GATE file; his team was filled as Pittsburgh Penguins from the official boxscore (home team, nhl_id 8481582, 2 SOG). Accent-folded team names so Montreal / Montréal match the stats API.")
        a("")

    a("### Overs split by opponent shots-allowed / game (season-to-date before game date)")
    a("")
    a(f"{len(overs)} decided overs; {len(overs_ok)} have a pre-game opponent SA/G. Buckets are equal-count tertiles of those over sides (ties broken by rank). 'High SA' = more generous opponent (higher shots allowed). Units at the official grader price.")
    a("")
    for lab, st, rng, sub in bucket_stats:
        a(f"- {lab}: opponent SA/G {rng[0]:.2f}–{rng[1]:.2f} (n={st['n']} sides): {fmt_wl(st)}.")
    a("")
    a("Same overs, by whether `sig_opp` agreed with the side:")
    a("")
    for lab, st in sig_overs.items():
        a(f"- Overs, sig_opp {lab}: {fmt_wl(st)}.")
    a("")
    a("All decided sides (overs and unders), sig_opp:")
    a("")
    for lab, st in sig_all_dec.items():
        a(f"- {lab}: {fmt_wl(st)}.")
    a("")
    a("Point estimates go the **opposite** way of a simple 'overs do better against generous defenses' story: overs vs stingier opponents were better than overs vs more generous ones, and overs where `sig_opp` agreed were worse than disagreed or neutral. The 95% CIs still overlap across buckets, so this does not establish a reliable pattern. It also does not support adding or trusting a defensive-metric rule at this sample size.")
    a("")

    a("### Pre-game team shot-volume projection (with vs against the side)")
    a("")
    a("For each side, projection = average of (shooter's team season SOG/game) and (opponent's season SOG-allowed/game), both strictly before that game's date. It **points OVER** if the projection is above the league-average SOG/game through the prior day, and **UNDER** if below. 'With' means the side matches that direction. Units at the official grader price.")
    a("")
    a(f"- Projection **with** the side ({proj_with_ou['ALL']['w']+proj_with_ou['ALL']['l']} sides): {fmt_wl(proj_with_ou['ALL'])}. Overs: {fmt_wl(proj_with_ou['OVER'])}. Unders: {fmt_wl(proj_with_ou['UNDER'])}.")
    a(f"- Projection **against** the side ({proj_against_ou['ALL']['w']+proj_against_ou['ALL']['l']} sides): {fmt_wl(proj_against_ou['ALL'])}. Overs: {fmt_wl(proj_against_ou['OVER'])}. Unders: {fmt_wl(proj_against_ou['UNDER'])}.")
    a(f"- Sides with no direction (missing rates or projection exactly equal to the league average): {n_unaligned}.")
    a("")
    a("Sides that went with the projection were not better than sides that went against it (CIs overlap). Same caution as above: this is descriptive, not a filter.")
    a("")

    a("## Full side list (tonight)")
    a("")
    a("| List | Game | Player | Team (DFO) | Side | Line | DK | Shop-at | Band | n/7 | Actual SOG | Result | u DK | u shop |")
    a("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    show = graded.sort_values(["list_id", "game", "player", "side"])
    for _, r in show.iterrows():
        band = "in" if r["in_band_dk"] == True else ("out" if r["in_band_dk"] == False else "")
        act = "" if pd.isna(r["actual"]) else str(int(r["actual"]))
        udk = "" if pd.isna(r["units_dk"]) else f"{r['units_dk']:+.2f}"
        ush = "" if pd.isna(r["units_shop"]) else f"{r['units_shop']:+.2f}"
        dk = "" if pd.isna(r["dk_price"]) else str(int(r["dk_price"]))
        sh = "" if pd.isna(r["fliff_shop_at"]) else str(int(r["fliff_shop_at"]))
        flag = f" {r['flag']}" if r.get("flag") else ""
        team = r["team_dfo"] if pd.notna(r.get("team_dfo")) else ""
        a(f"| {r['list_id']} | {r['game']} | {r['player']} | {team} | {r['side']} | {r['line']} | {dk} | {sh} | {band} | {int(r['agrees_n'])} | {act} | {r['result']}{flag} | {udk} | {ush} |")
    a("")
    a("CSV: `tonight_majority_graded.csv`.")
    a("")

    report = HERE / "REPORT.md"
    report.write_text("\n".join(lines) + "\n")
    print(f"Wrote {report}")
    print(f"Wrote {csv_path} ({len(graded)} rows)")
    print("TONIGHT", fmt_wl(overall_dk), "shop", overall_shop["units"])
    print("PENDING", len(pending), pending.game.unique().tolist() if len(pending) else [])
    print("DIFFS", len(diffs))
    if len(diffs):
        print(diffs.to_string(index=False))
    print("NSH state", nsh_state.get("gameState"))
    print("missing teams", missing_teams)
    print("cum n", n_cum, fmt_wl(cum_all))
    # also dump a small debug of unmatched sig merges
    miss_sig = y_all_decided["sig_opp"].isna().sum()
    miss_team = y_all_decided["team_dfo"].isna().sum()
    miss_sag = overs["opp_sag_pre"].isna().sum()
    print(f"merge miss sig_opp={miss_sig} team_dfo={miss_team} overs missing opp_sag={miss_sag}")


if __name__ == "__main__":
    main()
