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


def test_no_locks_in_ui():
    html = read_ui()
    for token in ("data-lock", "lockTag", "lockBtn", "bindLocks",
                  "toggleLock", "travad", "bloquead", "\U0001f512"):
        assert token not in html and token not in html.lower(), f"resto de trava: {token}"


def test_proposals_tab_and_deck():
    html = read_ui()
    assert 'data-tab="proposals"' in html
    assert "btn-yes" in html and "btn-no" in html
    assert "tab-proposals-badge" in html


def test_sprint_filters_owner_prio():
    html = read_ui()
    for eid in ("s-search", "s-origin", "s-priority", "sprint-count", "s-owner"):
        assert f'id="{eid}"' in html, f"filtro ausente: {eid}"
    assert "btn-add-task" not in html
    assert "data-exec-t" not in html


def test_sprint_dnd_and_realtime():
    html = read_ui()
    assert 'draggable="true"' in html
    assert "bindSprintDnd" in html
    assert "mv-select" in html
    assert "setInterval(pokeRealtime" in html
    for st in ("executado", "solicitacao_testes", "aguardando_aprovacao"):
        assert st in html


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


def test_view_button_and_modal():
    html = read_ui()
    assert "data-view-t=" in html
    assert "function viewTask(" in html
    assert "descHtml(" in html and "linkify(" in html
    assert "target=\"_blank\"" in html


def test_table_list_shows_column_names():
    html = read_ui()
    assert "validateEmbeddedColumns" in html
    assert "c.name" in html
    assert "data-open-t=" in html


def test_page_preview_uses_latest_and_comments():
    html = read_ui()
    assert "function renderPageDetail(" in html
    assert "snapshotHtml" in html
    assert "pvBlockVisual" in html
    assert "pageOrdered" in html
    assert "data-c-send=" in html
    assert "PvSelected" in html
    assert "validateEmbeddedElements" in html


def test_page_simulation_and_page_level_comments():
    html = read_ui()
    # simulação da página final: iframe único monta os elementos na ordem
    assert "function buildSimDoc(" in html
    assert "'allow-scripts'" in html or '"allow-scripts"' in html
    assert "sim-block" in html
    assert "postMessage" in html
    # comentário no resultado final da página (pageId), além do elemento
    assert "function sendPageComment(" in html
    assert "data-pc-send=" in html
    assert "pageCommentsHtml" in html
    assert "{pageId:pid,author,text}" in html


def test_simulation_uses_real_design_html_and_css():
    """A simulação precisa refletir o resultado final: CSS do editor visual
    é salvo (getCss) e recarregado (splitSnap/setStyle); fallback estilizado."""
    html = read_ui()
    assert "function splitSnap(" in html
    assert "ed.getCss" in html
    assert "ed.setStyle" in html
    assert "sim-fb" in html
    # sem padding no bloco (layout igual ao final) e placeholder claro de imagem
    assert "padding:0;outline:2px dashed transparent" in html
    assert "#1a2130" not in html  # fundo escuro de painel não pode vazar pro iframe


def test_page_preview_html_real_capture():
    """previewHtml (captura do resultado real) tem prioridade na simulação."""
    html = read_ui()
    assert "function buildPreviewDoc(" in html
    assert "function simBridgeJS(" in html
    assert "pg.previewHtml?buildPreviewDoc(pg):buildSimDoc(ordered)" in html
    assert "id=\"m-preview\"" in html
    assert "previewHtml:$('m-preview').value" in html
    assert "resultado real capturado" in html
    assert "o.previewHtml=vStr" in html


def test_preview_capture_elements_are_clickable():
    """Nós anotados com data-sim-id no preview real: clique seleciona
    (postMessage select) e o bridge destaca hover/seleção em qualquer nó,
    não só em .sim-block da simulação montada."""
    html = read_ui()
    assert "closest('[data-sim-id]')" in html
    assert "querySelectorAll('[data-sim-id]')" in html
    assert "[data-sim-id]:hover" in html
    assert "[data-sim-id].sim-selected" in html
