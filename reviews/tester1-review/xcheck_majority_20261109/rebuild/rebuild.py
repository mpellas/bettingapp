"""Tester1 independent rebuild of NHL majority-list grader (Nov 5 + Nov 9).
Convention: risk 1u flat; win pays (dec-1); loss -1; void/push 0 and excluded.
Price: DK list price from the sheet, Fliff only if an 'offered' capture at the
same line is tied to that pass. Band: outside iff price < -150."""
import pandas as pd, glob, os, re, json
S="../src"
rows=[]
for p in sorted(glob.glob(f"{S}/sheets/*_D_*_picks.xlsx")):
    d,hh=re.match(r".*/(\d{8})_D_(\d{4})_picks",p).groups()
    df=pd.read_excel(p); df=df[df.agrees_n>=4]
    for _,r in df.iterrows():
        rows.append(dict(date=d,pass_=hh,game=r.game.strip(),player=r.player.strip(),side=r.side.upper(),
                         line=float(r.line),agrees_n=int(r.agrees_n),dk=int(r.dk_price)))
A=pd.DataFrame(rows).sort_values(["date","pass_"])
k=["date","game","player","side","line"]
app=A.groupby(k)["pass_"].agg(lambda s:",".join(s))
U=A.drop_duplicates(k,keep="first").set_index(k); U["appeared"]=app; U=U.reset_index()
# check agrees_n / price drift across passes
drift=A.groupby(k).agg(n_ag=("agrees_n","nunique"),n_dk=("dk","nunique")); 
print("sides with agrees_n changing across passes:",(drift.n_ag>1).sum(),"dk changing:",(drift.n_dk>1).sum())
# ids from D csvs
D=pd.concat([pd.read_csv(f) for f in glob.glob(f"{S}/picks/*_D_*.csv") if "GATE" not in f])
D["date"]=D.captured_utc.astype(str) if False else None
ids={}
for f in glob.glob(f"{S}/picks/*_D_*.csv"):
    if "GATE" in f: continue
    d=os.path.basename(f)[:8]
    for _,r in pd.read_csv(f).iterrows(): ids[(d,r.game.strip(),r.player.strip())]=(int(r.nhl_id),int(r.gameId))
U["nhl_id"]=[ids.get((r.date,r.game,r.player),(None,None))[0] for r in U.itertuples()]
U["gameId"]=[ids.get((r.date,r.game,r.player),(None,None))[1] for r in U.itertuples()]
# fliff
F=pd.concat([pd.read_csv(f) for f in glob.glob(f"{S}/fliff_prices/*.csv")])
U["price"]=U.dk; U["src"]="dk"
for _,f in F[F.fliff_status=="offered"].iterrows():
    m=(U.date==str(f.date))&(U.player==f.player)&(U.side==f.side.upper())&(U.line==f.line)&(f.fliff_line==f.line)
    m&=U.apply(lambda r: f.list_file.startswith(f"{r.date}_{r.pass_}"),axis=1)
    U.loc[m,"price"]=int(f.fliff_price); U.loc[m,"src"]="fliff"
# shots from NHL boxscores
shots={};fin={}
for b in glob.glob("nhl_api/box_*.json"):
    j=json.load(open(b)); gid=j["id"]; fin[gid]=j["gameState"] in("OFF","FINAL")
    for t in("awayTeam","homeTeam"):
        for g in("forwards","defense"):
            for p in j["playerByGameStats"][t][g]: shots[(p["playerId"],gid)]=p["sog"]
def grade(r):
    if not fin.get(r.gameId): return "pending",None
    y=shots.get((r.nhl_id,r.gameId))
    if y is None: return "void",None
    if y==r.line: return "push",y
    return ("W" if (y>r.line)==(r.side=="OVER") else "L"),y
U[["result","actual"]]=U.apply(lambda r: pd.Series(grade(r)),axis=1)
dec=lambda a:1+(a/100 if a>0 else 100/-a)
U["units"]=U.apply(lambda r:(dec(r.price)-1) if r.result=="W" else (-1.0 if r.result=="L" else 0.0),axis=1)
U["in_band"]=U.price>=-150
U.to_csv("my_graded_sides.csv",index=False)
G=U[U.result.isin(["W","L"])]
def rec(x): 
    w=(x.result=="W").sum(); l=(x.result=="L").sum()
    return f"{w}-{l} ({w/max(w+l,1):.1%}) {x.units.sum():+.2f}u n={len(x)}"
print("unique",len(U),"by date",U.date.value_counts().to_dict(),"results",U.result.value_counts().to_dict())
print("ALL",rec(G)); print("break-even (mean implied)", f"{(1/G.price.map(dec)).mean():.1%}", "| 1/mean dec", f"{1/G.price.map(dec).mean():.1%}")
for n,x in G.groupby("in_band"): print("in_band",n,rec(x))
for n,x in G.groupby("agrees_n"): print("agrees",n,rec(x))
for n,x in G.groupby("side"): print(n,rec(x))
for n,x in G.groupby("date"): print(n,rec(x))
for n,x in G.groupby("game"): print(n,rec(x))
