"""System Design MCP server — ferramentas do chat (cérebro e agentes).

O chat NUNCA escreve direto nos arquivos de dados: ele cria PROPOSTAS via
``system_design_propose`` e o usuário aprova/rejeita pela UI do plugin.
Toda proposta passa pelo inbox — nao existem travas; reescrever e mover de volta e sempre permitido ao usuario.

Dados: <projectsRoot>/<project>/.opencode/system-design/*.json
"""

import json
import os

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # permite importar as funções sem o pacote mcp instalado
    FastMCP = None

from store import (
    decide,
    list_projects,
    load_data,
    propose,
    user_action,
)

PROJECTS_ROOT = os.environ.get("SYSTEM_DESIGN_PROJECTS_ROOT", "/home/guipvi/projetos")

mcp = FastMCP("system-design") if FastMCP else None


def _ok(**kwargs):
    return {"ok": True, **kwargs}


def _err(message):
    return {"ok": False, "error": str(message)}


def tool_list_projects():
    try:
        return _ok(projects=list_projects(PROJECTS_ROOT))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def tool_get(project, tab):
    try:
        data = load_data(PROJECTS_ROOT, project, {
            "concept": "concept.json", "sprint": "sprint.json",
            "pages": "pages.json", "tables": "tables.json",
            "proposals": "proposals.json",
        }[tab])
        return _ok(project=project, tab=tab, data=data)
    except KeyError:
        return _err(f"tab invalida: {tab!r}")
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def tool_propose(project, tab, target_kind, action, payload_json="{}",
                 target_id=None, reason=""):
    try:
        payload = json.loads(payload_json or "{}")
    except json.JSONDecodeError:
        return _err("payload_json invalido")
    try:
        proposal = propose(PROJECTS_ROOT, project, tab, target_kind,
                           target_id, action, payload, reason)
        return _ok(proposal=proposal,
                   hint="proposta criada como pending; o usuario precisa aprovar pela UI")
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def tool_list_proposals(project, status="pending"):
    try:
        data = load_data(PROJECTS_ROOT, project, "proposals.json")
        items = [p for p in data.get("proposals", [])
                 if status in ("all", p.get("status"))]
        return _ok(project=project, proposals=items)
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def tool_task_update(project, task_id, payload_json="{}"):
    try:
        payload = json.loads(payload_json or "{}")
    except json.JSONDecodeError:
        return _err("payload_json invalido")
    try:
        from store import agent_task_update
        task = agent_task_update(PROJECTS_ROOT, project, task_id, payload)
        return _ok(task=task,
                   hint="atualizado direto (owner=agent); usuario ve em tempo real")
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


if mcp is not None:
    @mcp.tool()
    def system_design_list_projects() -> dict:
        """Lista os projetos com dados de system design.
        Returns: {ok, projects: [projectId, ...]}
        """
        return tool_list_projects()

    @mcp.tool()
    def system_design_get(project: str, tab: str) -> dict:
        """Lê os dados de uma aba (concept|sprint|pages|tables|proposals) de um projeto.
        Args: project: id do projeto. tab: concept|sprint|pages|tables|proposals.
        """
        return tool_get(project, tab)

    @mcp.tool()
    def system_design_propose(project: str, tab: str, target_kind: str,
                              action: str, payload_json: str = "{}",
                              target_id: str = "", reason: str = "") -> dict:
        """Propõe uma mudança (vira pending; o usuário aprova pela UI).
        NUNCA edite os arquivos .opencode/system-design/ diretamente.
        QUALIDADE MINIMA (rejeitado com erro se generico): `concept-element`,
        `page` e `table` em `create` exigem `description`/`desc` com 20+ …
        `page` também exige `elements: [{type?, label, content?, order?, snapshotHtml?}]`
        (ao menos 1) para a UI renderir a última versão e permitir comentários;
        `table` também exige `columns: [{name, type?, pk?, nullable?, fk?}]`
        (ao menos 1) — a UI lista os nomes (PK/FK).
        caracteres reais (responsabilidades, regras, onde vive no repo);
        `concept-vision` exige ao menos 1 campo preenchido. Nunca proponha
        titulo + referencia solta.
        ORIGEM IMPLICA TAREFAS (nada avulso): aprova-se pagina, algoritmo,
        elemento, conceito, tabela e relacionamento — tarefas nascem
        indiretamente. `concept-element`, `page` e `table` em `create`
        exigem `tasks` ([{title, desc?, priority?, status?}], ao menos 1);
        aprovar a origem cria as tasks na sprint com origem registrada.
        `status` pode vir `executado` com evidencia quando o repo ja executa.
        FORMULARIO: briefs aceitam `questions` ([{question, type?, options?}])
        e `afterAnswer` (executado|solicitacao_testes) — responder tudo move
        sozinho.
        `sprint-task` em `create` e REJEITADO; `update`/`move`/`delete`
        valem para progresso e correcoes.
        Args:
            project: id do projeto. tab: concept|sprint|pages|tables.
            target_kind: concept-element|sprint-task|page|page-element|page-comment|table|table-column|relation.
            action: create|update|delete|move|comment.
            payload_json: objeto JSON com os campos da mudança.
            target_id: id do alvo (vazio para create).
            reason: motivo da mudança.
        """
        return tool_propose(project, tab, target_kind, action, payload_json,
                            target_id or None, reason)

    @mcp.tool()
    def system_design_list_proposals(project: str, status: str = "pending") -> dict:
        """Lista propostas (pending|approved|rejected|all) de um projeto."""
        return tool_list_proposals(project, status)

    @mcp.tool()
    def system_design_task_update(project: str, task_id: str,
                                  payload_json: str = "{}") -> dict:
        """Edita DIRETO uma task com owner=agent (sem proposta).
        Vale title/desc/priority(1-10)/owner/status com a matriz: para
        aguardando_aprovacao só de solicitacao_testes; de aguardando só o
        usuário sai (para executado); solicitacao_testes só parte de
        executado. Tarefa com owner=user: use system_design_propose.
        Args:
            project: id do projeto. task_id: id da tarefa.
            payload_json: objeto JSON parcial com os campos.
        """
        return tool_task_update(project, task_id, payload_json)


if __name__ == "__main__":
    if mcp is None:
        raise SystemExit("pacote 'mcp' nao instalado")
    mcp.run()
