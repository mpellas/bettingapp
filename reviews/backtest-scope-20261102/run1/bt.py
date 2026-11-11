import pandas as pd,numpy as np
d=pd.read_csv('/workspace/prop-finder/output/backtest_2025/nfl_real_lines_graded.csv')
d=d[d.over_price.notna()&d.under_price.notna()&d.result.isin(['win','loss'])].copy()
imp=lambda a: np.where(a<0,-a/(-a+100),100/(a+100))
po,pu=imp(d.over_price),imp(d.under_price); fo=po/(po+pu)
ov=d.pick.eq('OVER'); d['price']=np.where(ov,d.over_price,d.under_price)
d['fair']=np.where(ov,fo,1-fo); d['edge']=d.model_p_side-d.fair
d['units']=np.where(d.result=='win',np.where(d.price>0,d.price/100,100/-d.price),-1.0)
d['be']=imp(d.price); d['band']=(d.price<=110)&(d.price>=-150)
d['e14']=0.5*d.model_p_side+0.5*d.fair-d.fair
# naive: rebuild over/under for every line
def naive(side):
  x=d.copy(); x['pick']=side; o=side=='OVER'
  x['price']=x.over_price if o else x.under_price
  win=(x.actual>x.line) if o else (x.actual<x.line)
  x=x[x.actual!=x.line]; win=win[x.index]
  x['units']=np.where(win,np.where(x.price>0,x.price/100,100/-x.price),-1.0); x['result']=np.where(win,'win','loss')
  x['be']=imp(x.price); x['band']=(x.price<=110)&(x.price>=-150); return x
Y=['pass_yds','rush_yds','rec_yds']; U=d[d.stat.isin(Y)]
R={'R01':U,'R02':U[U.edge>=0],'R03':U[U.edge>=.02],'R04':U[U.edge>=.04],'R05':U[U.edge>=.06],
'R06':U[(U.edge>=.02)&(U.pick=='OVER')],'R07':U[(U.edge>=.02)&(U.pick=='UNDER')]}
for i,m in zip(['R08','R09','R10'],Y): R[i]=U[(U.edge>=.02)&(U.stat==m)]
R['R11']=U[U.model_p_side<.55];R['R12']=U[(U.model_p_side>=.55)&(U.model_p_side<.6)];R['R13']=U[U.model_p_side>=.6]
R['R14']=U[U.e14>=.02]
for k,s in [('R15','UNDER'),('R16','OVER')]: n=naive(s); R[k]=n[n.stat.isin(Y)]
R['R17']=d[d.edge>=.02]
rng=np.random.default_rng(7)
def ci(x):
  g=x.groupby('event_id').units.sum().values; s=len(x)
  if len(g)<2: return (np.nan,)*3
  b=rng.choice(g,(5000,len(g))).sum(1)/s
  return np.percentile(b,[2.5,97.5]).tolist()+[np.percentile(b,0.14)]
out=[]
for k,x in R.items():
  for f in ['all','band']:
    y=x if f=='all' else x[x.band]
    if k=='R18': pass
    lo,hi,bon=ci(y); w=(y.result=='win').sum()
    out.append(dict(rule=k,prices=f,n=len(y),games=y.event_id.nunique(),W=w,L=len(y)-w,units=round(y.units.sum(),2),roi=round(y.units.mean()*100,1),hit=round(w/len(y)*100,1),be=round(y.be.mean()*100,1),ci95_lo=round(lo*100,1),ci95_hi=round(hi*100,1),bonf_lo=round(bon*100,1)))
for f in ['all','band']:
  y=U if f=='all' else U[U.band]; y=y.sort_values('edge',ascending=False).groupby('week').head(10)
  lo,hi,bon=ci(y); w=(y.result=='win').sum()
  out.append(dict(rule='R18',prices=f,n=len(y),games=y.event_id.nunique(),W=w,L=len(y)-w,units=round(y.units.sum(),2),roi=round(y.units.mean()*100,1),hit=round(w/len(y)*100,1),be=round(y.be.mean()*100,1),ci95_lo=round(lo*100,1),ci95_hi=round(hi*100,1),bonf_lo=round(bon*100,1)))
o=pd.DataFrame(out); o.to_csv('nfl2025_results.csv',index=False); print(o.to_string(index=False))
