"""Markdown + PNG report for one evaluated (config, period, line source)."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .markets import MARKETS  # noqa: E402
from .metrics import cluster_bootstrap_roi, reliability  # noqa: E402

SIM_BANNER = ("> **SIMULATED LINES.** Every betting number below is measured against *simulated* sharp-market lines "
              "(see README, 'Simulated lines'). They are a research stress-test, **not evidence of real-world "
              "profitability**.")
REAL_BANNER = ("> **REAL LINES** ({src}). Small sample — treat the game-clustered ROI confidence intervals "
               "seriously.")


def _ci(bets: pd.DataFrame):
    """95% CI of flat ROI from a GAME-clustered bootstrap (bets in one game are correlated; Tester1 B6)."""
    return cluster_bootstrap_roi(bets)


def charts(ev: dict, out: Path, title: str) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    p, bets, curve = ev["_p"], ev["_bets"], ev["_curve"]
    files = {}
    # bankroll curve
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.5))
    if len(curve):
        start = float(ev["_bets"]["bank_before"].iloc[0]) if len(ev["_bets"]) else 1000.0
        y = np.concatenate([[start], curve["bankroll"].values])
        ax[0].plot(np.arange(len(y)), y, color="tab:blue")
        ax[0].axhline(start, color="grey", ls="--", lw=0.8)
        ticks = curve.reset_index(drop=True).groupby("season").head(1)
        ax[0].set_xticks(ticks.index + 1, [f"{s} wk{w}" for s, w in zip(ticks["season"], ticks["week"])])
    ax[0].set_title("Fractional-Kelly bankroll (start 1000)")
    ax[0].set_xlabel("betting week (first week of each season labelled)")
    for mk in sorted(MARKETS):
        b = bets[bets["market"] == mk].sort_values(["season", "week"]) if len(bets) else bets
        if len(b):
            ax[1].plot(np.arange(len(b)), b["flat_profit"].cumsum().values, label=f"{mk} ({len(b)} bets)")
    ax[1].axhline(0, color="grey", ls="--", lw=0.8)
    ax[1].set_title("Cumulative flat-stake profit (units) by market")
    ax[1].set_xlabel("bet #")
    ax[1].legend()
    fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    files["bankroll"] = out / "bankroll_curve.png"
    fig.savefig(files["bankroll"], dpi=110)
    plt.close(fig)
    # calibration
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.2))
    for ax, (name, sub) in zip(axes, [("all markets", p)] + [(m, p[p["market"] == m]) for m in sorted(MARKETS)]):
        sub = sub[~sub["push"]]
        if len(sub) == 0:
            continue
        for col, lab, c in [("p_over_model", "raw model", "tab:orange"), ("p_over", "used (after blend)", "tab:blue")]:
            r = reliability(sub.assign(p_over=sub[col]))
            r = r[r["n"] >= 10]
            ax.plot(r["mean_pred"], r["obs_rate"], "o-", ms=3, label=lab, color=c)
        ax.plot([0, 1], [0, 1], "k--", lw=0.7)
        ax.set_xlim(0, 1), ax.set_ylim(0, 1)
        ax.set_title(f"P(over) calibration: {name} (n={len(sub)})", fontsize=9)
        ax.set_xlabel("predicted P(over)")
        ax.set_ylabel("observed over rate")
        ax.legend(fontsize=7)
    fig.tight_layout()
    files["calibration"] = out / "calibration.png"
    fig.savefig(files["calibration"], dpi=110)
    plt.close(fig)
    # per-market ROI
    fig, ax = plt.subplots(figsize=(7, 4))
    names, rois, lo, hi, ns = [], [], [], [], []
    for mk in sorted(MARKETS) + ["ALL"]:
        b = bets if mk == "ALL" else (bets[bets["market"] == mk] if len(bets) else bets)
        r = b["flat_profit"].mean() * 100 if len(b) else 0.0
        c = _ci(b) if len(b) > 1 else (np.nan, np.nan)
        names.append(mk), ns.append(len(b)), rois.append(r)
        lo.append(0 if np.isnan(c[0]) else r - c[0] * 100), hi.append(0 if np.isnan(c[1]) else c[1] * 100 - r)
    ax.bar(names, rois, yerr=[lo, hi], capsize=6, color=["tab:green" if r > 0 else "tab:red" for r in rois])
    for i, n in enumerate(ns):
        ax.text(i, 0, f"n={n}", ha="center", va="bottom" if rois[i] < 0 else "top", fontsize=8)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_ylabel("flat-stake ROI % (95% CI, game-clustered bootstrap)")
    ax.set_title("ROI per market", fontsize=10)
    fig.tight_layout()
    files["roi"] = out / "roi_by_market.png"
    fig.savefig(files["roi"], dpi=110)
    plt.close(fig)
    return files


def _fmt(v, pct=False, d=3):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "–"
    if pct:
        return f"{v * 100:.1f}%"
    return f"{v:.{d}f}" if isinstance(v, float) else str(v)


def market_table(ev: dict) -> str:
    hdr = ("| market | lines | bets (O/U) | hit rate | flat ROI [95% CI, game-clustered] | Kelly ROI | "
           "Brier used / mkt | log loss raw model / used / mkt | MAE model | MAE naive EWMA | MAE public proj | "
           "MAE line | CRPS |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
    rows = []
    items = list(ev["per_market"].items()) + [("ALL", ev["overall"])]
    for mk, m in items:
        b = ev["_bets"] if mk == "ALL" else (ev["_bets"][ev["_bets"]["market"] == mk] if len(ev["_bets"]) else
                                             ev["_bets"])
        ci = _ci(b)
        rows.append(f"| {mk} | {m.get('n_lines', 0)} | {m['n_bets']} ({m['n_over']}/{m['n_under']}) | "
                    f"{_fmt(m['hit_rate'], True)} | {_fmt(m['flat_roi'], True)} [{_fmt(ci[0], True)}, {_fmt(ci[1], True)}] | "
                    f"{_fmt(m['kelly_roi'], True)} | {_fmt(m.get('brier'), d=4)} / {_fmt(m.get('brier_market'), d=4)} | "
                    f"{_fmt(m.get('logloss_raw'), d=4)} / {_fmt(m.get('logloss'), d=4)} / {_fmt(m.get('logloss_market'), d=4)} | {_fmt(m['mae_model'], d=2)} | "
                    f"{_fmt(m['mae_naive_ewma'], d=2)} | {_fmt(m['mae_market_proxy'], d=2)} | "
                    f"{_fmt(m.get('mae_line'), d=2)} | {_fmt(m['crps_model'], d=2)} |")
    return hdr + "\n".join(rows) + "\n"


def season_table(ev: dict) -> str:
    hdr = "| season | lines | bets | hit rate | flat ROI | log loss model / mkt | MAE model / naive |\n|---|---|---|---|---|---|---|\n"
    rows = [f"| {s} | {m.get('n_lines', 0)} | {m['n_bets']} | {_fmt(m['hit_rate'], True)} | {_fmt(m['flat_roi'], True)} | "
            f"{_fmt(m.get('logloss'), d=4)} / {_fmt(m.get('logloss_market'), d=4)} | {_fmt(m['mae_model'], d=2)} / "
            f"{_fmt(m['mae_naive_ewma'], d=2)} |" for s, m in sorted(ev["per_season"].items())]
    return hdr + "\n".join(rows) + "\n"


def diagnostic_md(preds, cfg: dict, history=None) -> tuple[str, dict]:
    """Fixed, untuned policy (config `diagnostic_policy`) so bet-level metrics exist even if the tuned policy is
    'don't bet'."""
    from .metrics import evaluate
    dp = cfg.get("diagnostic_policy", {"prob_method": "stacker", "edge_threshold": 0.04, "kelly_fraction": 0.25})
    bc = dict(cfg["betting"], **dp)
    ev = evaluate(preds, bc, history)
    o = ev["overall"]
    md = (f"## Fixed policy (not tuned; = the pre-declared holdout policy): probabilities={dp.get('prob_method')}, "
          f"edge_threshold={dp['edge_threshold']}, kelly_fraction={dp['kelly_fraction']}, exposure caps as config\n\n"
          f"Bankroll 1000 → {o['final_bankroll']:.0f}, max drawdown {o['max_drawdown'] * 100:.1f}%.\n\n"
          + market_table(ev))
    return md, ev


def write_report(ev: dict, cfg: dict, bc: dict, out: Path, title: str, simulated: bool, src_name: str,
                 extra_md: str = "", preds=None, history=None) -> Path:
    no_bet = ev["overall"]["n_bets"] == 0
    if preds is not None:
        dmd, dev = diagnostic_md(preds, cfg, history)
        extra_md = dmd + "\n\n" + extra_md
    chart_ev = dev if (no_bet and preds is not None) else ev
    files = charts(chart_ev, out, title + (" — SIMULATED LINES" if simulated else f" — REAL LINES ({src_name})")
                   + (" — charts use the DIAGNOSTIC policy (tuned policy = no bets)" if chart_ev is not ev else ""))
    o = ev["overall"]
    rel = reliability(ev["_p"][~ev["_p"]["push"]])
    md = [f"# {title}", "", SIM_BANNER if simulated else REAL_BANNER.format(src=src_name), "",
          f"* seasons: {sorted(ev['per_season'])}  |  line source: `{src_name}`",
          ("* **tuned policy = DON'T BET** (no betting params grew the bankroll on the validation seasons); "
           "bet-level numbers below come from the diagnostic fixed policy section" if no_bet else ""),
          f"* betting params: probabilities={bc.get('prob_method', 'blend')}, edge_threshold={bc['edge_threshold']}, "
          f"kelly_fraction={bc['kelly_fraction']}, caps: bet {bc['max_bet_frac']}, game {bc.get('max_game_frac')} "
          f"(max {bc.get('max_bets_per_game')} bets), team-game {bc.get('max_team_frac')}, "
          f"{bc.get('max_bets_per_player')} bet/player-game, week {bc['max_week_exposure']}",
          f"* bankroll: 1000 → **{o['final_bankroll']:.0f}**, max drawdown **{o['max_drawdown'] * 100:.1f}%**, "
          f"turnover {o['turnover']:.0f}",
          f"* model: `{json.dumps(cfg['model'])}`", "",
          "## Per market", "", market_table(ev), "",
          "Brier/log loss are for P(over) on **every** priced line (not just bets): *raw model* = the distributional "
          "model alone, *used* = after the rolling stacker (market probability until a market has enough earlier "
          "lines), *mkt* = no-vig implied probability. A model has information beyond the line only if its log loss "
          "is *below* the market's. ROI CIs are game-clustered bootstrap intervals. MAE columns compare the model mean to a naive EWMA, the public projection and the line.", "",
          "## Per season", "", season_table(ev), "",
          "## Reliability (all markets, P(over) used for betting)", "",
          "| bin mean pred | observed over rate | n |\n|---|---|---|\n" +
          "\n".join(f"| {r.mean_pred:.3f} | {r.obs_rate:.3f} | {r.n} |" for r in rel.itertuples()), "",
          "## Charts", "", f"![bankroll]({files['bankroll'].name})", "", f"![calibration]({files['calibration'].name})",
          "", f"![roi]({files['roi'].name})", "", extra_md]
    (out / "report.md").write_text("\n".join(md))
    return out / "report.md"
