"""Valida o manifesto e a presença dos arquivos do plugin."""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_manifest():
    with open(os.path.join(ROOT, "plugin.json"), encoding="utf-8") as fh:
        return json.load(fh)


def test_manifest_required_fields():
    m = load_manifest()
    for field in ("id", "name", "version", "description"):
        assert m.get(field), f"campo ausente: {field}"
    assert m["id"] == "system-design"


def test_manifest_capabilities():
    m = load_manifest()
    assert set(m["capabilities"]) == {"agents", "hooks", "instructions", "mcp", "ui"}


def test_manifest_files_exist():
    m = load_manifest()
    assert os.path.isfile(os.path.join(ROOT, m["ui"]["file"]))
    assert os.path.isfile(os.path.join(ROOT, m["instructions_file"]))
    assert os.path.isfile(os.path.join(ROOT, "mcp_server.py"))
    assert os.path.isfile(os.path.join(ROOT, "store.py"))
    assert os.path.isfile(os.path.join(ROOT, "hooks", "on_install.py"))


def test_manifest_version_semver():
    import re
    m = load_manifest()
    assert re.match(r"^\d+\.\d+\.\d+$", m["version"])
