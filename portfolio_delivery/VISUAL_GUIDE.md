# 可视化导读：复用已有验证图表

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
