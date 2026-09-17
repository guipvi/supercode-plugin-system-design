# System Design — instruções para o cérebro e agentes

Você tem ferramentas MCP `system_design_*` para interagir com as abas do
plugin (projeto conceitual, sprint, páginas, tabelas).

## Regra de ouro (permissão)

- Você NUNCA escreve direto nos arquivos `.opencode/system-design/*.json`
  (sem `Edit`/`Write`/`Bash` nesses arquivos).
- Toda mudança vira PROPOSTA via `system_design_propose` (status `pending`).
- O usuário aprova ou rejeita cada proposta pela UI do plugin.
- A aba **projeto conceitual SEMPRE exige proposta+aprovação**, mesmo destravada.
- Alvos com `locked=true` REJEITAM propostas (erro). Não tente contornar:
  avise o usuário e aguarde ele destravar.
- Apenas o usuário decide propostas (não existe ferramenta de aprovar).

## Fluxo

1. Leia antes de propor: `system_design_get(project, tab)`.
2. Proponha com `reason` claro e `payload` mínimo (só os campos que mudam).
3. Informe ao usuário que a proposta está no inbox (aba do plugin, topo).
4. Acompanhe com `system_design_list_proposals(project, "pending")`.
5. Após aprovação, releia a aba para confirmar o estado aplicado.

## Alvos e ações

- `concept-element`: create|update|delete — elemento de interface/página/função/algoritmo.
- `concept-vision`: update — visão (objetivo, público, escopo, não-objetivos).
- `sprint-task`: create|update|move|delete — `status` em backlog|doing|done.
- `page`: create|update|delete. `page-element`: create|update|delete.
- `page-comment`: comment — `{elementId, text}` (comentário do agente).
- `table`: create|update|delete. `table-column`: create|update|delete.
- `relation`: create|update|delete.

## Limites

Respeite os limites do `store.py` (tamanhos, quantidades, enums). FKs e
relações precisam referenciar tabela.coluna existentes. Nunca proponha
renomear tabela/coluna referenciada (remova e recrie as dependências antes,
com aprovação do usuário para cada passo).
