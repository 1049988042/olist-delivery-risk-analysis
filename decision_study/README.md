# 异常履约订单处置优先级：独立增强研究

运行（从项目根目录）：

```powershell
python -X utf8 decision_study/priority_study.py
```

使用已有Python、pandas、numpy、matplotlib和sqlite3，不需要额外服务、statsmodels、付费API或新模型。所有新增文件均在本目录；不改写已有项目。读取上级目录原始订单、评价、客户、商品明细CSV，其他历史文件只做哈希保护。

先读 [DECISION_REPORT.md](DECISION_REPORT.md)。`design.json`是回测前规定的时间区间、规则家族、容量、阈值、随机种子、敏感性与推荐门槛；`frozen_rules.json`在测试评估前写入。重跑会覆盖本目录的本轮派生产物，不触碰历史阶段。

## 文件

- priority_metrics.json：汇总指标、时间泄漏检查、规则与结论。
- priority_backtest.csv：主测试全部策略×10/20/30%按日容量。
- development_validation.csv：内部验证和规则家族选择。
- daily_queue_and_capacity.csv：逐日汇总候选、预算和覆盖，无订单明细。
- cohort_stage_profile.csv、feature_availability.csv：样本、阶段与缺失。
- training_group_support.csv：训练分组样本支持；无测试标签用于定分组。
- test_subperiods.csv、threshold_sensitivity.csv：预定时段和阈值敏感性。
- separate_landmark_sensitivity.csv：D+3和D+7独立截面，不与主队列混算。
- final_status_outcome_audit_not_features.csv：事后状态构成，禁止回填到排序。
- candidate_validation.sql、sql_crosscheck.csv：独立SQL核验。
- allocation_validation.sql、allocation_crosscheck_and_outcome_context.csv：独立SQL特征/分数/每日名额复核及事后构成。
- complexity_increment.csv：地理细化相对简单阶段规则的附加覆盖，不用于事后重选。
- freeze_guard.json：在首次测试后扩充审计前记录的规则/设计哈希，防止借审计调参。
- input_hashes.json、audit_checks.json：输入和历史保护、信息泄漏审计。
- risk_coverage.png、paired_increment.png：风险覆盖与配对不确定性。

## 字段时点与规则

T=预计送达日次日零时；只收已下单、未见不晚于T的送达、首次评价严格晚于T或尚无评价的订单。首次1–2星评分在(T,T+30天]内才算主事件；无评价不是满意。

理论在T可知：购买时间、承诺日期、订单商品/金额/客户州快照、交接事件是否已发生及等待时长。快照可用性与数据入库均未得到验证。未来交接被隐藏，负交接时长作为未知阶段；最终送达、最终状态、未来评分仅用于资格事件时间重构/后续结果，不能用于优先级。

基准为同日随机与购买等待时长。候选最多三类：未确认交接优先后按阶段等待；训练期阶段×长短等待四组事件率；有足够训练样本才细化客户州的四组事件率。后两类是小型历史分组表，使用固定收缩，不训练机器学习估计器。阈值、支持条件及选择均来自2017年，测试为2018年1—6月。

每天floor(候选量×模拟比例)个名额，所有策略相同；不做滚动积压与跨日处理。随机期望可能有小数覆盖事件，不能读作实际小数个客户。2,000次日历周配对Bootstrap评估策略差异，另用超几何模拟随机选择。主推荐家族由2017年内部验证冻结，不按测试集最高值改选。

取消事件、实际入库时间、时区、服务成本和可挽回性缺失；候选可能含已取消或缺货单。这是历史事件时间模拟，不证明实时可用、因果效果或处置收益。D+3/D+7同单重叠明确保留，禁止相加。
