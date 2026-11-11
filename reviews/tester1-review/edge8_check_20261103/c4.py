import re,glob,os,csv,json,datetime as dt
RX=re.compile(r'^Fliff check: (.+?) (OVER|UNDER) ([\d.]+) \(DK ([+-]\d+).*model \+([\d.]+) pts')
rows={}
for f in sorted(glob.glob('in/picks/2026*_post.txt')):
    b=os.path.basename(f)[:-9]
    if not re.fullmatch(r'\d{8}_\d{4}',b): continue
    for l in open(f):
        m=RX.match(l)
        if m: rows[(b[:8],)+m.groups()[:3]]=(b,float(m.group(5)))
ages=[];noclose=0;n8=0;books=set()
for (d,n,s,L),(b,e) in rows.items():
    if not '20261017'<=d<='20261102': continue
    fn=f'in/picks/{d}_D_{b[9:]}.csv'
    if os.path.exists(fn):
        for r in csv.DictReader(open(fn)):
            if r['player']==n and r['line']==L:
                cap=dt.datetime.fromisoformat(r['captured_utc']); pt=dt.datetime.strptime(b,'%Y%m%d_%H%M').replace(tzinfo=dt.timezone(dt.timedelta(hours=-7 if d<'20261101' else -8)))
                ages.append(round((pt-cap).total_seconds()/60,1)); ev=r['event']; break
        else: ev=None
    else: ev=None
    if e>=8:
        n8+=1; ok=False
        for cf in glob.glob(f'in/captures/{d}/{ev}_C*.json') if ev else []:
            try: c=json.load(open(cf))
            except: continue
            books.add(c.get('book'))
            if any(x['player']==n and str(x['line'])==L for x in c.get('sog_lines',[])): ok=True
        noclose+=not ok
print('ages n',len(ages),'min',min(ages),'max',max(ages),'8+ posted',n8,'no close',noclose,'books',books)
