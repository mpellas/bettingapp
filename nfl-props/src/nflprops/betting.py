"""Turn predicted P(over) into bets: no-vig comparison, edge threshold, fractional Kelly with caps, bankroll sim."""
from __future__ import annotations

import numpy as np
import pandas as pd


def american_to_decimal(a):
    a = np.asarray(a, dtype=float)
    return np.where(a > 0, 1 + a / 100.0, 1 + 100.0 / np.abs(a))


def no_vig_over(over_price, under_price):
    io, iu = 1 / american_to_decimal(over_price), 1 / american_to_decimal(under_price)
    return io / (io + iu)


def add_probs(preds: pd.DataFrame, market_blend: float = 0.0) -> pd.DataFrame:
    p = preds[preds["line"].notna()].copy()
    p["p_mkt_over"] = no_vig_over(p["over_price"], p["under_price"])
    p["p_over"] = (1 - market_blend) * p["p_over_model"] + market_blend * p["p_mkt_over"]
    p["p_over"] = p["p_over"].clip(1e-4, 1 - 1e-4)
    p["over_hit"] = (p["actual"] > p["line"]).astype(float)
    p["push"] = p["actual"] == p["line"]
    return p


def select_bets(p: pd.DataFrame, bc: dict) -> pd.DataFrame:
    """One side per player-game-market: the side with the larger edge vs the no-vig price, if >= threshold & EV>0."""
    thr = bc.get("edge_threshold", 0.04)
    edge_o = p["p_over"] - p["p_mkt_over"]
    edge_u = (1 - p["p_over"]) - (1 - p["p_mkt_over"])
    side_over = edge_o >= edge_u
    b = p.assign(side=np.where(side_over, "over", "under"), edge=np.where(side_over, edge_o, edge_u),
                 p_win=np.where(side_over, p["p_over"], 1 - p["p_over"]),
                 dec=np.where(side_over, american_to_decimal(p["over_price"]), american_to_decimal(p["under_price"])))
    b["ev"] = b["p_win"] * (b["dec"] - 1) - (1 - b["p_win"])
    b = b[(b["edge"] >= thr) & (b["ev"] > 0)].copy()
    b["won"] = np.where(b["side"] == "over", b["actual"] > b["line"], b["actual"] < b["line"])
    b["kelly_f"] = (b["p_win"] * (b["dec"] - 1) - (1 - b["p_win"])) / (b["dec"] - 1)
    b["flat_profit"] = np.where(b["push"], 0.0, np.where(b["won"], b["dec"] - 1, -1.0))
    return b


def simulate_bankroll(bets: pd.DataFrame, bc: dict, start: float | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Week-by-week, stakes sized off the start-of-week bankroll and settled at week end.

    Kelly is applied to the betting probability (the stacked / shrunk p). Exposure caps, applied greedily in order
    of decreasing edge within the week (Tester1 B6/#7 — bets in one game/team are correlated):
      * per player-game: at most `max_bets_per_player` bets (default 1 => only the best of his rush/rec/pass edges)
      * per game: at most `max_bets_per_game` bets and `max_game_frac` of bankroll
      * per team-game: at most `max_team_frac` of bankroll (QB pass + his WR's rec yds are positively correlated)
      * per bet `max_bet_frac`; per week `max_week_exposure` (scaled down proportionally if exceeded)
    Bets that receive no stake under the caps are dropped (they are not counted in any metric)."""
    bank = float(start if start is not None else bc.get("start_bankroll", 1000.0))
    kf, cap, wcap = bc.get("kelly_fraction", 0.25), bc.get("max_bet_frac", 0.02), bc.get("max_week_exposure", 0.2)
    gcap, tcap = bc.get("max_game_frac", 0.04), bc.get("max_team_frac", 0.03)
    gn, pn = bc.get("max_bets_per_game", 3), bc.get("max_bets_per_player", 1)
    out, curve = [], []
    for (season, week), g in bets.sort_values(["season", "week"]).groupby(["season", "week"], sort=True):
        g = g.sort_values("edge", ascending=False)
        want = np.minimum(kf * g["kelly_f"].clip(lower=0).values, cap)
        gsum, tsum, gcnt, pcnt = {}, {}, {}, {}
        frac = np.zeros(len(g))
        for i, (gid, tm, pid) in enumerate(zip(g["game_id"], g["team"], g["player_id"])):
            if gcnt.get(gid, 0) >= gn or pcnt.get((gid, pid), 0) >= pn:
                continue
            f_ = min(want[i], gcap - gsum.get(gid, 0.0), tcap - tsum.get((gid, tm), 0.0))
            if f_ <= 1e-9:
                continue
            frac[i] = f_
            gsum[gid] = gsum.get(gid, 0.0) + f_
            tsum[(gid, tm)] = tsum.get((gid, tm), 0.0) + f_
            gcnt[gid] = gcnt.get(gid, 0) + 1
            pcnt[(gid, pid)] = pcnt.get((gid, pid), 0) + 1
        keep = frac > 0
        g, frac = g[keep], frac[keep]
        if frac.sum() > wcap:
            frac = frac * wcap / frac.sum()
        if len(g) == 0:
            continue
        stake = frac * bank
        profit = np.where(g["push"], 0.0, np.where(g["won"], stake * (g["dec"] - 1), -stake))
        g = g.assign(stake=stake, profit=profit, bank_before=bank)
        bank += profit.sum()
        out.append(g)
        curve.append({"season": season, "week": week, "bankroll": bank, "n_bets": len(g)})
    bets_out = pd.concat(out) if out else bets.iloc[0:0].assign(stake=[], profit=[], bank_before=[])
    return bets_out, pd.DataFrame(curve)
