# Olist 电商履约时效与用户差评风险分析

## 复现

在本目录保留九个原始 CSV，安装 `requirements.txt` 后运行：

```powershell
python audit_olist.py > audit_results.json
python run_project.py > project/run_log.json
```

报告见 `project/report.md`；订单级 SQL 见 `project/analysis.sql`；计算结果见 `project/metrics.json` 和各分组 CSV；图表在 `project/figures`。脚本读取源 CSV，不改写原件。首次运行会新建 `project` 目录。SQLite 使用内存数据库，分析 SQL 对商品、支付、评价分别先汇总再与订单连接。审查脚本处理九表结构与关系；主脚本执行指标、检验、Logistic 回归和作图。

技术环境：Python 3.11+；pandas、numpy、scipy、scikit-learn、matplotlib。回归由 SciPy 优化，标准误来自观察信息矩阵。运行时间取决于本机，约需数十秒。

## 口径摘要

订单级唯一键 `order_id`；仅 `delivered` 且实际送达时间非空用于延迟分析。预计送达时间按日期精度解释：实际送达日期晚于预计日期才计延迟。评价按每单 `review_answer_timestamp` 最晚的一条，时间相同时按 `review_id` 排序；1–2 星为差评。无评价订单保留在履约指标，排除于评分分析。多品类/多卖家订单不用于单品类/单卖家归因。

这些是分析口径，并非原始数据事实或因果假设。评分最小值、最大值、排除冲突评价及 1–3 星定义均有敏感性结果。报告说明适用边界。

## 增量统计审计与深度研究

保留原版报告和指标后，运行 `python deep_audit.py` 生成 `deep_study` 目录。新增 [深度报告](deep_study/deep_report.md)、[指标](deep_study/deep_metrics.json)、[SQL](deep_study/deep_analysis.sql)、分组 CSV 和图表。`deep_audit.py` 使用 statsmodels 独立复核原 Logistic 模型，并计算用户聚类标准误、送达日期梯度、评价时间顺序、交接与运输阶段及时间切分指标。全部产物可从原始 CSV 重新生成。

当前环境的 statsmodels 和 patsy 安装于 `audit_deps`；脚本先从该目录导入。如果新环境没有此目录，可按 `requirements.txt` 安装全部依赖。无需修改原始 CSV。
