"""One real Codex generation request followed by deterministic fixture tests."""
import json
from pathlib import Path
import urllib.request
base='http://127.0.0.1:8787'
with urllib.request.urlopen(base+'/api/config') as r: config=json.load(r)
assert config['generator']=='codex'
def post(endpoint, body):
    req=urllib.request.Request(base+'/api/'+endpoint,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Studio-Token':config['token']})
    try:
        with urllib.request.urlopen(req,timeout=270) as r:return json.load(r)
    except urllib.error.HTTPError as exc: raise RuntimeError(exc.read().decode()) from None
result=post('generate',{'rule':'Markdown files must not contain the literal TODO (case-sensitive).','context':'Applies to all .md files at every depth with no exceptions.','generator':'regex'})
print(json.dumps(result,indent=2),flush=True)
assert result['status']=='generated'
for expected, artifact in [('pass',{'files':{'README.md':'# Complete'}}),('fail',{'files':{'docs/note.md':'TODO: finish'}})]:
    checked=post('test',{'spec':result['spec'],'artifact':artifact})
    print(expected,checked,flush=True)
    assert checked['status']==expected
Path(__file__).resolve().parents[1].joinpath('data','generation-smoke.json').write_text(json.dumps(result,indent=2))
