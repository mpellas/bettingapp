import csv,glob,json,subprocess,unicodedata,math
from collections import defaultdict
import openpyxl
N='/workspace/nhl-sog/'
g=[x for x in csv.DictReader(open(N+'majority/graded_sides.csv')) if x['result'] in('W','L')]
print('decided',len(g))
# sig_opp + team from sheets
sig={};team={}
for x in g:
    for f in glob.glob(N+f"sheets/{x['list_id'].replace('_','_D_',1)}_picks.xlsx"):
        pass
cache={}
def sheet(lid):
    if lid not in cache:
        f=N+'sheets/'+lid.replace('_','_D_',1)+'_picks.xlsx'
        ws=openpyxl.load_workbook(f,read_only=True)['Picks']
        cache[lid]={(r[2],r[3],float(r[4])):r for r in list(ws.iter_rows(values_only=True))[1:]}
    return cache[lid]
def gate(lid):
    f=N+'picks/'+lid.replace('_','_D_',1)+'_GATE.csv'
    return {r['player']:r['team_dfo'] for r in csv.DictReader(open(f))}
gc={}
for x in g:
    r=sheet(x['list_id']).get((x['player'],x['side'],float(x['line'])))
    x['sig_opp']=r[37] if r else None
    if x['list_id'] not in gc: gc[x['list_id']]=gate(x['list_id'])
    x['team']=gc[x['list_id']].get(x['player'])
print('missing sig',sum(x['sig_opp'] is None for x in g),'missing team',sum(not x['team'] for x in g))
# own team game logs from NHL schedule+boxscores
def get(u): return json.loads(subprocess.run(['curl','-s','-A','Mozilla/5.0',u],capture_output=True,text=True).stdout)
games={}
import datetime
d=datetime.date(2026,10,1)
while d<=datetime.date(2026,11,10):
    s=get(f'https://api-web.nhle.com/v1/score/{d}')
    for gm in s.get('games',[]):
        if gm.get('gameType')==2 and gm.get('gameState') in('OFF','FINAL'):
            games[gm['id']]=(str(d),gm['awayTeam'],gm['homeTeam'])
    d+=datetime.timedelta(days=1)
json.dump({k:v for k,v in games.items()},open('games.json','w'))
print('games',len(games))
print('sample',list(games.values())[0][1].keys())
def fold(s): return unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode()
log=[]  # date, team_fullname, sf, sa
for gid,(dt,a,h) in games.items():
    an=fold(a['name']['default']) ; hn=fold(h['name']['default'])
    log.append((dt,a.get('abbrev'),a.get('sog'),h.get('sog'),gid)); log.append((dt,h.get('abbrev'),h.get('sog'),a.get('sog'),gid))
print('null sog',sum(l[2] is None for l in log))
# map full names to abbrev via gameId of graded side
ab={}
for gid,(dt,a,h) in games.items():
    for t in (a,h):
        ab[fold(t.get('placeName',{}).get('default','')+' '+t.get('commonName',{}).get('default',''))]=t['abbrev']
def pre(abv,dt,i):
    v=[l[i] for l in log if l[1]==abv and l[0]<dt and l[i] is not None]; return sum(v)/len(v) if v else None
def lg(dt):
    v=[l[2] for l in log if l[0]<dt and l[2] is not None]; return sum(v)/len(v)
gm={str(k):v for k,v in games.items()}
def rec(xs):
    w=sum(x['result']=='W' for x in xs);u=sum(float(x['units']) for x in xs);return f"{w}-{len(xs)-w} {u:+.2f}u"
for x in g:
    dt=f"{x['date'][:4]}-{x['date'][4:6]}-{x['date'][6:]}"
    ent=gm.get(x['gameId'])
    if not ent: 
        sc=get(f"https://api-web.nhle.com/v1/gamecenter/{x['gameId']}/boxscore"); a,h=sc['awayTeam'],sc['homeTeam']
    else: a,h=ent[1],ent[2]
    t=x['team'] or ''
    mine=None
    for side in (a,h):
        nm=fold((side.get('name') or {}).get('default','') or (side.get('commonName') or {}).get('default',''))
        if nm and nm.split()[-1] in fold(t): mine=side
    if mine is None: mine = h if x['player']=='Nick Robertson' else None
    opp = h if mine is a else a
    x['opp_sa']=pre(opp['abbrev'],dt,3); x['own_sf']=pre(mine['abbrev'],dt,2); x['lg']=lg(dt)
ov=sorted([x for x in g if x['side']=='OVER'],key=lambda x:x['opp_sa'])
n=len(ov);k=[ov[:round(n/3)],ov[round(n/3):round(2*n/3)],ov[round(2*n/3):]]
for nm,b in zip(['stingy','mid','generous'],k): print('overs',nm,round(b[0]['opp_sa'],2),round(b[-1]['opp_sa'],2),rec(b))
for s in '+-0': print('all sig_opp',s,rec([x for x in g if x['sig_opp']==s])); print(' overs',s,rec([x for x in ov if x['sig_opp']==s]))
for x in g:
    p=(x['own_sf']+x['opp_sa'])/2; d='OVER' if p>x['lg'] else 'UNDER'; x['with']=d==x['side']
print('proj with',rec([x for x in g if x['with']]),'against',rec([x for x in g if not x['with']]))
