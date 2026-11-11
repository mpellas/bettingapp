"""Convert cached ESPN core-API historical propBets (ESPN BET, provider 58) into the lines CSV schema.

TIMING CAVEAT (Tester1 B5, verified): the only timestamp ESPN gives is the prop item's `lastUpdated`, and 99.3% of
them are AFTER kickoff. The `open` block is described by ESPN as the opening value, but we cannot verify when it was
observed. These are therefore "ESPN BET lines of uncertain timing", not verified pre-game openers. The `timestamp`
column is exported as `espn_last_updated` to make that explicit.

Source files: /workspace/prop-finder/data/hist_props/nfl/{event_id}.json (fetched earlier by the sibling prop-finder
project; read-only here, no network calls). Main O/U line = the item pair carrying both an over and an under price.
We export the OPENING line+prices (`open`, posted pre-game) as the default because ESPN's `current` value for a
finished event is the last listed value and its timestamp can fall after kickoff. `--which current` exports those.

    python -m nflprops.import_espn_lines [--which open|current] [--out ...]
    default output: data/lines/espn_bet_2025_open_uncertain_timing.csv
"""
from __future__ import annotations

import argparse
import glob
import json
import re

import pandas as pd

from . import DATA
from .data import load

SRC = "/workspace/prop-finder/data/hist_props/nfl"
MK = {"Total Passing Yards": "pass_yds", "Total Rushing Yards": "rush_yds", "Total Receiving Yards": "rec_yds"}


def _am(x):
    v = (x or {}).get("american")
    if v in (None, ""):
        return None
    if v == "EVEN":
        return 100
    try:
        return int(str(v).replace("+", ""))
    except ValueError:
        return None


def parse(raw: dict, which: str) -> list[dict]:
    cand = {}
    for it in raw.get("props", {}).get("58", []):
        name = re.sub(r"\s*\(incl\.? overtime\)\s*$", "", (it.get("type") or {}).get("name", ""), flags=re.I)
        mk = MK.get(name.strip())
        if not mk or "athlete" not in it:
            continue
        m = re.search(r"/athletes/(\d+)", it["athlete"].get("$ref", ""))
        blk = it.get(which) or {}
        for side in ("over", "under"):
            if side in blk:
                cand.setdefault((m.group(1), mk), {}).setdefault(side, []).append(
                    ((blk.get("target") or {}).get("value"), _am(blk.get(side)), it.get("lastUpdated", "")))
    rows = []
    for (aid, mk), d in cand.items():
        # all over/under pairs at the same target with both prices; v1 silently kept the LAST one. Now: if several
        # main pairs exist, keep the most balanced one (smallest |no-vig P(over) - 0.5|) and record how many there were
        pairs = []
        for o in d.get("over", []):
            for u in d.get("under", []):
                if o[0] == u[0] and o[1] and u[1]:
                    io = 1 / (1 + (o[1] / 100 if o[1] > 0 else 100 / abs(o[1])))
                    iu = 1 / (1 + (u[1] / 100 if u[1] > 0 else 100 / abs(u[1])))
                    pairs.append((abs(io / (io + iu) - 0.5), o, u))
        if not pairs:
            continue
        _, o, u = min(pairs, key=lambda x: x[0])
        rows.append({"event_id": raw["event_id"], "espn_id": aid, "market": mk, "line": o[0],
                     "over_price": o[1], "under_price": u[1], "espn_last_updated": max(o[2], u[2]),
                     "n_main_pairs": len(pairs)})
    return rows


def build(which="open") -> pd.DataFrame:
    rows = []
    for f in sorted(glob.glob(f"{SRC}/*.json")):
        rows += parse(json.load(open(f)), which)
    df = pd.DataFrame(rows)
    d = load(2015, 2025)
    s = d["schedules"].dropna(subset=["espn"])
    s = s.assign(espn=s["espn"].astype(str))[["espn", "season", "week", "game_type"]]
    pl = d["players"].dropna(subset=["espn_id"]).assign(espn_id=lambda x: x["espn_id"].astype(str))
    df = df.merge(s, left_on="event_id", right_on="espn", how="inner")
    df = df.merge(pl[["espn_id", "gsis_id", "display_name"]].drop_duplicates("espn_id"), on="espn_id", how="left")
    df = df.rename(columns={"gsis_id": "player_id", "display_name": "player_name"})
    df["book"] = "ESPN BET (uncertain timing)"
    return df[["season", "week", "player_id", "player_name", "market", "line", "over_price", "under_price", "book",
               "espn_last_updated", "n_main_pairs", "event_id", "espn_id", "game_type"]]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", default="open", choices=["open", "current"])
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    df = build(a.which)
    out = a.out or str(DATA / "lines" / f"espn_bet_2025_{a.which}_uncertain_timing.csv")
    df.to_csv(out, index=False)
    print(f"wrote {len(df)} rows -> {out}; unmapped players: {df['player_id'].isna().sum()}")
    print(df.groupby(["season", "market"]).size())
