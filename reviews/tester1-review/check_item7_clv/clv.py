import csv,json,glob,os,datetime as dt
def ip(a):
    a=int(a); return 100/(a+100) if a>0 else -a/(-a+100)
ab={'VAN':'Vancouver','NYR':'Rangers','TB':'Tampa','SEA':'Seattle','PHI':'Philadelphia','UTA':'Utah','EDM':'Edmonton','CGY':'Calgary','VGK':'Vegas','PIT':'Pittsburgh','COL':'Colorado','CAR':'Carolina','WPG':'Winnipeg','FLA':'Florida','STL':'St. Louis','NSH':'Nashville','BOS':'Boston','LA':'Los Angeles','CBJ':'Columbus','MIN':'Minnesota','ANA':'Anaheim','DET':'Detroit','DAL':'Dallas','WSH':'Washington','NJ':'New Jersey','SJ':'San Jose','BUF':'Buffalo','TOR':'Toronto','MTL':'Montreal','OTT':'Ottawa','NYI':'Islanders','CHI':'Chicago'}
import unicodedata
def norm(s): return unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower().replace('.','').replace('-',' ')
rows=[r for r in csv.DictReader(open('bets.csv')) if r['sport']=='nhl' and r['market']=='sog' and '2026-10-11'<=r['date']<='2026-10-24']
print(len(rows))
out=[]
for r in rows:
    d=dt.date.fromisoformat(r['date']); a,h=[x.strip() for x in r['game'].split('@')]
    cands=[]
    for day in (d,d+dt.timedelta(1)):
        for f in glob.glob(f'captures/{day:%Y%m%d}/*_CLOSE.json'):
            j=json.load(open(f))
            if ab[a] in j['name'] and ab[h] in j['name']: cands.append((f,j))
    hit=None;note=''
    if not cands: note='NO CLOSE FILE'
    for f,j in cands:
        for l in j['closed']:
            if norm(l['player']).split()[-1]==norm(r['player']).split()[-1] and float(l['line'])==float(r['line']):
                hit=(f,l)
        if not hit:
            same=[ (l['player'],l['line']) for l in j['closed'] if norm(l['player']).split()[-1]==norm(r['player']).split()[-1]]
            note=f'{f}: player lines {same}'
    if hit:
        f,l=hit; o,u=ip(l['over']),ip(l['under']); nv=(o/(o+u)) if r['side']=='over' else u/(o+u)
        cp=l[r['side']]; b=ip(r['price']); c=ip(cp)
        out.append((r,f,cp,round(100*(c-b),2),round(100*(nv-b),2)))
        print(r['date'],r['player'],r['side'],r['line'],r['book'],r['price'],'close',cp,'rawpts',round(100*(c-b),2),'nvpts',round(100*(nv-b),2),os.path.basename(f))
    else: print('MISSING',r['date'],r['player'],r['line'],r['side'],r['book'],note)
import statistics as S
for bk in ('draftkings','fliff',None):
    xs=[x for x in out if bk is None or x[0]['book']==bk]
    for k,name in ((3,'raw'),(4,'nv')):
        v=[x[k] for x in xs]; print(bk,name,len(v),'beat',sum(t>0.05 for t in v),'match',sum(abs(t)<=0.05 for t in v),'worse',sum(t<-0.05 for t in v),'avg',round(S.mean(v),2))
