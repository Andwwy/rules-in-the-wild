"""Generator contracts and explicitly labeled hand-authored examples."""
import json
from pathlib import Path

CATALOG = {
 'regex': {'label': 'pygrep · text / regex', 'description': 'Native pygrep configuration for text patterns and literal constraints. Supports multiple rules and explicit whole-file/per-line matching. No file paths needed for a reusable text predicate.', 'icon': 'Aa'},
 'json_schema': {'label': 'JSON Schema', 'description': 'JSON field presence, types, values, and structured relationships. File paths are optional at generation; a reusable schema can validate a pasted JSON document.', 'icon': '{}'},
 'conftest': {'label': 'Conftest · path inventory', 'description': 'Native Rego policy over a typed path inventory: file/directory/link existence, counts, naming, and requirements for every service or directory. Does not prevent filesystem operations.', 'icon': '▤'},
 'danger': {'label': 'Danger · local Git', 'description': 'Generate a native Dangerfile for Git change policies: changed-file/line limits, protected paths, and conditional changesets. Local staged diff by default; branch comparison for whole-PR rules. No CI or token required.', 'icon': '±'},
 'semgrep': {'label': 'Semgrep', 'description': 'Native Semgrep source rules, with per-rule paths, search operators and supported taint analysis when sources/sinks are established. Missing deployment paths do not block generation.', 'icon': '</>'},
}
# Display copy stays separate from the detailed routing criteria above.
PRESENTATION = {
 'regex': ('Text / regex', 'pygrep', 'https://pre-commit.com/#pygrep', 'Required or forbidden text, literal markers, and regex patterns.'),
 'json_schema': ('Structured data', 'check-jsonschema', 'https://check-jsonschema.readthedocs.io/en/latest/', 'Required fields, types, allowed values, and numeric or string constraints.'),
 'conftest': ('Files & directories', 'Conftest', 'https://www.conftest.dev/', 'Required paths, naming, file types, counts, and per-directory requirements.'),
 'danger': ('Git changes', 'Danger JS', 'https://danger.systems/js/', 'Changed-file and line limits, protected paths, and conditional changesets.'),
 'semgrep': ('Source code', 'Semgrep', 'https://semgrep.dev/docs/', 'Code patterns, forbidden API calls, and supported source-to-sink flows.'),
}
for key, (category, enforcer, docs_url, summary) in PRESENTATION.items():
    CATALOG[key].update(category=category, enforcer=enforcer, docs_url=docs_url, summary=summary)

DEFERRED = {
 'needs_context': 'Required language, scope, schema, exceptions, or semantics are unspecified; do not guess.',
 'deferred': 'Requires runtime permissions, approvals, command interception, action ordering, or workflow integration.',
 'unsupported': 'No supported generator can faithfully cover all obligations; includes unresolved composite rules and subjective properties.'
}


def spec(kind, rule, include, config):
    return {'version':'1.0', 'generator':kind, 'rule':rule, 'description':rule, 'scope':{'include':include,'exclude':[]}, 'config':config}

EXAMPLES = [
 {'id':'literal', 'label':'No TODO markers', 'rule':'Markdown files must not contain the literal TODO (case-sensitive).', 'context':'Applies to every .md file, at any depth, with no exceptions.',
  'spec':spec('regex','Markdown files must not contain the literal TODO (case-sensitive).',['**/*.md'],{'pattern':'TODO','mode':'forbid','ignore_case':False}),
  'pass':{'files':{'README.md':'# Ready\nAll done.'}}, 'fail':{'files':{'docs/notes.md':'TODO: finish this.'}}},
 {'id':'schema', 'label':'A typed config', 'rule':'config.json must contain a boolean debug field and a positive integer port no greater than 65535. Additional fields are allowed.', 'context':'The file is at the repository root. This checks content when the file is present; file existence is not required.',
  'spec':spec('json_schema','config.json must contain a boolean debug field and an integer port from 1 through 65535.',['config.json'],{'schema':{'type':'object','required':['debug','port'],'properties':{'debug':{'type':'boolean'},'port':{'type':'integer','minimum':1,'maximum':65535}}}}),
  'pass':{'files':{'config.json':'{"debug":false,"port":8080}'}}, 'fail':{'files':{'config.json':'{"debug":"false","port":0}'}}},
 {'id':'paths', 'label':'Required project files', 'rule':'The repository must contain README.md and LICENSE at its root.', 'context':'Both must be files, not directories.',
  'spec':spec('path_manifest','The repository must contain README.md and LICENSE at its root.',['**'],{'required':['README.md','LICENSE'],'forbidden':[]}),
  'pass':{'files':{'README.md':'# Project','LICENSE':'MIT'}}, 'fail':{'files':{'README.md':'# Project'}}},
 {'id':'diff', 'label':'Protect migrations', 'rule':'Do not modify, add, or delete any files under migrations/.', 'context':'Check tracked changes relative to HEAD through the working tree; untracked files are outside this diff contract. Compare all changed paths.',
  'spec':spec('git_diff','No tracked changes under migrations/.',['**'],{'allowed_paths':[],'forbidden_paths':['migrations/**'],'forbid_deletions':False}),
  'pass':{'changes':[{'path':'src/app.py','status':'M'}]}, 'fail':{'changes':[{'path':'migrations/001.sql','status':'D'}]}},
 {'id':'semgrep', 'label':'No Python eval calls', 'rule':'Python source files must not call the built-in eval function directly.', 'context':'All .py files. Match direct eval(...) syntax, not aliases or dynamically resolved calls; no path exceptions.',
  'spec':spec('semgrep','No direct eval(...) calls in Python source files.',['**/*.py'],{'rules':[{'id':'no-direct-eval','message':'Direct eval calls are forbidden','severity':'ERROR','languages':['python'],'pattern':'eval(...)'}]}),
  'pass':{'files':{'main.py':'value = int("3")\n'}}, 'fail':{'files':{'main.py':'value = eval("3 + 4")\n'}}}
]


LEGACY_DIFF_EXAMPLE = EXAMPLES[3]

def danger_spec(rule, source, mode='staged', base='HEAD'):
    return {'version':'1.0','generator':'danger','rule':rule,'description':rule,'scope':None,
            'config':{'dangerfile':source,'mode':mode,'base':base}}

EXAMPLES[3] = {
 'id':'diff','label':'Limit changed files','rule':'Total changed files <= 2.',
 'context':'Apply to the staged changes about to be committed. Count added, modified, and deleted paths once each.',
 'spec':danger_spec('Total changed files <= 2.', 'const { danger, fail } = require("danger");\nconst changed = new Set([...danger.git.created_files, ...danger.git.modified_files, ...danger.git.deleted_files]);\nif (changed.size > 2) fail(`Changed ${changed.size} files; maximum is 2.`);\n'),
 'pass':{'git':{'created_files':['src/a.ts'],'modified_files':['src/b.ts'],'deleted_files':[]}},
 'fail':{'git':{'created_files':['src/a.ts','src/b.ts','src/c.ts'],'modified_files':[],'deleted_files':[]}}
}


LEGACY_PATH_EXAMPLE = EXAMPLES[2]
EXAMPLES[0]['spec']={'version':'1.0','generator':'regex','rule':EXAMPLES[0]['rule'],'description':EXAMPLES[0]['rule'],'scope':None,
 'config':{'pygrep':{'repos':[{'repo':'local','hooks':[{'id':'no-todo','name':'No TODO markers','language':'pygrep','entry':'TODO','types':['text'],'files':r'\.md$'}]}]}}}
EXAMPLES[2]={'id':'paths','label':'Dockerfile per service','rule':'Every service under services/ must have a Dockerfile.',
 'context':'Services are the immediate child directories of services/. Dockerfile must be a regular file directly inside each service directory.',
 'spec':{'version':'1.0','generator':'conftest','rule':'Every service under services/ must have a Dockerfile.','description':'Each immediate service directory has a Dockerfile.','scope':None,
 'config':{'policy':'''package main

has_dockerfile(directory) if {
  some entry in input.entries
  entry.path == concat("/", [directory, "Dockerfile"])
  entry.kind == "file"
}

deny contains msg if {
  some entry in input.entries
  entry.kind == "directory"
  parts := split(entry.path, "/")
  count(parts) == 2
  parts[0] == "services"
  not has_dockerfile(entry.path)
  msg := sprintf("Missing Dockerfile in %s", [entry.path])
}
'''}},
 'pass':{'entries':[{'path':'services','kind':'directory'},{'path':'services/api','kind':'directory'},{'path':'services/api/Dockerfile','kind':'file'},{'path':'services/web','kind':'directory'},{'path':'services/web/Dockerfile','kind':'file'}]},
 'fail':{'entries':[{'path':'services','kind':'directory'},{'path':'services/api','kind':'directory'},{'path':'services/api/Dockerfile','kind':'file'},{'path':'services/web','kind':'directory'}]}}


def build_schema():
    string={'type':'string','minLength':1,'maxLength':20000}
    strings={'type':'array','items':string,'maxItems':50}
    def obj(properties): return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
    schema=obj({'version':{'const':'1.0'},'generator':{'enum':list(CATALOG)+['git_diff','path_manifest']},'rule':string,'description':string,
        'scope':{'anyOf':[obj({'include':dict(strings,minItems=1),'exclude':strings}),{'type':'null'}]}, 'config':{'type':'object'}})
    configs={
        'regex':{'anyOf':[obj({'pygrep':{'type':'object'}}),obj({'pattern':string,'mode':{'enum':['require','forbid']},'ignore_case':{'type':'boolean'}})]},
        'conftest':obj({'policy':{'type':'string','minLength':1,'maxLength':60000}}),
        'json_schema':obj({'schema':{'type':['object','boolean']}}),
        'path_manifest':obj({'required':strings,'forbidden':strings}),
        'git_diff':obj({'allowed_paths':strings,'forbidden_paths':strings,'forbid_deletions':{'type':'boolean'}}),
        'danger':obj({'dangerfile':{'type':'string','minLength':1,'maxLength':60000},'mode':{'enum':['staged','branch']},'base':{'type':'string','minLength':1,'maxLength':200,'pattern':'^[^-]'}}),
        'semgrep':obj({'rules':{'type':'array','minItems':1,'maxItems':10,'items':{'type':'object'}}})}
    configs['git_diff']['properties'].update({
        'base': {'type':'string','minLength':1,'pattern':'^[^-]'},
        'include_untracked': {'type':'boolean'},
        'forbidden_changes': {'type':'array','maxItems':50,'items':obj({'paths':dict(strings,minItems=1),'statuses':{'type':'array','minItems':1,'uniqueItems':True,'items':{'enum':['A','M','D','T']}}})}
    })
    schema['allOf']=[{'if':{'properties':{'generator':{'const':k}}},'then':{'properties':{'config':v}}} for k,v in configs.items()]
    schema['allOf'].append({'if':{'properties':{'generator':{'not':{'enum':['json_schema','danger','regex','semgrep','conftest']}}}},'then':{'properties':{'scope':{'type':'object'}}}})
    schema['$schema']='https://json-schema.org/draft/2020-12/schema'
    return schema

if __name__=='__main__':
    Path(__file__).with_name('spec.schema.json').write_text(json.dumps(build_schema(),indent=2)+'\n')
