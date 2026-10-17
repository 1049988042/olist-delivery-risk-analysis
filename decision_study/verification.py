"""Independent SQL allocation audit and descriptive rule-complexity contrasts."""
from pathlib import Path
import hashlib,sqlite3
import numpy as np
import pandas as pd

def audit_allocations(root,out,rules,results,seed):
    orders=pd.read_csv(root/'olist_orders_dataset.csv')
    reviews=pd.read_csv(root/'olist_order_reviews_dataset.csv')
    customers=pd.read_csv(root/'olist_customers_dataset.csv',usecols=['customer_id','customer_state'])
    cells=pd.DataFrame([{'cell':key,'score':value['score']} for key,value in rules['cells'].items()])
    geo=pd.DataFrame([{'geo_key':key,'score':value['score']} for key,value in rules['supported_geo_cells'].items()],columns=['geo_key','score'])
    sql="""
WITH r AS (
 SELECT *,ROW_NUMBER() OVER(PARTITION BY order_id ORDER BY review_answer_timestamp,review_id) rn FROM reviews
), joined AS (
 SELECT o.*,c.customer_state,r.review_answer_timestamp,r.review_score,
 datetime(date(o.order_estimated_delivery_date),'+1 day') decision_time
 FROM orders o LEFT JOIN r ON o.order_id=r.order_id AND r.rn=1
 LEFT JOIN customers c ON o.customer_id=c.customer_id
), eligible AS (
 SELECT *,CASE WHEN order_delivered_carrier_date >= order_purchase_timestamp AND order_delivered_carrier_date <= decision_time THEN 1 ELSE 0 END stage,
 CAST(strftime('%s',decision_time) AS INTEGER)-CAST(strftime('%s',order_purchase_timestamp) AS INTEGER) age_seconds
 FROM joined WHERE decision_time >= '2018-01-01' AND decision_time < '2018-07-01'
 AND order_purchase_timestamp >= '2017-01-01' AND order_purchase_timestamp <= decision_time
 AND (order_delivered_customer_date IS NULL OR order_delivered_customer_date > decision_time)
 AND (review_answer_timestamp IS NULL OR review_answer_timestamp > decision_time)
), ages AS (
 SELECT *,CASE WHEN stage=1 THEN CAST(strftime('%s',decision_time) AS INTEGER)-CAST(strftime('%s',order_delivered_carrier_date) AS INTEGER) ELSE age_seconds END stage_seconds,
 CASE WHEN review_answer_timestamp > decision_time AND review_answer_timestamp <= datetime(decision_time,'+30 days') AND review_score <= 2 THEN 1 ELSE 0 END event
 FROM eligible
), keys AS (
 SELECT *, CASE WHEN stage=1 THEN 'in_transit' ELSE 'handoff_unconfirmed' END ||
 CASE WHEN stage_seconds > CASE WHEN stage=1 THEN :transit_cutoff ELSE :unconfirmed_cutoff END * 86400 THEN '|long' ELSE '|short' END cell
 FROM ages
), scores AS (
 SELECT k.*,c.score base_score,COALESCE(g.score,c.score) geo_score,tie_hash(k.order_id) tie,
 COUNT(*) OVER(PARTITION BY k.decision_time) day_n
 FROM keys k LEFT JOIN cells c ON k.cell=c.cell LEFT JOIN geo g ON k.cell || '|' || k.customer_state=g.geo_key
), ranked AS (
 SELECT *,ROW_NUMBER() OVER(PARTITION BY decision_time ORDER BY __ORDER__) priority_number FROM scores
)
SELECT COUNT(*) selected_orders,SUM(event) selected_bad_events,
 SUM(CASE WHEN stage=0 THEN 1 ELSE 0 END) selected_handoff_unconfirmed,
 SUM(CASE WHEN order_status='delivered' THEN 1 ELSE 0 END) selected_final_delivered,
 SUM(CASE WHEN order_status='canceled' THEN 1 ELSE 0 END) selected_final_canceled,
 SUM(CASE WHEN order_status='unavailable' THEN 1 ELSE 0 END) selected_final_unavailable,
 SUM(CASE WHEN order_status!='delivered' THEN event ELSE 0 END) events_final_status_not_delivered
FROM ranked WHERE priority_number <= CAST(day_n*:capacity+1e-12 AS INTEGER);
"""
    (out/'allocation_validation.sql').write_text(sql,encoding='utf-8')
    order_by={'random_hash_draw':'tie ASC','oldest_purchase':'age_seconds DESC,tie ASC','stage_wait':'stage ASC,stage_seconds DESC,tie ASC','four_cell':'base_score DESC,stage_seconds DESC,tie ASC','geo_four_cell':'geo_score DESC,stage_seconds DESC,tie ASC'}
    rows=[]
    with sqlite3.connect(':memory:') as con:
        for name,table in [('orders',orders),('reviews',reviews),('customers',customers),('cells',cells),('geo',geo)]:table.to_sql(name,con,index=False)
        con.create_function('tie_hash',1,lambda x:int(hashlib.sha256((str(seed)+'|'+x).encode()).hexdigest()[:15],16))
        for strategy,order in order_by.items():
            for q in [.1,.2,.3]:
                params={'capacity':q,'transit_cutoff':rules['thresholds_days']['True'],'unconfirmed_cutoff':rules['thresholds_days']['False']}
                row=pd.read_sql_query(sql.replace('__ORDER__',order),con,params=params).iloc[0].to_dict()
                actual=results[(results.strategy==strategy)&(results.capacity_fraction==q)].iloc[0]
                assert int(row['selected_orders'])==int(actual.selected_orders),(strategy,q,row,actual.to_dict())
                assert int(row['selected_bad_events'])==int(actual.selected_bad_events),(strategy,q,row,actual.to_dict())
                row.update(strategy=strategy,capacity_fraction=q,sql_pandas_match=True,order_by=order)
                rows.append(row)
    output=pd.DataFrame(rows);output.to_csv(out/'allocation_crosscheck_and_outcome_context.csv',index=False,encoding='utf-8-sig')
    return {'sql_independent_feature_scoring_ranking_and_daily_allocation_match':True,'strategy_capacity_combinations_checked':len(rows),'selection_outcome_context':output.to_dict('records')}

def complexity_contrasts(out,daily,seed,repetitions):
    rows=[]
    for q in [.1,.2,.3]:
        subset=daily[daily.capacity_fraction==q]
        week={}
        for name in ['geo_four_cell','four_cell','stage_wait']:
            week[name]=subset[subset.strategy==name].groupby('week')[['selected_bad_events','candidate_bad_events']].sum()
        reference=week['stage_wait'];idx=np.random.default_rng(seed+1).integers(0,len(reference),size=(repetitions,len(reference)))
        denominator=reference.candidate_bad_events.to_numpy()[idx].sum(axis=1)
        for comparator in ['stage_wait','four_cell']:
            observed=week['geo_four_cell'].selected_bad_events.sum()-week[comparator].selected_bad_events.sum()
            delta=(week['geo_four_cell'].selected_bad_events.to_numpy()-week[comparator].selected_bad_events.to_numpy())[idx].sum(axis=1)
            low,high=np.quantile(100*delta/denominator,[.025,.975])
            rows.append({'capacity_fraction':q,'strategy':'geo_four_cell','comparator':comparator,'additional_observed_events':float(observed),'recall_gain_pp':float(100*observed/reference.candidate_bad_events.sum()),'ci95_low_pp':float(low),'ci95_high_pp':float(high),'status':'descriptive_complexity_audit_not_used_to_retune'})
    output=pd.DataFrame(rows);output.to_csv(out/'complexity_increment.csv',index=False,encoding='utf-8-sig')
    return output.to_dict('records')
