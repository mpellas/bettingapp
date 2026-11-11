import sys,json,glob,statistics,re
sys.path.insert(0,'/workspace/props-finder'); import find as F
sys.path.insert(0,'/workspace/props-finder/analysis/nov01')
import pandas as pd
PF='/workspace/props-finder'; PD='/workspace/nfl-props/data/predictions/2026_wk08/'
PULLS=[('20261101T1709','pregame_20261101T175833Z.csv'),('20261101T1956','pregame_20261101T175833Z.csv'),('20261102T0013','pregame_20261101T210053Z.csv')]
SHARPS={'pinnacle','fanduel'}; BET={'draftkings','fliff'}
MK={'player_pass_yds':'pass_yds','player_rush_yds':'rush_yds','player_reception_yds':'reception_yds'}
NICK={'joshua':'josh','jacob':'jake','matthew':'matt','michael':'mike','christopher':'chris','william':'will','robert':'rob','kenneth':'ken','nicholas':'nick','daniel':'dan','gabriel':'gabe','cameron':'cam','joseph':'joe'}
def nn(n):
    n=re.sub(r"[.'’\-]",' ',str(n).lower()); w=[x for x in n.split() if x not in ('jr','sr','ii','iii','iv','v')]
    if w: w[0]=NICK.get(w[0],w[0])
    return ' '.join(w)
inj=pd.read_csv(PF+'/analysis/nov01/all_sides_stage1.csv').drop_duplicates('player').set_index('player').injury.to_dict(); inj={nn(k):v for k,v in inj.items()}
rows=[]
for tag,mf in PULLS:
    M=pd.read_csv(PD+mf); M['nk']=M.player_display_name.map(nn); M['market']=M.market.replace({'rec_yds':'reception_yds'})
    TEAM=M.drop_duplicates('nk').set_index('nk').team.to_dict(); Mi={(r.nk,r.market):r for r in M.itertuples()}
    props,gm,ko={},{},{}
    for f in sorted(glob.glob(f'{PF}/raw/{tag}/*.json')):
        ev=json.load(open(f)); gm[ev['id']]=f"{ev['away_team']} @ {ev['home_team']}"; ko[ev['id']]=ev['commence_time']
        for b in ev['bookmakers']:
            for m in b['markets']:
                if m['key'] not in MK: continue
                for o in m['outcomes']:
                    if o.get('point') is None: continue
                    k=(ev['id'],nn(o['description']),MK[m['key']],float(o['point']))
                    if b['key'] in F.DFS: continue
                    props.setdefault(k,{}).setdefault(b['key'],{})[o['name']]=o['price']
    pull_utc=pd.Timestamp(tag,tz='UTC')
    for k,bk in props.items():
        two={b:s for b,s in bk.items() if 'Over' in s and 'Under' in s}
        eid,nk,mk,ln=k; r=Mi.get((nk,mk))
        for b in two:
            if b not in BET: continue
            others={x:s for x,s in two.items() if x!=b}
            nv=lambda s:F.imp(s['Over'])/(F.imp(s['Over'])+F.imp(s['Under']))
            fo_all=statistics.median(nv(s) for s in two.values())
            fo=statistics.median(nv(s) for s in others.values()) if others else None
            sh=sorted(x for x in others if x in SHARPS)
            for side in ('Over','Under'):
                pr=two[b][side]
                fp=None if fo is None else (fo if side=='Over' else 1-fo)
                fpa=fo_all if side=='Over' else 1-fo_all
                inu=r is not None and bool(r.in_model_universe); mp=None
                if inu:
                    mp=float(r.p_over_D) if side=='Over' else 1-float(r.p_over_D)
                    if not (ln<=r.line_D if side=='Over' else ln>=r.line_D): mp=0.0
                rows.append(dict(pull=tag,model_file=mf,event_id=eid,game=gm[eid],kickoff_utc=ko[eid],team=(r.team if r is not None else TEAM.get(nk,'')),player=nk,market=mk,line=ln,side=side,book=b,price=pr,
                  n_other_books=len(others),n_sharp_other=len(sh),sharps=','.join(sh),fair_excl=fp,ev_excl=None if fp is None else (fp*F.dec(pr)-1)*100,
                  fair_all=fpa,ev_all=(fpa*F.dec(pr)-1)*100,model_p=mp,in_model=inu,injury=inj.get(nk,'not listed')))
A=pd.DataFrame(rows); A.to_csv('all_sides_all_pulls.csv',index=False)
A=A[pd.to_datetime(A.pull,utc=True)<pd.to_datetime(A.kickoff_utc)]
A['pull_ts']=pd.to_datetime(A.pull,utc=True)
D=A.sort_values('pull_ts').groupby(['event_id','player','market','line','side','book']).tail(1).drop(columns='pull_ts')
D.to_csv('sides_deduped.csv',index=False); print('raw rows',len(rows),'deduped',len(D))
