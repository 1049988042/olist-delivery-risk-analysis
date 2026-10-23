# Olist 电商履约时效与用户差评风险分析

> **求职作品集速读（约 1 分钟）**
>
> **业务问题**：配送延迟与差评的关联有多强？在客服资源有限时，应该优先核查哪些订单？
>
> **关键证据**：96,470 笔具有实际送达日期的已送达订单中，6,534 笔超过承诺日（6.77%）；延迟组差评率 62.42%，非延迟组 9.27%。针对承诺节点的历史优先级回测，在每日模拟 20% 容量下，简单规则覆盖 704 个后续首次差评事件，相对购买等待基准增加 84 个；进一步加入有样本支持的地区规则覆盖 712 个事件，但增量稳定性不足。
>
> **方法**：九表预聚合与 SQL 核查、Python 数据质量审计、评价时序、Logistic 回归、时间留出回测。
>
> **边界**：差评关联并非配送延迟的因果效应；历史事件覆盖提升不等于真实减少差评或已实施客服干预。
>
> **快速阅读**：[完整报告](final_delivery/FINAL_REPORT.md) · [回测与口径](decision_study/DECISION_REPORT.md) · [证据索引](portfolio_delivery/EVIDENCE_INDEX.md)。


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
