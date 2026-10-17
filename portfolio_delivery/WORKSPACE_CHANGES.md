# 工作区变更与历史保护

开始和结束检查均表明项目及上级目录不是Git仓库；没有可用Git diff。以首次快照和SHA256审计本轮变更。没有初始化、暂存、提交、推送或部署。现存忽略目录中的旧Git探针仅用于只读check-ignore，没有运行git init。

119个既有非运行时文件保持相同哈希；包括九张原始CSV及project、deep_study、review_timing_study、final_delivery、decision_study全部已有成果。仅以下根文件按本轮要求更新，原文备份在history/：

| 文件 | 原SHA256前缀 | 当前SHA256前缀 |
|---|---|---|
| .gitignore | b20f2f70225a… | 418f1d5dc13d… |
| README.md | 8dc8383f8f62… | baa2ab8e5fa0… |

新增公开文件共19个，位于portfolio_delivery/；准确路径见publication_manifest.csv。新建复现副本和虚拟环境位于忽略的.repro_runs/portfolio_*。本轮初始清单见protected_manifest.json。历史交付中的README哈希和公开清单反映当时版本，本轮授权更新不回写那些历史记录。
