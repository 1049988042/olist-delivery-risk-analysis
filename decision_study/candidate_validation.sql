
WITH r AS (
 SELECT *,ROW_NUMBER() OVER(PARTITION BY order_id ORDER BY review_answer_timestamp,review_id) rn FROM reviews
), joined AS (
 SELECT o.*,r.review_answer_timestamp,r.review_score,datetime(date(o.order_estimated_delivery_date),'+1 day') decision_time
 FROM orders o LEFT JOIN r ON o.order_id=r.order_id AND r.rn=1
), eligible AS (
 SELECT * FROM joined WHERE order_purchase_timestamp >= '2017-01-01'
 AND date(order_estimated_delivery_date) BETWEEN '2017-01-01' AND '2018-06-30'
 AND order_purchase_timestamp <= decision_time
 AND (order_delivered_customer_date IS NULL OR order_delivered_customer_date > decision_time)
 AND (review_answer_timestamp IS NULL OR review_answer_timestamp > decision_time)
)
SELECT CASE WHEN decision_time >= '2018-01-01' AND decision_time < '2018-07-01' THEN 'test' ELSE 'other' END period,
 COUNT(*) orders,
 SUM(CASE WHEN review_answer_timestamp > decision_time AND review_answer_timestamp <= datetime(decision_time,'+30 days') THEN 1 ELSE 0 END) reviews_30d,
 SUM(CASE WHEN review_answer_timestamp > decision_time AND review_answer_timestamp <= datetime(decision_time,'+30 days') AND review_score <= 2 THEN 1 ELSE 0 END) bad_30d
FROM eligible GROUP BY period;
