"""Local fictional worker subprocess; no service/HTTP endpoint."""
import argparse
import json
from pathlib import Path
from durable_fixture_payments import LocalJournal
p=argparse.ArgumentParser();p.add_argument('config');p.add_argument('input');p.add_argument('action',choices=['receive','supply','process','reconcile','apply']);p.add_argument('--fail')
a=p.parse_args();v=json.loads(Path(a.input).read_text());j=LocalJournal(a.config)
b=v['binding']['business_id'];n=v['notification'];key=n['id'];now='2026-04-01T12:00:00Z'
if a.action=='receive':result=j.receive(b,json.dumps(n,sort_keys=True).encode(),a.fail)
elif a.action=='supply':result=j.supply_simulated_facts(b,key,v['contract'],v['canonical'])
elif a.action=='process':result=j.process(b,key,now,a.fail)
elif a.action=='reconcile':result=j.reconcile(b,key,a.fail)
else:result=j.apply(b,key,now,a.fail)
print(json.dumps({'status':result,'fixture_only':True}))
