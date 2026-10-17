# 评价时点与配送承诺关系：增量研究

在项目根目录运行：

```powershell
python -X utf8 review_timing_study.py
```

依赖沿用现有 pandas、numpy、matplotlib 和 Python 自带 sqlite3，无需额外模型或 API。脚本会调用 `build_review_timing_report.py`，从真实结果生成报告。运行只更新本轮 `review_timing_study/` 产物，校验原始九表、旧报告、旧结果和旧代码的哈希保持不变。

- `review_timing_report.md`：中文报告，包含口径、四组结果、时间窗口、前瞻解释审计和经营含义。
- `timing_metrics.json`：汇总指标与来源说明。
- `timestamp_precision.csv`、`nonmidnight_creation_dates.csv`：原始时间精度与非午夜值。
- `review_time_states_latest.csv`、`review_time_states_first.csv`、`review_time_states_original_sample.csv`：最后/首次评价及原样本四状态。
- `delivery_timing_sensitivity.csv`、`promise_boundary_sensitivity.csv`：送达顺序与承诺边界容忍窗口。
- `sequence_flag_evidence.csv`、`sequence_flag_sensitivity.csv`：明显顺序异常及仅对其排除的敏感性结果。
- `final_delivery_presence_groups.csv`、`missing_delivery_and_final_status.csv`：缺送达时间分层与最终状态背景。
- `original_final_delay_vs_review_state.csv`：旧模型最终延迟与本轮评价状态交叉表。
- `landmark_future_first_review_30d.csv`、`landmark_monthly.csv`、`landmark_final_status_context.csv`：承诺日次日零时、此前无评价人群的后续30天首次评价研究。
- 两份 `.sql` 与 `sql_*crosscheck.csv`：独立 SQL 复核主表及后续研究。
- `order_timing_audit.csv.gz`：每单可追溯的评价与订单时间、状态代理和异常标记。
- `validation.json`：输入和旧产物 SHA-256、环境版本及验证结果。

四状态中的“已送达”指记录的送达事件时间不晚于作答时间；“未见送达”包括未来才有送达时间和始终缺送达时间，不能证明平台当时是否收到数据或客户是否实际签收。预计送达日当日算未过期。后续研究未用最终配送状态筛选资格；其候选累计数不能当作某日实际在途积压。
