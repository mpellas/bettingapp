"""Pre-listing lineup/injury VETO for the shop list ONLY. Never changes model, leans, picks/<date>_<TAG>.csv or grading.
Usage: python3 shop_gate.py YYYYMMDD [TAG=D]  -> picks/<date>_<TAG>_GATE.csv (+ prints vetoed players)
Sources (free): DailyFaceoff line-combinations fetched live (injuryStatus, gameTimeDecision, EV line, PP unit),
ESPN NHL injuries endpoint (live), and the DFO lineup stored in the D snapshot as the baseline for line/PP moves.
Veto (shop_veto non-empty -> do NOT list the side) when the player is: out/IR/day-to-day/questionable/GTD (DFO or ESPN);
missing from today's DFO EV lineup; moved down an EV line vs the D snapshot or vs his recent slot (top-6 F now f3/f4);
off PP1 vs the D snapshot or vs his recent +PP1 slot;
role_change (role_check.py): history slot vs today's EV line / PP1. promotion -> role_veto_under, demotion -> role_veto_over
(side-specific, shop_ok unchanged), mixed -> both + shop_veto (shop_ok False). dk_listable_over/_under are per side. If DFO can't be fetched, 'gate_unverified' is set and the side is vetoed."""
import sys,re,json,glob,os,unicodedata,requests,pandas as pd
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from role_check import role_change
from lineup_age import stale_reason, stale_check   # 2026-11-03: 12h stale-lineup skip + last-game fallback
date=sys.argv[1]; TAG=sys.argv[2] if len(sys.argv)>2 else 'D'; H={'User-Agent':'Mozilla/5.0'}
norm=lambda s:re.sub(r'[^a-z]','',unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().lower())
def dfo(team):
    slug=re.sub(r'[^a-z0-9]+','-',unicodedata.normalize('NFKD',team).encode('ascii','ignore').decode().lower()).strip('-')
    try:
        h=requests.get(f'https://www.dailyfaceoff.com/teams/{slug}/line-combinations',headers=H,timeout=(10,20)).text
        c=json.loads(re.search(r'__NEXT_DATA__" type="application/json">(.*?)</script>',h).group(1))['props']['pageProps']['combinations']
        return {'updatedAt':c.get('updatedAt'),'players':c['players']}
    except Exception as e: return {'error':str(e)}
def index(lu):  # name -> {ev group, pp group, injury, gtd}
    out={}
    for p in (lu or {}).get('players',[]):
        r=out.setdefault(norm(p['name']),{'ev':None,'pp':None,'inj':None,'gtd':False})
        if p.get('categoryIdentifier')=='ev': r['ev']=p.get('groupIdentifier')
        if p.get('categoryIdentifier')=='pp': r['pp']=p.get('groupIdentifier')
        if p.get('injuryStatus'): r['inj']=p['injuryStatus']
        r['gtd']|=bool(p.get('gameTimeDecision'))
    return out
rank=lambda g:int(g[1:]) if g and g[0] in 'fd' and g[1:].isdigit() else None
P=pd.read_csv(f'picks/{date}_{TAG}.csv',dtype={'over':str,'under':str})
esp={}
try:
    for t in requests.get('https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/injuries',headers=H,timeout=20).json()['injuries']:
        for i in t['injuries']: esp[norm(i['athlete']['displayName'])]=i.get('status')
except Exception as e: print('ESPN injuries unavailable:',e)
base,live={},{}
for ev in P.event.unique():
    f=sorted(glob.glob(f'captures/*/{ev}_D.json')); d=json.load(open(f[-1])) if f else {}
    for t,lu in d.get('lineups',{}).items():
        base[t]=index(lu)
        if t not in live: live[t]=dfo(t)
liveidx={t:index(v) for t,v in live.items() if 'error' not in v}
rows=[]
for _,r in P.iterrows():
    n=norm(r.player); bt=[t for t in base if n in base[t]] or [t for t in liveidx if n in liveidx[t]]
    t=bt[0] if bt else None; b=base.get(t,{}).get(n,{}); L=liveidx.get(t,{}).get(n) if t else None
    v=[]
    if t is None or t not in liveidx: v.append('gate_unverified')
    elif L is None or (L['ev'] is None and not L['inj']): v.append('not_in_lineup')
    if L and L['inj']: v.append('dfo_'+L['inj'])
    if L and L['gtd']: v.append('gtd')
    if esp.get(n): v.append('espn_'+esp[n].replace(' ','_').lower())
    dv,dtxt=[],[]   # older lineup demotion signals -> veto the OVER only (side-specific, not shop_ok)
    if L and L['ev']:
        if rank(b.get('ev')) and rank(L['ev'])>rank(b['ev']): dv.append(f"line_down_{b['ev']}->{L['ev']}"); dtxt.append(f"lineup: line moved down {b['ev']}->{L['ev']}")
        if str(r.slot).startswith('F_top6') and L['ev'] in ('f3','f4'): dv.append(f"below_recent_top6_{L['ev']}"); dtxt.append(f"lineup: below recent top-6, today {L['ev']}")
        if (b.get('pp')=='pp1' or '+PP1' in str(r.slot)) and L['pp']!='pp1': dv.append(f"off_pp1_now_{L['pp']}"); dtxt.append(f"lineup: off PP1, today {L['pp'] or 'no_pp'}")
    rk,rvo,rvu,rr=role_change(r.slot,L and L['ev'],L and L['pp'])   # history slot vs today's lineup (directional)
    kind=rk
    if dv: kind='mixed' if rk in ('promotion','mixed') else 'demotion'   # older demotion + role promotion -> mixed
    rvo=kind in ('demotion','mixed'); rvu=kind in ('promotion','mixed')
    parts=dtxt+([rr] if rr else [])
    reason=('mixed: ' if kind=='mixed' and rk!='mixed' else '')+'; '.join(parts)
    if kind=='mixed': v.append(reason)                                 # mixed -> both sides vetoed (shop_ok False)
    lst,lsrc=stale_check(live.get(t,{}).get('updatedAt'),t,r.gameId,r.nhl_id,bool(L and L['ev'])) if t in liveidx else ('','')   # 2026-11-03: DFO >12h old -> last-game NHL.com fallback (user-approved), else skip
    if lst: v.append(lst)
    rows.append(dict(r,team_dfo=t,ev_base=b.get('ev'),pp_base=b.get('pp'),ev_now=L and L['ev'],pp_now=L and L['pp'],
        dfo_updated=live.get(t,{}).get('updatedAt'),lineup_stale=lst,lineup_source=lsrc,espn_status=esp.get(n),role_mismatch=bool(rk),role_change=kind,role_veto_over=rvo,role_veto_under=rvu,role_reason=reason,lineup_veto_over=';'.join(dv),shop_veto=';'.join(v)))
G=pd.DataFrame(rows)
G['shop_ok']=G.shop_veto==''                      # no BOTH-SIDES veto (injury/status/not in lineup/unverified/mixed role); side vetoes in role_veto_*
G['dk_ev_ok']=G.pick.fillna('')!=''               # model lean beats DraftKings (frozen model's pick column)
G['dk_listable_over']=G.shop_ok&(G.pick=='OVER')&~G.role_veto_over     # per side: lean on that side, line not vetoed,
G['dk_listable_under']=G.shop_ok&(G.pick=='UNDER')&~G.role_veto_under  # and side not role-vetoed
G['dk_listable']=G.dk_listable_over|G.dk_listable_under                 # the side with positive EV is listable
out=f'picks/{date}_{TAG}_GATE.csv'; G.to_csv(out,index=False)
print(out,len(G),'lines;',(G.shop_veto!='').sum(),'vetoed;',(G.pick.fillna('')!='').sum(),'leans;',G.shop_ok.sum(),'pass veto;',G.dk_listable.sum(),'DK-listable')
print(G[G.shop_veto!=''][['player','game','line','slot','ev_base','ev_now','pp_base','pp_now','pick','shop_veto']].to_string(index=False))
R=G[G.role_change!='']
print('role_change:',R.role_change.value_counts().to_dict())
if len(R): print(R[['player','line','slot','ev_now','pp_now','pick','role_veto_over','role_veto_under','role_reason']].to_string(index=False))
