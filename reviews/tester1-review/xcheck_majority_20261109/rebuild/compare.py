import pandas as pd, json, glob, os

mine = pd.read_csv("/workspace/tester1-review/xcheck_majority_20261109/rebuild/my_graded_sides.csv")
his = pd.read_csv("/workspace/tester1-review/xcheck_majority_20261109/src/majority/graded_sides.csv")

# normalize keys
for d in (mine, his):
    d["player"] = d["player"].astype(str).str.strip()
    d["side"] = d["side"].astype(str).str.upper()
    d["game"] = d["game"].astype(str).str.strip()
    d["line"] = d["line"].astype(float)
    d["date"] = d["date"].astype(str)

# his appeared_on vs my appeared (I used pass_ only, need to compare format)
# my appeared is like 1401,1512 — his is 20261109_1401,20261109_1512
def norm_appear(row, col, has_date=False):
    s = str(row[col])
    if s in ("nan", ""):
        return ""
    parts = []
    for p in s.split(","):
        p = p.strip()
        if "_" in p and len(p) >= 13:
            parts.append(p)
        else:
            parts.append(f"{row['date']}_{p}")
    return ",".join(parts)

mine["appeared_on"] = [norm_appear(r, "appeared") for _, r in mine.iterrows()]
mine["list_id"] = mine["date"].astype(str) + "_" + mine["pass_"].astype(str).str.zfill(4)

k = ["date", "game", "player", "side", "line"]
print("mine unique", mine.groupby(k).ngroups, "rows", len(mine), "his", his.groupby(k).ngroups, "rows", len(his))

m_keys = set(map(tuple, mine[k].values))
h_keys = set(map(tuple, his[k].values))
print("only mine", len(m_keys-h_keys), list(m_keys-h_keys)[:10])
print("only his", len(h_keys-m_keys), list(h_keys-m_keys)[:10])

# merge
H = his.set_index(k)
M = mine.set_index(k)
both = H.index.intersection(M.index)
print("overlap", len(both))

def mismatches(col_h, col_m, tol=None):
    rows = []
    for idx in both:
        a, b = H.loc[idx, col_h], M.loc[idx, col_m]
        if tol is not None:
            # numeric
            if pd.isna(a) and pd.isna(b):
                continue
            try:
                if abs(float(a) - float(b)) <= tol:
                    continue
            except Exception:
                pass
            rows.append((idx, a, b))
        else:
            sa, sb = str(a), str(b)
            if sa == "nan" and sb == "nan":
                continue
            if sa != sb:
                rows.append((idx, a, b))
    return rows

checks = [
    ("result", "result", None),
    ("price", "price", 0),
    ("price_source", "src", None),
    ("in_band", "in_band", None),
    ("agrees_n", "agrees_n", 0),
    ("list_id", "list_id", None),
    ("appeared_on", "appeared_on", None),
    ("dk_price", "dk", 0),
    ("actual", "actual", 0),
    ("units", "units", 1e-6),
    ("gameId", "gameId", 0),
    ("nhl_id", "nhl_id", 0),
    ("game_finished", "result", "SPECIAL"),
]
print("\n======= FIELD DIFFS =======")
# result, price, etc.
for col_h, col_m, tol in [
    ("result","result",None),
    ("price","price",0),
    ("price_source","src",None),
    ("in_band","in_band",None),
    ("agrees_n","agrees_n",0),
    ("list_id","list_id",None),
    ("appeared_on","appeared_on",None),
    ("dk_price","dk",0),
    ("actual","actual",0),
    ("units","units",1e-5),
    ("gameId","gameId",0),
    ("nhl_id","nhl_id",0),
]:
    mm = mismatches(col_h, col_m, tol)
    print(f"{col_h}: {len(mm)} mismatches")
    for item in mm[:15]:
        print("   ", item)

# game_finished vs pending
fin_mm = []
for idx in both:
    hf = bool(H.loc[idx, "game_finished"])
    mf = M.loc[idx, "result"] != "pending"
    if hf != mf:
        fin_mm.append((idx, H.loc[idx,"game_finished"], M.loc[idx,"result"]))
print(f"game_finished vs pending: {len(fin_mm)}")
for item in fin_mm[:10]:
    print("   ", item)

# missing nhl_id in mine
print("\nmine missing ids", mine.nhl_id.isna().sum(), mine.gameId.isna().sum())
print("his missing ids", his.nhl_id.isna().sum(), his.gameId.isna().sum())

# Fliff
print("\nFliff rows mine:")
print(mine[mine.src=="fliff"][["player","side","line","price","dk","list_id"]].to_string())
print("Fliff rows his:")
print(his[his.price_source=="fliff"][["player","side","line","price","dk_price","list_id"]].to_string())

# Utah detail
print("\n======= UTAH 0-9 =======")
uta = mine[mine.game.str.contains("Utah")]
print(uta[["player","side","line","agrees_n","price","actual","result","units"]].to_string(index=False))

# All unders
print("\n======= ALL GRADED UNDERS =======")
u = mine[(mine.side=="UNDER")&(mine.result.isin(["W","L"]))]
print(u[["game","player","side","line","price","actual","result","units"]].to_string(index=False))

# User plays
print("\n======= USER PLAYS =======")
plays = [
    ("20261109", "J.T. Miller", "OVER", 1.5),
    ("20261109", "Porter Martone", "OVER", 1.5),
    ("20261105", "Pavel Zacha", "OVER", 1.5),
    ("20261105", "David Pastrnak", "OVER", 3.5),  # list line may differ
    ("20261105", "Rickard Rakell", "OVER", 2.5),
]
# also search by player name loosely
for date, name, side, line in plays:
    hit = mine[(mine.date==date)&(mine.player==name)]
    print(f"--- {name} {date} sought {side} {line} ---")
    if hit.empty:
        # fuzzy
        hit = mine[mine.player.str.contains(name.split()[-1], case=False)]
        print("  exact miss, surname hits:")
    print(hit[["date","game","player","side","line","agrees_n","price","result","actual","list_id"]].to_string(index=False) if len(hit) else "  NOT IN SET")

# any Pastrnak / Rakell / Zacha other lines
print("\nall zacha/pastrnak/rakell/miller/martone in universe:")
print(mine[mine.player.str.contains("Zacha|Pastrnak|Rakell|Miller|Martone", case=False)][
    ["date","player","side","line","agrees_n","price","result","actual"]].to_string(index=False))

# Nov 5 late games in full sheet (any agrees_n)
sheet = pd.read_excel("/workspace/tester1-review/xcheck_majority_20261109/src/sheets/20261105_D_1239_picks.xlsx")
print("\n======= NOV5 SHEET GAMES / PUCK DROP =======")
print(sheet.groupby("game").agg(n=("player","count"), drop=("puck_drop_pt","first"), max_ag=("agrees_n","max")).to_string())

# Compare shots: box vs graded csv vs pkl
print("\n======= SHOT SOURCE DISAGREEMENTS (graded sides only) =======")
g = pd.read_csv("/workspace/tester1-review/xcheck_majority_20261109/src/graded/20261105.csv")
pkl = pd.read_pickle("/workspace/tester1-review/xcheck_majority_20261109/src/shadow/s2026_live.pkl")
# box already in mine.actual for graded
graded = mine[mine.result.isin(["W","L","void","push"])].copy()
# lookup graded csv
gmap = {}
for _, r in g.iterrows():
    if pd.notna(r.actual):
        gmap[(int(r.nhl_id), int(r.gameId))] = int(r.actual)
pmap = {}
for _, r in pkl.iterrows():
    if pd.notna(r.shots):
        pmap[(int(r.playerId), int(r.gameId))] = int(r.shots)

n_box_g = n_box_p = n_g_p = 0
dis = []
for _, r in graded.iterrows():
    k2 = (int(r.nhl_id), int(r.gameId))
    box = r.actual if pd.notna(r.actual) else None
    gv = gmap.get(k2)
    pv = pmap.get(k2)
    if box is not None and gv is not None and int(box) != int(gv):
        n_box_g += 1
        dis.append(("box vs graded.csv", r.player, r.game, box, gv, pv))
    if box is not None and pv is not None and int(box) != int(pv):
        n_box_p += 1
        dis.append(("box vs pkl", r.player, r.game, box, gv, pv))
    if gv is not None and pv is not None and int(gv) != int(pv):
        n_g_p += 1
print(f"box vs graded.csv diffs: {n_box_g}")
print(f"box vs pkl diffs: {n_box_p}")
print(f"graded.csv vs pkl diffs (on these sides): {n_g_p}")
for d in dis[:20]:
    print(" ", d)

# units recompute check vs his
import math
def am2dec(a):
    a=float(a)
    return 1 + (a/100.0 if a>0 else 100.0/-a)
his_wl = his[his.result.isin(["W","L"])].copy()
his_wl["u2"] = his_wl.apply(lambda r: (am2dec(r.price)-1) if r.result=="W" else -1.0, axis=1)
print("\nhis units vs recomputed max abs", (his_wl.units - his_wl.u2).abs().max())
print("his units sum", his_wl.units.sum(), "recomputed", his_wl.u2.sum())

# break-even convention
print("1/mean(dec)", 1/his_wl.price.map(am2dec).mean())
print("mean of 1/dec (avg implied)", (1/his_wl.price.map(am2dec)).mean())

# band edge cases: exactly -150
print("\nprice == -150 count", (his.price==-150).sum())
print(his[his.price==-150][["player","side","line","price","in_band","result"]].to_string(index=False))
print("price < -150 and in_band?", ((his.price<-150)&(his.in_band==True)).sum())
print("price >= -150 and not in_band?", ((his.price>=-150)&(his.in_band==False)).sum())

# 6 of 7 detail
print("\n======= 6 of 7 =======")
print(his[his.agrees_n==6][["date","game","player","side","line","price","actual","result","units","in_band"]].to_string(index=False))

# How many of 67 were user-played (only those in graded, i.e. Nov 5)
print("\n======= 67 graded that are user plays =======")
user = mine[(mine.result.isin(["W","L"])) & (mine.player.isin(["Pavel Zacha","David Pastrnak","Rickard Rakell","J.T. Miller","Porter Martone"]))]
print(user[["date","player","side","line","result","actual","price"]].to_string(index=False))
