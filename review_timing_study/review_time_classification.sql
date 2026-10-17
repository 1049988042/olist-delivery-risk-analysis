
WITH ranked AS (
 SELECT *, ROW_NUMBER() OVER(PARTITION BY order_id ORDER BY review_answer_timestamp DESC, review_id DESC) rn
 FROM reviews
), classified AS (
 SELECT o.order_id, CAST(r.review_score AS INTEGER) review_score,
 CASE
 WHEN r.review_answer_timestamp IS NULL OR o.order_estimated_delivery_date IS NULL THEN 'unclassified'
 WHEN o.order_delivered_customer_date IS NOT NULL AND o.order_delivered_customer_date <= r.review_answer_timestamp
 THEN CASE WHEN date(o.order_delivered_customer_date) > date(o.order_estimated_delivery_date)
           THEN 'delivered_late' ELSE 'delivered_on_time' END
 WHEN date(r.review_answer_timestamp) > date(o.order_estimated_delivery_date) THEN 'pending_overdue'
 ELSE 'pending_within_promise' END state
 FROM orders o JOIN ranked r ON o.order_id=r.order_id AND r.rn=1
)
SELECT state, COUNT(*) orders, SUM(CASE WHEN review_score <= 2 THEN 1 ELSE 0 END) bad_orders
FROM classified GROUP BY state;
