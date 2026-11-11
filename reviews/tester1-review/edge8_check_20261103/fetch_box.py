import csv,glob,json,os,urllib.request,time
g=set()
for f in glob.glob('in/picks/2026*_D*.csv'):
    for r in csv.DictReader(open(f)):
        if r.get('gameId'): g.add(r['gameId'])
for gid in sorted(g):
    fn=f'box/{gid}.json'
    if os.path.exists(fn): continue
    try:
        d=urllib.request.urlopen(urllib.request.Request(f'https://api-web.nhle.com/v1/gamecenter/{gid}/boxscore',headers={'User-Agent':'Mozilla/5.0'}),timeout=20).read()
        open(fn,'wb').write(d)
    except Exception as e: print(gid,e)
    time.sleep(0.2)
print(len(g))
