import json
import urllib.request
import urllib.error
from pathlib import Path
base='http://127.0.0.1:8787'
with urllib.request.urlopen(base+'/api/config') as r: token=json.load(r)['token']
def post(endpoint,body):
    request=urllib.request.Request(base+'/api/'+endpoint,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Studio-Token':token})
    try:
        with urllib.request.urlopen(request,timeout=270) as r: return json.load(r)
    except urllib.error.HTTPError as e:raise RuntimeError(e.read().decode()) from None
result=post('generate',{'rule':'Do not create or modify GitHub Actions workflows.','context':'','generator':'danger'})
print(json.dumps(result,indent=2),flush=True)
assert result['status']=='generated'
for status in ['A','M','T','D']:
    checked=post('test',{'spec':result['spec'],'artifact':{'git':{'created_files':['.github/workflows/ci.yml'] if status=='A' else [],'modified_files':['.github/workflows/ci.yml'] if status in ('M','T') else [],'deleted_files':['.github/workflows/ci.yml'] if status=='D' else []}}})
    print(status,checked,flush=True)
    assert checked['status']==('pass' if status=='D' else 'fail')
assert post('test',{'spec':result['spec'],'artifact':{'git':{'created_files':[],'modified_files':[],'deleted_files':[]}}})['status']=='pass'
Path(__file__).resolve().parents[1].joinpath('data','workflow-generation-smoke.json').write_text(json.dumps(result,indent=2))
