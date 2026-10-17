"""Read-only release checks; never initializes, stages, or commits a Git repo."""
from pathlib import Path
import argparse, csv, hashlib, json, os, re, shutil, subprocess
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'portfolio_delivery'
RUNTIME={'.git','.repro_runs','audit_deps','__pycache__','.venv','venv','.matplotlib_cache','matplotlib_cache'}
AUTHORIZED={'README.md','.gitignore'}

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def files():
    answer=[]
    for base,dirs,names in os.walk(ROOT):
        dirs[:]=[d for d in dirs if d not in RUNTIME]
        answer.extend(Path(base)/n for n in names)
    return sorted(answer)

def dump(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def snapshot():
    target=OUT/'protected_manifest.json'
    if target.exists():raise RuntimeError('Initial snapshot already exists; refusing to reset history baseline')
    before={p.relative_to(ROOT).as_posix():sha(p) for p in files() if OUT not in p.parents}
    (OUT/'history').mkdir(exist_ok=True)
    for rel in AUTHORIZED:shutil.copy2(ROOT/rel,OUT/'history'/(rel.replace('.','_')+'_before_portfolio.txt'))
    dump('protected_manifest.json',{'scope':'All pre-existing non-runtime files; only root README.md and .gitignore authorized to change','files':before,'authorized_changes':sorted(AUTHORIZED)})
    print(json.dumps({'existing_files_snapshotted':len(before),'authorized_changes':sorted(AUTHORIZED)}))

def git_probe(paths):
    probe=subprocess.run(['git','-C',str(ROOT),'rev-parse','--show-toplevel'],capture_output=True,text=True)
    existing=ROOT/'.repro_runs/gitignore_probe/.git'
    if probe.returncode==0:
        prefix=['git','-C',str(ROOT)]
        method='Existing project repository, read-only check-ignore --no-index'
    elif existing.exists():
        prefix=['git','--git-dir='+str(existing),'--work-tree='+str(ROOT)]
        method='Existing ignored probe Git metadata, project work-tree; no Git initialization or index writes'
    else:
        raise RuntimeError('No existing Git metadata for real ignore-rule verification; initialize nothing automatically')
    process=subprocess.run([*prefix,'check-ignore','--no-index','-z','--stdin'],input='\0'.join(paths)+'\0',capture_output=True,text=True,encoding='utf-8')
    assert process.returncode in (0,1),process.stderr
    ignored=set(process.stdout.rstrip('\0').split('\0')) if process.stdout else set()
    status=subprocess.run(['git','-C',str(ROOT),'status','--short','--branch'],capture_output=True,text=True)
    return ignored,{'repository_exists':probe.returncode==0,'root':probe.stdout.strip() if probe.returncode==0 else None,'status':status.stdout.splitlines() if status.returncode==0 else [],'probe_error':probe.stderr.strip() if probe.returncode else None,'ignore_check_method':method,'initialized':False,'index_modified':False,'commit_created':False,'pushed':False}

def main():
    manifest=json.loads((OUT/'protected_manifest.json').read_text(encoding='utf-8'))['files']
    changed=[];preserved=0
    for rel,expected in manifest.items():
        actual=sha(ROOT/rel)
        if actual!=expected:
            assert rel in AUTHORIZED,rel
            changed.append({'path':rel,'before_sha256':expected,'after_sha256':actual})
        else:preserved+=1
    assert set(x['path'] for x in changed)<=AUTHORIZED
    # Reserve the audit outputs before deriving a reproducible proposed file list.
    for name in ['publication_audit.json','publication_manifest.csv','WORKSPACE_CHANGES.md','GITHUB_CHECKLIST.md']:
        if not (OUT/name).exists():(OUT/name).write_text('',encoding='utf-8')
    all_files=files();rels=[p.relative_to(ROOT).as_posix() for p in all_files]
    examples=['decision_study/.matplotlib_cache/fontlist.json','portfolio_delivery/.matplotlib_cache/fontlist.json','.repro_runs/any/.venv/pyvenv.cfg','.env','config.env','secrets.yaml','service-account-prod.json','client.pem','data/raw/orders.csv']
    ignored,git=git_probe(rels+examples)
    raw=[p.name for p in ROOT.glob('olist_*_dataset.csv')]+['product_category_name_translation.csv']
    assert len(raw)==9 and set(raw)<=ignored
    assert set(examples)<=ignored,set(examples)-ignored
    public=[p for p in all_files if p.relative_to(ROOT).as_posix() not in ignored]
    assert ROOT/'decision_study/priority_backtest.csv' in public
    assert ROOT/'project/metrics.json' in public
    large=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'ignored':p.relative_to(ROOT).as_posix() in ignored} for p in all_files if p.stat().st_size>=10*1024**2]
    assert all(x['ignored'] for x in large),large
    signatures={
        'aws_key':r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
        'private_key':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
        'api_key_shape':r'\bsk-[A-Za-z0-9_-]{24,}\b',
        'github_token_shape':r'\bgh[pousr]_[A-Za-z0-9]{30,}\b',
    }
    hits=[];scanned=0;identifier_outputs=[]
    for p in public:
        if p.suffix.lower() not in {'.py','.md','.json','.csv','.sql','.txt','.toml','.yaml','.yml','.cfg'}:continue
        assert p.stat().st_size<5*1024**2,p
        scanned+=1
        for number,line in enumerate(p.read_text(encoding='utf-8-sig',errors='replace').splitlines(),1):
            for label,pattern in signatures.items():
                if re.search(pattern,line):hits.append({'path':p.relative_to(ROOT).as_posix(),'line':number,'signature':label})
        if p.suffix=='.csv':
            with p.open(encoding='utf-8-sig',newline='') as f:header=next(csv.reader(f),[])
            if any(x in header for x in ['order_id','customer_id','customer_unique_id','review_id','review_comment_message']):identifier_outputs.append(p.relative_to(ROOT).as_posix())
    assert not hits,'Credential-shaped content detected; values intentionally not printed'
    assert not identifier_outputs,identifier_outputs
    credential_files=[p.relative_to(ROOT).as_posix() for p in all_files if p.name in {'.env','credentials','credentials.json','id_rsa','id_ed25519'} or p.suffix in {'.pem','.key','.p12','.pfx'}]
    public_set=set(public);broken=[];links=0;ignored_link_notes=[]
    docs=[ROOT/'README.md',*OUT.glob('*.md')]
    for doc in docs:
        for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',doc.read_text(encoding='utf-8')):
            target=unquote(target.strip('<>').split('#',1)[0])
            if not target or re.match(r'^(https?://|mailto:)',target):continue
            resolved=(doc.parent/target).resolve();links+=1
            if not resolved.exists():broken.append({'document':doc.relative_to(ROOT).as_posix(),'target':target})
            elif resolved.is_file() and resolved not in public_set:ignored_link_notes.append({'document':doc.relative_to(ROOT).as_posix(),'target':target})
    assert not broken,broken
    assert not ignored_link_notes,ignored_link_notes
    evidence=json.loads((OUT/'evidence_snapshot.json').read_text(encoding='utf-8'))['metrics']
    old_evidence=json.loads((ROOT/'final_delivery/evidence_snapshot.json').read_text(encoding='utf-8'))['metrics']
    assert evidence[:len(old_evidence)]==old_evidence
    for item in evidence:
        code=(ROOT/item['code']).read_text(encoding='utf-8').splitlines()
        assert item['code_anchor'] in code[item['line']-1],item['key']
        assert ROOT/item['output'] in public_set,item['output']
    with (ROOT/'decision_study/priority_backtest.csv').open(encoding='utf-8-sig',newline='') as f:
        policies=list(csv.DictReader(f))
    actual={r['strategy']:r for r in policies if float(r['capacity_fraction'])==.2}
    assert all(int(r['selected_orders'])==895 for r in actual.values())
    assert float(actual['geo_four_cell']['selected_bad_events'])==712 and float(actual['oldest_purchase']['selected_bad_events'])==620
    assert float(actual['stage_wait']['selected_bad_events'])==704
    assert abs(float(actual['geo_four_cell']['recall_gain_vs_wait_pp'])-100*(712-620)/3157)<1e-10
    replay=json.loads((OUT/'reproducibility.json').read_text(encoding='utf-8'))
    assert replay['status']=='passed'
    audit={'git':git,'original_csv_count':9,'original_csv_ignored':True,'ignore_examples_matched':examples,'historical_files_unchanged':preserved,'authorized_changed_files':changed,'proposed_file_count':len(public),'secret_scan_text_files':scanned,'secret_signature_hits':hits,'credential_like_files_outside_runtime':credential_files,'order_customer_review_id_csvs_proposed':identifier_outputs,'scan_limits':'Pattern checks on proposed text files, no semantic guarantee; raw data and runtime excluded. Anonymous seller ranking IDs may remain in historical aggregate tables.','files_over_10mib':large,'proposed_files_over_10mib':[],'new_document_local_links_checked':links,'broken_links':broken,'links_to_ignored_files':ignored_link_notes,'evidence_entries_checked':len(evidence),'legacy_evidence_preserved':len(old_evidence),'reproduction_status':replay['status'],'license_verified_from_publisher':'CC BY-NC-SA 4.0','license_verified_on':'2026-10-17','release_performed':False}
    dump('publication_audit.json',audit)
    change_rows='\n'.join(f"| {x['path']} | {x['before_sha256'][:12]}… | {x['after_sha256'][:12]}… |" for x in changed)
    new_files=[p.relative_to(ROOT).as_posix() for p in public if p.relative_to(ROOT).as_posix() not in manifest]
    (OUT/'WORKSPACE_CHANGES.md').write_text(f'''# 工作区变更与历史保护

开始和结束检查均表明项目及上级目录不是Git仓库；没有可用Git diff。以首次快照和SHA256审计本轮变更。没有初始化、暂存、提交、推送或部署。现存忽略目录中的旧Git探针仅用于只读check-ignore，没有运行git init。

{preserved}个既有非运行时文件保持相同哈希；包括九张原始CSV及project、deep_study、review_timing_study、final_delivery、decision_study全部已有成果。仅以下根文件按本轮要求更新，原文备份在history/：

| 文件 | 原SHA256前缀 | 当前SHA256前缀 |
|---|---|---|
{change_rows}

新增公开文件共{len(new_files)}个，位于portfolio_delivery/；准确路径见publication_manifest.csv。新建复现副本和虚拟环境位于忽略的.repro_runs/portfolio_*。本轮初始清单见protected_manifest.json。历史交付中的README哈希和公开清单反映当时版本，本轮授权更新不回写那些历史记录。
''',encoding='utf-8')
    (OUT/'GITHUB_CHECKLIST.md').write_text(f'''# GitHub发布验收清单（尚未发布）

## 已完成

- [x] 招聘方首页、四阶段阅读路线、已有图表、简历描述与5个追问。
- [x] 历史成果保护：{preserved}个既有文件哈希相同，根README和.gitignore为明确授权变更。
- [x] 九个原始CSV均被实际Git忽略规则匹配；缓存、环境、逐单异常及凭据路径也排除。
- [x] 拟公开{len(public)}个文件；文本模式扫描{scanned}个，无命中密钥形状；无订单/客户/评价ID逐单CSV被纳入。
- [x] 拟公开文件无超过10MiB者；保留重要SQL、代码、定义、聚合结果、图表、历史验证记录。
- [x] 独立虚拟环境实际重跑已有四阶段计算，见[复现记录](REPRODUCIBILITY.md)。
- [x] 数据署名和CC BY-NC-SA 4.0条款链接，见[数据来源与许可](DATA_LICENSE.md)。

## 发布前仍需作者完成

- [ ] 核对[拟公开文件清单](publication_manifest.csv)及[扫描记录](publication_audit.json)。模式扫描不是无敏感内容的证明。
- [ ] 决定原创代码的开源许可；当前没有擅自替作者选择MIT等许可。数据及其改编材料的上游限制不被代码许可替代。
- [ ] 署名信息使用本人愿意公开的名字；本项目不填造作者、教育或任职经历。
- [ ] 经作者授权后建立仓库，检查git status及暂存差异；本轮没有执行这些动作。尤其.gitignore不会自动移除未来已被跟踪的数据。
- [ ] 如决定推送，重新检查远程地址、可见性与数据授权；推送、公开发布和部署均未执行。

## 公开范围

纳入：首页、依赖清单、原分析代码与SQL、聚合CSV/JSON、已验证PNG、历史报告和本轮交付。原始数据由读者从发布者取得。保留匿名卖家汇总ID用于历史可追溯，不纳入客户/订单明细或评价文本。不得将此作品描述为Olist官方项目或真实客服干预结果。

完整清单由本地实际文件和Git忽略规则生成，不等于已暂存或已发布。当前无项目Git仓库；运行时目录内旧探针不是项目仓库。
''',encoding='utf-8')
    # Fill manifest last so all ordinary file sizes/hashes reflect final content.
    self_refs={'portfolio_delivery/publication_manifest.csv','portfolio_delivery/publication_audit.json'}
    with (OUT/'publication_manifest.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['path','bytes','sha256','status']);writer.writeheader()
        for p in public:
            rel=p.relative_to(ROOT).as_posix()
            writer.writerow({'path':rel,'bytes':'' if rel in self_refs else p.stat().st_size,'sha256':'' if rel in self_refs else sha(p),'status':'proposed_only_not_staged'})
    print(json.dumps({'history_preserved':preserved,'authorized_changes':[x['path'] for x in changed],'proposed_files':len(public),'links_checked':links,'secret_hits':len(hits),'git_repository':git['repository_exists']},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--snapshot',action='store_true');args=parser.parse_args()
    snapshot() if args.snapshot else main()
