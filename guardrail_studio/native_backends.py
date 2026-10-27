"""Generate, validate, execute and export native checker artifacts."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import yaml

HERE=Path(__file__).resolve().parent

GUIDES={
'regex':'''Target the canonical pre-commit pygrep language. Generate config={"pygrep": <native pre-commit configuration object>}, scope:null. The configuration is repos:[{repo:"local",hooks:[{id:"rule-id",name:"Check name",language:"pygrep",entry:"<Python bytes-regex>",types:["text"],args:[],files:"<optional path regex>",exclude:"<optional path regex>"}]}]. Generate one or more native pygrep hooks for independent predicates. Every hook must be repo:local and language:pygrep; do not invent a custom Python checker or remote dependency. Missing file scope is not a generation blocker: omit files to operate on the explicitly supplied text/files. File scope belongs in native files/exclude regexes, not wrapper globs.
pygrep reports a violation on a match. args:[--negate] instead requires at least one match per file, NOT every line. Default mode scans each line as bytes (includes the line terminator), without MULTILINE/DOTALL. args:[--multiline] searches the whole file with MULTILINE and DOTALL; --ignore-case is optional. To validate a whole value use --multiline, --negate and absolute anchors \\A...\\Z; decide whether terminal newlines are allowed from the rule/context. To require a property on EVERY line, forbid an invalid line via a suitable regex; --negate alone is not an every-line requirement. Avoid Unicode-only regex semantics unsupported by bytes matching; choose Semgrep/JSON Schema/needs_context rather than claim them. Distinguish literals from regexes. Preserve case sensitivity and all obligations.
Return fixtures as {"text":"..."} for a reusable text/value predicate, or {"files":{"relative/name.ext":"contents"}} when filenames/scope matter. For text-only fixtures the test filename is input.txt; this is an application input, not scope inferred from the source. No PDF extraction is supplied by pygrep. Export is a standard regex-check.yaml, manually runnable with pre-commit run --config regex-check.yaml --all-files; no hook installation required.''',
'conftest':'''Target native Conftest/OPA Rego v1 for a path inventory. Generate scope:null, config={"policy":"<complete Rego source>"}. Start with package main and use deny contains msg if {...} rules, plus helper rules/functions as necessary. Do NOT emit a required/forbidden-globs JSON policy or custom Python enforcement code. Conftest implements count, every, comprehensions, predicates, regex.match/glob.match and cross-entry relationships. If you use every with an intermediate collection use every entry in collection {...}. No input adapter needs to be invented.
Input contract: {"entries":[{"path":"services/api","kind":"directory"},{"path":"services/api/Dockerfile","kind":"file"},{"path":"link","kind":"symlink","target":"relative/link-target"}]}. Paths are normalized POSIX relative to the inventory root; omit the root itself and .git. Kinds are file,directory,symlink,other. Inventory collection does not follow symlinks or read file contents. It does not infer services: if services are defined as immediate directories under services/, quantify over those DIRECTORY entries, and check a separate matching Dockerfile FILE for each one. Do not mistake one glob match for coverage of every directory. A symlink is not automatically a regular file. Rules about counts, naming, existence, required per-directory files and link metadata are expressible. Do not fabricate a service-directory definition if no context establishes it. Generating an unbound policy with an explicit input contract is allowed.
Use only input.entries and standard pure Rego functions. Do not use http.send, net.lookup_ip_addr, opa.runtime, parse_config_file, parse_combined_config_files, external data or file reads. Declare helper rules under package main. Emit deny failures for violations; warn alone does not enforce a rule. Filesystem permissions, action prevention and transient state remain outside this target.
Passing/failing artifact JSON must be the manifest directly ({"entries":[...]}). Export policy.rego and use conftest test inventory.json --policy policy.rego --rego-version v1 --strict --show-builtin-errors. A supplied manifest.py only collects metadata; it contains no rule predicate.''',
'semgrep':'''Generate a native Semgrep rules document as config={"rules":[<native rule objects>]}, scope:null. Use per-rule paths.include/exclude for actual file scope. Do NOT use the former wrapper allowlist or claim paths, options, metadata or taint modes are unsupported. Supported search rules may use any native operators, nested patterns, metavariable filters and path conditions. Native taint rules may use mode:taint, pattern-sources, pattern-sinks, pattern-sanitizers, propagators, etc. Only use taint mode when sources/sinks/semantics are established in rule/context; do not invent them. Respect the installed community engine, not unverified proprietary/interfile guarantees. Do not select a new tool merely because mentioned. Do not emit actions, network validators, autofixes or supply-chain/secrets dependencies; these need a separate interface. All generated rules are compiled/scanned by the actual Semgrep engine.
File scope is optional during generation: the eventual invocation chooses targets, while explicit rule-specific scope goes in native paths. Missing language or essential syntactic/semantic definitions can still need context. Include native fields id,message,languages,severity and valid engine-supported rule bodies. Export is semgrep.yml, runnable by semgrep scan --config semgrep.yml --error --strict --metrics=off TARGET.
Fixtures must be {"files":{"relative/path.py":"source text"}} with correct extensions and scope. Passing fixtures must contain applicable source, not an empty or irrelevant file. This backend is static analysis of artifacts, not prevention of a live action.''',
'json_schema':'''Generate a native Draft 2020-12 JSON Schema in config.schema. The visible/exported artifact is schema.json, not a custom policy JSON. Scope may be null: missing input file paths never block generation. Unspecified property types remain unconstrained; do not infer nonempty strings or forbid additional properties unless the rule requires them. For name,description,steps[] require those keys and array-valued steps only. Conditional, oneOf, dependentRequired and other standard JSON Schema features are available. A referenced authoritative schema not supplied still needs context; do not hallucinate it. Only internal $ref/$dynamicRef are available until referenced schemas are explicitly bundled.
Input parsing is separate: check-jsonschema validates JSON/YAML instances; JSONL is parsed record by record then each record is validated against the SAME native schema. Do not invent JSON source when context establishes YAML, or refuse just because YAML is mentioned. Schema constraints validate parsed data, not YAML lexical style, duplicate keys, source quotes or workflow/runtime behavior. Fixtures may be {"document":<JSON value>} or {"files":{"workflow.yaml":"YAML text"}} / {"files":{"records.jsonl":"JSONL text"}} according to the rule. Use raw document fixtures when no source format is required. Standalone invocation: check-jsonschema --schemafile schema.json instance.json instance.yaml.'''
}


def yaml_dump(value): return yaml.safe_dump(value,sort_keys=False,allow_unicode=True)


def pygrep_config(spec):
    c=spec['config']
    if 'pygrep' in c:return c['pygrep']
    # Compatibility for old saved literal validators; new outputs are native configs.
    args=['--multiline']
    if c['mode']=='require':args.append('--negate')
    if c['ignore_case']:args.append('--ignore-case')
    hook={'id':'guardrail','name':spec['description'],'language':'pygrep','entry':c['pattern'],'types':['text'],'args':args}
    return {'repos':[{'repo':'local','hooks':[hook]}]}


def validate_native(spec):
    kind,c=spec['generator'],spec['config']
    if kind=='regex' and 'pygrep' in c:
        document=c['pygrep']
        if not isinstance(document,dict) or not isinstance(document.get('repos'),list) or not document['repos']:
            raise ValueError('A native pygrep configuration must contain local repos/hooks')
        for repo in document['repos']:
            if repo.get('repo')!='local' or not repo.get('hooks'):raise ValueError('Only local pygrep hooks are supported')
            for hook in repo['hooks']:
                if hook.get('pass_filenames') is False:raise ValueError('pygrep checks must receive their selected files')
                if hook.get('language')!='pygrep':raise ValueError('Regex output must use native language: pygrep')
                if not isinstance(hook.get('entry'),str):raise ValueError('pygrep entry must be a regex string')
                re.compile(hook['entry'].encode())
                if set(hook.get('args',[]))-{'-i','--ignore-case','--multiline','--negate'}:raise ValueError('Unsupported pygrep argument')
        import cfgv
        from pre_commit.clientlib import CONFIG_SCHEMA
        cfgv.validate(document,CONFIG_SCHEMA)
    elif kind=='conftest':
        if not c['policy'].strip():raise ValueError('A Rego policy is required')
        if not re.search(r'^\s*package\s+main\s*$',c['policy'],re.M):raise ValueError('Conftest policy must use package main')
    elif kind=='semgrep':
        if not c['rules']:raise ValueError('At least one native Semgrep rule is required')
        for rule in c['rules']:
            if not isinstance(rule,dict):raise ValueError('Each Semgrep rule must be an object')
            if {'validators','request','response','fix','fix-regex'} & rule.keys():
                raise ValueError('Active validators/autofix need a separate interface; this checker only scans')
            if rule.get('mode') not in (None,'search','taint'):
                raise ValueError('This interface supports native search and taint rules')


def native_artifact(spec):
    kind,c=spec['generator'],spec['config']
    if kind=='regex' and 'pygrep' in c:
        return {'filename':'regex-check.yaml','content':yaml_dump(c['pygrep']),'command':'pre-commit run --config regex-check.yaml --all-files (no hook installation needed)'}
    if kind=='json_schema':
        return {'filename':'schema.json','content':json.dumps(c['schema'],indent=2)+'\n','command':'check-jsonschema --schemafile schema.json input.json input.yaml'}
    if kind=='semgrep':
        return {'filename':'semgrep.yml','content':yaml_dump({'rules':c['rules']}),'command':'semgrep scan --config semgrep.yml --error --strict --metrics=off TARGET'}
    if kind=='conftest':
        return {'filename':'policy.rego','content':c['policy'],'command':'conftest test inventory.json --policy policy.rego --rego-version v1 --strict --show-builtin-errors'}
    if kind=='danger':
        return {'filename':'dangerfile.js','content':c['dangerfile'],'command':'npm ci --ignore-scripts; npm run check -- --repo /path/to/repo'}
    return {'filename':'guardrail.json','content':json.dumps(spec,indent=2),'command':'python3 guardrail.py --repo /path/to/repo'}


def spec_from_source(spec,source):
    s=copy.deepcopy(spec);kind=s['generator']
    if kind=='regex' and 'pygrep' in s['config']:s['config']['pygrep']=yaml.safe_load(source)
    elif kind=='json_schema':s['config']['schema']=json.loads(source)
    elif kind=='semgrep':
        data=yaml.safe_load(source)
        if not isinstance(data,dict) or set(data)!={'rules'}:raise ValueError('A native Semgrep file must contain a rules list')
        s['config']['rules']=data['rules']
    elif kind=='conftest':s['config']['policy']=source
    elif kind=='danger':s['config']['dangerfile']=source
    else:s=json.loads(source)
    from guardrail import validate_spec
    return validate_spec(s)


def executable(name):
    path=shutil.which(name)
    if not path:raise ValueError(f'{name} is not installed; see the native artifact README')
    return path


def write_files(directory,files):
    from guardrail import safe_path
    if not isinstance(files,dict) or any(not isinstance(c,str) for c in files.values()):raise ValueError('files must map relative filenames to text')
    for p,content in files.items():
        safe_path(p);dest=directory/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(content)


def evaluate_pygrep(spec,artifact):
    from pre_commit.clientlib import load_config
    from pre_commit.commands.run import Classifier
    from types import SimpleNamespace
    files=artifact.get('files',{'input.txt':artifact['text']} if 'text' in artifact else {})
    if not files:return {'status':'not_applicable','checked':0,'violations':[]}
    with tempfile.TemporaryDirectory(prefix='pygrep-check-') as d:
        root=Path(d);write_files(root,files)
        config=root/'regex-check.yaml';config.write_text(yaml_dump(pygrep_config(spec)))
        # Native pre-commit filtering and native pygrep matching; no reimplementation of the predicate.
        document=load_config(str(config))
        previous=Path.cwd();checked=0;violations=[]
        # This runs in the isolated checker subprocess, never in the threaded server.
        os.chdir(root)
        try:
            for repo in document['repos']:
                for hook in repo['hooks']:
                    classifier=Classifier.from_config(files,document['files'],document['exclude'])
                    paths=tuple(classifier.filenames_for_hook(SimpleNamespace(**hook)))
                    checked+=len(paths)
                    if not paths:continue
                    run=subprocess.run([sys.executable,'-m','pre_commit.languages.pygrep',*hook['args'],hook['entry'],*paths],capture_output=True,text=True,timeout=15)
                    if run.returncode not in (0,1):return {'status':'error','message':run.stdout+run.stderr,'engine':'pre-commit pygrep'}
                    if run.returncode:violations.append({'message':hook['name'],'details':run.stdout+run.stderr})
        finally:os.chdir(previous)
    return {'status':'fail' if violations else 'pass' if checked else 'not_applicable','checked':checked,'violations':violations,'engine':'pre-commit pygrep'}


def evaluate_schema(spec,artifact):
    with tempfile.TemporaryDirectory(prefix='schema-check-') as d:
        root=Path(d);schema=root/'schema.json';schema.write_text(json.dumps(spec['config']['schema']))
        if 'document' in artifact:files={'input.json':json.dumps(artifact['document'])}
        else:files=artifact.get('files',{})
        if not files:return {'status':'not_applicable','checked':0,'violations':[]}
        from guardrail import matches
        scope=spec.get('scope')
        if scope and 'document' not in artifact:
            files={p:c for p,c in files.items() if any(matches(p,g) for g in scope['include']) and not any(matches(p,g) for g in scope['exclude'])}
        work=root/'input';work.mkdir();write_files(work,files)
        checked=0;violations=[]
        for path in files:
            if path.lower().endswith(('.jsonl','.ndjson')):
                instances=[]
                for line_no,line in enumerate(files[path].splitlines(),1):
                    if not line.strip():continue
                    try:value=json.loads(line)
                    except ValueError as exc:violations.append({'path':path,'message':f'line {line_no}: invalid JSON: {exc}'});continue
                    instance=root/'record.json';instance.write_text(json.dumps(value));instances.append((line_no,instance.read_text()))
                if not instances:continue
            else:instances=[(None,None)]
            for line_no,content in instances:
                instance=work/path
                if content is not None:instance=root/'record.json';instance.write_text(content)
                run=subprocess.run([executable('check-jsonschema'),'--schemafile',str(schema),'--output-format','json',str(instance)],capture_output=True,text=True,timeout=20)
                checked+=1
                if run.returncode:
                    if run.returncode not in (1,):return {'status':'error','message':run.stdout+run.stderr,'engine':'check-jsonschema'}
                    violations.append({'path':path,**({'line':line_no} if line_no else {}),'message':run.stdout+run.stderr})
        return {'status':'fail' if violations else 'pass' if checked else 'not_applicable','checked':checked,'violations':violations,'engine':'check-jsonschema'}


def validate_manifest(value):
    from guardrail import safe_path
    if not isinstance(value,dict) or not isinstance(value.get('entries'),list):raise ValueError('Path policy input must have an entries array')
    seen=set()
    for e in value['entries']:
        if not isinstance(e,dict):raise ValueError('Each inventory entry must be an object')
        p=safe_path(e.get('path'))
        if p in seen:raise ValueError('Duplicate inventory path: '+p)
        seen.add(p)
        if e.get('kind') not in ('file','directory','symlink','other'):raise ValueError('Unknown entry kind')
        if e['kind']=='symlink' and not isinstance(e.get('target'),str):raise ValueError('Symlinks require a target string')


def evaluate_conftest(spec,artifact):
    validate_manifest(artifact)
    with tempfile.TemporaryDirectory(prefix='path-policy-') as d:
        root=Path(d);policy=root/'policy.rego';policy.write_text(spec['config']['policy'])
        data=root/'inventory.json';data.write_text(json.dumps(artifact))
        command=[executable('conftest'),'test',str(data),'--policy',str(policy),'--rego-version','v1','--output','json','--strict','--show-builtin-errors','--capabilities',str(HERE/'conftest-capabilities.json')]
        run=subprocess.run(command,capture_output=True,text=True,timeout=20)
        try:rows=json.loads(run.stdout)
        except ValueError:return {'status':'error','message':run.stderr+run.stdout,'engine':'Conftest'}
        if run.returncode not in (0,1):return {'status':'error','message':run.stderr+run.stdout,'engine':'Conftest'}
        if sum(row.get('successes',0)+len(row.get('failures',[])) for row in rows)==0:
            return {'status':'error','message':'The policy produced no evaluable deny checks','engine':'Conftest'}
        violations=[{'message':f['msg']} for row in rows for f in row.get('failures',[])]
        exceptions=[x for row in rows for x in row.get('exceptions',[])]
        if exceptions:return {'status':'error','message':'Policy evaluation exceptions: '+json.dumps(exceptions),'engine':'Conftest'}
        return {'status':'fail' if violations else 'pass','checked':1,'violations':violations,'engine':'Conftest'}


def evaluate_semgrep(spec,artifact):
    from guardrail import matches
    files=artifact.get('files',{})
    scope=spec.get('scope')
    if scope:files={p:c for p,c in files.items() if any(matches(p,g) for g in scope['include']) and not any(matches(p,g) for g in scope['exclude'])}
    with tempfile.TemporaryDirectory(prefix='semgrep-native-') as d:
        root=Path(d);source=root/'input';source.mkdir();write_files(source,files)
        config=root/'semgrep.yml';config.write_text(yaml_dump({'rules':spec['config']['rules']}))
        run=subprocess.run([executable('semgrep'),'scan','--config',str(config),'--json','--error','--strict','--metrics=off','--disable-version-check','--disable-nosem','--no-git-ignore',str(source)],capture_output=True,text=True,timeout=35)
        try:data=json.loads(run.stdout)
        except ValueError:return {'status':'error','message':run.stderr+run.stdout,'engine':'Semgrep'}
        if data.get('errors') or run.returncode not in (0,1):return {'status':'error','message':json.dumps(data.get('errors'))+' '+run.stderr[-1200:],'engine':'Semgrep'}
        checked=len(data.get('paths',{}).get('scanned',[]))
        violations=[{'path':str(Path(f['path']).relative_to(source)),'line':f['start']['line'],'message':f['extra']['message']} for f in data.get('results',[])]
        return {'status':'fail' if violations else 'pass' if checked else 'not_applicable','checked':checked,'violations':violations,'engine':'Semgrep'}


def native_bundle(spec):
    import io,zipfile
    artifact=native_artifact(spec);kind=spec['generator']
    memory=io.BytesIO()
    with zipfile.ZipFile(memory,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr(artifact['filename'],artifact['content'])
        if kind=='regex':
            z.writestr('requirements.txt','pre-commit==4.7.0\n')
            readme='''# Native pygrep text check

The rule lives in the standard pre-commit configuration `regex-check.yaml`, using `language: pygrep`. There is no custom Python policy runner.

Install `python3 -m pip install -r requirements.txt`. From the target Git repository run:

```
pre-commit run --config /absolute/path/to/regex-check.yaml --all-files
# Or choose input files explicitly:
pre-commit run --config /absolute/path/to/regex-check.yaml --files path/to/file.txt
```

No `pre-commit install` or hook installation is required. Exit 1 reports violations; other nonzero codes indicate an execution/configuration problem. Review output for skipped rules: no applicable files is not proof of compliance. Native `files` and `exclude` are regexes over filenames. `--all-files` selects tracked files, while `--files` accepts the chosen filenames; it does not validate a proposed staged snapshot automatically.

pygrep uses Python byte regexes. Default mode examines lines; `--multiline` searches a whole file with MULTILINE and DOTALL. `--negate` requires at least one match per file, not a match on every line. Whole-value checks should use absolute anchors, and per-line constraints should explicitly forbid invalid lines. It does not extract PDF text or parse structured fields.
'''
        elif kind=='json_schema':
            z.writestr('requirements.txt','check-jsonschema==0.38.0\n')
            z.write(HERE/'check_jsonl.py','check_jsonl.py')
            readme='''# Native JSON Schema

`schema.json` is a standard Draft 2020-12 schema. Use it with check-jsonschema or another compatible validator. The schema is reusable and is not bound to repository paths.

```
python3 -m pip install -r requirements.txt
check-jsonschema --schemafile schema.json input.json input.yaml
# JSONL: split input into records, then use the same native validator per record:
python3 check_jsonl.py --schemafile schema.json records.jsonl
```

YAML is parsed before schema validation; YAML quoting/style is not a schema property. check_jsonl.py is an input adapter only: it contains no generated rule predicates. Invalid or empty JSONL input does not report a successful check. Only internal schema references are currently supported; supply referenced contracts before generating a self-contained schema. Format checks depend on the validator's supported formats. Extra fields/types are constrained only if the source rule establishes that obligation.
'''
        elif kind=='semgrep':
            z.writestr('requirements.txt','semgrep==1.182.1\n')
            readme='''# Native Semgrep rules

`semgrep.yml` is a standard native rule file. It supports search operators, per-rule paths, metadata/options, and community-engine-supported taint rules. The installed engine validates the configuration; there is no custom required/forbidden-policy vocabulary.

```
python3 -m pip install -r requirements.txt
semgrep scan --config /absolute/path/to/semgrep.yml --error --strict --metrics=off --disable-version-check --disable-nosem TARGET
```

Exit 1 reports findings; parse/configuration/scan errors must not be treated as passes. Check the scan summary for skipped or nonapplicable files. The Studio uses the community engine; do not assume proprietary or cross-file capabilities. Active network validators, autofixes and dependency/secrets rules require a separate interface. This checks artifacts, not live file writes.
'''
        elif kind=='conftest':
            z.write(HERE/'manifest.py','manifest.py')
            z.write(HERE/'conftest-capabilities.json','capabilities.json')
            z.writestr('inventory.schema.json',json.dumps({'type':'object','required':['entries'],'properties':{'entries':{'type':'array','items':{'type':'object','required':['path','kind'],'properties':{'path':{'type':'string','minLength':1},'kind':{'enum':['file','directory','symlink','other']},'target':{'type':'string'}}}}}},indent=2))
            readme='''# Native Conftest/Rego path policy

`policy.rego` contains the rule as native Rego v1. Conftest evaluates it against a typed filesystem inventory. This can express counts, per-directory requirements, entry types and relationships without custom Python enforcement code.

Install Conftest 0.71.1 (OPA 1.21.1) from its official release or package manager, then run:

```
python3 manifest.py /path/to/repo > inventory.json
conftest test inventory.json --policy policy.rego --rego-version v1 --strict --show-builtin-errors --capabilities capabilities.json
```

You can also supply inventory.json directly. Its contract is documented in inventory.schema.json: entries have normalized repository-relative POSIX paths and kind file/directory/symlink/other; symlinks also have their lexical target. manifest.py only collects metadata. It contains no generated rule predicates, skips .git, reads no file contents, and never follows symlinks. The input root is selected by you. Policies must establish how to identify services/modules from those entries, rather than guess.

Capabilities are derived from the official OPA 1.21.1 capabilities and exclude HTTP, DNS lookup and runtime-environment access. The generated path policy operates on the supplied inventory, not current actions/history or file contents. Inventory validity/collection failure is not a policy pass. No hook or workflow is installed.
'''
        else:raise ValueError('No native bundle for '+kind)
        z.writestr('README.md',readme+'\nGenerated rules and example fixtures are not human-validated. Review and independently test their semantics before relying on them.\n')
    return memory.getvalue()


def check_definition(spec):
    """Definition validation, not evidence that the rule faithfully captures the source."""
    from guardrail import validate_spec
    validate_spec(spec)
    kind=spec['generator']
    if kind=='semgrep':result=evaluate_semgrep(spec,{'files':{}})
    elif kind=='conftest':result=evaluate_conftest(spec,{'entries':[]})
    else:return {'status':'valid','message':'Native artifact syntax/schema validated; semantics still require testing.'}
    if result['status']=='error':return result
    return {'status':'valid','message':'Compiled by '+result['engine']+'; semantics still require testing.'}
