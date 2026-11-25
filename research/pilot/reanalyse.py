import csv, json, numpy as np
from scipy import stats
rows=[r for r in csv.DictReader(open('eval_final.csv')) if r['post_score_primary']]
f=lambda k: np.array([float(r[k]) for r in rows])
out={"n_listed":17,"n_complete":len(rows)}
rng=np.random.default_rng(1)
def boot(d,B=20000):
    idx=rng.integers(0,len(d),(B,len(d))); m=d[idx].mean(1); return [round(float(np.percentile(m,2.5)),2),round(float(np.percentile(m,97.5)),2)]
for name,pre,post in [("primary_score","pre_score_primary","post_score_primary"),("readiness","pre_readiness","post_readiness"),("highest_level","pre_highest_level","post_highest_level")]:
    a,b=f(pre),f(post); d=b-a
    out[name]={"pre_mean":round(a.mean(),2),"post_mean":round(b.mean(),2),"gain":round(d.mean(),2),"gain_sd":round(d.std(ddof=1),2),
      "t_p":round(float(stats.ttest_rel(b,a).pvalue),4),"wilcoxon_p":round(float(stats.wilcoxon(b,a).pvalue),4),
      "dz":round(d.mean()/d.std(ddof=1),2),"boot95":boot(d),"n_improved":int((d>0).sum()),"n_worse":int((d<0).sum()),
      "corr_gain_vs_pre":round(float(stats.pearsonr(a,d)[0]),2)}
# ceiling on highest level
out["highest_level"]["post_at_ceiling_5"]=int((f("post_highest_level")==5).sum())
out["highest_level"]["pre_at_ceiling_5"]=int((f("pre_highest_level")==5).sum())
# simulation-adjusted highest-level gain (spurious +0.30 under zero learning)
d=f("post_highest_level")-f("pre_highest_level")
out["highest_level"]["adjusted_gain_minus_0.30"]=round(d.mean()-0.30,2)
out["highest_level"]["adjusted_t_p"]=round(float(stats.ttest_1samp(d,0.30).pvalue),4)
# robustness: drop the extreme low pre-test (Student 8, pre=5%)
keep=[i for i,r in enumerate(rows) if r['register_number']!='STUDENT08']
for name,pre,post in [("primary_score","pre_score_primary","post_score_primary"),("readiness","pre_readiness","post_readiness")]:
    a,b=f(pre)[keep],f(post)[keep]
    out[name]["without_student08"]={"gain":round((b-a).mean(),2),"t_p":round(float(stats.ttest_rel(b,a).pvalue),4),"wilcoxon_p":round(float(stats.wilcoxon(b,a).pvalue),4)}
out["cards_read_total"]=int(f("cards_read").sum()); out["cards_total_total"]=int(f("cards_total").sum())
# readiness differs between the two exports for the same students?
early={r['register_number']:r for r in csv.DictReader(open('eval_early.csv'))}
diffs=[(r['register_number'],early[r['register_number']]['pre_readiness'],r['pre_readiness']) for r in rows if r['register_number'] in early and early[r['register_number']]['pre_readiness']!=r['pre_readiness']]
out["readiness_changed_between_exports"]=len(diffs); out["example_change"]=diffs[:3]
json.dump(out,open('pilot_results.json','w'),indent=1); print(json.dumps(out,indent=1))
