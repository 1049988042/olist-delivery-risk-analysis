# 本轮独立环境复现记录

状态：**passed**。实际执行入口：

```powershell
python -X utf8 portfolio_delivery/reproduce_portfolio.py
```

工作副本：`.repro_runs/portfolio_20261017_185853/work`。新建虚拟环境，不继承system-site-packages，不复制audit_deps，禁用用户site和PYTHONPATH；实际探针确认numpy、pandas、statsmodels从新虚拟环境导入。数据和原脚本复制后核对哈希，脚本输出只写入副本。

## 实际执行

| 步骤 | 退出码 | 秒 | stderr |
|---|---:|---:|---|
| pinned_install | 0 | 139.276 | 无 |
| pip_check | 0 | 0.781 | 无 |
| environment_probe | 0 | 3.231 | 无 |
| pip_freeze | 0 | 0.646 | 无 |
| data_audit | 0 | 11.348 | 无 |
| baseline | 0 | 163.724 | 无 |
| statistical_audit | 0 | 39.746 | 无 |
| review_timing | 0 | 19.907 | 无 |
| priority_backtest | 0 | 56.524 | 无 |
| aggregate_csv_comparison | 0 | 0.697 | 无 |

完整命令参数、退出码、环境探针、对比清单及日志位置在[reproducibility.json](reproducibility.json)。本机stdout/stderr保留在忽略的运行目录；依赖安装读取requirements-repro.txt并用历史environment.freeze.txt约束传递版本，实际安装版本另存[本轮环境清单](environment.freeze.txt)。没有回写历史环境记录。

## 比较范围

实际比较5组JSON参考和42份聚合CSV，重新生成7张PNG；九张原始CSV与101个既有分析文件哈希未变，冻结规则JSON哈希相同。计数、文本和布尔要求完全一致；浮点rtol=1e-4、atol=1e-6。

九表审查使用公开的final_delivery/audit_reference.json核对，剔除原审查里的逐单示例后比较，因此不依赖私有audit_results.json参考。三阶段指标与处置阶段全部科学结果比较；聚合CSV逐表比较，包括队列、容量、敏感性、SQL核验和不确定性结果。按日策略选择的哈希也在比较范围。

不要求跨数值环境逐位相同的内容：优化迭代次数、极小梯度、条件数；处置指标的运行耗时、环境路径和副本保护文件数。原始历史诊断仍保留，收敛标记与科学统计结果需要匹配。逐单异常清单不是公开参考，不参与CSV逐表比较；重跑仍可能生成本地逐单产物。

## 验证边界

这是全新Windows/Python 3.12.6环境中的本地原代码＋独立数据输入模拟，不是远程Git克隆或已发布仓库验收。没有执行Linux/macOS、其他Python版本、源系统日志核对、真实客服干预或实验。

旧手写报告没有自动重写；本轮通过原统计输出及证据索引核对其采用口径。PNG只验证重建、非空，不要求二进制相同；另已目视检查精选图。代码复现不会解决评价选择、取消/入库时间缺失等研究局限。

本页是本次整理时的运行快照。未来重跑会再次创建新的忽略副本，更新reproducibility.json并保留旧本地日志；应以机器记录的新状态为准，本页不会由复现入口自动刷新。不覆盖final_delivery或decision_study历史成果。网络依赖安装失败、数据版本/哈希变化时应如实保留失败记录，不可跳过比较称为成功。
