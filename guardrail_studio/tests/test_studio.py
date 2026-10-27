import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog import EXAMPLES, LEGACY_DIFF_EXAMPLE, LEGACY_PATH_EXAMPLE, spec as make_spec
from guardrail import evaluate, matches, validate_spec
from server import bundle, test_spec

class GuardrailTests(unittest.TestCase):
    def test_examples(self):
        for example in EXAMPLES:
            if example['id']=='semgrep' and not shutil.which('semgrep'): continue
            with self.subTest(example=example['id']):
                self.assertEqual(evaluate(example['spec'],example['pass'])['status'],'pass')
                self.assertEqual(evaluate(example['spec'],example['fail'])['status'],'fail')

    def test_scope_and_no_matching_files(self):
        spec=json.loads(json.dumps(EXAMPLES[0]['spec']))
        spec['config']['pygrep']['repos'][0]['hooks'][0]['exclude']='^vendor/'
        self.assertEqual(evaluate(spec,{'files':{'vendor/docs/a.md':'TODO'}})['status'],'not_applicable')
        self.assertEqual(evaluate(spec,{'files':{'docs/a.md':'TODO','a.py':'fine'}})['status'],'fail')
        self.assertTrue(matches('README.md','**/*.md'))
        self.assertFalse(matches('a/b.py','*.py'))
        self.assertTrue(matches('a/b/c.py','**/*.py'))

    def test_schema_invalid_json_and_remote_refs(self):
        spec=json.loads(json.dumps(EXAMPLES[1]['spec']))
        self.assertEqual(evaluate(spec,{'files':{'config.json':'{no'}})['status'],'fail')
        spec['config']['schema']={'$ref':'https://example.com/schema'}
        with self.assertRaises(ValueError): validate_spec(spec)

    def test_bad_paths_and_types(self):
        for path in ['../escape','/abs','a/../b','a\\b','a//b']:
            with self.subTest(path=path),self.assertRaises(ValueError): evaluate(EXAMPLES[0]['spec'],{'files':{path:'TODO'}})
        with self.assertRaises(ValueError): evaluate(EXAMPLES[0]['spec'],{'files':{'x.md':42}})
        with self.assertRaises(ValueError): evaluate(LEGACY_DIFF_EXAMPLE['spec'],{'files':{}})

    def test_empty_manifest_is_violation(self):
        self.assertEqual(evaluate(LEGACY_PATH_EXAMPLE['spec'],{'files':{}})['status'],'fail')

    def test_bundle_is_portable_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with zipfile.ZipFile(io.BytesIO(bundle(make_spec('regex','No TODO',['**/*.md'],{'pattern':'TODO','mode':'forbid','ignore_case':False})))) as archive: archive.extractall(root)
            for artifact,code in [(EXAMPLES[0]['pass'],0),(EXAMPLES[0]['fail'],1),({'files':{}},2)]:
                (root/'artifact.json').write_text(json.dumps(artifact))
                run=subprocess.run([sys.executable,str(root/'guardrail.py'),'--artifact',str(root/'artifact.json')],capture_output=True,text=True)
                self.assertEqual(run.returncode,code,run.stdout+run.stderr)

    def test_git_repository_diff(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            subprocess.run(['git','init',str(root)],check=True,capture_output=True)
            (root/'migrations').mkdir(); (root/'migrations'/'one.sql').write_text('SELECT 1;')
            subprocess.run(['git','-C',str(root),'add','.'],check=True)
            subprocess.run(['git','-C',str(root),'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','fixture'],capture_output=True,check=True)
            (root/'migrations'/'one.sql').write_text('SELECT 2;')
            from guardrail import repository_artifact
            artifact=repository_artifact(root,LEGACY_DIFF_EXAMPLE['spec'],'HEAD')
            self.assertEqual(evaluate(LEGACY_DIFF_EXAMPLE['spec'],artifact)['status'],'fail')

    def test_workflow_status_restrictions(self):
        spec=json.loads(json.dumps(LEGACY_DIFF_EXAMPLE['spec']))
        spec['config'].update(forbidden_paths=[], base='HEAD', include_untracked=True,
            forbidden_changes=[{'paths':['.github/workflows/**'],'statuses':['A','M','T']}])
        for status in ['A','M','T','D']:
            result=evaluate(spec,{'changes':[{'path':'.github/workflows/ci.yml','status':status}]})
            self.assertEqual(result['status'],'pass' if status=='D' else 'fail')
        self.assertEqual(evaluate(spec,{'changes':[]})['status'],'pass')
        self.assertEqual(evaluate(spec,{'changes':[{'path':'src/a.py','status':'M'}]})['status'],'pass')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            subprocess.run(['git','init',str(root)],check=True,capture_output=True)
            subprocess.run(['git','-C',str(root),'-c','user.name=Test','-c','user.email=test@example.invalid','commit','--allow-empty','-m','fixture'],capture_output=True,check=True)
            (root/'.github/workflows').mkdir(parents=True)
            (root/'.github/workflows/ci.yml').write_text('name: CI')
            from guardrail import repository_artifact
            artifact=repository_artifact(root,spec,None)
            self.assertEqual(artifact['changes'],[{'path':'.github/workflows/ci.yml','status':'A'}])
            self.assertEqual(evaluate(spec,artifact)['status'],'fail')

    def test_unbound_schema_and_explicit_binding(self):
        spec=json.loads(json.dumps(EXAMPLES[1]['spec']))
        spec['scope']=None
        spec['config']['schema']={'type':'object','required':['name','description','steps'],'properties':{'steps':{'type':'array'}}}
        validate_spec(spec)
        for document, expected in [({'name':42,'description':None,'steps':[],'extra':True},'pass'),
                                   ({'name':'x','steps':[]},'fail'),
                                   ({'name':'x','description':'y','steps':'bad'},'fail'),(None,'fail')]:
            self.assertEqual(evaluate(spec,{'document':document})['status'],expected)
        self.assertEqual(evaluate(spec,{'files':{'data.json':'{}'}})['status'],'fail')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with zipfile.ZipFile(io.BytesIO(bundle(spec))) as archive: archive.extractall(root)
            (root/'input.json').write_text(json.dumps({'name':42,'description':None,'steps':[]}))
            command=[sys.executable,str(Path(__file__).resolve().parents[1]/'guardrail.py'),'--spec',str(root/'saved-spec.json')]
            (root/'saved-spec.json').write_text(json.dumps(spec))
            for arguments, expected in [(['--document',str(root/'input.json')],0),
                                       (['--repo',str(root)],2),
                                       (['--repo',str(root),'--include','input.json'],0)]:
                run=subprocess.run(command+arguments,capture_output=True,text=True)
                self.assertEqual(run.returncode,expected,run.stdout+run.stderr)
        spec['generator']='path_manifest';spec['config']={'required':[],'forbidden':[]}
        with self.assertRaises(Exception): validate_spec(spec)

    def test_regex_worker_returns_error_not_pass(self):
        spec=json.loads(json.dumps(EXAMPLES[0]['spec'])); spec['config']['pygrep']['repos'][0]['hooks'][0]['entry']='['
        with self.assertRaises(Exception): test_spec(spec,EXAMPLES[0]['pass'])

if __name__=='__main__': unittest.main()
