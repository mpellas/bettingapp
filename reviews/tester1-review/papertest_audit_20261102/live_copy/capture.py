"""Idempotent capture of DraftKings (ESPN provider 100) NHL shots-on-goal + goalie saves props + DailyFaceoff lines/PP units.
Saves per game: D = latest capture while 150-210 min before puck drop; C snapshots taken 0-40 min before (archived).
Every snapshot -> captures/<date>/archive/<event>_<tag>_HHMMSS.json; <event>_<tag>.json = latest snapshot WITH lines
(a 0-line pull is archived but never overwrites a main file that has lines; see keep_main).
Graded close = per-line latest price 0-30 min out, pulled lines logged, never backfilled: see close.py -> <event>_CLOSE.json.
Prints 'NEXT_SLEEP <sec>' (180 if any game within 45 min, else 600). Exits fast when no upcoming games."""
import requests,json,os,re,sys,unicodedata,datetime as dt
import close
CORE='https://sports.core.api.espn.com/v2/sports/hockey/leagues/nhl'
SITE='https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard'
H={'User-Agent':'Mozilla/5.0'}
os.chdir(os.path.dirname(os.path.abspath(__file__))); os.makedirs('captures',exist_ok=True)
def j(u,**kw): return requests.get(u.replace('http:','https:'),headers=H,timeout=(10,20),**kw).json()
def load(f): return json.load(open(f)) if os.path.exists(f) else {}
ATH,IDM='captures/athletes.json','captures/idmap.json'; ath,idm=load(ATH),load(IDM)
def norm(s): return re.sub(r'[^a-z]','',unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().lower())
def athlete(ref):
    aid=ref.split('/athletes/')[1].split('?')[0]
    if aid not in ath:
        try: a=j(ref); ath[aid]={'name':a.get('displayName'),'pos':a.get('position',{}).get('abbreviation')}
        except Exception: return aid,{'name':None}
    return aid,ath[aid]
def nhl_id(aid,name,teams,pos=None):
    """ESPN athlete id -> NHL playerId via NHL public player search (name match; team tiebreak). Cached."""
    if aid in idm: return idm[aid]
    try:
        r=j('https://search.d3.nhle.com/api/v1/search/player',params={'culture':'en-us','limit':20,'q':name,'active':'true'})
        c=[x for x in r if norm(x['name'])==norm(name)]
        if len(c)>1: c=[x for x in c if x.get('teamAbbrev') in teams] or c
        if len(c)>1 and pos: c=[x for x in c if (x.get('positionCode')=='D')==(pos=='D')] or c
        idm[aid]=int(c[0]['playerId']) if len(c)==1 else None
    except Exception: return None
    return idm[aid]
def am2p(a): a=float(a); return -a/(-a+100) if a<0 else 100/(a+100)
def sides(items,TOT='Total Shots on Goal',MS='Shots on Goal Milestones'):
    """Pair Total SOG entries into over/under. Over = entry whose current price equals the over-only Milestone (ceil(line))+ price;
    fallback: listing order (first=over). order_matches is True ONLY when the side is confirmed by the milestone price; False for order_fallback."""
    by={}
    for p in items: by.setdefault(p['espn_id'],[]).append(p)
    out=[]
    for aid,ps in by.items():
        tot=[p for p in ps if p['type']==TOT]; ms={p['target']:p['american'] for p in ps if p['type']==MS}
        for line in sorted({p['line'] for p in tot}):
            pair=[p for p in tot if p['line']==line]
            if len(pair)!=2: continue
            k=float(line)+0.5; m=ms.get(k)
            if m is not None and (pair[0]['american']==m)!=(pair[1]['american']==m):
                ov,un=(pair[0],pair[1]) if pair[0]['american']==m else (pair[1],pair[0]); how='milestone'
            else: ov,un=pair; how='order_fallback'
            po,pu=am2p(ov['american']),am2p(un['american'])
            out.append({'espn_id':aid,'player':ov['player'],'nhl_id':ov.get('nhl_id'),'line':float(line),'over':ov['american'],'under':un['american'],
              'over_open':ov['american_open'],'under_open':un['american_open'],'nv_over':round(po/(po+pu),4),'side_method':how,'order_matches':how=='milestone'})
    return out
def dfo(team):
    slug=re.sub(r'[^a-z0-9]+','-',unicodedata.normalize('NFKD',team).encode('ascii','ignore').decode().lower()).strip('-')
    try:
        h=requests.get(f'https://www.dailyfaceoff.com/teams/{slug}/line-combinations',headers=H,timeout=(10,20)).text
        c=json.loads(re.search(r'__NEXT_DATA__" type="application/json">(.*?)</script>',h).group(1))['props']['pageProps']['combinations']
        return {'updatedAt':c.get('updatedAt'),'source':c.get('sourceName'),'players':[{k:p.get(k) for k in ['name','positionIdentifier','groupIdentifier','categoryIdentifier','injuryStatus','gameTimeDecision']} for p in c['players']]}
    except Exception as e: return {'error':str(e)}
def keep_main(fn,out):
    """Number of lines in the existing main file if this pull must NOT overwrite it (pull has 0 lines, main has >0); else 0."""
    if out.get('sog_lines'): return 0
    try: return len(json.load(open(fn)).get('sog_lines') or [])
    except Exception: return 0
TEST=len(sys.argv)>1 and sys.argv[1] in ('TEST','ADHOC')  # writes <event>_TEST.json for every upcoming game
now=dt.datetime.now(dt.timezone.utc); soonest=1e9
for day in sorted({(now+dt.timedelta(hours=h)).strftime('%Y%m%d') for h in (-8,0,8)}):
  for e in j(SITE,params={'dates':day}).get('events',[]):
    start=dt.datetime.fromisoformat(e['date'].replace('Z','+00:00')); mins=(start-now).total_seconds()/60
    if e['status']['type']['state']!='pre' or mins<0: continue
    soonest=min(soonest,mins)
    tag=sys.argv[1] if TEST else 'D' if 150<=mins<=210 else 'C' if mins<=40 else None
    if not tag: continue
    eid=e['id']; comp=e['competitions'][0]['competitors']
    teams={c['homeAway']:c['team'] for c in comp}; abbrs={t['abbreviation'] for t in teams.values()}|{ {'TB':'TBL','LA':'LAK','NJ':'NJD','SJ':'SJS','UTAH':'UTA'}.get(t['abbreviation'],t['abbreviation']) for t in teams.values()}
    raw=[]
    for p in j(f'{CORE}/events/{eid}/competitions/{eid}/odds/100/propBets',params={'limit':1000}).get('items',[]):
        if not ('Shots on Goal' in p['type']['name'] or p['type']['name'] in ('Total Saves','Goalkeeper Saves Milestones')) or 'athlete' not in p: continue
        aid,a=athlete(p['athlete']['$ref'])
        raw.append({'type':p['type']['name'],'espn_id':aid,'player':a.get('name'),'nhl_id':nhl_id(aid,a.get('name'),abbrs,a.get('pos')) if a.get('name') else None,
          'line':p['odds'].get('total',{}).get('value'),'target':p.get('current',{}).get('target',{}).get('value'),
          'american':p['odds']['american'].get('value'),'american_open':p['odds']['american'].get('open'),'lastUpdated':p.get('lastUpdated')})
    out={'event':eid,'name':e.get('name'),'home':teams['home']['displayName'],'away':teams['away']['displayName'],'start_utc':e['date'],
         'captured_utc':now.isoformat(),'tag':tag,'minutes_to_start':round(mins,1),'book':'DraftKings (ESPN provider 100)',
         'sog_lines':sides(raw),'saves_lines':sides(raw,'Total Saves','Goalkeeper Saves Milestones'),'raw':raw,'lineups':{t['displayName']:dfo(t['displayName']) for t in teams.values()}}
    d=f'captures/{start.strftime("%Y%m%d")}'; os.makedirs(d,exist_ok=True)
    fn=f'{d}/{eid}_{tag}.json'
    os.makedirs(f'{d}/archive',exist_ok=True)
    json.dump(out,open(f'{d}/archive/{eid}_{tag}_{now.strftime("%H%M%S")}.json','w'),indent=1)
    # Empty-pull guard (2026-10-17, BOS@LA 401892530: DK pulled all SOG lines ~13 min before puck drop and the empty pulls
    # overwrote the main C file). The empty pull is always archived above (the record); it only never replaces a main
    # <eid>_C/_D.json that has lines. Fewer-but-nonzero lines DO replace it: single lines get pulled for real (scratches),
    # and the main file is 'latest snapshot'. close.py builds the graded close from archive/ either way.
    prev=keep_main(fn,out)
    if prev: print(f'kept {fn}: this pull has 0 lines, main file keeps {prev} lines (empty pull archived only)')
    else: json.dump(out,open(fn,'w'),indent=1)  # latest snapshot only; the graded close is built per line from archive (close.py)
    if tag=='C':
        try: r=close.build(d,eid); print(f'close {eid}: in_window={r["n_in_window"]} closed={len(r["closed"])} pulled={len(r["pulled_before_close"])}')
        except Exception as ex: print(f'close build failed {eid}: {ex}')
    print(f'{"archived only (main kept)" if prev else "saved"} {d}/{eid}_{tag}.json {e.get("name")} {mins:.0f}min lines={len(out["sog_lines"])} saves={len(out["saves_lines"])}')
json.dump(ath,open(ATH,'w')); json.dump(idm,open(IDM,'w'))
# Land in the 0-30 close window ASAP: if the next drop is 30-60 min out, wake when it is 28 min out (not 180/600 later).
# Once any drop is <=30 min out, C snapshot ~every 4 min until puck drop (per-line close = latest in-window price).
nxt=max(30,int((soonest-28)*60)) if 30<soonest<=60 else (240 if 0<=soonest<=30 else 600)
print('NEXT_SLEEP',nxt, f'(next puck drop in {soonest:.0f} min)' if soonest<1e9 else '(no upcoming games)')
