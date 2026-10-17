
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
