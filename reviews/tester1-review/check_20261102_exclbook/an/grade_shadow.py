import json,glob,re,csv,unicodedata
box={}
anywhere={}
abmap={'WSH':'WAS','LAR':'LA'}
def norm(s):
    s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()
    s=re.sub(r"[.'\-]"," ",s); s=re.sub(r"\b(jr|sr|ii|iii|iv)\b","",s)
    return re.sub(r"\s+"," ",s).strip()
for f in glob.glob('box/*.json'):
    d=json.load(open(f))
    for t in d['boxscore'].get('players',[]):
        ab=abmap.get(t['team']['abbreviation'],t['team']['abbreviation'])
        for s in t['statistics']:
            for a in s['athletes']:
                n=norm(a['athlete']['displayName']); st=dict(zip(s['keys'],a['stats']))
                r=box.setdefault((ab,n),{}); anywhere[(ab,n)]=a['athlete']['displayName']
                k={'passing':('pass_yds','passingYards'),'rushing':('rush_yds','rushingYards'),'receiving':('reception_yds','receivingYards')}.get(s['name'])
                if k: r[k[0]]=float(st[k[1]])
def find(team,player):
    p=norm(player)
    if (team,p) in box: return (team,p)
    cands=[k for k in box if k[0]==team and (k[1].replace(' ','')==p.replace(' ','') or (k[1].split()[-1]==p.split()[-1] and k[1][0]==p[0]))]
    return cands[0] if len(cands)==1 else None
def payout(price): return 100/abs(price) if price<0 else price/100
def be(price): return abs(price)/(abs(price)+100) if price<0 else 100/(price+100)
out=[]
for f in sorted(glob.glob('shadow_modelled_*.csv')):
    for r in csv.DictReader(open(f)):
        k=find(r['team'],r['player']); line=float(r['line']); pr=float(r['price'])
        if k is None: res,act='void',''
        else:
            act=box[k].get(r['market'],0.0)
            if act==line: res='push'
            else: res='win' if (act>line)==(r['side']=='Over') else 'loss'
        u={'win':payout(pr),'loss':-1.0}.get(res,0.0)
        mp=float(r['model_p']); b='55-60' if mp<.60 else '60-65' if mp<.65 else '65+'
        out.append(dict(grade_date='2026-11-01',slate_date='2026-11-01',file=f,game=r['game'],team=r['team'],player=r['player'],market=r['market'],line=line,side=r['side'],book=r['book'],price=pr,model_p=mp,prob_bucket=b,breakeven=round(be(pr),4),actual=act,result=res,units=round(u,4),graded_at='2026-11-01T22:40-08:00'))
json.dump(out,open('/tmp/graded.json','w'))
for o in out:
    if o['result']=='void': print('VOID',o['team'],o['player'],o['market'])
