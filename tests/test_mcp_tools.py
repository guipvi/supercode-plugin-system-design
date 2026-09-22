"""Testes das ferramentas MCP (sem exigir o pacote mcp instalado)."""

import pytest

import mcp_server


@pytest.fixture
def root(tmp_path, monkeypatch):
    base = tmp_path / "projetos"
    base.mkdir()
    (base / "demo").mkdir()
    monkeypatch.setattr(mcp_server, "PROJECTS_ROOT", str(base))
    return str(base)


def test_tools_exist_without_mcp_package():
    assert callable(mcp_server.tool_list_projects)
    assert callable(mcp_server.tool_get)
    assert callable(mcp_server.tool_propose)
    assert callable(mcp_server.tool_list_proposals)


def test_list_projects(root):
    out = mcp_server.tool_list_projects()
    assert out["ok"] is True
    assert "demo" in out["projects"]


def test_get_invalid_tab(root):
    out = mcp_server.tool_get("demo", "nope")
    assert out["ok"] is False


def test_propose_and_list(root):
    import store
    store.user_action(root, "demo", "sprint", "sprint-task", None, "create", {"title": "T"})
    task = store.load_data(root, "demo", store.SPRINT_FILE)["tasks"][0]
    out = mcp_server.tool_propose("demo", "sprint", "sprint-task", "move",
                                  '{"status": "doing"}', task["id"], "começar")
    assert out["ok"] is True
    assert out["proposal"]["status"] == "pending"
    # mudança ainda não aplicada
    assert store.load_data(root, "demo", store.SPRINT_FILE)["tasks"][0]["status"] == "backlog"
    lst = mcp_server.tool_list_proposals("demo", "pending")
    assert lst["ok"] is True
    assert len(lst["proposals"]) == 1


def test_propose_standalone_task_rejected(root):
    out = mcp_server.tool_propose("demo", "sprint", "sprint-task", "create",
                                  '{"title": "Fazer X"}', None, "")
    assert out["ok"] is False
    assert "aceitas a parte" in out["error"]


def test_propose_package_accepted(root):
    out = mcp_server.tool_propose(
        "demo", "concept", "concept-element", "create",
        '{"kind": "page", "title": "Home", '
        '"description": "Pagina inicial publica do marketplace", '
        '"tasks": [{"title": "Montar hero"}]}', None, "pacote")
    assert out["ok"] is True
    assert out["proposal"]["status"] == "pending"


def test_propose_bad_payload_json(root):
    out = mcp_server.tool_propose("demo", "sprint", "sprint-task", "move", "{oops", None, "")
    assert out["ok"] is False


def test_propose_traversal_rejected(root):
    out = mcp_server.tool_propose("../x", "sprint", "sprint-task", "move", "{}", None, "")
    assert out["ok"] is False


def test_task_update_direct_and_matrix(root):
    import store
    t = store.user_action(root, "demo", "sprint", "sprint-task", None, "create",
                          {"title": "T", "desc": "x"})
    out = mcp_server.tool_task_update("demo", t["id"], '{"status": "doing", "priority": 9}')
    assert out["ok"] is True and out["task"]["priority"] == 9
    bad = mcp_server.tool_task_update("demo", t["id"], '{"status": "solicitacao_testes"}')
    assert bad["ok"] is False
    store.user_action(root, "demo", "sprint", "sprint-task", t["id"], "update", {"owner": "user"})
    bad2 = mcp_server.tool_task_update("demo", t["id"], '{"title": "hack"}')
    assert bad2["ok"] is False
