"""Testes estáticos da UI (ui.html autocontida e segura)."""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI = os.path.join(ROOT, "ui.html")


def read_ui():
    with open(UI, encoding="utf-8") as fh:
        return fh.read()


def test_ui_exists_and_self_contained():
    html = read_ui()
    assert "<script>" in html and "</script>" in html
    # sem dependências locais externas: tudo inline (só o GrapesJS via CDN sob demanda)
    assert 'src="http' not in html.replace("cdn.jsdelivr.net/npm/grapesjs", "")
    assert "href=\"http" not in html.replace("cdn.jsdelivr.net/npm/grapesjs", "")


def test_esc_helper_present():
    html = read_ui()
    assert re.search(r"const esc\s*=", html), "função esc() ausente"


def test_no_dangerous_sinks():
    html = read_ui()
    assert "eval(" not in html
    assert "document.write" not in html
    assert "new Function(" not in html


def test_user_fields_escaped_in_templates():
    html = read_ui()
    # campos vindos de usuário/agente precisam passar por esc() nas interpolações
    for field in ("e.title", "t.title", "c.text", "p.name", "t.name", "c.name", "el.label"):
        assert f"esc({field}" in html or f"esc(({field}" in html, f"campo sem esc(): {field}"


def test_srcdoc_escaped():
    html = read_ui()
    assert 'srcdoc="${esc(' in html, "srcdoc precisa interpolar com esc()"


def test_grapes_pinned_and_on_demand():
    html = read_ui()
    assert "cdn.jsdelivr.net/npm/grapesjs@0.22.6" in html
    assert html.count("loadGrapes()") >= 1
    # loadGrapes só é chamado dentro de openVisualEditor (clique explícito)
    assert "openVisualEditor" in html


def test_approve_disabled_when_locked():
    html = read_ui()
    assert "Destrave o alvo para aprovar" in html
    assert "data-approve" in html


def test_project_id_validated_client_side():
    html = read_ui()
    assert "PROJECT_RE" in html
    assert "/projects/index" in html


def test_four_tabs_present():
    html = read_ui()
    for tab in ("concept", "sprint", "pages", "tables"):
        assert f'data-tab="{tab}"' in html, f"aba ausente: {tab}"
    assert "projeto" in html.lower() and "sprint" in html.lower()


def test_project_selector_on_top():
    html = read_ui()
    assert 'id="project"' in html
    # seletor aparece antes das abas no documento
    assert html.index('id="project"') < html.index('id="tabs"')


def test_no_secrets_hardcoded():
    html = read_ui()
    assert "ghp_" not in html
    assert "gsk_" not in html
    assert "sk-ant-" not in html
    assert "METRICS_API_TOKEN" not in html
