"""Live Jev/Codex generation followed by independent fixtures and native Danger checks."""
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import bundle
from test_danger_backend import fixture
HERE=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:8787'
with urllib.request.urlopen(BASE+'/api/config') as r: config=json.load(r)
assert 'danger' in config['catalog'] and 'git_diff' not in config['catalog']
def post(endpoint,body):
    req=urllib.request.Request(BASE+'/api/'+endpoint,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Studio-Token':config['token']})
    try:
        with urllib.request.urlopen(req,timeout=270) as r:return json.load(r)
    except urllib.error.HTTPError as exc:raise RuntimeError(exc.read().decode()) from None
cases=[
 ('count','Total changed files <= 2.','',[
  (fixture(modified=['a','b']),'pass'),(fixture(created=['a'],modified=['b'],deleted=['c']),'fail')]),
 ('changeset','If your diff touches packages/pixi-reels/src/** or packages/pixi-reels/package.json, you MUST add a .changeset/*.md file in the same PR.','',[
  (fixture(modified=['packages/pixi-reels/src/a.ts']),'fail'),
  (fixture(modified=['packages/pixi-reels/src/a.ts','.changeset/old.md']),'fail'),
  (fixture(created=['.changeset/new.md'],modified=['packages/pixi-reels/src/a.ts']),'pass'),
  (fixture(modified=['README.md']),'pass')]),
 ('lines','Total changed lines <= 30 (logic code only).','For this check, logic code means every changed line, including comments and blank lines, in src/**/*.ts. Exclude all other paths. Count added plus deleted lines in the staged diff.',[
  (fixture(created=['src/a.ts'],diffs={'src/a.ts':{'before':'','after':'x\n'*30}}),'pass'),
  (fixture(created=['src/a.ts'],diffs={'src/a.ts':{'before':'','after':'x\n'*31}}),'fail'),
  (fixture(created=['docs/a.md'],diffs={'docs/a.md':{'before':'','after':'x\n'*40}}),'pass')])]
for name,rule,context,fixtures in cases:
    routed=post('route',{'rule':rule,'context':context})
    print(name,'route',routed['generator'],flush=True)
    assert routed['generator']=='danger',routed
    generated=post('generate',{'rule':rule,'context':context,'generator':'danger'})
    print(name,'generation',json.dumps(generated),flush=True)
    assert generated['status']=='generated',generated
    for artifact,expected in fixtures:
        checked=post('test',{'spec':generated['spec'],'artifact':artifact})
        print(name,expected,checked,flush=True)
        assert checked['status']==expected,checked
    (HERE/'data'/('danger-'+name+'-smoke.json')).write_text(json.dumps(generated,indent=2))
    if name=='count':
        # Confirm the generated source really works in the native Danger runtime too.
        with tempfile.TemporaryDirectory(prefix='generated-danger-') as directory:
            root=Path(directory)
            for args in [('init','-b','main'),('config','user.name','Test'),('config','user.email','test@example.invalid'),('commit','--allow-empty','-m','baseline')]:
                subprocess.run(['git','-C',str(root),*args],capture_output=True,check=True)
            out=root/'.guardrails/rule';out.mkdir(parents=True)
            with zipfile.ZipFile(io.BytesIO(bundle(generated['spec']))) as z:z.extractall(out)
            (out/'node_modules').symlink_to(HERE/'node_modules',target_is_directory=True)
            for name in ['a','b','c']:(root/name).write_text('x\n')
            subprocess.run(['git','-C',str(root),'add','a','b','c'],check=True)
            result=subprocess.run(['node',str(out/'run-local.js'),'--repo',str(root)],capture_output=True,text=True,timeout=60)
            print('Native generated check:',result.returncode,result.stdout,result.stderr,flush=True)
            assert result.returncode!=0 and '3' in result.stdout+result.stderr
