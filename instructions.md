# System Design — instruções para o cérebro e agentes

Você tem ferramentas MCP `system_design_*` para interagir com as abas do
plugin (projeto conceitual, sprint, páginas, tabelas, propostas).

## Regra de ouro (permissão)

- Você NUNCA escreve direto nos arquivos `.opencode/system-design/*.json`
  (sem `Edit`/`Write`/`Bash` nesses arquivos).
- Toda mudança vira PROPOSTA via `system_design_propose` (status `pending`).
- O usuário aprova ou rejeita cada proposta pela UI do plugin.
- A aba **projeto conceitual SEMPRE exige proposta+aprovação**.
- Não existem travas: nada fica bloqueado. O usuário pode reescrever
  qualquer item e movê-lo de volta (ex.: tarefa para backlog) a qualquer
  momento — reescrever é o controle, não travar.
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
- `sprint-task`: update|move|delete — `status` em backlog|doing|done
  (progresso e correções; `create` é rejeitado: tarefas nascem de
  aprovações, nunca avulsas).
- `page`: create|update|delete. `previewHtml` (update) aceita a captura
  estática do resultado final da rota (HTML sem scripts + CSS inline) —
  quando presente, a aba Páginas mostra esse preview na simulação em vez
  da composição dos elementos. `page-element`: create|update|delete.
- `page-comment`: comment — `{elementId|pageId, text}` (comentário do agente no elemento ou no resultado final da página).
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

## Origem implica tarefas (nada avulso)

O usuário aprova páginas, algoritmos, elementos, conceitos, tabelas e
relacionamentos — NUNCA tarefas avulsas. Tarefas nascem indiretamente:

- `concept-element`, `page` e `table` em `create` exigem `tasks` com ao
  menos 1 tarefa `{title, desc?, priority?, status?}` — sem isso o
  `propose` é rejeitado.
- `page` em `create` também exige `elements` (ao menos 1 com `label`);
  `table` em `create` também exige `columns` (ao menos 1 com `name`).
  Página sem elementos e tabela sem colunas são rejeitadas como genéricas.
- `sprint-task` em `create` é REJEITADO sempre: embuta o trabalho na
  origem (crie a origem com `tasks`, ou proponha `update` adicionando
  `tasks` à origem aprovada).
- `status` pode vir `done` com evidência quando o repo já executa
  (sistemas existentes): cheque o código e cite a evidência no
  `desc`/`reason` (arquivo, teste, migração).
- Aprovar a origem cria as tasks na sprint com `origin` registrada
  (tab/kind/id/título) — sem carta separada, sem nova aprovação.
  Títulos duplicados são ignorados.
- Movimentação e correção (`update`/`move`/`delete` em `sprint-task`)
  continuam valendo para relatar progresso e corrigir.
- `relation` somente após as tabelas existirem aprovadas (o dry-run
  rejeita FK para tabela inexistente — proponha as tabelas primeiro,
  aguarde aprovação, depois proponha as relações).

## Propostas = briefings sintéticos

Toda proposta que você envia (`page`, `concept-element`, `concept-vision`,
`table`, `relation`) deve se parecer com um **briefing sintético**, não com
dump estrutural ou especificação longa. Format:

- **1 frase de objetivo** (o quê e por quê) no `description`/`desc`/
  `reason` — concreta, sem gerúndio genérico.
- **3–6 linhas de miolo**: público/contexto, tom/estilo visual esperado,
  seções-chave na ordem (o que aparece em cada uma), dado de estado
  necessário (vazio/carregando/erro) e CTA principal.
- **Critério de pronto** em 1 linha (o que o diretor de arte deve ver
  para aprovar).
- Nada de listas exaustivas de tags/classes, JSON de layout ou prosa
  decorativa. `elements` continua exigido (é estrutura), mas cada
  `label` curto e cada `content` em 1 linha.

Briefing bom: *"Página de checkout única para confirmar o plano mensal do
psicólogo antes do pagamento: topo com resumo do pedido (plano, valor,
cobrança mensal), meio com cartão/Pix em abas, base com total e CTA
'Pagar R$ X' fixo. Tom sóbrio (azul escuro + branco), estados de erro
inline no campo. Pronto quando o diretore consegue imaginar a tela sem
ver o código."*

## Captura do resultado real (`previewHtml`) — todas as páginas

A aba Páginas deve renderizar TODA página como protótipo do resultado
final (para o diretor de arte comentar). Prioridade: `previewHtml`
(HTML estático da rota real, sem scripts, com `<style>` inline, `<base>`
para assets relativos e nós anotados com `data-sim-id` das `elements`) →
senão, a composição `buildSimDoc`.

Fluxo de captura (rota existente em produção — faça para página nova ou
recriar após mudança visual relevante):

1. Navegue o Chrome compartilhado na rota real
   (`https://<app>/<route>`) e aguarde a hidratação.
2. Naquele origin, `evaluate`: clone `document.documentElement`, remova
   `script`, troque cada `link[rel=stylesheet]` pelo CSS (`fetch` +
   `<style>`), injete `<base href="https://<app>/">`, serialice
   `<!doctype html>` + `outerHTML`, comprima (gzip+base64) e **acrescente**
    ao acumulador `window.name` `SDCAP2|` + `JSON.stringify([{id,gz},...])`
    — o `window.name` persiste entre navegações **same-origin** (dá para
    capturar várias rotas seguidas sem ir ao painel; ~800KB testados ok).
    **Lote curto: salte para o painel a cada ~5 capturas** — qualquer
    página de erro/interstício do navegador (ex.: chrome-error) **apaga o
    `window.name`** e o lote inteiro se perde.
3. Entrega por **navegação top-level com hash** (o hash fica no cliente,
   não vai ao servidor): `location.href = '<host>/plugins/system-design/ui#sd=' +
   encodeURIComponent(JSON.stringify(entries))` (via `setTimeout(…,150)`
   para o `evaluate` retornar antes da navegação). No `boot()`,
   `sdIngestName()` lê `#sd=` (fallback: `SDCAP2|` no `window.name`),
   faz gunzip de cada `gz`, anota os `data-sim-id` (heurística
   label/conteúdo↔DOM), **recomprime e grava `previewHtml` como
   `'gz:'+base64`** (o arquivo `pages.json` tem limite de 2MB alinhado ao
   store; HTML cru de ~28 páginas não caberia), hidrata em memória
   (`PREV_RAW`/`previewRawOf`) para o render, limpa hash+name, mostra o
   toast *Capturas ingeridas* e expõe `window.__sdIngest`
   (`{total, ok, errs, ids}`).
4. Confirme com `evaluate` lendo `window.__sdIngest` e o badge
   *resultado real capturado*; recarregue a UI principal (outra aba)
   para enxergar os dados salvos.

Regras: rota que redireciona para login (exige auth) ou é dinâmica
(`/:slug`) fica sem captura e usa o fallback de composição — não grave
tela de login como se fosse a página-alvo. Canais testados e FIRMES:
`fetch` HTTPS→HTTP (mixed content), iframe de terceiros (cookie
SameSite não vai → API sem sessão), `window.open`/`postMessage` entre
abas (popup bloqueado) e `window.name` cross-origin (navegador limpa).
Válido: acumular same-origin em `window.name` + jump no hash
(existe também o receiver `sd-capture` via `postMessage`, reserva).

## Qualidade mínima (anti-genérico)

O `propose` REJEITA com erro proposta genérica — não tente contornar,
melhore o conteúdo:

- `concept-element` / `page` / `table` em `create`: `description`
  (ou `desc`) com 20+ caracteres reais + `tasks` com ao menos 1 tarefa
  + (`page`: `elements` com ≥1 `label` · `table`: `columns` com ≥1 `name`).
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

Aprovar NÃO executa: só registra (e materializa as tarefas na sprint).
O trabalho acontece assim:

1. Quando o usuário pedir para executar (ex.: "execute a tarefa X" ou
   colar o prompt do botão "executar no chat"), leia a tarefa com
   `system_design_get(project, "sprint")` — filtre por origem/status
   como o usuário faria na UI.
2. Proponha `sprint-task` action `move` para `doing` e aguarde aprovação.
3. Faça o trabalho de verdade no repo (código, migração, doc — o que a
   tarefa mandar), sem atalhos.
4. Proponha `move` para `done` + uma proposta `page-comment`
   (action `comment`) na página/elemento afetado com o resumo do que foi
   feito (arquivos, comandos de verificação).
5. Se emperrar, NÃO fique em silêncio: proponha `move` de volta para
   `backlog` com o motivo em `reason` e explique ao usuário. O usuário
   também pode reescrever a tarefa e movê-la de volta quando quiser.

## Relatório de status (dizer o que foi executado)

Quando o usuário perguntar "o que já foi feito / está em execução",
NUNCA responda de memória: leia na hora `system_design_get` das 4 abas
+ `system_design_list_proposals(project, "all")` e responda com números
exatos: aprovadas aplicadas (por aba), pendentes aguardando avaliação,
rejeitadas, tarefas por status (backlog/doing/done) e o próximo passo
concreto. Sem leitura, sem resposta. Na sprint, filtre por origem
(tab/kind), status e prioridade como a UI faz.

## Sprint em tempo real (você também enxerga)

A aba sprint se atualiza sozinha via JavaScript — e você deve fazer o
mesmo: antes de falar de sprint, RELEIA com `system_design_get` (é o
"tempo real" do agente). Use os mesmos filtros da UI: texto, origem
(concept/pages/tables), dono (agent/user) e prioridade mínima.

## Dono e prioridade 1–10

- Toda task tem `owner`: `agent` (vez do modelo trabalhar) ou `user`
  (vez do humano avaliar). Criadas nascem do agente; muda de lado
  conforme o estágio — e ambos podem ajustar manualmente.
- `priority` é inteiro de **1 (baixo) a 10 (muito alta)**. O usuário muda
  na UI e você DEVE ler antes de escolher o que fazer. Você também dá
  prioridade às suas tasks para o usuário (edite direto se for sua).
- Para responder "o que eu faço agora", ordene: dono=user primeiro?
  Não — dono=agent com priority alta, exceto o que aguarda o usuário.

## Colunas e matriz de movimento

Colunas: backlog → doing → executado → solicitacao_testes →
aguardando_aprovacao (volta para executado). Quem move o quê:

- `solicitacao_testes` SÓ a partir de `executado`, e SÓ o usuário move.
- `aguardando_aprovacao` SÓ a partir de `solicitacao_testes`, e SÓ você
  (agente) move. Ao chegar aí, o dono vira o usuário.
- De `aguardando_aprovacao` SÓ se sai para `executado`, e SÓ o usuário.
- No resto (backlog/doing/executado), ambos movem livremente — inclusive
  voltar para backlog reescrevendo.

## Edição direta nas suas tasks (sem proposta)

Use `system_design_task_update(project, task_id, payload_json)` para
mexer DIRETO nas tasks com `owner=agent` (título, desc, priority,
owner, status com a matriz acima) — sem proposta, com o usuário vendo
em tempo real. Tarefa com `owner=user`: NÃO edite, proponha
(`system_design_propose`). Nunca use arquivos: só as tools.


## Formulário de execução (perguntas que movem a task)

Toda task criada pelo agente PODE trazer `questions` (no brief embutido):
`[{question, type?, options?, answer?}]`, `type` em text|choice|yesno
(choice exige `options`). E `afterAnswer`: `executado` (padrão) ou
`solicitacao_testes`.

- Na UI, perguntas sem resposta viram FORMULÁRIO no card. Responder
  tudo move automaticamente: para `executado`, ou compondo
  backlog→executado→`solicitacao_testes` (só o usuário; para você,
  agente, para em `executado` e o dono vira o usuário).
- Resposta parcial não move. Tipo `choice` fora das opções é rejeitado.
- Para criar o formulário, embuta `questions` (e `afterAnswer` quando
  for caso de teste) nas `tasks` do conceito/página/tabela. Para
  responder como agente nas suas tasks, use `system_design_task_update`
  com `questions` completo (ids preservados).
- Nunca invente resposta pelo usuário: sem resposta dele, sem avanço.

## Task dirigida a você = tutorial

Quando a task tem `owner=user` (ou vai terminar com você executando —
`afterAnswer` responder→executado/testes), a `desc` NÃO é resumo: é um
TUTORIAL de execução, com:

1. Objetivo em 1 frase.
2. Passos numerados (1., 2., 3…) concretos, um por linha.
3. Links clicáveis no formato `[texto](https://…)` — doc oficial,
   repo, ticket, arquivo relevante. Mínimo 1 link quando existir
   documentação. Sem inventar URL: use fonte real ou diga "sem doc".
4. Critério de pronto (o que conta como feito) e o que responder nas
   `questions` do formulário, se houver.

A UI renderiza `desc` com os links clicáveis no botão **ver** da task
(/modal de detalhe). Não encaixote o tutorial só no chat: ele vive na
`desc`.

## Colunas da tabela no mesmo create

`table` em `create` ACEITA E EXIGE `columns: [{name, type?, pk?, nullable?, desc?, fk?}]`
com ao menos 1 coluna — sem colunas o `propose` é rejeitado (tabela vazia
não modela nada). A UI lista os nomes (chave/PK e FK no título). Modele
tudo de uma vez; colunas novas depois vão em `table-column` create.

## Elementos da página no mesmo create

`page` em `create` ACEITA E EXIGE `elements: [{type?, label, content?, order?, snapshotHtml?}]`
com ao menos 1 elemento — sem elementos o `propose` é rejeitado (página
vazia não renderiza design). Tipos: texto|cabecalho|botao|formulario|
imagem|lista|navegacao|outro. `order` define a pilha visual; `snapshotHtml`
(opcional) é a última versão HTML do bloco (editor visual) e é o que a UI
mostra na prévia ao abrir a página. Elementos novos depois vão em
`page-element` create; design visual em `page-element` update com
`snapshotHtml`. Páginas já existentes sem elementos: proponha `page`
action `update` com `elements` (mesmo formato) para preencher de uma vez.
