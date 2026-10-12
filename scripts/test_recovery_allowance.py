"""Test-service allowances must not change production trial enforcement."""
import ast
import os
from pathlib import Path
from unittest.mock import patch

tree = ast.parse(Path('app.py').read_text())
functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
             and n.name in ('is_recovery_test_service', 'consume_property_lookup')]
class DB:
    def execute(self, sql, params):
        self.sql = sql
        return self
    def fetchone(self):
        if 'FROM dealers ' in self.sql:
            return dict(dealer_name='Test Customer', email='test@example.invalid', status='active', lookup_limit=3)
        return dict(property_lookups=3)
    def close(self): pass
scope = dict(os=os, DATABASE_URL='postgresql://test', session={}, estimate_db=DB)
exec(compile(ast.Module(body=functions, type_ignores=[]), 'app.py', 'exec'), scope)
for env, allowed in [({}, False),
                     ({'RENDER_SERVICE_ID': 'srv-db5a2g5ckfvc739fui70'}, True),
                     ({'RENDER_EXTERNAL_HOSTNAME': 'aeriquote-commercial-test.onrender.com'}, True),
                     ({'RENDER_EXTERNAL_HOSTNAME': 'aeriquote-roof-measurement.onrender.com'}, False)]:
    with patch.dict(os.environ, env, clear=True):
        result = scope['consume_property_lookup']('dealer')
        assert result[0] == allowed, (env, result)
print('PASS: named recovery service unrestricted; production exhausted trial stays blocked')
