import csv
def imp(a): return -a/(-a+100) if a<0 else 100/(a+100)
rows=list(csv.DictReader(open('nfl_real_lines_graded.csv')))
tot=W=L=0;u=0.0;games=set();bw=bl=0;bu=0.0;other=0;pushes=0
from collections import Counter
res=Counter(r['result'] for r in rows); print(res)
for r in rows:
  if not r['over_price'] or not r['under_price']: continue
  if r['result'] not in('win','loss'): continue
  if r['stat'] not in('pass_yds','rush_yds','rec_yds'): continue
  op,up=float(r['over_price']),float(r['under_price'])
  p=op if r['pick']=='OVER' else up
  # independent grading from actual vs line
  a,l=float(r['actual']),float(r['line'])
  win=(a>l) if r['pick']=='OVER' else (a<l)
  if (r['result']=='win')!=win: other+=1
  x=(p/100 if p>0 else 100/-p) if win else -1
  tot+=1;games.add(r['event_id']);u+=x;W+=win;L+=(not win)
  if -150<=p<=110: bw+=win;bl+=(not win);bu+=x
print('n',tot,'games',len(games),'W-L',W,L,'units',round(u,2),'roi',round(u/tot*100,2))
print('band',bw,bl,round(bu,2)); print('result-col disagreements',other)
