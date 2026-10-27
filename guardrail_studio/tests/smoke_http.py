"""Exercise a running local server. --live-jev sends one paid routing request."""
import argparse
import io
import json
import urllib.request
import urllib.error
import zipfile
parser=argparse.ArgumentParser();parser.add_argument('--live-jev',action='store_true');args=parser.parse_args()
base='http://127.0.0.1:8787'
with urllib.request.urlopen(base+'/api/config') as r: config=json.load(r)
def post(endpoint,body,raw=False):
    req=urllib.request.Request(base+'/api/'+endpoint,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Studio-Token':config['token']})
    with urllib.request.urlopen(req,timeout=90) as r: return r.read() if raw else json.load(r)
for example in config['examples']:
    for label in ['pass','fail']:
        result=post('test',{'spec':example['spec'],'artifact':example[label]})
        assert result['status']==label,(example['id'],label,result)
    print(example['id']+': passing and failing HTTP fixtures verified')
archive=zipfile.ZipFile(io.BytesIO(post('bundle',{'spec':config['examples'][0]['spec']},True)))
assert 'regex-check.yaml' in archive.namelist()
assert 'guardrail.py' not in archive.namelist()
print('Download bundle verified')
if args.live_jev:
    e=config['examples'][0]
    answer=post('route',{'rule':e['rule'],'context':e['context']})
    print('Live Jev:',json.dumps(answer))
    assert answer['generator']=='regex'
