import copy
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
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from catalog import EXAMPLES
from guardrail import evaluate,validate_spec
from manifest import collect
from native_backends import native_artifact,spec_from_source,check_definition
from server import bundle
HERE=Path(__file__).resolve().parents[1]


def regex_spec(pattern,args=None):
    s=copy.deepcopy(EXAMPLES[0]['spec'])
    s['config']['pygrep']['repos'][0]['hooks']=[{'id':'check','name':'Check input','language':'pygrep','entry':pattern,'types':['text'],'args':args or []}]
    return s


class NativeBackendTests(unittest.TestCase):
    def test_regex_unbound_text_whole_value(self):
        s=regex_spec(r'\A[a-z]+\Z',['--multiline','--negate'])
        self.assertIsNone(s['scope']);validate_spec(s)
        self.assertEqual(evaluate(s,{'text':'abc'})['status'],'pass')
        for text in ['abc\nINVALID','UPPER','']:
            self.assertEqual(evaluate(s,{'text':text})['status'],'fail')

    def test_regex_composition_per_line_and_paths(self):
        s=regex_spec(r'[^a-z\r\n]')
        self.assertEqual(evaluate(s,{'text':'abc\ndef\n'})['status'],'pass')
        self.assertEqual(evaluate(s,{'text':'abc\nBAD\n'})['status'],'fail')
        hook=s['config']['pygrep']['repos'][0]['hooks'][0]
        hook['files']=r'^docs/';hook['exclude']=r'^docs/vendor/'
        self.assertEqual(evaluate(s,{'files':{'docs/vendor/a.txt':'BAD'}})['status'],'not_applicable')
        self.assertEqual(evaluate(s,{'files':{'docs/a.txt':'BAD'}})['status'],'fail')
        s['config']['pygrep']['repos'][0]['hooks'].append({'id':'no-todo','name':'No TODO','language':'pygrep','entry':'TODO','types':['text']})
        self.assertEqual(evaluate(s,{'text':'TODO'})['status'],'fail')

    def test_native_configuration_roundtrip(self):
        for example in EXAMPLES:
            s=example['spec'];a=native_artifact(s)
            parsed=spec_from_source(s,a['content'])
            self.assertEqual(parsed,s)

    def test_native_rule_syntax_is_not_silently_accepted(self):
        s=copy.deepcopy(EXAMPLES[0]['spec']);s['config']['pygrep']['repos'][0]['hooks'][0]['entry']='['
        with self.assertRaises(Exception):validate_spec(s)
        s=copy.deepcopy(EXAMPLES[2]['spec']);s['config']['policy']='package main\ndeny contains msg if { MISSING SYNTAX }'
        self.assertEqual(evaluate(s,EXAMPLES[2]['pass'])['status'],'error')
        s=copy.deepcopy(EXAMPLES[4]['spec']);s['config']['rules'][0]['pattern']='def invalid('
        self.assertEqual(evaluate(s,EXAMPLES[4]['pass'])['status'],'error')
        self.assertEqual(check_definition(s)['status'],'error')

    def test_conftest_every_service_not_one_glob_match(self):
        s=EXAMPLES[2]['spec']
        self.assertEqual(evaluate(s,EXAMPLES[2]['pass'])['status'],'pass')
        self.assertEqual(evaluate(s,EXAMPLES[2]['fail'])['status'],'fail')
        data=copy.deepcopy(EXAMPLES[2]['pass']);data['entries'][-1]={'path':'services/web/Dockerfile','kind':'symlink','target':'../api/Dockerfile'}
        self.assertEqual(evaluate(s,data)['status'],'fail')

    def test_conftest_directory_count_and_adapter(self):
        s=copy.deepcopy(EXAMPLES[2]['spec'])
        s['config']['policy']='''package main
has_docs if { some e in input.entries; e.path == "docs"; e.kind == "directory" }
deny contains "docs directory missing" if { not has_docs }
deny contains "Too many files" if { count([e | some e in input.entries; e.kind == "file"]) > 1 }
'''
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'docs').mkdir();(root/'one').write_text('a');(root/'link').symlink_to('one');(root/'.git').mkdir();(root/'.git/secret').write_text('ignored')
            data=collect(root)
            self.assertIn({'path':'docs','kind':'directory'},data['entries'])
            self.assertIn({'path':'link','kind':'symlink','target':'one'},data['entries'])
            self.assertFalse(any(e['path'].startswith('.git') for e in data['entries']))
            self.assertEqual(evaluate(s,data)['status'],'pass')
            (root/'two').write_text('b')
            self.assertEqual(evaluate(s,collect(root))['status'],'fail')

    def test_conftest_missing_input_and_capabilities(self):
        with self.assertRaises(ValueError):evaluate(EXAMPLES[2]['spec'],{'files':{}})
        s=copy.deepcopy(EXAMPLES[2]['spec']);s['config']['policy']='''package main
deny contains "x" if { response := http.send({"method":"GET","url":"https://example.com"}); response.status_code == 200 }
'''
        self.assertEqual(evaluate(s,{'entries':[]})['status'],'error')
        s['config']['policy']='package main\nhelper := true\n'
        self.assertEqual(evaluate(s,{'entries':[]})['status'],'error')

    def test_semgrep_native_paths(self):
        s=copy.deepcopy(EXAMPLES[4]['spec']);s['scope']=None
        s['config']['rules'][0].update(paths={'include':['src/**'],'exclude':['src/vendor/**']},metadata={'category':'correctness'})
        validate_spec(s)
        artifact={'files':{'src/main.py':'eval("x")\n','tests/test.py':'eval("x")\n','src/vendor/lib.py':'eval("x")\n'}}
        result=evaluate(s,artifact)
        self.assertEqual(result['status'],'fail')
        self.assertEqual([v['path'] for v in result['violations']],['src/main.py'])

    def test_semgrep_native_taint(self):
        s=copy.deepcopy(EXAMPLES[4]['spec']);s['scope']=None
        s['config']['rules']=[{'id':'flow','message':'Unsanitized flow','languages':['python'],'severity':'ERROR','mode':'taint','pattern-sources':[{'pattern':'source(...)'}],'pattern-sinks':[{'pattern':'sink(...)'}],'pattern-sanitizers':[{'pattern':'sanitize(...)'}]}]
        validate_spec(s)
        self.assertEqual(evaluate(s,{'files':{'a.py':'sink(sanitize(source()))\n'}})['status'],'pass')
        self.assertEqual(evaluate(s,{'files':{'a.py':'sink(source())\n'}})['status'],'fail')

    def test_json_yaml_and_jsonl_use_same_schema(self):
        s=copy.deepcopy(EXAMPLES[1]['spec']);s['scope']=None
        s['config']['schema']={'type':'object','required':['name','description','steps'],'properties':{'steps':{'type':'array'}}}
        self.assertEqual(evaluate(s,{'document':{'name':1,'description':None,'steps':[],'other':True}})['status'],'pass')
        self.assertEqual(evaluate(s,{'files':{'pipeline.yaml':'name: demo\ndescription: null\nsteps: []\n'}})['status'],'pass')
        self.assertEqual(evaluate(s,{'files':{'pipeline.yaml':'name: demo\nsteps: wrong\n'}})['status'],'fail')
        records='{"name":"a","description":"b","steps":[]}\n{"name":"c","description":"d","steps":"wrong"}\n'
        result=evaluate(s,{'files':{'records.jsonl':records}})
        self.assertEqual(result['status'],'fail')
        self.assertEqual(result['checked'],2)
        self.assertEqual(result['violations'][0]['line'],2)
        self.assertEqual(evaluate(s,{'files':{'records.jsonl':'not json'}})['status'],'fail')
        self.assertEqual(evaluate(s,{'files':{'records.jsonl':''}})['status'],'not_applicable')
        self.assertEqual(evaluate(s,{'files':{'empty.jsonl':'','valid.json':'{\"name\":1,\"description\":null,\"steps\":[]}'}})['status'],'pass')

    def test_downloads_are_native_and_install_no_hooks(self):
        expected={0:'regex-check.yaml',1:'schema.json',2:'policy.rego',4:'semgrep.yml'}
        for i,filename in expected.items():
            with zipfile.ZipFile(io.BytesIO(bundle(EXAMPLES[i]['spec']))) as z:
                self.assertIn(filename,z.namelist())
                self.assertNotIn('guardrail.py',z.namelist())
                self.assertNotIn('guardrail.json',z.namelist())
                self.assertNotIn('install-hook.py',z.namelist())

    def test_exported_regex_config_runs_natively_without_hook(self):
        s=regex_spec(r'\A[a-z]+\Z',['--multiline','--negate'])
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with zipfile.ZipFile(io.BytesIO(bundle(s))) as z:z.extractall(root)
            subprocess.run(['git','init',str(root)],capture_output=True,check=True)
            value=root/'input.txt';value.write_text('abc')
            env={**os.environ,'PRE_COMMIT_HOME':str(root/'cache')}
            command=['pre-commit','run','--config',str(root/'regex-check.yaml'),'--files','input.txt']
            run=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True,timeout=30)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            value.write_text('abc\nBAD')
            run=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True,timeout=30)
            self.assertEqual(run.returncode,1,run.stdout+run.stderr)
            self.assertFalse((root/'.git/hooks/pre-commit').exists())

    def test_exported_schema_and_jsonl_adapter(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with zipfile.ZipFile(io.BytesIO(bundle(EXAMPLES[1]['spec']))) as z:z.extractall(root)
            path=root/'config.jsonl';path.write_text('{"debug":false,"port":8000}\n{"debug":"false","port":0}\n')
            command=[sys.executable,str(root/'check_jsonl.py'),'--schemafile',str(root/'schema.json'),str(path)]
            run=subprocess.run(command,capture_output=True,text=True,timeout=30)
            self.assertEqual(run.returncode,1,run.stdout+run.stderr)
            path.write_text('{"debug":false,"port":8000}\n')
            run=subprocess.run(command,capture_output=True,text=True,timeout=30)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)

if __name__=='__main__':unittest.main()
