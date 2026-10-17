"""Replay unchanged research in a new no-system-packages venv and compare outputs.

No new study, fitting specification, Git operation, or writes to old deliverables.
"""
from pathlib import Path
import argparse, datetime, hashlib, json, math, os, shutil, subprocess, sys, time, venv

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'portfolio_delivery'
SCRIPTS=['audit_olist.py','run_project.py','deep_audit.py','review_timing_study.py','build_review_timing_report.py']
SKIP_NUMERIC={'iterations','iteration_count','score_gradient_max_abs','condition_number'}
RECORDS=[]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def dump(summary):(OUT/'reproducibility.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')

def compare(a,b,path='',skip=()):
    if isinstance(a,dict):
        assert isinstance(b,dict) and a.keys()==b.keys(),path
        for key in a:
            if key not in skip:compare(a[key],b[key],path+'/'+key,skip)
    elif isinstance(a,list):
        assert len(a)==len(b),path
        for i,(x,y) in enumerate(zip(a,b)):compare(x,y,path+'/'+str(i),skip)
    elif isinstance(a,bool) or a is None or isinstance(a,str):assert a==b,(path,a,b)
    elif isinstance(a,int):assert a==b,(path,a,b)
    elif math.isnan(a):assert math.isnan(b),path
    else:assert math.isclose(a,b,rel_tol=1e-4,abs_tol=1e-6),(path,a,b)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--offline',action='store_true',help='Use pip cache only; no package-index access');args=parser.parse_args()
    run_name='portfolio_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    base=ROOT/'.repro_runs'/run_name;work=base/'work';envdir=base/'.venv';logs=base/'logs'
    work.mkdir(parents=True);logs.mkdir()
    protected=load(OUT/'protected_manifest.json')['files'] if (OUT/'protected_manifest.json').exists() else None
    before={p.relative_to(ROOT).as_posix():sha(p) for directory in ['project','deep_study','review_timing_study','final_delivery','decision_study'] for p in (ROOT/directory).rglob('*') if p.is_file() and not any(x in p.parts for x in ['__pycache__','.matplotlib_cache'])}
    source_files=sorted(ROOT.glob('olist_*_dataset.csv'))+[ROOT/'product_category_name_translation.csv']
    assert len(source_files)==9
    copied=[]
    for path in source_files+[ROOT/n for n in SCRIPTS]:
        shutil.copy2(path,work/path.name);assert sha(path)==sha(work/path.name);copied.append(path.name)
    (work/'decision_study').mkdir()
    for path in [*(ROOT/'decision_study').glob('*.py'),ROOT/'decision_study/design.json',ROOT/'decision_study/freeze_guard.json']:
        shutil.copy2(path,work/'decision_study'/path.name);assert sha(path)==sha(work/'decision_study'/path.name)
    venv.EnvBuilder(with_pip=True,system_site_packages=False).create(envdir)
    python=envdir/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    summary={'status':'running','run_directory':base.relative_to(ROOT).as_posix(),'source_copies':copied,'new_virtual_environment':True,'system_site_packages':False,'audit_deps_copied':False,'commands':RECORDS,'platform':sys.platform,'python_host':sys.version,'rtol':1e-4,'atol':1e-6,'scope':'Rerun existing analyses, no new research; isolated code+CSV simulation, not remote Git clone','limitations':['Windows/Python 3.12 execution only','Historical handwritten reports are preserved, not automatically regenerated','Fonts/PNG byte identity and source-system truth not validated','No experiment, deployment or realized customer-service benefit']}
    dump(summary)
    def command(arguments,name,stdout_file=None):
        started=time.perf_counter();env=os.environ.copy();env.pop('PYTHONPATH',None)
        env.update(PYTHONUTF8='1',PYTHONHASHSEED='0',PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1',MPLCONFIGDIR=str(base/'matplotlib_cache'),PIP_DISABLE_PIP_VERSION_CHECK='1')
        result=subprocess.run([str(python),'-X','utf8',*arguments],cwd=work,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
        for kind,value in [('stdout',result.stdout),('stderr',result.stderr)]: (logs/(name+'.'+kind+'.txt')).write_text(value,encoding='utf-8')
        RECORDS.append({'step':name,'command':['<fresh-venv-python>','-X','utf8',*arguments],'exit_code':result.returncode,'seconds':round(time.perf_counter()-started,3),'stderr_nonempty':bool(result.stderr.strip()),'logs':(logs/name).relative_to(ROOT).as_posix()})
        dump(summary);print(f'{name}: exit={result.returncode}, seconds={RECORDS[-1]["seconds"]}',flush=True)
        if result.returncode:raise RuntimeError(name+' failed; inspect ignored local logs')
        if stdout_file:stdout_file.write_text(result.stdout,encoding='utf-8')
        return result.stdout
    try:
        install=['-m','pip','install','-r',str(ROOT/'requirements-repro.txt'),'-c',str(ROOT/'final_delivery/environment.freeze.txt')]
        if args.offline:install.append('--no-index')
        command(install,'pinned_install')
        command(['-m','pip','check'],'pip_check')
        probe=json.loads(command(['-c',"import sys,site,json,statsmodels,pandas,numpy; print(json.dumps({'python':sys.version,'prefix':sys.prefix,'base_prefix':sys.base_prefix,'enable_user_site':site.ENABLE_USER_SITE,'statsmodels_file':statsmodels.__file__,'pandas_file':pandas.__file__,'numpy_file':numpy.__file__}))"],'environment_probe'))
        assert probe['prefix']!=probe['base_prefix'] and not probe['enable_user_site']
        assert all(str(envdir).lower() in probe[k].lower() for k in ['statsmodels_file','pandas_file','numpy_file'])
        summary['environment_probe']=probe
        freeze=command(['-m','pip','freeze'],'pip_freeze');(OUT/'environment.freeze.txt').write_text(freeze,encoding='utf-8')
        command(['audit_olist.py'],'data_audit',work/'audit_results.json')
        command(['run_project.py'],'baseline')
        command(['deep_audit.py'],'statistical_audit')
        command(['review_timing_study.py'],'review_timing')
        command(['decision_study/priority_study.py'],'priority_backtest')
        compared=[]
        for name in ['project/metrics.json','deep_study/deep_metrics.json','review_timing_study/timing_metrics.json']:
            compare(load(ROOT/name),load(work/name),skip=SKIP_NUMERIC);compared.append(name)
        audit=load(work/'audit_results.json');audit['reviews'].pop('examples',None)
        compare(load(ROOT/'final_delivery/audit_reference.json'),audit);compared.append('audit vs public audit_reference.json')
        a=load(ROOT/'decision_study/priority_metrics.json');b=load(work/'decision_study/priority_metrics.json')
        # Environment/history footprint/timing vary; compare every scientific result.
        for key in ['environment','elapsed_seconds_before_reporting']:a.pop(key,None);b.pop(key,None)
        a['audit'].pop('historical_files_sha256_unchanged',None);b['audit'].pop('historical_files_sha256_unchanged',None)
        compare(a,b);compared.append('decision_study/priority_metrics.json: all scientific and audit fields')
        assert sha(ROOT/'decision_study/frozen_rules.json')==sha(work/'decision_study/frozen_rules.json')
        csv_check=r'''
from pathlib import Path
import json,pandas as pd
root=Path(__ROOT__);work=Path.cwd();rows=[]
for directory in ['project','deep_study','review_timing_study','decision_study']:
 for ref in sorted((root/directory).glob('*.csv')):
  if ref.name=='sequence_flag_evidence.csv':continue
  rel=ref.relative_to(root);actual=work/rel
  assert actual.exists(),str(rel)
  pd.testing.assert_frame_equal(pd.read_csv(ref),pd.read_csv(actual),check_dtype=False,check_exact=False,rtol=1e-4,atol=1e-6)
  rows.append(rel.as_posix())
print(json.dumps(rows))
'''.replace('__ROOT__',repr(str(ROOT)))
        csvs=json.loads(command(['-c',csv_check],'aggregate_csv_comparison'))
        figures=[p.relative_to(work).as_posix() for directory in ['project','deep_study','review_timing_study','decision_study'] for p in (work/directory).rglob('*.png')]
        assert len(figures)==7 and all((work/p).stat().st_size>1000 for p in figures)
        assert all(sha(ROOT/rel)==expected for rel,expected in before.items())
        assert all(sha(ROOT/p.name)==sha(work/p.name) for p in source_files)
        summary.update(status='passed',compared_json=compared,compared_csv=csvs,regenerated_figures=figures,frozen_rules_sha256_equal=True,historical_analysis_files_unchanged=len(before),raw_csv_hashes_unchanged=9,excluded_comparisons=['Optimization iteration counts, tiny score gradients, condition numbers','Decision metrics environment, elapsed time and historical footprint count','Per-order sequence evidence not needed in public reference'],source_sha256={p.name:sha(p) for p in source_files})
        dump(summary);print(f'PASS: {len(compared)} JSON references, {len(csvs)} aggregate CSVs, {len(figures)} regenerated figures; original analysis files unchanged.',flush=True)
    except Exception as exc:
        summary.update(status='failed',failure_type=type(exc).__name__,failure_message=str(exc));dump(summary);raise

if __name__=='__main__':main()
