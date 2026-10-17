"""Simple rule triage, chronological holdout, daily quota and paired uncertainty.

Run from any directory: python -X utf8 decision_study/priority_study.py
All new artifacts remain in decision_study; no ML estimators or external API.
"""
from pathlib import Path
import os, sys, json, hashlib, sqlite3, platform, time
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent; ROOT=OUT.parent
os.environ['MPLCONFIGDIR']=str(OUT/'.matplotlib_cache')
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

DESIGN=json.loads((OUT/'design.json').read_text(encoding='utf-8'))
SEED=DESIGN['seed']; CANDIDATES=DESIGN['candidate_policies']
FEATURES=['order_id','decision_time','day','week','customer_state','order_age_days','handoff_observed','stage_age_days','item_value','freight','item_count','seller_count']

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
    return h.hexdigest()

def history_manifest():
    result={};skip={'decision_study','.repro_runs','audit_deps','__pycache__','.git','.venv'}
    for base,dirs,files in os.walk(ROOT):
        dirs[:]=[d for d in dirs if d not in skip]
        for name in files:
            p=Path(base)/name;result[p.relative_to(ROOT).as_posix()]=sha(p)
    return result

def write_json(name,obj):
    def convert(x):
        if isinstance(x,(np.integer,)):return int(x)
        if isinstance(x,(np.floating,)):return float(x)
        if isinstance(x,(np.bool_,)):return bool(x)
        if isinstance(x,(pd.Timestamp,)):return str(x)
        raise TypeError(type(x))
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=convert,allow_nan=False),encoding='utf-8')

def save_csv(name,frame):frame.to_csv(OUT/name,index=False,encoding='utf-8-sig')
def frame_records(frame):return frame.astype(object).where(pd.notna(frame),None).to_dict('records')
def div(a,b):return float(a/b) if b else 0.0
def interval(values):return [float(x) for x in np.quantile(values,[.025,.975])]
def period(frame,dates):
    return frame[(frame.decision_time>=pd.Timestamp(dates[0]))&(frame.decision_time<pd.Timestamp(dates[1])+pd.Timedelta(days=1))].copy()

def load_base():
    orders=pd.read_csv(ROOT/'olist_orders_dataset.csv')
    reviews=pd.read_csv(ROOT/'olist_order_reviews_dataset.csv')
    customers=pd.read_csv(ROOT/'olist_customers_dataset.csv',usecols=['customer_id','customer_state'])
    items=pd.read_csv(ROOT/'olist_order_items_dataset.csv',usecols=['order_id','seller_id','price','freight_value'])
    first=reviews.sort_values(['review_answer_timestamp','review_id'],kind='stable').groupby('order_id').head(1)[['order_id','review_answer_timestamp','review_score']]
    agg=items.groupby('order_id').agg(item_value=('price','sum'),freight=('freight_value','sum'),item_count=('price','size'),seller_count=('seller_id','nunique')).reset_index()
    base=orders.merge(first,on='order_id',how='left',validate='one_to_one').merge(customers,on='customer_id',validate='one_to_one').merge(agg,on='order_id',how='left',validate='one_to_one')
    for col in ['order_purchase_timestamp','order_estimated_delivery_date','order_delivered_carrier_date','order_delivered_customer_date','review_answer_timestamp']:
        raw=base[col];parsed=pd.to_datetime(raw,errors='coerce')
        assert not (raw.notna()&parsed.isna()).any(),col
        base[col]=parsed
    assert len(base)==99441 and base.order_id.is_unique
    return base,orders,reviews

def make_cohort(base,offset=1,censor_future=False):
    x=base.copy()
    x['decision_time']=x.order_estimated_delivery_date.dt.normalize()+pd.Timedelta(days=offset)
    if censor_future:
        for c in ['order_delivered_customer_date','order_delivered_carrier_date','review_answer_timestamp']:
            x.loc[x[c]>x.decision_time,c]=pd.NaT
        x['review_score']=np.nan;x['order_status']='HIDDEN_FUTURE_STATE'
    select=(x.order_purchase_timestamp>=pd.Timestamp(DESIGN['purchase_start']))&(x.order_purchase_timestamp<=x.decision_time)&(x.order_estimated_delivery_date.dt.normalize()<=pd.Timestamp(DESIGN['reference_promise_end']))&(x.order_estimated_delivery_date.dt.normalize()>=pd.Timestamp('2017-01-01'))&(x.order_delivered_customer_date.isna()|(x.order_delivered_customer_date>x.decision_time))&(x.review_answer_timestamp.isna()|(x.review_answer_timestamp>x.decision_time))
    x=x[select].copy().reset_index(drop=True)
    x['day']=x.decision_time.dt.strftime('%Y-%m-%d')
    x['week']=x.decision_time.dt.to_period('W-SUN').astype(str)
    x['order_age_days']=(x.decision_time-x.order_purchase_timestamp).dt.total_seconds()/86400
    x['handoff_observed']=x.order_delivered_carrier_date.notna()&(x.order_delivered_carrier_date<=x.decision_time)&(x.order_delivered_carrier_date>=x.order_purchase_timestamp)
    age=(x.decision_time-x.order_delivered_carrier_date).dt.total_seconds()/86400
    x['stage_age_days']=age.where(x.handoff_observed,x.order_age_days)
    horizon=x.decision_time+pd.Timedelta(days=DESIGN['outcome_days'])
    x['review_30d']=x.review_answer_timestamp.notna()&(x.review_answer_timestamp>x.decision_time)&(x.review_answer_timestamp<=horizon)
    x['event']=((x.review_score<=2)&x.review_30d).astype(int)
    x['still_no_delivery_30d']=(x.order_delivered_customer_date.isna()|(x.order_delivered_customer_date>horizon)).astype(int)
    x['future_handoff_only_audit']=x.order_delivered_carrier_date>x.decision_time
    x['invalid_handoff_only_audit']=x.order_delivered_carrier_date<x.order_purchase_timestamp
    assert x.order_id.is_unique and (x.order_age_days>=0).all() and (x.stage_age_days>=0).all()
    return x

def outcome_summary(x):
    return {'orders':len(x),'bad_events_30d':int(x.event.sum()),'observed_bad_event_rate':div(x.event.sum(),len(x)),'first_reviews_30d':int(x.review_30d.sum()),'review_coverage_30d':div(x.review_30d.sum(),len(x)),'bad_rate_among_reviewers':div(x.event.sum(),x.review_30d.sum()),'still_no_delivery_30d':int(x.still_no_delivery_30d.sum()),'no_valid_handoff_at_decision':int((~x.handoff_observed).sum())}

def fit_rules(x,quantile=None,geo_minimum=None):
    q=DESIGN['long_wait_quantile'] if quantile is None else quantile
    nmin=DESIGN['geo_minimum_orders'] if geo_minimum is None else geo_minimum
    thresholds={str(bool(phase)):float(g.stage_age_days.quantile(q)) for phase,g in x.groupby('handoff_observed')}
    z=cell_keys(x[FEATURES].copy(),thresholds)
    z['event']=x.event.to_numpy()
    prior=float(x.event.mean());cells={};geos={}
    for key,g in z.groupby('cell'):
        n=len(g);k=int(g.event.sum());strength=DESIGN['cell_shrinkage_orders']
        cells[key]={'n':n,'events':k,'score':float((k+strength*prior)/(n+strength))}
    for (cell,state),g in z.groupby(['cell','customer_state'],dropna=False):
        n=len(g);k=int(g.event.sum())
        if n>=nmin and min(k,n-k)>=DESIGN['geo_minimum_each_outcome']:
            strength=DESIGN['geo_shrinkage_orders'];parent=cells[cell]['score']
            geos[cell+'|'+str(state)]={'n':n,'events':k,'score':float((k+strength*parent)/(n+strength))}
    return {'quantile':q,'geo_minimum':nmin,'training_n':len(x),'training_start':str(x.decision_time.min()),'training_end':str(x.decision_time.max()),'training_label_window_end':str((x.decision_time+pd.Timedelta(days=30)).max()),'prior_event_rate':prior,'thresholds_days':thresholds,'cells':cells,'supported_geo_cells':geos}

def cell_keys(features,thresholds):
    z=features.copy()
    long=z.stage_age_days>z.handoff_observed.astype(str).map(thresholds)
    z['cell']=np.where(z.handoff_observed,'in_transit','handoff_unconfirmed')+np.where(long,'|long','|short')
    return z

def tie_hash(ids,salt):
    return ids.map(lambda s:int(hashlib.sha256((str(salt)+'|'+s).encode()).hexdigest()[:15],16)).to_numpy()

def priorities(features,rules):
    assert list(features.columns)==FEATURES
    z=cell_keys(features,rules['thresholds_days'])
    base=z.cell.map(lambda c:rules['cells'].get(c,{'score':rules['prior_event_rate']})['score']).to_numpy()
    geo=np.array([rules['supported_geo_cells'].get(c+'|'+str(s),{'score':score})['score'] for c,s,score in zip(z.cell,z.customer_state,base)])
    tie=tie_hash(features.order_id,SEED)
    # Lexicographic ordering is implemented by globally sorting then ranking.
    spec={
      'random_hash_draw': [tie],
      'oldest_purchase':[-features.order_age_days.to_numpy(),tie],
      'stage_wait':[features.handoff_observed.to_numpy().astype(int),-features.stage_age_days.to_numpy(),tie],
      'four_cell':[-base,-features.stage_age_days.to_numpy(),tie],
      'geo_four_cell':[-geo,-features.stage_age_days.to_numpy(),tie],
    }
    result={}
    for name,keys in spec.items():
        order=np.lexsort(tuple(reversed(keys)))
        rank=np.empty(len(z),int);rank[order]=np.arange(len(z));result[name]=rank
    return result

def evaluate(x,rules,split,offset=1,bootstrap=True):
    ranks=priorities(x[FEATURES],rules)
    bounds=DESIGN['held_out_test'] if split=='test' else DESIGN['development_validation'] if split=='validation' else split.split('_') if '_' in split and len(split.split('_'))==2 else [x.decision_time.min(),x.decision_time.max()]
    dates=pd.date_range(bounds[0],bounds[1],freq='D')
    day_names=dates.strftime('%Y-%m-%d');week_names=dates.to_period('W-SUN').astype(str)
    days=pd.DataFrame(index=day_names)
    grouped=x.groupby('day')
    days['n']=grouped.size().reindex(day_names,fill_value=0)
    days['bad']=grouped.event.sum().reindex(day_names,fill_value=0)
    days['week']=week_names
    day_index={v:i for i,v in enumerate(day_names)}
    row_day=x.day.map(day_index).to_numpy();n_day=days.n.to_numpy(int);bad_day=days.bad.to_numpy(int)
    totals=int(x.event.sum());rows=[];daily=[];details={}
    for fraction in DESIGN['capacity_fractions']:
        k=np.floor(n_day*fraction+1e-12).astype(int)
        selections={}
        for policy,rank in ranks.items():
            local=pd.DataFrame({'day':x.day.to_numpy(),'rank':rank}).groupby('day')['rank'].rank(method='first').to_numpy()-1
            selections[policy]=local<k[row_day]
        rand_expected=np.divide(k*bad_day,n_day,out=np.zeros(len(days)),where=n_day>0)
        weekly=[]
        for policy in [*ranks,'random_expectation']:
            if policy=='random_expectation':
                captured=rand_expected
                review_selected=np.divide(k*grouped.review_30d.sum().reindex(day_names,fill_value=0).to_numpy(),n_day,out=np.zeros(len(days)),where=n_day>0)
                stage_selected=np.divide(k*grouped.still_no_delivery_30d.sum().reindex(day_names,fill_value=0).to_numpy(),n_day,out=np.zeros(len(days)),where=n_day>0)
                selected_ids_hash=None
            else:
                sel=selections[policy]
                captured=np.bincount(row_day,weights=x.event.to_numpy()*sel,minlength=len(days))
                review_selected=np.bincount(row_day,weights=x.review_30d.to_numpy()*sel,minlength=len(days))
                stage_selected=np.bincount(row_day,weights=x.still_no_delivery_30d.to_numpy()*sel,minlength=len(days))
                selected_ids_hash=hashlib.sha256('|'.join(sorted(x.loc[sel,'order_id'])).encode()).hexdigest()
                assert sel.sum()==k.sum() and x.loc[sel,'order_id'].is_unique
            table=pd.DataFrame({'day':day_names,'week':week_names,'candidate_orders':n_day,'candidate_bad_events':bad_day,'selected_orders':k,'selected_bad_events':captured})
            w=table.groupby('week')[['candidate_orders','candidate_bad_events','selected_orders','selected_bad_events']].sum()
            weekly.append((policy,w))
            details[(policy,fraction)]={'table':table,'selected_mask':selections.get(policy)}
            nsel=int(k.sum());hit=float(captured.sum())
            row={'split':split,'decision_offset_days':offset,'strategy':policy,'capacity_fraction':fraction,'candidate_orders':len(x),'all_bad_events':totals,'selected_orders':nsel,'selected_bad_events':hit,'event_recall':div(hit,totals),'selected_event_rate':div(hit,nsel),'effective_selected_fraction':div(nsel,len(x)),'daily_integer_budget_utilization':1.0 if nsel else 0.0,'fractional_budget_utilization':div(nsel,len(x)*fraction),'rounding_slots_lost':float(len(x)*fraction-nsel),'selected_reviews_30d':float(review_selected.sum()),'selected_review_coverage':div(review_selected.sum(),nsel),'selected_bad_rate_among_reviewers':div(hit,review_selected.sum()),'selected_still_no_delivery_30d':float(stage_selected.sum()),'selected_ids_sha256':selected_ids_hash,'is_random_expectation':policy=='random_expectation','active_queue_days':int((n_day>0).sum()),'zero_budget_days_with_queue':int(((n_day>0)&(k==0)).sum()),'daily_candidates_median':float(np.median(n_day)),'daily_candidates_p90':float(np.quantile(n_day,.9)),'daily_candidates_max':int(n_day.max()),'daily_selected_median':float(np.median(k)),'daily_selected_max':int(k.max())}
            rows.append(row)
            table['split']=split;table['decision_offset_days']=offset;table['strategy']=policy;table['capacity_fraction']=fraction
            daily.append(table)
        baseline={r['strategy']:r for r in rows if r['capacity_fraction']==fraction}
        week_map=dict(weekly);base=week_map['oldest_purchase'];rand=week_map['random_expectation']
        idx=np.random.default_rng(SEED+offset).integers(0,len(base),size=(DESIGN['bootstrap_repetitions'],len(base))) if bootstrap else None
        for row in [r for r in rows if r['capacity_fraction']==fraction]:
            policy=row['strategy'];w=week_map[policy]
            row['recall_gain_vs_wait_pp']=100*(row['event_recall']-baseline['oldest_purchase']['event_recall'])
            row['recall_gain_vs_random_pp']=100*(row['event_recall']-baseline['random_expectation']['event_recall'])
            row['recall_lift_vs_wait']=div(row['event_recall'],baseline['oldest_purchase']['event_recall'])
            row['recall_lift_vs_random']=div(row['event_recall'],baseline['random_expectation']['event_recall'])
            if bootstrap:
                denominator=base.candidate_bad_events.to_numpy()[idx].sum(axis=1)
                selected=base.selected_orders.to_numpy()[idx].sum(axis=1)
                capture=w.selected_bad_events.to_numpy()[idx].sum(axis=1)
                waiting=base.selected_bad_events.to_numpy()[idx].sum(axis=1)
                random=rand.selected_bad_events.to_numpy()[idx].sum(axis=1)
                assert (denominator>0).all() and (selected>0).all()
                row['event_recall_ci_low'],row['event_recall_ci_high']=interval(capture/denominator)
                row['selected_event_rate_ci_low'],row['selected_event_rate_ci_high']=interval(capture/selected)
                row['gain_vs_wait_ci_low_pp'],row['gain_vs_wait_ci_high_pp']=interval(100*(capture-waiting)/denominator)
                row['gain_vs_random_ci_low_pp'],row['gain_vs_random_ci_high_pp']=interval(100*(capture-random)/denominator)
        if bootstrap:
            rng=np.random.default_rng(SEED+int(fraction*1000)+offset)
            draws=rng.hypergeometric(bad_day,n_day-bad_day,k,size=(DESIGN['random_selection_repetitions'],len(days))).sum(axis=1)
            randomrow=next(r for r in rows if r['strategy']=='random_expectation' and r['capacity_fraction']==fraction)
            randomrow['random_selection_recall_interval_low'],randomrow['random_selection_recall_interval_high']=interval(draws/totals)
            randomrow['random_selection_expected_event_count']=float(rand_expected.sum())
            assert abs(draws.mean()-rand_expected.sum())<max(2.0,draws.std()/4)
    return pd.DataFrame(rows),pd.concat(daily,ignore_index=True),details

def cohort_profile(x,split):
    summary=outcome_summary(x);summary.update(split=split,start=str(x.decision_time.min()),end=str(x.decision_time.max()))
    return summary

def main():
    started=time.perf_counter();history=history_manifest()
    write_json('input_hashes.json',{'protected_files':history,'design_sha256':sha(OUT/'design.json'),'study_code_sha256':{p.name:sha(p) for p in OUT.glob('*.py')},'excluded_runtime_dirs':['.repro_runs','audit_deps','__pycache__','.git','decision_study']})
    base,raw_orders,raw_reviews=load_base()
    primary=make_cohort(base)
    censored=make_cohort(base,censor_future=True)
    pd.testing.assert_frame_equal(primary[FEATURES],censored[FEATURES])
    original=primary[(primary.order_estimated_delivery_date.dt.normalize()<=pd.Timestamp('2018-06-30'))]
    assert len(original)==8248 and original.event.sum()==5501 and original.review_30d.sum()==7943
    feature_profile=[]
    for field in FEATURES[3:]:
        s=primary[field]
        feature_profile.append({'field':field,'orders':len(primary),'missing':int(s.isna().sum()),'used_for_ranking':field in ['customer_state','order_age_days','handoff_observed','stage_age_days']})
    save_csv('feature_availability.csv',pd.DataFrame(feature_profile))
    dev=period(primary,DESIGN['development_fit']);val=period(primary,DESIGN['development_validation']);train=period(primary,DESIGN['final_fit']);test=period(primary,DESIGN['held_out_test'])
    assert (dev.decision_time+pd.Timedelta(days=30)).max()<val.decision_time.min()
    assert (train.decision_time+pd.Timedelta(days=30)).max()<test.decision_time.min()
    assert set(train.order_id).isdisjoint(test.order_id)
    development_rules=fit_rules(dev)
    validation,_,_=evaluate(val,development_rules,'validation',bootstrap=True)
    save_csv('development_validation.csv',validation)
    eligible=validation[(validation.strategy.isin(CANDIDATES))&(validation.capacity_fraction==.2)].copy()
    eligible['complexity']=eligible.strategy.map({p:i for i,p in enumerate(CANDIDATES)})
    chosen=eligible.sort_values(['event_recall','complexity'],ascending=[False,True]).iloc[0].strategy
    rules=fit_rules(train)
    frozen={'design_sha256':sha(OUT/'design.json'),'chosen_on_validation':chosen,'selection_period':DESIGN['development_validation'],'development_rules':development_rules,'final_training_rules':rules,'feature_allowlist':FEATURES,'excludes_final_status_and_delivery_and_outcomes':True}
    write_json('frozen_rules.json',frozen)
    frozen_hash=sha(OUT/'frozen_rules.json')
    if (OUT/'freeze_guard.json').exists():
        guard=json.loads((OUT/'freeze_guard.json').read_text(encoding='utf-8'))
        assert guard['frozen_rules_sha256']==frozen_hash and guard['design_sha256']==sha(OUT/'design.json'),'Policy changed after initial holdout evaluation'
    # The held-out evaluation starts only after policy selection and rule freeze.
    result,daily,details=evaluate(test,rules,'test',bootstrap=True)
    assert (result.groupby('capacity_fraction').selected_orders.nunique()==1).all()
    save_csv('priority_backtest.csv',result);save_csv('daily_queue_and_capacity.csv',daily)
    subperiods=[]
    for dates in DESIGN['test_subperiods']:
        part=period(test,dates);r,_,_=evaluate(part,rules,dates[0]+'_'+dates[1],bootstrap=False);subperiods.append(r)
    subperiods=pd.concat(subperiods,ignore_index=True);save_csv('test_subperiods.csv',subperiods)
    sensitivities=[]
    for quant in DESIGN['threshold_sensitivity_quantiles']:
        model=fit_rules(train,quantile=quant);r,_,_=evaluate(test,model,'test',bootstrap=False)
        r=r[r.strategy.isin(['four_cell','geo_four_cell'])].copy();r['variant']='training_quantile_'+str(quant);sensitivities.append(r)
    for nmin in DESIGN['geo_support_sensitivity_minimums']:
        model=fit_rules(train,geo_minimum=nmin);r,_,_=evaluate(test,model,'test',bootstrap=False)
        r=r[r.strategy=='geo_four_cell'].copy();r['variant']='training_geo_minimum_'+str(nmin);sensitivities.append(r)
    save_csv('threshold_sensitivity.csv',pd.concat(sensitivities,ignore_index=True))
    secondary=[];overlap={}
    for offset in DESIGN['secondary_decision_offsets_days']:
        x=make_cohort(base,offset);part=period(x,DESIGN['held_out_test'])
        r,_,_=evaluate(part,rules,'test',offset,bootstrap=True);secondary.append(r)
        overlap[str(offset)]={'orders':len(part),'overlap_with_primary_test':len(set(part.order_id)&set(test.order_id)),'thresholds_refitted':False}
    save_csv('separate_landmark_sensitivity.csv',pd.concat(secondary,ignore_index=True))
    # Frozen-score invariance to hiding future carrier/delivery/review data.
    for key,value in priorities(test[FEATURES],rules).items():
        hidden=period(censored,DESIGN['held_out_test'])
        assert np.array_equal(value,priorities(hidden[FEATURES],rules)[key])
    cells=cell_keys(train[FEATURES],rules['thresholds_days']).assign(event=train.event.to_numpy())
    cell_output=cells.groupby(['cell','customer_state']).agg(orders=('order_id','size'),events=('event','sum')).reset_index()
    cell_output['supported_geography']=cell_output.apply(lambda r:r['cell']+'|'+str(r['customer_state']) in rules['supported_geo_cells'],axis=1)
    save_csv('training_group_support.csv',cell_output)
    stage_rows=[]
    for split,x in [('development',dev),('validation',val),('training',train),('test',test)]:
        for phase,g in x.groupby('handoff_observed'):
            row=cohort_profile(g,split);row['handoff_observed']=bool(phase);row['stage_age_median']=float(g.stage_age_days.median());row['order_age_median']=float(g.order_age_days.median());stage_rows.append(row)
    save_csv('cohort_stage_profile.csv',pd.DataFrame(stage_rows))
    # Outcome/status fields may be summarized only after fixed selections.
    selected=details[(chosen,.2)]['selected_mask']
    audit_status=test.assign(selected_by_frozen_rule_20pct=selected).groupby(['selected_by_frozen_rule_20pct','order_status']).agg(orders=('order_id','size'),bad_events=('event','sum')).reset_index()
    save_csv('final_status_outcome_audit_not_features.csv',audit_status)
    sql_check(raw_orders,raw_reviews,primary,test)
    focal=result[(result.strategy==chosen)&(result.capacity_fraction==.2)].iloc[0]
    halves=subperiods[(subperiods.strategy==chosen)&(subperiods.capacity_fraction==.2)]
    gate=bool(focal.recall_gain_vs_wait_pp>=2 and focal.gain_vs_wait_ci_low_pp>0 and (halves.recall_gain_vs_wait_pp>0).all())
    profile=[cohort_profile(x,s) for s,x in [('all_reference',primary),('development',dev),('validation',val),('training',train),('test',test)]]
    metrics={'design':DESIGN,'reference_matches_previous_pending_cohort':{'orders':len(original),'reviews_30d':int(original.review_30d.sum()),'bad_events_30d':int(original.event.sum())},'cohorts':profile,'development_selection':{'chosen_family':chosen,'metric':'validation event recall at 20% daily capacity','no_test_tuning':True},'frozen_rules_sha256':frozen_hash,'training_rules':rules,'recommendation_gate_passed':gate,'frozen_family_primary_test':focal.dropna().to_dict(),'best_test_family_descriptive_only':result[(result.capacity_fraction==.2)&result.strategy.isin(CANDIDATES)].sort_values('event_recall',ascending=False).iloc[0].strategy,'secondary_landmark_overlap':overlap,'dq':{'reference_missing_carrier':int(primary.order_delivered_carrier_date.isna().sum()),'reference_future_carrier_not_used':int(primary.future_handoff_only_audit.sum()),'reference_carrier_before_purchase':int(primary.invalid_handoff_only_audit.sum()),'first_review_exactly_at_main_decision_all_orders':int((base.review_answer_timestamp==base.order_estimated_delivery_date.dt.normalize()+pd.Timedelta(days=1)).sum()),'test_missing_final_delivery':int(test.order_delivered_customer_date.isna().sum()),'test_multi_seller':int((test.seller_count>1).sum())},'audit':{'future_censoring_preserves_candidates_features_and_scores':True,'feature_allowlist_enforced':True,'no_status_delivery_or_review_score_in_priority_features':True,'training_outcome_window_precedes_test':True,'development_outcome_window_precedes_validation':True,'no_order_duplicate_within_each_landmark':True,'secondary_landmarks_not_pooled':True,'rules_file_unchanged_after_test':sha(OUT/'frozen_rules.json')==frozen_hash,'sql_pandas_candidate_and_event_counts_match':True},'environment':{'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__,'matplotlib':matplotlib.__version__},'elapsed_seconds_before_reporting':round(time.perf_counter()-started,3)}
    from verification import audit_allocations,complexity_contrasts
    metrics['independent_allocation_audit']=audit_allocations(ROOT,OUT,rules,result,SEED)
    metrics['complexity_audit']=complexity_contrasts(OUT,daily,SEED,DESIGN['bootstrap_repetitions'])
    metrics['backtest_results']=frame_records(result)
    metrics['validation_results']=frame_records(validation)
    metrics['test_subperiod_results']=frame_records(subperiods)
    metrics['threshold_sensitivity_results']=frame_records(pd.concat(sensitivities,ignore_index=True))
    metrics['secondary_landmark_results']=frame_records(pd.concat(secondary,ignore_index=True))
    metrics['stage_profiles']=stage_rows
    metrics['feature_availability']=feature_profile
    metrics['audit']['independent_sql_policy_scoring_and_allocation_match']=True
    metrics['audit']['initial_policy_and_threshold_freeze_preserved']=True
    assert metrics['audit']['rules_file_unchanged_after_test']
    assert history_manifest()==history,'Historical artifacts changed'
    metrics['audit']['historical_files_sha256_unchanged']=len(history)
    metrics['elapsed_seconds_before_reporting']=round(time.perf_counter()-started,3)
    write_json('priority_metrics.json',metrics)
    make_figures(result,daily,chosen)
    from reporting import build_report
    build_report(OUT)
    assert history_manifest()==history
    write_json('audit_checks.json',metrics['audit'])
    print(json.dumps({'validation_chosen':chosen,'test_best_descriptive':metrics['best_test_family_descriptive_only'],'recommendation_gate_passed':gate,'test':outcome_summary(test),'primary_chosen':focal.dropna().to_dict(),'history_unchanged':len(history)},ensure_ascii=False,default=str,indent=2))

def sql_check(orders,reviews,primary,test):
    sql="""
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
"""
    (OUT/'candidate_validation.sql').write_text(sql,encoding='utf-8')
    with sqlite3.connect(':memory:') as con:
        orders.to_sql('orders',con,index=False);reviews.to_sql('reviews',con,index=False)
        r=pd.read_sql_query(sql,con)
    assert r.orders.sum()==len(primary) and r.bad_30d.sum()==primary.event.sum() and r.reviews_30d.sum()==primary.review_30d.sum()
    selected=r[r.period=='test'].iloc[0]
    assert selected.orders==len(test) and selected.bad_30d==test.event.sum() and selected.reviews_30d==test.review_30d.sum()
    save_csv('sql_crosscheck.csv',r)

def make_figures(results,daily,chosen):
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans'];plt.rcParams['axes.unicode_minus']=False
    names={'stage_wait':'交接状态+阶段等待','four_cell':'训练期四组事件率','geo_four_cell':'四组+有支持的客户州','oldest_purchase':'购买等待时长基准','random_expectation':'同日随机选择期望'}
    fig,ax=plt.subplots(figsize=(8,5))
    for policy in ['random_expectation','oldest_purchase',*CANDIDATES]:
        p=results[results.strategy==policy].sort_values('capacity_fraction')
        ax.plot(p.effective_selected_fraction*100,p.event_recall*100,marker='o',label=names[policy],linewidth=2.5 if policy==chosen else 1.5)
    ax.set_xlabel('实际处理候选订单比例（按日预算向下取整）%');ax.set_ylabel('后续30天首次差评事件覆盖率 %');ax.set_title('独立时间测试：风险覆盖，不代表可减少差评');ax.legend(fontsize=9);fig.tight_layout();fig.savefig(OUT/'risk_coverage.png',dpi=180);plt.close(fig)
    p=results[(results.capacity_fraction==.2)&results.strategy.isin(CANDIDATES)]
    fig,ax=plt.subplots(figsize=(8,4));xx=np.arange(len(p))
    ax.errorbar(p.recall_gain_vs_wait_pp,xx,xerr=[p.recall_gain_vs_wait_pp-p.gain_vs_wait_ci_low_pp,p.gain_vs_wait_ci_high_pp-p.recall_gain_vs_wait_pp],fmt='o',capsize=4)
    ax.axvline(0,color='#666',linestyle='--');ax.set_yticks(xx,[names[v] for v in p.strategy]);ax.set_xlabel('相对购买等待基准的事件覆盖率增量（百分点）');ax.set_title('20%按日预算：配对日历周Bootstrap 95%区间');fig.tight_layout();fig.savefig(OUT/'paired_increment.png',dpi=180);plt.close(fig)

if __name__=='__main__':main()
