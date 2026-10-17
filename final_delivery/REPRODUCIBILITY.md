# 可复现性验证：实际执行记录

结论：**passed**。本轮新建Windows/Python 3.12.6虚拟环境，`system_site_packages=False`；复制九张原始CSV和五个原脚本到`.repro_runs/clean_env/`，未复制`audit_deps`，statsmodels确实从新虚拟环境导入。原始数据、历史代码和历史输出均在原目录只读。

实际先运行`python final_delivery/prepare_workspace.py`，再执行`python final_delivery/reproduce.py`。安装固定直接依赖成功；`pip check`无依赖冲突。下表命令均实际执行，工作目录为隔离副本；为便于阅读只缩写了长`-c`代码，完整参数、退出码、耗时与本地日志位置见[机器记录](reproducibility.json)。每条实际Python命令同时包含`-X utf8`。

| 步骤 | 实际命令（路径简写） | 退出码 | 秒 | stderr |
|---|---|---:|---:|---|
| pinned_install | `<venv-python> -m pip install -r requirements-repro.txt` | 0 | 3.661 | 无 |
| pip_check | `<venv-python> -m pip check` | 0 | 0.597 | 无 |
| pip_freeze | `<venv-python> -m pip freeze` | 0 | 0.557 | 无 |
| environment_probe | `<venv-python> -c <环境与statsmodels路径探针，完整命令见JSON>` | 0 | 0.083 | 无 |
| audit | `<venv-python> -X utf8 audit_olist.py` | 0 | 9.913 | 无 |
| baseline | `<venv-python> -X utf8 run_project.py` | 0 | 69.819 | 无 |
| deep | `<venv-python> -X utf8 deep_audit.py` | 0 | 44.282 | 无 |
| review_timing | `<venv-python> -X utf8 review_timing_study.py` | 0 | 19.109 | 无 |
| csv_comparison | `<venv-python> -c <逐CSV比较，完整命令见JSON>` | 0 | 0.615 | 无 |

## 比较的实际范围

- 4份JSON：audit_results.json、project/metrics.json、deep_study/deep_metrics.json、review_timing_study/timing_metrics.json。
- 30份CSV：三个阶段目录下保留的全部参考CSV，包括分组、时间容忍、承诺节点与SQL交叉核对结果。公开副本不含逐单异常清单，因此比完整本地参考少一份；重跑仍会生成该本地清单。
- 5张PNG从脚本重新生成；验证文件存在及非空，不要求图像字节相同。
- 67个历史/原始文件的SHA-256保持不变；原README另存历史副本，首页改写是本轮授权整理。
- 整数计数、布尔和文本要求一致；浮点允许rtol=1e-4、atol=1e-6。优化迭代次数、信息矩阵条件数及极小梯度等诊断不要求跨数值实现逐位相同；收敛标记仍要求匹配。

这不是“文件存在即成功”：各阶段进程实际运行，新的结果写入隔离副本并与既有结果逐项比较。环境探针和详细stdout/stderr保存在忽略的`.repro_runs/clean_env/logs/`，公开机器记录给出退出码与比较范围。

## 环境与再次复现

直接依赖固定在[requirements-repro.txt](../requirements-repro.txt)。首轮独立安装固定七个直接包，将实际解析的全部传递版本写入[environment.freeze.txt](environment.freeze.txt)；此后复现脚本发现该文件时，也会通过pip的`-c`约束传递版本。另一种全依赖安装方式是在已创建的隔离环境运行：

```powershell
.repro_runs/clean_env/.venv/Scripts/python.exe -m pip install -r final_delivery/environment.freeze.txt
```

该行是未来可用的全依赖安装方法；本轮实际安装命令以表格和JSON为准，不把未执行的命令算作验证。然后按README执行复现脚本。若源数据文件哈希不同，先核对版本，不应强行要求统计与当前数据完全相同。

## 未验证与不可声称

仅实际验证Windows/Python 3.12.6，未跑Linux/macOS或其他Python版本；依赖网络可用性、其他平台轮子和中文字体不保证。手写的基础/深度历史报告由人撰写，脚本不自动重建；其数值通过输出与统一稿证据索引对应。统一报告由已有输出构建。

没有执行源系统事件核对、在线预警、A/B实验、收益验证、远程推送或部署。时间戳语义、时区一致性、取消历史与真实入库时间仍是研究限制，不会因代码可复现而消失。

## 仅公开文件集的第二次验证

另外按publication_manifest复制拟公开文件，明确不带audit_results.json、audit_deps、逐单异常和压缩审计表，再单独提供本地九张原始CSV。在新的虚拟环境中执行README流程，分析重跑成功，最终发布校验经修复后通过；4份JSON参考、29份公开CSV参考匹配，5图重建。审查JSON使用去除示例的audit_reference.json，消除了对本机私有产物的依赖。它是本地公开文件集模拟，不是远程Git克隆或公开发布。详见[第二次验证记录](public_snapshot_test.json)。

首次公开副本发布校验曾因不存在的逐单文件被错误要求出现在已忽略文件集合中而失败。修正规则测试后，仅重跑该校验并成功；分析步骤此前已通过，没有重复拟合或隐藏首次失败。详见上述第二次验证记录。
