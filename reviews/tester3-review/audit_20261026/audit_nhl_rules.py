"""Tester3 Oct 26 audit, section 4: re-run NHL card gates from raw GATE csv + sheets + post files. Read-only."""
import glob, re, math, os, pandas as pd, numpy as np
from zoneinfo import ZoneInfo
PT=ZoneInfo('America/Los_Angeles'); R='/workspace/nhl-sog'
HUGE_MOVE=float(os.environ.get('HUGE_MOVE','5.0'))  # pts; threshold NOT codified in repo -> parameter
import sys; sys.path.insert(0,R); import game_starts
logs=pd.read_pickle(f'{R}/data/s2026.pkl')
def pois_cdf(k,mu): return sum(math.exp(-mu)*mu**i/math.factorial(i) for i in range(int(k)+1)) if k>=0 else 0.0
def shop_at(p):
    d=1/p
    return int(math.ceil(100*(d-1)-1e-9)) if d>=2 else -int(math.floor(100/(d-1)+1e-9))
def season_toi(pid,iso):
    g=logs[(logs.playerId==pid)&(logs.gameDate<iso)&(logs.gameDate>=iso[:4]+'-09-01')]
    return (g.timeOnIcePerGame.mean()/60, len(g))
rows=[]
for sh in sorted(glob.glob(f'{R}/sheets/202610*_D_*picks.xlsx')):
    b=os.path.basename(sh); m=re.match(r'(\d{8})_D_(?:(\d{4})_)?picks',b); date,hh=m.group(1),m.group(2)
    if not('20261017'<=date<='20261025'): continue
    tag=f'D_{hh}' if hh else 'D'
    gp=f'{R}/picks/{date}_{tag}_GATE.csv'; post=f'{R}/picks/{date}_{hh}_post.txt' if hh else f'{R}/picks/{date}_post.txt'
    G=pd.read_csv(gp,dtype={'over':str,'under':str}) if os.path.exists(gp) else None
    posted=set()
    if os.path.exists(post):
        for l in open(post):
            mm=re.match(r'Fliff check: (.+?) (OVER|UNDER) ([\d.]+) ',l)
            if mm: posted.add((mm.group(1),mm.group(2),float(mm.group(3))))
    S=pd.read_excel(sh,'Picks'); iso=f'{date[:4]}-{date[4:6]}-{date[6:]}'
    floor_on = (date,hh or '0000')>=('20261020','1513')
    toi_on = (date,hh or '0000')>=('20261020','1406')
    move_rule = date>='20261024'
    for _,s in S.iterrows():
        side=s.side; o=side=='OVER'; L=float(s.line)
        g=None
        if G is not None:
            gg=G[(G.player==s.player)&(G.line.astype(float)==L)]
            g=gg.iloc[0] if len(gg) else None
        edge=s.p_model-s.p_novig
        # model/sheet probabilities are side-oriented in sheet
        pt=None
        if g is not None:
            st0=game_starts.starts_for([int(g.gameId)]).get(int(g.gameId))
            if st0 is not None: pt=pd.Timestamp(st0).tz_convert(PT)
        if pt is None:
            mm2=re.match(r'\s*(\d{1,2}:\d\d [AP]M)',str(s.puck_drop_pt))
            pt=pd.Timestamp(iso+' '+mm2.group(1)).tz_localize(PT) if mm2 else None
        cap=pd.Timestamp(g.captured_utc).tz_convert(PT) if g is not None else None
        mins=(pt-cap).total_seconds()/60 if (cap is not None and pt is not None) else np.nan
        win = 'n/a' if np.isnan(mins) else ('pass' if 150<=mins<=210 else ('pass(210-240 ext)' if 210<mins<=240 else 'FAIL'))
        noon='n/a' if pt is None else ('FAIL' if pt.hour<12 else 'pass')
        # recent form recomputed from GATE raw
        if g is not None:
            mu=g.sog60_r10*g.toi_r5/60; nvs=g.nv_over if o else 1-g.nv_over
            pr=(1-pois_cdf(math.floor(L),mu)) if o else pois_cdf(math.ceil(L)-1,mu)
            rec='pass' if pr>nvs else 'FAIL'
            st,n=season_toi(int(g.nhl_id),iso); d=g.toi_r5-st if n>=5 else np.nan
            toi_vote='0' if (n<5 or abs(d)<1.0) else (('+' if (d>0)==o else '-'))
            rvx=g.get('role_veto_over' if o else 'role_veto_under'); rv = (str(rvx)=='True') if rvx is not None else False
            veto = isinstance(g.get('shop_veto'),str) and isinstance(g.shop_veto,str) and g.shop_veto.strip()!=''
            pm_raw = g.p_model_over if o else 1-g.p_model_over
            blend=0.95*nvs+0.05*pm_raw; sa=shop_at(blend)
        else: pr=mu=np.nan; rec='n/a'; toi_vote='n/a'; d=np.nan; rv=False; veto=False; sa=None; n=0
        mv=re.search(r'no-vig moved ([\d.]+) pts (toward|away)',str(s.evidence_summary))
        mvp=float(mv.group(1)) if mv else 0.0; toward = bool(mv and mv.group(2)=='toward')
        agrees=int(s.agrees_n) if not pd.isna(s.agrees_n) else np.nan
        agrees_rule = agrees - (1 if (move_rule and toward and mvp>=HUGE_MOVE and s.sig_move=='+') else 0)
        posted_flag=(s.player,side,L) in posted
        # rule outcome: list if passes everything and was sheet-eligible
        fails=[]
        if win=='FAIL': fails.append('window')
        if noon=='FAIL': fails.append('noon')
        if floor_on and edge<0.05-1e-12: fails.append('floor')
        if rec=='FAIL': fails.append('recent')
        if rv: fails.append('role_veto')
        if veto: fails.append('shop_veto')
        if not pd.isna(agrees_rule) and agrees_rule<=2: fails.append('agree<=2')
        if edge<=0: fails.append('no_model_edge')
        sheet_list = s.status=='Fliff check'
        rule_list = sheet_list and not fails   # top-5 cap & other sheet-only flags taken from sheet
        near = (not sheet_list) and edge>=0.03 and rec!='FAIL' and not rv and not veto
        if not (posted_flag or sheet_list or near): continue
        reasons=[]; 
        if posted_flag!=rule_list:
            reasons.append(('posted but rule says skip: ' if posted_flag else 'rule says list but not posted: ')+','.join(fails or ['(sheet/top-5)']))
        if rec!='n/a' and (rec=='pass')!=(s.flag_recent_pass=='yes'): reasons.append(f'recent flag differs (sheet {s.flag_recent_pass}, recomputed {rec})')
        if sa is not None and sa!=int(s.fliff_shop_at): reasons.append(f'shop-at differs (sheet {int(s.fliff_shop_at):+d}, recomputed {sa:+d})')
        if toi_on and toi_vote not in ('n/a',) and toi_vote!=str(s.sig_toi): reasons.append(f'TOI vote differs (sheet {s.sig_toi}, recomputed {toi_vote}; using GATE toi_r5, sheet may use fresh_toi_r5)')
        rows.append(dict(date=date,pass_=hh or 'morning',player=s.player,side=side,line=L,game=s.game,puck=pt.strftime('%H:%M') if pt is not None else '',
            captured_pt=cap.strftime('%H:%M') if cap is not None else '',mins_before=round(mins,1),window=win,noon=noon,
            edge_pts=round(edge*100,1),floor=('pass' if edge>=0.05-1e-12 else 'FAIL') if floor_on else 'pre-floor',
            p_recent=round(pr,3) if not pd.isna(pr) else '',nv=round(s.p_novig,3),recent=rec,toi_season_n=n,toi_gap=round(d,2) if not pd.isna(d) else '',
            toi_vote=toi_vote,sheet_toi=s.sig_toi,agrees=agrees,move_pts=mvp if toward else -mvp,agrees_rule=agrees_rule,
            role_veto=rv,shop_veto=veto,shop_at_sheet=int(s.fliff_shop_at),shop_at_recomp=sa,sheet_status=s.status,
            posted=posted_flag,rule_list=rule_list,near_miss=near,mismatch=bool(reasons),reason='; '.join(reasons)))
D=pd.DataFrame(rows)
# classification
skips={('20261020','Kasperi Kapanen'),('20261020','Mackie Samoskevich'),('20261024','Barrett Hayton'),('20261024','Matt Coronato'),
 ('20261024','Vince Dunn'),('20261024','Mattias Samuelsson'),('20261024','Darren Raddysh')}
def cls(r):
    if not r.posted: return ''
    if r.date=='20261025': return 'skipped (Oct 25 NO BETS)'
    return 'skipped (tester)' if (r.date,r.player) in skips else 'final-card'
D['card_class']=D.apply(cls,axis=1)
D.to_csv('gates_table.csv',index=False)
P=D[D.posted]
print('rows',len(D),'posted',len(P),'sheet Fliff check',(D.sheet_status=='Fliff check').sum(),'near-miss',D.near_miss.sum(),'mismatch',D.mismatch.sum())
print(P.groupby('date').size().to_dict()); print(P.card_class.value_counts().to_dict())
print(D[D.mismatch][['date','pass_','player','side','line','posted','rule_list','reason']].to_string())
