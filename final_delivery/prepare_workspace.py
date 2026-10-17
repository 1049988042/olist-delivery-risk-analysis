"""Create an isolated replay workspace without changing historical outputs."""
from pathlib import Path
import hashlib, json, shutil, sys, venv

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'final_delivery'
WORK=ROOT/'.repro_runs'/'clean_env'
SCRIPTS=['audit_olist.py','run_project.py','deep_audit.py','review_timing_study.py','build_review_timing_report.py']

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    OUT.mkdir(exist_ok=True)
    (OUT/'history').mkdir(exist_ok=True)
    backup=OUT/'history'/'README_before_delivery.md'
    if not backup.exists():shutil.copy2(ROOT/'README.md',backup)
    manifest_path=OUT/'historical_manifest.json'
    files=[*ROOT.glob('*.csv'),*(ROOT/n for n in SCRIPTS),ROOT/'audit_results.json',ROOT/'data_quality_review.md',ROOT/'requirements.txt']
    files += [p for name in ['project','deep_study','review_timing_study'] for p in (ROOT/name).rglob('*') if p.is_file()]
    manifest={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in files if p.exists()}
    if not manifest_path.exists():
        manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    WORK.mkdir(parents=True,exist_ok=True)
    (WORK/'input_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    for path in [*ROOT.glob('*.csv'),*(ROOT/n for n in SCRIPTS)]:
        destination=WORK/path.name
        if not destination.exists():shutil.copy2(path,destination)
        assert sha(path)==sha(destination),path.name
    env=WORK/'.venv'
    if not (env/'pyvenv.cfg').exists():venv.EnvBuilder(with_pip=True,system_site_packages=False).create(env)
    assert len(list(WORK.glob('*.csv')))==9,'Exactly nine source CSVs required'
    info={'workspace':str(WORK.relative_to(ROOT)).replace('\\','/'),'source_copy_count':len(list(WORK.glob('*.csv'))),'scripts_copied':SCRIPTS,'host_python':sys.version,'venv_system_site_packages':False}
    (OUT/'workspace_preparation.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    print(json.dumps(info,indent=2))

if __name__=='__main__':main()
