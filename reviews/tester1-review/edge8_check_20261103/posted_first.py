import re,glob,json,os,sys,collections
def shots(date):
    m={}
    for f in glob.glob('box/*.json'):
        d=json.load(open(f))
        if d['gameDate'].replace('-','')!=date or d['gameState'] not in ('OFF','FINAL'): continue
        for t in ('awayTeam','homeTeam'):
            for g in ('forwards','defense'):
                for p in d['playerByGameStats'][t][g]: m[p['name']['default'].split('. ')[-1].lower(),p['name']['default'][0]]=p.get('sog',0)
    return m
def pay(a): a=int(a); return a/100 if a>0 else 100/-a
RX=re.compile(r'^Fliff check: (.+?) (OVER|UNDER) ([\d.]+) \(DK ([+-]\d+).*model \+([\d.]+) pts')
if __name__!="__main__": raise SystemExit
mode=sys.argv[1]
rows={}
for f in sorted(glob.glob('in/picks/2026*_post.txt')):
    b=os.path.basename(f)[:-9]
    if not re.fullmatch(r'\d{8}_\d{4}',b): continue
    if mode=='marker' and not os.path.exists(f'in/picks/finalcall_done/{b}.txt'): continue
    for l in open(f):
        m=RX.match(l)
        if m: n,s,L,pr,e=m.groups(); rows.setdefault((b[:8],n,s,L),(pr,float(e)))  # last pass wins
agg=collections.defaultdict(lambda:[0,0,0.0,0]); miss=[]
cache={}
for (dte,n,s,L),(pr,e) in sorted(rows.items()):
    if not('20261017'<=dte<='20261102'): continue
    sh=cache.setdefault(dte,shots(dte)); k=(n.split(' ',1)[1].lower(),n[0])
    if k not in sh: miss.append((dte,n)); continue
    win=(sh[k]>float(L))==(s=='OVER')
    b='12+' if e>=12 else '8-12' if e>=8 else '5-8' if e>=5 else '<5'
    a=agg[b]; a[0]+=win; a[1]+=not win; a[2]+=pay(pr) if win else -1; a[3]+=1
print(mode,'n',sum(v[3] for v in agg.values()),'unresolved',miss)
for b,v in agg.items(): print(b,f'{v[0]}-{v[1]} {v[2]:+.1f}u')
