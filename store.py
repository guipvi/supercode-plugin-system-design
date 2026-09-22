"""System Design plugin — camada de dados e regras (contrato compartilhado).

Usado pelo ``mcp_server.py`` (lado dos agentes) e pelos testes automatizados.
A UI (``ui.html``) implementa o mesmo contrato em JavaScript contra a API
de arquivos do supercode; os esquemas e limites abaixo são a referência.

Armazenamento (por projeto, acessível à UI e aos agentes):
    <projectsRoot>/<project>/.opencode/system-design/{concept,sprint,pages,tables,proposals}.json

Regras de permissão:
- O agente NUNCA escreve direto nos dados: ele cria PROPOSTAS (status pending).
- O usuário aprova/rejeita cada proposta pela UI (inbox de propostas).
  desabilita o botão de aprovar até o usuário destravar.
- Edições diretas do usuário (actor="user") sempre são permitidas.
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

DATA_SUBDIR = Path(".opencode") / "system-design"

CONCEPT_FILE = "concept.json"
SPRINT_FILE = "sprint.json"
PAGES_FILE = "pages.json"
TABLES_FILE = "tables.json"
PROPOSALS_FILE = "proposals.json"
DATA_FILES = (CONCEPT_FILE, SPRINT_FILE, PAGES_FILE, TABLES_FILE, PROPOSALS_FILE)

MAX_FILE_BYTES = 512 * 1024

MAX_TITLE = 200
MAX_DESC = 5000
MAX_DETAILS = 20000
MAX_COMMENT = 2000
MAX_REASON = 2000

MAX_ELEMENTS = 500
MAX_TASKS = 1000
MAX_PAGES = 200
MAX_PAGE_ELEMENTS = 200
MAX_COMMENTS = 200
MAX_TABLES = 200
MAX_COLUMNS = 100
MAX_RELATIONS = 500
MAX_PROPOSALS = 1000
MAX_PENDING = 200

PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
ENTITY_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

CONCEPT_KINDS = ("interface", "page", "function", "algorithm")
PRIORITIES = tuple(range(1, 11))
STATUSES = ("backlog", "doing", "executado", "solicitacao_testes", "aguardando_aprovacao")
STATUS_LABELS = {"backlog": "Backlog", "doing": "Executando", "executado": "Executado",
                 "solicitacao_testes": "Solicitação de testes",
                 "aguardando_aprovacao": "Aguardando aprovação"}
OWNERS = ("agent", "user")


def _check_priority(value, what="priority"):
    try:
        iv = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{what} deve ser inteiro de 1 a 10")
    if iv < 1 or iv > 10:
        raise ValueError(f"{what} deve ser inteiro de 1 a 10")
    return iv


def _auto_owner(status):
    """Dono pelo estagio: agent executa, user avalia."""
    if status in ("executado", "aguardando_aprovacao"):
        return "user"
    return "agent"


def _check_move(actor, cur, nxt):
    """Matriz de movimentacao usuario x agente."""
    if cur == nxt:
        return
    if nxt == "solicitacao_testes" and cur != "executado":
        raise ValueError("solicitacao_testes: só a partir de executado")
    if nxt == "aguardando_aprovacao":
        if not (actor == "agent" and cur == "solicitacao_testes"):
            raise ValueError("aguardando_aprovacao: só o agente move, e só de solicitacao_testes")
        return
    if cur == "aguardando_aprovacao":
        if not (actor == "user" and nxt == "executado"):
            raise ValueError("aguardando_aprovacao: só o usuário move, e só para executado")
        return
    if cur == "solicitacao_testes":
        raise ValueError("solicitacao_testes: só o agente move, para aguardando_aprovacao")
    if cur == "executado" and nxt == "solicitacao_testes" and actor != "user":
        raise ValueError("solicitacao de testes: só o usuário solicita")
    return
TABS = ("concept", "sprint", "pages", "tables")
ACTIONS = ("create", "update", "delete", "move", "comment")
PROPOSAL_STATUSES = ("pending", "approved", "rejected")
PAGE_ELEMENT_TYPES = ("texto", "cabecalho", "botao", "formulario", "imagem", "lista", "navegacao", "outro")
COLUMN_TYPES = ("uuid", "text", "integer", "numeric", "boolean", "date", "timestamptz", "jsonb")
CARDINALITIES = ("1:1", "1:N", "N:N")

TARGET_KINDS = (
    "concept-vision",
    "concept-element",
    "sprint-task",
    "page",
    "page-element",
    "page-comment",
    "table",
    "table-column",
    "relation",
)


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def validate_project_id(pid):
    if not isinstance(pid, str) or not PROJECT_ID_RE.match(pid):
        raise ValueError(f"project invalido: {pid!r}")
    if pid in (".", "..") or "/" in pid or "\\" in pid:
        raise ValueError(f"project invalido: {pid!r}")
    return pid


def validate_entity_id(eid, what="id"):
    if not isinstance(eid, str) or not ENTITY_ID_RE.match(eid):
        raise ValueError(f"{what} invalido: {eid!r}")
    return eid


def _check_str(value, what, max_len, required=True, allow_empty=False):
    if value is None:
        if required:
            raise ValueError(f"{what} obrigatorio")
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{what} deve ser texto")
    value = value.strip()
    if required and not allow_empty and not value:
        raise ValueError(f"{what} obrigatorio")
    if len(value) > max_len:
        raise ValueError(f"{what} excede {max_len} caracteres")
    return value


def _check_enum(value, what, allowed, required=True, default=None):
    if value is None:
        if required and default is None:
            raise ValueError(f"{what} obrigatorio")
        return default
    if value not in allowed:
        raise ValueError(f"{what} invalido: {value!r} (esperado um de {', '.join(allowed)})")
    return value



def projects_root(root=None):
    base = Path(root or os.environ.get("SYSTEM_DESIGN_PROJECTS_ROOT", "/home/guipvi/projetos"))
    return base.resolve()


def project_data_dir(root, project):
    validate_project_id(project)
    base = projects_root(root)
    candidate = (base / project / DATA_SUBDIR).resolve()
    # trava anti path-traversal: o dir final precisa estar dentro de base/<project>
    expected = (base / project).resolve()
    if expected != candidate.parent.parent or base not in list(candidate.parents) + [candidate.parent]:
        raise ValueError("project invalido")
    if candidate.parent.parent != expected:
        raise ValueError("project invalido")
    return candidate


def data_file(root, project, name):
    if name not in DATA_FILES:
        raise ValueError(f"arquivo de dados invalido: {name!r}")
    return project_data_dir(root, project) / name


def default_data(name):
    if name == CONCEPT_FILE:
        return {"version": 1, "vision": {"objective": "", "audience": "", "scope": "", "nonGoals": ""},
                "elements": []}
    if name == SPRINT_FILE:
        return {"version": 1, "columns": ["backlog", "doing", "done"], "tasks": []}
    if name == PAGES_FILE:
        return {"version": 1, "pages": []}
    if name == TABLES_FILE:
        return {"version": 1, "tables": [], "relations": []}
    if name == PROPOSALS_FILE:
        return {"version": 1, "proposals": []}
    raise ValueError(f"arquivo de dados invalido: {name!r}")


def load_data(root, project, name):
    path = data_file(root, project, name)
    if not path.is_file():
        return default_data(name)
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError(f"{name} excede o tamanho maximo")
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise ValueError(f"{name} contem JSON invalido")
    if not isinstance(data, dict):
        raise ValueError(f"{name} invalido")
    merged = default_data(name)
    for key, value in data.items():
        if key in merged:
            merged[key] = value
    return merged


def save_data(root, project, name, data):
    path = data_file(root, project, name)
    raw = json.dumps(data, ensure_ascii=False, indent=2)
    if len(raw.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError(f"{name} excede o tamanho maximo")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(raw, encoding="utf-8")
    tmp.replace(path)
    return {"ok": True, "path": str(path)}


def list_projects(root=None):
    base = projects_root(root)
    if not base.is_dir():
        return []
    out = []
    for child in sorted(base.iterdir()):
        if child.is_dir() and PROJECT_ID_RE.match(child.name):
            out.append(child.name)
    return out


# ------------------------------------------------------------------ conceitos

QUESTION_TYPES = ("text", "choice", "yesno")
AFTER_ANSWER = ("executado", "solicitacao_testes")


def validate_question(item, idx=0):
    """Pergunta do formulario de execucao: {id?, question, type?, options?, answer?}."""
    if isinstance(item, str):
        item = {"question": item}
    if not isinstance(item, dict):
        raise ValueError("pergunta invalida")
    qtype = item.get("type") or "text"
    if qtype not in QUESTION_TYPES:
        raise ValueError(f"tipo de pergunta invalido: {qtype!r}")
    options = []
    if qtype == "choice":
        raw = item.get("options") or []
        if not isinstance(raw, list) or not raw:
            raise ValueError("pergunta choice exige options")
        options = [_check_str(x, "option", 200) for x in raw][:10]
    ans = item.get("answer")
    if ans is not None:
        ans = _check_str(ans, "answer", 2000, required=False) or ""
        if qtype == "choice" and ans and ans not in options:
            raise ValueError("resposta fora das opcoes")
    qid = item.get("id") or f"q{idx + 1}"
    out = {"id": validate_entity_id(str(qid), "question.id"),
           "question": _check_str(item.get("question"), "question", 500),
           "type": qtype, "options": options, "answer": ans or ""}
    for k in ("answeredBy", "answeredAt"):
        if item.get(k):
            out[k] = item[k]
    return out


def _stamp_answers(old_list, new_list, actor):
    """Carimba autoria/hora nas respostas recem-preenchidas."""
    old_by_id = {q.get("id"): q for q in (old_list or []) if isinstance(q, dict)}
    for q in new_list or []:
        if not isinstance(q, dict):
            continue
        prev = old_by_id.get(q.get("id"), {})
        if (q.get("answer") or "").strip() and not (prev.get("answer") or "").strip():
            q["answeredBy"] = actor
            q["answeredAt"] = utcnow()
    return new_list


def _maybe_auto_advance(task, actor):
    """Formulario completo -> avanca (executado ou solicitacao_testes).

    Compoe passos legais da matriz. Retorna o status final ou None.
    """
    qs = task.get("questions") or []
    if not qs:
        return None
    if any(not (q.get("answer") or "").strip() for q in qs if isinstance(q, dict)):
        return None
    cur = task.get("status") or "backlog"
    if cur not in ("backlog", "doing"):
        return None
    target = task.get("afterAnswer") or "executado"
    if target not in AFTER_ANSWER:
        target = "executado"
    if target == "solicitacao_testes" and actor != "user":
        target = "executado"
    if target == "solicitacao_testes" and cur != "executado":
        _check_move(actor, cur, "executado")
        task["status"] = "executado"
        task["owner"] = _auto_owner("executado")
        cur = "executado"
    _check_move(actor, cur, target)
    task["status"] = target
    task["owner"] = _auto_owner(target)
    return target


def validate_task_brief(item):
    """Uma tarefa implicada no conceito: {title, desc?, priority?}."""
    if not isinstance(item, dict):
        raise ValueError("tarefa implicada invalida")
    raw_q = item.get("questions") or []
    if not isinstance(raw_q, list):
        raise ValueError("'questions' deve ser uma lista")
    return {
        "title": _check_str(item.get("title"), "task.title", MAX_TITLE),
        "desc": _check_str(item.get("desc"), "task.desc", MAX_DESC, required=False),
        "priority": _check_priority(item.get("priority"), "task.priority") if item.get("priority") is not None else 5,
        "status": _check_enum(item.get("status"), "task.status", STATUSES, required=False, default="backlog"),
        "afterAnswer": item.get("afterAnswer") if item.get("afterAnswer") in AFTER_ANSWER else "executado",
        "questions": [validate_question(x, i) for i, x in enumerate(raw_q)],
    }


def validate_concept_element(payload, partial=False):
    req = (not partial)
    out = {
        "kind": _check_enum(payload.get("kind"), "kind", CONCEPT_KINDS, required=req, default="interface"),
        "title": _check_str(payload.get("title"), "title", MAX_TITLE, required=req),
        "description": _check_str(payload.get("description"), "description", MAX_DESC, required=False),
        "details": _check_str(payload.get("details"), "details", MAX_DETAILS, required=False),
    }
    if "tasks" in (payload or {}):
        raw = payload.get("tasks")
        if raw is None:
            out["tasks"] = []
        elif not isinstance(raw, list):
            raise ValueError("'tasks' deve ser uma lista")
        else:
            out["tasks"] = [validate_task_brief(x) for x in raw]
    elif req:
        out["tasks"] = []
    return out


def apply_concept(data, target_id, action, payload, actor):
    elements = data.setdefault("elements", [])
    if action == "create":
        if len(elements) >= MAX_ELEMENTS:
            raise ValueError("limite de elementos atingido")
        clean = validate_concept_element(payload or {})
        now = utcnow()
        elements.append({
            "id": validate_entity_id((payload or {}).get("id") or _new_id("e"), "id"),
            **clean,
            "updatedBy": actor, "updatedAt": now,
        })
        return elements[-1]
    item = next((e for e in elements if e.get("id") == target_id), None)
    if item is None:
        raise ValueError("elemento nao encontrado")
    if action == "update":
        clean = validate_concept_element(payload or {}, partial=True)
        for key, value in clean.items():
            if key in (payload or {}):
                item[key] = value
        item["updatedBy"] = actor
        item["updatedAt"] = utcnow()
        return item
    if action == "delete":
        elements.remove(item)
        return {"deleted": target_id}
    raise ValueError(f"acao invalida para conceito: {action!r}")


def apply_vision(data, payload, actor):
    vision = data.setdefault("vision", {"objective": "", "audience": "", "scope": "", "nonGoals": ""})
    for key in ("objective", "audience", "scope", "nonGoals"):
        if key in (payload or {}):
            vision[key] = _check_str(payload.get(key), key, MAX_DESC, required=False)
    data["visionUpdatedBy"] = actor
    data["visionUpdatedAt"] = utcnow()
    return vision


# -------------------------------------------------------------------- sprint

def validate_task(payload, partial=False):
    req = (not partial)
    return {
        "title": _check_str(payload.get("title"), "title", MAX_TITLE, required=req),
        "desc": _check_str(payload.get("desc"), "desc", MAX_DESC, required=False),
        "priority": _check_priority(payload.get("priority"), "priority") if payload.get("priority") is not None else 5,
        "owner": payload.get("owner") if payload.get("owner") in OWNERS else None,
        "status": _check_enum(payload.get("status"), "status", STATUSES, required=False, default="backlog"),
        "assignee": _check_str(payload.get("assignee"), "assignee", 120, required=False),
        "afterAnswer": payload.get("afterAnswer") if payload.get("afterAnswer") in AFTER_ANSWER else "executado",
        "questions": ([validate_question(x, i) for i, x in enumerate(payload.get("questions"))]
                      if "questions" in (payload or {}) else []),
    }


def apply_sprint(data, target_id, action, payload, actor):
    tasks = data.setdefault("tasks", [])
    if action == "create":
        if len(tasks) >= MAX_TASKS:
            raise ValueError("limite de tarefas atingido")
        clean = validate_task(payload or {})
        now = utcnow()
        clean["owner"] = clean.get("owner") or _auto_owner(clean.get("status") or "backlog")
        tasks.append({
            "id": validate_entity_id((payload or {}).get("id") or _new_id("t"), "id"),
            **clean,
            "createdBy": actor, "createdAt": now, "updatedBy": actor, "updatedAt": now,
        })
        _stamp_answers([], tasks[-1].get("questions"), actor)
        _maybe_auto_advance(tasks[-1], actor)
        return tasks[-1]
    item = next((t for t in tasks if t.get("id") == target_id), None)
    if item is None:
        raise ValueError("tarefa nao encontrada")
    if action in ("update", "move"):
        if action == "move" and "status" in (payload or {}):
            nxt = _check_enum(payload.get("status"), "status", STATUSES)
            _check_move(actor, item.get("status") or "backlog", nxt)
            item["status"] = nxt
            item["owner"] = _auto_owner(nxt)
        old_q = [dict(q) for q in (item.get("questions") or []) if isinstance(q, dict)]
        clean = validate_task(payload or {}, partial=True)
        for key, value in clean.items():
            if key in (payload or {}) and key not in ("status", "owner"):
                item[key] = value
        if "owner" in (payload or {}) and payload.get("owner") in OWNERS:
            item["owner"] = payload.get("owner")
        if "questions" in (payload or {}) and "status" not in (payload or {}):
            _stamp_answers(old_q, item.get("questions"), actor)
            _maybe_auto_advance(item, actor)
        item["updatedBy"] = actor
        item["updatedAt"] = utcnow()
        return item
    if action == "delete":
        tasks.remove(item)
        return {"deleted": target_id}
    raise ValueError(f"acao invalida para sprint: {action!r}")


# -------------------------------------------------------------------- paginas

def validate_page(payload, partial=False):
    req = (not partial)
    out = {
        "name": _check_str(payload.get("name"), "name", MAX_TITLE, required=req),
        "route": _check_str(payload.get("route"), "route", MAX_TITLE, required=False),
        "desc": _check_str(payload.get("desc"), "desc", MAX_DESC, required=False),
    }
    out.update(_validate_tasks_field(payload, req))
    if out["route"] and not re.match(r"^[A-Za-z0-9/_.:-]{1,200}$", out["route"]):
        raise ValueError("route invalida")
    return out


def validate_page_element(payload, partial=False):
    req = (not partial)
    return {
        "type": _check_enum(payload.get("type"), "type", PAGE_ELEMENT_TYPES, required=False, default="texto"),
        "label": _check_str(payload.get("label"), "label", MAX_TITLE, required=req),
        "content": _check_str(payload.get("content"), "content", MAX_DETAILS, required=False),
        "order": payload.get("order", 0) if isinstance(payload.get("order", 0), int) else 0,
    }


def _find_page(data, page_id):
    page = next((p for p in data.get("pages", []) if p.get("id") == page_id), None)
    if page is None:
        raise ValueError("pagina nao encontrada")
    return page


def _find_element(page, element_id):
    el = next((e for e in page.get("elements", []) if e.get("id") == element_id), None)
    if el is None:
        raise ValueError("elemento nao encontrado")
    return el


def apply_pages(data, target_kind, target_id, action, payload, actor):
    pages = data.setdefault("pages", [])
    payload = payload or {}
    if target_kind == "page":
        if action == "create":
            if len(pages) >= MAX_PAGES:
                raise ValueError("limite de paginas atingido")
            clean = validate_page(payload)
            now = utcnow()
            pages.append({
                "id": validate_entity_id(payload.get("id") or _new_id("p"), "id"),
                **clean,
                    "elements": [], "updatedBy": actor, "updatedAt": now,
            })
            return pages[-1]
        page = next((p for p in pages if p.get("id") == target_id), None)
        if page is None:
            raise ValueError("pagina nao encontrada")
        if action == "update":
            clean = validate_page(payload, partial=True)
            for key, value in clean.items():
                if key in payload:
                    page[key] = value
            page["updatedBy"] = actor
            page["updatedAt"] = utcnow()
            return page
        if action == "delete":
            pages.remove(page)
            return {"deleted": target_id}
        raise ValueError(f"acao invalida para pagina: {action!r}")
    if target_kind == "page-element":
        page_id = payload.get("pageId") or payload.get("page_id")
        if action == "create" and not page_id:
            raise ValueError("pageId obrigatorio")
        page = _find_page(data, page_id) if action == "create" else _find_page(data, payload.get("pageId") or _page_of(data, target_id))
        if action == "create":
            elements = page.setdefault("elements", [])
            if len(elements) >= MAX_PAGE_ELEMENTS:
                raise ValueError("limite de elementos da pagina atingido")
            clean = validate_page_element(payload)
            now = utcnow()
            elements.append({
                "id": validate_entity_id(payload.get("id") or _new_id("el"), "id"),
                **clean,
                    "snapshotHtml": "", "comments": [],
                "updatedBy": actor, "updatedAt": now,
            })
            return elements[-1]
        owner_page_id, el = _find_element_anywhere(data, target_id)
        if action == "update":
            clean = validate_page_element(payload, partial=True)
            for key, value in clean.items():
                if key in payload:
                    el[key] = value
            if "snapshotHtml" in payload and actor == "user":
                el["snapshotHtml"] = _check_str(payload.get("snapshotHtml"), "snapshotHtml", MAX_DETAILS, required=False)
            el["updatedBy"] = actor
            el["updatedAt"] = utcnow()
            return el
        if action == "delete":
            owner = _find_page(data, owner_page_id)
            owner["elements"].remove(el)
            return {"deleted": target_id}
        raise ValueError(f"acao invalida para elemento: {action!r}")
    if target_kind == "page-comment":
        if action != "comment":
            raise ValueError("comentarios usam acao 'comment'")
        owner_page_id, el = _find_element_anywhere(data, payload.get("elementId") or payload.get("element_id") or target_id)
        comments = el.setdefault("comments", [])
        if len(comments) >= MAX_COMMENTS:
            raise ValueError("limite de comentarios atingido")
        text = _check_str(payload.get("text"), "text", MAX_COMMENT, required=True)
        author = _check_str(payload.get("author"), "author", 120, required=False) or actor
        comment = {"id": validate_entity_id(payload.get("id") or _new_id("c"), "id"),
                   "author": author, "text": text, "createdAt": utcnow()}
        comments.append(comment)
        el["updatedBy"] = actor
        el["updatedAt"] = utcnow()
        return comment
    raise ValueError(f"alvo invalido para paginas: {target_kind!r}")


def _page_of(data, element_id):
    for page in data.get("pages", []):
        for el in page.get("elements", []):
            if el.get("id") == element_id:
                return page.get("id")
    raise ValueError("elemento nao encontrado")


def _find_element_anywhere(data, element_id):
    validate_entity_id(element_id, "elementId")
    for page in data.get("pages", []):
        for el in page.get("elements", []):
            if el.get("id") == element_id:
                return page.get("id"), el
    raise ValueError("elemento nao encontrado")


# -------------------------------------------------------------------- tabelas

def _table_names(tables):
    return [t.get("name", "") for t in tables]


def _validate_embedded_columns(raw, tables=()):
    """Colunas vindas no create da tabela: [{name, type?, pk?, nullable?, desc?, fk?}]."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("'columns' deve ser uma lista")
    if len(raw) > MAX_COLUMNS:
        raise ValueError("limite de colunas")
    out = []
    names = []
    for i, item in enumerate(raw):
        if isinstance(item, str):
            item = {"name": item}
        if not isinstance(item, dict):
            raise ValueError(f"columns[{i}] invalida")
        col = validate_column(item, sibling_names=names, tables=tables)
        names.append(col.get("name") or "")
        out.append(col)
    return out


def validate_table(payload, partial=False, sibling_names=()):
    req = (not partial)
    name = _check_str(payload.get("name"), "name", 120, required=req)
    if name:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]{0,119}$", name):
            raise ValueError("nome de tabela invalido (use letras, numeros e _)")
        lowered = [s.lower() for s in sibling_names]
        if name.lower() in lowered:
            raise ValueError(f"tabela '{name}' ja existe")
    out = {
        "name": name,
        "desc": _check_str(payload.get("desc"), "desc", MAX_DESC, required=False),
    }
    out.update(_validate_tasks_field(payload, req))
    if "columns" in payload and not partial:
        out["columns"] = _validate_embedded_columns(payload.get("columns"), tables=())
    return out


def validate_column(payload, partial=False, sibling_names=(), tables=()):
    req = (not partial)
    name = _check_str(payload.get("name"), "name", 120, required=req)
    if name:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]{0,119}$", name):
            raise ValueError("nome de coluna invalido (use letras, numeros e _)")
        lowered = [s.lower() for s in sibling_names]
        if name.lower() in lowered:
            raise ValueError(f"coluna '{name}' ja existe nesta tabela")
    col = {
        "name": name,
        "type": _check_enum(payload.get("type"), "type", COLUMN_TYPES, required=False, default="text"),
        "pk": bool(payload.get("pk", False)),
        "nullable": bool(payload.get("nullable", True)),
        "desc": _check_str(payload.get("desc"), "desc", MAX_DESC, required=False),
    }
    fk = payload.get("fk")
    if fk is not None:
        if not isinstance(fk, dict):
            raise ValueError("fk invalida")
        ref_table = _check_str(fk.get("table"), "fk.table", 120, required=True)
        ref_col = _check_str(fk.get("column"), "fk.column", 120, required=True)
        target = next((t for t in (tables or []) if t.get("name") == ref_table), None)
        if target is None:
            raise ValueError(f"fk aponta para tabela inexistente: {ref_table}")
        if ref_col not in [c.get("name") for c in target.get("columns", [])]:
            raise ValueError(f"fk aponta para coluna inexistente: {ref_table}.{ref_col}")
        col["fk"] = {"table": ref_table, "column": ref_col}
    else:
        col["fk"] = None
    return col


def _find_table(data, table_id):
    table = next((t for t in data.get("tables", []) if t.get("id") == table_id), None)
    if table is None:
        raise ValueError("tabela nao encontrada")
    return table


def _referenced_by(data, table_name, column_name=None):
    refs = []
    for rel in data.get("relations", []):
        if rel.get("toTable") == table_name and (column_name is None or rel.get("toColumn") == column_name):
            refs.append(rel.get("id"))
    for table in data.get("tables", []):
        for col in table.get("columns", []):
            fk = col.get("fk") or {}
            if fk.get("table") == table_name and (column_name is None or fk.get("column") == column_name):
                refs.append(f"{table.get('name')}.{col.get('name')}")
    return refs


def apply_tables(data, target_kind, target_id, action, payload, actor):
    payload = payload or {}
    tables = data.setdefault("tables", [])
    relations = data.setdefault("relations", [])
    if target_kind == "table":
        if action == "create":
            if len(tables) >= MAX_TABLES:
                raise ValueError("limite de tabelas atingido")
            clean = validate_table(payload, sibling_names=_table_names(tables))
            now = utcnow()
            cols = clean.pop("columns", [])
            tables.append({
                "id": validate_entity_id(payload.get("id") or _new_id("tb"), "id"),
                **clean,
                "columns": cols,
                "updatedBy": actor, "updatedAt": now,
            })
            return tables[-1]
        table = _find_table(data, target_id)
        if action == "update":
            others = [n for n in _table_names(tables) if n != table.get("name")]
            clean = validate_table(payload, partial=True, sibling_names=others)
            if "name" in payload and payload["name"] != table.get("name"):
                raise ValueError("renomear tabela exige remover e recriar (evita quebrar FKs)")
            for key, value in clean.items():
                if key in payload and key != "name":
                    table[key] = value
            table["updatedBy"] = actor
            table["updatedAt"] = utcnow()
            return table
        if action == "delete":
            refs = _referenced_by(data, table.get("name"))
            if refs:
                raise ValueError(f"tabela referenciada por: {', '.join(refs[:5])}")
            tables.remove(table)
            return {"deleted": target_id}
        raise ValueError(f"acao invalida para tabela: {action!r}")
    if target_kind == "table-column":
        table_id = payload.get("tableId") or payload.get("table_id")
        if action == "create":
            if not table_id:
                raise ValueError("tableId obrigatorio")
            table = _find_table(data, table_id)
            columns = table.setdefault("columns", [])
            if len(columns) >= MAX_COLUMNS:
                raise ValueError("limite de colunas atingido")
            clean = validate_column(payload, sibling_names=[c.get("name", "") for c in columns], tables=tables)
            now = utcnow()
            columns.append({
                "id": validate_entity_id(payload.get("id") or _new_id("col"), "id"),
                **clean,
                    "updatedBy": actor, "updatedAt": now,
            })
            return columns[-1]
        owner, col = _find_column_anywhere(data, target_id)
        if action == "update":
            others = [c.get("name", "") for c in owner.get("columns", []) if c.get("id") != target_id]
            if "name" in payload and payload["name"] != col.get("name"):
                refs = _referenced_by(data, owner.get("name"), col.get("name"))
                if refs:
                    raise ValueError(f"coluna referenciada por: {', '.join(refs[:5])}")
            clean = validate_column(payload, partial=True, sibling_names=others, tables=tables)
            for key, value in clean.items():
                if key in payload:
                    col[key] = value
            col["updatedBy"] = actor
            col["updatedAt"] = utcnow()
            return col
        if action == "delete":
            refs = _referenced_by(data, owner.get("name"), col.get("name"))
            if refs:
                raise ValueError(f"coluna referenciada por: {', '.join(refs[:5])}")
            owner["columns"].remove(col)
            return {"deleted": target_id}
        raise ValueError(f"acao invalida para coluna: {action!r}")
    if target_kind == "relation":
        if action == "create":
            if len(relations) >= MAX_RELATIONS:
                raise ValueError("limite de relacoes atingido")
            clean = validate_relation(payload, tables)
            now = utcnow()
            relations.append({
                "id": validate_entity_id(payload.get("id") or _new_id("rel"), "id"),
                **clean,
                    "updatedBy": actor, "updatedAt": now,
            })
            return relations[-1]
        rel = next((r for r in relations if r.get("id") == target_id), None)
        if rel is None:
            raise ValueError("relacao nao encontrada")
        if action == "update":
            if any(k in payload for k in ("fromTable", "fromColumn", "toTable", "toColumn")):
                raise ValueError("alterar pontas da relacao exige remover e recriar")
            if "cardinality" in payload:
                rel["cardinality"] = _check_enum(payload.get("cardinality"), "cardinality", CARDINALITIES)
            if "desc" in payload:
                rel["desc"] = _check_str(payload.get("desc"), "desc", MAX_DESC, required=False)
            rel["updatedBy"] = actor
            rel["updatedAt"] = utcnow()
            return rel
        if action == "delete":
            relations.remove(rel)
            return {"deleted": target_id}
        raise ValueError(f"acao invalida para relacao: {action!r}")
    raise ValueError(f"alvo invalido para tabelas: {target_kind!r}")


def validate_relation(payload, tables):
    from_table = _check_str(payload.get("fromTable") or payload.get("from_table"), "fromTable", 120)
    from_col = _check_str(payload.get("fromColumn") or payload.get("from_column"), "fromColumn", 120)
    to_table = _check_str(payload.get("toTable") or payload.get("to_table"), "toTable", 120)
    to_col = _check_str(payload.get("toColumn") or payload.get("to_column"), "toColumn", 120)
    src = next((t for t in tables if t.get("name") == from_table), None)
    dst = next((t for t in tables if t.get("name") == to_table), None)
    if src is None:
        raise ValueError(f"tabela de origem inexistente: {from_table}")
    if dst is None:
        raise ValueError(f"tabela de destino inexistente: {to_table}")
    if from_col not in [c.get("name") for c in src.get("columns", [])]:
        raise ValueError(f"coluna de origem inexistente: {from_table}.{from_col}")
    if to_col not in [c.get("name") for c in dst.get("columns", [])]:
        raise ValueError(f"coluna de destino inexistente: {to_table}.{to_col}")
    return {
        "fromTable": from_table, "fromColumn": from_col,
        "toTable": to_table, "toColumn": to_col,
        "cardinality": _check_enum(payload.get("cardinality"), "cardinality", CARDINALITIES, required=False, default="1:N"),
        "desc": _check_str(payload.get("desc"), "desc", MAX_DESC, required=False),
    }


def _find_column_anywhere(data, column_id):
    validate_entity_id(column_id, "columnId")
    for table in data.get("tables", []):
        for col in table.get("columns", []):
            if col.get("id") == column_id:
                return table, col
    raise ValueError("coluna nao encontrada")


# ----------------------------------------------------------------- propostas

def _new_id(prefix):
    import random
    import time
    return f"{prefix}-{int(time.time() * 1000) % 100000000}-{random.randint(1000, 9999)}"


# Qualidade minima anti-generico — vale SOMENTE no caminho do agente
# (propose()). O usuario, editando direto via UI, continua livre.
# Exige texto real (responsabilidades, regras, onde vive no repo) em vez de
# titulo + referencia solta. Erro orienta o agente a re-propor melhor.
MIN_RICH_TEXT = 20
RICH_FIELDS = {
    ("concept", "concept-element"): (("description", MIN_RICH_TEXT),
                                     ("details", MIN_RICH_TEXT)),
    ("sprint", "sprint-task"): (("desc", MIN_RICH_TEXT),),
    ("pages", "page"): (("desc", MIN_RICH_TEXT),),
    ("tables", "table"): (("desc", MIN_RICH_TEXT),),
    # visao: update vazio nao significa nada; exige ao menos 1 campo preenchido
    ("concept", "concept-vision"): (("objective", 1), ("audience", 1),
                                    ("scope", 1), ("nonGoals", 1)),
}


def _check_not_generic(tab, target_kind, action, payload):
    """Rejeita proposta generica demais do agente (create; vision: update).

    Tarefas NAO sao aceitas a parte: sprint-task em create e rejeitado
    sempre — tarefas nascem de aprovacoes (conceito/pagina/tabela).
    Movimentacao e correcao (update/move/delete) continuam permitidas.
    """
    if tab == "sprint" and target_kind == "sprint-task" and action == "create":
        raise ValueError(
            "tarefas nao sao aceitas a parte: sprint-task.create do agente esta "
            "desativado. Descreva o trabalho em 'tasks' do conceito/pagina/tabela "
            "correspondente (create ou update) — aprovar a origem cria as tasks.")
    if action == "create":
        spec = RICH_FIELDS.get((tab, target_kind))
        if not spec:
            return
    elif action == "update" and (tab, target_kind) == ("concept", "concept-vision"):
        spec = RICH_FIELDS[(tab, target_kind)]
    else:
        return
    if action == "create" and (tab, target_kind) in (
            ("concept", "concept-element"), ("pages", "page"), ("tables", "table")):
        briefs = (payload or {}).get("tasks")
        if (not isinstance(briefs, list) or not [
                x for x in briefs
                if isinstance(x, dict) and str(x.get("title", "")).strip()]):
            raise ValueError(
                f"proposta generica: {target_kind}.create do agente exige origem que implica tarefas: "
                "'tasks' com ao menos 1 tarefa {title, desc?, priority?, status?} "
                "descrevendo o trabalho que o conceito demanda (status pode vir "
                "'done' com evidencia quando o repo ja executa). Tarefa avulsa "
                "separada nao entra no inbox: embuta no conceito.")
    payload = payload or {}
    for field, minimum in spec:
        value = payload.get(field)
        if isinstance(value, str) and len(value.strip()) >= minimum:
            return
    need = " ou ".join(f"'{f}' (≥{m} caracteres)" for f, m in spec)
    raise ValueError(
        f"proposta generica demais: {target_kind}.{action} do agente exige "
        f"{need} com conteudo real (responsabilidades, regras, onde vive no "
        f"repo). Releia a visao e re-proponha sem genericidade."
    )


def validate_proposal(tab, target_kind, target_id, action, payload, reason):
    _check_enum(tab, "tab", TABS)
    if target_kind not in TARGET_KINDS:
        raise ValueError(f"targetKind invalido: {target_kind!r}")
    if action not in ACTIONS:
        raise ValueError(f"action invalida: {action!r}")
    if action in ("update", "delete", "move") and not target_id and target_kind != "concept-vision":
        raise ValueError("targetId obrigatorio para esta acao")
    if target_id:
        validate_entity_id(target_id, "targetId")
    if payload is not None and not isinstance(payload, dict):
        raise ValueError("payload deve ser um objeto")
    _check_str(reason, "reason", MAX_REASON, required=False)
    return True


def propose(root, project, tab, target_kind, target_id, action, payload, reason=""):
    """Cria uma proposta de AGENTE (actor=agent). Valida esquema."""
    validate_project_id(project)
    validate_proposal(tab, target_kind, target_id, action, payload or {}, reason)
    _check_not_generic(tab, target_kind, action, payload or {})
    data = load_data(root, project, PROPOSALS_FILE)
    proposals = data.setdefault("proposals", [])
    pending = [p for p in proposals if p.get("status") == "pending"]
    if len(pending) >= MAX_PENDING:
        raise ValueError("inbox de propostas cheio: aguarde aprovacao")
    if len(proposals) >= MAX_PROPOSALS:
        # poda as mais antigas já decididas
        decided = [p for p in proposals if p.get("status") != "pending"]
        for old in sorted(decided, key=lambda p: p.get("decidedAt") or p.get("createdAt") or "")[: len(proposals) - MAX_PROPOSALS + 1]:
            proposals.remove(old)
    # dry-run contra os dados atuais para validar o esquema
    _dry_run(root, project, tab, target_kind, target_id, action, payload or {})
    proposal = {
        "id": _new_id("prop"),
        "tab": tab,
        "targetKind": target_kind,
        "targetId": target_id,
        "action": action,
        "payload": payload or {},
        "reason": (reason or "").strip(),
        "status": "pending",
        "createdBy": "agent",
        "createdAt": utcnow(),
        "decidedAt": None,
    }
    proposals.append(proposal)
    save_data(root, project, PROPOSALS_FILE, data)
    return proposal


def _dry_run(root, project, tab, target_kind, target_id, action, payload):
    """Executa a mudança em cópia para validar o esquema sem salvar."""
    import copy
    if tab == "concept":
        data = copy.deepcopy(load_data(root, project, CONCEPT_FILE))
        if target_kind == "concept-vision":
            apply_vision(data, payload, "agent")
        elif target_kind == "concept-element":
            apply_concept(data, target_id, action, payload, "agent")
        else:
            raise ValueError(f"alvo invalido para conceito: {target_kind!r}")
        return
    if tab == "sprint":
        data = copy.deepcopy(load_data(root, project, SPRINT_FILE))
        apply_sprint(data, target_id, action, payload, "agent")
        return
    if tab == "pages":
        data = copy.deepcopy(load_data(root, project, PAGES_FILE))
        apply_pages(data, target_kind, target_id, action, payload, "agent")
        return
    if tab == "tables":
        data = copy.deepcopy(load_data(root, project, TABLES_FILE))
        apply_tables(data, target_kind, target_id, action, payload, "agent")
        return
    raise ValueError(f"tab invalida: {tab!r}")


def _validate_tasks_field(payload, req):
    """Campo opcional 'tasks' ([{title, desc?, priority?, status?}])."""
    if "tasks" not in (payload or {}):
        return {"tasks": []} if req else {}
    raw = payload.get("tasks")
    if raw is None:
        return {"tasks": []}
    if not isinstance(raw, list):
        raise ValueError("'tasks' deve ser uma lista")
    return {"tasks": [validate_task_brief(x) for x in raw]}


def _spawn_implied_tasks(root, project, element, actor, origin=None):
    """Aprovar conceito = aprovar o pacote: cria as sprint tasks embutidas.

    Idempotente por titulo (re-aprovacao ou update repetido nao duplica).
    Retorna a lista criada (pode ser vazia).
    """
    wanted = (element or {}).get("tasks") or []
    if not wanted:
        return []
    origin = origin or {}
    if isinstance(element, dict) and element.get("id") and not origin.get("id"):
        origin = {"tab": origin.get("tab"), "kind": origin.get("kind"),
                  "id": element.get("id"),
                  "title": element.get("title") or element.get("name")}
    data = load_data(root, project, SPRINT_FILE)
    tasks = data.setdefault("tasks", [])
    existing = {str(x.get("title", "")).strip().lower() for x in tasks}
    created = []
    for item in wanted:
        title = str(item.get("title", "")).strip()
        if not title or title.lower() in existing:
            continue
        now = utcnow()
        st = item.get("status") if item.get("status") in STATUSES else "backlog"
        tasks.append({
            "id": _new_id("t"),
            "title": title[:MAX_TITLE],
            "desc": str(item.get("desc", "") or "")[:MAX_DESC],
            "priority": _check_priority(item.get("priority"), "priority") if item.get("priority") is not None else 5,
            "owner": _auto_owner(st),
            "status": st,
            "afterAnswer": item.get("afterAnswer") if item.get("afterAnswer") in AFTER_ANSWER else "executado",
            "questions": [dict(q) for q in (item.get("questions") or []) if isinstance(q, dict)],
            "origin": {"tab": origin.get("tab"), "kind": origin.get("kind"),
                       "id": origin.get("id"), "title": origin.get("title")},
            "createdBy": f"{actor}:{origin.get('kind') or 'origem'}",
            "createdAt": now, "updatedBy": actor, "updatedAt": now,
        })
        existing.add(title.lower())
        created.append(tasks[-1])
    if created:
        save_data(root, project, SPRINT_FILE, data)
    return created


def decide(root, project, proposal_id, approve, by="user"):
    """Aprova (aplica) ou rejeita uma proposta. Só o usuário decide (UI)."""
    validate_entity_id(proposal_id, "proposalId")
    props = load_data(root, project, PROPOSALS_FILE)
    proposal = next((p for p in props.get("proposals", []) if p.get("id") == proposal_id), None)
    if proposal is None:
        raise ValueError("proposta nao encontrada")
    if proposal.get("status") != "pending":
        raise ValueError("proposta ja decidida")
    if by != "user":
        raise ValueError("apenas o usuario pode decidir propostas")
    if not approve:
        proposal["status"] = "rejected"
        proposal["decidedAt"] = utcnow()
        save_data(root, project, PROPOSALS_FILE, props)
        return {"status": "rejected", "proposal": proposal}
    tab = proposal["tab"]
    file_map = {"concept": CONCEPT_FILE, "sprint": SPRINT_FILE, "pages": PAGES_FILE, "tables": TABLES_FILE}
    data = load_data(root, project, file_map[tab])
    result = _apply_decision(data, proposal)
    save_data(root, project, file_map[tab], data)
    spawned = []
    if (proposal.get("action") in ("create", "update")
            and isinstance(result, dict) and result.get("id")
            and (tab, proposal.get("targetKind")) in (
                ("concept", "concept-element"), ("pages", "page"), ("tables", "table"))
            and ("title" in result or "name" in result)):
        spawned = _spawn_implied_tasks(
            root, project, result, "agent-aprovado",
            {"tab": tab, "kind": proposal.get("targetKind")})
    proposal["status"] = "approved"
    proposal["decidedAt"] = utcnow()
    proposal["applied"] = result
    proposal["spawnedTasks"] = [x["id"] for x in spawned]
    save_data(root, project, PROPOSALS_FILE, props)
    return {"status": "approved", "proposal": proposal, "result": result,
            "spawnedTasks": spawned}


def _apply_decision(data, proposal):
    tab = proposal["tab"]
    kind = proposal["targetKind"]
    tid = proposal.get("targetId")
    action = proposal["action"]
    payload = proposal.get("payload") or {}
    if tab == "concept":
        if kind == "concept-vision":
            return apply_vision(data, payload, "agent-aprovado")
        return apply_concept(data, tid, action, payload, "agent-aprovado")
    if tab == "sprint":
        return apply_sprint(data, tid, action, payload, "agent-aprovado")
    if tab == "pages":
        return apply_pages(data, kind, tid, action, payload, "agent-aprovado")
    if tab == "tables":
        return apply_tables(data, kind, tid, action, payload, "agent-aprovado")
    raise ValueError(f"tab invalida: {tab!r}")


def agent_task_update(root, project, task_id, payload):
    """Edição DIRETA do agente nas SUAS tarefas (sem proposta).

    usadO pela tool system_design_task_update. Só em task com owner=agent;
    tarefa do usuário exige proposta. Movimentação segue a matriz.
    """
    validate_project_id(project)
    validate_entity_id(task_id, "task_id")
    data = load_data(root, project, SPRINT_FILE)
    tasks = data.setdefault("tasks", [])
    item = next((x for x in tasks if x.get("id") == task_id), None)
    if item is None:
        raise ValueError("tarefa nao encontrada")
    if (item.get("owner") or "agent") != "agent":
        raise ValueError("tarefa do usuário: use system_design_propose")
    payload = payload or {}
    if "status" in payload and payload.get("status") != item.get("status"):
        nxt = _check_enum(payload.get("status"), "status", STATUSES)
        _check_move("agent", item.get("status") or "backlog", nxt)
        item["status"] = nxt
        item["owner"] = _auto_owner(nxt)
    old_q = [dict(q) for q in (item.get("questions") or []) if isinstance(q, dict)]
    clean = validate_task(payload, partial=True)
    for key, value in clean.items():
        if key in payload and key not in ("status", "owner"):
            item[key] = value
    if payload.get("owner") in OWNERS:
        item["owner"] = payload.get("owner")
    if "questions" in payload and "status" not in payload:
        _stamp_answers(old_q, item.get("questions"), "agent")
        _maybe_auto_advance(item, "agent")
    item["updatedBy"] = "agent"
    item["updatedAt"] = utcnow()
    save_data(root, project, SPRINT_FILE, data)
    return item


def user_action(root, project, tab, target_kind, target_id, action, payload):
    """Edição direta do USUÁRIO (actor=user)."""
    validate_project_id(project)
    file_map = {"concept": CONCEPT_FILE, "sprint": SPRINT_FILE, "pages": PAGES_FILE, "tables": TABLES_FILE}
    if tab not in file_map:
        raise ValueError(f"tab invalida: {tab!r}")
    data = load_data(root, project, file_map[tab])
    payload = payload or {}
    if tab == "concept":
        if target_kind == "concept-vision":
            result = apply_vision(data, payload, "user")
        elif target_kind == "concept-element":
            result = apply_concept(data, target_id, action, payload, "user")
            if action in ("create", "update") and isinstance(result, dict) and result.get("id") and "title" in result:
                save_data(root, project, file_map[tab], data)
                _spawn_implied_tasks(root, project, result, "user",
                                     {"tab": tab, "kind": target_kind})
                data = load_data(root, project, file_map[tab])
        else:
            raise ValueError(f"alvo invalido para conceito: {target_kind!r}")
    elif tab == "sprint":
        result = apply_sprint(data, target_id, action, payload, "user")
    elif tab == "pages":
        result = apply_pages(data, target_kind, target_id, action, payload, "user")
        if target_kind == "page" and action in ("create", "update") and isinstance(result, dict) and result.get("id") and "name" in result:
            save_data(root, project, file_map[tab], data)
            _spawn_implied_tasks(root, project, result, "user", {"tab": tab, "kind": target_kind})
            data = load_data(root, project, file_map[tab])
    else:
        result = apply_tables(data, target_kind, target_id, action, payload, "user")
        if target_kind == "table" and action in ("create", "update") and isinstance(result, dict) and result.get("id") and "name" in result:
            save_data(root, project, file_map[tab], data)
            _spawn_implied_tasks(root, project, result, "user", {"tab": tab, "kind": target_kind})
            data = load_data(root, project, file_map[tab])
    save_data(root, project, file_map[tab], data)
    return result



