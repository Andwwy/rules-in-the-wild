import json
import urllib.request
import urllib.error
base='http://127.0.0.1:8787'
with urllib.request.urlopen(base+'/api/config') as r:token=json.load(r)['token']
def post(endpoint,body):
    req=urllib.request.Request(base+'/api/'+endpoint,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Studio-Token':token})
    try:
        with urllib.request.urlopen(req,timeout=270) as r:return json.load(r)
    except urllib.error.HTTPError as e:raise RuntimeError(e.read().decode()) from None
rule='Required fields: `name`, `description`, `steps[]`.'
route=post('route',{'rule':rule,'context':''})
print('Route:',route,flush=True)
assert route['generator']=='json_schema'
result=post('generate',{'rule':rule,'context':'','generator':'json_schema'})
print(json.dumps(result,indent=2),flush=True)
assert result['status']=='generated'
assert result['spec']['scope'] is None
for document,expected in [({'name':42,'description':None,'steps':[],'extra':True},'pass'),({'name':'n','steps':[]},'fail'),({'name':'n','description':'d','steps':'wrong'},'fail')]:
    outcome=post('test',{'spec':result['spec'],'artifact':{'document':document}})
    print(outcome,flush=True)
    assert outcome['status']==expected
