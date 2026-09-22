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
    assert el["id"]
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
    # agentes não têm função de escrita direta: só propose()
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


def test_no_locks_propose_always_allowed(root):
    # sem travas: propose vale para qualquer alvo, o controle é o inbox
    el = store.user_action(root, PROJ, "concept", "concept-element", None, "create",
                           {"kind": "interface", "title": "Header"})
    prop = store.propose(root, PROJ, "concept", "concept-element", el["id"], "update",
                         {"title": "X"}, reason="tentativa")
    assert prop["status"] == "pending"
    upd = store.user_action(root, PROJ, "concept", "concept-element", el["id"], "update", {"title": "Y"})
    assert upd["title"] == "Y"


def test_decide_only_user(root):
    el = store.user_action(root, PROJ, "concept", "concept-element", None, "create",
                           {"kind": "interface", "title": "T"})
    prop = store.propose(root, PROJ, "concept", "concept-element", el["id"], "update", {"title": "Z"})
    with pytest.raises(ValueError):
        store.decide(root, PROJ, prop["id"], True, by="agent")


def test_approve_applies_without_locks(root):
    el = store.user_action(root, PROJ, "concept", "concept-element", None, "create",
                           {"kind": "interface", "title": "T"})
    prop = store.propose(root, PROJ, "concept", "concept-element", el["id"], "update", {"title": "Z"})
    out = store.decide(root, PROJ, prop["id"], True)
    assert out["status"] == "approved"
    assert store.load_data(root, PROJ, store.CONCEPT_FILE)["elements"][0]["title"] == "Z"


def test_reject_proposal(root):
    el = store.user_action(root, PROJ, "concept", "concept-element", None, "create",
                           {"kind": "interface", "title": "T"})
    prop = store.propose(root, PROJ, "concept", "concept-element", el["id"], "update", {"title": "Z"})
    out = store.decide(root, PROJ, prop["id"], False)
    assert out["status"] == "rejected"
    assert store.load_data(root, PROJ, store.CONCEPT_FILE)["elements"][0]["title"] == "T"


def test_sprint_flow(root):
    t = store.user_action(root, PROJ, "sprint", "sprint-task", None, "create",
                          {"title": "Login", "priority": 9})
    assert t["status"] == "backlog"
    store.user_action(root, PROJ, "sprint", "sprint-task", t["id"], "move", {"status": "doing"})
    assert store.load_data(root, PROJ, store.SPRINT_FILE)["tasks"][0]["status"] == "doing"
    with pytest.raises(ValueError):
        store.user_action(root, PROJ, "sprint", "sprint-task", t["id"], "move", {"status": "qa"})
    # sem travas: progresso via proposta funciona (doing/done)
    prop = store.propose(root, PROJ, "sprint", "sprint-task", t["id"], "move", {"status": "executado"})
    assert prop["status"] == "pending"


def test_pages_comments(root):
    pg = store.user_action(root, PROJ, "pages", "page", None, "create",
                           {"name": "Checkout", "route": "/checkout"})
    el = store.user_action(root, PROJ, "pages", "page-element", None, "create",
                           {"pageId": pg["id"], "type": "botao", "label": "Pagar", "content": "CTA"})
    c = store.user_action(root, PROJ, "pages", "page-comment", el["id"], "comment",
                          {"elementId": el["id"], "author": "você", "text": "aumentar contraste"})
    assert c["text"] == "aumentar contraste"
    prop = store.propose(root, PROJ, "pages", "page-element", el["id"], "update",
                         {"pageId": pg["id"], "label": "X"})
    assert prop["status"] == "pending"
    c2 = store.user_action(root, PROJ, "pages", "page-comment", el["id"], "comment",
                           {"elementId": el["id"], "text": "ok"})
    assert c2["id"]


def test_page_level_comment_on_final_result(root):
    """Comentário no RESULTADO FINAL da página (pageId), não no elemento."""
    pg = store.user_action(root, PROJ, "pages", "page", None, "create",
                           {"name": "Home", "route": "/"})
    assert pg["comments"] == []
    c = store.user_action(root, PROJ, "pages", "page-comment", pg["id"], "comment",
                          {"pageId": pg["id"], "author": "você",
                           "text": "banner muito alto no topo"})
    assert c["text"] == "banner muito alto no topo"
    got = store.load_data(root, PROJ, store.PAGES_FILE)
    assert got["pages"][0]["comments"][0]["text"] == "banner muito alto no topo"
    # sem elementId: target_id sendo o id da página também resolve
    c2 = store.user_action(root, PROJ, "pages", "page-comment", pg["id"], "comment",
                           {"pageId": pg["id"], "text": "ok"})
    assert c2["id"]
    assert len(got["pages"][0]["comments"]) == 1  # dado antigo ainda não recarregado
    got2 = store.load_data(root, PROJ, store.PAGES_FILE)
    assert len(got2["pages"][0]["comments"]) == 2
    # proposta de agente comentando a página passa no dry-run e fica pending
    prop = store.propose(root, PROJ, "pages", "page-comment", pg["id"], "comment",
                         {"pageId": pg["id"], "text": "CTA principal deveria ser verde"},
                         reason="feedback no resultado final da Home")
    assert prop["status"] == "pending"
    # página inexistente com pageId explícito → erro claro
    with pytest.raises(ValueError, match="pagina nao encontrada"):
        store.user_action(root, PROJ, "pages", "page-comment", pg["id"], "comment",
                          {"pageId": "p-que-nao-existe", "text": "x"})


def test_page_preview_html_roundtrip(root):
    """previewHtml: captura estática do resultado final (HTML+CSS inline)."""
    pg = store.user_action(root, PROJ, "pages", "page", None, "create",
                           {"name": "Login", "route": "/login",
                            "previewHtml": "<!doctype html><html><head><style>.a{}</style>"
                                           "</head><body><main>Entrar</main></body></html>"})
    assert pg["previewHtml"].startswith("<!doctype html>")
    got = store.load_data(root, PROJ, store.PAGES_FILE)
    assert "Entrar" in got["pages"][0]["previewHtml"]
    store.user_action(root, PROJ, "pages", "page", pg["id"], "update",
                      {"previewHtml": "<html><body>sem css</body></html>"})
    got2 = store.load_data(root, PROJ, store.PAGES_FILE)
    assert got2["pages"][0]["previewHtml"] == "<html><body>sem css</body></html>"
    # update sem previewHtml não apaga o existente
    store.user_action(root, PROJ, "pages", "page", pg["id"], "update", {"desc": "ok"})
    got3 = store.load_data(root, PROJ, store.PAGES_FILE)
    assert got3["pages"][0]["previewHtml"] == "<html><body>sem css</body></html>"
    assert got3["pages"][0]["desc"] == "ok"
    # acima do limite → erro
    with pytest.raises(ValueError):
        store.user_action(root, PROJ, "pages", "page", pg["id"], "update",
                          {"previewHtml": "x" * (store.MAX_PREVIEW + 1)})


def test_tables_fk(root):
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
    # sem travas: propor delete de relacao funciona
    prop = store.propose(root, PROJ, "tables", "relation", rel["id"], "delete", {})
    assert prop["status"] == "pending"


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


def test_propose_rejects_generic_concept_element(root):
    with pytest.raises(ValueError, match="generica"):
        store.propose(root, PROJ, "concept", "concept-element", None, "create",
                      {"kind": "interface", "title": "Frontend Web"})
    with pytest.raises(ValueError, match="generica"):
        store.propose(root, PROJ, "concept", "concept-element", None, "create",
                      {"kind": "interface", "title": "X", "description": "curta"})
    with pytest.raises(ValueError, match="implica tarefas"):
        store.propose(root, PROJ, "concept", "concept-element", None, "create",
                      {"kind": "interface", "title": "Frontend Web",
                       "description": "Responsavel pelas 26 rotas publicas em client/src com Tailwind"})
    ok = store.propose(root, PROJ, "concept", "concept-element", None, "create",
                       {"kind": "interface", "title": "Frontend Web",
                        "description": "Responsavel pelas 26 rotas publicas em client/src com Tailwind",
                        "tasks": [{"title": "Mapear rotas", "desc": "Listar as 26 rotas wouter"}]})
    assert ok["status"] == "pending"


def test_approve_concept_spawns_tasks(root):
    prop = store.propose(root, PROJ, "concept", "concept-element", None, "create",
                         {"kind": "function", "title": "Checkout",
                          "description": "Fluxo de pagamento ponta a ponta no repo",
                          "tasks": [{"title": "Implementar checkout", "desc": "tRPC + Pagar.me"},
                                    {"title": "Checkout ja auditado", "desc": "webhooks idempotentes vistos em payouts.ts", "status": "executado"}]})
    out = store.decide(root, PROJ, prop["id"], True)
    assert [t["id"] for t in out["spawnedTasks"]]
    tasks = store.load_data(root, PROJ, store.SPRINT_FILE)["tasks"]
    by_title = {t["title"]: t["status"] for t in tasks}
    assert by_title["Implementar checkout"] == "backlog"
    assert by_title["Checkout ja auditado"] == "executado"


def test_approve_concept_dedupes_tasks(root):
    prop = store.propose(root, PROJ, "concept", "concept-element", None, "create",
                         {"kind": "function", "title": "A",
                          "description": "Descricao longa o suficiente aqui",
                          "tasks": [{"title": "Mesma tarefa"}]})
    store.decide(root, PROJ, prop["id"], True)
    prop2 = store.propose(root, PROJ, "concept", "concept-element", None, "create",
                          {"kind": "function", "title": "B",
                           "description": "Outra descricao longa o suficiente",
                           "tasks": [{"title": "Mesma tarefa"}, {"title": "Nova tarefa"}]})
    out2 = store.decide(root, PROJ, prop2["id"], True)
    assert [t["title"] for t in out2["spawnedTasks"]] == ["Nova tarefa"]
    tasks = store.load_data(root, PROJ, store.SPRINT_FILE)["tasks"]
    assert len(tasks) == 2


def test_standalone_tasks_rejected_pages_need_tasks(root):
    # sprint-task avulsa: banida (tarefas nascem de aprovacoes)
    with pytest.raises(ValueError, match="aceitas a parte"):
        store.propose(root, PROJ, "sprint", "sprint-task", None, "create",
                      {"title": "Fazer X", "desc": "Detalhar o fluxo de checkout ponta a ponta"})
    # page sem tasks: generica
    with pytest.raises(ValueError, match="generica"):
        store.propose(root, PROJ, "pages", "page", None, "create",
                      {"name": "Home", "route": "/",
                       "desc": "Pagina inicial publica com proposta de valor",
                       "elements": [{"label": "Hero"}]})
    # page com tasks mas sem elements: generica
    with pytest.raises(ValueError, match="elements"):
        store.propose(root, PROJ, "pages", "page", None, "create",
                      {"name": "Home", "route": "/",
                       "desc": "Pagina inicial publica com proposta de valor",
                       "tasks": [{"title": "Montar hero"}]})
    with pytest.raises(ValueError, match="generica"):
        store.propose(root, PROJ, "concept", "concept-vision", None, "update", {})
    # page com tasks + elements: pacote valido
    ok = store.propose(root, PROJ, "pages", "page", None, "create",
                       {"name": "Home", "route": "/",
                        "desc": "Pagina inicial publica com proposta de valor",
                        "elements": [
                            {"type": "cabecalho", "label": "Hero", "content": "Bem-vindo"},
                            {"type": "botao", "label": "Começar", "order": 1},
                        ],
                        "tasks": [{"title": "Montar hero"}]})
    assert ok["status"] == "pending"
    # table sem tasks: generica
    with pytest.raises(ValueError, match="generica"):
        store.propose(root, PROJ, "tables", "table", None, "create", {"name": "users"})
    # table com tasks mas sem columns: generica
    with pytest.raises(ValueError, match="columns"):
        store.propose(root, PROJ, "tables", "table", None, "create",
                      {"name": "users", "desc": "Usuarios do sistema com email e senha",
                       "tasks": [{"title": "Criar tabela users"}]})
    out = store.decide(root, PROJ, ok["id"], True)
    assert [t["title"] for t in out["spawnedTasks"]] == ["Montar hero"]
    assert store.load_data(root, PROJ, store.SPRINT_FILE)["tasks"][0]["origin"]["tab"] == "pages"
    page = store.load_data(root, PROJ, store.PAGES_FILE)["pages"][0]
    assert [e["label"] for e in page["elements"]] == ["Hero", "Começar"]


def test_approve_table_spawns_with_origin(root):
    prop = store.propose(root, PROJ, "tables", "table", None, "create",
                         {"name": "orders", "desc": "Pedidos do marketplace em geral",
                          "columns": [
                              {"name": "id", "type": "uuid", "pk": True},
                              {"name": "total", "type": "numeric"},
                          ],
                          "tasks": [{"title": "Criar migration orders", "status": "executado", "desc": "migration 0025"}]})
    out = store.decide(root, PROJ, prop["id"], True)
    assert len(out["spawnedTasks"]) == 1
    t = store.load_data(root, PROJ, store.SPRINT_FILE)["tasks"][0]
    assert (t["title"], t["status"]) == ("Criar migration orders", "executado")
    assert t["origin"] == {"tab": "tables", "kind": "table", "id": t["origin"]["id"], "title": "orders"}
    table = store.load_data(root, PROJ, store.TABLES_FILE)["tables"][0]
    assert [c["name"] for c in table["columns"]] == ["id", "total"]


def test_user_direct_create_stays_free(root):
    el = store.user_action(root, PROJ, "concept", "concept-element", None, "create",
                           {"kind": "interface", "title": "Rascunho"})
    assert el["id"]


def test_priority_int_range(root):
    with pytest.raises(ValueError, match="1 a 10"):
        store.user_action(root, PROJ, "sprint", "sprint-task", None, "create",
                          {"title": "X", "priority": 11})
    with pytest.raises(ValueError, match="1 a 10"):
        store.user_action(root, PROJ, "sprint", "sprint-task", None, "create",
                          {"title": "X", "priority": "alta"})
    t = store.user_action(root, PROJ, "sprint", "sprint-task", None, "create",
                          {"title": "X"})
    assert t["priority"] == 5 and t["owner"] == "agent"


def test_move_matrix(root):
    t = store.user_action(root, PROJ, "sprint", "sprint-task", None, "create",
                          {"title": "T"})
    tid = t["id"]
    # agente nao entra em solicitacao direto
    with pytest.raises(ValueError, match="solicitacao_testes"):
        store.agent_task_update(root, PROJ, tid, {"status": "solicitacao_testes"})
    # agente trabalha e conclui
    store.agent_task_update(root, PROJ, tid, {"status": "doing"})
    store.agent_task_update(root, PROJ, tid, {"status": "executado", "desc": "feito"})
    assert store.load_data(root, PROJ, store.SPRINT_FILE)["tasks"][0]["owner"] == "user"
    # usuario solicita testes; agente testa e devolve para aprovacao
    store.user_action(root, PROJ, "sprint", "sprint-task", tid, "move",
                      {"status": "solicitacao_testes"})
    store.agent_task_update(root, PROJ, tid, {"status": "aguardando_aprovacao"})
    # agente nao sai de aguardando; usuario finaliza
    with pytest.raises(ValueError, match="usuário"):
        store.agent_task_update(root, PROJ, tid, {"status": "executado"})
    store.user_action(root, PROJ, "sprint", "sprint-task", tid, "move", {"status": "executado"})
    assert store.load_data(root, PROJ, store.SPRINT_FILE)["tasks"][0]["status"] == "executado"


def test_agent_only_own_tasks(root):
    t = store.user_action(root, PROJ, "sprint", "sprint-task", None, "create",
                          {"title": "T"})
    tid = t["id"]
    store.user_action(root, PROJ, "sprint", "sprint-task", tid, "update", {"owner": "user"})
    with pytest.raises(ValueError, match="usuário"):
        store.agent_task_update(root, PROJ, tid, {"title": "hack"})
    # dono agente: edicao direta ok
    t2 = store.user_action(root, PROJ, "sprint", "sprint-task", None, "create",
                           {"title": "U"})
    out = store.agent_task_update(root, PROJ, t2["id"], {"desc": "andamento", "priority": 8})
    assert out["desc"] == "andamento" and out["priority"] == 8


def test_questions_autoadvance_user(root):
    t = store.user_action(root, PROJ, "sprint", "sprint-task", None, "create",
                          {"title": "Deploy", "questions": ["Qual ambiente?"]})
    assert t["questions"][0]["id"] == "q1" and t["status"] == "backlog"
    store.user_action(root, PROJ, "sprint", "sprint-task", t["id"], "update",
                      {"questions": [{"id": "q1", "question": "Qual ambiente?",
                                      "answer": "VPS"}]})
    got = store.load_data(root, PROJ, store.SPRINT_FILE)["tasks"][0]
    assert got["status"] == "executado" and got["owner"] == "user"
    assert got["questions"][0]["answeredBy"] == "user"


def test_questions_solicitacao_composed(root):
    t = store.user_action(root, PROJ, "sprint", "sprint-task", None, "create",
                          {"title": "Checkout", "afterAnswer": "solicitacao_testes",
                           "questions": [{"question": "Validado?"}]})
    store.user_action(root, PROJ, "sprint", "sprint-task", t["id"], "update",
                      {"questions": [{"id": t["questions"][0]["id"],
                                      "question": "Validado?", "answer": "sim"}]})
    got = store.load_data(root, PROJ, store.SPRINT_FILE)["tasks"][0]
    assert got["status"] == "solicitacao_testes" and got["owner"] == "agent"


def test_agent_answers_stops_at_executado(root):
    t = store.user_action(root, PROJ, "sprint", "sprint-task", None, "create",
                          {"title": "Job", "afterAnswer": "solicitacao_testes",
                           "questions": [{"question": "Rodou?"}]})
    out = store.agent_task_update(root, PROJ, t["id"],
                                  {"questions": [{"id": t["questions"][0]["id"],
                                                  "question": "Rodou?", "answer": "sim"}]})
    assert out["status"] == "executado" and out["owner"] == "user"


def test_incomplete_no_advance_bad_choice(root):
    t = store.user_action(root, PROJ, "sprint", "sprint-task", None, "create",
                          {"title": "P", "questions": [{"question": "A?"},
                                                       {"question": "B?"}]})
    store.user_action(root, PROJ, "sprint", "sprint-task", t["id"], "update",
                      {"questions": [{"id": t["questions"][0]["id"], "question": "A?",
                                      "answer": "x"},
                                     {"id": t["questions"][1]["id"], "question": "B?"}]})
    got = store.load_data(root, PROJ, store.SPRINT_FILE)["tasks"][0]
    assert got["status"] == "backlog"
    import pytest as _pt
    with _pt.raises(ValueError, match="fora das opcoes"):
        store.user_action(root, PROJ, "sprint", "sprint-task", t["id"], "update",
                          {"questions": [{"id": "q9", "question": "C?", "type": "choice",
                                          "options": ["a", "b"], "answer": "z"}]})


def test_table_create_with_columns(root):
    tb = store.user_action(root, PROJ, "tables", "table", None, "create",
                           {"name": "usuarios",
                            "desc": "usuarios do sistema com email e senha",
                            "columns": [
                                {"name": "id", "type": "integer", "pk": True},
                                {"name": "email", "type": "text"},
                                "senha"]})
    assert [c["name"] for c in tb["columns"]] == ["id", "email", "senha"]
    assert tb["columns"][0]["pk"] is True
    got = store.load_data(root, PROJ, store.TABLES_FILE)["tables"][0]
    assert len(got["columns"]) == 3


def test_table_create_columns_dup_rejected(root):
    import pytest as _pt
    with _pt.raises(ValueError, match="ja existe"):
        store.user_action(root, PROJ, "tables", "table", None, "create",
                          {"name": "dup",
                           "desc": "tabela com colunas duplicadas",
                           "columns": ["id", "id"]})


def test_page_create_embedded_elements(root):
    pg = store.user_action(root, PROJ, "pages", "page", None, "create",
                           {"name": "Login", "route": "/login",
                            "desc": "Tela de autenticacao com email e senha",
                            "elements": [
                                {"type": "cabecalho", "label": "Entrar", "order": 0},
                                {"type": "formulario", "label": "Email", "content": "email@x"},
                                {"type": "botao", "label": "Entrar", "order": 2,
                                 "snapshotHtml": "<button>Entrar</button>"},
                            ]})
    assert len(pg["elements"]) == 3
    assert pg["elements"][2]["snapshotHtml"] == "<button>Entrar</button>"
    assert pg["elements"][0]["comments"] == []
    got = store.load_data(root, PROJ, store.PAGES_FILE)["pages"][0]
    assert [e["label"] for e in got["elements"]] == ["Entrar", "Email", "Entrar"]


def test_propose_page_requires_elements_and_table_columns(root):
    import pytest as _pt
    with _pt.raises(ValueError, match="elements"):
        store.propose(root, PROJ, "pages", "page", None, "create",
                      {"name": "P", "desc": "Pagina com descricao real o suficiente",
                       "tasks": [{"title": "t"}]})
    with _pt.raises(ValueError, match="columns"):
        store.propose(root, PROJ, "tables", "table", None, "create",
                      {"name": "t1", "desc": "Tabela com descricao real o suficiente",
                       "tasks": [{"title": "t"}]})
    ok = store.propose(root, PROJ, "pages", "page", None, "create",
                       {"name": "P", "route": "/p",
                        "desc": "Pagina com descricao real o suficiente",
                        "elements": [{"type": "texto", "label": "Corpo"}],
                        "tasks": [{"title": "t"}]})
    assert ok["status"] == "pending"


def test_agent_propose_snapshot_html_applies(root):
    pg = store.user_action(root, PROJ, "pages", "page", None, "create",
                           {"name": "Home", "route": "/",
                            "desc": "Pagina inicial com descricao real",
                            "elements": [{"label": "Hero"}]})
    eid = pg["elements"][0]["id"]
    prop = store.propose(root, PROJ, "pages", "page-element", eid, "update",
                         {"snapshotHtml": "<section class=\"hero\">Oi</section>"},
                         "design visual")
    store.decide(root, PROJ, prop["id"], True)
    got = store.load_data(root, PROJ, store.PAGES_FILE)["pages"][0]["elements"][0]
    assert "hero" in got["snapshotHtml"]


def test_agent_can_backfill_page_elements_via_update(root):
    pg = store.user_action(root, PROJ, "pages", "page", None, "create",
                           {"name": "Vazia", "route": "/vazia",
                            "desc": "Pagina que nasceu sem elementos"})
    assert pg["elements"] == []
    prop = store.propose(root, PROJ, "pages", "page", pg["id"], "update",
                         {"elements": [
                             {"type": "cabecalho", "label": "Titulo"},
                             {"type": "texto", "label": "Corpo", "content": "ok"},
                         ]},
                         "preencher elementos da pagina vazia")
    store.decide(root, PROJ, prop["id"], True)
    got = store.load_data(root, PROJ, store.PAGES_FILE)["pages"][0]
    assert [e["label"] for e in got["elements"]] == ["Titulo", "Corpo"]
