"""Garante que as instruções dos agentes impõem o fluxo de permissão da UI."""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_instructions():
    with open(os.path.join(ROOT, "instructions.md"), encoding="utf-8") as fh:
        return fh.read()


def test_forbids_direct_writes():
    text = read_instructions()
    assert "NUNCA" in text
    assert "system-design" in text and ".json" in text


def test_concept_requires_proposal():
    text = read_instructions()
    assert "conceitual" in text.lower()
    assert "proposta" in text.lower()


def test_no_locks_rewrite_is_control():
    text = read_instructions()
    assert "locked" not in text
    assert "reescrever" in text


def test_indirect_tasks_and_matrix():
    text = read_instructions()
    for token in ("aguardando_aprovacao", "solicitacao_testes", "system_design_task_update",
                  "owner", "1 (baixo) a 10", "tempo real"):
        assert token in text, f"instrucao ausente: {token}"


def test_only_user_decides():
    text = read_instructions().lower()
    assert "usuário" in text or "usuario" in text
    assert "aprov" in text


def test_tutorial_rule():
    text = read_instructions()
    for token in ("tutorial", "[texto](https://", "owner=user", "ver"):
        assert token in text, f"regra tutorial ausente: {token}"


def test_execution_updates_status_directly():
    """Conforme executa, o agente move o card DIRETO (task_update, sem
    aguardar aprovação) e usa a matriz real — nunca o status 'done'."""
    text = read_instructions()
    start = text.index("## Execução e status")
    end = text.index("\n## ", start + 1)
    sec = text[start:end]
    assert "system_design_task_update" in sec
    assert '{"status":"doing"}' in sec
    assert '{"status":"executado"}' in sec
    assert '{"status":"backlog"}' in sec
    assert "aguarde aprovação" not in sec
    assert "backlog|doing|done" not in text
    assert "`done`" not in text
    # exceção única da regra de ouro: task_update direto
    assert "Exceção única" in text


def test_columns_in_create():
    text = read_instructions()
    assert "columns: [{name" in text
    assert "exige" in text.lower() or "EXIGE" in text


def test_page_elements_in_create():
    text = read_instructions()
    assert "elements: [{type?" in text or "elements: [{type" in text
    assert "ao menos 1 elemento" in text or "ao menos 1" in text
