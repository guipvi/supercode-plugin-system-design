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
- PROIBIDO criar arquivos `*-propostas*.json`, `*-v2.json` ou qualquer
  "scaffolding" de propostas fora de `.opencode/system-design/`: o inbox
  (proposals.json via `system_design_propose`) É a área de stage. Se as
  tools MCP estiverem indisponíveis, AVISE o usuário e aguarde — nunca
  despeje o conteúdo num arquivo solto "para depois".

## Execução e status (aprovação vira trabalho)

Aprovar NÃO executa: só registra. O trabalho acontece assim:

1. Quando o usuário pedir para executar (ex.: "execute a tarefa X" ou
   colar o prompt do botão "executar no chat"), leia a tarefa com
   `system_design_get(project, "sprint")`.
2. Proponha `sprint-task` action `move` para `doing` e aguarde aprovação.
3. Faça o trabalho de verdade no repo (código, migração, doc — o que a
   tarefa mandar), sem atalhos.
4. Proponha `move` para `done` + uma proposta `page-comment`
   (action `comment`) na página/elemento afetado com o resumo do que foi
   feito (arquivos, comandos de verificação).
5. Se travar, NÃO fique em silêncio: proponha `move` de volta para
   `backlog` com o motivo em `reason` e explique ao usuário.

## Relatório de status (dizer o que foi executado)

Quando o usuário perguntar "o que já foi feito / está em execução",
NUNCA responda de memória: leia na hora `system_design_get` das 4 abas
+ `system_design_list_proposals(project, "all")` e responda com números
exatos: aprovadas aplicadas (por aba), pendentes aguardando avaliação,
rejeitadas, tarefas por status (backlog/doing/done) e o próximo passo
concreto. Sem leitura, sem resposta.

## Conceito implica tarefas (pacote único)

Tarefas NÃO vão ao inbox separadas: nascem descritas no conceito.

- `concept-element` em `create` exige `tasks` com ao menos 1 tarefa
  `{title, desc?, priority?, status?}` — sem isso o propose é rejeitado.
- `status` pode vir `done` com evidência quando o repo já executa
  (sistemas existentes): cheque o código antes e cite a evidência no
  `desc`/`reason` (arquivo, teste, migração).
- Aprovar o conceito cria as tasks na sprint automaticamente (sem carta
  separada, sem nova aprovação). Títulos duplicados são ignorados.
- Nunca proponha `sprint-task` avulsa para trabalho que pertence a um
  conceito: embuta no elemento (crie o elemento com `tasks`, ou proponha
  `update` adicionando `tasks` ao elemento aprovado).
