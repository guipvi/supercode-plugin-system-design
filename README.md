# Plugin System Design (supercode)

Expande a interface do supercode para **design de sistemas** com 4 abas por
projeto: **projeto conceitual**, **sprint**, **páginas** e **tabelas**.

O chat (cérebro e agentes) **nunca edita direto**: ele cria **propostas** que
você aprova ou rejeita no inbox. Qualquer elemento pode ser **travado** (🔒)
para o sistema não conseguir mais alterá-lo.

## Arquivos

| Arquivo            | Papel                                                        |
|--------------------|--------------------------------------------------------------|
| `plugin.json`      | Manifesto (id `system-design`, capacidades, runtime)         |
| `ui.html`          | UI autocontida das 4 abas + inbox de propostas               |
| `store.py`         | Dados, validação e regras de permissão (usado pelo MCP)      |
| `mcp_server.py`    | Ferramentas `system_design_*` para o chat                    |
| `instructions.md`  | Regras que o cérebro/agentes devem seguir                    |
| `hooks/on_install.py` | Valida o manifesto na instalação                          |
| `tests/`           | Testes automatizados (`pytest`)                              |

## As 4 abas

- **Projeto conceitual** — no topo, seletor do projeto em edição. Formulários
  para visão (objetivo, público, escopo, não-objetivos) e elementos
  (interface, página, função, algoritmo). **Toda edição do chat aqui exige
  sua aprovação**, mesmo destravada.
- **Sprint** — backlog, executando e executado por projeto (criar, mover,
  editar, travar tarefas).
- **Páginas** — páginas + elementos com **comentários** por elemento e
  **comentário sobre o resultado final da página**. A prévia é a
  **simulação da página final**: quando existe `previewHtml` (captura
  estática da rota real, HTML+CSS inline) ela é exibida como o resultado
  de verdade; sem preview, os elementos são montados na ordem (design do
  editor visual quando existir) com clique para selecionar e comentar
  blocos. Inclui um **editor visual open-source (GrapesJS, MIT)**
  carregado somente quando você clica em "editor visual" (com fallback
  para o formulário se o CDN estiver fora).
- **Tabelas** — entidades, colunas (tipos, PK, FK, NOT NULL) e relações
  (1:1, 1:N, N:N) com validação referencial e **trava por tabela, coluna
  e relação**.

## Permissão e travas

- Chat → `system_design_propose` → proposta `pending` → você aprova/rejeita.
  Exceção: progresso de tasks com `owner=agent` é **direto** em tempo real
  (`system_design_task_update`: doing → executado → backlog, sem proposta).
- Aprovar origem com tasks embutidas cria as tarefas na sprint **com
  perguntas, dono e `afterAnswer` preservados** — os formulários do usuário
  aparecem no card da tarefa (v1.9.14).
- Alvo com 🔒 **rejeita proposta do chat com erro** e a UI **desabilita o
  botão Aprovar** até você destravar.
- Travar depois de propor também bloqueia a aprovação (re-checagem).
- Suas edições diretas nunca são bloqueadas.

## Dados

Por projeto, junto do código (acessível à UI e aos agentes):

```
<projeto>/.opencode/system-design/{concept,sprint,pages,tables,proposals}.json
```

## Instalação

1. Suba estes arquivos para um repositório público, ex.
   `github.com/<voce>/supercode-plugin-system-design`.
2. No painel do supercode, abra a aba **plugins** e adicione ao catálogo
   (`browser/plugins_catalog.json`, no servidor):
   ```json
   {
     "id": "system-design",
     "name": "System Design",
     "description": "Projeto conceitual, sprint, páginas e tabelas com aprovação e travas.",
     "github": "https://github.com/<voce>/supercode-plugin-system-design",
     "capabilities": ["ui", "mcp", "instructions", "agents", "hooks"],
     "category": "planning",
     "runtime": "sandbox",
     "env": []
   }
   ```
3. Clique em **Instalar** no catálogo. A aba do plugin aparece no painel.

## Testes

```bash
python3 -m pytest tests/ -q
```

51 testes: manifesto, dados/regras, ferramentas MCP, instruções, hooks,
estáticos da UI (sintaxe JS via esprima, wiring de ids, XSS/segredos) —
mais teste vivo no Chrome (fluxos das 4 abas, aprovação, travas, XSS,
path-traversal 403, limite 413, persistência e limpeza).
