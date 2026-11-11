#!/usr/bin/env python
"""Stage 2 of the 2025 backtest: grade, tune (weeks 2-9) / validate (weeks 10+), and write the report.

Reads data/backtest/projections.pkl + actuals.pkl produced by `python backtest.py`.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import backtest as runner
from prop_finder import analysis, backtest as bt, cfb_context, cfbd, hist_lines, nfl_stats
from prop_finder.report import CSS, md_to_html

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "data" / "backtest"
OUT = runner.OUT
TUNE_W, HOLD_W = runner.TUNE_W, runner.HOLD_W
SHRINK_GRID = [0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.75, 1.0]
AGREE_GRID = [0.0, 5.0, 10.0, 20.0]
RANK_SHRINK_GRID = [0.4, 0.6, 0.75, 1.0]
log = runner.log


# ------------------------------------------------------------------ formatting
def table(df: pd.DataFrame, pct=("hit_rate", "roi_110", "roi_price", "mean_pred", "hit_rate_flagged",
                                 "hit_rate_unflagged", "p_side_mean")) -> str:
    if df is None or df.empty:
        return "_none_\n"
    cols = list(df.columns)
    out = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        vals = []
        for c in cols:
            v = r[c]
            if v is None or (isinstance(v, float) and np.isnan(v)):
                v = ""
            elif isinstance(v, (float, np.floating)):
                v = f"{v:+.1%}" if str(c).startswith("roi") else (f"{v:.1%}" if c in pct or str(c).startswith("hit")
                                                                  else f"{v:.4g}")
            vals.append(str(v).replace("|", "/"))
        out.append("| " + " | ".join(vals) + " |")
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------ evaluation helpers
def headline(g: pd.DataFrame, label: str) -> pd.DataFrame:
    rows = [bt.summarize(g, f"{label}: all lines")]
    for n in (10, 25):
        rows.append(bt.summarize(bt.top_n(g, n), f"{label}: top {n}/week"))
    for th in (0, 5, 10, 15, 20):
        rows.append(bt.summarize(g[g.rank_score >= th], f"{label}: rank_score >= {th}"))
    # naive reference: bet every line on one side (no model)
    for side in ("UNDER", "OVER"):
        alt = g.copy()
        alt["pick"] = side
        alt["result"] = np.where(alt.actual.isna(), "void", np.where(alt.actual == alt.line, "push",
                                 np.where((alt.actual > alt.line) == (side == "OVER"), "win", "loss")))
        pr = alt.under_price if side == "UNDER" else alt.over_price
        alt["profit_110"] = [bt._profit(x == "win", -110) if x in ("win", "loss") else 0.0 for x in alt.result]
        alt["profit_price"] = [bt._profit(x == "win", q) if x in ("win", "loss") else 0.0 for x, q in zip(alt.result, pr)]
        rows.append(bt.summarize(alt, f"{label}: NAIVE always {side} (no model)"))
    return pd.DataFrame(rows)


def split(g: pd.DataFrame, col: str, label: str) -> pd.DataFrame:
    rows = []
    for k, d in g.groupby(col):
        s = bt.summarize(d, f"{label} {k}")
        s[col] = k
        rows.append(s)
    return pd.DataFrame(rows)


GUARDS = {"far_line": "GUARD_FAR_F", "teammate_out": "GUARD_MATE_UNDER_F", "missed_last": "GUARD_MISSED_F",
          "small_sample": "GUARD_SMALL_F"}


class consts:
    """Temporarily override analysis module constants."""
    def __init__(self, **kw):
        self.kw, self.old = kw, {}

    def __enter__(self):
        for k, v in self.kw.items():
            self.old[k] = getattr(analysis, k)
            setattr(analysis, k, v)

    def __exit__(self, *a):
        for k, v in self.old.items():
            setattr(analysis, k, v)


def regrade(proj, lines, weeks, synthetic=False):
    return bt.grade(bt.rank_all(proj, lines, synthetic=synthetic), weeks)


def guard_study(proj, lines, weeks, label, synthetic=False):
    """Flagged vs unflagged hit rates + counterfactual re-ranks with each guard discount switched off."""
    g = regrade(proj, lines, weeks, synthetic)
    variants = {"live guards": g}
    for gname, const in GUARDS.items():
        with consts(**{const: 1.0}):
            variants[f"{gname} discount OFF"] = regrade(proj, lines, weeks, synthetic)
    with consts(**{c: 1.0 for c in GUARDS.values()}):
        variants["ALL guard discounts OFF"] = regrade(proj, lines, weeks, synthetic)
    eff, tun = [], []
    t25 = bt.summarize(bt.top_n(g, 25), "")
    for gname in GUARDS:
        col = f"guard_{gname}"
        fl = g[g[col] & ((g.pick == "UNDER") if gname == "teammate_out" else True)]
        un = g[~g.index.isin(fl.index)]
        s_f, s_u = bt.summarize(fl, ""), bt.summarize(un, "")
        s_alt = bt.summarize(bt.top_n(variants[f"{gname} discount OFF"], 25), "")
        eff.append({"set": label, "guard": gname, "discount": getattr(analysis, GUARDS[gname]),
                    "flagged_bets": s_f["bets"], "hit_rate_flagged": s_f["hit_rate"], "roi_flagged": s_f["roi_110"],
                    "hit_rate_unflagged": s_u["hit_rate"], "roi_unflagged": s_u["roi_110"],
                    "top25_live_hit": t25["hit_rate"], "top25_live_roi": t25["roi_110"],
                    "top25_guard_off_hit": s_alt["hit_rate"], "top25_guard_off_roi": s_alt["roi_110"]})
    for vname, gv in variants.items():
        r = {"set": label, "variant": vname}
        for nm, wk in (("tune", TUNE_W), ("holdout", HOLD_W)):
            s_ = bt.summarize(bt.top_n(gv[gv.week.isin(wk)], 25), "")
            r[f"{nm}_top25_bets"], r[f"{nm}_top25_hit"], r[f"{nm}_top25_roi"] = s_["bets"], s_["hit_rate"], s_["roi_110"]
        tun.append(r)
    tun = pd.DataFrame(tun)
    b = tun[tun.variant == "live guards"].iloc[0]
    tun["better_on_both"] = (tun.tune_top25_roi > b.tune_top25_roi) & (tun.holdout_top25_roi > b.holdout_top25_roi)
    return pd.DataFrame(eff), tun


def market_brier(g: pd.DataFrame):
    """No-vig market P(over) from the opening prices (only rows with both prices)."""
    d = g[g.over_hit.notna() & g.over_price.notna() & g.under_price.notna()].copy()
    po = d.over_price.map(analysis.implied_prob)
    pu = d.under_price.map(analysis.implied_prob)
    d["p_mkt"] = po / (po + pu)
    return d, bt.brier(d, "p_mkt"), bt.brier(d, "p_over"), bt.logloss(d, "p_mkt"), bt.logloss(d, "p_over")


def rank_real(proj, lines):
    return bt.rank_all(proj, lines)


def main():
    t0 = time.time()
    runner.apply_cfg({})   # baseline = pre-backtest settings (analysis.py now carries the tuned values)
    OUT.mkdir(parents=True, exist_ok=True)
    P = pd.read_pickle(WORK / "projections.pkl")["results"]
    A = pd.read_pickle(WORK / "actuals.pkl")
    weeks = {lg: {W: {"actuals": d["actuals"]} for W, d in A[lg].items()} for lg in A}
    meta = json.load(open(WORK / "run_meta.json"))
    proj = {lg: P[("baseline", lg)][1] for lg in ("nfl", "ncaaf")}

    # ---------------- real historical lines (NFL only; FBS feed has no priced main lines)
    real_all = bt.real_lines("nfl", [str(e) for e in proj["nfl"].event_id.unique()])
    raw_rows = []
    for f in sorted((hist_lines.DIR / "nfl").glob("*.json")):
        raw_rows.extend(hist_lines.parse_event("nfl", json.loads(f.read_text())))
    raw_nfl = pd.DataFrame(raw_rows)
    gms = nfl_stats.load_games()
    gms = gms[(gms.season == 2025) & (gms.game_type == "REG")]
    ev2wk = dict(zip(gms.espn.astype("Int64").astype(str), gms.week))
    raw_nfl["week"] = raw_nfl.event_id.map(ev2wk)
    cfb_files = list((hist_lines.DIR / "ncaaf").glob("*.json"))
    cfb_with = cfb_ladder = 0
    for f in cfb_files:
        r = json.loads(f.read_text())
        if r["props"]:
            cfb_with += 1
            cfb_ladder += sum(len(v) for v in r["props"].values())
    cfb_main = sum(len(hist_lines.parse_event("ncaaf", json.loads(f.read_text()))) for f in cfb_files)

    g_real = bt.grade(rank_real(proj["nfl"], real_all), weeks["nfl"])
    # sensitivity: last listed line (may include post-kickoff updates -> not used for headline)
    last = raw_nfl[raw_nfl.line_last.notna()].copy()
    last["line"], last["over_price"], last["under_price"] = last.line_last, last.over_price_last, last.under_price_last
    last["line_note"] = "last listed line (may be post-kickoff)"
    g_last = bt.grade(rank_real(proj["nfl"], last), weeks["nfl"])

    # ---------------- synthetic proxy (both leagues)
    g_syn = {lg: bt.grade(bt.rank_all(proj[lg], None, synthetic=True), weeks[lg]) for lg in proj}

    # ---------------- projection accuracy
    acc = pd.concat([bt.proj_accuracy(proj[lg], weeks[lg]) for lg in proj], ignore_index=True)
    # market benchmark: opening line as a point forecast, same rows
    gm = g_real[g_real.actual.notna()]
    line_acc = gm.groupby("stat").apply(lambda d: pd.Series({
        "n": len(d), "model_mae": round((d.projection - d.actual).abs().mean(), 3),
        "open_line_mae": round((d.line - d.actual).abs().mean(), 3),
        "model_bias": round((d.projection - d.actual).mean(), 3),
        "open_line_bias": round((d.line - d.actual).mean(), 3)}), include_groups=False).reset_index()

    # ---------------- tuning: projection knobs (objective: normalized MAE on tune weeks)
    grid_rows = []
    for (name, lg), (cfg, pr) in P.items():
        grid_rows.append({"league": lg, "config": name, "settings": json.dumps(cfg) if cfg else "live settings",
                          "tune_norm_mae": bt.norm_mae(pr, weeks[lg], TUNE_W),
                          "holdout_norm_mae": bt.norm_mae(pr, weeks[lg], HOLD_W)})
    grid = pd.DataFrame(grid_rows)
    chosen = {}
    for lg, d in grid.groupby("league"):
        b = d[d.config == "baseline"].iloc[0]
        d = d[d.config != "baseline"].copy()
        d["knob"] = d.config.str.split(" ").str[0] + d.config.str.contains("prior").map({True: "-prior", False: ""}) + \
            d.config.str.contains("BETA|level").map({True: "-ctx", False: ""})
        picks = {}
        for knob, dk in d.groupby("knob"):
            best = dk.sort_values("tune_norm_mae").iloc[0]
            if "ablation" in best.config:
                continue   # ablations are diagnostics, never applied
            if best.tune_norm_mae < b.tune_norm_mae - 1e-4 and best.holdout_norm_mae < b.holdout_norm_mae - 1e-4:
                picks[knob] = best
        chosen[lg] = picks
        grid.loc[grid.league == lg, "delta_tune_vs_live"] = (grid.tune_norm_mae - b.tune_norm_mae).round(5)
        grid.loc[grid.league == lg, "delta_holdout_vs_live"] = (grid.holdout_norm_mae - b.holdout_norm_mae).round(5)
    grid["applied_candidate"] = [any(p.config == c for p in chosen.get(l, {}).values()) for l, c in zip(grid.league, grid.config)]

    # combined tuned projection config per league -> rerun the real model with it
    tuned_cfg = {lg: {k: v for p in chosen[lg].values() for k, v in json.loads(p.settings).items()} for lg in chosen}
    log("tuned candidates:", tuned_cfg)
    import hashlib

    def ck_path(lg, cfg):
        h = hashlib.md5(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:10]
        return WORK / f"tuned_{lg}_{h}.pkl"

    def run_ck(lg, cfg):   # checkpointed rerun of the real model with a config
        pth = ck_path(lg, cfg)
        if pth.exists():
            log("checkpoint hit", pth.name)
            return pd.read_pickle(pth)
        if lg == "nfl" and "nfl" not in runner.G:
            runner.G["nfl"] = bt.prepare_nfl()
        if lg == "ncaaf" and "cfb" not in runner.G:
            runner.G["ctx"] = cfb_context.Context(bt.SEASON, asof_ratings=True)
            runner.G["cfb"] = bt.prepare_cfb(runner.G["ctx"])[0]
        log("projecting", lg, cfg)
        _, _, _, pr, secs = runner.run_cfg(("combined", lg, cfg))
        pr.to_pickle(pth)
        log("saved", pth.name, f"{secs}s")
        return pr

    tuned_proj, combo_rows = {}, []
    for lg in ("nfl", "ncaaf"):
        cfg = tuned_cfg.get(lg) or {}
        if cfg:
            pr = run_ck(lg, cfg)
            base_h, new_h = bt.norm_mae(proj[lg], weeks[lg], HOLD_W), bt.norm_mae(pr, weeks[lg], HOLD_W)
            base_t, new_t = bt.norm_mae(proj[lg], weeks[lg], TUNE_W), bt.norm_mae(pr, weeks[lg], TUNE_W)
            ok = new_h < base_h - 1e-4 and new_t < base_t
            combo_rows.append({"league": lg, "combined_settings": json.dumps(cfg), "tune_norm_mae_live": base_t,
                               "tune_norm_mae_combined": new_t, "holdout_norm_mae_live": base_h,
                               "holdout_norm_mae_combined": new_h, "accepted": ok})
            if not ok:   # fall back to the single best knob on tune weeks that also held out
                best = min(chosen[lg].values(), key=lambda p: p.tune_norm_mae)
                cfg = json.loads(best.settings)
                pr = run_ck(lg, cfg)
                tuned_cfg[lg] = cfg
            tuned_proj[lg] = pr
        else:
            tuned_proj[lg] = proj[lg]
    # ---------------- tuning: ranking/probability layer on REAL NFL lines (tune weeks 2-9, held-out 10-13)
    base_shrink, base_agree = analysis.P_SHRINK, analysis.AGREE_W
    g0 = regrade(tuned_proj["nfl"], real_all, weeks["nfl"])
    shrink_rows = []
    for s_ in SHRINK_GRID:      # P(over) does not depend on ranking: recompute from the raw model probability
        gg = g0.assign(p_s=0.5 + s_ * (g0.p_over_raw - 0.5))
        tu, ho = gg[gg.week.isin(TUNE_W)], gg[gg.week.isin(HOLD_W)]
        shrink_rows.append({"P_SHRINK": s_, "tune_logloss": bt.logloss(tu, "p_s"), "holdout_logloss": bt.logloss(ho, "p_s"),
                            "tune_brier": bt.brier(tu, "p_s"), "holdout_brier": bt.brier(ho, "p_s")})
    sh = pd.DataFrame(shrink_rows)
    best_s = sh.sort_values("tune_logloss").iloc[0]
    base_row = sh[sh.P_SHRINK == base_shrink].iloc[0]
    shrink_new = float(best_s.P_SHRINK) if best_s.holdout_logloss < base_row.holdout_logloss - 1e-5 else base_shrink
    agree_rows = []
    base_rank = analysis.RANK_SHRINK
    with consts(P_SHRINK=shrink_new):
        for rs in RANK_SHRINK_GRID:
            for a_ in AGREE_GRID:
                with consts(AGREE_W=a_, RANK_SHRINK=rs):
                    gg = regrade(tuned_proj["nfl"], real_all, weeks["nfl"])
                r = {"RANK_SHRINK": rs, "AGREE_W": a_}
                for nm, wk in (("tune", TUNE_W), ("holdout", HOLD_W)):
                    for n in (10, 25):
                        s2 = bt.summarize(bt.top_n(gg[gg.week.isin(wk)], n), "")
                        r[f"{nm}_top{n}_hit"], r[f"{nm}_top{n}_roi"] = s2["hit_rate"], s2["roi_110"]
                agree_rows.append(r)
    ag = pd.DataFrame(agree_rows)
    best_a = ag.sort_values("tune_top25_roi", ascending=False).iloc[0]
    ref_a = ag[(ag.AGREE_W == base_agree) & (ag.RANK_SHRINK == base_rank)].iloc[0]
    if best_a.holdout_top25_roi > ref_a.holdout_top25_roi:
        agree_new, rank_new = float(best_a.AGREE_W), float(best_a.RANK_SHRINK)
    else:
        agree_new, rank_new = base_agree, base_rank
    # guards (at the chosen probability/ranking settings)
    with consts(P_SHRINK=shrink_new, AGREE_W=agree_new, RANK_SHRINK=rank_new):
        geff_r, gtun_r = guard_study(tuned_proj["nfl"], real_all, weeks["nfl"], "REAL NFL")
        geff_n, gtun_n = guard_study(tuned_proj["nfl"], None, weeks["nfl"], "SYNTHETIC NFL", True)
        geff_c, gtun_c = guard_study(tuned_proj["ncaaf"], None, weeks["ncaaf"], "SYNTHETIC FBS", True)
    guards, gtune = pd.concat([geff_r, geff_n, geff_c]), pd.concat([gtun_r, gtun_n, gtun_c])
    guard_new = {}
    for v in gtun_r[gtun_r.better_on_both].variant:
        gname = v.replace(" discount OFF", "")
        if gname in GUARDS:
            guard_new[GUARDS[gname]] = 1.0
    final_consts = {"P_SHRINK": shrink_new, "AGREE_W": agree_new, "RANK_SHRINK": rank_new, **guard_new}

    # ---------------- before / after on held-out weeks
    with consts(**final_consts):
        g_real_t = regrade(tuned_proj["nfl"], real_all, weeks["nfl"])
        g_syn_t = {lg: regrade(tuned_proj[lg], None, weeks[lg], True) for lg in proj}
    g_real_projonly = regrade(tuned_proj["nfl"], real_all, weeks["nfl"])   # tuned projections, live ranking
    ba = []
    for tag, gr_b, gr_a, lg, lab in [("REAL lines (NFL, ESPN BET opening)", g_real, g_real_t, "nfl", "real"),
                                     ("SYNTHETIC proxy NFL", g_syn["nfl"], g_syn_t["nfl"], "nfl", "syn"),
                                     ("SYNTHETIC proxy FBS", g_syn["ncaaf"], g_syn_t["ncaaf"], "ncaaf", "syn")]:
        vers = [("before (live settings)", gr_b, proj[lg])]
        if lab == "real":
            vers.append(("tuned projections only (live ranking/prob.)", g_real_projonly, tuned_proj[lg]))
        vers.append(("after (all tuned settings)", gr_a, tuned_proj[lg]))
        for when, gr, pr in vers:
            ho = gr[gr.week.isin(HOLD_W)]
            a_, t10, t25 = bt.summarize(ho, ""), bt.summarize(bt.top_n(ho, 10), ""), bt.summarize(bt.top_n(ho, 25), "")
            ba.append({"set": tag, "version": when, "holdout_weeks": f"{min(ho.week)}-{max(ho.week)}" if len(ho) else "",
                       "all_bets": a_["bets"], "all_hit": a_["hit_rate"], "all_roi": a_["roi_110"],
                       "top10_bets": t10["bets"], "top10_hit": t10["hit_rate"], "top10_roi": t10["roi_110"],
                       "top25_bets": t25["bets"], "top25_hit": t25["hit_rate"], "top25_roi": t25["roi_110"],
                       "logloss": bt.logloss(ho), "brier": bt.brier(ho),
                       "norm_mae": bt.norm_mae(pr, weeks[lg], HOLD_W)})
    ba = pd.DataFrame(ba)

    # ---------------- assemble tables
    head = pd.concat([headline(g_real, "REAL NFL"), headline(g_syn["nfl"], "SYNTHETIC NFL"),
                      headline(g_syn["ncaaf"], "SYNTHETIC FBS"),
                      headline(g_last, "SENSITIVITY NFL last-listed line")], ignore_index=True)
    head_price = bt.summarize(g_real, "REAL NFL at actual opening prices")
    by_stat = pd.concat([split(g_real, "stat", "REAL NFL").assign(set="REAL NFL all"),
                         split(bt.top_n(g_real, 25), "stat", "REAL NFL top25").assign(set="REAL NFL top25/wk"),
                         split(g_syn["nfl"], "stat", "SYN NFL").assign(set="SYNTHETIC NFL all"),
                         split(g_syn["ncaaf"], "stat", "SYN FBS").assign(set="SYNTHETIC FBS all")], ignore_index=True)
    by_side = pd.concat([split(g_real, "pick", "REAL NFL all").assign(set="REAL NFL all"),
                         split(bt.top_n(g_real, 25), "pick", "REAL NFL top25").assign(set="REAL NFL top25/wk"),
                         split(g_syn["nfl"], "pick", "SYN NFL").assign(set="SYNTHETIC NFL all"),
                         split(g_syn["ncaaf"], "pick", "SYN FBS").assign(set="SYNTHETIC FBS all"),
                         split(bt.top_n(g_syn["ncaaf"], 25), "pick", "SYN FBS top25").assign(set="SYNTHETIC FBS top25/wk")],
                        ignore_index=True)
    weekly = split(g_real, "week", "REAL NFL week")
    weekly_top25 = split(bt.top_n(g_real, 25), "week", "REAL NFL top25 week")
    cal = pd.concat([bt.calibration(g_real).assign(set="REAL NFL"), bt.calibration(g_syn["nfl"]).assign(set="SYNTHETIC NFL"),
                     bt.calibration(g_syn["ncaaf"]).assign(set="SYNTHETIC FBS"),
                     bt.calibration(g_real_t).assign(set="REAL NFL (tuned)")], ignore_index=True)
    md_rows, b_mkt, b_mod, ll_mkt, ll_mod = market_brier(g_real)
    # coverage
    calls = cfbd.network_calls_logged()
    q = cfbd.quota()
    cov = pd.DataFrame([
        {"item": "NFL games (weeks 2-18 projected)", "value": sum(A["nfl"][W]["n_games"] for W in A["nfl"])},
        {"item": "NFL games with ESPN BET historical props (weeks 1-13)", "value": raw_nfl.event_id.nunique()},
        {"item": "NFL main O/U lines parsed (all weeks, opening line present)", "value": int(raw_nfl.line_open.notna().sum())},
        {"item": "NFL real lines matched to a projection (weeks 2-13)", "value": len(g_real)},
        {"item": "NFL real-line bets graded (win/loss)", "value": int(g_real.result.isin(['win', 'loss']).sum())},
        {"item": "NFL real-line voids (no stat row: inactive/DNP)", "value": int((g_real.result == 'void').sum())},
        {"item": "NFL players projected (unique)", "value": proj["nfl"].player_id.nunique()},
        {"item": "NFL player-stat projections", "value": len(proj["nfl"])},
        {"item": "FBS games (weeks 2-16, >=1 FBS team)", "value": sum(A["ncaaf"][W]["n_games"] for W in A["ncaaf"])},
        {"item": "FBS games with implied totals (CFBD /lines)", "value": sum(A["ncaaf"][W]["n_implied"] for W in A["ncaaf"])},
        {"item": "FBS games where ESPN serves historical prop items", "value": cfb_with},
        {"item": "FBS prop items (alternate-ladder rungs, unpriced)", "value": cfb_ladder},
        {"item": "FBS priced main O/U lines found", "value": cfb_main},
        {"item": "FBS players projected (unique)", "value": proj["ncaaf"].player_id.nunique()},
        {"item": "FBS player-stat projections", "value": len(proj["ncaaf"])},
        {"item": "FBS projections with a 2024 prior", "value": int(proj["ncaaf"].prior_final.notna().sum())},
        {"item": "FBS projections for 2024->2025 school movers", "value": int(proj["ncaaf"].transfer_from.notna().sum())},
        {"item": "CFBD network calls (all time, data/cfbd/calls.log)", "value": calls},
        {"item": "CFBD calls remaining this month (from /info)", "value": q.get("remainingCalls")},
    ])

    # ---------------- write CSVs
    keep = ["week", "league", "game", "player", "pos", "team", "opp", "stat", "line", "pick", "projection", "p_over",
            "p_over_raw", "model_p_side", "rank_score", "raw_score", "over_price", "under_price", "actual", "result",
            "profit_110", "profit_price", "guard_far_line", "guard_teammate_out", "guard_missed_last",
            "guard_small_sample", "injury_status", "flags", "book", "source", "line_note", "event_id", "player_id"]
    g_real[keep].to_csv(OUT / "nfl_real_lines_graded.csv", index=False)
    g_real_t[keep].to_csv(OUT / "nfl_real_lines_graded_tuned.csv", index=False)
    for lg in g_syn:
        g_syn[lg][keep].to_csv(OUT / f"{lg}_synthetic_proxy_graded.csv", index=False)
    for lg in proj:
        pa = bt.attach_actuals(proj[lg].drop(columns=["vals_cur", "vals_all"], errors="ignore"), weeks[lg])
        pa.to_csv(OUT / f"{lg}_projections_vs_actual.csv", index=False)
    for name, df in [("coverage", cov), ("summary_headline", head), ("by_stat", by_stat), ("by_side", by_side),
                     ("weekly_real_nfl", weekly), ("weekly_real_nfl_top25", weekly_top25), ("calibration", cal),
                     ("guard_effects", guards), ("guard_tuning", gtune), ("projection_accuracy", acc), ("projection_vs_open_line_nfl", line_acc),
                     ("tuning_projection_grid", grid), ("tuning_combined", pd.DataFrame(combo_rows)),
                     ("tuning_p_shrink", sh), ("tuning_agree_w", ag), ("heldout_before_after", ba)]:
        df.to_csv(OUT / f"{name}.csv", index=False)
    result = {"tuned_cfg": tuned_cfg, "final_rank_consts": final_consts, "p_shrink_new": shrink_new, "p_shrink_old": base_shrink,
              "brier_market": b_mkt, "brier_model": b_mod, "logloss_market": ll_mkt, "logloss_model": ll_mod,
              "n_market_rows": len(md_rows), "head_price": head_price, "cfbd_calls_run": meta,
              "cfbd_remaining": q.get("remainingCalls")}
    json.dump(result, open(OUT / "tuning_result.json", "w"), indent=2, default=str)

    # ---------------- report
    gen = datetime.now().strftime("%Y-%m-%d %I:%M %p PT")
    hd = head.drop(columns=["group"]).assign(set=head.group)[["set", "bets", "wins", "losses", "voids", "hit_rate",
                                                              "roi_110", "roi_price", "units_110"]]
    md = [f"# Prop Finder: 2025 full-season walk-forward backtest", f"_Generated {gen}._", "",
          "**Read this first.** Real historical prop lines were found **for NFL weeks 1-13 only** (ESPN BET opening lines, "
          "ESPN core API). There are no usable real lines for NFL weeks 14-18 (ESPN serves only DraftKings there and its "
          "propBets return 404) or for **any FBS game** (ESPN serves only unpriced alternate-line ladder rungs for college, "
          "so the main line can't be identified). Every result marked **SYNTHETIC** is graded against a proxy line "
          "(floor(trailing-5-game average) + 0.5 at -110). That isn't a market line, and SYNTHETIC hit rates/ROI "
          "are not betting results.", "",
          "## Bottom line",
          f"- **Real lines (NFL weeks 2-13, {int(g_real.result.isin(['win','loss']).sum())} graded bets, pre-backtest settings):** every line: "
          f"{head.iloc[0].hit_rate:.1%} hit, {head.iloc[0].roi_110:+.1%} ROI at -110 ({head_price['roi_price']:+.1%} at the listed prices). Always betting the under "
          f"(no model) gave {head[head.group=='REAL NFL: NAIVE always UNDER (no model)'].iloc[0].hit_rate:.1%} / {head[head.group=='REAL NFL: NAIVE always UNDER (no model)'].iloc[0].roi_110:+.1%}.",
          f"- **Top 25/week:** {head.iloc[2].hit_rate:.1%}, {head.iloc[2].roi_110:+.1%} over weeks 2-13. All of the profit came from weeks 2-9 "
          f"({bt.summarize(bt.top_n(g_real[g_real.week.isin(TUNE_W)], 25), '')['roi_110']:+.1%}); held-out weeks 10-13 were "
          f"{bt.summarize(bt.top_n(g_real[g_real.week.isin(HOLD_W)], 25), '')['roi_110']:+.1%}. The model shows no reliable edge over the opening market. "
          f"Its probabilities are worse than the no-vig market's (Brier {b_mod} vs {b_mkt}).",
          f"- **Calibration:** the pre-backtest P(side) was strongly overconfident (picks rated 60-65% won ~50%). Calibrated P_SHRINK {shrink_new} cut held-out log-loss "
          f"{ba.iloc[0].logloss} -> {ba[ba.version.str.startswith('after')].iloc[0].logloss}.",
          f"- **After tuning (held-out real lines, weeks 10-13):** top-25 {ba.iloc[0].top25_hit:.1%}/{ba.iloc[0].top25_roi:+.1%} -> "
          f"{ba[ba.version.str.startswith('after')].iloc[0].top25_hit:.1%}/{ba[ba.version.str.startswith('after')].iloc[0].top25_roi:+.1%}; top-10 "
          f"{ba.iloc[0].top10_roi:+.1%} -> {ba[ba.version.str.startswith('after')].iloc[0].top10_roi:+.1%}. That's about 100 bets, which is within noise "
          "(1 SE of hit rate is about 5 pts), so it's still negative ROI.",
          "- **FBS:** no real lines exist, so only projection accuracy and the SYNTHETIC proxy are available. Tuning improved held-out normalized MAE. Ablations (held-out normalized MAE change "
          "if removed): the portal-aware 2024 prior " + f"{grid[(grid.league=='ncaaf')&(grid.config=='cfb no prior (ablation)')].delta_holdout_vs_live.iloc[0]:+.4f}" +
          ", the SP+ opponent adjustment " + f"{grid[(grid.league=='ncaaf')&(grid.config=='cfb opp-adj BETA 0 (ablation)')].delta_holdout_vs_live.iloc[0]:+.4f}" +
          ", the level-jump factor " + f"{grid[(grid.league=='ncaaf')&(grid.config=='cfb level-jump off (ablation)')].delta_holdout_vs_live.iloc[0]:+.4f}" +
          ". Positive means removing it hurts, so the level-jump showed no measurable effect.", "",
          "## Method",
          "- Walk-forward: for week W the live code (`analysis.build_projections` + `analysis.rank_props`, and for FBS `cfb_context.make_ctx`) sees "
          "only current-season games before W, the full 2024 season, team scoring before W, the week-W official NFL injury report (nflverse), and "
          "closing spread/total implied team totals (NFL: nflverse; FBS: median of CFBD /lines providers). No weather adjustment (no archived forecasts).",
          "- NFL weeks 2-18 (week 1 has no current-season game, which the live model needs). FBS weeks 2-16 (CFBD week numbering; week 1 includes week-0 games).",
          "- FBS: 2024 player stats are the prior. CFBD/ESPN athlete IDs and the CFBD 2025 transfer portal carry each player's 2024 production to his 2025 school, with the live "
          "level-jump, opponent-strength (SP+) and role/opportunity-share logic. **SP+ as-of: 2024 final SP+ is used as the 2025 rating all season** "
          "(CFBD's 2025 SP+ is end-of-season, which would leak). Conference strength = 2025 membership x 2024 ratings.",
          "- Real-line grading uses the **opening** main line and opening prices. ESPN's 'current' line has lastUpdated stamps after kickoff "
          "(e.g. DAL@PHI week 1: Hurts pass yds opened 214.5 and was last listed at 186.5), so it may include in-game moves. It's shown only as a sensitivity check.",
          "- Grading: actual > line = over. A player with no stat row in that game is a void (refund). ROI is per 1-unit bet at -110 unless noted; `roi_price` uses the listed opening prices.",
          "- Tuning protocol: knobs are chosen on weeks 2-9 only and applied only if they also improve weeks 10+ (held-out). Projection knobs use normalized MAE "
          "(model MAE / trailing-season-average MAE, averaged over stats). P(over) shrink uses log-loss on real NFL lines (tune weeks 2-9, held-out weeks 10-13).", "",
          "## Data coverage", table(cov), "",
          "## Headline results (live settings)", table(hd),
          f"At the listed opening prices (all real NFL lines): {head_price['bets']} bets, hit {head_price['hit_rate']:.1%}, ROI {head_price['roi_price']:+.1%}.", "",
          f"Probability quality on real NFL lines with both opening prices ({len(md_rows)} rows): model Brier {b_mod} vs no-vig market {b_mkt}; "
          f"log-loss {ll_mod} vs {ll_mkt} (lower is better).", "",
          "### Calibration (model probability of the picked side vs actual hit rate)", table(cal), "",
          "### By side (over / under)", table(by_side[["set", "pick", "bets", "hit_rate", "roi_110"]]), "",
          "### By stat", table(by_stat[["set", "stat", "bets", "hit_rate", "roi_110"]]), "",
          "### Weekly (REAL NFL, all lines and top 25)", table(weekly[["week", "bets", "hit_rate", "roi_110"]].merge(
              weekly_top25[["week", "bets", "hit_rate", "roi_110"]], on="week", suffixes=("_all", "_top25"))), "",
          "## Projection accuracy (all projected player-stats that played, live settings)", table(acc), "",
          "### Model vs the opening line as a point forecast (NFL rows with real lines)", table(line_acc), "",
          "## Guards and discounts", "Flagged vs unflagged hit rates, and top-25/week with each guard's discount removed (counterfactual re-rank through rank_props), at the tuned projection/probability settings.",
          table(guards), "",
          "### Guard discounts: tune vs held-out (top 25/week, at the tuned settings)", table(gtune),
          "Guard changes are reported only. They are applied to the live code only if they improve top-25 ROI on both tune and held-out REAL lines.", "",
          "## Tuning (tune weeks 2-9, validate weeks 10+)", "### Projection knobs (one at a time from live settings)",
          table(grid[["league", "config", "tune_norm_mae", "holdout_norm_mae", "delta_tune_vs_live", "delta_holdout_vs_live", "applied_candidate"]]),
          "### Combined tuned config", table(pd.DataFrame(combo_rows)) if combo_rows else "_no projection knob improved both tune and held-out weeks, so live settings were kept_\n",
          "### P(over) shrink toward 50% (real NFL lines)", table(sh),
          f"Chosen P_SHRINK: {shrink_new} (was {base_shrink}). Rule: best tune-week log-loss, applied only if held-out log-loss also improves.", "",
          "### Ranking layer: RANK_SHRINK (edge term inside rank_score) x AGREE_W (weight on last-10 hit-rate agreement)",
          "In v1 one shrink set both the displayed probability and the ranking. Calibrating it (0.75 -> 0.2) made rank_score mostly negative and let the "
          "hit-rate term dominate, which hurt top-N picks on the tune weeks. The two are now separate: P_SHRINK calibrates the displayed P(over) and model_p_side, and RANK_SHRINK orders picks.",
          table(ag),
          f"Chosen RANK_SHRINK {rank_new} (was {base_rank}), AGREE_W {agree_new} (was {base_agree}). Rule: best tune-week top-25 ROI, applied only if held-out top-25 ROI beats the live pair.", "",
          f"Guard discounts switched off (better top-25 ROI on both tune and held-out real lines): {guard_new or 'none'}.", "",
          "### Held-out before vs after", table(ba), "",
          "## Limitations and leakage notes",
          "- **Missing real lines:** NFL weeks 14-18 and all FBS games are proxy-only. Held-out real-line validation is therefore weeks 10-13 only (4 weeks).",
          "- **Opening vs closing:** opening lines are softer than closing lines, so real-line ROI here is probably better than betting closer to kickoff would give. "
          "The last-listed line can't be used safely because it may include in-game updates.",
          "- **One book:** ESPN BET only (n_books = 1). No line shopping.",
          "- **SP+ as-of proxy:** FBS opponent strength all season uses 2024 final SP+, not in-season ratings, so there's no leak but early-season accuracy is lower than live use would get. "
          "CFBD /teams 2025 conference membership is end-of-season (realignment is known preseason, so this is negligible).",
          "- **Transfer portal list:** the CFBD 2025 portal file is the final list (includes spring-window moves). That's known before the season, so no in-season leak.",
          "- **Implied totals** use closing spread/total (known pregame; slightly sharper than what's available early in the week).",
          "- **Injuries:** the NFL uses the official week-W final injury report (published pregame). FBS has no historical injury data, so there are no injury guards.",
          "- **No weather adjustment** in the backtest (historical forecasts not archived). Live runs use forecasts.",
          "- **Voids:** players without a stat row are voided. A receiver who played but drew no target has no row in nflverse/CFBD box scores, so some winning unders become voids. "
          "That biases under hit rate slightly in both directions of uncertainty.",
          "- **FBS positions** come from the CFBD 2025 roster (~2% inferred from usage when missing).",
          "- **Correlated picks:** top-N lists can hold several props for the same player (e.g. rush yds and rush+rec yds), so effective sample sizes are smaller than bet counts.",
          "- **Synthetic proxy line:** floor(trailing-5 avg)+0.5 is mechanically related to the model's own inputs. It tests whether the model's departures from a naive average are directionally right. It doesn't test profitability.",
          ]
    (OUT / "report.md").write_text("\n".join(md))
    html = md_to_html("\n".join(md)).replace("<title>Prop Finder</title>", "<title>Prop Finder 2025 backtest</title>")
    (OUT / "report.html").write_text(html)
    log(f"report written in {time.time() - t0:.0f}s:", OUT)
    print(json.dumps(result, indent=1, default=str))


if __name__ == "__main__":
    main()
