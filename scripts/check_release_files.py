"""Fail early when an incomplete source tree cannot be deployed on Render.

Read-only: does not import the application, connect to storage or modify files.
"""
import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    'app.py', 'requirements.txt', 'account_credits.py', 'account_recovery.py',
    'activation_metrics.py', 'measurement_integrity.py', 'pricing_integrity.py',
    'property_address.py', 'property_sessions.py', 'saved_estimate_edit.py',
    'storage_checks.py', 'support_center.py', 'support_inbound.py',
    'site/index.html', 'site/pricing.html', 'site/styles.css',
    'site/assets/aeriquote-logo.png',
    'qa_vector_pdf.js', 'qa_assets/DejaVuSans.ttf', 'qa_assets/DejaVu-LICENSE.txt',
)

def errors(root):
    result = []
    for name in REQUIRED:
        path = root / name
        if not path.is_file() or not path.stat().st_size:
            result.append('Missing or empty release file: ' + name)
        elif path.suffix == '.py':
            try:
                ast.parse(path.read_text(encoding='utf-8'), filename=name)
            except SyntaxError as exc:
                result.append(f'Invalid Python in {name}: {exc}')
    return result

if __name__ == '__main__':
    failures = errors(ROOT)
    for failure in failures:
        print('FAIL: ' + failure)
    if failures:
        sys.exit(1)
    print(f'PASS: {len(REQUIRED)} required deployment files are present and Python parses')
