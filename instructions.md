# System Design — instruções para o cérebro e agentes

Você tem ferramentas MCP `system_design_*` para interagir com as abas do
plugin (projeto conceitual, sprint, páginas, tabelas, propostas).

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

## Visão primeiro (ordem obrigatória)

1. Em projeto novo ou com visão vazia, proponha SEMPRE `concept-vision`
   (action `update`) antes de qualquer outra coisa — e aguarde a aprovação.
2. Toda proposta seguinte deve ser coerente com a visão aprovada: releia
   com `system_design_get(project, "concept")` e só proponha o que decorre
   dela. Se a visão mudar, revise as propostas pendentes antes de criar novas.
3. Ao conversar com o usuário, fale a partir do estado atual: consulte
   `system_design_list_proposals(project, "pending")` e cite quantas
   propostas aguardam avaliação e de quais abas.

## Propostas em cadeia (conceito implica execução)

Conceito e execução NÃO são coisas separadas: aprovar um conceito exige
dar consequência a ele. Por isso, toda proposta de `concept-element`
deve vir acompanhada das propostas implicadas, no mesmo lote:

- `sprint-task` (backlog) com o trabalho de implementar o conceito;
- `page` / `page-element` quando o conceito tem superfície visível;
- `table` / `table-column` quando o conceito persiste dados;
- `relation` somente após as tabelas existirem aprovadas (o dry-run
  rejeita FK para tabela inexistente — proponha as tabelas primeiro,
  aguarde aprovação, depois proponha as relações).

Indique a cadeia no `reason` de cada proposta (ex.: "decorre do conceito
'Checkout'; tarefa de implementação"). Se o usuário rejeitar o conceito,
considere as propostas encadeadas órfãs e avise antes de re-propô-las.

## Qualidade mínima (anti-genérico)

O `propose` REJEITA com erro proposta genérica — não tente contornar,
melhore o conteúdo:

- `concept-element` / `sprint-task` / `page` em `create`: `description`
  (ou `desc`) com 20+ caracteres reais. "Título + referência solta"
  (ex.: só nome + arquivo) é rejeitado.
- `concept-vision`: ao menos 1 dos 4 campos preenchido.
- Regra de bolso: cada proposta deve responder *o quê*, *por quê* e
  *onde vive no repo*. Elemento de interface/página sem descrição do
  comportamento não entra nem no inbox.
- Tabelas e relações são estruturadas (colunas/FKs dispensam texto
  longo), mas coluna sem tipo correto ou FK para tabela inexistente
  também é rejeitada.

## Artefatos sempre registrados (nada solto)

A aba design só enxerga os 5 JSONs de `.opencode/system-design/` — PDF,
imagem, planilha, doc ou diagrama solto no projeto é INVISÍVEL para ela.
Por isso, todo artefato que represente o sistema deve ser REGISTRADO:

- Gerou um arquivo para o projeto (ex.: cronograma PDF, mock, diagrama)?
  Crie na mesma hora uma proposta `page-comment` (action `comment`)
  com `{elementId, text}` onde `text` traz o **path do arquivo + o que
  ele representa** — ou um `concept-element` com o path em
  `description`/`details`.
- Nunca considere "entregue" um arquivo que não esteja referenciado em
  proposta aprovada ou pendente. Arquivo solto = trabalho invisível.
- Vale também para outputs de sandbox/downloads: copie para dentro do
  projeto e registre; `downloads/` e `/tmp/` não são o projeto.
