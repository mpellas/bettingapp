import re,glob,os,fnmatch,pandas as pd
B='nhl-sog'
PAT=re.compile(r'^Fliff check: (.+?) (OVER|UNDER) ([\d.]+) \(DK ([+-]?\d+)')
C=pd.read_csv(f'{B}/card_decisions.csv')
mk={os.path.basename(f)[:13] for f in glob.glob(f'{B}/picks/finalcall_done/*.txt')}
R=[]
for pf in sorted(glob.glob(f'{B}/picks/2026101[7-9]*_post.txt')+glob.glob(f'{B}/picks/2026102[0-5]*_post.txt')):
  b=os.path.basename(pf);d=b[:8];l=b[:13] if b[8]=='_' else d+'_AM'
  G=pd.read_csv(f'{B}/graded/{d}.csv')
  for ln in open(pf):
    m=PAT.match(ln)
    if not m: continue
    p,s,li,dk=m.group(1),m.group(2),float(m.group(3)),int(m.group(4))
    c=C[[fnmatch.fnmatch(l,a) and fnmatch.fnmatch(p,str(x)) and fnmatch.fnmatch(s,str(y)) for a,x,y in zip(C.list,C.player,C.side)]]
    dec=c.decision.iloc[0] if len(c) else None
    lr=C[[fnmatch.fnmatch(l,a) for a in C.list]]
    if dec=='skip': bk='skipped'
    elif dec=='card' or (l in mk and len(lr)==0): bk='card' if dec=='card' else 'MARKER_NO_ROW'
    elif l in mk: bk='card'
    else: bk='no_decision'
    g=G[(G.player==p)&(G.line==li)].actual.dropna()
    a=g.iloc[0] if len(g) else None
    h=None if a is None else int(a>li if s=='OVER' else a<li)
    u=None if h is None else ((dk/100 if dk>0 else 100/-dk) if h else -1)
    R.append(dict(list=l,player=p,side=s,line=li,dk=dk,marker=l in mk,bucket=bk,actual=a,hit=h,u=u))
R=pd.DataFrame(R);R.to_csv('mine.csv',index=False)
def s(r):g=r.dropna(subset=['hit']);return f'{len(r)} sides {int(g.hit.sum())}-{len(g)-int(g.hit.sum())} {g.u.sum():+.2f}u'
print(R.bucket.value_counts());print('card',s(R[R.bucket=='card']));print('card+nodec',s(R[R.bucket.isin(['card','no_decision'])]))
print(R[R.bucket.isin(['card','no_decision','MARKER_NO_ROW'])].to_string())
