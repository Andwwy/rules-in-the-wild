"""Reproduce backend restrictions without generating labels or changing the app."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog import EXAMPLES, spec
from guardrail import evaluate, repository_artifact, validate_spec
from server import bundle
import io,zipfile

results=[]
def record(name, observed, interpretation):
    results.append({'case':name,'observed':observed,'interpretation':interpretation})
def check_validation(s):
    try: validate_spec(s); return {'accepted':True}
    except Exception as e:return {'accepted':False,'error':str(e)[:400]}

# A simple required glob is existential; it does not establish an obligation per service.
s=spec('path_manifest','Every service under services/ has a Dockerfile',['**'],{'required':['services/*/Dockerfile'],'forbidden':[]})
a={'files':{'services/api/Dockerfile':'','services/web/package.json':'{}'}}
r=evaluate(s,a)
assert r['status']=='pass'
record('path_glob_is_not_per_service',r,'This tempting approximation passes with a missing web Dockerfile. A generated per-service predicate is needed; it is not evidence that Codex actually chose this approximation.')
with tempfile.TemporaryDirectory() as d:
    root=Path(d);(root/'docs').mkdir()
    s=spec('path_manifest','docs directory must exist',['**'],{'required':['docs'],'forbidden':[]})
    a=repository_artifact(root,s,None);r=evaluate(s,a)
    assert r['status']=='fail' and not a['files']
    record('path_directory_inventory',{'artifact':a,'result':r},'Repository collection records files only and skips symlinks. Directory existence/type rules cannot be faithfully checked with this contract.')

# The regex is native, but our always-search + MULTILINE setting needs explicit semantics.
s=spec('regex','The supplied value contains only lowercase letters',['**/*.txt'],{'pattern':'^[a-z]+$','mode':'require','ignore_case':False})
r=evaluate(s,{'files':{'value.txt':'valid\nINVALID'}})
assert r['status']=='pass'
record('regex_search_is_not_fullmatch',r,'A line-anchored pattern passes on one good line under MULTILINE search. A strict entire-value check needs fullmatch or absolute anchors; the engine can express it, but the interface does not make that distinction explicit.')
s['scope']=None
record('regex_unbound_predicate',check_validation(s),'The same deployment-scope blocker fixed for JSON Schema remains for regex. A reusable text predicate should not require repository paths.')

# Native JSON Schema conditionals and mutually exclusive properties are already supported.
s=spec('json_schema','Exactly one removal method',['**/*.json'],{'schema':{'type':'object','oneOf':[{'required':['indices'],'not':{'required':['scoreThreshold']}},{'required':['scoreThreshold'],'not':{'required':['indices']}}]}})
s['scope']=None
r=[evaluate(s,{'document':v})['status'] for v in [{'indices':[]},{'scoreThreshold':0.5},{'indices':[],'scoreThreshold':0.5},{}]]
assert r==['pass','pass','fail','fail']
record('json_schema_native_oneof',r,'Native JSON Schema supports the conditional predicate without custom policy fields. No backend replacement is needed.')

# Actual Semgrep rules rejected by our top-level allowlist.
base=copy.deepcopy(EXAMPLES[4]['spec'])
with_paths=copy.deepcopy(base);with_paths['config']['rules'][0]['paths']={'include':['src/**']}
record('semgrep_native_paths_rejected',check_validation(with_paths),'Native per-rule paths are rejected by our wrapper, although global wrapper scope is not a replacement for different scope per rule.')
taint=copy.deepcopy(base);taint['config']['rules']=[{'id':'source-to-sink','message':'Unsanitized flow','languages':['python'],'severity':'ERROR','mode':'taint','pattern-sources':[{'pattern':'source(...)'}],'pattern-sinks':[{'pattern':'sink(...)'}],'pattern-sanitizers':[{'pattern':'sanitize(...)'}]}]
record('semgrep_native_taint_rejected',check_validation(taint),'Our wrapper rejects native taint rules even when sources, sinks, and sanitizer are supplied.')
for name,s,files in [
 ('semgrep_native_paths_engine',with_paths,{'src/main.py':'eval("x")\n','tests/test_main.py':'eval("x")\n'}),
 ('semgrep_native_taint_engine',taint,{'src/main.py':'x = source()\nsink(x)\ny = sanitize(source())\nsink(y)\n'})]:
    with tempfile.TemporaryDirectory() as d:
        root=Path(d)
        for path,content in files.items():
            dest=root/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(content)
        config=root/'rules.json';config.write_text(json.dumps({'rules':s['config']['rules']}))
        run=subprocess.run(['semgrep','scan','--config',str(config),'--json','--metrics=off','--disable-nosem','--no-git-ignore',str(root)],capture_output=True,text=True,timeout=40)
        if run.returncode:raise RuntimeError(run.stderr[-1800:])
        native=json.loads(run.stdout)
        assert not native.get('errors'),native.get('errors')
        assert len(native['results'])==1,native
        record(name,{'findings':len(native['results']),'paths':[x['path'].replace(str(root),'<fixture>') for x in native['results']]},'The installed Semgrep engine handles this rule. The blocker is our custom wrapper, not this native capability.')

for example in [EXAMPLES[0],EXAMPLES[1],EXAMPLES[2],EXAMPLES[4]]:
    with zipfile.ZipFile(io.BytesIO(bundle(example['spec']))) as z:
        names=z.namelist()
    record('bundle_'+example['spec']['generator'],names,'Bundle contains a runnable checker but no hook installer or native schema/rules file; enforcement integration is still manual.')

out=Path(__file__).with_name('backend-probes.json');out.write_text(json.dumps(results,indent=2)+'\n')
for row in results:print(row['case'],json.dumps(row['observed']))
