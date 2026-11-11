"""Catch-up track grader (run_type=catchup, NOT posted, NOT bet). Picks = predict.py rows with pick set (blended EV>0)
from D snapshots captured before the outage cutoff, then the 5-pt model-edge floor (p_model - nv >= 0.05 on the pick side).
No shop_gate/DFO/evidence (those are live fetches; re-running now would be lookahead). Actuals: NHL stats API skater
summary (shots). Close: only a *_CLOSE.json capture within 30 min of puck drop, else 'no close' (excluded from CLV).
Does not import or modify grade.py/close.py."""
import pandas as pd,requests,glob,sys,json,os
rows=[]
def close_tag(cl,p):
    for c in cl:
        d=json.load(open(c)); t=d.get('captured_utc'); st=d.get('start_utc')
        if t and st and 0<=(pd.Timestamp(st)-pd.Timestamp(t)).total_seconds()<=1800 and d.get('lines'): return 'close '+t
    return 'no close'
for f in sorted(glob.glob('rebuilt/catchup/2026*_catchup.csv')):
    P=pd.read_csv(f); date=os.path.basename(f)[:8]; iso=f'{date[:4]}-{date[4:6]}-{date[6:]}'
    r=requests.get('https://api.nhle.com/stats/rest/en/skater/summary',params={'isAggregate':'false','isGame':'true','limit':-1,'cayenneExp':f'gameDate="{iso}" and gameTypeId=2'},timeout=60).json()['data']
    box={(x['playerId'],x['gameId']):x['shots'] for x in r}
    if date=='20261020': P=P[P.game.str.contains('Vegas')]  # TB@VGK only; others were posted live
    for _,p in P.iterrows():
        po=p.p_model_over; nv=p.nv_over
        if pd.notna(p.pick): side=p.pick; kind='DK list (blended EV>0)'
        elif abs(po-nv)>=0.05: side='OVER' if po>nv else 'UNDER'; kind='Fliff-check candidate (no Fliff price captured)'
        else: continue
        edge=(po-nv) if side=='OVER' else ((1-po)-(1-nv))
        price=p.over if side=='OVER' else p.under
        a=box.get((p.nhl_id,p.gameId)); res='VOID_dnp' if a is None else ('W' if (a>p.line)==(side=='OVER') else 'L')
        pr=int(str(price).replace('+','')); win=pr/100 if pr>0 else 100/-pr
        cl=[c for c in glob.glob(f'captures/*/{p.event}_CLOSE.json')]
        rows.append(dict(date=date,run_type='catchup',kind=kind,source_list=os.path.basename(f),player=p.player,game=p.game,side=side,line=p.line,
            dk_price_at_D=price,edge_pts=round(edge*100,1),floor='pass' if edge>=0.05 else 'below 5-pt floor (Skipped)',
            actual=a,result=res,units=(win if res=='W' else -1 if res=='L' else 0) if edge>=0.05 else None,
            close=close_tag(cl,p),
            src='lines: DK via ESPN D capture; actual: NHL stats API'))
O=pd.DataFrame(rows); O.to_csv('rebuilt/catchup/graded_catchup.csv',index=False); print(O.drop(columns=['src','game']).to_string() if len(O) else 'no rows')
