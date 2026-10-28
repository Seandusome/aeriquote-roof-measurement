"""Run touch QA with our disposable server in the same network namespace.

Requires installed Playwright Chromium and the repository's browser-test Node deps.
Never uses deployed credentials, DATABASE_URL, or external imagery providers.
"""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[1]
env = dict(os.environ, DATABASE_URL="", PYTHONDONTWRITEBYTECODE="1")
try:
    with socket.create_connection(("127.0.0.1", 8765), timeout=0.2):
        raise RuntimeError("Port 8765 is already in use; refusing to test an unknown server")
except OSError:
    pass

with tempfile.TemporaryFile(mode="w+") as log:
    server = subprocess.Popen(
        [sys.executable, "scripts/prelaunch_browser_server.py"],
        cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    try:
        for _ in range(100):
            if server.poll() is not None:
                raise RuntimeError("Disposable fixture server exited before readiness")
            try:
                with socket.create_connection(("127.0.0.1", 8765), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("Disposable fixture server did not become ready")
        result = subprocess.run(
            ["node", "scripts/test_linear_touch_browser.cjs"],
            cwd=root, env=env, timeout=240,
        )
        sys.exit(result.returncode)
    finally:
        server.terminate()
        server.wait(timeout=10)
