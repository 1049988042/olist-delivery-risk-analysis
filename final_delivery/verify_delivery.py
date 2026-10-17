"""Verify delivery documentation, history preservation and publication scope.

Creates a throwaway Git repository only under ignored .repro_runs/ to test ignore
rules. Never initializes/stages/commits the project repository.
"""
from pathlib import Path
import csv, hashlib, json, os, re, shutil, subprocess
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'final_delivery'

def read_json(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def git(args,cwd=ROOT,input_text=None):
    return subprocess.run(['git','-C',str(cwd),*args],input=input_text,capture_output=True,text=True,encoding='utf-8',errors='replace')

def write_reproduction_doc(r):
    display={
      'pinned_install':'<venv-python> -m pip install -r requirements-repro.txt',
      'pip_check':'<venv-python> -m pip check', 'pip_freeze':'<venv-python> -m pip freeze',
      'environment_probe':'<venv-python> -c <环境与statsmodels路径探针，完整命令见JSON>',
      'audit':'<venv-python> -X utf8 audit_olist.py',
      'baseline':'<venv-python> -X utf8 run_project.py',
      'deep':'<venv-python> -X utf8 deep_audit.py',
      'review_timing':'<venv-python> -X utf8 review_timing_study.py',
      'csv_comparison':'<venv-python> -c <逐CSV比较，完整命令见JSON>',
    }
    if any(x['name']=='pinned_install' and '-c' in x['command'] for x in r['commands']):
        display['pinned_install']+=' -c final_delivery/environment.freeze.txt'
    rows='\n'.join(f'| {x["name"]} | `{display[x["name"]]}` | {x["exit_code"]} | {x["elapsed_seconds"]} | {"有" if x["stderr_nonempty"] else "无"} |' for x in r['commands'])
    text=f'''# 可复现性验证：实际执行记录

结论：**{r['status']}**。本轮新建Windows/Python 3.12.6虚拟环境，`system_site_packages=False`；复制九张原始CSV和五个原脚本到`.repro_runs/clean_env/`，未复制`audit_deps`，statsmodels确实从新虚拟环境导入。原始数据、历史代码和历史输出均在原目录只读。

实际先运行`python final_delivery/prepare_workspace.py`，再执行`python final_delivery/reproduce.py`。安装固定直接依赖成功；`pip check`无依赖冲突。下表命令均实际执行，工作目录为隔离副本；为便于阅读只缩写了长`-c`代码，完整参数、退出码、耗时与本地日志位置见[机器记录](reproducibility.json)。每条实际Python命令同时包含`-X utf8`。

| 步骤 | 实际命令（路径简写） | 退出码 | 秒 | stderr |
|---|---|---:|---:|---|
{rows}

## 比较的实际范围

- {len(r['compared_json'])}份JSON：audit_results.json、project/metrics.json、deep_study/deep_metrics.json、review_timing_study/timing_metrics.json。
- {len(r['compared_csv'])}份CSV：三个阶段目录下保留的全部参考CSV，包括分组、时间容忍、承诺节点与SQL交叉核对结果。公开副本不含逐单异常清单，因此比完整本地参考少一份；重跑仍会生成该本地清单。
- {len(r['regenerated_figures'])}张PNG从脚本重新生成；验证文件存在及非空，不要求图像字节相同。
- {r['historical_files_unchanged']}个历史/原始文件的SHA-256保持不变；原README另存历史副本，首页改写是本轮授权整理。
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
'''
    public_test=OUT/'public_snapshot_test.json'
    if public_test.exists():
        p=read_json(public_test);assert p['status']=='passed'
        text+=f'''\n## 仅公开文件集的第二次验证\n\n另外按publication_manifest复制拟公开文件，明确不带audit_results.json、audit_deps、逐单异常和压缩审计表，再单独提供本地九张原始CSV。在新的虚拟环境中完整执行README四条命令，全部退出码为0；{len(p['replay']['compared_json'])}份JSON参考、{len(p['replay']['compared_csv'])}份公开CSV参考匹配，5图重建。审查JSON使用去除示例的audit_reference.json，消除了对本机私有产物的依赖。它是本地公开文件集模拟，不是远程Git克隆或公开发布。详见[第二次验证记录](public_snapshot_test.json)。\n'''
    text=text.replace('在新的虚拟环境中完整执行README四条命令，全部退出码为0','在新的虚拟环境中执行README流程，分析重跑成功，最终发布校验经修复后通过')
    if public_test.exists() and p.get('initial_failure'):
        text+='\n首次公开副本发布校验曾因不存在的逐单文件被错误要求出现在已忽略文件集合中而失败。修正规则测试后，仅重跑该校验并成功；分析步骤此前已通过，没有重复拟合或隐藏首次失败。详见上述第二次验证记录。\n'
    (OUT/'REPRODUCIBILITY.md').write_text(text,encoding='utf-8')

def main():
    r=read_json(OUT/'reproducibility.json');assert r['status']=='passed'
    runtime_manifest=ROOT/'.repro_runs/clean_env/input_manifest.json'
    manifest=read_json(runtime_manifest if runtime_manifest.exists() else OUT/'historical_manifest.json')
    for rel,expected in manifest.items():assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==expected,rel
    write_reproduction_doc(r)
    repo=git(['rev-parse','--show-toplevel'])
    repo_exists=repo.returncode==0
    status=git(['status','--short']) if repo_exists else None
    tracked=git(['ls-files']).stdout.splitlines() if repo_exists else []
    git_info={'project_repository_exists':repo_exists,'detected_root':repo.stdout.strip() if repo_exists else None,'status_short':status.stdout.splitlines() if status else [],'project_initialized_by_this_task':False,'index_modified':False,'commit_created':False,'remote_pushed':False,'probe_error':repo.stderr.strip() if not repo_exists else None}
    # Existing docs are preserved; these two artifacts are generated placeholders
    # before enumerating files so they are included in the publication manifest.
    for name in ['publication_audit.json','publication_manifest.csv']:
        if not (OUT/name).exists():(OUT/name).write_text('',encoding='utf-8')
    checklist=f'''# 最终交付清单与Git提交准备

- [x] [统一中文报告](FINAL_REPORT.md)：业务问题、质量、关联、时序、节点、建议、实验设计和局限。
- [x] [30项指标证据索引](EVIDENCE_INDEX.md)、CSV与JSON快照：代码行、统计输出、公式、分母。
- [x] [三阶段衔接](STAGE_RECONCILIATION.md)：保留修正轨迹，不混用样本。
- [x] [招聘方README](../README.md)：发现、图表、方法、复现、局限、报告入口；原版已备份。
- [x] [复现记录](REPRODUCIBILITY.md)：独立环境实际运行，{len(r['compared_json'])}份JSON、{len(r['compared_csv'])}份CSV匹配，{len(r['regenerated_figures'])}图重建。
- [x] [25道面试题](INTERVIEW.md)：订单粒度、差评、回归、时序、选择偏差、建议与实验。
- [x] [推荐目录结构](PROJECT_STRUCTURE.md)：保持历史路径，不删除无关产物。
- [x] [.gitignore](../.gitignore)：原始九表、逐单衍生数据、依赖、缓存、凭据和大文件忽略规则。
- [x] [发布准备检查](publication_audit.json)与[建议纳入文件清单](publication_manifest.csv)。
- [ ] Git提交：项目仓库当前{'已存在，必须由用户确认后才可提交' if repo_exists else '未建立，因此未初始化、暂存或提交'}。
- [ ] 远程发布、推送、部署：未执行。
- [ ] 真实监控、实验、经营收益：未实施或识别。

## 拟纳入公开版本的范围（未暂存）

README、.gitignore、固定依赖及原脚本，三阶段的历史报告/SQL/聚合结果/图表，以及本次统一报告、证据、复现和面试材料。精确路径见建议清单；清单是本地准备结果，不是Git提交或已发布清单。

不纳入：原始CSV、audit_deps、虚拟环境、复现数据副本、逐单审计和异常证据、凭据与缓存。原始CSV共九个，均应被实际Git忽略规则匹配。公开的聚合CSV保留，不使用一刀切的`*.csv`规则。

如果以后建立项目Git仓库，应重新检查`git status`与暂存差异；.gitignore不能移除已经被跟踪的敏感文件。当前没有用户确认的提交动作，不会自动创建提交。

## 求职展示自审

作品优势是数据粒度、分母和时间顺序审计，以及将统计证据转化为可验证的运营问题。主要不足是事件日志和业务成本缺失、非随机问卷、评价选择偏差、未观测混杂、没有真实实验或上线证据。展示时应以统一报告为主，历史报告用于解释审计演进，不把指标差异包装为可实现收益。
'''
    (OUT/'DELIVERY_CHECKLIST.md').write_text(checklist,encoding='utf-8')
    files=[]
    skip={'.git','.repro_runs','audit_deps','__pycache__','.venv','venv','.pytest_cache'}
    for base,dirs,names in os.walk(ROOT):
        dirs[:]=[d for d in dirs if d not in skip]
        for name in names:
            path=Path(base)/name;files.append(path)
    rels=sorted(str(p.relative_to(ROOT)).replace('\\','/') for p in files)
    probe=ROOT/'.repro_runs'/'gitignore_probe';probe.mkdir(parents=True,exist_ok=True)
    init=git(['init','--quiet'],probe);assert init.returncode==0
    shutil.copy2(ROOT/'.gitignore',probe/'.gitignore')
    ignored_result=git(['check-ignore','--no-index','-z','--stdin'],probe,'\0'.join(rels)+'\0')
    assert ignored_result.returncode in (0,1)
    ignored=set(ignored_result.stdout.rstrip('\0').split('\0')) if ignored_result.stdout else set()
    original_names=[p.name for p in ROOT.glob('olist_*_dataset.csv')]+['product_category_name_translation.csv']
    assert len(original_names)==9 and all(p in ignored for p in original_names)
    derivative_names=['audit_results.json','review_timing_study/order_timing_audit.csv.gz','review_timing_study/sequence_flag_evidence.csv']
    derivative_stdout=git(['check-ignore','--no-index','-z','--stdin'],probe,'\0'.join(derivative_names)+'\0').stdout
    derivative_ignored=set(derivative_stdout.rstrip('\0').split('\0')) if derivative_stdout else set()
    assert set(derivative_names)<=derivative_ignored
    rule_examples=['audit_deps/statsmodels/api.py','.repro_runs/clean_env/olist_orders_dataset.csv','.venv/pyvenv.cfg','__pycache__/example.pyc','.env','service-account-prod.json','client.pem']
    example_stdout=git(['check-ignore','--no-index','-z','--stdin'],probe,'\0'.join(rule_examples)+'\0').stdout
    example_ignored=example_stdout.rstrip('\0').split('\0') if example_stdout else []
    assert set(rule_examples)<=set(example_ignored),set(rule_examples)-set(example_ignored)
    candidates=[rel for rel in rels if rel not in ignored]
    signatures={
        'aws_access_key':re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
        'private_key_header':re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
        'api_token_shape':re.compile(r'\bsk-[A-Za-z0-9_-]{24,}\b'),
        'github_token_shape':re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}\b'),
    }
    secret_hits=[];scanned=0
    for rel in candidates:
        path=ROOT/rel
        if path.suffix.lower() not in {'.py','.md','.json','.csv','.sql','.txt','.toml','.yaml','.yml','.ini','.cfg'}:continue
        if path.stat().st_size>5*1024*1024:continue
        scanned+=1
        for number,line in enumerate(path.read_text(encoding='utf-8-sig',errors='replace').splitlines(),1):
            for label,pattern in signatures.items():
                if pattern.search(line):secret_hits.append({'path':rel,'line':number,'signature':label})
    assert not secret_hits,'Potential credential pattern found; inspect locally'
    public_large=[{'path':rel,'bytes':(ROOT/rel).stat().st_size} for rel in candidates if (ROOT/rel).stat().st_size>=10*1024*1024]
    assert not public_large,public_large
    all_large=[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'bytes':p.stat().st_size,'ignored':str(p.relative_to(ROOT)).replace('\\','/') in ignored} for p in files if p.stat().st_size>=10*1024*1024]
    tracked_ignored=sorted(set(tracked)&ignored)
    assert not tracked_ignored,tracked_ignored
    cache_footprint=[]
    for name in ['audit_deps','.repro_runs','__pycache__']:
        directory=ROOT/name
        if directory.exists():
            sizes=[p.stat().st_size for p in directory.rglob('*') if p.is_file()]
            cache_footprint.append({'directory':name,'files':len(sizes),'bytes':sum(sizes),'proposed_for_publication':False})
    credential_like_files=[str(p.relative_to(ROOT)).replace('\\','/') for p in files if p.name=='.env' or p.name.startswith('.env.') or p.suffix.lower() in {'.pem','.key','.p12','.pfx'} or p.name in {'credentials','credentials.json'} or p.name.startswith('service-account')]
    link_errors=[];link_count=0
    docs=[ROOT/'README.md',*[p for p in OUT.glob('*.md')]]
    for doc in docs:
        for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',doc.read_text(encoding='utf-8')):
            target=target.strip().strip('<>')
            if re.match(r'^(https?://|mailto:|#)',target):continue
            target=unquote(target.split('#',1)[0])
            if not target:continue
            link_count+=1
            if not (doc.parent/target).exists():link_errors.append({'document':str(doc.relative_to(ROOT)),'target':target})
    assert not link_errors,link_errors
    evidence=read_json(OUT/'evidence_snapshot.json')['metrics']
    for item in evidence:
        lines=(ROOT/item['code']).read_text(encoding='utf-8').splitlines()
        assert item['code_anchor'] in lines[item['line']-1],item['key']
        assert (ROOT/item['output']).exists()
    audit={'git':git_info,'gitignore_test_method':'git check-ignore --no-index in ignored throwaway repository, without modifying project index','original_csv_count':len(original_names),'all_original_csv_ignored':True,'per_order_derivatives_ignored':derivative_names,'runtime_cache_secret_rule_examples_matched':example_ignored,'candidate_file_count':len(candidates),'secret_scan_text_files':scanned,'credential_like_files_present_outside_runtime_dirs':credential_like_files,'potential_secret_signatures':secret_hits,'secret_scan_limitations':'Pattern scan of proposed text files only; not a proof that no confidential content exists. No credential values printed. Raw CSVs, vendor/runtime and replay directories excluded.','files_over_10mib':all_large,'local_only_runtime_cache_footprint':cache_footprint,'proposed_files_over_10mib':public_large,'already_tracked_ignored_files':tracked_ignored,'verified_local_markdown_links':link_count,'broken_links':link_errors,'verified_evidence_entries':len(evidence),'historical_files_sha256_unchanged':len(manifest),'project_index_modified':False,'public_release_completed':False}
    (OUT/'publication_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    with (OUT/'publication_manifest.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['path','bytes','category']);writer.writeheader()
        for rel in candidates:
            # The manifest's own file length is self-referential; leave it blank.
            writer.writerow({'path':rel,'bytes':'' if rel=='final_delivery/publication_manifest.csv' else (ROOT/rel).stat().st_size,'category':'proposed_only_not_staged'})
    print(json.dumps({'reproduction':r['status'],'historical_unchanged':len(manifest),'evidence_verified':len(evidence),'links_checked':link_count,'original_csv_ignored':len(original_names),'secret_findings':len(secret_hits),'proposed_files':len(candidates),'project_git_exists':repo_exists},indent=2))

if __name__=='__main__':main()
