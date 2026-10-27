"""Native Dangerfile output with offline, capability-free JavaScript fixture tests."""
import difflib
import json
from pathlib import Path

DANGER_VERSION = '14.1.0'

API_GUIDE = '''Generate a native CommonJS dangerfile.js, starting with const { danger, fail, warn, schedule } = require("danger");
Write the rule as JavaScript using the Danger API, NOT the legacy git_diff configuration. Arbitrary predicates over local Git paths, file counts, changed lines, and conditional required additions are supported.
The real API provides danger.git.created_files, modified_files, deleted_files (arrays of repository-relative paths). Union these for all changed files; do not count duplicates. For forbidden creation/modification use created_files + modified_files, allowing deletion if the rule does. For a condition triggered by ANY change, include all three arrays. fileMatch is unnecessary: ordinary string/regex predicates work without extra libraries. To require a NEW changeset use created_files, not modified_files, and require .changeset/<name>.md (not an arbitrary nested or non-md file).
For changed-line rules use schedule(async () => { ... await danger.git.structuredDiffForFile(path) ... }). It returns {chunks:[{changes:[{type:"add", add:true, content:"+..."}, {type:"del", del:true, content:"-..."}, {type:"normal",normal:true,content:" ..."}]}]} or null. Count add/del entries only, not context or patch headers. Use fail() when required diff evidence is missing; never silently count missing data as zero. Change count means additions+deletions unless the user states otherwise, and state that interpretation. Binary or unparseable files must fail review rather than silently pass a numeric limit.
For plain changed-file-count or conditional path checks, no diff data or async calls are needed. fail(message, file?, line?) records a blocking failure; warn() alone does not enforce a prohibition. All asynchronous checks must be registered with schedule. Do not catch errors and convert them to passes.
Use only require("danger"), the listed Danger fields/functions, and standard JavaScript. No fs, process, network, external packages, subprocesses, filesystem reads, plugins, eval, Function, Date, or randomness. No import/export or TypeScript syntax. You can define reusable functions and arbitrary predicates; this is real code, not a limited policy JSON.
The default integration is LOCAL Git pre-commit: Danger supplies the STAGED diff (index vs HEAD). Generate config.mode="staged" and config.base="HEAD" by default, and explain that unstaged/untracked files are excluded. No PR, CI, hosted repo, token or network is required. For rules explicitly about an entire PR/branch (e.g. "same PR"), generate config.mode="branch" with config.base="main" as an explicit deployment default unless another base is supplied; that compares merge-base(base, HEAD) through committed HEAD, excluding staged/unstaged changes. Do not claim a staged check covers an entire PR, and do not silently reinterpret PR scope as commit scope. The user can select another mode/base in the application controls. A literal commit-count rule with "per commit" applies to staged mode. Renames follow Danger's local Git classification, not a guaranteed D+A normalization. Missing semantic definitions such as "logic code only" STILL need context unless the source specifies paths or line criteria. Do not invent that definition.
Set spec generator="danger", scope=null, config={"dangerfile": "<complete JS source>", "mode":"staged" or "branch", "base":"HEAD" or a base ref}. In the explanation describe the check and any interpretation.
Passing/failing artifact JSON strings must encode {"git":{"created_files":[],"modified_files":[],"deleted_files":[],"diffs":{}}}. Each diff entry maps a changed path to {"before":"old text","after":"new text"}. diffs is optional for path/count/conditional checks but required for every inspected path in line-count checks. The Studio offline tester derives structured hunks from these texts. Fixtures represent one staged/branch diff, not filesystem snapshots. Do not refer to PR metadata in generated code. Neighboring context rules are not additional obligations of the selected clause.
'''


def _validate_path(path):
    if not isinstance(path, str) or not path or path.startswith('/') or '\\' in path or '\x00' in path or any(p in ('', '.', '..') for p in path.split('/')):
        raise ValueError('Git file paths must be normalized repository-relative POSIX paths')
    return path


def fixture_context(artifact):
    git = artifact.get('git')
    if not isinstance(git, dict):
        raise ValueError('Danger tests require a git object with created_files, modified_files, deleted_files arrays')
    result = {}
    for field in ('created_files', 'modified_files', 'deleted_files'):
        paths = git.get(field)
        if not isinstance(paths, list): raise ValueError('Missing or invalid git.' + field)
        result[field] = list(dict.fromkeys(_validate_path(p) for p in paths))
    sets = [set(result[f]) for f in result]
    if any(sets[i] & sets[j] for i in range(3) for j in range(i+1,3)):
        raise ValueError('A path must have only one Git change status')
    diffs = git.get('diffs', {})
    if not isinstance(diffs, dict): raise ValueError('git.diffs must map filenames to before/after text')
    changed = set().union(*sets)
    result['structured'] = {}
    for path, versions in diffs.items():
        _validate_path(path)
        if path not in changed: raise ValueError('Diff supplied for an unchanged path: ' + path)
        if not isinstance(versions, dict) or any(not isinstance(versions.get(k), str) for k in ('before', 'after')):
            raise ValueError('Each git.diffs entry requires before and after text')
        before, after = versions['before'], versions['after']
        if '\x00' in before or '\x00' in after:
            raise ValueError('Binary diff cannot establish changed-line count: ' + path)
        old, new = before.splitlines(), after.splitlines()
        changes = []
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
            if tag == 'equal': continue
            if tag in ('delete','replace'):
                changes.extend({'type':'del','del':True,'content':'-'+old[i], 'ln':i+1} for i in range(i1,i2))
            if tag in ('insert','replace'):
                changes.extend({'type':'add','add':True,'content':'+'+new[j], 'ln':j+1} for j in range(j1,j2))
        result['structured'][path] = {'fromPath':path,'chunks':[{'changes':changes}]}
    return result


def _context():
    import quickjs
    context = quickjs.Context()
    context.set_memory_limit(32 * 1024 * 1024)
    context.set_max_stack_size(512 * 1024)
    context.set_time_limit(1)
    return context


def validate_source(source):
    if not isinstance(source, str) or not source.strip() or len(source) > 60000:
        raise ValueError('A Dangerfile must contain 1–60,000 characters of JavaScript')
    context = _context()
    try: context.eval('(function(require){\n"use strict";\n' + source + '\n})')
    except Exception as exc: raise ValueError('Dangerfile JavaScript syntax error: ' + str(exc)) from None


def evaluate_danger(source, artifact):
    """Run the actual generated source with a narrow Danger fixture API, without host I/O."""
    validate_source(source)
    git = fixture_context(artifact)
    context = _context()
    # No host functions or Python objects are exposed to this JS engine.
    bootstrap = '''
const fixture = JSON.parse(INPUT_JSON);
let outcome = null;
const failures = [], warnings = [], tasks = [];
const git = Object.freeze({
  created_files: Object.freeze(fixture.created_files),
  modified_files: Object.freeze(fixture.modified_files),
  deleted_files: Object.freeze(fixture.deleted_files),
  structuredDiffForFile: async path => {
    if (!Object.prototype.hasOwnProperty.call(fixture.structured, path))
      throw new Error("Missing before/after diff evidence for " + path);
    return fixture.structured[path];
  }
});
const api = Object.freeze({
  danger: Object.freeze({git}),
  fail: (message, file, line) => failures.push({message:String(message), ...(file ? {path:String(file)} : {}), ...(line ? {line} : {})}),
  warn: message => warnings.push({message:String(message)}),
  schedule: task => tasks.push(task)
});
function require(name) {
  if (name !== "danger") throw new Error("Studio fixture tests support only require('danger')");
  return api;
}
'''.replace('INPUT_JSON', json.dumps(json.dumps(git)))
    try:
        context.eval(bootstrap)
        context.eval('(function(require){\n"use strict";\n' + source + '\n})(require);')
        context.eval('''
Promise.all(tasks.map(task => typeof task === "function" ? task() : task))
  .then(() => { outcome = {status: failures.length ? "fail" : "pass", checked:1, violations:failures, warnings}; })
  .catch(error => { outcome = {status:"error", message:String(error)}; });
''')
        for _ in range(10000):
            if not context.execute_pending_job(): break
        raw = context.eval('JSON.stringify(outcome)')
        if raw == 'null': raise ValueError('Dangerfile did not complete scheduled checks')
        result = json.loads(raw)
    except Exception as exc:
        result = {'status':'error','message':'Danger fixture execution failed: '+str(exc)}
    result['runner'] = 'Offline JavaScript fixture test; native Danger runs locally in Git'
    return result


def dangerfile_from_spec(spec):
    if spec.get('generator') != 'danger': raise ValueError('A Danger spec is required')
    return spec['config']['dangerfile']


def package_manifest():
    return {'name':'generated-danger-guardrail','version':'1.0.0','private':True,
            'engines':{'node':'>=22'},
            'scripts':{'check':'node run-local.js'},
            'devDependencies':{'danger':DANGER_VERSION}}


def local_runner(spec):
    config = spec['config']
    return """#!/usr/bin/env node
// Runs the installed Danger CLI locally; never downloads packages at commit time.
if (Number(process.versions.node.split('.')[0]) < 22) { console.error('This Danger bundle requires Node.js 22 or newer.'); process.exit(2); }
const { spawnSync } = require('node:child_process');
const path = require('node:path');
const mode = MODE;
const base = BASE;
const args = process.argv.slice(2);
const repoArg = args.indexOf('--repo');
const cwd = repoArg >= 0 ? args[repoArg + 1] : process.cwd();
if (!cwd) { console.error('--repo requires a path'); process.exit(2); }
const git = spawnSync('git', ['rev-parse', '--show-toplevel'], { cwd, encoding: 'utf8' });
if (git.status !== 0) { console.error('Run inside a Git repository or pass --repo PATH'); process.exit(2); }
const root = git.stdout.trim();
const head = spawnSync('git', ['rev-parse', '--verify', 'HEAD'], { cwd: root, encoding: 'utf8' });
if (head.status !== 0) { console.error('Danger needs an existing HEAD. Create a baseline commit before installing this guardrail.'); process.exit(2); }
if (mode === 'branch') {
  const ref = spawnSync('git', ['rev-parse', '--verify', base + '^{commit}'], { cwd: root, encoding: 'utf8' });
  if (ref.status !== 0) { console.error('Comparison base not found: ' + base); process.exit(2); }
}
let cli;
try { cli = require.resolve('danger/distribution/commands/danger-local.js'); }
catch (_) { console.error('Install the pinned runtime in this bundle directory with npm ci --ignore-scripts'); process.exit(2); }
const command = [cli, '--base', mode === 'staged' ? 'HEAD' : base, '--dangerfile', path.join(__dirname, 'dangerfile.js'), '--failOnErrors', '--text-only'];
if (mode === 'staged') command.push('--staging');
const env = { ...process.env };
// Local mode should not inherit credentials or identify itself as hosted CI.
for (const key of Object.keys(env)) {
  if (/TOKEN|SECRET|API_KEY|PASSWORD/i.test(key) || /^(GITHUB_|GITLAB_|CI$|DANGER_)/.test(key)) delete env[key];
}
const result = spawnSync(process.execPath, command, { cwd: root, env, stdio: 'inherit', timeout: 45000 });
if (result.error) console.error(result.error.message);
process.exit(result.status === null ? 2 : result.status);
""".replace('MODE', json.dumps(config['mode'])).replace('BASE', json.dumps(config['base']))


INSTALLER = r'''#!/usr/bin/env python3
"""Install the local Danger guardrail without overwriting another pre-commit hook."""
import argparse
from pathlib import Path
import shlex
import shutil
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', default='.', help='Target repository directory')
args = parser.parse_args()
if BUNDLE_MODE != 'staged':
    raise SystemExit('Branch mode checks committed HEAD and excludes the proposed commit. Run it manually; choose staged mode to install a commit gate.')
root = Path(subprocess.check_output(['git', '-C', args.repo, 'rev-parse', '--show-toplevel'], text=True).strip()).resolve()
subprocess.run(['git', '-C', str(root), 'rev-parse', '--verify', 'HEAD'], check=True, capture_output=True)
bundle = Path(__file__).resolve().parent
if not (bundle/'node_modules/danger').is_dir():
    raise SystemExit('First run npm ci --ignore-scripts in the guardrail bundle directory.')
hooks = subprocess.check_output(['git', '-C', str(root), 'rev-parse', '--git-path', 'hooks'], text=True).strip()
hooks = Path(hooks) if Path(hooks).is_absolute() else root/hooks
hook = hooks/'pre-commit'
if hook.exists() or hook.is_symlink():
    raise SystemExit('An existing pre-commit hook is present. Add the command from pre-commit.sample to your existing hook; nothing was overwritten.')
hooks.mkdir(parents=True, exist_ok=True)
node = shutil.which('node')
if not node: raise SystemExit('Node.js 22 or newer is required.')
version = subprocess.check_output([node, '--version'], text=True).strip()
if int(version.lstrip('v').split('.')[0]) < 22: raise SystemExit('Node.js 22 or newer is required; found ' + version)
command = shlex.quote(node) + ' ' + shlex.quote(str(bundle/'run-local.js')) + ' --repo ' + shlex.quote(str(root))
hook.write_text('#!/bin/sh\n# Guardrail Studio: local Danger check\n' + command + '\n')
hook.chmod(0o755)
print('Installed ' + str(hook))
print('Keep the guardrail bundle at ' + str(bundle))
'''

BUNDLE_README = '''# Local Git guardrail (Danger JS)

The rule is native JavaScript in `dangerfile.js`. It runs on your machine, with no PR, CI, token, or network needed after dependency installation.

## Install and run

Requires Node.js 22 or newer and Git. Keep this bundle in a stable directory (for example `.guardrails/my-rule/` in your repository), then run inside the bundle:

```
npm ci --ignore-scripts
npm run check -- --repo /path/to/repo
python3 install-hook.py --repo /path/to/repo
```

The installer creates a local pre-commit hook. A failing Danger rule returns nonzero and blocks the commit. It refuses to replace an existing hook; use `pre-commit.sample` to integrate manually. Nothing is automatically installed into your repository by Studio. Local hooks can be bypassed with `git commit --no-verify`.

Default **staged** mode checks the index against HEAD: the changes about to be committed. It excludes unstaged and untracked files, and supports partial staging. Danger requires an existing HEAD; bootstrap a baseline commit before installing.

**Branch** mode compares the merge base of the configured base ref (default `main`) and HEAD through committed HEAD. It excludes the proposed staged commit, unstaged changes, and untracked files. Use this mode manually for a whole-branch/PR-style rule before pushing. For a hook that checks the proposed commit, choose staged mode. The UI explains this difference and the downloaded run-local.js records the selected mode/base.

Edit `dangerfile.js` to change the predicate. Change mode/base in Studio and download again to update the runner. If you already use Danger, merge this rule into your existing Dangerfile rather than replacing it. Renames follow Danger's local Git classification.

The Studio test panel executes the same JavaScript against offline fixtures with no filesystem, network, or credentials. It implements created_files, modified_files, deleted_files, structuredDiffForFile, fail, warn, and schedule. A fixture represents one selected diff:
`{"git":{"created_files":[],"modified_files":["src/a.ts"],"deleted_files":[],"diffs":{"src/a.ts":{"before":"old\n","after":"new\n"}}}}`

`diffs` is needed only for line/content checks. Missing diff evidence is an error, not zero changed lines. Offline fixtures use textual before/after data; native Danger reads Git hunks. The fixture test is not proof of semantics or of every Danger API. Review generated code and tests before installing it.
'''
