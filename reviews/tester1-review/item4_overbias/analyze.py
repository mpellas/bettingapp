import glob,json,os,re,math,numpy as np,pandas as pd,requests
R='nhl-sog-copy'
st={}
for f in glob.glob(R+'/captures/*/*.json'):
    try: d=json.load(open(f)); st[str(d['event'])]=pd.Timestamp(d['start_utc'].replace('Z','+00:00'))
    except Exception: pass
rows=[]
for f in sorted(glob.glob(R+'/picks/*_GATE.csv')):
    d=pd.read_csv(f,dtype={'event':str}); d['src']=os.path.basename(f); rows.append(d)
g=pd.concat(rows,ignore_index=True)
g['cap']=pd.to_datetime(g.captured_utc,utc=True,format='mixed')
g['start']=g.event.map(st)
g['mins']=(g.start-g.cap).dt.total_seconds()/60
n0=len(g)
g=g[g.p_model_over.notna()&g.nv_over.notna()]
g=g[(g.mins>=150)|g.mins.isna()]
g['date']=(g.start.fillna(g.cap)).dt.tz_convert('America/Los_Angeles').dt.strftime('%Y%m%d')
g=g[g.date<='20261030']
g=g.sort_values('cap').groupby(['nhl_id','gameId']).tail(1)
# results
act={}
for f in glob.glob(R+'/graded/*.csv'):
    d=pd.read_csv(f)
    if not {'actual','nhl_id','gameId'}<=set(d.columns): continue
    for r in d.itertuples():
        if pd.notna(r.actual): act[(int(r.nhl_id),int(r.gameId))]=float(r.actual)
box={}
def boxsog(gid):
    if gid in box: return box[gid]
    p=f'{R}/data/catchup_box/{gid}.json'
    try: d=json.load(open(p)) if os.path.exists(p) else requests.get(f'https://api-web.nhle.com/v1/gamecenter/{gid}/boxscore',timeout=20).json()
    except Exception: d={}
    m={}
    def walk(o):
        if isinstance(o,dict):
            if 'playerId' in o and 'sog' in o: m[int(o['playerId'])]=float(o['sog'])
            for v in o.values(): walk(v)
        elif isinstance(o,list):
            for v in o: walk(v)
    walk(d.get('playerByGameStats',d)); box[gid]=(m,d.get('gameState'))
    return box[gid]
src=[];A=[]
for r in g.itertuples():
    k=(int(r.nhl_id),int(r.gameId))
    if k in act: A.append(act[k]);src.append('graded');continue
    m,s=boxsog(k[1])
    if k[0] in m and s in ('OFF','FINAL'): A.append(m[k[0]]);src.append('nhl_box')
    else: A.append(np.nan);src.append('dnp_or_missing')
g['actual']=A;g['res_src']=src
g=g[g.actual.notna()].copy()
def imp(a):
    a=float(a); return 100/(a+100) if a>0 else -a/(-a+100)
def payout(a): a=float(a); return a/100 if a>0 else 100/-a
S=[]
for r in g.itertuples():
    pos='D' if str(r.slot).startswith('D') else 'F'
    hit=r.actual>r.line
    for side in ('over','under'):
        pm=r.p_model_over if side=='over' else 1-r.p_model_over
        pb=r.p_blend_over if side=='over' else 1-r.p_blend_over
        nv=r.nv_over if side=='over' else 1-r.nv_over
        pr=getattr(r,side); y=int(hit) if side=='over' else int(not hit)
        try: pp=payout(pr); be=imp(pr)
        except Exception: pp=100/110; be=110/210
        S.append(dict(date=r.date,player=r.player,nhl_id=r.nhl_id,gameId=r.gameId,side=side,line=r.line,pos=pos,p_model=pm,p_blend=pb,nv=nv,price=pr,payout=pp,be=be,y=y,actual=r.actual,res_src=r.res_src,role_reason=r.role_reason,src=r.src))
s=pd.DataFrame(S);s['edge']=(s.p_model-s.be)*100
s.to_csv('sides_scored.csv',index=False)
print('gate rows',n0,'player-games',len(g),'sides',len(s)); print(g.res_src.value_counts())
cl=lambda p:np.clip(p,1e-4,1-1e-4)
def brier(p,y):return np.mean((p-y)**2)
def ll(p,y):p=cl(p);return -np.mean(y*np.log(p)+(1-y)*np.log(1-p))
rng=np.random.default_rng(7)
def boot(f,d,B=2000):
    idx=np.arange(len(d)); v=[f(d.iloc[rng.choice(idx,len(d))]) for _ in range(B)]; return np.percentile(v,[2.5,97.5])
# (1) reliability
rel=[];sc=[]
bins=np.arange(0,1.01,0.1)
for side,d in s.groupby('side'):
    d=d.assign(b=pd.cut(d.p_model,bins))
    for b,x in d.groupby('b',observed=True): rel.append(dict(side=side,bin=str(b),n=len(x),mean_pred=x.p_model.mean(),mean_nv=x.nv.mean(),hit=x.y.mean()))
    for nm in ('p_model','p_blend','nv'):
        ci=boot(lambda x:brier(x[nm],x.y)-brier(x.nv,x.y),d) if nm!='nv' else [np.nan,np.nan]
        sc.append(dict(side=side,prob=nm,n=len(d),brier=brier(d[nm],d.y),logloss=ll(d[nm],d.y),brier_minus_nv_CI_lo=ci[0],brier_minus_nv_CI_hi=ci[1]))
pd.DataFrame(rel).to_csv('reliability_by_direction.csv',index=False)
sc=pd.DataFrame(sc);sc.to_csv('scores_by_direction.csv',index=False)
# (2) bias
s['lineb']=s.line.map(lambda l:'3.5+' if l>=3.5 else str(l))
s['edgeb']=pd.cut(s.edge,[-100,0,2.5,5,10,100],labels=['<0','0-2.5','2.5-5','5-10','10+'])
s['bias']=s.p_model-s.y
bb=[]
for dim in ('lineb','pos','edgeb'):
    for (side,k),x in s.groupby(['side',dim],observed=True):
        ci=boot(lambda z:z.bias.mean(),x,1000) if len(x)>=10 else [np.nan]*2
        bb.append(dict(dim=dim,side=side,level=str(k),n=len(x),mean_pred=x.p_model.mean(),hit=x.y.mean(),bias=x.bias.mean(),ci_lo=ci[0],ci_hi=ci[1],nv_bias=(x.nv-x.y).mean()))
for side,x in s.groupby('side'):
    ci=boot(lambda z:z.bias.mean(),x,1000); bb.append(dict(dim='all',side=side,level='all',n=len(x),mean_pred=x.p_model.mean(),hit=x.y.mean(),bias=x.bias.mean(),ci_lo=ci[0],ci_hi=ci[1],nv_bias=(x.nv-x.y).mean()))
bb=pd.DataFrame(bb);bb.to_csv('bias_by_direction.csv',index=False)
# (3) fixes, fit on over-side rows (under = complement)
o=s[s.side=='over'].copy()
lg=lambda p:np.log(cl(p)/(1-cl(p)));sg=lambda z:1/(1+np.exp(-z))
tr=o[o.date<='20261022'];te=o[o.date>='20261023']
from scipy.optimize import minimize
def fitll(fn,x0):return minimize(lambda w:ll(fn(w,tr),tr.y),x0,method='Nelder-Mead').x
fx={}
fx['raw']=lambda w,d:d.p_model
w_int=fitll(lambda w,d:sg(lg(d.p_model)+w[0]),[0]);fx['intercept']=lambda w,d:sg(lg(d.p_model)+w_int[0])
w_pl=fitll(lambda w,d:sg(w[0]+w[1]*lg(d.p_model)),[0,1]);fx['platt']=lambda w,d:sg(w_pl[0]+w_pl[1]*lg(d.p_model))
w_sh=fitll(lambda w,d:sg((1-w[0])*lg(d.p_model)+w[0]*lg(d.nv)),[0.5]);fx['shrink_nv']=lambda w,d:sg((1-w_sh[0])*lg(d.p_model)+w_sh[0]*lg(d.nv))
fx['nv']=lambda w,d:d.nv
params=dict(intercept=list(w_int),platt=list(w_pl),shrink_nv=list(w_sh))
print('params',params,'train',len(tr),'test',len(te))
oos=[]
for k,f in fx.items():
    for nm,d in (('train',tr),('test',te)):
        p=f(None,d)
        # sides in both directions: brier same for complement; ll same
        ci=boot(lambda z:brier(f(None,z),z.y)-brier(z.p_model,z.y),d,1000) if k!='raw' else [np.nan]*2
        oos.append(dict(fix=k,set=nm,n_player_games=len(d),brier=brier(p,d.y),logloss=ll(p,d.y),dBrier_vs_raw_CI_lo=ci[0],dBrier_vs_raw_CI_hi=ci[1]))
oos=pd.DataFrame(oos);oos.to_csv('fix_oos.csv',index=False)
# edge lists on test
best=min(['intercept','platt','shrink_nv'],key=lambda k:oos[(oos.fix==k)&(oos.set=='test')].brier.iloc[0])
tes=s[s.date>='20261023'].copy()
po=fx[best](None,o.set_index(['nhl_id','gameId']).loc[list(zip(tes.nhl_id,tes.gameId))].reset_index()).values
tes['p_fix']=np.where(tes.side=='over',po,1-po)
tes['edge_fix']=(tes.p_fix-tes.be)*100
tes['raw5']=tes.edge>=5;tes['fix5']=tes.edge_fix>=5
tes['units']=np.where(tes.y==1,tes.payout,-1.0)
lst=tes[tes.raw5|tes.fix5].copy()
lst['change']=np.select([lst.raw5&lst.fix5,lst.raw5],['kept','dropped'],'added')
lst.to_csv('edge5_list_changes_test.csv',index=False)
summ=lst.groupby(['change','side']).agg(n=('y','size'),W=('y','sum'),units=('units','sum')).reset_index()
summ.to_csv('edge5_change_summary.csv',index=False)
# full-sample over edge5
e5=s[(s.edge>=5)]
print(sc.round(4).to_string());print(bb[bb.dim.isin(['all','edgeb'])].round(3).to_string());print(oos.round(4).to_string());print('best',best);print(summ)
print('edge5 all',e5.groupby('side').agg(n=('y','size'),hit=('y','mean'),be=('be','mean')))
json.dump(dict(params=params,best=best),open('fix_params.json','w'))
