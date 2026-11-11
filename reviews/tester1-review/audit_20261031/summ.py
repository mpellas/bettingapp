import csv
r=list(csv.DictReader(open('skipped_sides.csv')))
def s(rs,label):
  g=[x for x in rs if x['result'] in 'WL' and x['result']]
  w=sum(x['result']=='W' for x in g);u=sum(float(x['units_dk']) for x in g)
  sh=[x for x in g if x['units_shop']];su=sum(float(x['units_shop']) for x in sh)
  cl=[float(x['clv_pts']) for x in rs if x['clv_pts']!='']
  return f"| {label} | {len(rs)} | {w}-{len(g)-w} | {u:+.2f} | {len(sh)} / {su:+.2f} | {len(cl)} / {sum(cl)/len(cl) if cl else 0:+.1f} | {len(rs)-len(cl)} |"
H="| Bucket | n | W-L | Units at DK (1u) | Shop-at n / units | CLV n / avg pts | No close |\n|---|---|---|---|---|---|---|"
L=[H]
for b in ['1_fliff_skip','2_stale_lineup','3_role_slot_veto']:
  L.append(s([x for x in r if x['bucket']==b],b))
b3=[x for x in r if x['bucket']=='3_role_slot_veto']
for k in ['role_demotion','role_promotion','slot']: L.append(s([x for x in b3 if x['tag']==k],'3: '+k))
L.append(s([x for x in b3 if float(x['blend_edge_pts'])>=5],'3: vetoed with blend edge>=5'))
L.append(s([x for x in b3 if float(x['blend_edge_pts'])>0],'3: vetoed with blend edge>0'))
b1=[x for x in r if x['bucket']=='1_fliff_skip']
for k in ['rising_toi_under','over_bias','falling_toi_over','market_move','cleared_unpriced','other']: L.append(s([x for x in b1 if x['tag']==k],'1: '+k))
print("\n".join(L))
