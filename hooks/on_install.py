#!/usr/bin/env python3
"""Hook on_install do plugin system-design.

Os dados do plugin vivem por projeto
(<projeto>/.opencode/system-design/) e são criados sob demanda pela UI e
pelas ferramentas MCP, então a instalação não precisa semear nada global.
Este hook apenas valida o manifesto.
"""

import json
import os
import sys

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    manifest_path = os.path.join(PLUGIN_DIR, "plugin.json")
    try:
        with open(manifest_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"system-design on_install: manifesto invalido: {exc}")
        return 1
    for field in ("id", "name", "version", "description"):
        if not manifest.get(field):
            print(f"system-design on_install: campo ausente: {field}")
            return 1
    print(f"system-design on_install: {manifest['id']} v{manifest['version']} ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
