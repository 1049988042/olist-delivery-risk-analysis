from pathlib import Path
import csv
import json
from datetime import datetime
from collections import Counter, defaultdict

ROOT = Path(__file__).parent
FILES = sorted(ROOT.glob('*.csv'))
KEYS = {
 'olist_customers_dataset.csv':['customer_id','customer_unique_id'],
 'olist_geolocation_dataset.csv':['geolocation_zip_code_prefix'],
 'olist_order_items_dataset.csv':['order_id','order_item_id','seller_id','product_id'],
 'olist_order_payments_dataset.csv':['order_id','payment_sequential'],
 'olist_order_reviews_dataset.csv':['review_id','order_id'],
 'olist_orders_dataset.csv':['order_id','customer_id'],
 'olist_products_dataset.csv':['product_id'],
 'olist_sellers_dataset.csv':['seller_id'],
 'product_category_name_translation.csv':['product_category_name']}

def read(path):
 with path.open(encoding='utf-8-sig',newline='') as f:
  return list(csv.DictReader(f))

def summary(rows, name):
 cols=list(rows[0])
 out={'rows':len(rows),'columns':cols,'missing':{},'key_candidates':{}}
 for c in cols:
  vals=[r[c] for r in rows]
  out['missing'][c]=sum(v=='' for v in vals)
  nonempty=[v for v in vals if v!='']
  def is_number(v):
   try: float(v); return True
   except ValueError: return False
  def is_date(v):
   try: datetime.fromisoformat(v); return True
   except ValueError: return False
  out.setdefault('inferred_types',{})[c]=('empty' if not nonempty else 'numeric' if all(map(is_number,nonempty)) else 'timestamp' if all(map(is_date,nonempty)) else 'text')
  if c in KEYS[name]:
   nonempty=[v for v in vals if v!='']
   out['key_candidates'][c]={'distinct':len(set(nonempty)),'duplicate_rows':len(nonempty)-len(set(nonempty))}
 return out

def main():
 data={p.name:read(p) for p in FILES}
 out={'tables':{n:summary(r,n) for n,r in data.items()}}
 r=data['olist_order_reviews_dataset.csv']
 by_id=defaultdict(list); by_order=defaultdict(list); by_pair=defaultdict(list)
 for row in r:
  by_id[row['review_id']].append(row)
  by_order[row['order_id']].append(row)
  by_pair[(row['order_id'],row['review_id'])].append(row)
 full=Counter(tuple(row.items()) for row in r)
 def examples(groups, pred, limit=5):
  return [{'key':k,'rows':len(v),'scores':sorted(set(x['review_score'] for x in v))} for k,v in groups.items() if pred(v)][:limit]
 out['reviews']={
  'unique_order_id':len(by_order),'unique_review_id':len(by_id),'unique_pairs':len(by_pair),
  'review_ids_multiple_orders':sum(len(set(x['order_id'] for x in v))>1 for v in by_id.values()),
  'rows_in_review_ids_multiple_orders':sum(len(v) for v in by_id.values() if len(set(x['order_id'] for x in v))>1),
  'orders_multiple_review_ids':sum(len(set(x['review_id'] for x in v))>1 for v in by_order.values()),
  'rows_in_orders_multiple_review_ids':sum(len(v) for v in by_order.values() if len(set(x['review_id'] for x in v))>1),
  'repeated_pairs':sum(len(v)>1 for v in by_pair.values()),
  'excess_rows_repeated_pairs':sum(len(v)-1 for v in by_pair.values()),
  'exact_duplicate_groups':sum(n>1 for n in full.values()),
  'excess_exact_duplicate_rows':sum(n-1 for n in full.values()),
  'orders_conflicting_scores':sum(len(set(x['review_score'] for x in v))>1 for v in by_order.values()),
  'review_ids_conflicting_scores':sum(len(set(x['review_score'] for x in v))>1 for v in by_id.values()),
  'repeated_pair_conflicting_scores':sum(len(set(x['review_score'] for x in v))>1 for v in by_pair.values()),
  'examples':{
   'review_ids_multiple_orders':examples(by_id,lambda v:len(set(x['order_id'] for x in v))>1),
   'orders_multiple_review_ids':examples(by_order,lambda v:len(set(x['review_id'] for x in v))>1),
   'repeated_pairs':examples(by_pair,lambda v:len(v)>1),
   'orders_conflicting_scores':examples(by_order,lambda v:len(set(x['review_score'] for x in v))>1),
   'review_ids_conflicting_scores':examples(by_id,lambda v:len(set(x['review_score'] for x in v))>1)}}
 o=data['olist_orders_dataset.csv']
 status=Counter(x['order_status'] for x in o)
 out['orders']={'status':status,'delivered_missing_delivery':sum(x['order_status']=='delivered' and not x['order_delivered_customer_date'] for x in o),'canceled_with_delivery':sum(x['order_status']=='canceled' and x['order_delivered_customer_date']!='' for x in o)}
 out['relationships']={}
 out['composite_keys']={
  'items_order_item':len({(x['order_id'],x['order_item_id']) for x in data['olist_order_items_dataset.csv']}),
  'payments_order_sequence':len({(x['order_id'],x['payment_sequential']) for x in data['olist_order_payments_dataset.csv']})}
 orderids={x['order_id'] for x in o}
 reviewids=set(by_order)
 out['coverage']={'orders_without_review':len(orderids-reviewids),'delivered_candidate_without_review':sum(x['order_status']=='delivered' and bool(x['order_delivered_customer_date']) and x['order_id'] not in reviewids for x in o)}
 checks=[('orders.customer_id','olist_orders_dataset.csv','customer_id','olist_customers_dataset.csv','customer_id'),('items.order_id','olist_order_items_dataset.csv','order_id','olist_orders_dataset.csv','order_id'),('payments.order_id','olist_order_payments_dataset.csv','order_id','olist_orders_dataset.csv','order_id'),('reviews.order_id','olist_order_reviews_dataset.csv','order_id','olist_orders_dataset.csv','order_id'),('items.product_id','olist_order_items_dataset.csv','product_id','olist_products_dataset.csv','product_id'),('items.seller_id','olist_order_items_dataset.csv','seller_id','olist_sellers_dataset.csv','seller_id'),('products.category','olist_products_dataset.csv','product_category_name','product_category_name_translation.csv','product_category_name')]
 for label,child,ck,parent,pk in checks:
  parent_keys={x[pk] for x in data[parent] if x[pk]}
  vals=[x[ck] for x in data[child]]
  out['relationships'][label]={'unmatched_rows':sum(v!='' and v not in parent_keys for v in vals),'unmatched_distinct_keys':len({v for v in vals if v!='' and v not in parent_keys}),'blank_foreign_keys':sum(v=='' for v in vals)}
 print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
