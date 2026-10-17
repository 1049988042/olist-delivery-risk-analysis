
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
