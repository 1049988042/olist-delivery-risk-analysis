# 关键指标证据索引

所有数值取自既有统计输出；源代码链接标记实际行号。分母必须与人群、观察时点一起阅读。`audit_results.json`及逐单异常清单仅本地保留，公开查看汇总快照 `evidence_snapshot.json`。

| 指标 | 数值 | 分母/口径 | 源代码 | 输出与选择器 |
|---|---:|---|---|---|
| 原始订单 | 99441 | COUNT(orders.order_id)，order_id唯一；分母 99441 | [run_project.py:L38](../run_project.py#L38) | [project/metrics.json](../project/metrics.json)：`order_rows` |
| 快照delivered订单 | 96478 | order_status=delivered的订单数；分母 99441 | [run_project.py:L97](../run_project.py#L97) | [project/metrics.json](../project/metrics.json)：`delivered` |
| 用于日期配送分析的有效送达 | 96470 | delivered且实际送达时间非空：96478-8；分母 96478 | [run_project.py:L43](../run_project.py#L43) | [project/metrics.json](../project/metrics.json)：`delivered_valid` |
| 有评价的有效送达 | 95824 | 96470-646无评价订单；分母 96470 | [run_project.py:L50](../run_project.py#L50) | [project/metrics.json](../project/metrics.json)：`reviewed_delivered` |
| 超承诺日期送达订单 | 6534 | 实际送达日>承诺日；分母 96470 | [run_project.py:L45](../run_project.py#L45) | [project/metrics.json](../project/metrics.json)：`late_count_all_valid` |
| 有效送达订单延迟率 | 6.77% | 6534/96470；分母 96470 | [run_project.py:L45](../run_project.py#L45) | [project/metrics.json](../project/metrics.json)：`late_rate_all_valid` |
| 延迟有评价订单差评率 | 62.42% | 3983/6381；分母 6381 | [run_project.py:L62](../run_project.py#L62) | [project/late_groups.csv](../project/late_groups.csv)：`late=true;bad_n/n` |
| 未延迟有评价订单差评率 | 9.27% | 8289/89443；分母 89443 | [run_project.py:L62](../run_project.py#L62) | [project/late_groups.csv](../project/late_groups.csv)：`late=false;bad_n/n` |
| 未调整差评风险比 | 6.735437019537263 | (3983/6381)/(8289/89443)；分母 95824 | [run_project.py:L95](../run_project.py#L95) | [project/metrics.json](../project/metrics.json)：`late_bad12_risk_ratio` |
| 主回归样本 | 95822 | 95824-2个稀疏月份订单；分母 95824 | [deep_audit.py:L68](../deep_audit.py#L68) | [deep_study/deep_metrics.json](../deep_study/deep_metrics.json)：`model_audit.n` |
| statsmodels调整延迟OR | 16.29951418292044 | exp(beta_late)；分母 95822 | [deep_audit.py:L78](../deep_audit.py#L78) | [deep_study/deep_metrics.json](../deep_study/deep_metrics.json)：`model_audit.main` |
| 用户聚类稳健SE | 0.03030672110048707 | 按customer_unique_id聚类的SE；分母 92746 | [deep_audit.py:L79](../deep_audit.py#L79) | [deep_study/deep_metrics.json](../deep_study/deep_metrics.json)：`model_audit.cluster_customer.se` |
| 旧单品类误判影响订单 | 55 | 非空类目数=1且存在NULL商品类目的有评价订单；分母 93781 | [deep_audit.py:L41](../deep_audit.py#L41) | [deep_study/deep_metrics.json](../deep_study/deep_metrics.json)：`category_null.mixed_null_reviewed` |
| 阶段耗时有效订单 | 96281 | 排除165负交接、23负运输、1缺交接，共189；分母 96470 | [deep_audit.py:L118](../deep_audit.py#L118) | [deep_study/deep_metrics.json](../deep_study/deep_metrics.json)：`timing.valid_stage_n` |
| 全体有评价订单 | 98673 | 每单最后一次评价；包括最终未送达/取消；分母 99441 | [review_timing_study.py:L97](../review_timing_study.py#L97) | [review_timing_study/timing_metrics.json](../review_timing_study/timing_metrics.json)：`selected_latest_orders` |
| 评价时已送达，超过承诺日期差评率 | 19.44% | 371/1908；分母 1908 | [review_timing_study.py:L101](../review_timing_study.py#L101) | [review_timing_study/review_time_states_latest.csv](../review_timing_study/review_time_states_latest.csv)：`state=delivered_late` |
| 评价时已送达，按承诺日期准时差评率 | 9.26% | 8262/89268；分母 89268 | [review_timing_study.py:L101](../review_timing_study.py#L101) | [review_timing_study/review_time_states_latest.csv](../review_timing_study/review_time_states_latest.csv)：`state=delivered_on_time` |
| 评价时未见送达，承诺日期已过差评率 | 81.01% | 5749/7097；分母 7097 | [review_timing_study.py:L101](../review_timing_study.py#L101) | [review_timing_study/review_time_states_latest.csv](../review_timing_study/review_time_states_latest.csv)：`state=pending_overdue` |
| 评价时未见送达，承诺日期未过差评率 | 28.00% | 112/400；分母 400 | [review_timing_study.py:L101](../review_timing_study.py#L101) | [review_timing_study/review_time_states_latest.csv](../review_timing_study/review_time_states_latest.csv)：`state=pending_within_promise` |
| 明显评价时间矛盾订单 | 61 | 下单前回复或创建日早于下单日等标记取并集；分母 98673 | [review_timing_study.py:L94](../review_timing_study.py#L94) | [review_timing_study/timing_metrics.json](../review_timing_study/timing_metrics.json)：`sequence_flags.strong_sequence_flag` |
| 评价和送达同日订单 | 1373 | 评价回复日=送达日；分母 98673 | [review_timing_study.py:L187](../review_timing_study.py#L187) | [review_timing_study/timing_metrics.json](../review_timing_study/timing_metrics.json)：`same_calendar_day_answer_delivery` |
| 承诺节点候选订单 | 13126 | 8248未见送达+4878已送达；分母 13126 | [review_timing_study.py:L193](../review_timing_study.py#L193) | [review_timing_study/timing_metrics.json](../review_timing_study/timing_metrics.json)：`landmark_cohort.eligible_orders` |
| 节点未见送达候选数 | 8248 | 按记录送达时间是否晚于承诺次日零时分组；分母 13126 | [review_timing_study.py:L199](../review_timing_study.py#L199) | [review_timing_study/landmark_future_first_review_30d.csv](../review_timing_study/landmark_future_first_review_30d.csv)：`pending_at_landmark=true;eligible_orders` |
| 节点未见送达后续30天评价覆盖率 | 96.30% | 7943/8248；分母 8248 | [review_timing_study.py:L200](../review_timing_study.py#L200) | [review_timing_study/landmark_future_first_review_30d.csv](../review_timing_study/landmark_future_first_review_30d.csv)：`pending_at_landmark=true;reviews_in_30d/eligible_orders` |
| 节点未见送达后续30天评价者差评率 | 69.26% | 5501/7943；分母 7943 | [review_timing_study.py:L201](../review_timing_study.py#L201) | [review_timing_study/landmark_future_first_review_30d.csv](../review_timing_study/landmark_future_first_review_30d.csv)：`pending_at_landmark=true;bad_in_30d/reviews_in_30d` |
| 节点未见送达观察到首次差评事件比例 | 66.69% | 5501/8248；分母 8248 | [review_timing_study.py:L205](../review_timing_study.py#L205) | [review_timing_study/landmark_future_first_review_30d.csv](../review_timing_study/landmark_future_first_review_30d.csv)：`pending_at_landmark=true;bad_in_30d/eligible_orders` |
| 节点已送达候选数 | 4878 | 按记录送达时间是否晚于承诺次日零时分组；分母 13126 | [review_timing_study.py:L199](../review_timing_study.py#L199) | [review_timing_study/landmark_future_first_review_30d.csv](../review_timing_study/landmark_future_first_review_30d.csv)：`pending_at_landmark=false;eligible_orders` |
| 节点已送达后续30天评价覆盖率 | 84.07% | 4101/4878；分母 4878 | [review_timing_study.py:L200](../review_timing_study.py#L200) | [review_timing_study/landmark_future_first_review_30d.csv](../review_timing_study/landmark_future_first_review_30d.csv)：`pending_at_landmark=false;reviews_in_30d/eligible_orders` |
| 节点已送达后续30天评价者差评率 | 13.09% | 537/4101；分母 4101 | [review_timing_study.py:L201](../review_timing_study.py#L201) | [review_timing_study/landmark_future_first_review_30d.csv](../review_timing_study/landmark_future_first_review_30d.csv)：`pending_at_landmark=false;bad_in_30d/reviews_in_30d` |
| 节点已送达观察到首次差评事件比例 | 11.01% | 537/4878；分母 4878 | [review_timing_study.py:L205](../review_timing_study.py#L205) | [review_timing_study/landmark_future_first_review_30d.csv](../review_timing_study/landmark_future_first_review_30d.csv)：`pending_at_landmark=false;bad_in_30d/eligible_orders` |

完整说明、原始数值与限制见 [CSV索引](evidence_index.csv) 和 [JSON快照](evidence_snapshot.json)。
