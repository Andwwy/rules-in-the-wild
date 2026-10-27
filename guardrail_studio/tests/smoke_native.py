"""Live native generation and independent behavioral fixtures; no hooks installed."""
import argparse
import json
from pathlib import Path
import urllib.request
import urllib.error
parser=argparse.ArgumentParser();parser.add_argument('--only',nargs='*');args=parser.parse_args()
BASE='http://127.0.0.1:8787'
with urllib.request.urlopen(BASE+'/api/config') as r:config=json.load(r)
def post(endpoint,body):
    request=urllib.request.Request(BASE+'/api/'+endpoint,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Studio-Token':config['token']})
    try:
        with urllib.request.urlopen(request,timeout=270) as response:return json.load(response)
    except urllib.error.HTTPError as exc:raise RuntimeError(exc.read().decode()) from None
cases=[
('regex','The supplied value must consist only of lowercase ASCII letters.','Validate the entire supplied text value, not one matching line. No whitespace, digits, punctuation, or trailing newline are allowed. Empty values are not allowed.',[
 ({'text':'abc'},'pass'),({'text':'abc\nINVALID'},'fail'),({'text':'abc\n'},'fail'),({'text':''},'fail')]),
('conftest','Every service under services/ must have a Dockerfile.','Services are immediate child directories of services/. Each Dockerfile must be a regular file directly inside its service directory.',[
 ({'entries':[{'path':'services','kind':'directory'},{'path':'services/a','kind':'directory'},{'path':'services/a/Dockerfile','kind':'file'},{'path':'services/b','kind':'directory'}]},'fail'),
 ({'entries':[{'path':'services','kind':'directory'},{'path':'services/a','kind':'directory'},{'path':'services/a/Dockerfile','kind':'file'},{'path':'services/b','kind':'directory'},{'path':'services/b/Dockerfile','kind':'file'}]},'pass')]),
('semgrep','Python code under src/ must not pass a value from source() to sink() unless sanitize() is applied first.','source(), sink(), and sanitize() are the exact API names. Exclude tests/; check intraprocedural dataflow with the community engine. Do not require cross-file analysis.',[
 ({'files':{'src/a.py':'x = source()\nsink(x)\n'}},'fail'),
 ({'files':{'src/a.py':'x = sanitize(source())\nsink(x)\n','tests/test_a.py':'sink(source())\n'}},'pass')]),
('json_schema','Required fields: `name`, `description`, `steps[]`.','Selected clause from: ### Run Mode (with pipeline name)\n1. Validate pipeline exists: workflows/{name}.yaml\n2. Load and validate YAML structure:\n- Required fields: name, description, steps[]\n- Each step has either skill: or prompt: (not both)\n- Referenced skills exist in .claude/skills/\nOnly translate the selected required-fields clause.',[
 ({'files':{'workflows/demo.yaml':'name: 3\ndescription: null\nsteps: []\nextra: true\n'}},'pass'),
 ({'files':{'workflows/demo.yaml':'name: demo\nsteps: []\n'}},'fail'),
 ({'files':{'records.jsonl':'{"name":"a","description":"b","steps":[]}\n{"name":"c","description":"d","steps":"wrong"}\n'}},'fail')])]
for kind,rule,context,fixtures in cases:
    if args.only and kind not in args.only:continue
    route=post('route',{'rule':rule,'context':context});print(kind,'routed:',route['generator'],flush=True);assert route['generator']==kind,route
    result=post('generate',{'rule':rule,'context':context,'generator':kind})
    print(kind,'generation:',json.dumps(result),flush=True);assert result['status']=='generated',result
    restored=post('source',{'spec':result['spec'],'content':result['artifact']['content']})
    assert restored['spec']==result['spec']
    for fixture,expected in fixtures:
        checked=post('test',{'spec':result['spec'],'artifact':fixture})
        print(kind,expected,checked,flush=True);assert checked['status']==expected,checked
    # Also exercise the generated model fixtures, without treating them as independent evidence.
    for label in ['pass','fail']:
        checked=post('test',{'spec':result['spec'],'artifact':result[label]})
        assert checked['status']==label,(label,checked)
    out=Path(__file__).resolve().parents[1]/'data'/('native-'+kind+'-smoke.json');out.write_text(json.dumps(result,indent=2))
