import pandas as pd, numpy as np, glob
C = 'nfl-props/sidecars/evidence/cache'
ps = pd.concat([pd.read_parquet(f'{C}/stats_player_week_{s}.parquet', columns=['player_id','player_display_name','season','week','season_type','passing_yards','rushing_yards','receiving_yards']) for s in (2024,2025,2026)])
ps = ps[ps.season_type=='REG']
STAT = {'pass_yds':'passing_yards','rush_yds':'rushing_yards','rec_yds':'receiving_yards','reception_yds':'receiving_yards'}
def am2p(a): a=float(a); return -a/(-a+100) if a<0 else 100/(a+100)
sym = {'+':1,'-':-1,'0':0}
allrows = []
for tag, W in (('wk8_0909', 8), ('wk7_0732', 7)):
    N = pd.read_csv(f'out/{tag}_new.csv', dtype={'player_id':str}); O = pd.read_csv(f'out/{tag}_old.csv', dtype={'player_id':str})
    print(f'== {tag}: rows {len(N)}; agrees_n new==old: {(N.agrees_n.values==O.agrees_n.values).all()}; sig cols equal:',
          all((N[c].astype(str)==O[c].astype(str)).all() for c in O if c.startswith('sig_')))
    # vs saved production evidence file (made earlier, with net) - informational
    P = pd.read_csv(f'pf/analysis_2026_{tag.split("_")[0]}_live_{ {"wk8_0909":"20261101T0909","wk7_0732":"20261025T0732"}[tag]}_evidence.csv')
    print('   vs saved production _evidence.csv agrees_n equal rows:', int((P.agrees_n.values==N.agrees_n.values).sum()), 'of', len(N))
    xs = [c for c in N if c.startswith('sig_x_')]
    plus = sum((N[c]=='+').astype(int) for c in xs)
    print('   tests_all_n', N.tests_all_n.unique(), 'extra cols', xs, '| X-of-N arithmetic fails', int((N.agrees_all_n != N.agrees_n + plus).sum()))
    for i, r in N.iterrows():
        g = ps[(ps.player_id==r.player_id) & ((ps.season<2026) | ((ps.season==2026)&(ps.week<W)))].sort_values(['season','week'])
        leak = ps[(ps.player_id==r.player_id)&(ps.season==2026)&(ps.week>=W)]
        col = STAT[r.market]; cur = g[g.season==2026]; o = r.side.lower().startswith('o')
        f = (lambda v: v > r.line) if o else (lambda v: v < r.line)
        y, y10 = cur[col].fillna(0), g.tail(10)[col].fillna(0)
        hs, h10 = f(y).mean() if len(y) else np.nan, f(y10).mean()
        fp = r.mkt_p; pa = r.price_assumed
        def sg(p):
            if len(cur) < 4 or pd.isna(p): return 0
            return 1 if (hs>=p+.05 and h10>=p+.05) else (-1 if (hs<=p-.05 and h10<=p-.05) else 0)
        # books: mine
        oth = N[(N.player==r.player)&(N.market==r.market)&(N.side.str.lower()==r.side.lower())&(N.book!=r.book)]
        allrows.append(dict(file=tag, player=r.player, market=r.market, side=r.side, line=r.line, book=r.book, price=r.price,
             n_season=len(cur), hit_season=int(f(y).sum()), hit_l10=int(f(y10).sum()), l10_last_season=int((g.tail(10).season<2026).sum()),
             mkt_p=fp, price_assumed=pa, my_hit=sg(fp), my_hit_vig=sg(am2p(r.price)), their_hit=sym[str(r.sig_x_hit)], their_books=sym[str(r.sig_x_books)],
             why_x_hit=r.why_x_hit, why_x_books=r.why_x_books, n_other_books_same_side=len(oth), games_wk_ge_W=len(leak)))
M = pd.DataFrame(allrows); M.to_csv('nfl_hit_books_compare.csv', index=False)
print('NFL sides', len(M), 'hit mismatches', int((M.my_hit!=M.their_hit).sum()))
print(M[M.my_hit!=M.their_hit][['file','player','side','line','market','their_hit','my_hit','why_x_hit']].to_string())
print('hit dist', M.their_hit.value_counts().to_dict(), '| would differ with vig price', int((M.my_hit!=M.my_hit_vig).sum()))
print('books dist', M.their_books.value_counts().to_dict(), '| sides with another book same side', int((M.n_other_books_same_side>0).sum()))
print('books whys', M.why_x_books.value_counts().to_dict())
print('l10 incl. prior season', int((M.l10_last_season>0).sum()), '| price_assumed True rows', int(M.price_assumed.astype(str).eq('True').sum()))
