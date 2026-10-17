"""Independent statistical audit and fulfillment-stage study; never edits source CSVs."""
from pathlib import Path
import sys, json, sqlite3, warnings
P=Path(__file__).parent; sys.path.insert(0,str(P/'audit_deps'))
import numpy as np, pandas as pd, statsmodels.api as sm
from scipy.stats import norm
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.linear_model import LogisticRegression
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=P/'deep_study'; O.mkdir(exist_ok=True)
raw={n:pd.read_csv(P/f'olist_{n}_dataset.csv',low_memory=False) for n in ['orders','order_reviews','order_items','order_payments','customers','products','sellers']}
orders=raw['orders']; reviews=raw['order_reviews']; items=raw['order_items']; products=raw['products']; sellers=raw['sellers']; customers=raw['customers']
cx=sqlite3.connect(':memory:')
for n,d in raw.items():d.to_sql(n,cx,index=False)
SQL="""
WITH item AS (
 SELECT i.order_id, COUNT(*) item_count, SUM(i.price) item_value, SUM(i.freight_value) freight,
 COUNT(DISTINCT i.seller_id) seller_count, COUNT(DISTINCT p.product_category_name) nonnull_category_count,
 SUM(CASE WHEN p.product_category_name IS NULL THEN 1 ELSE 0 END) null_category_items,
 MIN(p.product_category_name) only_category, MIN(i.seller_id) only_seller,
 MIN(i.shipping_limit_date) min_shipping_limit, MAX(i.shipping_limit_date) max_shipping_limit
 FROM order_items i LEFT JOIN products p ON i.product_id=p.product_id GROUP BY i.order_id
), pay AS (SELECT order_id, COUNT(*) payment_count, SUM(payment_value) payment_value FROM order_payments GROUP BY order_id),
rev AS (SELECT order_id, COUNT(*) review_count, COUNT(DISTINCT review_score) distinct_score_count FROM order_reviews GROUP BY order_id)
SELECT o.*,c.customer_unique_id,c.customer_state,i.item_count,i.item_value,i.freight,i.seller_count,
i.nonnull_category_count,i.null_category_items,i.only_category,i.only_seller,i.min_shipping_limit,i.max_shipping_limit,
s.seller_state,pay.payment_count,pay.payment_value,rev.review_count,rev.distinct_score_count
FROM orders o LEFT JOIN customers c ON o.customer_id=c.customer_id
LEFT JOIN item i ON o.order_id=i.order_id LEFT JOIN sellers s ON i.only_seller=s.seller_id AND i.seller_count=1
LEFT JOIN pay ON o.order_id=pay.order_id LEFT JOIN rev ON o.order_id=rev.order_id
"""
(O/'deep_analysis.sql').write_text(SQL,encoding='utf-8')
d=pd.read_sql_query(SQL,cx);assert len(d)==len(orders) and d.order_id.is_unique
r=reviews.copy();r['review_answer_timestamp']=pd.to_datetime(r.review_answer_timestamp);r['review_creation_date']=pd.to_datetime(r.review_creation_date)
last=r.sort_values(['review_answer_timestamp','review_id']).groupby('order_id').tail(1)[['order_id','review_score','review_creation_date','review_answer_timestamp']]
d=d.merge(last,on='order_id',validate='one_to_one',how='left')
for c in ['order_purchase_timestamp','order_delivered_carrier_date','order_delivered_customer_date','order_estimated_delivery_date','min_shipping_limit','max_shipping_limit']:d[c]=pd.to_datetime(d[c])
d['valid_delivery']=(d.order_status=='delivered')&d.order_delivered_customer_date.notna()
d['mixed_null_category']=(d.nonnull_category_count==1)&(d.null_category_items>0)
d['single_category_strict']=(d.nonnull_category_count==1)&(d.null_category_items==0)
d['carrier_days']=(d.order_delivered_carrier_date-d.order_purchase_timestamp).dt.total_seconds()/86400
d['transit_days']=(d.order_delivered_customer_date-d.order_delivered_carrier_date).dt.total_seconds()/86400
d['shipping_limit_to_carrier_days']=(d.order_delivered_carrier_date-d.max_shipping_limit).dt.total_seconds()/86400
d['signed_delay_days']=(d.order_delivered_customer_date.dt.normalize()-d.order_estimated_delivery_date.dt.normalize()).dt.days
d['late']=d.signed_delay_days>0
d['purchase_month']=d.order_purchase_timestamp.dt.to_period('M').astype(str)
d['bad12']=(d.review_score<=2).astype(int)
q=d[d.valid_delivery].copy(); a=q[q.review_score.notna()].copy()
assert len(q)==96470 and len(a)==95824 and a.order_id.is_unique

def jsonable(x):
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.floating,)):return float(x)
 raise TypeError(type(x))
def ci(p,n):
 z=1.96; den=1+z*z/n;center=(p+z*z/(2*n))/den;half=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den;return center-half,center+half
def grouped(x,col):
 t=x.groupby(col,observed=True,dropna=False).agg(n=('order_id','size'),late_n=('late','sum'),bad_n=('bad12','sum'),carrier_median=('carrier_days','median'),transit_median=('transit_days','median')).reset_index()
 t['late_rate']=t.late_n/t.n;t['bad_rate']=t.bad_n/t.n;t['bad_low'],t['bad_high']=ci(t.bad_rate,t.n)
 return t

bins=[-np.inf,-1,0,1,3,7,14,np.inf];labels=['提前≥1天','准时','延迟1天','延迟2–3天','延迟4–7天','延迟8–14天','延迟≥15天']
a['delay_group']=pd.cut(a.signed_delay_days,bins=bins,labels=labels)
delay=grouped(a,'delay_group');delay.to_csv(O/'delay_gradient.csv',index=False,encoding='utf-8-sig')

eligible=a.purchase_month.value_counts().loc[lambda s:s>=100].index
m=a[a.purchase_month.isin(eligible)].dropna(subset=['item_value','freight','item_count','customer_state','customer_unique_id']).copy()
def design(frame,gradient=False):
 x=pd.DataFrame(index=frame.index)
 if gradient:x=pd.get_dummies(frame.delay_group,prefix='delay',dtype=float).drop(columns=['delay_准时'])
 else:x['late']=frame.late.astype(float)
 x['log_value']=np.log1p(frame.item_value);x['log_freight']=np.log1p(frame.freight);x['log_items']=np.log1p(frame.item_count)
 x=pd.concat([x,pd.get_dummies(frame.customer_state,prefix='state',drop_first=True,dtype=float),pd.get_dummies(frame.purchase_month,prefix='month',drop_first=True,dtype=float)],axis=1)
 return sm.add_constant(x.astype(float),has_constant='add')
X=design(m);y=m.bad12.astype(float)
model=sm.GLM(y,X,family=sm.families.Binomial()).fit(maxiter=100,tol=1e-10)
cluster=sm.GLM(y,X,family=sm.families.Binomial()).fit(maxiter=100,tol=1e-10,cov_type='cluster',cov_kwds={'groups':m.customer_unique_id})
assert model.converged and cluster.converged
previous_models=json.loads((P/'project'/'metrics.json').read_text(encoding='utf-8'))['models'];old=previous_models['main']
def coef_result(fit,key):
 b=float(fit.params[key]);se=float(fit.bse[key]);return {'beta':b,'se':se,'or':float(np.exp(b)),'ci95':[float(np.exp(b-1.96*se)),float(np.exp(b+1.96*se))],'z':b/se,'p':float(2*norm.sf(abs(b/se)))}
gradient_score=np.asarray(model.model.score(model.params))
audit={'n':len(m),'events':int(y.sum()),'unique_customers':int(m.customer_unique_id.nunique()),'statsmodels_converged':bool(model.converged),'iteration_count':int(model.fit_history['iteration']),'score_gradient_max_abs':float(np.abs(gradient_score).max()),'main':coef_result(model,'late'),'cluster_customer':coef_result(cluster,'late'),'old_scipy':old,'or_difference':float(np.exp(model.params['late'])-old['late_or']),'se_ratio_cluster_to_classic':float(cluster.bse['late']/model.bse['late'])}

Xg=design(m,True);gm=sm.GLM(y,Xg,family=sm.families.Binomial()).fit(maxiter=100,tol=1e-10)
gc=sm.GLM(y,Xg,family=sm.families.Binomial()).fit(maxiter=100,tol=1e-10,cov_type='cluster',cov_kwds={'groups':m.customer_unique_id})
gradient={k:coef_result(gc,k) for k in Xg.columns if k.startswith('delay_')};
last_two=[k for k in Xg.columns if k.startswith('delay_')][-2:]
contrast=float(gc.params[last_two[0]]-gc.params[last_two[1]])
contrast_se=float(np.sqrt(gc.cov_params().loc[last_two[0],last_two[0]]+gc.cov_params().loc[last_two[1],last_two[1]]-2*gc.cov_params().loc[last_two[0],last_two[1]]))

early_review=a.review_answer_timestamp<a.order_delivered_customer_date
early_creation=a.review_creation_date<a.order_delivered_customer_date
timing_cross=a.assign(answer_before_delivery=early_review).groupby(['late','answer_before_delivery']).agg(n=('order_id','size'),bad_n=('bad12','sum')).reset_index()
timing_cross['bad_rate']=timing_cross.bad_n/timing_cross.n
timing_cross.to_csv(O/'review_timing_cross.csv',index=False,encoding='utf-8-sig')
mt=m[~(m.review_answer_timestamp<m.order_delivered_customer_date)].copy()
timing_model=sm.GLM(mt.bad12.astype(float),design(mt),family=sm.families.Binomial()).fit(maxiter=100,tol=1e-10)
mc=m[~(m.review_creation_date<m.order_delivered_customer_date)].copy()
creation_model=sm.GLM(mc.bad12.astype(float),design(mc),family=sm.families.Binomial()).fit(maxiter=100,tol=1e-10)
strict_model_data=m[m.single_category_strict].copy()
top_categories=strict_model_data.only_category.value_counts().head(15).index
category_design=pd.concat([design(strict_model_data),pd.get_dummies(strict_model_data.only_category.where(strict_model_data.only_category.isin(top_categories),'other'),prefix='category',drop_first=True,dtype=float)],axis=1)
strict_category_model=sm.GLM(strict_model_data.bad12.astype(float),category_design,family=sm.families.Binomial()).fit(maxiter=100,tol=1e-10)

# Time holdout: no purchase-month dummies; score 2018 after training on 2017 or earlier.
train=m[m.order_purchase_timestamp.dt.year<=2017];test=m[m.order_purchase_timestamp.dt.year==2018]
def predictive_design(x):
 z=pd.DataFrame({'late':x.late.astype(float),'log_value':np.log1p(x.item_value),'log_freight':np.log1p(x.freight),'log_items':np.log1p(x.item_count)},index=x.index)
 return pd.concat([z,pd.get_dummies(x.customer_state,prefix='state',dtype=float)],axis=1)
xt=predictive_design(train);xv=predictive_design(test).reindex(columns=xt.columns,fill_value=0)
pred=LogisticRegression(max_iter=2000).fit(xt,train.bad12).predict_proba(xv)[:,1]
holdout={'train_n':len(train),'test_n':len(test),'train_end':'2017-12','test_start':'2018-01','test_end':str(test.purchase_month.max()),'test_auc':float(roc_auc_score(test.bad12,pred)),'test_brier':float(brier_score_loss(test.bad12,pred)),'test_event_rate':float(test.bad12.mean()),'test_pred_mean':float(pred.mean())}

# Stage analysis: no seller attribution for multi-seller orders.
stage=q.copy();stage['valid_carrier']=(stage.carrier_days>=0)&(stage.transit_days>=0)
stage_valid=stage[stage.valid_carrier]
limit_known=stage_valid[stage_valid.max_shipping_limit.notna()].copy()
limit_known['after_all_item_limits']=limit_known.order_delivered_carrier_date>limit_known.max_shipping_limit
limit_stage=limit_known.groupby('after_all_item_limits').agg(n=('order_id','size'),late_n=('late','sum'),carrier_median=('carrier_days','median'),transit_median=('transit_days','median')).reset_index()
limit_stage['late_rate']=limit_stage.late_n/limit_stage.n
limit_stage.to_csv(O/'shipping_limit_stage.csv',index=False,encoding='utf-8-sig')
stage_groups=stage_valid.groupby('late').agg(n=('order_id','size'),carrier_median=('carrier_days','median'),carrier_p90=('carrier_days',lambda s:s.quantile(.9)),transit_median=('transit_days','median'),transit_p90=('transit_days',lambda s:s.quantile(.9))).reset_index()
stage_groups.to_csv(O/'stage_by_late.csv',index=False,encoding='utf-8-sig')
region=grouped(a,'customer_state');region['share_all_late']=region.late_n/a.late.sum();region.sort_values('late_n',ascending=False).to_csv(O/'region_priority.csv',index=False,encoding='utf-8-sig')
strict=a[a.single_category_strict];category=grouped(strict,'only_category');category.sort_values('late_n',ascending=False).to_csv(O/'category_priority_strict.csv',index=False,encoding='utf-8-sig')
pair=stage_valid[stage_valid.seller_count==1].groupby(['seller_state','customer_state']).agg(n=('order_id','size'),late_n=('late','sum'),carrier_median=('carrier_days','median'),transit_median=('transit_days','median')).reset_index()
pair['late_rate']=pair.late_n/pair.n;pair[pair.n>=100].sort_values('late_n',ascending=False).to_csv(O/'state_lane_priority.csv',index=False,encoding='utf-8-sig')

result={'category_null':{'mixed_null_orders_all':int(d.mixed_null_category.sum()),'mixed_null_valid_delivery':int(q.mixed_null_category.sum()),'mixed_null_reviewed':int(a.mixed_null_category.sum()),'old_single_category_reviewed':int(((a.nonnull_category_count==1)&a.only_category.notna()).sum()),'strict_single_category_reviewed':len(strict)},
 'timing':{'negative_carrier_valid_delivery':int((q.carrier_days<0).sum()),'missing_carrier_valid_delivery':int(q.carrier_days.isna().sum()),'negative_transit_valid_delivery':int((q.transit_days<0).sum()),'valid_stage_n':len(stage_valid),'valid_carrier_median':float(stage_valid.carrier_days.median()),'valid_carrier_p90':float(stage_valid.carrier_days.quantile(.9)),'valid_transit_median':float(stage_valid.transit_days.median()),'valid_transit_p90':float(stage_valid.transit_days.quantile(.9)),'review_answer_before_delivery':int(early_review.sum()),'review_creation_before_delivery':int(early_creation.sum()),'timing_clean_model_n':len(mt),'timing_clean_late_or':float(np.exp(timing_model.params['late'])),'timing_clean_late_ci95':coef_result(timing_model,'late')['ci95']},
 'model_audit':audit,'adjusted_delay_gradient':gradient,'last_two_delay_bins_difference_p':float(2*norm.sf(abs(contrast/contrast_se))),'gradient_model_converged':bool(gm.converged),'gradient_cluster_model_converged':bool(gc.converged),'creation_after_delivery_model':{'n':len(mc),'late_or':float(np.exp(creation_model.params['late'])),'late_ci95':coef_result(creation_model,'late')['ci95']},'strict_category_model':{'n':len(strict_model_data),'late_or':float(np.exp(strict_category_model.params['late'])),'late_ci95':coef_result(strict_category_model,'late')['ci95'],'converged':bool(strict_category_model.converged),'old_single_category_or':previous_models['single_category_adjusted']['late_or']},'time_holdout':holdout,'multi_seller_valid_delivery':int((q.seller_count>1).sum()),'multi_category_or_null_valid_delivery':int((~q.single_category_strict).sum()),'after_all_item_shipping_limits':int(limit_known.after_all_item_limits.sum()),'limit_known_stage_n':len(limit_known)}
(O/'deep_metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=jsonable),encoding='utf-8')
plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans'];plt.rcParams['axes.unicode_minus']=False
fig,ax=plt.subplots(figsize=(9,4));xx=np.arange(len(delay));ax.bar(xx,delay.bad_rate*100,color='#377eb8');ax.errorbar(xx,delay.bad_rate*100,yerr=[(delay.bad_rate-delay.bad_low)*100,(delay.bad_high-delay.bad_rate)*100],fmt='none',ecolor='#222');ax.set_xticks(xx,delay.delay_group,rotation=25,ha='right');ax.set_ylabel('1–2星差评率 (%)');ax.set_title('按承诺日期偏差分组的差评率与95% Wilson区间');fig.tight_layout();fig.savefig(O/'delay_gradient.png',dpi=170);plt.close(fig)
print(json.dumps(result,ensure_ascii=False,indent=2,default=jsonable))
