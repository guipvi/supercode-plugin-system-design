"""System Design MCP server — ferramentas do chat (cérebro e agentes).

O chat NUNCA escreve direto nos arquivos de dados: ele cria PROPOSTAS via
``system_design_propose`` e o usuário aprova/rejeita pela UI do plugin.
Alvos com ``locked=true`` rejeitam propostas com erro.

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
        Alvos com `locked=true` rejeitam propostas com erro.
        QUALIDADE MINIMA (rejeitado com erro se generico): `concept-element`,
        `sprint-task` e `page` em `create` exigem `description`/`desc` com 20+
        caracteres reais (responsabilidades, regras, onde vive no repo);
        `concept-vision` exige ao menos 1 campo preenchido. Nunca proponha
        titulo + referencia solta.
        CONCEITO IMPLICA TAREFAS: `concept-element` em `create` exige
        `tasks` ([{title, desc?, priority?, status?}], ao menos 1) — aprovar
        o conceito cria as tasks na sprint (sem carta separada). `status`
        pode vir `done` com evidencia quando o repo ja executa. Nunca
        proponha sprint-task avulsa para trabalho de um conceito.
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


if __name__ == "__main__":
    if mcp is None:
        raise SystemExit("pacote 'mcp' nao instalado")
    mcp.run()
