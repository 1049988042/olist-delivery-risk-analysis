# 推荐交付结构与公开边界

当前结构已经兼顾可追溯与可复现，不移动历史脚本，避免破坏其基于`__file__`的相对数据路径。推荐保留：

```text
Olist/
├─ README.md                         # 招聘方项目首页
├─ .gitignore
├─ requirements.txt                  # 历史兼容范围，保留
├─ requirements-repro.txt            # 本轮固定直接依赖
├─ audit_olist.py                    # 九表审查
├─ run_project.py                    # 基础SQL/分析/历史模型
├─ deep_audit.py                     # 独立统计审计/历史深度分析
├─ review_timing_study.py             # 评价时序与承诺节点研究
├─ build_review_timing_report.py
├─ data_quality_review.md
├─ project/                          # 基础历史报告/SQL/汇总/图
├─ deep_study/                       # 深度历史报告/SQL/汇总/图
├─ review_timing_study/              # 时序报告/SQL/汇总/图
└─ final_delivery/
   ├─ FINAL_REPORT.md                # 统一最终报告，建议优先阅读
   ├─ EVIDENCE_INDEX.md              # 指标→口径→代码→输出
   ├─ evidence_index.csv
   ├─ evidence_snapshot.json         # 仅汇总数值，便于公开核对
   ├─ audit_reference.json           # 去掉逐单示例的审查参考
   ├─ STAGE_RECONCILIATION.md         # 三阶段样本及历史限定
   ├─ REPRODUCIBILITY.md             # 实际运行及未验证事项
   ├─ reproducibility.json
   ├─ environment.freeze.txt
   ├─ historical_manifest.json
   ├─ publication_audit.json
   ├─ publication_manifest.csv       # 仅建议纳入范围，不是Git已暂存
   ├─ DELIVERY_CHECKLIST.md
   ├─ INTERVIEW.md
   ├─ PROJECT_STRUCTURE.md
   ├─ prepare_workspace.py
   ├─ reproduce.py
   ├─ build_delivery.py
   ├─ verify_delivery.py
   ├─ test_public_snapshot.py        # 仅拟公开文件加本地原始数据的重跑
   ├─ public_snapshot_test.json
   └─ history/README_before_delivery.md
```

仅本地保留并忽略：根目录九张原始CSV、audit_results.json中的异常示例、逐单审计与异常证据、audit_deps、__pycache__、.repro_runs及其虚拟环境和数据副本。聚合CSV/JSON、图表、SQL和代码可保留在建议公开范围；不要用`*.csv`一刀切忽略全部统计结果。

完整原始数据从发布者页面自行取得并置于项目根目录；公开作品不复制原始CSV。数据授权与代码授权应分别处理；本次没有擅自为用户代码选择许可证，也没有公开发布。

公开副本没有audit_results.json或逐单异常CSV时，复现程序使用audit_reference.json作为去示例参考，统计汇总仍从原始数据重新运行；运行期输入哈希单独保存在忽略的复现目录，避免把本机私有文件清单当成下载者必须已有的文件。
