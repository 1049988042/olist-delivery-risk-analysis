"""Present verified existing results. Does not run research or rewrite old reports."""
from pathlib import Path
import csv, json

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'portfolio_delivery'
def load(p):return json.loads((ROOT/p).read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader((ROOT/p).open(encoding='utf-8-sig',newline='')))
def write(p,text):(ROOT/p).write_text(text,encoding='utf-8')
def main():
    baseline=load('project/metrics.json');timing=load('review_timing_study/timing_metrics.json');deep=load('deep_study/deep_metrics.json')
    decision=load('decision_study/priority_metrics.json')
    policies=rows('decision_study/priority_backtest.csv')
    get=lambda name:next(r for r in policies if r['strategy']==name and float(r['capacity_fraction'])==.2)
    chosen,stage,wait=get('geo_four_cell'),get('stage_wait'),get('oldest_purchase')
    assert baseline['order_rows']==99441 and baseline['delivered_valid']==96470
    assert timing['landmark_cohort']['eligible_orders']==13126
    assert int(chosen['candidate_orders'])==4709 and int(chosen['selected_orders'])==895
    assert int(chosen['all_bad_events'])==3157
    assert float(chosen['selected_bad_events'])==712 and float(wait['selected_bad_events'])==620 and float(stage['selected_bad_events'])==704
    assert round(float(chosen['recall_gain_vs_wait_pp']),2)==2.91
    evidence=load('final_delivery/evidence_snapshot.json')['metrics']
    source='decision_study/priority_study.py'
    code=(ROOT/source).read_text(encoding='utf-8').splitlines()
    def add(key,title,value,output,selector,denominator,formula,anchor,notes):
        line=next(i+1 for i,text in enumerate(code) if anchor in text)
        evidence.append({'key':key,'title':title,'value':value,'code':source,'line':line,'code_anchor':anchor,'output':output,'selector':selector,'denominator':denominator,'formula':formula,'notes':notes})
    add('priority_test_n','优先级时间测试候选',4709,'decision_study/priority_metrics.json','cohorts[split=test].orders',4709,'2018-01至06月各订单D+1新增候选','dev=period(primary','2017年定规则；无首次评价且T时未见送达，不用最终状态筛选')
    add('priority_event_n','测试30天观察到首次差评事件',3157,'decision_study/priority_metrics.json','cohorts[split=test].bad_events_30d',4709,'3157/4709=67.04%','def make_cohort','未评价不等于满意；事件窗口(T,T+30天]')
    add('priority_review_n','测试30天首次评价覆盖',4547,'decision_study/priority_metrics.json','cohorts[split=test].first_reviews_30d',4709,'4547/4709=96.56%','def make_cohort','实际评价者差评率3157/4547=69.43%')
    for policy,label in [('oldest_purchase','购买等待'),('stage_wait','交接状态＋阶段等待'),('geo_four_cell','四组＋有支持的客户州')]:
        record=get(policy)
        add('priority_'+policy,'20%模拟能力：'+label,float(record['event_recall']),'decision_study/priority_backtest.csv','capacity_fraction=.2;strategy='+policy,3157,f"{int(float(record['selected_bad_events']))}/3157；同样选择895单",'def evaluate','按日floor预算，实际19.01%候选；不是可减少差评数')
    add('priority_gain','冻结规则对等待基准覆盖增量（百分点）',float(chosen['recall_gain_vs_wait_pp']),'decision_study/priority_backtest.csv','capacity_fraction=.2;strategy=geo_four_cell;recall_gain_vs_wait_pp',3157,'100*(712-620)/3157','def evaluate','配对周Bootstrap95%区间[2.00146,3.82343]；相对随机期望增量3.52035个百分点')
    add('priority_gain_ci','冻结规则覆盖增量95%区间（百分点）',[float(chosen['gain_vs_wait_ci_low_pp']),float(chosen['gain_vs_wait_ci_high_pp'])],'decision_study/priority_backtest.csv','gain_vs_wait_ci_low_pp/high_pp;geo_four_cell;.2',3157,'2000次配对日历周Bootstrap','def evaluate','分数固定；不覆盖混杂、状态缺失、训练估计和政策迁移不确定性')
    complexity=next(r for r in rows('decision_study/complexity_increment.csv') if r['comparator']=='stage_wait' and float(r['capacity_fraction'])==.2)
    add('geography_marginal_gain','地区细化相对简单阶段规则增量（百分点）',float(complexity['recall_gain_pp']),'decision_study/complexity_increment.csv','capacity_fraction=.2;comparator=stage_wait',3157,'100*(712-704)/3157','def evaluate','只多8事件；区间[-0.24121,0.70156]，不支持稳定的地区边际价值；独立审计实现见verification.py')
    add('selected_terminal_status','冻结选择中最终取消或缺货（事后审计）',227,'decision_study/allocation_crosscheck_and_outcome_context.csv','geo_four_cell;.2;selected_final_canceled+selected_final_unavailable',895,'102+125=227；最终状态不参与排序','selected=details','取消发生时间未知；不是T时已取消数量，不能按未来状态剔除重选')
    write('portfolio_delivery/evidence_snapshot.json',json.dumps({'scope':'Existing results only; legacy evidence retained, decision-study references added','metrics':evidence},ensure_ascii=False,indent=2))
    table=[]
    for e in evidence:
        value=json.dumps(e['value'],ensure_ascii=False)
        table.append(f"| {e['title']} | {value} | {e['denominator']}；{e['formula']} | [{e['code']}:{e['line']}](../{e['code']}#L{e['line']}) | [{e['output']}](../{e['output']})：`{e['selector']}` |")
    write('portfolio_delivery/EVIDENCE_INDEX.md','# 展示指标证据索引\n\n本轮不新增研究数字。保留原30项证据并增加决策回测索引；原始比例按0–1存储，百分点另有标注。完整精度、限制和代码锚点见[evidence_snapshot.json](evidence_snapshot.json)。\n\n| 指标 | 原始值 | 分母与口径 | 代码 | 统计输出与选择器 |\n|---|---|---|---|---|\n'+'\n'.join(table)+'\n')
    write('README.md','''# Olist 电商履约时效与用户差评风险分析

**数据分析 / 经营分析校招作品集｜从九表治理、统计关联与评价时序，走到有限客服资源下的处置优先级回测。**

平台哪些履约问题更值得关注？评价发生时客户是否已经遭遇失约？对于刚超过承诺日期、尚未确认送达且尚未首次评价的订单，客服应该先核查谁？本项目用公开历史数据回答这些问题，并保留无法识别因果效果的边界。

**快速入口：[中文主报告](final_delivery/FINAL_REPORT.md) · [优先级回测报告](decision_study/DECISION_REPORT.md) · [展示指标证据](portfolio_delivery/EVIDENCE_INDEX.md) · [实际复现记录](portfolio_delivery/REPRODUCIBILITY.md) · [简历与5个面试追问](portfolio_delivery/RESUME_AND_INTERVIEW.md)**

## 最值得看的发现

| 业务问题 | 已验证结果 | 可以支持的判断 |
|---|---|---|
| 履约表现如何？ | 原始99,441单；96,470笔有实际送达日期的delivered订单中，6,534单超过承诺日，延迟率 **6.77%** | 按日期判断，避免把承诺日午夜当作日终 |
| 延迟是否伴随更多差评？ | 有评价有效送达订单中，延迟组 **62.42%**（3,983/6,381），未延迟组 **9.27%**（8,289/89,443）；statsmodels调整OR **16.30** | 强观察性关联；OR不是概率倍数或因果效果 |
| 风险在什么时候可见？ | 13,126笔承诺节点未首次评价候选中，未见送达/已送达组后续30天**评价者**差评率 **69.26% / 13.09%** | 应同时报告评价覆盖率 **96.30% / 84.07%**；无评价不是满意 |
| 有限容量下先处理谁？ | 2018年1—6月时间留出：每日20%模拟容量实际选择895单；冻结规则覆盖712/3,157个后续事件，**22.55%**，购买等待基准为 **19.64%**；增量 **+2.91个百分点［95%区间+2.00至+3.82］** | 同等模拟容量能集中更多已观察风险；不代表能减少92个差评 |
| 是否需要复杂地区规则？ | 简单“交接状态＋阶段等待”已覆盖704个事件；地区细化再多8个，**+0.25个百分点［-0.24至+0.70］** | 地区细化的稳定边际价值尚未得到证明 |

主回归控制客户州、月份、金额、运费与件数；用户聚类标准误及多种口径敏感性已复核。所有发现的代码、输出、公式和分母见[证据索引](portfolio_delivery/EVIDENCE_INDEX.md)。

## 三分钟看懂业务价值

### 1. 评价时，客户处在什么履约状态？

![评价提交时履约状态及差评率](review_timing_study/review_time_states.png)

“承诺已过但未见送达”的差评率81.01%，而“已送达但超期”为19.44%。评价时状态与最终配送结果回答不同问题；未见送达可能包含取消、缺货或记录缺失，不能全部视为在途。

### 2. 同等模拟客服容量，规则能覆盖更多风险吗？

![20%按日预算相对购买等待基准的覆盖增量与区间](decision_study/paired_increment.png)

2017年确定阈值与规则，训练结果观察窗完整早于2018年测试。简单阶段分流已有增量；地区细化额外收益不确定。图中区间反映历史抽样波动，不能解释为干预效果。[图表导读与其他已验证图表](portfolio_delivery/VISUAL_GUIDE.md)

## 建议怎样行动

先补齐事件入库、取消与承诺变更日志，核实订单仍活跃；未确认交接的核查商家/仓库交接凭据，已交接且等待较长的跟进物流，其他订单可考虑自动状态同步。未确认交接不等于未发货，也不能据线路直接归责承运商。

最佳规则选中的895单里，227单最终取消或缺货，发生时点未知。高风险不等于可挽回，当前增量不能直接用于剔除非活跃订单后的真实队列。真实效果需预先定义人群、成本与评价覆盖，再做随机干预验证；本项目未实施。

## 研究流程与技术

| 阶段 | 解决的问题 | 主要实现与成果 |
|---|---|---|
| 订单治理与基础关联 | 九表粒度、一对多JOIN、评价冲突、配送表现 | [订单汇总SQL](project/analysis.sql)、[基础代码](run_project.py)、[基础报告](project/report.md) |
| 深度统计审计 | NULL单品类误判、负物流时长、回归复现与非线性 | [修正SQL](deep_study/deep_analysis.sql)、[审计代码](deep_audit.py)、[深度报告](deep_study/deep_report.md) |
| 评价时序与承诺节点 | 评价前已知信息、收货前评价、后续首次差评 | [时序代码](review_timing_study.py)、[节点SQL](review_timing_study/landmark_future_review.sql)、[时序报告](review_timing_study/review_timing_report.md) |
| 异常订单处置优先级 | 时间留出、按日容量、简单规则与基准比较 | [回测代码](decision_study/priority_study.py)、[独立SQL](decision_study/allocation_validation.sql)、[完整报告](decision_study/DECISION_REPORT.md) |

**技术栈：** Python 3.12、Pandas、NumPy、SQLite、SciPy、statsmodels、scikit-learn、Matplotlib。SQL承担订单预聚合、粒度控制和独立结果核验；统计方法包括Wilson区间、比例检验、Logistic回归、用户聚类稳健标准误及配对周Bootstrap。处置研究采用可解释规则，没有增加机器学习模型。

[完整阅读路线与目录](portfolio_delivery/PROJECT_GUIDE.md) · [历史口径修正衔接](final_delivery/STAGE_RECONCILIATION.md)

## 复现已有结果

1. 从[Olist发布者页面](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)取得九张CSV，保持原名放在项目根目录；原始数据不随仓库分发。数据及改编材料的署名、非商业和相同方式共享条件见[数据许可说明](portfolio_delivery/DATA_LICENSE.md)。
2. 安装Python 3.12，在项目根目录执行：

```powershell
python -X utf8 portfolio_delivery/reproduce_portfolio.py
```

脚本创建全新虚拟环境（不继承系统包），安装[固定直接依赖](requirements-repro.txt)及[传递版本约束](final_delivery/environment.freeze.txt)，复制原代码和数据到忽略的`.repro_runs/portfolio_*/`，实际重跑四阶段计算，再比较JSON和聚合CSV。原始CSV、历史报告、输出和研究代码均不回写。需要可用的依赖安装源和本地空间；实际执行范围与未验证事项见[本轮复现记录](portfolio_delivery/REPRODUCIBILITY.md)。

旧交付脚本和历史复现记录完整保留。当前首页推荐上面的隔离流程，以便把decision_study一起验证。[GitHub发布清单](portfolio_delivery/GITHUB_CHECKLIST.md)尚不代表已提交或发布。

## 解释边界

- 基础关联取每单最后回复评分；承诺节点和处置回测使用首次评价，分母不可互换。
- 观察性数据、评价触发与作答选择、最终状态筛选及未观测混杂限制因果解释。最终延迟变量及旧AUC不证明下单或在途预警能力。
- 缺少事件入库、取消时点、时区、承诺变更和正式抽取时间；回测是事件时间重构，不证明真实线上可用性或完整随访。
- 容量比例是假设；没有滚动积压、多次处置或真实处理成本模拟。D+7队列没有可靠增量证据。
- 处置研究按时间留出，但此前研究已查看2018年总体数据，不是外部盲测。
- 项目没有上线监控、真实客服干预、完成A/B实验、降低差评或验证经营收益。历史报告中的被审计解释以统一稿及后续研究限制为准。

本仓库是独立公开数据分析作品，不代表Olist官方立场。数据来源为Olist，许可为[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)；原创代码许可尚待作者确定，不将上游数据误标为MIT。
''')
    write('portfolio_delivery/PROJECT_GUIDE.md','''# 项目阅读路线与保留结构

## 招聘方阅读顺序

1. [根README](../README.md)：业务问题、可信发现、两张核心图和建议。
2. [统一中文报告](../final_delivery/FINAL_REPORT.md)：基础、统计审计、评价时序与承诺节点；原报告完整保留。
3. [处置优先级报告](../decision_study/DECISION_REPORT.md)：补充有限资源下的时间留出回测，不能替代活跃状态或干预效果验证。
4. [指标证据](EVIDENCE_INDEX.md)、[复现记录](REPRODUCIBILITY.md)：追溯数字和实际运行边界。
5. [简历与面试](RESUME_AND_INTERVIEW.md)：用订单粒度、时间顺序、选择偏差解释项目，而非堆叠模型。

## 建议公开结构（现有路径保留）

```text
README.md                         招聘方首页
.gitignore                        数据、逐单衍生和运行环境排除
requirements*.txt                 历史与固定直接依赖
audit_olist.py                     九表质量审查
run_project.py                    基础计算与订单预聚合SQL
deep_audit.py                     独立统计复核与阶段研究
review_timing_study.py             评价时序与节点队列
build_review_timing_report.py      时序报告生成
project/                          基础报告、SQL、聚合指标、图表
deep_study/                       修正规则、回归与稳健性输出
review_timing_study/               时序、首次评价、节点SQL与聚合结果
final_delivery/                    历史统一交付、30项证据、复现及面试材料
decision_study/                    冻结设计、回测、容量、独立SQL、审计与图表
portfolio_delivery/               本轮首页整理、扩展证据、简历、许可与验收
  history/                        本轮开始前README/.gitignore备份
  reproduce_portfolio.py          只在新副本重跑已有计算
  verify_portfolio.py             历史保护、发布范围、链接及敏感模式扫描
  publication_manifest.csv        拟公开清单，尚未暂存
```

本地另有九张原始CSV、audit_deps、.repro_runs和逐单审计，均不进入公开版本；不使用*.csv全局忽略，保留聚合结果。原始地理CSV大于50MiB，无需Git LFS，读者从发布者获取。

## 口径衔接

| 分析 | 单位与评分 | 分母/时点 | 正确用途 |
|---|---|---|---|
| 最终延迟关联 | 每单最后回复；1–2星 | 95,824笔有评价有效送达；回归95,822 | 回顾性关联，非预警或因果效果 |
| 评价时履约状态 | 每单最后回复；首次作敏感性 | 98,673笔有评价订单 | 区分失约等待与收货体验 |
| 承诺节点研究 | 每单首次评价 | 13,126笔节点未首次评价者；含已/未见送达 | 后续评价风险集中与分母辨析 |
| 处置优先级 | 每单首次评价；30天首次1–2星事件 | 全参考8,248笔未见送达；测试4,709笔；每日新增D+1 | 固定模拟资源的风险事件覆盖 |

时序历史窗口[节点,节点+30天)，优先级窗口(T,T+30天]；当前边界无相等记录，未见送达参考计数同为8,248/7,943/5,501。不是将不同窗口视为通用等价。D+3、D+7单独分析，有订单重叠，禁止相加。

历史单品类表和旧AUC保留审计轨迹；品类采用深度研究的NULL严格规则。完整限定见[三阶段衔接](../final_delivery/STAGE_RECONCILIATION.md)。本轮不重新拟定规则、不增加研究或模型。
''')
    write('portfolio_delivery/RESUME_AND_INTERVIEW.md','''# 简历项目描述与5个典型追问

## 可用于校招简历的项目描述

**Olist电商履约时效与差评风险分析｜Python、SQL、统计分析、业务回测**

- 基于九张公开表、99,441笔订单，使用SQLite先聚合商品、支付和评价再关联，建立订单粒度分析表；审查多评价、异常时序及NULL品类误判，并用独立统计实现和敏感性检验核验关联。
- 围绕配送承诺与评价时点开展研究：有评价有效送达订单中，延迟与未延迟组差评率为62.42%和9.27%；进一步构建13,126笔承诺节点候选，区分候选事件比例、评价覆盖率和评价者差评率。
- 设计可解释的异常订单分流规则，以2017年确定参数、2018年1—6月作时间留出。在每日20%模拟容量、同样选择895单时，冻结规则覆盖712个后续首次差评事件，覆盖率22.55%，较购买等待基准提高2.91个百分点（95%区间2.00–3.82）；明确其为历史风险覆盖，非客服干预收益。

精简版：**完成Olist九表订单治理、Logistic与评价时序审计，设计有限容量下的异常订单优先级回测；时间留出中相同895单资源覆盖率由19.64%提升至22.55%，同时识别地区规则增量不确定和取消时点缺失等落地限制。**

所有数字见[证据索引](EVIDENCE_INDEX.md)。禁止改写为“减少92个差评”“降低差评14.84%”“上线预警系统”或“已完成A/B实验”。提高的是模拟选择中的已观察事件覆盖率。

## 1. 为什么一定要先统一订单粒度？评价重复怎么处理？

**回答要点：** 商品、支付、评价都是一对多，直接JOIN会让商品×支付×评价笛卡尔式膨胀。先各自聚合至order_id，并验证订单唯一、总数和分子分母。review_id也不是全局订单主键，不能全局去重；基础按最后回复，节点按首次回复；1–2星为主，1–3星和多评分方案作敏感性。NULL品类不被COUNT(DISTINCT)计入，修正要求非空品类数=1且NULL商品数=0。

**可展示证据：** [修正SQL](../deep_study/deep_analysis.sql)、[历史口径衔接](../final_delivery/STAGE_RECONCILIATION.md)。55笔有评价订单被修正，不等于全订单仅55笔受影响。

## 2. Logistic OR约16.30意味着什么？为什么仍不能谈因果？

**回答要点：** 控制客户州、购买月份、金额、运费和件数后，延迟系数的指数为赔率比，不是概率倍数。statsmodels独立复现、收敛/梯度、常规与用户聚类SE均有核验。未观测混杂、评价选择、最终送达样本筛选和评价时序仍存在；显著性和聚类SE都不解决因果识别。旧AUC即使时间切分，也含最终延迟变量，不能称为在途预警能力。

**可展示证据：** [深度指标model_audit](../deep_study/deep_metrics.json)、[统一报告](../final_delivery/FINAL_REPORT.md)。

## 3. 为什么不删除收货前评价？决策回测怎样避免未来信息？

**回答要点：** 发布者描述收到货或预计日期到期时可发满意度问卷，收货前评价可能反映失约等待。review_creation_date主要是日期精度，回复时间作为作答代理；没有明确时区。T取承诺日次日零点，只用T之前的有效交接和下单信息；最终送达、最终状态、未来评分不排序。候选资格可通过事件是否已发生重构，但缺入库/取消日志，不能证明真实线上可得。

**可展示证据：** [时序精度](../review_timing_study/timestamp_precision.csv)、[冻结特征与规则](../decision_study/frozen_rules.json)、[信息泄漏审计](../decision_study/audit_checks.json)。

## 4. 覆盖率提高2.91个百分点，为什么不直接推荐最复杂规则？

**回答要点：** 规则家族由2017年内部验证选定，训练30天观察窗完整早于2018测试；每日向下取整容量一致，用配对周Bootstrap。20%时，复杂规则712/3,157，等待基准620/3,157，简单阶段规则已达704/3,157。地区只再多8事件，增量区间跨0，不能把主要提升全归给地区；名义20%实际19.01%，不存在已知企业客服容量。先核实活跃状态和阶段分流，复杂度需额外验证。

**可展示证据：** [回测明细](../decision_study/priority_backtest.csv)、[复杂度审计](../decision_study/complexity_increment.csv)。

## 5. 无评价如何解释？建议如何验证真实价值？

**回答要点：** 无评价不代表满意，承诺节点未见送达组69.26%是5,501/7,943评价者；全候选事件比例是5,501/8,248=66.69%。最佳规则选中895单中227单最终取消或缺货，取消时间未知，高风险可能不可挽回。先用日志核对真实活跃队列，再随机分配常规服务与主动核查/沟通；事前固定30天首次差评事件、评价覆盖、投诉、解决率、每单成本，必要时按物流团队分组随机。不得通过降低问卷触达改善表面差评率。

**可展示证据：** [节点汇总](../review_timing_study/landmark_future_first_review_30d.csv)、[事后状态审计](../decision_study/allocation_crosscheck_and_outcome_context.csv)。实验未执行，样本量和收益需在实际业务基线下另行确定。
''')
    write('portfolio_delivery/VISUAL_GUIDE.md','''# 可视化导读：复用已有验证图表

本轮不重算研究、不重绘图表。首页精选评价时状态和优先级增量两图；这里提供完整解释。图表、聚合输出和源代码均保留原路径。

## 1. 延迟程度与差评风险是否线性？

![最终送达日期偏差与差评率](../deep_study/delay_gradient.png)

**回答：** 晚1天19.63%，晚2–3天42.05%，晚4–7天67.68%；这是最终已送达有评价订单的描述性分组，不是截至当天的预警风险。较长延迟组末端的差异不能解释为等待过久反而改善。

**追溯：** [分组数据](../deep_study/delay_gradient.csv)、[源代码](../deep_audit.py)、[完整模型与限制](../deep_study/deep_report.md)。

## 2. 评价时尚未送达，是否是独立业务群体？

![评价发生时履约状态](../review_timing_study/review_time_states.png)

**回答：** 承诺已过未见送达组5,749/7,097=81.01%，已送达但超期组371/1,908=19.44%。全图每单取最后回复，共98,673笔有评价订单，不能与“有效已送达”分母混算。误差条为Wilson区间；未见送达不是已证明在途。

**追溯：** [四状态汇总](../review_timing_study/review_time_states_latest.csv)、[源代码](../review_timing_study.py)。

## 3. 相同模拟资源，哪些规则覆盖更多事件？

![容量与事件覆盖曲线](../decision_study/risk_coverage.png)

**回答：** 2018年1—6月4,709笔测试候选，3,157个30天首次差评事件。横轴是按日向下取整后的实际选择比例，非名义比例。20%名义预算实际处理895单，冻结规则覆盖712个事件；没有客服干预或可避免事件的测量。

**追溯：** [回测明细](../decision_study/priority_backtest.csv)、[按日队列](../decision_study/daily_queue_and_capacity.csv)、[源代码](../decision_study/priority_study.py)。

## 4. 增量有多确定？

![20%按日预算的覆盖增量](../decision_study/paired_increment.png)

**回答：** 冻结规则相对购买等待基准+2.91个百分点，95%配对周Bootstrap区间[2.00,3.82]。图中比较对象均为购买等待基准；不能凭两条区间重叠判断候选间差异。地区细化相对简单阶段规则的直接配对差异仅+0.25个百分点，区间[-0.24,0.70]。

**追溯：** [主回测区间](../decision_study/priority_backtest.csv)、[规则间直接比较](../decision_study/complexity_increment.csv)。区间不覆盖取消日志缺失、评价选择和因果不确定性。

图表属于基于Olist公开数据的派生分析，来源和授权条件见[数据许可](DATA_LICENSE.md)。本轮已目视检查以上四图的标签、坐标、中文和区间，不把“图已存在”当作统计复现。
''')
    write('portfolio_delivery/DATA_LICENSE.md','''# 数据来源、署名与公开范围

核查日期：2026-10-17。使用发布者与许可机构的一手来源，不以其他GitHub仓库的许可代替。

## 数据来源与许可

数据：**Brazilian E-Commerce Public Dataset by Olist**；提供者：**Olist及数据页面列示的合作者**。发布者页面标示 **CC BY-NC-SA 4.0**，说明数据经过匿名化，包含2016–2018年约十万笔公开订单。[Olist原始数据页面](https://www.kaggle.com/olistbr/brazilian-ecommerce)

该许可要求适当署名、提供许可链接、说明修改；限制商业使用，共享改编材料时要求相同方式共享。具体范围、定义及例外以[Creative Commons许可概要](https://creativecommons.org/licenses/by-nc-sa/4.0/)和[正式条文](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode.en)为准。公开可下载不等于可无条件商用。

## 本项目如何处理

- 用途：独立学习、非商业数据分析作品展示；不宣称Olist认可或参与，不展示虚构雇佣/干预效果。
- 原始九张CSV不进入公开版本，读者自行从发布者获取；未经改写的原始文件SHA256见保护/复现记录。
- 已做修改：清洗规则、订单聚合、派生变量、统计结果、图表和中文解释；不覆盖原始CSV。
- 基于数据的改编材料按上游CC BY-NC-SA 4.0条件处理，并保留本页数据署名与链接。不用单一MIT标签覆盖数据授权。
- 只公开聚合结果；排除订单/客户/评价逐条清单与评论文本。历史匿名卖家级聚合排名仍保留，以便审计，不等同于真实商家身份或责任认定。

可复用的数据署名：

> 数据来源：Olist，Brazilian E-Commerce Public Dataset by Olist（Kaggle），CC BY-NC-SA 4.0。本项目进行了订单聚合、统计分析和可视化；原始数据未随仓库分发。

## 原创代码许可尚待作者决定

本轮未擅自为原创Python/SQL代码选择MIT、Apache等软件许可，未添加虚构作者或权利人。源代码在拟公开范围内，当前没有授予独立的软件开源许可；公开可阅读与授予复用许可不是同一件事。作者发布前可明确代码许可范围，同时保留上游数据及派生材料的限制。依赖库遵从各自许可，本项目不分发audit_deps或虚拟环境。

网页许可核查成功不等于对所有潜在用途完成法律判断。若未来改为商业用途或再次分发数据，应对照当时源页面与条文重新核对。
''')
    replay_path=OUT/'reproducibility.json'
    if replay_path.exists():
        replay=json.loads(replay_path.read_text(encoding='utf-8'))
        records='\n'.join(f"| {r['step']} | {r['exit_code']} | {r['seconds']} | {'有，见本地日志' if r['stderr_nonempty'] else '无'} |" for r in replay['commands'])
        if replay['status']=='passed':
            result=f"实际比较{len(replay['compared_json'])}组JSON参考和{len(replay['compared_csv'])}份聚合CSV，重新生成{len(replay['regenerated_figures'])}张PNG；九张原始CSV与{replay['historical_analysis_files_unchanged']}个既有分析文件哈希未变，冻结规则JSON哈希相同。计数、文本和布尔要求完全一致；浮点rtol=1e-4、atol=1e-6。"
        else:result='尚未通过，不能把当前状态称为复现成功。失败/运行详情以机器记录为准。'
        write('portfolio_delivery/REPRODUCIBILITY.md',f'''# 本轮独立环境复现记录

状态：**{replay['status']}**。实际执行入口：

```powershell
python -X utf8 portfolio_delivery/reproduce_portfolio.py
```

工作副本：`{replay['run_directory']}/work`。新建虚拟环境，不继承system-site-packages，不复制audit_deps，禁用用户site和PYTHONPATH；实际探针确认numpy、pandas、statsmodels从新虚拟环境导入。数据和原脚本复制后核对哈希，脚本输出只写入副本。

## 实际执行

| 步骤 | 退出码 | 秒 | stderr |
|---|---:|---:|---|
{records}

完整命令参数、退出码、环境探针、对比清单及日志位置在[reproducibility.json](reproducibility.json)。本机stdout/stderr保留在忽略的运行目录；依赖安装读取requirements-repro.txt并用历史environment.freeze.txt约束传递版本，实际安装版本另存[本轮环境清单](environment.freeze.txt)。没有回写历史环境记录。

## 比较范围

{result}

九表审查使用公开的final_delivery/audit_reference.json核对，剔除原审查里的逐单示例后比较，因此不依赖私有audit_results.json参考。三阶段指标与处置阶段全部科学结果比较；聚合CSV逐表比较，包括队列、容量、敏感性、SQL核验和不确定性结果。按日策略选择的哈希也在比较范围。

不要求跨数值环境逐位相同的内容：优化迭代次数、极小梯度、条件数；处置指标的运行耗时、环境路径和副本保护文件数。原始历史诊断仍保留，收敛标记与科学统计结果需要匹配。逐单异常清单不是公开参考，不参与CSV逐表比较；重跑仍可能生成本地逐单产物。

## 验证边界

这是全新Windows/Python 3.12.6环境中的本地原代码＋独立数据输入模拟，不是远程Git克隆或已发布仓库验收。没有执行Linux/macOS、其他Python版本、源系统日志核对、真实客服干预或实验。

旧手写报告没有自动重写；本轮通过原统计输出及证据索引核对其采用口径。PNG只验证重建、非空，不要求二进制相同；另已目视检查精选图。代码复现不会解决评价选择、取消/入库时间缺失等研究局限。

本页是本次整理时的运行快照。未来重跑会再次创建新的忽略副本，更新reproducibility.json并保留旧本地日志；应以机器记录的新状态为准，本页不会由复现入口自动刷新。不覆盖final_delivery或decision_study历史成果。网络依赖安装失败、数据版本/哈希变化时应如实保留失败记录，不可跳过比较称为成功。
''')
    print(json.dumps({'evidence_entries':len(evidence),'documents_generated':7,'new_research':False},ensure_ascii=False))

if __name__=='__main__':main()
