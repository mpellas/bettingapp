"""Enhancement #1 re-score: drop ONLY the promotion->UNDER role veto. Runs on the verified copy in nhl-sog_copy/."""
import sys,os,glob,re,json,csv,urllib.request
from datetime import datetime
HERE=os.path.dirname(os.path.abspath(__file__)); C=os.path.join(HERE,'nhl-sog_copy')
sys.path.insert(0,C); os.chdir(C)
import pandas as pd, build_sheet as bs
def passes():
    out=[]
    for g in sorted(glob.glob('picks/2026*_GATE*.csv')):
        b=os.path.basename(g); m=re.match(r'(\d{8})_D(_\d{4})?_GATE(_1512pass)?\.csv$',b)
        if not m or not('20261015'<=m[1]<='20261029'): continue
        p=f"picks/{m[1]}_D{m[2] or ''}{m[3] or ''}.csv"
        if os.path.exists(p): out.append((m[1],(m[2] or '')[1:] or ('1512' if m[3] else 'D'),p,g))
    return out
def nv_open(r):
    try:
        f=lambda a:(100/(a+100) if a>0 else -a/(-a+100)); o,u=f(float(r.over_open)),f(float(r.under_open)); return o/(o+u)
    except Exception: return None
def run(date,hh,pf,gf,drop):
    P=pd.read_csv(pf); G=pd.read_csv(gf)
    promo=(G.role_veto_under.astype(str)=='True')&(G.role_veto_over.astype(str)!='True')
    if drop: G.loc[promo,'role_veto_under']=False
    df=bs.build_rows(P,G,'',date)
    return df,G,promo
def go(window_passes, verbose=True):
    rows=[]
    for date,hh,pf,gf in window_passes:
        try:
            base,G,promo=run(date,hh,pf,gf,False); new,_,_=run(date,hh,pf,gf,True)
        except Exception as e:
            print('FAIL',gf,e); continue
        for _,g in G[promo].iterrows():
            k=(new.player==g.player)&(new.line==g.line)&(new.side=='UNDER')
            if not k.any(): continue
            n=new[k].iloc[0]; b=base[k].iloc[0]
            stale=''
            try:
                age=(datetime.fromisoformat(str(g.captured_utc))-datetime.fromisoformat(str(g.dfo_updated).replace('Z','+00:00'))).total_seconds()/3600; stale=age>12
            except Exception: pass
            no=nv_open(g); move=abs(g.nv_over-no)*100 if no is not None else None
            tally=n.get('agrees_n')
            blockers=[]
            if n.status not in('DK bet','Fliff check'): blockers.append('sheet:'+str(n.status_reason).split(';')[0])
            if pd.notna(tally) and int(tally)<=2: blockers.append(f'tally {int(tally)}/7')
            if stale is True: blockers.append('stale lineup >12h')
            if move is not None and move>=20: blockers.append(f'market move {move:.1f}')
            rows.append(dict(date=date,pass_id=f'{date}_{hh}',gameId=g.gameId,game=g.game,player=g.player,nhl_id=g.nhl_id,line=g.line,
              dk_price=n.dk_price,shop_at=n.fliff_shop_at,nv_under=round(1-g.nv_over,4),p_blend_under=round(1-g.p_blend_over,4),
              p_model_under=round(1-g.p_model_over,4),edge_model_pts=round((g.nv_over-g.p_model_over)*100,1),
              edge_blend_pts=round((g.nv_over-g.p_blend_over)*100,1),toi_rise=round(g.toi_r5-g.toi_r30,2),
              role_reason=g.role_reason,slot_veto=g.slot_veto,opp_slot_ratio=g.opp_slot_ratio,base_status=b.status,new_status=n.status,
              new_reason=n.status_reason,tally=tally,stale=stale,move_pts=None if move is None else round(move,1),
              makes_list=not blockers,blockers=' | '.join(blockers),captured_utc=g.captured_utc))
    return pd.DataFrame(rows)
if __name__=='__main__':
    d=go(passes()); d.to_csv(os.path.join(HERE,'raw_pass_rows.csv'),index=False); print(len(d))
