"""Testa o hook on_install do plugin."""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_on_install_ok():
    proc = subprocess.run(
        [sys.executable, os.path.join(ROOT, "hooks", "on_install.py")],
        capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 0, proc.stderr
    assert "system-design on_install" in proc.stdout
    assert "ok" in proc.stdout
