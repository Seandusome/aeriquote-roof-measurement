#!/usr/bin/env python3
"""Offline JSON stdin → advisory JSON stdout. Never opens a database or app."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retention_restore_planner import plan_retention


if __name__ == '__main__':
    try:
        result = plan_retention(json.load(sys.stdin))
    except (ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'advisory_only': True, 'error': str(exc),
                          'restore_release_recommended': False}), file=sys.stderr)
        raise SystemExit(2)
    print(json.dumps(result, indent=2, sort_keys=True))
