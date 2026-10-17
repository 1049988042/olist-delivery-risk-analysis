"""Consolidate existing outputs into portfolio documentation; no raw research."""
from pathlib import Path
import csv, json

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'final_delivery'

def load(name):return json.loads((ROOT/name).read_text(encoding='utf-8-sig'))
def records(name):
    with (ROOT/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def pct(x):return f'{float(x)*100:.2f}%'
def count(x):return f'{int(x):,}'

def build():
    b=load('project/metrics.json');d=load('deep_study/deep_metrics.json');t=load('review_timing_study/timing_metrics.json')
    audit=load('audit_results.json') if (ROOT/'audit_results.json').exists() else load('final_delivery/audit_reference.json')
    audit['reviews'].pop('examples',None)
    (OUT/'audit_reference.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    late={r['late'].lower():r for r in records('project/late_groups.csv')}
    lm={str(r['pending_at_landmark']).lower():r for r in t['landmark_groups']}
    states={r['state']:r for r in t['main_groups']}
    evidence=[]
    def add(key,title,value,code,anchor,output,selector,denominator,formula,notes=''):
        text=(ROOT/code).read_text(encoding='utf-8')
        assert anchor in text,(code,anchor)
        line=text[:text.index(anchor)].count('\n')+1
        evidence.append(dict(key=key,title=title,value=value,code=code,line=line,code_anchor=anchor,output=output,selector=selector,denominator=denominator,formula=formula,notes=notes))
    add('raw_orders','原始订单',b['order_rows'],'run_project.py','assert len(df)==len(data', 'project/metrics.json','order_rows',99441,'COUNT(orders.order_id)，order_id唯一','audit_results.json亦核对原始表行数')
    add('delivered_status','快照delivered订单',b['delivered'],'run_project.py',"'delivered':int",'project/metrics.json','delivered',99441,'order_status=delivered的订单数','97.02%是快照已送达占比，不是成熟队列最终履约率')
    add('valid_delivery','用于日期配送分析的有效送达',b['delivered_valid'],'run_project.py',"df['delivered_valid']",'project/metrics.json','delivered_valid',96478,'delivered且实际送达时间非空：96478-8','不保证所有其他时间顺序有效')
    add('reviewed_valid_delivery','有评价的有效送达',b['reviewed_delivered'],'run_project.py','q=df[df.delivered_valid]', 'project/metrics.json','reviewed_delivered',96470,'96470-646无评价订单','每单最晚回复评分；非全平台客户样本')
    add('late_count','超承诺日期送达订单',b['late_count_all_valid'],'run_project.py',"df['late']=",'project/metrics.json','late_count_all_valid',96470,'实际送达日>承诺日')
    add('late_rate','有效送达订单延迟率',b['late_rate_all_valid'],'run_project.py',"df['late']=",'project/metrics.json','late_rate_all_valid',96470,'6534/96470')
    for flag,name,key in [('true','延迟有评价订单差评率','late_bad_rate'),('false','未延迟有评价订单差评率','ontime_bad_rate')]:
        r=late[flag];n=int(r['n']);k=int(r['bad_n'])
        add(key,name,float(r['bad_rate']),'run_project.py',"late=group(a,'late')",'project/late_groups.csv',f'late={flag};bad_n/n',n,f'{k}/{n}','1–2星，每单最晚回复；最终配送结果的回顾性关联')
    add('crude_rr','未调整差评风险比',b['late_bad12_risk_ratio'],'run_project.py','two=stats.contingency.relative_risk','project/metrics.json','late_bad12_risk_ratio',95824,'(3983/6381)/(8289/89443)','95% CI见late_bad12_rr_ci95；不等于调整OR')
    add('model_n','主回归样本',d['model_audit']['n'],'deep_audit.py','eligible=a.purchase_month.value_counts()','deep_study/deep_metrics.json','model_audit.n',95824,'95824-2个稀疏月份订单','保留缺失/排除原因；n=95822')
    add('adjusted_or','statsmodels调整延迟OR',d['model_audit']['main']['or'],'deep_audit.py','model=sm.GLM(y,X','deep_study/deep_metrics.json','model_audit.main',95822,'exp(beta_late)','控制州、月份、log1p商品金额/运费/件数；观察性关联')
    add('cluster_se','用户聚类稳健SE',d['model_audit']['cluster_customer']['se'],'deep_audit.py','cluster=sm.GLM','deep_study/deep_metrics.json','model_audit.cluster_customer.se',92746,'按customer_unique_id聚类的SE','样本95822订单；92746用户；非因果校正')
    add('strict_category_null_affected','旧单品类误判影响订单',d['category_null']['mixed_null_reviewed'],'deep_audit.py',"d['mixed_null_category']",'deep_study/deep_metrics.json','category_null.mixed_null_reviewed',93781,'非空类目数=1且存在NULL商品类目的有评价订单','55单；旧单品类样本93781改为93726')
    add('valid_stage','阶段耗时有效订单',d['timing']['valid_stage_n'],'deep_audit.py',"stage['valid_carrier']=",'deep_study/deep_metrics.json','timing.valid_stage_n',96470,'排除165负交接、23负运输、1缺交接，共189','仅排除于阶段时长指标，保留原始记录')
    add('all_reviewed_orders','全体有评价订单',t['selected_latest_orders'],'review_timing_study.py',"latest = select_reviews('latest')",'review_timing_study/timing_metrics.json','selected_latest_orders',99441,'每单最后一次评价；包括最终未送达/取消','不同于基础有评价已送达95824')
    for state,row in states.items():
        add('state_'+state,row['state_label']+'差评率',row['bad_rate'],'review_timing_study.py','def classify(frame','review_timing_study/review_time_states_latest.csv',f'state={state}',row['orders'],f'{row["bad_orders"]}/{row["orders"]}','全部有评价订单；事件时间代理，非入库时点；Wilson区间见输出')
    add('sequence_flags','明显评价时间矛盾订单',t['sequence_flags']['strong_sequence_flag'],'review_timing_study.py',"result['strong_sequence_flag']",'review_timing_study/timing_metrics.json','sequence_flags.strong_sequence_flag',98673,'下单前回复或创建日早于下单日等标记取并集','61单；不能把所有收货前评价当作异常')
    add('same_day','评价和送达同日订单',t['same_calendar_day_answer_delivery'],'review_timing_study.py','same_day = latest','review_timing_study/timing_metrics.json','same_calendar_day_answer_delivery',98673,'评价回复日=送达日','414笔作答在前；959笔在后或同时；另有窗口敏感性')
    add('landmark_n','承诺节点候选订单',t['landmark_cohort']['eligible_orders'],'review_timing_study.py','eligible = (','review_timing_study/timing_metrics.json','landmark_cohort.eligible_orders',13126,'8248未见送达+4878已送达','购买>=2017-01-01；承诺日2017-01-01至2018-06-30；节点已下单且无更早首次评价')
    for flag,title in [('true','节点未见送达'),('false','节点已送达')]:
        row=lm[flag];n=row['eligible_orders'];r=row['reviews_in_30d'];k=row['bad_in_30d']
        add('landmark_candidates_'+flag,title+'候选数',n,'review_timing_study.py',"land['pending_at_landmark']",'review_timing_study/landmark_future_first_review_30d.csv',f'pending_at_landmark={flag};eligible_orders',13126,'按记录送达时间是否晚于承诺次日零时分组','无送达时间亦属未见送达；无法排除当时已取消')
        add('future_review_coverage_'+flag,title+'后续30天评价覆盖率',row['review_coverage_30d'],'review_timing_study.py',"land['review_in_30d']",'review_timing_study/landmark_future_first_review_30d.csv',f'pending_at_landmark={flag};reviews_in_30d/eligible_orders',n,f'{r}/{n}','首次评价；区间[节点,节点+30天)')
        add('future_bad_rate_'+flag,title+'后续30天评价者差评率',row['bad_rate_among_30d_reviewers'],'review_timing_study.py',"land['bad_in_30d']",'review_timing_study/landmark_future_first_review_30d.csv',f'pending_at_landmark={flag};bad_in_30d/reviews_in_30d',r,f'{k}/{r}','69.26%与13.09%的分母是评价者，不是候选订单')
        add('future_observed_event_'+flag,title+'观察到首次差评事件比例',row['observed_bad_review_incidence_30d'],'review_timing_study.py',"landmark['observed_bad_review_incidence_30d']",'review_timing_study/landmark_future_first_review_30d.csv',f'pending_at_landmark={flag};bad_in_30d/eligible_orders',n,f'{k}/{n}','未评价不是好评；此为观察到事件比例而非潜在不满意率')
    assert b['order_rows']==99441 and b['delivered_valid']==96470 and b['reviewed_delivered']==95824
    assert int(late['true']['n'])==6381 and int(late['true']['bad_n'])==3983
    assert int(late['false']['n'])==89443 and int(late['false']['bad_n'])==8289
    assert lm['true']['eligible_orders']+lm['false']['eligible_orders']==13126
    assert lm['true']['bad_in_30d']==5501 and lm['true']['reviews_in_30d']==7943
    assert lm['false']['bad_in_30d']==537 and lm['false']['reviews_in_30d']==4101
    with (OUT/'evidence_index.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(evidence[0]));writer.writeheader();writer.writerows(evidence)
    (OUT/'evidence_snapshot.json').write_text(json.dumps({'scope':'Previously computed statistics only; no new models or research','metrics':evidence},ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 关键指标证据索引','','所有数值取自既有统计输出；源代码链接标记实际行号。分母必须与人群、观察时点一起阅读。`audit_results.json`及逐单异常清单仅本地保留，公开查看汇总快照 `evidence_snapshot.json`。','','| 指标 | 数值 | 分母/口径 | 源代码 | 输出与选择器 |','|---|---:|---|---|---|']
    for e in evidence:
        val=pct(e['value']) if '率' in e['title'] or '比例' in e['title'] else str(e['value'])
        lines.append(f'| {e["title"]} | {val} | {e["formula"]}；分母 {e["denominator"]} | [{e["code"]}:L{e["line"]}](../{e["code"]}#L{e["line"]}) | [{e["output"]}](../{e["output"]})：`{e["selector"]}` |')
    lines+=['','完整说明、原始数值与限制见 [CSV索引](evidence_index.csv) 和 [JSON快照](evidence_snapshot.json)。']
    (OUT/'EVIDENCE_INDEX.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    build_report(b,d,t,late,lm,states)
    print(f'Built final report and {len(evidence)} evidence entries from existing outputs.')

def build_report(b,d,t,late,lm,states):
    state_rows='\n'.join(f'| {states[s]["state_label"]} | {count(states[s]["orders"])} | {count(states[s]["bad_orders"])} | {pct(states[s]["bad_rate"])} | {pct(states[s]["ci95_low"])}–{pct(states[s]["ci95_high"])} |' for s in ['pending_within_promise','pending_overdue','delivered_on_time','delivered_late'])
    report=f'''# Olist 电商履约时效与用户差评风险分析

面向数据分析 / 经营分析校招的统一交付稿。本报告整合基础分析、深度统计审计和评价时序研究，使用已运行结果，不增加研究或模型。[关键指标证据索引](EVIDENCE_INDEX.md)逐项列出代码、输出、分子分母及口径。

## 管理层摘要

1. 99,441笔订单中，96,478笔快照状态为delivered；其中8笔缺实际送达时间，96,470笔用于配送日期分析，6,534笔超过承诺日送达，延迟率 **{pct(b['late_rate_all_valid'])}**。
2. 上述样本中有评价95,824笔：最终延迟订单差评率 **{pct(late['true']['bad_rate'])}**（3,983/6,381），未延迟订单 **{pct(late['false']['bad_rate'])}**（8,289/89,443）。统计控制后关联仍存在，但不能解释为因果效果。
3. 时间审计改变了经营解释：原样本4,653笔收货前评价中，4,429笔评价时已过承诺日期，224笔尚未到期。应区分“失约后仍等待”与“收货后的超期体验”。
4. 在13,126笔承诺节点时尚未首次评价的候选订单中，未见送达组后续30天**评价者**差评率 **{pct(lm['true']['bad_rate_among_30d_reviewers'])}**（5,501/7,943），已送达组 **{pct(lm['false']['bad_rate_among_30d_reviewers'])}**（537/4,101）。这是更接近监控时点的后续关联，仍受问卷触发、取消与作答选择影响。
5. 优先建议核对事件日志，定义“过承诺日、仍活跃、未确认送达”队列，再试验主动告知或异常工单。项目没有上线监控、实施实验、降低差评或证实收益。

## 业务问题与数据边界

平台需要知道履约表现、低评分集中在哪里，以及何时可以识别值得排查的订单。本项目依次回答“最终配送结果与评分是否关联”“关联能否被统计控制后复现”“评价发生时客户究竟处于什么履约状态”。研究从结果关联转向时点明确的风险识别，不把历史结果替代实时特征。

数据为Olist发布的2016–2018年匿名公开交易数据，原始九表分别为订单、客户、商品明细、支付、评价、商品、卖家、地理位置和品类翻译。数据下载与授权请遵守[发布者数据页面](https://www.kaggle.com/olistbr/brazilian-ecommerce/home/)的条款；本项目不附原始CSV。缺少承运商、仓库、取消事件时间、数据入库时间和承诺修改历史，无法重构完整实时状态或归因责任。

## 数据可信度与订单级建表

SQLite先把商品、支付和评价聚合至订单，再关联订单与客户；关联后assert订单数量及order_id唯一。商品和支付的候选键分别为(order_id, order_item_id)、(order_id, payment_sequential)。地理邮编不唯一，不直接JOIN原地理明细表。customer_id在本数据中对应订单，customer_unique_id用于识别重复购买。

评价有99,224条、98,673个订单、98,410个评价ID：789个ID对应多订单、547个订单有多个评价ID、202个订单评分不一致；订单–评价ID组合与完全相同评价行均无重复。不能全局按review_id去重，也不能把无评价当作好评。基础口径按每单最晚review_answer_timestamp取评分，同刻用review_id确定顺序，1–2星为差评；有评分争议的方案单独作敏感性分析。

关键修正：原COUNT(DISTINCT 类目)忽略NULL，使55笔有评价订单被误判为单品类。严格规则要求“非空类目数=1且NULL商品数=0”，单品类有评价样本由93,781变为93,726；加入品类控制后的OR约16.65，结论方向稳定。多卖家订单不任意归给单个卖家。

配送阶段分析另标记165笔负交接时长、23笔负运输时长及1笔缺交接时间，阶段有效样本为96,281。异常仅从相应阶段时长指标中排除，原始数据与订单记录保留。96,470仅表示有实际送达日期，不是“全部字段无异常”。另有6笔取消订单有送达时间，基本配送样本仍按delivered状态定义。

## 样本与指标口径

| 用途 | 人群/分母 | 与其他阶段的区别 |
|---|---:|---|
| 原始订单审查 | 99,441 | 全部快照状态 |
| 配送日期分析 | 96,470 | delivered且实际送达非空 |
| 基础评分关联 | 95,824 | 上述订单中有评价；646笔无评价不进入评分分母 |
| 主Logistic回归 | 95,822 | 再排除2笔稀疏购买月份订单 |
| 阶段耗时 | 96,281 | 交接/运输时间顺序有效 |
| 评价时状态研究 | 98,673 | 全体有评价订单，含未完结、取消、送达缺失 |
| 承诺节点后续首次评价 | 13,126 | 节点已下单、尚未首次评价；不用未来是否评价决定资格 |

承诺日全部为午夜，按日终失约：实际送达日超过承诺日才算延迟，承诺日当日仍算未过期。直接按完整送达时间与预计午夜比较会得到8.11%，而日级口径为6.77%。快照delivered占比97.02%不能当作成熟订单队列的最终履约率。

## 履约、评分与风险规模

有效已送达订单配送时长中位10.22天、90分位23.10天。时间顺序有效阶段样本中，下单至交接中位2.20天，交接至送达中位7.10天。无评价的646笔有效送达订单延迟率23.68%，有评价订单为6.66%，评价缺失明显与配送结果相关。

![最终配送结果与差评](../project/figures/late_bad_rate.png)

图中分母是最终已送达且有评价订单。延迟差评率62.42%与未延迟9.27%的风险比6.74（95% CI 6.55–6.93），不代表消除延迟可以减少同等数量差评。Fisher检验p值在计算中下溢为0，应读作极小而非数学意义上的零。

![延迟程度与差评](../deep_study/delay_gradient.png)

描述性分组中，晚1天差评率19.63%，晚2–3天42.05%，晚4–7天67.68%，晚8–14天80.15%，至少15天78.35%。后两组调整系数差异p约0.063，不能据此声称长期延迟后的风险下降。评价时点的构成差异也可能贡献该曲线。

地区/品类/线路用于规模筛查：RJ客户州有评价订单12,211笔、延迟1,456笔；SP州延迟1,786笔，绝对量更大。严格单品类下，cama_mesa_banho有8,976笔、663笔延迟，beleza_saude有8,530笔、632笔延迟。单卖家且阶段时间有效的SP→RJ线路8,034笔、1,147笔延迟，运输中位9.13天；不能把订单级运输时间直接定责到卖家。各名单未经层级收缩或多重比较校正，不用于直接处罚。

## 统计方法、诊断及稳健性

二元Logistic控制客户州、购买月份、log1p商品金额、运费与件数。statsmodels独立复现主模型OR **{d['model_audit']['main']['or']:.4f}**（95% CI 15.36–17.29），与SciPy实现16.2997一致，最大绝对score约3.3e-10；用户聚类SE比常规SE增加约0.22%。OR是赔率比，不是概率倍数或风险比，聚类SE也不解决未观测混杂。

将3星纳入、取最低/最高评分、排除冲突评价或严格单品类等敏感性分析中，关联方向稳定。信息矩阵条件数较高，模型设定、稀疏哑变量和未观测因素仍有局限。原训练集AUC约0.725仅是表观值；深度研究的时间切分AUC约0.734仍使用最终延迟变量，只代表事后区分，不能作为下单或在途预警能力。

深度报告排除收货前作答后得到OR约2.40，是换了条件人群后的关联，不能称为消除了偏差。另一个按创建时间不早于送达时间筛选的历史OR约2.22，混用了日期级创建字段与秒级送达字段，统一稿不采用它作为核心结论。历史输出保留以展示审计轨迹。

## 评价时点：从最终结果到当时状态

review_answer_timestamp作为评分提交时点代理。review_creation_date的99,139/99,224条为午夜，85条为01:00:00，按日期解释；预计送达全部午夜；四个字段无明确时区，未强行指定或转换。CSV送达字段是事件时间，不是入库时间，下表“已/未见送达”均是记录时序代理。

| 评价时状态 | 订单 | 差评 | 差评率 | Wilson 95% CI |
|---|---:|---:|---:|---:|
{state_rows}

![评价时履约状态](../review_timing_study/review_time_states.png)

四组共98,673笔，范围比原已送达样本大。未见送达组含最终仍缺送达时间和取消/缺货订单，不能直接解释为全部在途。61笔明显顺序矛盾都在“承诺未过、未见送达”组；敏感性排除后该组剩339笔，差评率21.24%，其他三组不变。正常收货前评价没有被删除。

同日评价与送达1,373笔，其中414笔作答时间在前、959笔在后或同时。把同日或相距±1/6/12/24/48小时的记录单列为顺序待定后，逾期未见送达组差评率仍约81%；窗口并不证明时区一致，也不改变缺失送达的含义。每单改取首次评价，主要差异仍在。

原95,824笔样本的4,653笔收货前评价中，4,429笔评价时已逾期，失约当时即可判断；224笔未到承诺日，最终是否延迟未知（180笔最终准时、44笔最终延迟）。所以不能把所有收货前评价都称为泄漏，但在下单时使用最终延迟以及对这224笔作时点解释时，确有未来信息问题。发布者描述到期也可发问卷，失约等待中的反馈有独立业务意义。

## 承诺节点与后续30天首次评价

统一观察点为承诺日期次日00:00。购买日>=2017-01-01，承诺日2017-01-01至2018-06-30；节点已下单、没有更早首次评价。候选资格不根据最终评分、是否最终送达或未来是否评价筛选；后续窗口为[节点,节点+30天)。13,126是跨节点累计候选，不是某天积压存量。

| 节点状态代理 | 候选订单 | 后续首次评价 | 其中差评 | 评价覆盖率 | 评价者差评率（95% CI） |
|---|---:|---:|---:|---:|---:|
| 未见送达 | 8,248 | 7,943 | 5,501 | 96.30% | **69.26%**（68.23%–70.26%） |
| 已送达 | 4,878 | 4,101 | 537 | 84.07% | **13.09%**（12.10%–14.16%） |

69.26%与13.09%仅针对后续作答者。全体候选中观察到首次差评事件比例分别为66.69%与11.01%，不能将未作答解释为满意。未见送达组有2,431笔最终仍无送达时间，取消/缺货可能混入；缺少取消事件日志无法还原真实活跃队列。较早截止日期减少数据尾部截断，但正式抽取时间未知，完整随访仍无法保证。两套SQL/Pandas汇总已独立核对。

## 运营优先级与实验验证设计

| 优先级 | 建议与依据 | 实施前验证 | 后续验证方式（未执行） |
|---|---|---|---|
| 1 | 核实承诺、签收、入库、取消与问卷时间链 | 时区、回填、事件时间和系统可用时间、承诺修改 | 抽样核对源系统日志，制定异常率和日志完整率 |
| 2 | 定义过承诺日仍活跃且未确认送达的队列 | 剔除当时已取消/缺货；按超期日分级，避免用未来信息 | 对节点候选随机分配常规流程与主动告知/异常工单 |
| 3 | 复核RJ、SP→RJ及高绝对量品类 | 仓库、承运商、距离、商品体积、承诺设置 | 在线路/团队存在干扰时考虑群组随机化；禁止依据本名单直接定责 |

实验方案须事前固定人群、触发时点、随访窗和主要指标。可将30天观察到首次差评事件、评价覆盖率、评价者差评率、投诉与客服成本一起报告；不能通过抑制问卷来改善表面指标。实验样本量需基于实际业务基线、最小可检测效果和聚类结构计算，本项目未计算或执行。只有实验或其他可识别设计支持后，才讨论净效果与成本收益。

## 结论可靠范围与尚未完成事项

较可靠：已记录样本内的订单计数、日期口径、组别分子分母；延迟/失约等待与低评分存在明显关联；问卷时点会显著改变业务解释。有限支持：地区、品类、线路名单可作为排查候选；承诺节点队列具有后续低分集中现象。

不能支持：延迟净因果效应、商家或承运商责任、前瞻预警性能、实时积压真实历史、降低差评或经营收益。主要限制包括观察性混杂、问卷触发与评价选择、时间精度与入库时间缺失、最终状态筛选、缺少取消历史和数据末端截断。区间未涵盖这些系统性不确定性。

完整复现记录见[复现说明](REPRODUCIBILITY.md)与[机器记录](reproducibility.json)。发布准备与Git检查见[交付清单](DELIVERY_CHECKLIST.md)。本统一稿不替换历史报告；历史中被审计限定的解释以本稿及证据索引为准。
'''
    (OUT/'FINAL_REPORT.md').write_text(report,encoding='utf-8')

if __name__=='__main__':build()
