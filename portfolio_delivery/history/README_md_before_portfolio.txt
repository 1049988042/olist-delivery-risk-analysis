# Olist 电商履约时效与用户差评风险分析

**面向数据分析 / 经营分析校招的完整作品：从订单粒度和统计关联，追问到评价发生时是否已经失约。**

平台应优先关注哪些履约风险、何时识别、现有数据能支持多强的建议？本项目通过九表审查、SQL订单汇总、统计复核和评价时序研究回答这些问题。

**先看：[完整中文报告](final_delivery/FINAL_REPORT.md) · [指标证据索引](final_delivery/EVIDENCE_INDEX.md) · [实际复现记录](final_delivery/REPRODUCIBILITY.md) · [面试问题](final_delivery/INTERVIEW.md)**

## 核心发现

| 发现 | 统计证据 | 经营含义与边界 |
|---|---|---|
| 有效送达订单延迟率6.77% | 6,534/96,470；原始订单99,441 | 按承诺日的日终判断，避免午夜误判 |
| 最终延迟与低评分强关联 | 延迟有评价订单62.42%（3,983/6,381），未延迟9.27%（8,289/89,443） | 回顾性关联，不能换算成干预收益 |
| 评价时的等待状态值得单独监控 | “承诺已过、未见送达”差评率81.01%；“已送达但超期”19.44% | 记录事件时间代理，可能混有取消、缺货或时间缺失 |
| 承诺边界存在后续差评集中现象 | 13,126笔当时未首次评价的候选；后续30天评价者差评率69.26%（5,501/7,943）与13.09%（537/4,101） | 候选分别8,248和4,878；评价覆盖96.30%与84.07%，未评价不是好评 |

![评价时履约状态与差评率](review_timing_study/review_time_states.png)

![最终延迟程度与差评率](deep_study/delay_gradient.png)

两图分别回答评价时状态和最终延迟程度的问题，均不能识别因果效果。

## 方法与质量控制

- **可信数据**：审查粒度、键和关联；商品、支付、评价先汇总再JOIN，检查order_id唯一及分子分母守恒。
- **统计证据**：Wilson区间、Fisher检验、Logistic回归、statsmodels独立复现、用户聚类SE、评分和时间窗口敏感性。
- **业务深度**：修正COUNT(DISTINCT)忽略NULL的单品类误判，拆分交接与运输，研究地区/品类/线路规模和承诺节点后续评价。
- **主动审计**：保留历史代码和报告，限定AUC及最终延迟变量的解释；不把收货前评价简单删除。

技术：Python 3.12、Pandas、NumPy、SQLite、SciPy、statsmodels、scikit-learn、Matplotlib。SQL用于实质性订单预汇总及独立交叉核验。

## 复现

从[Olist发布者页面](https://www.kaggle.com/olistbr/brazilian-ecommerce/home/)取得九张CSV并遵守数据授权条件，保持原文件名放在项目根目录。原始CSV不纳入公开版本。

推荐在Windows/Python 3.12中通过隔离副本运行，避免覆盖历史baseline：

```powershell
python final_delivery/prepare_workspace.py
python final_delivery/reproduce.py
python final_delivery/build_delivery.py
python final_delivery/verify_delivery.py
```

准备脚本复制数据及五个原脚本，创建不继承系统包的虚拟环境；复现脚本安装固定依赖、实际运行三个阶段并比较输出。环境和副本保存在忽略的`.repro_runs/`。交付构建脚本仅从既有统计输出生成报告与证据索引，验证脚本核查链接、哈希及发布准备。

直接依赖固定在[requirements-repro.txt](requirements-repro.txt)，完整版本在[environment.freeze.txt](final_delivery/environment.freeze.txt)。历史[requirements.txt](requirements.txt)保留，但宽范围依赖不能替代固定环境。[复现记录](final_delivery/REPRODUCIBILITY.md)说明实际命令、退出码、结果和未验证事项。

公开副本不需要本机的audit_deps或逐单异常文件；审查参考使用去除示例的[汇总参考](final_delivery/audit_reference.json)，原始审查结果从CSV重新生成。

## 口径与局限

基础评分分析为95,824笔有评价有效送达订单；时序主表为98,673笔全部有评价订单；13,126笔节点候选不是某天积压存量。基础取每单最后回复，节点研究用首次评价并排除节点前已评价者。

时间戳没有明确时区和入库时间，取消历史和抽取时间缺失；问卷触发、评价选择及未观测混杂限制解释。项目提出风险排查和实验方案，**没有上线监控、执行A/B实验、证明因果效果、降低差评或测得收益**。

## 详细材料

- [统一报告](final_delivery/FINAL_REPORT.md)、[证据索引](final_delivery/EVIDENCE_INDEX.md)、[三阶段衔接与历史限定](final_delivery/STAGE_RECONCILIATION.md)。
- [基础历史报告](project/report.md)、[深度审计](deep_study/deep_report.md)、[评价时序](review_timing_study/review_timing_report.md)：保留演进过程，解释以统一稿为准。
- [推荐目录](final_delivery/PROJECT_STRUCTURE.md)、[交付清单](final_delivery/DELIVERY_CHECKLIST.md)、[发布准备检查](final_delivery/publication_audit.json)。

公开范围与准备检查见[交付清单](final_delivery/DELIVERY_CHECKLIST.md)。旧README保存在[历史副本](final_delivery/history/README_before_delivery.md)。
