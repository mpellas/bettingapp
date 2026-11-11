import pandas as pd, numpy as np, glob
NHL='/workspace/nhl-sog'
S=pd.read_pickle('board_dedup.pkl')
def dec(a): a=float(a); return a/100 if a>0 else 100/abs(a)
def plf(hit,price): return np.nan if (pd.isna(price) or pd.isna(hit)) else (dec(price) if hit else -1.0)
F=pd.concat([pd.read_csv(f).assign(ffile=f.split('/')[-1]) for f in sorted(glob.glob(f'{NHL}/fliff_prices/2026102[5-9]*.csv'))])
F['date']=F.date.astype(str)
C=S[(S.date>='20261025')&(S.status!='Skipped')].copy()
C=C.merge(F[['date','player','side','line','fliff_status','fliff_line','fliff_price']],on=['date','player','side','line'],how='left')
C['list']=C.date+'_'+C['pass']
C.loc[C.fliff_line.notna()&(C.fliff_line!=C.line),'fliff_price']=np.nan
# reasons (sources: card_decisions.csv notes, picks/*_room.txt, fliff_prices/*.csv, NOTES.md)
P='price_worse_than_shop_at'; FN='fliff_not_posted'; TOI='toi_up_on_under'; ST='stale_lineup'; G27='gate_2_of_7'; CK='checker_missing_or_split'; OT='other'
R={
('20261025_0922','Roman Kantserov'):([P,FN],'','room 9:22 + fliff_prices: Fliff not offered; DK +100 < +115'),
('20261025_1202','Brayden Schenn'):([P],'','conditional card Fliff +109 or better only; Fliff -110, DK -105 never reached it'),
('20261025_1202','Roope Hintz'):([P],'','Fliff -190, DK -185 < -157'),
('20261025_1202','Miro Heiskanen'):([P,TOI],'','Fliff +110, DK +130 < +145; TOI +1.6 min (cited as TOI-up precedent in Oct 26 Laferriere note)'),
('20261025_1404','Roman Josi'):([P,FN],'','DK -195 < -164; Fliff only had 2.5 line'),
('20261025_1404','Sam Malinski'):([P],'','Fliff -115, DK -105 < +109'),
('20261025_1601','Jake DeBrusk'):([G27,P],'','2-of-7 agreement skip; removed from post (post_prerule.txt); Fliff not priced'),
('20261026_1311','Trevor Moore'):([P,OT],'checker veto: overs-5+-edge audit / TOI down / market -1.8','Tester1 skip unopposed; Fliff -165, DK -145 < -123'),
('20261026_1311','Alex Laferriere'):([P,TOI],'','Tester2 TOI-up/PP1 veto; Fliff -130, DK -145 < -123'),
('20261026_1438','Darren Raddysh'):([P,OT],'checker NO BETS: 3-of-7 leans on 2.9-pt move','Fliff -125, DK -125 < -107'),
('20261026_1516','Kasperi Kapanen'):([P,TOI],'','T2+T3 skip TOI up 1.7 min; Fliff -115, DK -110 < +105'),
('20261027_1305','Travis Sanheim'):([P,FN,CK],'','no clear from both checkers by final call'),
('20261027_1305','Christian Dvorak'):([P,FN,CK,TOI],'','no clear from both checkers; TOI up 1.5'),
('20261027_1305','Zach Werenski'):([ST,P,FN],'','CBJ DFO ~27h old'),
('20261027_1305','Alex Bump'):([P,FN,CK],'','no clear from both checkers'),
('20261027_1339','Logan Stankoven'):([P],'','both checkers matched; Fliff +105, DK +110 < +125'),
('20261027_1339','Timo Meier'):([ST,P],'','NJD DFO ~29h; DK -105 < +109 (Fliff not priced)'),
('20261027_1339','Jesper Bratt'):([ST,P],'','NJD DFO ~29h; DK -140 < -121 (Fliff not priced)'),
('20261027_1339','Jack Hughes'):([ST,P],'','NJD DFO ~29h; DK -150 < -127 (Fliff not priced)'),
('20261027_1339','Mark Scheifele'):([],'','CARD PLAY: hold_prizepicks, both checkers clear; user played it on PrizePicks power2'),
('20261027_1432','Blake Coleman'):([ST,P],'','MIN DFO ~31h; DK -135 < -117 (Fliff not priced)'),
('20261027_1432','Dylan Guenther'):([P,FN,CK],'','checkers split (T3 skip on 16-pt no-vig move vs side)'),
('20261027_1533','Tomas Hertl'):([P],'','Fliff -180, DK -160 < -138'),
('20261027_1533','Jake DeBrusk'):([ST,P],'','VAN DFO ~28h; DK -135 < -117 (Fliff not priced)'),
('20261027_1533','Jackson LaCombe'):([P,TOI],'','Fliff -115, DK +100 < +114; both checkers flag rising TOI'),
('20261027_1533',"Drew O'Connor"):([ST,P],'','VAN DFO ~28h; DK -155 < -132 (Fliff not priced)'),
('20261027_1533','Cutter Gauthier'):([P,TOI],'','Fliff +100, DK +105 < +120; both checkers flag rising TOI'),
('20261027_1609','Jack Quinn'):([P,TOI],'','Fliff -125, DK -105 < +109; T2+T3 would skip on rising TOI'),
('20261028_1304','Travis Sanheim'):([P,CK,OT],'T1 over-bias skip','Fliff +110, DK +115 < +129; checker split'),
('20261028_1304','Trevor Zegras'):([P,CK,OT],'T1 over-bias skip','Fliff -145, DK -125 < -107; checker split'),
('20261028_1304','Aliaksei Protas'):([P],'','Fliff -115, DK -120 < -103; T1+T3 clear at price'),
('20261028_1509','Sam Malinski'):([P],'','Fliff -140, DK -140 < -121; T1+T2 clear at price'),
('20261028_1535','William Nylander'):([P,OT],'TOI-down on over (T2+T3)','Fliff -130, DK -115 < +101'),
('20261028_1535','Darren Raddysh'):([P],'','Fliff -125, DK -130 < -112; T2+T3 clear at price'),
('20261029_1233','Gage Goncalves'):([P,FN,CK],'','T3/T1 split'),
('20261029_1233','MacKenzie Weegar'):([P,FN,CK],'','T3/T1 split'),
('20261029_1233','Dylan Guenther'):([P,FN,OT],'both checkers skip (16.3-pt no-vig move vs side; TOI +1.3 in evidence)','both checkers skip'),
('20261029_1233','Nikolaj Ehlers'):([P,FN,CK],'','T3/T1 split'),
('20261029_1233','Sebastian Aho'):([P,FN,CK],'','T3/T1 split'),
}
C['reasons']=[R[(l,p)][0] for l,p in zip(C.list,C.player)]
C['other_detail']=[R[(l,p)][1] for l,p in zip(C.list,C.player)]
C['source_note']=[R[(l,p)][2] for l,p in zip(C.list,C.player)]
C['decision']=np.where(C.reasons.str.len()==0,'card_play','skipped')
C['hit']=C.hit.astype('boolean')
C['pl_shop_at']=[plf(h,p) for h,p in zip(C.hit,C.fliff_shop_at)]
C['pl_dk']=[plf(h,p) for h,p in zip(C.hit,C.dk_price)]
best=[]
for d,f in zip(C.dk_price,C.fliff_price):
    if pd.notna(f) and dec(f)>dec(d): best.append(f)
    else: best.append(d)
C['best_avail_price']=best
C['pl_best_avail']=[plf(h,p) for h,p in zip(C.hit,C.best_avail_price)]
C['in_band_dk']=[(-150<=p<=110) for p in C.dk_price]
C['grade_source']=np.where(C.date=='20261029','graded_overlay (pinned grade VOID_noC; logged shots)','graded (pinned)')
C['n_reasons']=C.reasons.str.len()
C['price_only']=C.reasons.apply(lambda r: r==[P])
C.to_pickle('cands.pkl')
out=C[C.decision=='skipped'].copy()
out['reasons']=out.reasons.str.join('; ')
cols=['date','list','game','player','side','line','dk_price','fliff_status','fliff_price','fliff_shop_at','best_avail_price','in_band_dk','edge','agrees_n','sig_toi','lineup_age_h','reasons','n_reasons','other_detail','source_note','actual','hit','pl_shop_at','pl_dk','pl_best_avail','grade_source']
out['edge']=(out.edge*100).round(1); out['lineup_age_h']=out.lineup_age_h.round(1)
for c in ['pl_shop_at','pl_dk','pl_best_avail']: out[c]=out[c].round(3)
out['fliff_status']=out.fliff_status.fillna('not checked (no Fliff credit spent)').str.replace(r' \(.*','',regex=True)
out[cols].to_csv('skips_graded.csv',index=False)
print(out[cols[:4]+['reasons','hit','pl_shop_at','pl_dk']].to_string())
