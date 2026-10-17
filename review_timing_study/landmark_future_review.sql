
WITH ranked AS (
 SELECT *, ROW_NUMBER() OVER(PARTITION BY order_id ORDER BY review_answer_timestamp, review_id) rn
 FROM reviews
), joined AS (
 SELECT o.*,r.review_answer_timestamp,r.review_score,
 datetime(date(o.order_estimated_delivery_date),'+1 day') landmark
 FROM orders o LEFT JOIN ranked r ON o.order_id=r.order_id AND r.rn=1
), eligible AS (
 SELECT *,CASE WHEN order_delivered_customer_date IS NULL OR order_delivered_customer_date > landmark THEN 1 ELSE 0 END pending_at_landmark
 FROM joined
 WHERE order_purchase_timestamp >= '2017-01-01'
 AND date(order_estimated_delivery_date) BETWEEN '2017-01-01' AND '2018-06-30'
 AND order_purchase_timestamp <= landmark
 AND (review_answer_timestamp IS NULL OR review_answer_timestamp >= landmark)
)
SELECT pending_at_landmark,COUNT(*) eligible_orders,
 SUM(CASE WHEN review_answer_timestamp < datetime(landmark,'+30 days') THEN 1 ELSE 0 END) reviews_in_30d,
 SUM(CASE WHEN review_answer_timestamp < datetime(landmark,'+30 days') AND CAST(review_score AS INTEGER) <= 2 THEN 1 ELSE 0 END) bad_in_30d
FROM eligible GROUP BY pending_at_landmark;
