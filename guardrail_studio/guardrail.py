#!/usr/bin/env python3
"""Portable deterministic guardrail runner. Exit 0 pass, 1 violation, 2 error/no scope."""
import argparse
import fnmatch
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile


def matches(path, pattern):
    # POSIX, segment-aware globs: * never crosses /; ** does, including zero directories.
    def rec(a, b):
        if not b:
            return not a
        if b[0] == '**':
            return rec(a, b[1:]) or bool(a) and rec(a[1:], b)
        return bool(a) and fnmatch.fnmatchcase(a[0], b[0]) and rec(a[1:], b[1:])
    return rec(path.split('/'), pattern.split('/'))


def safe_path(path):
    if not isinstance(path, str) or not path or '\\' in path or '\x00' in path:
        raise ValueError('Artifact paths must be nonempty relative POSIX paths')
    if path.startswith('/') or any(p in ('..', '.', '') for p in path.split('/')):
        raise ValueError('Artifact paths must be normalized and relative')
    return path


def validate_spec(spec):
    import jsonschema
    schema = json.loads(Path(__file__).with_name('spec.schema.json').read_text())
    jsonschema.Draft202012Validator(schema).validate(spec)
    kind, config = spec['generator'], spec['config']
    if kind == 'danger':
        from danger_backend import validate_source
        validate_source(config['dangerfile'])
    if kind in ('semgrep','conftest') or (kind == 'regex' and 'pygrep' in config):
        from native_backends import validate_native
        validate_native(spec)
    if kind == 'regex' and 'pattern' in config:
        re.compile(config['pattern'])
    if kind == 'json_schema':
        def refs(v):
            if isinstance(v, dict):
                for k, x in v.items():
                    if k in ('$ref', '$dynamicRef') and not str(x).startswith('#'):
                        raise ValueError('Only local JSON Schema references are supported')
                    refs(x)
            elif isinstance(v, list):
                for x in v: refs(x)
        refs(config['schema'])
        jsonschema.Draft202012Validator.check_schema(config['schema'])
    return spec


def evaluate(spec, artifact):
    validate_spec(spec)
    files = artifact.get('files', {})
    if not isinstance(files, dict) or any(not isinstance(x, str) for x in files.values()):
        raise ValueError('files must map relative filenames to text contents')
    for path in files: safe_path(path)
    kind, c = spec['generator'], spec['config']
    if kind == 'regex' and 'pygrep' in c:
        from native_backends import evaluate_pygrep
        return evaluate_pygrep(spec,artifact)
    if kind == 'conftest':
        from native_backends import evaluate_conftest
        return evaluate_conftest(spec,artifact)
    if kind == 'semgrep':
        from native_backends import evaluate_semgrep
        return evaluate_semgrep(spec,artifact)
    if kind == 'json_schema':
        from native_backends import evaluate_schema
        return evaluate_schema(spec,artifact)
    if kind == 'danger':
        from danger_backend import evaluate_danger
        return evaluate_danger(c['dangerfile'], artifact)
    scope = spec['scope']
    if kind == 'json_schema' and 'document' in artifact:
        from jsonschema import Draft202012Validator, FormatChecker
        validator = Draft202012Validator(c['schema'], format_checker=FormatChecker())
        violations = [{'path':'/'.join(map(str, error.absolute_path)) or '$', 'message':error.message}
                      for error in validator.iter_errors(artifact['document'])]
        return {'status':'fail' if violations else 'pass', 'checked':1, 'violations':violations}
    if scope is None:
        raise ValueError('File scope is not bound. Supply a document, or bind include/exclude paths before checking files.')
    scoped = lambda p: any(matches(p, g) for g in scope['include']) and not any(matches(p, g) for g in scope['exclude'])
    selected = {p: v for p, v in files.items() if scoped(p)}
    violations = []
    checked = len(selected)
    def fail(path, message): violations.append({'path': path, 'message': message})
    if kind == 'regex':
        pattern = re.compile(c['pattern'], re.MULTILINE | (re.IGNORECASE if c['ignore_case'] else 0))
        for path, content in selected.items():
            hit = bool(pattern.search(content))
            if (c['mode'] == 'forbid' and hit) or (c['mode'] == 'require' and not hit):
                fail(path, spec['description'])
    elif kind == 'json_schema':
        from jsonschema import Draft202012Validator, FormatChecker
        validator = Draft202012Validator(c['schema'], format_checker=FormatChecker())
        for path, content in selected.items():
            try: data = json.loads(content)
            except ValueError as exc:
                fail(path, 'Invalid JSON: ' + str(exc)); continue
            for error in validator.iter_errors(data):
                fail(path, '/'.join(map(str, error.absolute_path)) + ': ' + error.message)
    elif kind == 'path_manifest':
        checked = 1  # Existence constraints evaluate even an empty manifest.
        for glob in c['required']:
            if not any(matches(p, glob) for p in selected): fail(glob, 'Required path is missing')
        for path in selected:
            if any(matches(path, g) for g in c['forbidden']): fail(path, 'Forbidden path exists')
    elif kind == 'git_diff':
        changes = artifact.get('changes')
        if not isinstance(changes, list): raise ValueError('Git-diff checks require a changes array')
        checked = 1
        for change in changes:
            path = safe_path(change['path'])
            status = change['status']
            if status not in ('A', 'M', 'D', 'T'): raise ValueError('Change status must be A, M, D, or T; represent renames as D+A')
            if not scoped(path): continue
            if c['allowed_paths'] and not any(matches(path, g) for g in c['allowed_paths']): fail(path, 'Change outside allowed paths')
            if any(matches(path, g) for g in c['forbidden_paths']): fail(path, 'Protected path changed')
            if c['forbid_deletions'] and status == 'D': fail(path, 'File deletion is forbidden')
            for restriction in c.get('forbidden_changes', []):
                if status in restriction['statuses'] and any(matches(path, g) for g in restriction['paths']):
                    fail(path, 'Forbidden change status: ' + status)
    elif kind == 'semgrep':
        executable = shutil.which('semgrep')
        if not executable: raise ValueError('Semgrep is not installed. Install requirements.txt to run this guardrail.')
        if selected:
            with tempfile.TemporaryDirectory(prefix='guardrail-scan-') as directory:
                root = Path(directory); source = root/'artifact'; source.mkdir()
                for path, content in selected.items():
                    dest = source/path; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_text(content)
                config = root/'rules.json'; config.write_text(json.dumps({'rules': c['rules']}))
                run = subprocess.run([executable, 'scan', '--config', str(config), '--json', '--metrics=off', '--disable-nosem', '--no-git-ignore', str(source)], capture_output=True, text=True, timeout=35)
                if run.returncode: raise ValueError('Semgrep could not complete: ' + run.stderr[-1500:])
                result = json.loads(run.stdout)
                if result.get('errors'): raise ValueError('Semgrep reported scan errors: ' + json.dumps(result['errors'])[:1500])
                checked = len(result.get('paths', {}).get('scanned', []))
                for finding in result.get('results', []):
                    fail(str(Path(finding['path']).relative_to(source)), finding['extra']['message'] + ' (line ' + str(finding['start']['line']) + ')')
    status = 'fail' if violations else 'pass' if checked else 'not_applicable'
    return {'status': status, 'checked': checked, 'violations': violations}


def repository_artifact(repo, spec, base):
    root = Path(repo).resolve()
    if not root.is_dir(): raise ValueError('Repository directory does not exist')
    if spec['generator']=='conftest':
        from manifest import collect
        return collect(root)
    if spec['scope'] is None: raise ValueError('Choose repository file scope with --include before scanning, or use --document for a single JSON document.')
    if spec['generator'] == 'git_diff':
        base = base or spec['config'].get('base', 'HEAD')
        if base.startswith('-'): raise ValueError('Git base must be a revision, not an option')
        run = subprocess.run(['git', '-C', str(root), 'diff', '--no-renames', '--name-status', '-z', base, '--'], capture_output=True, timeout=15, check=True)
        parts = run.stdout.decode().split('\x00'); changes = []
        for i in range(0, len(parts)-1, 2): changes.append({'status': parts[i], 'path': parts[i+1]})
        if spec['config'].get('include_untracked', False):
            untracked = subprocess.run(['git', '-C', str(root), 'ls-files', '--others', '--exclude-standard', '-z'], capture_output=True, timeout=15, check=True)
            changes.extend({'status':'A', 'path':p} for p in untracked.stdout.decode().split('\x00') if p)
        return {'files': {}, 'changes': changes}
    files = {}
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d != '.git' and not (Path(directory)/d).is_symlink()]
        for name in names:
            path = Path(directory)/name
            if path.is_symlink(): continue
            relative = path.relative_to(root).as_posix()
            if not any(matches(relative, g) for g in spec['scope']['include']) or any(matches(relative, g) for g in spec['scope']['exclude']): continue
            if spec['generator'] == 'path_manifest': files[relative] = ''; continue
            if path.stat().st_size > 2_000_000: raise ValueError('In-scope file exceeds 2MB: ' + relative)
            files[relative] = path.read_text(encoding='utf-8')
    return {'files': files}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', default=str(Path(__file__).with_name('guardrail.json')))
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--artifact', help='JSON containing files and/or changes')
    source.add_argument('--document', help='Validate one JSON document with a JSON Schema guardrail; no file scope needed')
    parser.add_argument('--include', action='append', help='Bind JSON Schema to a repository file glob; repeat for multiple globs')
    source.add_argument('--repo', help='Check local repository artifacts (read only)')
    parser.add_argument('--base', default=None, help='Override the configured Git comparison base (fallback HEAD)')
    args = parser.parse_args()
    try:
        spec = validate_spec(json.loads(Path(args.spec).read_text()))
        if args.include:
            if spec['generator'] != 'json_schema': raise ValueError('--include binding is supported for JSON Schema only')
            spec['scope'] = {'include': args.include, 'exclude': (spec['scope'] or {}).get('exclude', [])}
            validate_spec(spec)
        if args.document:
            if spec['generator'] != 'json_schema': raise ValueError('--document requires a JSON Schema guardrail')
            artifact = {'document':json.loads(Path(args.document).read_text())}
        else:
            artifact = json.loads(Path(args.artifact).read_text()) if args.artifact else repository_artifact(args.repo, spec, args.base)
        result = evaluate(spec, artifact)
    except Exception as exc:
        result = {'status': 'error', 'message': str(exc)}
    print(json.dumps(result, indent=2))
    return {'pass': 0, 'fail': 1}.get(result['status'], 2)

if __name__ == '__main__': sys.exit(main())
