# 项目阅读路线与保留结构

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
