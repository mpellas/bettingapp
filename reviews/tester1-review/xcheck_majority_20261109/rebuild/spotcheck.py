import json, pandas as pd, os, urllib.request

API = "/workspace/tester1-review/xcheck_majority_20261109/rebuild/nhl_api"
mine = pd.read_csv("/workspace/tester1-review/xcheck_majority_20261109/rebuild/my_graded_sides.csv")
graded = mine[mine.result.isin(["W","L"])].copy()

# Build box lookup with TOI / sweater if present
info = {}  # (pid,gid) -> dict
for fn in os.listdir(API):
    if not fn.startswith("box_"): continue
    b = json.load(open(os.path.join(API, fn)))
    gid = b["id"]
    pbg = b.get("playerByGameStats") or {}
    for t in ("awayTeam", "homeTeam"):
        team = pbg.get(t) or {}
        for grp in ("forwards", "defense", "goalies"):
            for p in team.get(grp) or []:
                pid = p.get("playerId")
                if pid is None: continue
                info[(int(pid), int(gid))] = {
                    "name": (p.get("name") or {}).get("default") if isinstance(p.get("name"), dict) else p.get("name"),
                    "sog": p.get("sog"),
                    "toi": p.get("toi") or p.get("timeOnIce") or p.get("toiPerGame"),
                    "grp": grp,
                    "team": t,
                    "keys": list(p.keys()),
                }

# zeros and low TOI
print("======= 0-SHOT GRADED SIDES (DNP risk) =======")
zeros = graded[graded.actual == 0]
for _, r in zeros.iterrows():
    inf = info.get((int(r.nhl_id), int(r.gameId)), {})
    print(f"  {r.player} {r.side} {r.line} actual={r.actual} result={r.result} toi={inf.get('toi')} grp={inf.get('grp')} box_sog={inf.get('sog')} name={inf.get('name')}")

# anyone graded whose box row is missing? (shouldn't)
print("\n======= GRADED WITH NO BOX ROW =======")
for _, r in graded.iterrows():
    if (int(r.nhl_id), int(r.gameId)) not in info:
        print(" MISSING", r.player, r.gameId, r.actual)

# anyone in universe for finished games with no box row (would be void)
print("\n======= FINISHED BUT NO BOX (voids) =======")
fin = mine[mine.result != "pending"]
for _, r in fin.iterrows():
    if (int(r.nhl_id), int(r.gameId)) not in info:
        print(" NO BOX", r.player, r.game, r.result)

# Spot-check 12 diverse sides: print box SOG
spot = [
    ("Clayton Keller",), ("Lane Hutson",), ("Cole Caufield",),
    ("David Pastrnak",), ("Pavel Zacha",), ("Rickard Rakell",),
    ("Charlie McAvoy",), ("Moritz Seider",), ("Porter Martone",),
    ("Evgeni Malkin",), ("Tyler Bertuzzi",), ("Sidney Crosby",),
]
print("\n======= SPOT CHECK (boxscore vs our actual) =======")
# just print 12 specific plus a systematic sample
names = ["Clayton Keller","Lane Hutson","Cole Caufield","David Pastrnak","Pavel Zacha",
         "Rickard Rakell","Charlie McAvoy","Moritz Seider","Porter Martone","Evgeni Malkin",
         "Tyler Bertuzzi","Sidney Crosby","Zack Bolduc","Mikhail Sergachev","Ben Kindel"]
for _, r in graded[graded.player.isin(names)].iterrows():
    inf = info.get((int(r.nhl_id), int(r.gameId)), {})
    ok = inf.get("sog") == r.actual
    print(f"  {'OK' if ok else 'DIFF'} {r.game[:40]:40} {r.player:22} box_sog={inf.get('sog')} actual={r.actual} toi={inf.get('toi')} {r.side} {r.line} {r.result}")

# stats API cross-check
print("\n======= STATS API PULL =======")
url = 'https://api.nhle.com/stats/rest/en/skater/summary?isAggregate=false&isGame=true&limit=-1&cayenneExp=gameDate="2026-11-05" and gameTypeId=2'
try:
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    data = json.load(urllib.request.urlopen(req, timeout=60))["data"]
    smap = {(int(x["playerId"]), int(x["gameId"])): int(x["shots"]) for x in data if x.get("shots") is not None}
    print("stats rows", len(data), "shot keys", len(smap), "gameIds", sorted({int(x["gameId"]) for x in data}))
    diffs = 0
    missing = 0
    for _, r in graded.iterrows():
        k = (int(r.nhl_id), int(r.gameId))
        if k not in smap:
            missing += 1
            print("  missing in stats", r.player, r.gameId, "box", r.actual)
        elif smap[k] != int(r.actual):
            diffs += 1
            print("  DIFF stats", smap[k], "box", r.actual, r.player)
    print(f"stats vs box on 67: diffs={diffs} missing={missing}")
    # late games present?
    late = {2026020259,2026020260,2026020261}
    print("stats includes late games?", late <= {int(x['gameId']) for x in data})
except Exception as e:
    print("stats API failed:", type(e), e)

# TOI distribution for zeros already printed. Also check scratches list from box?
print("\n======= SCRATCHES on Nov 5 boxes vs our sides =======")
# box may have scratches somewhere
b = json.load(open(os.path.join(API, "box_2026020251.json")))
print("top keys", b.keys())
# look for scratch
for k,v in b.items():
    if "scratch" in k.lower() or "roster" in k.lower() or "lineup" in k.lower():
        print(" key", k, type(v))
# gameInfo?
if "gameInfo" in b:
    print("gameInfo keys", b["gameInfo"].keys() if isinstance(b["gameInfo"], dict) else type(b["gameInfo"]))

# sample player keys
sample = info[next(iter(info))]
print("player keys", sample["keys"])

# 1512 unique check
print("\n======= 1512 only sides (should be 0) =======")
# already know appeared_on
his = pd.read_csv("/workspace/tester1-review/xcheck_majority_20261109/src/majority/graded_sides.csv")
print(his[his.appeared_on.str.contains("1512") & ~his.appeared_on.str.contains("1401") & ~his.appeared_on.str.contains("1509")])
print("1512 appearances", his.appeared_on.str.contains("1512").sum())

# Nov 6-8 confirm from source dirs (copied? we listed earlier)
print("\n======= late Nov5 games max agrees if they had been on a sheet? (they weren't) =======")
print("sheet games only the 8 early")

# units by over/under and date already have

# Heineman Nov 5 vs Nov 9
print("\nHeineman rows:")
print(mine[mine.player.str.contains("Heineman")][["date","game","side","line","price","src","result","actual"]].to_string(index=False))
