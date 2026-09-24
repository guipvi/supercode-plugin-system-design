"""Garante que o JS da ui.html está ligado corretamente ao HTML (wiring).

Pega a classe mais comum de defeito em página autocontida: referência a
id inexistente, botão sem handler, aba sem render.
"""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI = os.path.join(ROOT, "ui.html")


def parts():
    with open(UI, encoding="utf-8") as fh:
        html = fh.read()
    m = re.search(r"<script>(.*)</script>", html, re.S)
    assert m, "bloco <script> ausente"
    head = html[: m.start()]
    return head, m.group(1)


def test_ids_referenciados_existem():
    head, js = parts()
    # ids estáticos no HTML + ids gerados dinamicamente pelo próprio JS
    # (modais e detalhes renderizados via template string)
    defined = set(re.findall(r'id="([\w-]+)"', head)) | set(
        re.findall(r'id="([\w-]+)"', js)) | set(
        re.findall(r"id='([\w-]+)'", js))
    used = set(re.findall(r"\$\('([\w-]+)'\)", js)) | set(
        re.findall(r'getElementById\("([\w-]+)"\)', js))
    missing = used - defined
    assert not missing, f"ids referenciados mas ausentes no HTML: {sorted(missing)}"


def test_data_actions_tem_binding():
    head, js = parts()
    in_html = set(re.findall(r"data-([\w-]+)=", head))
    # bindings dinâmicos via querySelectorAll
    bound = set(re.findall(r"querySelectorAll?\('\[data-([\w-]+)", js))
    # atributos lidos via dataset.* também contam como tratados
    read = set(re.findall(r"dataset\.([\w]+)", js))
    for attr in in_html:
        camel = re.sub(r"-(\w)", lambda m: m.group(1).upper(), attr)
        assert attr in bound or camel in read or attr in ("tab", "view"), \
            f"data-{attr} no HTML sem binding no JS"


def test_abas_tem_render():
    _, js = parts()
    for tab, fn in (("concept", "renderConcept"), ("sprint", "renderSprint"),
                    ("pages", "renderPages"), ("tables", "renderTables")):
        assert f"data-tab=\"{tab}\"" in open(UI, encoding="utf-8").read()
        assert f"function {fn}(" in js, f"{fn} ausente"
    assert "function renderInbox(" in js
    assert "function renderAll(" in js
    assert "boot();" in js


def test_apply_cobre_targets_de_proposta():
    _, js = parts()
    for kind in ("concept-element", "sprint-task", "page", "page-element",
                 "page-comment", "table", "table-column", "relation",
                 "concept-vision"):
        assert kind in js, f"apply sem cobertura para {kind}"


def test_grapes_somente_sob_clique():
    _, js = parts()
    assert "openVisualEditor" in js
    # loadGrapes não pode ser chamado no boot
    boot = js[js.index("async function boot()"):]
    assert "loadGrapes" not in boot


def _fn_body(js, name):
    start = js.index(f"function {name}(")
    end = js.index("\n}", start)
    return js[start:end]


def test_spawn_implied_tasks_preserva_forms():
    """Regressão v1.9.14: aprovar origem com tasks embutidas precisa levar
    questions/owner/afterAnswer para a sprint. Antes o spawn descartava esses
    campos e os formulários do usuário sumiam da sprint (só restavam em
    proposals.json)."""
    _, js = parts()
    for fn in ("vTaskBrief", "spawnImpliedTasksUI"):
        body = _fn_body(js, fn)
        for field in ("questions", "owner", "afterAnswer"):
            assert field in body, f"{fn} descarta {field}"
    spawn = _fn_body(js, "spawnImpliedTasksUI")
    assert "vQuestion" in spawn, "spawn precisa validar as perguntas embutidas"
