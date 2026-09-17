"""Testes da camada de dados e regras de permissão (store.py)."""

import json
import os

import pytest

import store


@pytest.fixture
def root(tmp_path):
    base = tmp_path / "projetos"
    base.mkdir()
    (base / "demo").mkdir()
    return str(base)


PROJ = "demo"


def test_project_id_rejects_traversal(root):
    for bad in ("..", "../x", "a/b", "a\\b", "", ".", "x" * 82, "するために"):
        with pytest.raises(ValueError):
            store.project_data_dir(root, bad)


def test_data_file_allowlist(root):
    with pytest.raises(ValueError):
        store.data_file(root, PROJ, "evil.json")
    with pytest.raises(ValueError):
        store.data_file(root, PROJ, "../../x.json")


def test_concept_crud_user(root):
    el = store.user_action(root, PROJ, "concept", "concept-element", None, "create",
                           {"kind": "function", "title": "Checkout", "description": "d", "details": "x"})
    assert el["id"] and el["locked"] is False
    got = store.load_data(root, PROJ, store.CONCEPT_FILE)
    assert len(got["elements"]) == 1
    upd = store.user_action(root, PROJ, "concept", "concept-element", el["id"], "update",
                            {"title": "Checkout v2"})
    assert upd["title"] == "Checkout v2"
    store.user_action(root, PROJ, "concept", "concept-element", el["id"], "delete", {})
    assert store.load_data(root, PROJ, store.CONCEPT_FILE)["elements"] == []


def test_concept_validation(root):
    with pytest.raises(ValueError):
        store.user_action(root, PROJ, "concept", "concept-element", None, "create",
                          {"kind": "nope", "title": "t"})
    with pytest.raises(ValueError):
        store.user_action(root, PROJ, "concept", "concept-element", None, "create",
                          {"kind": "page", "title": "   "})
    with pytest.raises(ValueError):
        store.user_action(root, PROJ, "concept", "concept-element", None, "create",
                          {"kind": "page", "title": "t" * 201})


def test_vision_update(root):
    v = store.user_action(root, PROJ, "concept", "concept-vision", None, "update",
                          {"objective": "vender", "scope": "loja"})
    assert v["objective"] == "vender"
    assert store.load_data(root, PROJ, store.CONCEPT_FILE)["vision"]["scope"] == "loja"


def test_vision_via_proposal_and_approve(root):
    prop = store.propose(root, PROJ, "concept", "concept-vision", None, "update",
                         {"objective": "vender online"}, reason="definir visão")
    assert prop["status"] == "pending"
    out = store.decide(root, PROJ, prop["id"], True)
    assert out["status"] == "approved"
    assert store.load_data(root, PROJ, store.CONCEPT_FILE)["vision"]["objective"] == "vender online"


def test_agent_must_propose_concept_even_unlocked(root):
    # agentes não têm função de escrita direta: só propose() — e propose valida locks
    el = store.user_action(root, PROJ, "concept", "concept-element", None, "create",
                           {"kind": "page", "title": "Home"})
    prop = store.propose(root, PROJ, "concept", "concept-element", el["id"], "update",
                         {"title": "Home v2"}, reason="melhorar")
    assert prop["status"] == "pending"
    # nada aplicado ainda
    assert store.load_data(root, PROJ, store.CONCEPT_FILE)["elements"][0]["title"] == "Home"
    out = store.decide(root, PROJ, prop["id"], True)
    assert out["status"] == "approved"
    assert store.load_data(root, PROJ, store.CONCEPT_FILE)["elements"][0]["title"] == "Home v2"


def test_locked_blocks_agent_propose(root):
    el = store.user_action(root, PROJ, "concept", "concept-element", None, "create",
                           {"kind": "interface", "title": "Header"})
    store.set_lock(root, PROJ, "concept", "concept-element", el["id"], True)
    with pytest.raises(ValueError, match="bloqueado"):
        store.propose(root, PROJ, "concept", "concept-element", el["id"], "update",
                      {"title": "X"}, reason="tentativa")
    # usuário continua podendo editar
    upd = store.user_action(root, PROJ, "concept", "concept-element", el["id"], "update", {"title": "Y"})
    assert upd["title"] == "Y"


def test_lock_only_user(root):
    el = store.user_action(root, PROJ, "concept", "concept-element", None, "create",
                           {"kind": "interface", "title": "T"})
    with pytest.raises(ValueError):
        store.set_lock(root, PROJ, "concept", "concept-element", el["id"], True, by="agent")


def test_decide_only_user(root):
    el = store.user_action(root, PROJ, "concept", "concept-element", None, "create",
                           {"kind": "interface", "title": "T"})
    prop = store.propose(root, PROJ, "concept", "concept-element", el["id"], "update", {"title": "Z"})
    with pytest.raises(ValueError):
        store.decide(root, PROJ, prop["id"], True, by="agent")


def test_lock_after_propose_blocks_approve(root):
    el = store.user_action(root, PROJ, "concept", "concept-element", None, "create",
                           {"kind": "interface", "title": "T"})
    prop = store.propose(root, PROJ, "concept", "concept-element", el["id"], "update", {"title": "Z"})
    store.set_lock(root, PROJ, "concept", "concept-element", el["id"], True)
    with pytest.raises(ValueError, match="travado"):
        store.decide(root, PROJ, prop["id"], True)
    # destravou: aprova
    store.set_lock(root, PROJ, "concept", "concept-element", el["id"], False)
    out = store.decide(root, PROJ, prop["id"], True)
    assert out["status"] == "approved"


def test_reject_proposal(root):
    el = store.user_action(root, PROJ, "concept", "concept-element", None, "create",
                           {"kind": "interface", "title": "T"})
    prop = store.propose(root, PROJ, "concept", "concept-element", el["id"], "update", {"title": "Z"})
    out = store.decide(root, PROJ, prop["id"], False)
    assert out["status"] == "rejected"
    assert store.load_data(root, PROJ, store.CONCEPT_FILE)["elements"][0]["title"] == "T"


def test_sprint_flow(root):
    t = store.user_action(root, PROJ, "sprint", "sprint-task", None, "create",
                          {"title": "Login", "priority": "alta"})
    assert t["status"] == "backlog"
    store.user_action(root, PROJ, "sprint", "sprint-task", t["id"], "move", {"status": "doing"})
    assert store.load_data(root, PROJ, store.SPRINT_FILE)["tasks"][0]["status"] == "doing"
    with pytest.raises(ValueError):
        store.user_action(root, PROJ, "sprint", "sprint-task", t["id"], "move", {"status": "qa"})
    store.set_lock(root, PROJ, "sprint", "sprint-task", t["id"], True)
    with pytest.raises(ValueError, match="bloqueada"):
        store.propose(root, PROJ, "sprint", "sprint-task", t["id"], "move", {"status": "done"})


def test_pages_comments_and_lock(root):
    pg = store.user_action(root, PROJ, "pages", "page", None, "create",
                           {"name": "Checkout", "route": "/checkout"})
    el = store.user_action(root, PROJ, "pages", "page-element", None, "create",
                           {"pageId": pg["id"], "type": "botao", "label": "Pagar", "content": "CTA"})
    c = store.user_action(root, PROJ, "pages", "page-comment", el["id"], "comment",
                          {"elementId": el["id"], "author": "você", "text": "aumentar contraste"})
    assert c["text"] == "aumentar contraste"
    store.set_lock(root, PROJ, "pages", "page-element", el["id"], True)
    with pytest.raises(ValueError, match="bloqueado"):
        store.propose(root, PROJ, "pages", "page-element", el["id"], "update",
                      {"pageId": pg["id"], "label": "X"})
    # comentário em elemento travado continua permitido (comentário não é edição de design)
    c2 = store.user_action(root, PROJ, "pages", "page-comment", el["id"], "comment",
                           {"elementId": el["id"], "text": "ok"})
    assert c2["id"]


def test_tables_fk_and_locks(root):
    users = store.user_action(root, PROJ, "tables", "table", None, "create", {"name": "users"})
    store.user_action(root, PROJ, "tables", "table-column", None, "create",
                      {"tableId": users["id"], "name": "id", "type": "uuid", "pk": True})
    orders = store.user_action(root, PROJ, "tables", "table", None, "create", {"name": "orders"})
    store.user_action(root, PROJ, "tables", "table-column", None, "create",
                      {"tableId": orders["id"], "name": "id", "type": "uuid", "pk": True})
    store.user_action(root, PROJ, "tables", "table-column", None, "create",
                      {"tableId": orders["id"], "name": "user_id", "type": "uuid",
                       "fk": {"table": "users", "column": "id"}})
    with pytest.raises(ValueError):
        store.user_action(root, PROJ, "tables", "table-column", None, "create",
                          {"tableId": orders["id"], "name": "bad", "fk": {"table": "nope", "column": "id"}})
    rel = store.user_action(root, PROJ, "tables", "relation", None, "create",
                            {"fromTable": "orders", "fromColumn": "user_id",
                             "toTable": "users", "toColumn": "id", "cardinality": "1:N"})
    assert rel["cardinality"] == "1:N"
    # excluir tabela referenciada deve falhar
    with pytest.raises(ValueError, match="referenciada"):
        store.user_action(root, PROJ, "tables", "table", users["id"], "delete", {})
    store.set_lock(root, PROJ, "tables", "relation", rel["id"], True)
    with pytest.raises(ValueError, match="bloqueada"):
        store.propose(root, PROJ, "tables", "relation", rel["id"], "delete", {})


def test_duplicate_names_rejected(root):
    store.user_action(root, PROJ, "tables", "table", None, "create", {"name": "users"})
    with pytest.raises(ValueError, match="ja existe"):
        store.user_action(root, PROJ, "tables", "table", None, "create", {"name": "Users"})


def test_corrupt_json_rejected(root):
    path = store.data_file(root, PROJ, store.SPRINT_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{invalido", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON invalido"):
        store.load_data(root, PROJ, store.SPRINT_FILE)


def test_size_limit_enforced(root):
    big = "x" * (store.MAX_FILE_BYTES + 1)
    path = store.data_file(root, PROJ, store.SPRINT_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "tasks": [], "pad": big}), encoding="utf-8")
    with pytest.raises(ValueError, match="tamanho maximo"):
        store.load_data(root, PROJ, store.SPRINT_FILE)


def test_xss_payload_stored_neutrally(root):
    evil = "<script>alert(1)</script><img src=x onerror=alert(2)>"
    el = store.user_action(root, PROJ, "concept", "concept-element", None, "create",
                           {"kind": "interface", "title": evil, "description": evil})
    raw = store.data_file(root, PROJ, store.CONCEPT_FILE).read_text(encoding="utf-8")
    assert evil in raw  # armazenamento é neutro; a neutralização é na renderização (esc())
    assert el["title"] == evil
