
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
