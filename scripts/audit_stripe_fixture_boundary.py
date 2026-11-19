"""Independent, read-only SQL/JSON checks; imports no application/evaluator/adapter."""
import json
from pathlib import Path
import sqlite3
import sys
from fractions import Fraction

root=Path(sys.argv[1]); fixtures=json.loads(Path(sys.argv[2]).read_text())
limits={'basic':25,'pro':75,'business':200}
report={'fixture_only':True,'databases':[],'boundary_decisions':{},'independent_proration':{}}
u=fixtures['cases']['upgrade'];p=u['contract']['period'];at=u['contract']['effective_at']
fraction=Fraction(p['end']-at,p['end']-p['start'])
assert fraction==Fraction(1,2)
assert u['contract']['lines'][0]['amount']==-2900*fraction==-1450
assert u['contract']['lines'][1]['amount']==5900*fraction==2950
assert u['canonical']['invoice']['amount_paid']==1500
report['independent_proration']={'remaining_fraction':'1/2','basic_credit_cents':-1450,'pro_debit_cents':2950,'paid_cents':1500}
for path in sorted(root.rglob('*.sqlite')):
    with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as c:
        s=json.loads(c.execute('SELECT data FROM projection').fetchone()[0])
        receipts=list(c.execute('SELECT operation_id,status FROM receipts'))
        ops=[x[0] for x in receipts if x[1]=='applied'];assert len(set(ops))==len(ops)
        for status,before,after in c.execute('SELECT status,before_state,after_state FROM audit'):
            if status in ('review','duplicate','observed_no_grant'):assert json.loads(before)==json.loads(after)
        assert s['saved_work']=={'sentinel':'UNCHANGED'}
        info={'database':str(path.relative_to(root)),'applied_operations':ops,'remaining':None}
        snap=s['snapshot']
        if snap:
            assert snap['extras']=={'lookups':7,'estimates':11}
            cap=limits[snap['period']['plan']]+sum(limits[x['to_plan']]-limits[x['from_plan']] for x in snap['upgrades'])
            remain={channel:cap-snap['used'][channel] for channel in ('lookups','estimates')}
            assert min(remain.values())>=0;info['remaining']=remain
            name=path.parent.name
            if name=='test_upgrade_23_used_leaves52':assert remain=={'lookups':52,'estimates':52}
            if name in ('test_out_of_order_paid_chain','test_all_paid_delivery_permutations'):
                assert remain=={'lookups':75,'estimates':75} and snap['period']['id']=='p2'
                assert s['periods']['p1']['used']=={'lookups':23,'estimates':23}
            if name=='test_renewal_duplicate_no_reset_after_usage':assert remain=={'lookups':72,'estimates':72}
        report['databases'].append(info)
for path in sorted(root.rglob('*audit.json')):
    for entry in json.loads(path.read_text()):
        status=entry['result']['status'];report['boundary_decisions'][status]=report['boundary_decisions'].get(status,0)+1
        if status=='review':assert entry['before']==entry['after']
assert len(report['databases'])>=23
report['passed']=True
print(json.dumps(report,indent=2))
