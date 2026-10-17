"""Replay the release-shaped file set plus locally supplied raw CSVs, offline
from any private artifacts. No upload, project git init or model changes.
"""
from pathlib import Path
import csv,json,os,shutil,subprocess,sys,time

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'final_delivery'

def main():
    with (OUT/'publication_manifest.csv').open(encoding='utf-8-sig',newline='') as f:paths=[row['path'] for row in csv.DictReader(f)]
    dest=ROOT/'.repro_runs'/'share'
    i=1
    while dest.exists():dest=ROOT/'.repro_runs'/f'share_{i}';i+=1
    dest.mkdir(parents=True)
    for rel in paths:
        target=dest/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,target)
    assert not (dest/'audit_results.json').exists()
    assert not (dest/'audit_deps').exists()
    assert not (dest/'review_timing_study/sequence_flag_evidence.csv').exists()
    assert not (dest/'review_timing_study/order_timing_audit.csv.gz').exists()
    for p in ROOT.glob('*.csv'):shutil.copy2(p,dest/p.name)
    logs=ROOT/'.repro_runs'/'public_snapshot_logs';logs.mkdir(exist_ok=True)
    results=[]
    for script in ['prepare_workspace.py','reproduce.py','build_delivery.py','verify_delivery.py']:
        start=time.perf_counter()
        command=[sys.executable,'-X','utf8',str(dest/'final_delivery'/script)]
        env=os.environ.copy();env.pop('PYTHONPATH',None)
        run=subprocess.run(command,cwd=dest,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
        (logs/(script+'.stdout.txt')).write_text(run.stdout,encoding='utf-8')
        (logs/(script+'.stderr.txt')).write_text(run.stderr,encoding='utf-8')
        results.append({'command':['python','-X','utf8','final_delivery/'+script],'exit_code':run.returncode,'elapsed_seconds':round(time.perf_counter()-start,3),'stderr_nonempty':bool(run.stderr.strip())})
        print(f'public snapshot {script}: exit={run.returncode}, {results[-1]["elapsed_seconds"]}s',flush=True)
        if run.returncode:raise RuntimeError(f'{script} failed; see ignored public_snapshot_logs')
    replay=json.loads((dest/'final_delivery/reproducibility.json').read_text(encoding='utf-8'))
    publication=json.loads((dest/'final_delivery/publication_audit.json').read_text(encoding='utf-8'))
    result={'status':'passed','source':'publication_manifest.csv plus nine locally supplied raw CSVs','snapshot_workspace':str(dest.relative_to(ROOT)).replace('\\','/'),'private_artifacts_not_copied':['audit_results.json','audit_deps','review_timing_study/sequence_flag_evidence.csv','review_timing_study/order_timing_audit.csv.gz'],'commands':results,'replay':replay,'snapshot_local_links_checked':publication['verified_local_markdown_links'],'snapshot_project_git_exists':publication['git']['project_repository_exists'],'no_upload_or_remote_clone_performed':True}
    (OUT/'public_snapshot_test.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'PASS: release-shaped snapshot replay; {len(replay["compared_json"])} JSON, {len(replay["compared_csv"])} CSV, {len(replay["regenerated_figures"])} figures.',flush=True)

def resume_verification(relative):
    dest=(ROOT/relative).resolve()
    assert dest.is_relative_to((ROOT/'.repro_runs').resolve())
    replay=json.loads((dest/'final_delivery/reproducibility.json').read_text(encoding='utf-8'))
    assert replay['status']=='passed','Only resume after the analysis has actually passed'
    logs=ROOT/'.repro_runs'/'public_snapshot_logs'
    original_failure=(logs/'verify_delivery.py.stderr.txt').read_text(encoding='utf-8')
    assert 'AssertionError' in original_failure
    shutil.copy2(OUT/'verify_delivery.py',dest/'final_delivery/verify_delivery.py')
    start=time.perf_counter()
    run=subprocess.run([sys.executable,'-X','utf8',str(dest/'final_delivery/verify_delivery.py')],cwd=dest,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (logs/'verify_delivery.retry.stdout.txt').write_text(run.stdout,encoding='utf-8')
    (logs/'verify_delivery.retry.stderr.txt').write_text(run.stderr,encoding='utf-8')
    assert run.returncode==0,run.stderr
    publication=json.loads((dest/'final_delivery/publication_audit.json').read_text(encoding='utf-8'))
    result={'status':'passed','source':'publication_manifest.csv plus nine locally supplied raw CSVs','snapshot_workspace':relative,'private_artifacts_not_copied':['audit_results.json','audit_deps','review_timing_study/sequence_flag_evidence.csv','review_timing_study/order_timing_audit.csv.gz'],'initial_failure':{'command':'python -X utf8 final_delivery/verify_delivery.py','exit_code':1,'reason':'Ignore test incorrectly required deliberately omitted per-order files to exist in the enumerated file set','log':'.repro_runs/public_snapshot_logs/verify_delivery.py.stderr.txt'},'commands':[{'command':['python','-X','utf8','final_delivery/verify_delivery.py'],'scope':'retry only after correcting path rule assertion; analysis not rerun','exit_code':run.returncode,'elapsed_seconds':round(time.perf_counter()-start,3),'stderr_nonempty':bool(run.stderr.strip())}],'replay':replay,'snapshot_local_links_checked':publication['verified_local_markdown_links'],'snapshot_project_git_exists':publication['git']['project_repository_exists'],'no_upload_or_remote_clone_performed':True}
    (OUT/'public_snapshot_test.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'PASS repaired publication check; existing fresh analysis passed {len(replay["compared_json"])} JSON, {len(replay["compared_csv"])} CSV; no new fitting.',flush=True)

if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--resume':resume_verification(sys.argv[2])
    else:main()
