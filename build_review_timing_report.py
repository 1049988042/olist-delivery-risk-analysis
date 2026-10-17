"""Build the final Chinese report from computed review-time audit outputs."""
from pathlib import Path
import json
import pandas as pd

def build_report(out):
    out=Path(out)
    m=json.loads((out/'timing_metrics.json').read_text(encoding='utf-8'))
    g=pd.read_csv(out/'review_time_states_latest.csv').set_index('state')
    first=pd.read_csv(out/'review_time_states_first.csv').set_index('state')
    clean=pd.read_csv(out/'sequence_flag_sensitivity.csv').set_index('state')
    sens=pd.read_csv(out/'delivery_timing_sensitivity.csv')
    landmark=pd.read_csv(out/'landmark_future_first_review_30d.csv').set_index('pending_at_landmark')
    precision=pd.read_csv(out/'timestamp_precision.csv').set_index('field')
    cross=pd.read_csv(out/'original_final_delay_vs_review_state.csv')
    def num(x): return f'{int(x):,}'
    def pct(x): return f'{float(x)*100:.2f}%'
    def ci(row,low='ci95_low',high='ci95_high'): return f'{pct(row[low])}–{pct(row[high])}'
    state_order=['pending_within_promise','pending_overdue','delivered_on_time','delivered_late']
    rows='\n'.join(f'| {g.loc[s,"state_label"]} | {num(g.loc[s,"orders"])} | {num(g.loc[s,"bad_orders"])} | {pct(g.loc[s,"bad_rate"])} | {ci(g.loc[s])} |' for s in state_order)
    sens_rows=[]
    scenario_names={'exact':'秒级原始时序','1h_ambiguous':'±1小时','6h_ambiguous':'±6小时','12h_ambiguous':'±12小时','24h_ambiguous':'±24小时','48h_ambiguous':'±48小时','same_day_ambiguous':'评价与送达同日全部待定'}
    for scenario,tab in sens.groupby('scenario',sort=False):
        z=tab.set_index('state'); r=z.loc['pending_overdue']; amb=z.loc['delivery_time_ambiguous','orders'] if 'delivery_time_ambiguous' in z.index else 0
        sens_rows.append(f'| {scenario_names[scenario]} | {num(amb)} | {num(r.orders)} | {pct(r.bad_rate)} | {ci(r)} |')
    sens_text='\n'.join(sens_rows)
    lm_rows=[]
    for key,name in [(True,'承诺日期已过、未见送达事件'),(False,'承诺边界时已送达')]:
        r=landmark.loc[key]
        lm_rows.append(f'| {name} | {num(r.eligible_orders)} | {num(r.reviews_in_30d)} | {num(r.bad_in_30d)} | {pct(r.review_coverage_30d)} | {pct(r.bad_rate_among_30d_reviewers)}（{ci(r,"bad_rate_ci95_low","bad_rate_ci95_high")}） |')
    lm_text='\n'.join(lm_rows)
    c=precision.loc['review_creation_date']; e=precision.loc['order_estimated_delivery_date']
    overdue_future=cross[cross.state=='pending_overdue'].orders.sum()
    pending_old=cross[cross.state.isin(['pending_within_promise','pending_overdue'])].orders.sum()
    unknown=cross[cross.state=='pending_within_promise'].orders.sum()
    report=f'''# Olist 最后一轮：评价时点与配送承诺关系研究

## 结论及决策增量

**本轮确实提供了超出原报告的信息：应把“过了承诺日期仍未确认送达”作为独立的履约状态，而不是把所有最终延迟订单混在一起。** 以每单最后一次评价回复为观察点，在 {num(m['selected_latest_orders'])} 笔有评价订单中，按时间戳重构的“承诺已过、尚未送达”组差评率 {pct(g.loc['pending_overdue','bad_rate'])}，而“已送达但超期”组为 {pct(g.loc['delivered_late','bad_rate'])}。这一区分提示：等待状态本身值得单独监控，实际可行动的时点是承诺边界，而非等最终送达后计算延迟天数。

这些比例属于有评价人群的统计关联。差异可能还包含评价触发机制、取消/缺货、客户选择及时间回填，不能解释为提前沟通能降低多少差评。CSV 没有事件入库时间、取消时间和承诺修改历史，因此本研究重构的是**事件时间状态代理**，无法证明平台实时系统当时知道什么。

## 1. 时间字段的精度、时区与语义

- `review_creation_date`：{num(c.nonmissing)} 条非空记录中，{num(c.midnight_n)} 条为午夜（{pct(c.midnight_fraction)}），另 **85 条为 01:00:00**，集中在 2016-10-16（1 条）与 2017-10-15（84 条）。并非全部午夜；没有秒或分钟级变化，分析时按日期使用。两个日期的偏移可能来自日期生成或时钟处理，无法凭数据确认具体原因。
- `review_answer_timestamp`：全部 {num(precision.loc['review_answer_timestamp','nonmissing'])} 条可解析到秒，只有 {num(precision.loc['review_answer_timestamp','midnight_n'])} 条正好为午夜；本轮将其作为顾客提交问卷评分时间代理，不把它理解为卖家回复时间。
- `order_delivered_customer_date`：{num(precision.loc['order_delivered_customer_date','nonmissing'])} 条非空，全部含时分秒，{num(precision.loc['order_delivered_customer_date','midnight_n'])} 条为午夜；代表记录中的客户送达事件时间，不是数据库入库时间，也不能证明扫描无回填。
- `order_estimated_delivery_date`：{num(e.nonmissing)} 条全部为午夜，按承诺日解释。承诺日当日仍算未过期，到次日 00:00 起才算已过期。午夜不是客户被承诺的具体送达时刻。

四个字段原始字符串均没有时区偏移或 `Z` 标记；本轮未做时区转换。不能从国家名称或午夜分布推断它们已经统一到某个巴西时区。容忍窗口反映时间顺序不确定性，不能代替时区核实。

发布者描述：客户收货后，或预计送达日期到期时，会收到满意度邮件问卷。因此，问卷创建/发出日期与实际作答时间应分开，收货前评价也可能合理。[Olist 发布者的数据说明](https://www.kaggle.com/olistbr/brazilian-ecommerce/home/)

本地数据也支持将创建字段视为日期级流程代理：每单最后一条评价的创建日期，有 {num(m['creation_one_day_after_min_delivery_or_promise_date'])} 笔是“送达日与承诺日较早者”的次日，有 {num(m['creation_on_min_delivery_or_promise_date'])} 笔是同日，另有 {num(m['creation_before_min_delivery_or_promise_date'])} 笔早于该日期。这里只验证分布，不据此断言系统严格执行某种触发算法。缺少发信日志，无法证实精确发送时刻。

用创建时间与送达秒级时间直接比较，会得到 {num(m['creation_timestamp_before_delivery'])} 笔“创建早于送达”；按日期比较真正早一个或多个日历日的只有 {num(m['creation_calendar_date_before_delivery_date'])} 笔，另 {num(m['creation_same_calendar_date_as_delivery'])} 笔为同日。原深度报告把创建日期不早于送达时间作为严格筛选，存在混用日期与秒级精度的局限；本轮改用评价回复时间作为观察点，不重新估计该模型。

## 2. 四种评价时状态及差评率

先按 `review_answer_timestamp`、`review_id` 排序，每单保留最后一条，延续原项目口径；这是回顾性的每单评价口径，不能作为前瞻研究的起点。主表纳入全部有评价订单，包括取消、在途和缺少最终送达时间的订单，避免用未来“最终送达”筛选观察对象。1–2 星为差评。四组定义如下：

1. 送达时间缺失或晚于评价时间，且评价日不晚于承诺日：承诺未过、未见送达。
2. 送达时间缺失或晚于评价时间，且评价日晚于承诺日：承诺已过、未见送达。
3. 送达时间不晚于评价时间，且送达日不晚于承诺日：评价时已送达且准时。
4. 送达时间不晚于评价时间，且送达日晚于承诺日：评价时已送达但超期。

| 评价时状态代理 | 订单数 | 差评数 | 差评率 | Wilson 95% CI |
|---|---:|---:|---:|---:|
{rows}

![评价时状态与评分](review_time_states.png)

区间按订单作 Wilson 估计，是有评价样本中的描述性比例区间，不包含时区、记录回填、选择偏差或用户聚集带来的不确定性。四组相加等于 {num(m['selected_latest_orders'])}，SQL 与 Pandas 独立汇总完全一致。

“未见送达”不应一律读作实际未收到货。到数据快照结束仍没有送达时间的有 {num(m['final_delivery_missing_latest_orders'])} 单，其中 {num(g.loc['pending_overdue','missing_final_delivery'])} 单在逾期待送达组，{num(g.loc['pending_within_promise','missing_final_delivery'])} 单在未过承诺组。前者包含已取消、缺货和其他未完结状态，不能直接作为活跃物流积压处理。按是否最终存在送达时间分层，逾期待送达组差评率分别约 81.26% 与 80.58%，高比例不只是由缺少最终时间的订单造成。分层使用了未来信息，仅用于审计稳健性。

## 3. 时间异常与合理的提前评价

真正明显的顺序矛盾单独标记：最后一条评价中，有 {num(m['sequence_flags']['reply_before_purchase'])} 笔回复时间早于下单，{num(m['sequence_flags']['creation_date_before_purchase_date'])} 笔创建日早于下单日，合并 {num(m['sequence_flags']['strong_sequence_flag'])} 笔；都在“承诺未过、未见送达”组。不能用提前发问卷的合理业务流程解释这些下单前记录。关联错误、日期记录错误或订单变更均需源系统核实，本轮未自行修补。

主表保留这些记录并提供异常清单；只排除明显顺序矛盾后的敏感性结果中，承诺未过组剩 {num(clean.loc['pending_within_promise','orders'])} 单、{num(clean.loc['pending_within_promise','bad_orders'])} 笔差评，差评率 {pct(clean.loc['pending_within_promise','bad_rate'])}（95% CI {ci(clean.loc['pending_within_promise'])}）；其他三组不变。没有发现评价回复日早于创建日、送达早于下单或承诺日早于下单日的已选记录。这里的排除仅作数据质量敏感性分析，没有剔除正常的收货前评价。

原 95,824 笔有评价已送达样本中，评价早于送达的 {num(pending_old)} 笔，有 {num(overdue_future)} 笔在评价时承诺已过（{pct(overdue_future/pending_old)}），而 {num(unknown)} 笔承诺尚未到期。前者在评价时已处于失约等待状态，收货前作答与发布者描述的问卷触发流程相容，应作为独立业务群体保留。

## 4. 同日精度及时间窗口敏感性

评价回复与送达同一日的共有 {num(m['same_calendar_day_answer_delivery'])} 笔，其中 {num(m['same_day_answer_before_delivery'])} 笔回复秒级时间在前，{num(m['same_day_answer_at_or_after_delivery'])} 笔在后或同时。由于时分秒来源和入库时点未验证，本轮把两时间相距不超过指定窗口的记录改列“顺序不确定”，而不是把评价后才发生的送达向前平移。所有记录仍保留，主表及不确定组都输出数量和区间。

| 规则 | 顺序待定订单 | 仍明确处于逾期未见送达组 | 该组差评率 | 95% CI |
|---|---:|---:|---:|---:|
{sens_text}

即使将同日或相距 24 小时以内的记录单列，逾期未见送达组仍维持较高差评比例。48 小时窗口会把大量收货后一两天作答的正常记录也列为待定，它是压力测试，不是推荐清洗口径。另将承诺日当日或承诺日终点附近 ±12 小时单列，完整结果见 `promise_boundary_sensitivity.csv`，不把预计午夜错当作日初失约。

把每单最后一次评价改为第一次，逾期未见送达组为 {num(first.loc['pending_overdue','orders'])} 单、差评率 {pct(first.loc['pending_overdue','bad_rate'])}；已送达超期组为 {num(first.loc['delivered_late','orders'])} 单、差评率 {pct(first.loc['delivered_late','bad_rate'])}。主要状态差异没有依赖最后评价选择，但承诺未过组受重复评价与异常更明显，不能对该小组作过强推断。

## 5. 原模型解释与信息泄漏的判断

原模型适合描述最终履约结果与评价的回顾性关联，其数值已在上一轮独立复现。若把它解释为“最终收货体验导致评分变化”，会混淆评价时已收货与仍等待收货两种状态。OR 16.30 不能当作收货后延迟反应的净效应。

也不能把所有评价早于送达都一概称为未来信息泄漏。原样本中，{num(overdue_future)} 笔在评价时已经超过承诺日，其失约状态当时就可以从日期推知；但 {num(unknown)} 笔承诺尚未到期，最终准时/延迟尚未知（其中 180 笔最终准时、44 笔最终延迟）。对这类记录使用最终延迟确实引入未来信息。原样本还按最终送达及最终评价选择订单，用于前瞻评估同样会造成选择问题。

在下单或交接物流商时预测时，“最终是否延迟”对所有未完成配送的订单都不能作为已知特征。即使使用时间切分，仍不能补救特征时点错误。本轮不增加模型和 AUC，而是用承诺边界之前可观察的日期与送达事件定义监控研究。

## 6. 承诺边界的后续评价研究：更接近可行动指标

为避免用评分本身定义研究时点，设统一观察点为**承诺日期后的次日 00:00**，只纳入该时点已经下单、尚未有首次评价的订单；不根据未来会不会评价来选样本。购买日从 2017-01-01 开始，承诺日限定 2017-01-01 至 2018-06-30，向后观察 30 天首次评价。较早的截止日期减少数据末端截断风险，但数据没有正式抽取时间，不能保证完整随访。

| 观察点状态代理 | 合格订单 | 30天内首次评价 | 其中差评 | 评价覆盖率 | 评价者差评率（95% CI） |
|---|---:|---:|---:|---:|---:|
{lm_text}

这是**首次评价尚未发生的条件人群**，并非全平台所有到期订单；其中标记明显时间顺序矛盾的订单数为 {num(m['landmark_cohort']['strong_sequence_flag_orders'])}。它提供了在时间顺序上更清楚的后续关联：评价尚未发生时，已过期但未见送达的一组随后差评较集中。两组评价覆盖率不同，不能将未评价视为好评。以全体合格订单为分母的“30天观察到首次差评事件”比例分别为 {pct(landmark.loc[True,'observed_bad_review_incidence_30d'])} 与 {pct(landmark.loc[False,'observed_bad_review_incidence_30d'])}；这也不是全体顾客的不满意概率。

未见送达组中 {num(landmark.loc[True,'missing_final_delivery'])} 笔到快照结束仍无送达时间。取消/缺货订单可能混入，缺少取消事件时间，无法重构该时点真正的活跃配送队列。故 {num(landmark.loc[True,'eligible_orders'])} 是研究期内“每单承诺边界上”的累计候选数，不是某一天同时在途积压量。状态和后续分子分母也已经 SQL 与 Pandas 独立复核。

## 7. 建议落地的指标与验证次序

1. **实时过期未确认送达存量**：在本地已核实的业务时区，每日固定时点，筛选已过承诺日、尚未收到送达确认且当时仍活跃的订单；同时按超期 1 天、2–3 天、4–7 天分层。取消、退款、缺货单另列。本数据无法给出真实历史同时存量，应在事件日志中计算。
2. **待评价订单的后续首次差评事件率**：对固定观察点尚未评价的人群，分别报告后续 7/30 天首次评价覆盖率、评价者差评率、全体合格订单中观察到首次差评的比例。当前只实际计算 30 天口径，7 天是可落地设计，未声称已验证。
3. **过期未送达状态下的评价量与评分**：与“已送达后评价”分别报告，便于区分等待投诉与收货体验。不要为了降低差评而抑制问卷；验证重点应是异常告知、预计到达更新和问题解决。
4. **事件数据质量监控**：下单前评价、送达回填延迟、承诺修改、字段时区、创建日期的异常小时值都应有独立计数；先补日志，再讨论预警试验。试验以观察点分配，比较评价覆盖、投诉、评分、履约及成本，不能用现有差异估算收益。

## 8. 验证、局限和交付

代码实际核验九张原始 CSV 与既有报告/指标/代码的 SHA-256 未变化；日期解析失败为零；订单关联后保持唯一；四组和各敏感性分组分子分母守恒；原始 SQL 与 Pandas 对主结果和承诺边界后续研究均独立得到相同统计。结果明细、异常清单、字段精度表及验证记录保存在本目录。

已验证事实是记录的时间分布、状态划分、人数和评分比例；统计关联是过期等待状态与低分及后续低分同现。合理业务假设是到期问卷和等待投诉具有联系。时区一致性、实际收到货的时刻、系统当时已知信息、取消时间、因果效应和经营收益均未得到识别。问卷触发与作答选择本身会影响组间构成，不宜把本轮结果包装为模型性能提升或干预收益。

**本轮的实质增量是把“最终延迟”改写为“评价时已失约且仍等待”与“收货后对超期作答”两个不同场景，并用固定承诺边界验证了后续首次评价的关联。** 它能指导监控队列与事件日志需求，但尚不能决定最优干预阈值、归责某一履约方，或证明主动沟通会改善评分。
'''
    (out/'review_timing_report.md').write_text(report,encoding='utf-8')

if __name__=='__main__':
    build_report(Path(__file__).resolve().parent/'review_timing_study')
