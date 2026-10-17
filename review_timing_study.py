"""Review-time fulfillment audit. Standalone, read-only source access, no models.

Reproduce: python review_timing_study.py
Outputs: review_timing_study/ (previous project outputs are never overwritten).
"""
from pathlib import Path
import hashlib
import json
import sqlite3
import platform
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'review_timing_study'
OUT.mkdir(exist_ok=True)
LABELS = {
    'pending_within_promise': '评价时未见送达，承诺日期未过',
    'pending_overdue': '评价时未见送达，承诺日期已过',
    'delivered_on_time': '评价时已送达，按承诺日期准时',
    'delivered_late': '评价时已送达，超过承诺日期',
    'delivery_time_ambiguous': '评价与送达时间接近，顺序不确定',
    'unclassified': '关键时间缺失或解析失败',
    'promise_boundary_ambiguous': '承诺日期边界附近，时点不确定',
}
STATE_ORDER = list(LABELS)[:4]

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()

protected = sorted(ROOT.glob('*.csv')) + sorted(ROOT.glob('*.md')) + sorted(ROOT.glob('*.json')) + [
    ROOT / 'run_project.py', ROOT / 'deep_audit.py', ROOT / 'audit_olist.py',
    ROOT / 'requirements.txt',
]
protected += [p for directory in ['project','deep_study'] for p in (ROOT/directory).rglob('*') if p.is_file()]
before = {str(p.relative_to(ROOT)): digest(p) for p in protected if p.exists()}
orders = pd.read_csv(ROOT / 'olist_orders_dataset.csv', dtype='string')
reviews = pd.read_csv(ROOT / 'olist_order_reviews_dataset.csv', dtype='string')
assert orders.order_id.is_unique
assert len(reviews) == 99224 and len(orders) == 99441
raw_orders = orders.copy()
raw_reviews = reviews.copy()

precision = []
for name, frame, col in [
    ('reviews', reviews, 'review_creation_date'),
    ('reviews', reviews, 'review_answer_timestamp'),
    ('orders', orders, 'order_delivered_customer_date'),
    ('orders', orders, 'order_estimated_delivery_date'),
    ('orders', orders, 'order_purchase_timestamp'),
]:
    raw = frame[col]
    parsed = pd.to_datetime(raw, errors='coerce')
    valid = parsed.dropna()
    precision.append({
        'table': name, 'field': col, 'rows': len(raw),
        'nonmissing': int(raw.notna().sum()),
        'parse_failures_nonmissing': int((raw.notna() & parsed.isna()).sum()),
        'midnight_n': int((valid == valid.dt.normalize()).sum()),
        'midnight_fraction': float((valid == valid.dt.normalize()).mean()),
        'nonzero_seconds_n': int((valid.dt.second != 0).sum()),
        'fractional_second_strings_n': int(raw.str.contains(r'\d{2}:\d{2}:\d{2}\.\d+', na=False).sum()),
        'timezone_token_n': int(raw.str.contains(r'(?:Z|[+-]\d{2}:?\d{2})$', na=False).sum()),
        'format_yyyy_mm_dd_hh_mm_ss_n': int(raw.str.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', na=False).sum()),
        'parsed_timezone': str(parsed.dt.tz),
        'min': str(valid.min()), 'max': str(valid.max()),
    })
    frame[col] = parsed
precision = pd.DataFrame(precision)
assert precision.parse_failures_nonmissing.sum() == 0
precision.to_csv(OUT / 'timestamp_precision.csv', index=False, encoding='utf-8-sig')
reviews.loc[reviews.review_creation_date != reviews.review_creation_date.dt.normalize(), 'review_creation_date'].value_counts().sort_index().rename_axis('creation_timestamp').reset_index(name='review_events').to_csv(OUT/'nonmidnight_creation_dates.csv',index=False,encoding='utf-8-sig')
reviews['review_score'] = pd.to_numeric(reviews.review_score)

def select_reviews(which):
    ordered = reviews.sort_values(['review_answer_timestamp', 'review_id'], kind='stable')
    selected = ordered.groupby('order_id', sort=False).head(1) if which == 'first' else ordered.groupby('order_id', sort=False).tail(1)
    result = orders.merge(selected, on='order_id', how='inner', validate='one_to_one')
    result['bad12'] = (result.review_score <= 2).astype(int)
    result['deadline_exclusive'] = result.order_estimated_delivery_date.dt.normalize() + pd.Timedelta(days=1)
    result['answer_minus_delivery_hours'] = (result.review_answer_timestamp - result.order_delivered_customer_date).dt.total_seconds() / 3600
    result['reply_before_purchase'] = result.review_answer_timestamp < result.order_purchase_timestamp
    result['reply_date_before_creation'] = result.review_answer_timestamp.dt.normalize() < result.review_creation_date.dt.normalize()
    result['creation_date_before_purchase_date'] = result.review_creation_date.dt.normalize() < result.order_purchase_timestamp.dt.normalize()
    result['delivery_before_purchase'] = result.order_delivered_customer_date < result.order_purchase_timestamp
    result['promise_date_before_purchase_date'] = result.order_estimated_delivery_date.dt.normalize() < result.order_purchase_timestamp.dt.normalize()
    result['strong_sequence_flag'] = result[['reply_before_purchase', 'reply_date_before_creation', 'creation_date_before_purchase_date', 'delivery_before_purchase', 'promise_date_before_purchase_date']].any(axis=1)
    return result

latest = select_reviews('latest')
first = select_reviews('first')
assert len(latest) == len(first) == reviews.order_id.nunique() == 98673

def classify(frame, window_hours=0, date_only=False):
    t = frame.review_answer_timestamp
    d = frame.order_delivered_customer_date
    e = frame.order_estimated_delivery_date
    known = d.notna() & (d <= t)
    ambiguous = pd.Series(False, index=frame.index)
    if window_hours > 0:
        ambiguous = d.notna() & ((t - d).abs() <= pd.Timedelta(hours=window_hours))
    if date_only:
        ambiguous = d.notna() & (d.dt.normalize() == t.dt.normalize())
        known = d.notna() & (d.dt.normalize() < t.dt.normalize())
    overdue = t >= frame.deadline_exclusive
    delivery_late = d.dt.normalize() > e.dt.normalize()
    state = pd.Series('unclassified', index=frame.index, dtype='string')
    valid = t.notna() & e.notna()
    state.loc[valid & ~known & ~overdue] = 'pending_within_promise'
    state.loc[valid & ~known & overdue] = 'pending_overdue'
    state.loc[valid & known & ~delivery_late] = 'delivered_on_time'
    state.loc[valid & known & delivery_late] = 'delivered_late'
    state.loc[valid & ambiguous] = 'delivery_time_ambiguous'
    return state

def wilson(k, n):
    n = np.asarray(n, dtype=float)
    p = np.divide(k, n, out=np.full(n.shape, np.nan), where=n > 0)
    z = 1.959963984540054
    with np.errstate(divide='ignore', invalid='ignore'):
        center = (p + z*z/(2*n)) / (1+z*z/n)
        half = z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return p, center-half, center+half

def summarize(frame, state):
    t = frame.assign(state=state).groupby('state', dropna=False).agg(
        orders=('order_id', 'size'), bad_orders=('bad12', 'sum'),
        missing_final_delivery=('order_delivered_customer_date', lambda s: s.isna().sum()),
    ).reset_index()
    t['bad_rate'], t['ci95_low'], t['ci95_high'] = wilson(t.bad_orders.to_numpy(), t.orders.to_numpy())
    t['state_label'] = t.state.map(LABELS)
    assert t.orders.sum() == len(frame) and t.bad_orders.sum() == frame.bad12.sum()
    return t

latest['state'] = classify(latest)
first['state'] = classify(first)
groups = summarize(latest, latest.state)
groups.to_csv(OUT / 'review_time_states_latest.csv', index=False, encoding='utf-8-sig')
summarize(first, first.state).to_csv(OUT / 'review_time_states_first.csv', index=False, encoding='utf-8-sig')
old_sample = latest[(latest.order_status == 'delivered') & latest.order_delivered_customer_date.notna()]
assert len(old_sample) == 95824
summarize(old_sample, old_sample.state).to_csv(OUT / 'review_time_states_original_sample.csv', index=False, encoding='utf-8-sig')

sens = []
for label, hours, date_only in [('exact', 0, False), ('1h_ambiguous', 1, False), ('6h_ambiguous', 6, False), ('12h_ambiguous', 12, False), ('24h_ambiguous', 24, False), ('48h_ambiguous', 48, False), ('same_day_ambiguous', 0, True)]:
    t = summarize(latest, classify(latest, hours, date_only))
    t.insert(0, 'scenario', label)
    sens.append(t)
sensitivity = pd.concat(sens, ignore_index=True)
sensitivity.to_csv(OUT / 'delivery_timing_sensitivity.csv', index=False, encoding='utf-8-sig')
# Deadline precision is separate from delivery sequence: mark the whole promise
# date, or +/-12h around its end, as uncertain rather than shifting it to midnight.
promise_sens = []
for label, ambiguous in [
    ('promise_date_ambiguous', latest.review_answer_timestamp.dt.normalize() == latest.order_estimated_delivery_date.dt.normalize()),
    ('deadline_plus_minus_12h_ambiguous', (latest.review_answer_timestamp-latest.deadline_exclusive).abs() <= pd.Timedelta(hours=12)),
]:
    s = latest.state.copy()
    s.loc[ambiguous & s.isin(['pending_within_promise', 'pending_overdue'])] = 'promise_boundary_ambiguous'
    t = summarize(latest, s); t.insert(0, 'scenario', label); promise_sens.append(t)
pd.concat(promise_sens).to_csv(OUT / 'promise_boundary_sensitivity.csv', index=False, encoding='utf-8-sig')

missing = latest.assign(delivery_timestamp_missing=latest.order_delivered_customer_date.isna()).groupby(['state', 'delivery_timestamp_missing', 'order_status']).agg(orders=('order_id','size'), bad_orders=('bad12','sum')).reset_index()
missing.to_csv(OUT / 'missing_delivery_and_final_status.csv', index=False, encoding='utf-8-sig')
clean = latest[~latest.strong_sequence_flag]
summarize(clean, clean.state).to_csv(OUT / 'sequence_flag_sensitivity.csv', index=False, encoding='utf-8-sig')
latest[latest.strong_sequence_flag][['order_id', 'review_id', 'order_purchase_timestamp', 'review_creation_date', 'review_answer_timestamp', 'order_delivered_customer_date', 'order_estimated_delivery_date', 'reply_before_purchase', 'reply_date_before_creation', 'creation_date_before_purchase_date', 'delivery_before_purchase', 'promise_date_before_purchase_date']].to_csv(OUT / 'sequence_flag_evidence.csv', index=False, encoding='utf-8-sig')
presence=[]
for present, sub in latest.groupby(latest.order_delivered_customer_date.notna()):
    temp=summarize(sub,sub.state);temp.insert(0,'final_delivery_timestamp_present',bool(present));presence.append(temp)
pd.concat(presence).to_csv(OUT/'final_delivery_presence_groups.csv',index=False,encoding='utf-8-sig')
temporal_cross=old_sample.assign(final_late=old_sample.order_delivered_customer_date.dt.normalize()>old_sample.order_estimated_delivery_date.dt.normalize()).groupby(['state','final_late']).agg(orders=('order_id','size'),bad_orders=('bad12','sum')).reset_index()
temporal_cross.to_csv(OUT/'original_final_delay_vs_review_state.csv',index=False,encoding='utf-8-sig')

# Review creation is date-level. Compare calendar dates to avoid midnight bias.
creation_delta = (latest.review_creation_date-latest.order_delivered_customer_date.dt.normalize()).dt.days
earliest_trigger_day = pd.concat([latest.order_delivered_customer_date.dt.normalize(), latest.order_estimated_delivery_date.dt.normalize()], axis=1).min(axis=1)
trigger_offset = (latest.review_creation_date - earliest_trigger_day).dt.days
trigger_offset.value_counts(dropna=False).sort_index().rename_axis('creation_minus_min_delivery_promise_days').reset_index(name='orders').to_csv(OUT / 'survey_trigger_date_offsets.csv', index=False, encoding='utf-8-sig')
same_day = latest.order_delivered_customer_date.notna() & (latest.order_delivered_customer_date.dt.normalize() == latest.review_answer_timestamp.dt.normalize())

# Prospectively defined landmark: next midnight after promised date. Eligibility
# never uses final order status or whether a review will ultimately be submitted.
base = orders.merge(first[['order_id', 'review_answer_timestamp', 'review_score', 'strong_sequence_flag']], on='order_id', how='left', validate='one_to_one')
base['landmark'] = base.order_estimated_delivery_date.dt.normalize() + pd.Timedelta(days=1)
eligible = ((base.order_purchase_timestamp >= pd.Timestamp('2017-01-01')) &
            (base.order_estimated_delivery_date.dt.normalize() <= pd.Timestamp('2018-06-30')) &
            (base.order_estimated_delivery_date.dt.normalize() >= pd.Timestamp('2017-01-01')) &
            (base.order_purchase_timestamp <= base.landmark) &
            (base.review_answer_timestamp.isna() | (base.review_answer_timestamp >= base.landmark)))
land = base[eligible].copy()
land['pending_at_landmark'] = land.order_delivered_customer_date.isna() | (land.order_delivered_customer_date > land.landmark)
land['review_in_30d'] = land.review_answer_timestamp.notna() & (land.review_answer_timestamp < land.landmark+pd.Timedelta(days=30))
land['bad_in_30d'] = land.review_in_30d & (pd.to_numeric(land.review_score) <= 2)
landmark = land.groupby('pending_at_landmark').agg(eligible_orders=('order_id','size'), reviews_in_30d=('review_in_30d','sum'), bad_in_30d=('bad_in_30d','sum'), missing_final_delivery=('order_delivered_customer_date', lambda s:s.isna().sum())).reset_index()
landmark['review_coverage_30d'] = landmark.reviews_in_30d/landmark.eligible_orders
landmark['bad_rate_among_30d_reviewers'], landmark['bad_rate_ci95_low'], landmark['bad_rate_ci95_high'] = wilson(landmark.bad_in_30d.to_numpy(), landmark.reviews_in_30d.to_numpy())
landmark['observed_bad_review_incidence_30d'] = landmark.bad_in_30d/landmark.eligible_orders
landmark.to_csv(OUT / 'landmark_future_first_review_30d.csv', index=False, encoding='utf-8-sig')
land.groupby(['pending_at_landmark','order_status']).agg(eligible_orders=('order_id','size'),reviews_in_30d=('review_in_30d','sum'),bad_in_30d=('bad_in_30d','sum')).reset_index().to_csv(OUT/'landmark_final_status_context.csv',index=False,encoding='utf-8-sig')
land.assign(landmark_month=land.landmark.dt.to_period('M').astype(str)).groupby(['landmark_month','pending_at_landmark']).agg(eligible_orders=('order_id','size'),reviews_in_30d=('review_in_30d','sum'),bad_in_30d=('bad_in_30d','sum')).reset_index().to_csv(OUT / 'landmark_monthly.csv', index=False, encoding='utf-8-sig')

# Independent SQL classification and aggregation directly from raw strings.
SQL = '''
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
'''
(OUT / 'review_time_classification.sql').write_text(SQL, encoding='utf-8')
LANDMARK_SQL='''
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
'''
(OUT/'landmark_future_review.sql').write_text(LANDMARK_SQL,encoding='utf-8')
with sqlite3.connect(':memory:') as con:
    raw_orders.to_sql('orders',con,index=False)
    raw_reviews.to_sql('reviews',con,index=False)
    sql_groups = pd.read_sql_query(SQL, con)
    pd.testing.assert_frame_equal(groups[['state','orders','bad_orders']].sort_values('state').reset_index(drop=True),sql_groups.sort_values('state').reset_index(drop=True),check_dtype=False)
    sql_landmark=pd.read_sql_query(LANDMARK_SQL,con)
    pd.testing.assert_frame_equal(landmark[['pending_at_landmark','eligible_orders','reviews_in_30d','bad_in_30d']].reset_index(drop=True),sql_landmark,check_dtype=False)
sql_groups.to_csv(OUT/'sql_crosscheck.csv',index=False,encoding='utf-8-sig')
sql_landmark.to_csv(OUT/'sql_landmark_crosscheck.csv',index=False,encoding='utf-8-sig')

all_events = orders.merge(reviews, on='order_id', how='inner', validate='one_to_many')
assert len(all_events)==len(reviews)
event_pre_purchase = int((all_events.review_answer_timestamp < all_events.order_purchase_timestamp).sum())
event_pre_creation = int((all_events.review_answer_timestamp.dt.normalize() < all_events.review_creation_date.dt.normalize()).sum())
metrics = {
    'selected_latest_orders': len(latest), 'selected_first_orders': len(first), 'source_review_events':len(reviews),
    'final_delivery_missing_latest_orders': int(latest.order_delivered_customer_date.isna().sum()),
    'time_zone_evidence':'All inspected nonmissing values are timezone-naive; actual timezone and cross-system clock consistency are unverified. No timezone conversion applied.',
    'date_precision_evidence':precision.to_dict('records'),
    'main_groups':groups.to_dict('records'),
    'original_sample_groups':summarize(old_sample, old_sample.state).to_dict('records'),
    'same_calendar_day_answer_delivery':int(same_day.sum()),
    'same_day_answer_before_delivery':int((same_day & (latest.review_answer_timestamp<latest.order_delivered_customer_date)).sum()),
    'same_day_answer_at_or_after_delivery':int((same_day & (latest.review_answer_timestamp>=latest.order_delivered_customer_date)).sum()),
    'answer_before_delivery_latest_all':int((latest.review_answer_timestamp<latest.order_delivered_customer_date).sum()),
    'creation_timestamp_before_delivery':int((latest.review_creation_date<latest.order_delivered_customer_date).sum()),
    'creation_calendar_date_before_delivery_date':int((creation_delta<0).sum()),
    'creation_same_calendar_date_as_delivery':int((creation_delta==0).sum()),
    'creation_before_min_delivery_or_promise_date':int((trigger_offset<0).sum()),
    'creation_on_min_delivery_or_promise_date':int((trigger_offset==0).sum()),
    'creation_one_day_after_min_delivery_or_promise_date':int((trigger_offset==1).sum()),
    'sequence_flags':{c:int(latest[c].sum()) for c in ['reply_before_purchase','reply_date_before_creation','creation_date_before_purchase_date','delivery_before_purchase','promise_date_before_purchase_date','strong_sequence_flag']},
    'all_events_reply_before_purchase':event_pre_purchase, 'all_events_reply_date_before_creation':event_pre_creation,
    'landmark_cohort':{'eligible_orders':len(land),'strong_sequence_flag_orders':int(land.strong_sequence_flag.eq(True).sum()),'purchase_start':'2017-01-01','promise_date_start':'2017-01-01','promise_date_end':'2018-06-30','follow_up_days':30,'extraction_time_known':False,'outcome':'first review only; excludes any first review before landmark; no review is not counted as positive satisfaction'},
    'landmark_groups':landmark.to_dict('records'),
    'source_description_url':'https://www.kaggle.com/olistbr/brazilian-ecommerce/home/',
    'source_description_checked_on':'2026-10-17',
    'source_description_paraphrase':'The publisher describes email survey sending after receipt or when estimated delivery is due. Exact timezone and ingestion timestamps are not provided in the local files.',
    'original_sample_final_delay_vs_state':temporal_cross.to_dict('records'),
}
(OUT/'timing_metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
audit_cols=['order_id','review_id','review_score','review_creation_date','review_answer_timestamp','order_purchase_timestamp','order_delivered_customer_date','order_estimated_delivery_date','state','strong_sequence_flag']
latest[audit_cols].to_csv(OUT/'order_timing_audit.csv.gz',index=False,compression='gzip')

plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans']
plt.rcParams['axes.unicode_minus']=False
fig, ax=plt.subplots(figsize=(9,5))
g=groups.set_index('state').reindex(STATE_ORDER)
xx=np.arange(len(g)); ax.bar(xx,g.bad_rate*100,color=['#65a9ca','#db633c','#65a9ca','#db633c'])
ax.errorbar(xx,g.bad_rate*100,yerr=[(g.bad_rate-g.ci95_low)*100,(g.ci95_high-g.bad_rate)*100],fmt='none',ecolor='#333',capsize=3)
ax.set_xticks(xx,['未见送达\n承诺未过','未见送达\n承诺已过','已送达\n准时','已送达\n超期'])
ax.set_ylabel('1–2 星差评率（%）');ax.set_title('以评价回复时间重构履约状态（最终每单一条评价）')
for i,row in enumerate(g.itertuples()):ax.text(i,row.ci95_high*100+2,f'n={row.orders:,}',ha='center',fontsize=9)
ax.set_ylim(0,min(100,g.bad_rate.max()*100+13));fig.tight_layout();fig.savefig(OUT/'review_time_states.png',dpi=180);plt.close(fig)

after={str(p.relative_to(ROOT)):digest(p) for p in protected if p.exists()}
assert before==after
validation={'protected_files_sha256_unchanged':before,'sql_pandas_groups_match':True,'sql_pandas_landmark_match':True,'all_group_sums_match':True,'datetime_parse_failures':int(precision.parse_failures_nonmissing.sum()),'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__,'matplotlib':matplotlib.__version__}
(OUT/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf-8')
from build_review_timing_report import build_report
build_report(OUT)
print(json.dumps({'groups':groups.to_dict('records'),'same_day':metrics['same_calendar_day_answer_delivery'],'flags':metrics['sequence_flags'],'landmark':landmark.to_dict('records')},ensure_ascii=False,indent=2))
