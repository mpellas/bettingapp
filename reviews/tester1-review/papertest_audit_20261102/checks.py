import json,csv,datetime as dt,zoneinfo,re,collections
Z=zoneinfo.ZoneInfo('America/Los_Angeles'); S='src_copy/'
sch=json.load(open('nhl_schedule_20261102.json'))['gameWeek'][0]['games']
drop={str(g['id']):dt.datetime.fromisoformat(g['startTimeUTC'].replace('Z','+00:00')).astimezone(Z) for g in sch}
abbr={str(g['id']):f"{g['awayTeam']['abbrev']}@{g['homeTeam']['abbrev']}" for g in sch}
def pt(s):
    s=s.strip().replace(' PT','')
    for f in ('%Y-%m-%d %H:%M:%S','%Y-%m-%d %H:%M'):
        try: return dt.datetime.strptime(s,f).replace(tzinfo=Z)
        except: pass
viol=[];unm=[];n=0
def chk(file,line,gid,ts,label):
    global n; n+=1
    if gid not in drop: unm.append((file,line,gid,label)); return
    t=pt(ts)
    if t is None: unm.append((file,line,gid,label+' unparseable ts '+ts)); return
    m=(drop[gid]-t).total_seconds()/60
    if m<=0: viol.append((file,line,gid,label,ts,round(m,1)))
    return m
for fn,tcol in [('challenger_picks.csv','logged_pt'),('lineup_repull_log.csv','run_pt')]:
    for i,r in enumerate(csv.DictReader(open(S+fn)),start=2):
        m=chk(fn,i,r['gameId'],r[tcol],tcol)
        if fn.startswith('chal') and abs(m-float(r['mins_to_drop']))>0.15: print('mins_to_drop mismatch',fn,i,m,r['mins_to_drop'])
# social: handle shifted reddit rows
rows=list(csv.reader(open(S+'social_log.csv')));hdr=rows[0]
for i,r in enumerate(rows[1:],start=2):
    if r[1]=='x': gid,src,auth,tp,run=r[0],r[1],r[2],r[3],r[8]
    else: # shifted: run_pt,gameId,source,author,time_pt,url,text,...
        run,gid,src,auth,tp=r[0],r[1],r[2],r[3],r[4]; print(f'social_log.csv line {i}: column-shifted {src} row (run_pt in gameId col); post time "{tp}" has no tz label')
    chk('social_log.csv',i,gid,tp,f'{src} post time ({auth})'); chk('social_log.csv',i,gid,run,'run_pt')
# x_calls: map notes to games
for i,r in enumerate(csv.DictReader(open(S+'x_calls.csv')),start=2):
    gs=[g for g,a in abbr.items() if a.replace('SJS','SJ') in r['note'].replace('SJS','SJ') or a in r['note']]
    for g in gs: chk('x_calls.csv',i,g,r['run_pt'],'x call')
    if not gs: unm.append(('x_calls.csv',i,'?',r['note'][:40]))
print('drops',{abbr[k]:v.strftime('%H:%M PT') for k,v in drop.items()})
print('entries checked',n,'violations',viol,'unmatched',unm)
# D band
bad=[]
for i,r in enumerate(csv.DictReader(open(S+'challenger_picks.csv')),start=2):
    p=int(r['dk_price'].replace('+',''))
    ok=(-150<=p<=-100) or (100<=p<=110)
    if not ok: bad.append((i,r['player'],p))
print('D picks',i-1,'out of band',bad)
# E
X=list(csv.DictReader(open(S+'x_calls.csv')))
print('x rows',len(X),'sum calls',sum(int(r['calls']) for r in X),'by utc day',dict(collections.Counter({}) ) )
byday=collections.defaultdict(int)
for r in X: byday[r['x_day_utc']]+=int(r['calls'])
print('by x_day_utc',dict(byday),'logged day_total last per day',{r['x_day_utc']:r['day_total'] for r in X})
