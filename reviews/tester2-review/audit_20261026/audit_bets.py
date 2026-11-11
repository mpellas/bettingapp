import sys,os,re,pandas as pd
sys.path.insert(0,'/workspace/nhl-sog'); os.chdir('/workspace/nhl-sog')
import three_records as T
B=pd.read_csv('/workspace/props-finder/user_bets/bets.csv')
N=open('/workspace/props-finder/user_bets/NOTES.md').read()+open('/workspace/nhl-sog/NOTES.md').read()
dec=lambda a:1+(a/100 if a>0 else 100/-a)
out=[]
for i,r in B.iterrows():
    f=[];exp=None
    if r.result=='win' and r.market!='pp_power2': exp=round(r.risk*dec(int(r.price)),2)
    if r.result=='loss': exp=0.0
    if exp is not None and abs(exp-r.payout)>0.011: f.append(f'payout {r.payout} vs calc {exp}')
    act=None
    if r.sport=='nhl':
        d=r.date.replace('-','');s,fin,g=T.shots(d,r.player);act=s
        if s is not None:
            L=float(r.line); w=s>L if r.side=="over" else s<L
            if (r.result=='win')!=w: f.append(f'regrade mismatch: {s} shots')
        else: f.append('player not found in box')
    last=r.player.split()[-1]
    proof='ID in NOTES' if re.search(rf'{last}[^\n]{{0,160}}(DK\d{{8,}}|pick \d{{9}}|\b7\d{{8}}\b)|(DK\d{{8,}}|Fliff \d{{9}})[^\n]{{0,40}}{last}',N) else ('described in NOTES, no ID' if last in N else 'NO PROOF')
    out.append(dict(row=i+2,date=r.date,player=r.player,book=r.book,price=r.price,risk=r.risk,payout=r.payout,result=r.result,shots=act,proof=proof,flags='; '.join(f)))
O=pd.DataFrame(out);O.to_csv('/workspace/tester2-review/audit_20261026/bets_audit.csv',index=False)
B['net']=B.payout-B.risk
print(O[(O.flags!='')|(O.proof!='ID in NOTES')].to_string())
print(B.groupby('date').agg(n=('net','size'),w=('result',lambda x:(x=='win').sum()),net=('net','sum')).round(2).to_string())
