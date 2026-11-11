import csv,glob,json,collections,math
def shots_by_id(date):
    m={}
    for f in glob.glob('box/*.json'):
        d=json.load(open(f))
        if d['gameDate'].replace('-','')!=date or d['gameState'] not in ('OFF','FINAL'): continue
        for t in ('awayTeam','homeTeam'):
            for g in ('forwards','defense'):
                for p in d['playerByGameStats'][t][g]: m[p['playerId']]=p.get('sog',0)
    return m
def pay(a): a=int(a); return a/100 if a>0 else 100/-a
