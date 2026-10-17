"""Rebuild Olist fulfillment and review-risk analysis from immutable source CSVs."""
from pathlib import Path
import json, sqlite3
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize
from scipy.special import expit
from sklearn.metrics import roc_auc_score
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

P=Path(__file__).parent; OUT=P/'project'; (OUT/'figures').mkdir(parents=True,exist_ok=True)
names={'orders':'olist_orders_dataset','reviews':'olist_order_reviews_dataset','items':'olist_order_items_dataset','payments':'olist_order_payments_dataset','customers':'olist_customers_dataset','products':'olist_products_dataset','sellers':'olist_sellers_dataset','geo':'olist_geolocation_dataset','categories':'product_category_name_translation'}
data={k:pd.read_csv(P/(v+'.csv'),dtype={'customer_zip_code_prefix':'string','seller_zip_code_prefix':'string','geolocation_zip_code_prefix':'string'},low_memory=False) for k,v in names.items()}
con=sqlite3.connect(':memory:')
for k,v in data.items(): v.to_sql(k,con,index=False)
sql="""
WITH item_agg AS (
 SELECT i.order_id, COUNT(*) item_count, SUM(i.price) item_value, SUM(i.freight_value) freight,
 COUNT(DISTINCT i.seller_id) seller_count, COUNT(DISTINCT p.product_category_name) category_count,
 MIN(i.seller_id) only_seller, MIN(p.product_category_name) only_category
 FROM items i LEFT JOIN products p ON i.product_id=p.product_id GROUP BY i.order_id
), pay_agg AS (SELECT order_id, COUNT(*) payment_count, SUM(payment_value) payment_value FROM payments GROUP BY order_id),
review_agg AS (SELECT order_id,COUNT(*) review_count,COUNT(DISTINCT review_score) distinct_score_count,
 MIN(review_score) min_score,MAX(review_score) max_score,AVG(review_score) avg_score
 FROM reviews GROUP BY order_id)
SELECT o.*,c.customer_state,c.customer_zip_code_prefix,a.item_count,a.item_value,a.freight,a.seller_count,a.category_count,a.only_seller,a.only_category,p.payment_count,p.payment_value,
 r.review_count,r.distinct_score_count,r.min_score,r.max_score,r.avg_score
 FROM orders o LEFT JOIN customers c ON o.customer_id=c.customer_id
 LEFT JOIN item_agg a ON o.order_id=a.order_id
 LEFT JOIN pay_agg p ON o.order_id=p.order_id
 LEFT JOIN review_agg r ON o.order_id=r.order_id
"""
(OUT/'analysis.sql').write_text(sql,encoding='utf-8')
df=pd.read_sql_query(sql,con)
assert len(df)==len(data['orders']) and df.order_id.is_unique
rv=data['reviews'].copy(); rv['review_answer_timestamp']=pd.to_datetime(rv.review_answer_timestamp)
latest=rv.sort_values(['review_answer_timestamp','review_id']).groupby('order_id').tail(1)[['order_id','review_score']].rename(columns={'review_score':'latest_score'})
df=df.merge(latest,on='order_id',how='left',validate='one_to_one')
for c in ['order_purchase_timestamp','order_approved_at','order_delivered_carrier_date','order_delivered_customer_date','order_estimated_delivery_date']: df[c]=pd.to_datetime(df[c])
df['delivered_valid']=(df.order_status=='delivered') & df.order_delivered_customer_date.notna()
df['has_review']=df.latest_score.notna()
df['late']=(df.order_delivered_customer_date.dt.normalize()>df.order_estimated_delivery_date.dt.normalize())
df['delay_days']=(df.order_delivered_customer_date.dt.normalize()-df.order_estimated_delivery_date.dt.normalize()).dt.days.clip(lower=0)
df['delivery_days']=(df.order_delivered_customer_date-df.order_purchase_timestamp).dt.total_seconds()/86400
df['carrier_days']=(df.order_delivered_carrier_date-df.order_purchase_timestamp).dt.total_seconds()/86400
df['purchase_month']=df.order_purchase_timestamp.dt.to_period('M').astype(str)
q=df[df.delivered_valid].copy(); a=q[q.has_review].copy()
a['bad12']=(a.latest_score<=2).astype(int); a['bad123']=(a.latest_score<=3).astype(int)
assert len(q)==96470 and q.order_id.is_unique and a.order_id.is_unique

def group(frame,key,min_n=0):
 t=frame.groupby(key,dropna=False).agg(n=('order_id','size'),late_n=('late','sum'),late_rate=('late','mean'),bad_n=('bad12','sum'),bad_rate=('bad12','mean')).reset_index()
 t['bad_wilson_low']=stats.binomtest(1,2).proportion_ci().low if False else 0.0
 z=1.96; n=t.n; p=t.bad_rate
 t['bad_wilson_low']=(p+z*z/(2*n)-z*np.sqrt(p*(1-p)/n+z*z/(4*n*n)))/(1+z*z/n)
 t['bad_wilson_high']=(p+z*z/(2*n)+z*np.sqrt(p*(1-p)/n+z*z/(4*n*n)))/(1+z*z/n)
 return t[t.n>=min_n].sort_values('n',ascending=False)

late=group(a,'late'); region=group(a,'customer_state',500)
single=a[(a.category_count==1)&a.only_category.notna()].copy(); cat=group(single,'only_category',300)
seller=a[(a.seller_count==1)&a.only_seller.notna()].copy(); sellers=group(seller,'only_seller',100)
monthly=group(a,'purchase_month',100)
for name,t in [('late_groups',late),('regions',region),('categories_single',cat),('sellers_single',sellers),('monthly',monthly)]:t.to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')

def fit(frame,outcome='bad12',with_category=False):
 x=frame[['late','customer_state','purchase_month','item_value','freight','item_count']].copy()
 x['log_value']=np.log1p(x.item_value);x['log_freight']=np.log1p(x.freight);x['log_items']=np.log1p(x.item_count)
 x=x.drop(columns=['item_value','freight','item_count'])
 x=pd.get_dummies(x,columns=['customer_state','purchase_month'],drop_first=True,dtype=float)
 if with_category:
  top=frame.only_category.value_counts().head(15).index
  cat=frame.only_category.where(frame.only_category.isin(top),'other')
  x=pd.concat([x,pd.get_dummies(cat,prefix='category',drop_first=True,dtype=float)],axis=1)
 x=x.astype(float);x.insert(0,'intercept',1.0)
 y=frame[outcome].to_numpy(float); X=x.to_numpy(float)
 def fn(b):
  z=X@b;p=expit(z);return np.logaddexp(0,z).sum()-y@z, X.T@(p-y)
 result=minimize(lambda b:fn(b),np.zeros(X.shape[1]),jac=True,method='L-BFGS-B',options={'maxiter':1000,'ftol':1e-11})
 b=result.x;p=expit(X@b);w=p*(1-p);h=X.T@(X*w[:,None]);se=np.sqrt(np.diag(np.linalg.pinv(h)))
 j=list(x.columns).index('late'); beta=b[j]; s=se[j]
 return {'n':len(y),'events':int(y.sum()),'converged':bool(result.success),'iterations':result.nit,'late_or':float(np.exp(beta)),'late_ci95':[float(np.exp(beta-1.96*s)),float(np.exp(beta+1.96*s))],'late_p':float(2*stats.norm.sf(abs(beta/s))),'auc_apparent':float(roc_auc_score(y,p)),'features':len(b),'condition_number':float(np.linalg.cond(h))}

eligible_months=a.purchase_month.value_counts().loc[lambda s:s>=100].index
mod=a[a.purchase_month.isin(eligible_months)].dropna(subset=['item_value','freight','item_count','customer_state']).copy()
models={'main':fit(mod),'bad123':fit(mod,'bad123')}
nonconflict=mod[mod.distinct_score_count<=1].copy();models['unambiguous_reviews']=fit(nonconflict)
mod['bad12_min']=(mod.min_score<=2).astype(int);mod['bad12_max']=(mod.max_score<=2).astype(int)
models['min_score']=fit(mod,'bad12_min');models['max_score']=fit(mod,'bad12_max')
models['single_category_adjusted']=fit(mod[(mod.category_count==1)&mod.only_category.notna()],'bad12',True)

ct=pd.crosstab(a.late,a.bad12);odds,p_fisher=stats.fisher_exact(ct)
two=stats.contingency.relative_risk(ct.loc[True,1],ct.loc[True].sum(),ct.loc[False,1],ct.loc[False].sum())
metric={
 'source_rows':{k:len(v) for k,v in data.items()},'order_rows':len(df),'delivered':int((df.order_status=='delivered').sum()),'delivered_valid':len(q),'delivered_missing_date':int(((df.order_status=='delivered')&df.order_delivered_customer_date.isna()).sum()),'canceled_with_date':int(((df.order_status=='canceled')&df.order_delivered_customer_date.notna()).sum()),
 'delivered_share_all_orders':float((df.order_status=='delivered').mean()),'valid_delivery_share_all_orders':float(df.delivered_valid.mean()),'reviewed_delivered':len(a),'candidate_no_review':len(q)-len(a),
 'late_count_all_valid':int(q.late.sum()),'late_rate_all_valid':float(q.late.mean()),'delivery_days_median':float(q.delivery_days.median()),'delivery_days_p90':float(q.delivery_days.quantile(.9)),'carrier_days_median':float(q.carrier_days.median()),'carrier_days_missing':int(q.carrier_days.isna().sum()),'carrier_days_negative':int((q.carrier_days<0).sum()),'delivery_days_negative':int((q.delivery_days<0).sum()),
 'bad12_rate_reviewed':float(a.bad12.mean()),'bad123_rate_reviewed':float(a.bad123.mean()),'late_bad12_risk_ratio':float(two.relative_risk),'late_bad12_rr_ci95':[float(two.confidence_interval().low),float(two.confidence_interval().high)],'fisher_p':float(p_fisher),'late_bad12_odds_ratio':float(odds),
 'multi_category_orders_reviewed':int((a.category_count>1).sum()),'multi_seller_orders_reviewed':int((a.seller_count>1).sum()),'ambiguous_score_orders_reviewed':int((a.distinct_score_count>1).sum()),'models':models}
metric['model_excluded_sparse_months']=len(a)-len(mod)
metric['late_rate_reviewed']=float(a.late.mean())
metric['late_rate_without_review']=float(q[~q.has_review].late.mean())
metric['timestamp_late_rate_all_valid']=float((q.order_delivered_customer_date>q.order_estimated_delivery_date).mean())
metric['region_rj']={'n':int(region.set_index('customer_state').loc['RJ','n']),'late_n':int(region.set_index('customer_state').loc['RJ','late_n'])}
(OUT/'metrics.json').write_text(json.dumps(metric,ensure_ascii=False,indent=2),encoding='utf-8')

plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans'];plt.rcParams['axes.unicode_minus']=False
fig,ax=plt.subplots(figsize=(6,4));ax.bar(['On time','Late'],late.sort_values('late').bad_rate*100,color=['#377eb8','#e6550d']);ax.set_ylabel('1–2 star rate (%)');ax.set_title('Review risk by delivery timing');fig.tight_layout();fig.savefig(OUT/'figures'/'late_bad_rate.png',dpi=170);plt.close(fig)
fig,ax=plt.subplots(figsize=(8,4));m=monthly.sort_values('purchase_month');ax.plot(m.purchase_month,m.late_rate*100,label='Late delivery');ax.plot(m.purchase_month,m.bad_rate*100,label='1–2 star');ax.tick_params(axis='x',rotation=65);ax.set_ylabel('Rate (%)');ax.legend();fig.tight_layout();fig.savefig(OUT/'figures'/'monthly_rates.png',dpi=170);plt.close(fig)
fig,ax=plt.subplots(figsize=(7,5));r=region.sort_values('late_rate',ascending=False).head(12);ax.barh(r.customer_state[::-1],r.late_rate[::-1]*100,color='#e6550d');ax.set_xlabel('Late delivery rate (%)');ax.set_title('Regions with at least 500 reviewed deliveries');fig.tight_layout();fig.savefig(OUT/'figures'/'region_late_rate.png',dpi=170);plt.close(fig)
print(json.dumps(metric,ensure_ascii=False,indent=2))
