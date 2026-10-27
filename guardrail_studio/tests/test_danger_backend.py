import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog import EXAMPLES, danger_spec
from danger_backend import evaluate_danger
from server import bundle

HERE = Path(__file__).resolve().parents[1]
COUNT = EXAMPLES[3]['spec']['config']['dangerfile']
WORKFLOW = '''const {danger, fail} = require("danger");
for (const p of [...danger.git.created_files, ...danger.git.modified_files])
  if (p.startsWith(".github/workflows/")) fail("Workflow additions and modifications forbidden", p);
'''
CHANGESET = '''const {danger, fail} = require("danger");
const changed = [...danger.git.created_files, ...danger.git.modified_files, ...danger.git.deleted_files];
const touched = changed.some(p => p.startsWith("packages/pixi-reels/src/") || p === "packages/pixi-reels/package.json");
if (touched && !danger.git.created_files.some(p => /^\\.changeset\\/[^/]+\\.md$/.test(p))) fail("Add a new changeset");
'''
LINES = '''const {danger, fail, schedule} = require("danger");
schedule(async () => {
  let count = 0;
  const paths = new Set([...danger.git.created_files, ...danger.git.modified_files, ...danger.git.deleted_files]);
  for (const p of paths) {
    const diff = await danger.git.structuredDiffForFile(p);
    if (!diff || !diff.chunks || diff.chunks.length === 0) { fail("Missing text diff: " + p); continue; }
    for (const chunk of diff.chunks) for (const change of chunk.changes)
      if (change.add || change.del) count++;
  }
  if (count > 2) fail("At most 2 added/deleted lines");
});
'''

def fixture(created=None, modified=None, deleted=None, diffs=None):
    return {'git': {'created_files': created or [], 'modified_files': modified or [],
                    'deleted_files': deleted or [], 'diffs': diffs or {}}}


class DangerFixtureTests(unittest.TestCase):
    def test_changed_files_and_statuses(self):
        self.assertEqual(evaluate_danger(COUNT, fixture(created=['a'], deleted=['b']))['status'], 'pass')
        self.assertEqual(evaluate_danger(COUNT, fixture(created=['a','b','c']))['status'], 'fail')
        for field in ['created', 'modified', 'deleted']:
            result = evaluate_danger(WORKFLOW, fixture(**{field:['.github/workflows/ci.yml']}))
            self.assertEqual(result['status'], 'pass' if field == 'deleted' else 'fail')

    def test_conditional_requires_new_changeset(self):
        self.assertEqual(evaluate_danger(CHANGESET, fixture(modified=['README.md']))['status'], 'pass')
        self.assertEqual(evaluate_danger(CHANGESET, fixture(modified=['packages/pixi-reels/src/a.ts']))['status'], 'fail')
        self.assertEqual(evaluate_danger(CHANGESET, fixture(modified=['packages/pixi-reels/package.json', '.changeset/old.md']))['status'], 'fail')
        self.assertEqual(evaluate_danger(CHANGESET, fixture(created=['.changeset/new.md'], deleted=['packages/pixi-reels/src/a.ts']))['status'], 'pass')
        self.assertEqual(evaluate_danger(CHANGESET, fixture(created=['.changeset/nested/new.md'], modified=['packages/pixi-reels/src/a.ts']))['status'], 'fail')

    def test_line_counts_and_missing_evidence(self):
        self.assertEqual(evaluate_danger(LINES, fixture(modified=['a'], diffs={'a':{'before':'old\n','after':'new\n'}}))['status'], 'pass')
        self.assertEqual(evaluate_danger(LINES, fixture(created=['a'], diffs={'a':{'before':'','after':'1\n2\n3\n'}}))['status'], 'fail')
        self.assertEqual(evaluate_danger(LINES, fixture(modified=['a']))['status'], 'error')

    def test_no_host_capabilities_and_time_limit(self):
        self.assertEqual(evaluate_danger('require("fs").readFileSync("/etc/passwd");', fixture())['status'], 'error')
        self.assertEqual(evaluate_danger('process.exit(0);', fixture())['status'], 'error')
        self.assertEqual(evaluate_danger('while (true) {}', fixture())['status'], 'error')

    def test_bundle_contains_native_code_and_hook(self):
        with zipfile.ZipFile(io.BytesIO(bundle(EXAMPLES[3]['spec']))) as z:
            self.assertEqual(z.read('dangerfile.js').decode(), COUNT)
            self.assertNotIn('.github/workflows/guardrail.yml', z.namelist())
            self.assertNotIn('guardrail.py', z.namelist())
            compile(z.read('install-hook.py'), 'install-hook.py', 'exec')
            self.assertIn('14.1.0', z.read('package-lock.json').decode())


@unittest.skipUnless(shutil.which('node') and (HERE/'node_modules/danger').exists(), 'Native Danger dependency required')
class NativeLocalDangerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='local-danger-test-')
        self.root = Path(self.temp.name)
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.root/'a.txt').write_text('old\n')
        self.git('add', 'a.txt')
        self.git('commit', '-m', 'baseline')
        self.out = self.root/'.guardrails'/'sample'
        self.out.mkdir(parents=True)
        with zipfile.ZipFile(io.BytesIO(bundle(EXAMPLES[3]['spec']))) as z: z.extractall(self.out)
        (self.out/'node_modules').symlink_to(HERE/'node_modules', target_is_directory=True)

    def tearDown(self): self.temp.cleanup()

    def git(self, *args, check=True):
        result = subprocess.run(['git', '-C', str(self.root), *args], text=True, capture_output=True, timeout=60)
        if check and result.returncode: self.fail(result.stdout + result.stderr)
        return result

    def native(self):
        return subprocess.run(['node', str(self.out/'run-local.js'), '--repo', str(self.root)], text=True, capture_output=True, timeout=60)

    def test_hook_blocks_commit_and_ignores_unstaged_files(self):
        install = subprocess.run([sys.executable,str(self.out/'install-hook.py'),'--repo',str(self.root)],text=True,capture_output=True)
        self.assertEqual(install.returncode,0,install.stdout+install.stderr)
        hook=self.root/'.git/hooks/pre-commit'
        self.assertTrue(hook.read_text().startswith('#!/bin/sh\n'))
        for name in ['b.txt','c.txt','d.txt']:
            (self.root/name).write_text('new\n')
        self.git('add','b.txt','c.txt','d.txt')
        blocked=self.git('commit','-m','must fail',check=False)
        self.assertNotEqual(blocked.returncode,0,blocked.stdout+blocked.stderr)
        self.assertIn('Changed 3 files',blocked.stdout+blocked.stderr)
        self.assertEqual(self.git('log','-1','--format=%s').stdout.strip(),'baseline')
        self.git('restore','--staged','d.txt')
        accepted=self.git('commit','-m','two files',check=False)
        self.assertEqual(accepted.returncode,0,accepted.stdout+accepted.stderr)
        self.assertEqual(self.git('log','-1','--format=%s').stdout.strip(),'two files')
        # Preserve existing hooks on a second install attempt.
        again=subprocess.run([sys.executable,str(self.out/'install-hook.py'),'--repo',str(self.root)],text=True,capture_output=True)
        self.assertNotEqual(again.returncode,0)
        self.assertIn('nothing was overwritten',again.stderr+again.stdout)

    def test_native_lines_honor_partial_staging(self):
        (self.out/'dangerfile.js').write_text(LINES)
        (self.root/'a.txt').write_text('new\n')
        self.git('add','a.txt')
        # Extra unstaged content must not alter the staged diff's 2-line count.
        (self.root/'a.txt').write_text('new\nextra\nextra\nextra\n')
        passed=self.native()
        self.assertEqual(passed.returncode,0,passed.stdout+passed.stderr)
        self.git('add','a.txt')
        failed=self.native()
        self.assertNotEqual(failed.returncode,0,failed.stdout+failed.stderr)
        self.assertIn('At most 2',failed.stdout+failed.stderr)

    def test_native_conditional_changeset(self):
        (self.out/'dangerfile.js').write_text(CHANGESET)
        path=self.root/'packages/pixi-reels/src/a.ts';path.parent.mkdir(parents=True);path.write_text('export const x=1;\n')
        self.git('add','packages')
        failed=self.native()
        self.assertNotEqual(failed.returncode,0,failed.stdout+failed.stderr)
        self.assertIn('Add a new changeset',failed.stdout+failed.stderr)
        cs=self.root/'.changeset/new.md';cs.parent.mkdir();cs.write_text('---\n---\nChange\n')
        self.git('add','.changeset/new.md')
        passed=self.native()
        self.assertEqual(passed.returncode,0,passed.stdout+passed.stderr)

    def test_branch_mode_checks_committed_range(self):
        from danger_backend import local_runner
        spec=danger_spec('At most two files',COUNT,mode='branch',base='main')
        (self.out/'run-local.js').write_text(local_runner(spec))
        self.git('switch','-c','feature')
        for name in ['b','c','d']: (self.root/name).write_text('x\n')
        self.git('add','b','c','d');self.git('commit','-m','three changed files')
        result=self.native()
        self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('Changed 3 files',result.stdout+result.stderr)

if __name__ == '__main__': unittest.main()
