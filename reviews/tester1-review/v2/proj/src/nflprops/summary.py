"""Build reports/REPORT.md: data, leakage check (current + legacy v1), the pre-declared holdout policy (with sha1),
experiment history under the v2 promotion rule, champion walk-forward 2019-2024 (SIMULATED lines), sensitivity to
the simulated market's sharpness, and the FROZEN holdout result if `python -m nflprops.holdout` has been run.

This script never scores the holdout season (Tester1 B10): it only reads experiments/holdout_frozen.json.

    python -m nflprops.summary
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from . import EXPERIMENTS, REPORTS, leakage  # noqa: E402
from .backtest import walk_forward  # noqa: E402
from .config import deep_update  # noqa: E402
from .features import FEATURE_VERSION, load_features  # noqa: E402
from .holdout import FROZEN, POLICY, policy_sha1  # noqa: E402
from .improve import CHAMP, RUNS  # noqa: E402
from .metrics import cluster_bootstrap_roi, evaluate  # noqa: E402
from .report import _fmt, diagnostic_md, market_table, write_report  # noqa: E402

DECL = EXPERIMENTS / "policy_declared.json"


def history_chart(runs: pd.DataFrame, st: dict, path):
    fig, ax = plt.subplots(figsize=(9, 4.2))
    c = runs[(runs["role"] == "candidate")]
    ax.scatter(c["iteration"], c["metrics.logloss_raw"], c="lightgrey", label="candidate (validation 2019-22)",
               zorder=2)
    init = runs[(runs["role"] == "initial_champion") & (runs["period"] == "validation")]["metrics.logloss_raw"]
    cur, its, vals = float(init.iloc[0]), [0], [float(init.iloc[0])]
    for h in st["history"][1:]:
        if h.get("promoted"):
            cur = h["val_raw_ll_challenger"]
        its.append(h["iteration"]), vals.append(cur)
    ax.step(its, vals, where="post", color="tab:blue", label="champion (validation 2019-22)")
    ch = runs[runs["role"] == "challenger"]
    if len(ch):
        ax.scatter(ch["iteration"], ch["metrics.logloss_raw"], marker="x", color="tab:red",
                   label="challenger (selection 2023-24)", zorder=3)
    ax.axhline(0.693147, color="k", ls="--", lw=0.8, label="ln 2 (coin flip)")
    ax.set_xlabel("improvement iteration")
    ax.set_ylabel("RAW model log loss of P(over) at the line")
    ax.set_title("Experiment loop, v2 rule (simulated lines)")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def _leak(legacy: bool, name: str):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ok = leakage.run(legacy=legacy)
    (REPORTS / name).write_text(buf.getvalue())
    return ok, buf.getvalue().strip()


def holdout_md(fr: dict) -> str:
    out = [f"Scored at {fr['scored_at']} (policy sha1 `{fr['policy_sha1']}`, champion `{fr['champion_hash']}`"
           f"{', FORCED re-run' if fr.get('forced') else ''}). Read from `experiments/holdout_frozen.json`; "
           "not re-scored by this script.\n"]
    for tag in ("real_espn_uncertain_timing", "sim"):
        r = fr[tag]
        head = ("### PRIMARY: ESPN BET lines of uncertain timing (REAL prices, 2025 REG wk 1-13)" if tag != "sim"
                else "### Secondary: SIMULATED 2025 lines (not evidence of real profitability)")
        rows = []
        for mk, v in list(r["per_market"].items()) + [("ALL", r)]:
            ci = v["roi_ci95_game_clustered"]
            lr, ls = v["ll_gain_raw_vs_market"], v["ll_gain_stacked_vs_market"]
            rows.append({"market": mk, "lines": v["n_lines"], "bets": v["n_bets"], "games bet": v["n_games_bet"],
                         "hit rate": _fmt(v["hit_rate"], True),
                         "flat ROI [95% CI, game-clustered]": f"{_fmt(v['flat_roi'], True)} [{_fmt(ci[0], True)}, "
                                                              f"{_fmt(ci[1], True)}]",
                         "LL raw / stacked / mkt": f"{_fmt(v['logloss_raw'], d=4)} / {_fmt(v['logloss'], d=4)} / "
                                                   f"{_fmt(v['logloss_market'], d=4)}",
                         "LL gain raw vs mkt [95% CI]": f"{lr['gain_nats_per_line']:+.4f} [{lr['ci95'][0]:+.4f}, "
                                                        f"{lr['ci95'][1]:+.4f}]",
                         "LL gain stacked vs mkt [95% CI]": f"{ls['gain_nats_per_line']:+.4f} [{ls['ci95'][0]:+.4f}, "
                                                            f"{ls['ci95'][1]:+.4f}]",
                         "MAE model / line": f"{_fmt(v['mae_model'], d=2)} / {_fmt(v.get('mae_line'), d=2)}"})
        out += [head, "", f"Bankroll 1000 → **{r['final_bankroll']:.0f}** (Kelly {r['kelly_roi'] * 100 if r['kelly_roi'] == r['kelly_roi'] else float('nan'):.1f}% ROI on turnover), "
                f"max drawdown {r['max_drawdown'] * 100:.1f}%. First week with stacker coefficients (bets possible) "
                f"by market: {r.get('first_bettable_week_by_market')}. Report: `{r['report']}`", "",
                pd.DataFrame(rows).to_markdown(index=False), "",
                "Last stacker coefficients (c = model weight): " + json.dumps(
                    {k: {kk: round(vv, 3) if isinstance(vv, float) else vv for kk, vv in v.items()}
                     for k, v in r["stacker_coefs_last"].items()}), ""]
    out += ["**Simulated vs real lines on the same 2025 player-games** (simulator realism):", "",
            pd.DataFrame(fr["sim_vs_real_lines"]).T.round(3).to_markdown(), ""]
    return "\n".join(out)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    REPORTS.mkdir(exist_ok=True)
    st = json.loads(CHAMP.read_text())
    cfg = st["champion"]
    V, S, H = cfg["periods"]["validation_seasons"], cfg["periods"]["selection_seasons"], cfg["periods"]["holdout_season"]
    feats = load_features(cfg["data"]["first_season"], cfg["data"]["last_season"])

    sha = policy_sha1()
    if not DECL.exists() and not FROZEN.exists():
        DECL.write_text(json.dumps({"policy_sha1": sha, "declared_at": dt.datetime.now().astimezone()
                                    .isoformat(timespec="seconds")}, indent=2))
    decl = json.loads(DECL.read_text()) if DECL.exists() else {}
    if decl.get("policy_sha1") != sha:
        logging.warning("policy file changed since declaration (%s -> %s)", decl.get("policy_sha1"), sha)

    ok, leak_txt = _leak(False, "leakage_check.txt")
    ok_old, leak_old = _leak(True, "leakage_check_legacy_v1.txt")

    # champion walk-forward 2019-2024, tuned policy (from validation) + fixed policy
    bc = dict(cfg["betting"], **{k: st["betting"][k] for k in ("edge_threshold", "kelly_fraction")})
    preds = walk_forward(cfg, V + S, feats)
    ev = evaluate(preds, bc)
    write_report(ev, cfg, bc, REPORTS / "champion_walkforward_2019_2024_sim",
                 f"Champion walk-forward {V[0]}–{S[-1]} (validation + selection)", True, "simulated_sharp",
                 preds=preds)
    predsV = walk_forward(cfg, V, feats)
    predsS = walk_forward(cfg, S, feats)
    evS = evaluate(predsS, bc, predsV)
    dmd_all, dev_all = diagnostic_md(preds, cfg)
    dmd_S, _ = diagnostic_md(predsS, cfg, predsV)
    wk = ev["_bets"]
    roi_week_ci = cluster_bootstrap_roi(wk.assign(sw=wk["season"] * 100 + wk["week"]), key="sw") if len(wk) else None

    sens = []
    dp = dict(cfg["betting"], **cfg.get("diagnostic_policy", {}))
    for label, r in [("ref_share=0.0 (softer market)", 0.0), ("ref_share=0.5 (DEFAULT)", 0.5),
                     ("ref_share=1.0 (market knows a strong public model)", 1.0)]:
        c2 = deep_update(cfg, {"lines": {"sim": {"ref_share": r}}})
        pr, hv = walk_forward(c2, S, feats), walk_forward(c2, V, feats)
        e2 = evaluate(pr, dp, hv)
        o = e2["overall"]
        ci = cluster_bootstrap_roi(e2["_bets"])
        sens.append({"simulated market": label, "bets": o["n_bets"], "hit rate": _fmt(o["hit_rate"], True),
                     "flat ROI [95% CI]": f"{_fmt(o['flat_roi'], True)} [{_fmt(ci[0], True)}, {_fmt(ci[1], True)}]",
                     "LL raw / stacked / mkt": f"{_fmt(o['logloss_raw'], d=4)} / {_fmt(o['logloss'], d=4)} / "
                                               f"{_fmt(o['logloss_market'], d=4)}",
                     "final bankroll": f"{o['final_bankroll']:.0f}"})
    sens_md = pd.DataFrame(sens).to_markdown(index=False)

    from .lines import calibrate_sim
    from .reference import attach_reference
    calib = calibrate_sim(attach_reference(feats, cfg), cfg)
    runs = pd.json_normalize([json.loads(line) for line in open(RUNS)])
    history_chart(runs, st, REPORTS / "experiment_history.png")
    hist_rows = []
    for h in st["history"]:
        hist_rows.append({
            "iter": h["iteration"], "event": h.get("event"), "best candidate change": ", ".join(h.get("changes", [])),
            "val raw LL chal / champ": f"{_fmt(h.get('val_raw_ll_challenger'), d=5)} / {_fmt(h.get('val_raw_ll_champion'), d=5)}",
            "val seasons better": h.get("val_seasons_better", "–"),
            "sel raw-LL gain": _fmt(h.get("sel_gain"), d=5), "SE (game-clustered)": _fmt(h.get("sel_se"), d=5),
            "z_adj (Bonferroni m)": f"{_fmt(h.get('z_adj'), d=2)} ({h.get('m_tests', '–')})",
            "required margin": _fmt(h.get("margin"), d=5), "candidates tried so far": h.get("n_candidates_tried", "–")})
    cand = runs[runs["role"] == "candidate"][["run_id", "iteration", "changes", "metrics.logloss_raw",
                                              "metrics.logloss", "metrics.logloss_market", "metrics.mae_model",
                                              "metrics.n_bets", "metrics.flat_roi", "betting.edge_threshold",
                                              "betting.kelly_fraction", "betting.market_blend"]]
    cand = cand.assign(changes=cand["changes"].map(lambda x: ", ".join(x)))
    cand.columns = [c.replace("metrics.", "").replace("betting.", "") for c in cand.columns]
    cand = cand.rename(columns={"market_blend": "best diag. blend", "logloss": "logloss_stacked"})

    fr = json.loads(FROZEN.read_text()) if FROZEN.exists() else None
    pol_txt = POLICY.read_text()
    o = ev["overall"]
    md = f"""# NFL player-prop research pipeline — summary report (v2, after Tester1 review)

> **Read this first.** No real historical prop odds exist in this pipeline for 2015-2024. Every betting metric for
> 2019-2024 is measured against **SIMULATED** lines and **cannot show real-world profitability**. The only test
> against real prices is the frozen 2025 holdout against **ESPN BET lines of uncertain timing** (one book, weeks
> 1-13). ESPN's timestamps are last-update times, 99.3% of them after kickoff, so these are not clean opening lines.

## Data actually used
* nflverse weekly player stats, snap counts and schedules (from schedules only rest days, roof, home/away, division,
  and PRIOR games' scores and starting QBs are used; no spread/total/weather/actual-starter features since v2), seasons **{int(feats['season'].min())}–{int(feats['season'].max())}**,
  {len(feats):,} offensive player-game rows. Feature version `{FEATURE_VERSION}`.
* Walk-forward periods: validation {V}, selection {S}, frozen holdout {H}.
* Simulated-line calibration (pre-validation seasons only): `{json.dumps(calib)}`
  (c = public-projection median multiplier, beta = efficient weight on the noisy inside-info signal,
  info_noise_sd = signal noise solved so MAE(line)/MAE(public projection) matches the ESPN ratios).

## Pre-declared 2025 holdout policy
`configs/holdout_policy.yaml`, sha1 **`{sha}`**, first published in this report at **{decl.get('declared_at', '?')}**
(before the holdout was scored). `python -m nflprops.holdout` refuses to run unless this sha1 is in this file and
refuses to run twice.

```yaml
{pol_txt.strip()}
```

## Leakage check — current features: {"PASS" if ok else "FAIL"}; legacy v1 features: {"PASS (test is blind!)" if ok_old else "FAIL (as it should: test catches the v1 look-ahead)"}
The check rebuilds features after scrambling every post-cutoff row: player stats, snaps, **and** game-level schedule
fields (spread, total, moneylines, wind, temperature, scores, roof open/closed and the starting-QB ids). Pre-cutoff
feature values must be unchanged.

Current (`reports/leakage_check.txt`):
```
{leak_txt}
```
Legacy v1 features (`reports/leakage_check_legacy_v1.txt`):
```
{leak_old}
```

## Improvement loop under the v2 promotion rule (experiments/runs.jsonl, experiments/champion.json)
Rule: rank candidates by validation **raw** model log loss (no market blend). The challenger must beat the champion
overall and in ≥ {cfg['improve']['min_val_seasons_better']} of {len(V)} validation seasons. On the selection seasons it
must then show a raw log-loss gain > z_adj × SE, where SE comes from a paired game-clustered bootstrap and
z_adj = Φ⁻¹(1 − {cfg['improve']['alpha']}/m), with m = the number of promotion tests so far (Bonferroni).
Candidates tried: **{st['n_candidates_tried']}**; promotion tests: **{st['n_promotion_tests']}**;
promotions: **{sum(bool(h.get('promoted')) for h in st['history'])}**.

![history](experiment_history.png)

{pd.DataFrame(hist_rows).to_markdown(index=False)}

All candidates (validation 2019-2022; betting params tuned on validation only; "best diag. blend" = the linear
market blend with the best validation log loss, a diagnostic only, 1.0 = model adds nothing):

{cand.to_markdown(index=False)}

Champion `{st['champion_hash']}`: model `{json.dumps(cfg['model'])}`; validation-tuned betting `{json.dumps(st['betting'])}`.

## Champion walk-forward 2019-2024 — SIMULATED lines
Full report: `reports/champion_walkforward_2019_2024_sim/report.md`. Tuned policy (validation-tuned edge/Kelly,
stacker probabilities, exposure caps): bankroll 1000 → {o['final_bankroll']:.0f}, max drawdown
{o['max_drawdown'] * 100:.1f}%. Week-clustered 95% ROI CI: {roi_week_ci and f"[{_fmt(roi_week_ci[0], True)}, {_fmt(roi_week_ci[1], True)}]"}.

{market_table(ev)}

{dmd_all}

Selection seasons only ({S}); these were not used to tune this champion's betting params. Stacker history = validation seasons. Tuned policy:

{market_table(evS)}

{dmd_S}

## Sensitivity: selection-period result vs simulated-market sharpness (fixed policy, SIMULATED)
{sens_md}

## Frozen holdout {H}
{holdout_md(fr) if fr else "_not scored yet: `python -m nflprops.holdout` (one time only)_"}
"""
    (REPORTS / "REPORT.md").write_text(md)
    print(REPORTS / "REPORT.md")


if __name__ == "__main__":
    main()
