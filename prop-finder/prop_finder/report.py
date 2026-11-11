"""CSV / Markdown / HTML output."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

PT = ZoneInfo("America/Los_Angeles")


def to_pt(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(PT).strftime("%a %m/%d %I:%M %p PT")
    except Exception:  # noqa: BLE001
        return iso


def _md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_none_\n"
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        vals = []
        for c in cols:
            v = r[c]
            if isinstance(v, float):
                v = "" if pd.isna(v) else (f"{v:.0%}" if c.startswith(("hit", "P(", "model")) else f"{v:g}")
            vals.append(str(v).replace("|", "/"))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def _fmt(v, empty=""):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return empty
    return f"{v:g}" if isinstance(v, (int, float)) else str(v)


def props_view(df: pd.DataFrame, n: int) -> pd.DataFrame:
    if df.empty:
        return df
    d = df.head(n).copy()
    return pd.DataFrame({
        "#": range(1, len(d) + 1),
        "Player": d["player"] + " (" + d["pos"].fillna("") + ", " + d["team"] + ")",
        "Game": d["game"], "Kickoff": d["kickoff_utc"].map(to_pt),
        "Prop": d["prop"], "Line": d["line"], "Pick": d["pick"], "Proj": d["projection"],
        "Edge": d["edge"], "model P": d["model_p_side"],
        "hit L5": d["hit_rate_l5_side"], "hit L10": d["hit_rate_l10_side"], "hit season": d["hit_rate_season_side"],
        "Szn avg (G)": d["season_avg"].map(lambda x: f"{x:g}") + " (" + d["games_season"].astype(str) + ")",
        "Last 5": d["last5_values"], "Matchup": d["matchup_note"].fillna(""), "Flags": d["flags"].fillna(""),
    })


def proj_view(proj: pd.DataFrame, stat: str, n: int, sort_col: str = "projection") -> pd.DataFrame:
    d = proj[(proj["stat"] == stat) & (proj["game_state"] != "post")]
    d = d[~d["injury_status"].isin(["Out", "Doubtful"])].sort_values(sort_col, ascending=False).head(n)
    if d.empty:
        return pd.DataFrame()
    out = pd.DataFrame({
        "Player": d["player"] + " (" + d["pos"].fillna("") + ", " + d["team"] + ")",
        "vs": d["home_away"].map({"H": "vs ", "A": "@ ", "N": "vs* "}) + d["opp"],
        "Proj": d["projection"], "Szn avg": d["season_avg"], "G": d["games_season"], "L3": d["l3_avg"],
        "Prev szn": d["prior_season_avg"].map(_fmt), "Home/Away": d.apply(
            lambda r: f"{_fmt(r.home_avg, '-')} / {_fmt(r.away_avg, '-')}", axis=1),
        "Last 5": d["last5_values"], "Trend": d["trend"], "Matchup": d["matchup_note"].fillna(""),
        "Imp. TT": d["implied_team_total"], "Weather": d["weather"].fillna(""), "Inj": d["injury_status"].fillna(""),
    })
    if stat == "rush_rec_tds":
        out.insert(2, "P(anytime TD)", d["p_anytime_td"].values)
    if "prior_weight" in d.columns and d["prior_weight"].notna().any():
        out.insert(out.columns.get_loc("Szn avg") + 1, "Szn opp-adj", d["season_avg_oppadj"].values)
        out["Prev szn"] = [f"{_fmt(r)}{' @' + t if isinstance(t, str) else ''}"
                           for r, t in zip(d["prior_season_avg"], d["transfer_from"])]
        out.insert(out.columns.get_loc("Prev szn") + 1, "Prior used (wt)",
                   [f"{_fmt(v)} ({w:.0%})" if v is not None and not pd.isna(v) else "" for v, w in zip(d["prior_final"], d["prior_weight"].fillna(0))])
        out["Role"] = [("VACATED ROLE: " if f else "") + (n or "") for f, n in zip(d["vacated_role"].fillna(False), d["role_note"].fillna(""))]
    return out


MAIN = {"QB": "pass_yds", "RB": "rush_yds", "WR": "rec_yds", "TE": "rec_yds"}


def _main_rows(proj):
    m = proj[proj.apply(lambda r: MAIN.get(r["pos_group"]) == r["stat"], axis=1)]
    return m[~m["injury_status"].isin(["Out", "Doubtful"])]


def transfers_view(proj: pd.DataFrame, transfers: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    m = _main_rows(proj)
    m = m[m["transfer_from"].notna()].sort_values("projection", ascending=False).head(n)
    if m.empty:
        return m
    t = transfers.set_index("player_id") if not transfers.empty else pd.DataFrame()
    def tinfo(pid, col):
        try:
            v = t.loc[pid, col]
            return v.iloc[0] if isinstance(v, pd.Series) else v
        except KeyError:
            return None
    return pd.DataFrame({
        "Player": m["player"] + " (" + m["pos"].fillna("") + ")",
        "2025 team (conf)": [f"{tf} ({tinfo(pid, 'conf_2025') or '?'})" for tf, pid in zip(m["transfer_from"], m["player_id"])],
        "2026 team (conf)": [f"{tm} ({tinfo(pid, 'conf_2026') or '?'})" for tm, pid in zip(m["team"], m["player_id"])],
        "Portal *": [_fmt(tinfo(pid, "stars")) for pid in m["player_id"]],
        "Stat": m["stat_label"], "2025 G": m["games_prior"], "2025 raw/g": m["prior_season_avg"],
        "opp-adj/g": m["prior_oppadj"], "Level x": m["level_factor"], "Role x": m["role_ratio"],
        "Prior used": m["prior_final"], "Prior wt now": m["prior_weight"].map(lambda x: f"{x:.0%}"),
        "2026 avg (G)": m["season_avg"].map(_fmt) + " (" + m["games_season"].astype(str) + ")",
        "Proj": m["projection"], "vs": m["opp"],
    })


def vacated_view(proj: pd.DataFrame, per_pos: int = 6) -> pd.DataFrame:
    m = _main_rows(proj)
    m = m[m["vacated_role"].fillna(False).astype(bool)]
    if m.empty:
        return m
    m = pd.concat([m[m["pos_group"] == pg].sort_values("projection", ascending=False).head(per_pos)
                   for pg in ("QB", "RB", "WR", "TE")])
    return pd.DataFrame({
        "Player": m["player"] + " (" + m["pos"].fillna("") + ", " + m["team"] + ")", "vs": m["opp"],
        "Stat": m["stat_label"], "Proj": m["projection"], "2026 avg (G)": m["season_avg"].map(_fmt) + " (" + m["games_season"].astype(str) + ")",
        "2025/g": m["prior_season_avg"].map(_fmt), "Role change": m["role_note"],
    })


def team_vacancy_view(vac: pd.DataFrame, slate_teams: set, n: int = 15) -> pd.DataFrame:
    v = vac[vac["team"].isin(slate_teams)].copy()
    if v.empty:
        return v
    v["max_vac"] = v[["vacated_rush", "vacated_rec", "vacated_pass"]].max(axis=1)
    v = v.sort_values("max_vac", ascending=False).head(n)
    pct = lambda x: "" if x is None or pd.isna(x) else f"{x:.0%}"  # noqa: E731
    return pd.DataFrame({
        "Team": v["team"], "Vacated 2025 pass att": v["vacated_pass"].map(pct),
        "Vacated carries": v["vacated_rush"].map(pct), "Vacated receptions": v["vacated_rec"].map(pct),
        "CFBD returning usage (pass/rush/rec)": [f"{pct(a)}/{pct(b)}/{pct(c)}" for a, b, c in zip(
            v["cfbd_returning_pass_usage"], v["cfbd_returning_rush_usage"], v["cfbd_returning_rec_usage"])],
        "Top departed (2025 volume)": v["top_departed"],
    })


SECTIONS = [("pass_yds", "Passing yards"), ("rush_yds", "Rushing yards"), ("rec_yds", "Receiving yards"),
            ("receptions", "Receptions"), ("pass_tds", "Passing TDs"), ("rush_rec_tds", "Anytime TD (rush+rec TDs)")]


def build_markdown(results: list[dict], generated: datetime, top: int) -> str:
    md = [f"# Football Player Prop Finder — report\n",
          f"Generated {generated.astimezone(PT).strftime('%a %b %d %Y %I:%M %p PT')}. "
          "All numbers are computed from the data sources listed per league; nothing is hand-entered.\n",
          "> Not betting advice. Projections are a simple transparent model (see Method). DraftKings lines via ESPN "
          "carry no prices, so -110 (52.4% breakeven) is assumed for them.\n"]
    for res in results:
        lg = res["league"].upper()
        md.append(f"\n## {lg} — {res['season']} week {res['week']}\n")
        md.append("**Data status**\n")
        for k, v in res["status"].items():
            md.append(f"- {k}: {v}")
        md.append("")
        ranked = res["ranked"]
        if not ranked.empty:
            live = ranked[ranked["bettable_now"]]
            md.append(f"\n### Top {top} props by edge — games not yet started\n")
            md.append(_md_table(props_view(live, top)))
            started = ranked[(ranked["game_state"] != "pre")]
            if not started.empty:
                md.append(f"\n### Games already kicked off (graded vs last pregame line; not bettable pregame)\n")
                md.append(_md_table(props_view(started, min(10, top))))
        else:
            md.append("\n_No sportsbook prop lines available for this slate right now — projections only._\n")
        md.append(f"\n### Projections for this week's games (no line needed)\n")
        for stat, title in SECTIONS:
            sort_col = "p_anytime_td" if stat == "rush_rec_tds" else "projection"
            md.append(f"\n#### {title}\n")
            md.append(_md_table(proj_view(res["proj"], stat, 12, sort_col)))
        ctx = res.get("ctx")
        if ctx:
            slate_teams = {g["home"] for g in res["games"]} | {g["away"] for g in res["games"]}
            md.append("\n### Transfers the model now handles (prior-season stats carried across schools)\n")
            md.append("2025 per-game production is opponent-adjusted (CFBD SP+), scaled by the conference-strength "
                      "change (Level x) and by the change in the player's share of team opportunities (Role x), then "
                      "blended in with a weight that fades as 2026 games accumulate.\n")
            md.append(_md_table(transfers_view(res["proj"], ctx["transfers"])))
            md.append("\n### Players stepping into vacated roles\n")
            md.append(_md_table(vacated_view(res["proj"])))
            md.append("\n### Biggest roster turnover on this slate (2025 opportunity no longer on the roster)\n")
            md.append("'Vacated' = share of the team's 2025 attempts/carries/receptions by players with no 2026 box-score "
                      "line for that team (transferred, graduated/NFL, or injured all season). CFBD returning usage is "
                      "CFBD's official returning-production figure.\n")
            md.append(_md_table(team_vacancy_view(ctx["vacated_df"], slate_teams)))
        md.append("\n### Easiest / toughest matchups on this slate (defense vs position, current season)\n")
        md.append(_md_table(res["dvp_view"]))
    md.append("""
## Method
- **Game logs:** current season + previous season (NFL: nflverse; college: CFBD box scores, followed across schools).
  L5/L10 hit rates span seasons; "season" = current season only.
- **College (with CFBD key):** every college game is adjusted for opponent quality using CFBD SP+
  (×(1 + 0.012 × SP+ points the defense is better than FBS average), capped 0.8–1.25; non-FBS opponents are treated as
  15 points below average and count half weight). The prior season gets the same treatment, then × a level-jump factor
  for transfers (1 − 0.006 × change in conference average SP+, capped 0.85–1.08; non-FBS origin = −25) and × the change in
  the player's share of team opportunities (i.e. per-opportunity production × new share, capped 0.1–10; changes beyond 3× also cut the prior's reliability by 3/ratio). Prior weight = (0.70 − 0.13 × games played in 2026, floor
  0.05) × reliability (prior games/6 × last-season share/10%). Defense-vs-position is adjusted for the SP+ offense faced,
  with non-FBS games at half weight, and only FBS defenses are ranked.
- **Base projection:** 45% season avg + 35% last-3 avg + up to 20% previous-season avg (NFL; scaled by games played).
- **Matchup:** opponent's per-game yards/receptions/TDs allowed to that position group vs league average,
  shrunk by sample size (k = games/(games+4)), multiplier capped to ±20%.
- **Game environment:** sportsbook implied team total vs the team's season scoring average (capped ±12%).
- **Weather:** outdoor games only; gusts ≥22 mph −4%, ≥30 mph −8%, precip ≥60% −3% on passing/receiving stats.
- **Injuries:** NFL = ESPN game-day injury list + nflverse weekly report; college = ESPN roster "out" group and a
  flag when a player had no stats in his team's most recent game. Out/Doubtful players are pushed to the bottom.
- **Probability:** normal distribution (player SD blended with a stat-specific CV floor); Poisson for TD/INT props.
- **Rank score:** 100×(raw model P(side) − breakeven)×sample-confidence + 20×(L10 hit rate on that side − 50%). It's an ordering heuristic: in the 2025 backtest, even top picks were roughly break-even. **model P** is calibrated (raw edge shrunk 80% toward 50%), so it's usually just above or below breakeven.
""")
    return "\n".join(md)


CSS = """body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:24px;color:#222}
table{border-collapse:collapse;font-size:12px;margin:8px 0 18px}th,td{border:1px solid #ddd;padding:4px 6px;text-align:left}
th{background:#f3f3f3;position:sticky;top:0}tr:nth-child(even){background:#fafafa}h2{border-bottom:2px solid #333}
blockquote{color:#555;border-left:3px solid #ccc;margin:0;padding-left:10px}"""


def md_to_html(md: str) -> str:
    """Tiny markdown->HTML for the subset we emit (headings, tables, bullets, paragraphs)."""
    import html as H
    import re
    out, i, lines = [], 0, md.split("\n")

    def inline(t):
        t = H.escape(t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        return re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<i>\1</i>", t)
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i]); i += 1
            hdr = [c.strip() for c in rows[0].strip("|").split("|")]
            out.append("<table><tr>" + "".join(f"<th>{inline(c)}</th>" for c in hdr) + "</tr>")
            for r in rows[2:]:
                out.append("<tr>" + "".join(f"<td>{inline(c.strip())}</td>" for c in r.strip().strip("|").split("|")) + "</tr>")
            out.append("</table>")
            continue
        m = re.match(r"^(#{1,4}) (.*)", ln)
        if m:
            n = len(m.group(1)); out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
        elif ln.startswith("- "):
            out.append(f"<li>{inline(ln[2:])}</li>")
        elif ln.startswith("> "):
            out.append(f"<blockquote>{inline(ln[2:])}</blockquote>")
        elif ln.strip():
            out.append(f"<p>{inline(ln)}</p>")
        i += 1
    return f"<!doctype html><html><head><meta charset='utf-8'><title>Prop Finder</title><style>{CSS}</style></head><body>{''.join(out)}</body></html>"
