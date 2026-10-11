# Verificação — o que foi testado, como, e o que ficou por verificar

Registo honesto por fase. O que não está aqui não foi verificado.

## Fase 0 — Fundação (2026-10-11)

| Verificação | Comando | Resultado real |
|---|---|---|
| Configuração do Django | `manage.py check` | `System check identified no issues (0 silenced)` |
| Migrações | `manage.py migrate` | 18 migrações aplicadas, incluindo `livros.0001_initial` |
| Tabelas criadas | inspeção direta do `db.sqlite3` via `sqlite3` | `livros_livro`, `livros_linklivro`, `livros_notalivro` presentes |
| Modelo (15 testes) | `manage.py test livros` | 15/15 `OK` |
| Healthcheck por HTTP real | `curl http://127.0.0.1:8000/saude/` | `200`, `application/json`, `{"status": "ok", "bd": "ok"}` |
| Segredos fora do git | `git check-ignore -v .env db.sqlite3 .venv/bin/python` | os três ignorados pelo `.gitignore` |

Notas de desenho confirmadas **na fonte do Django** (não por suposição): a
`UniqueConstraint` com `data_leitura` nula não gera falso duplicado, porque
`UniqueConstraint.validate` sai cedo quando um campo da constraint é `NULL`
("NULL != NULL em SQL") — coerente com o comportamento do SQLite.

## Fase 1 — Autenticação e CRUD no site desktop (2026-10-11)

### Testes automáticos

`manage.py test` → **57/57 `OK`** (42 em 20 s na primeira execução).

Cobertura dos pontos que importam:

- **Acesso fechado**: `/`, `/livros/`, `/livros/novo/`, detalhe, edição e remoção de
  anónimo devolvem `302` para `/entrar/` com `next` preservado.
- **Sem registo público**: `/registar/`, `/registro/`, `/signup/`, `/accounts/signup/` → `404`.
- **Login/logout**: credenciais válidas entram; inválidas não criam sessão; `sair` por
  `POST` termina a sessão; `sair` por `GET` → `405` e a sessão mantém-se.
- **Isolamento entre utilizadores**: livro de outro utilizador dá `404` em detalhe,
  edição e remoção (e a alteração não chega a acontecer — confirmado com `refresh_from_db`).
- **Pertencimento**: um `POST` com `utilizador=<outro id>` continua a criar o livro
  para quem está autenticado.
- **Validação**: data no futuro rejeitada; título em branco rejeitado; avaliação fora de
  1-5 rejeitada; duplicado exato (título+autor+data) rejeitado **com mensagem no
  formulário**; releitura com data diferente aceite; dois livros "a ler" iguais aceites
  (coerente com a BD); editar sem mudar nada não dá erro.
- **Filtros e ordenação**: pesquisa por título, autor, texto de nota e descrição de URL
  (sem linhas duplicadas por causa das junções), filtro por estado, por avaliação e
  "sem avaliação", filtro inválido ignorado, ordenação por título/avaliação/recentes.
- **Contagens**: o número de cartões no HTML é comparado programaticamente com
  `Livro.objects.filter(utilizador=…).count()`; os contadores do resumo são comparados
  com agregações feitas na BD.
- **Paginação**: 25 livros → 20 na primeira página, 8 na segunda, "Página 2 de 2";
  `?page=999` → `404` (comportamento do Django, não rebenta).
- **Healthcheck**: `/saude/` → `200` JSON público.

### Verificação no browser real (Chrome via CDP)

Sessão injetada por `SessionStore` para uma **conta descartável** (`revisao`) — nunca
foram usadas credenciais reais.

| Verificação | Resultado |
|---|---|
| `/` sem sessão | `302` → `/entrar/?next=/livros/`; `next` preservado no formulário |
| Login em pt-PT | "Utilizador" / "Palavra-passe" (traduções do Django), sem CDN |
| CSS próprio servido | `getComputedStyle(body).backgroundColor` = `rgb(246, 244, 241)` |
| Lista | 8 cartões no DOM = 8 livros na BD; 8 badges de estado; 7 avaliações em estrelas |
| Cores de estado | borda esquerda do cartão "lido" = `rgb(21, 128, 61)` |
| Topbar | `position: sticky` confirmado |
| Ficha | título, estrelas grandes, 1 nota e 1 URL visíveis; links com `rel="noopener noreferrer"` |
| Formulário | 6 opções de estrelas (Sem avaliação + 1-5), `input type=date`, título obrigatório |
| Ecrã de telefone (390×844) | sem scroll horizontal (`scrollWidth == innerWidth == 390`), cartões empilhados |

### Defeito encontrado e corrigido nesta fase

A 390 px o botão "+ Novo livro" do topo **partia em duas linhas** (visível em
screenshot). Corrigido com `white-space: nowrap` nos botões e ocultando a navegação do
topo abaixo de 720 px (o cabeçalho da página já oferece as mesmas ações). Reverificado:
barra de topo com 61 px e uma só linha, sem scroll horizontal.

### Ainda não verificado (por fase)

- **Fase 2**: gestão de URLs e notas a partir da interface (o modelo e a cascata estão
  testados; os formulários de adicionar/remover ainda não existem).
- **Fase 3**: PWA. Nada feito.
- **Fase 5**: `manage.py check --deploy`, HTTPS, systemd, Nginx, DuckDNS.
- **Data no `type="date"`**: o browser de teste (locale `en-US`) mostra `mm/dd/yyyy`;
  num browser em pt-PT mostrará `dd/mm/aaaa`. O valor guardado é sempre ISO.
- **Acessibilidade**: foco visível e contraste foram desenhados, mas não medidos com
  ferramenta de acessibilidade nem testados com leitor de ecrã.

## Alteração pedida: data sempre em dd/mm/aaaa (2026-10-11)

O campo era `type="date"`, que mostra a data no formato do sistema do utilizador — no
browser de verificação aparecia `mm/dd/yyyy`. Passou a ser um campo de texto com widget
próprio (`DataBRWidget`), placeholder `dd/mm/aaaa` e `inputmode="numeric"`:

| Verificação | Resultado |
|---|---|
| `manage.py test` | 86/86 `OK` |
| Campo no browser | `type: text`, `valor: 14/08/2026`, `placeholder: dd/mm/aaaa` |
| Entrada em dd/mm/aaaa | aceite (`01/06/2025` → `date(2025, 6, 1)`) |
| Entrada em ISO | aceite por compatibilidade (`2025-06-01`) |
| Entrada com formato errado | rejeitada com «Escreve a data no formato dd/mm/aaaa (ex.: 14/08/2026).» |
| Listagem e ficha | já usavam `|date:"d/m/Y"` — `14/08/2026`, `11/10/2026 19:53` |

**Custo assumido:** perde-se o calendário nativo do browser. Não há forma de forçar o
formato de um `type="date"` — a escolha foi entre formato determinístico e calendário.

## Fase 2 — URLs e notas na ficha do livro (2026-10-11)

### Testes automáticos

86/86 `OK` (29 novos nesta fase):

- **Adicionar URL**: grava no livro certo, aceita descrição vazia, vários URLs no mesmo
  livro, `GET` → `405`, anónimo → `302` para o login, livro alheio → `404`.
- **URL inválido**: `400`, nada gravado, erro no formulário e **o texto escrito não se
  perde** (a ficha é redesenhada com o que o utilizador escreveu).
- **Apagar URL**: mantém o livro e as notas; URL de outro utilizador → `404`; `GET` → `405`.
- **Adicionar/apagar nota**: nota vazia rejeitada; várias notas ordenadas da mais recente;
  apagar nota mantém o livro e os URLs; nota alheia → `404`.
- **Sem token CSRF** (cliente com `enforce_csrf_checks`): criar URL, criar nota e apagar
  livro devolvem `403` e não alteram nada.
- **Ficha**: mostra os dois formulários de acrescentar, um botão de remover por item,
  contadores iguais ao que está na BD, links externos com `target="_blank"` e
  `rel="noopener noreferrer"`, e a data em `dd/mm/aaaa`.
- **Cascata pela interface**: apagar o livro apaga URLs e notas.

### Verificação no browser real (fluxo completo, com dados de exemplo)

| Passo | Resultado observado |
|---|---|
| Ficha do livro | 2 formulários de acrescentar, 1 URL e 1 nota existentes |
| Adicionar URL pela interface | mensagem «URL adicionado ao livro.», 2 URLs na página, texto novo visível |
| Adicionar nota pela interface | mensagem «Nota adicionada ao livro.», 2 notas na página |
| Remover URL pela interface | mensagem «URL removido.», 1 URL e **2 notas intactas** |
| Estado na BD (verificação independente) | `LinkLivro` e `NotaLivro` coerentes com o que a página mostrava |
| A 390 px | sem scroll horizontal; itens e botões alinhados |

### Defeito encontrado e corrigido nesta fase

Os itens de URL apareciam **empilhados e centrados** em vez de lado a lado. Causa:
`.lista-simples li` (especificidade 0,1,1) sobrepunha-se a `.item-relacao` (0,1,0).
Corrigido com `.lista-simples li.item-relacao`. Reverificado por medição no browser:
`flexDirection: row`, conteúdo à esquerda (x=151), botão à direita (x=1020), mesma linha,
sem transbordo do cartão. **Não era visível em testes de HTML — só em pixel.**

### Desvio ao plano

O plano previa `inlineformset_factory` para acrescentar 1-2 URLs/notas logo na criação do
livro. Não foi feito: os formulários de acrescentar vivem na ficha do livro, que é a única
superfície de edição (uma página a menos para manter, e é a mesma que a PWA mobile vai
reutilizar). Quem cria um livro é encaminhado para a lista com uma mensagem a lembrar que
a ficha do livro é onde se juntam URLs e notas.

### Dados reais já em uso

A conta `dinis` foi criada pelo próprio utilizador e tem um livro registado pela interface
(«O estrangeiro», Albert Camus, 01/09/2026, 5 estrelas) — gravado corretamente. Os dados de
exemplo usam uma conta separada (`revisao`) e nunca tocaram na conta real.

## Fase 3 — PWA mobile em /pwa/ (2026-10-11)

### Testes automáticos

120/120 `OK` (34 novos nesta fase, em `pwa/tests.py`):

- **Acesso**: `/pwa/` e `/pwa/novo/` sem sessão vão para `/pwa/entrar/` (e não para o
  login do site desktop); login mobile volta para a lista mobile e respeita `?next=`;
  `sair` volta à entrada mobile.
- **Sem CDNs**: o HTML do shell não contém `cdn`, `unpkg` nem `googleapis` (a app tem de
  funcionar offline).
- **Manifest**: content-type `application/manifest+json`, `Cache-Control: no-cache`, JSON
  válido, `name`/`start_url`/`scope`/`display`/`lang`, 4 ícones declarados com `any` e
  `maskable` em 192 e 512.
- **Service worker**: content-type JavaScript, `Service-Worker-Allowed: /pwa/`,
  `Cache-Control: no-cache`, versão da cache presente, e **zero restos de template**
  (`{%`, `{{`, `}}`); nomes de cache de estáticos e de dados presentes.
- **Lista**: cartões no HTML == livros na BD, só os do utilizador, carimbo de atualização,
  filtro por estado, pesquisa, paginação 25/página e **links de filtro sem parâmetros
  acumulados** (`estado=lido&estado=…`).
- **Escrita**: criar livro (data em `dd/mm/aaaa`), editar, apagar (cascata), adicionar e
  remover URL e nota, tudo com resposta em `/pwa/…`.
- **Recusas**: `GET` em endpoint de escrita → `405`; livro de outro utilizador → `404` em
  sete rotas diferentes (detalhe, editar, apagar, adicionar/remover URL e nota); sem CSRF →
  `403` (cliente com `enforce_csrf_checks`).

### Smoke test HTTP real

`scripts/smoke_test.py` (só biblioteca padrão, contra `runserver` a correr):
**61/61 verificações passaram**. Cria um utilizador descartável, extrai o CSRF do HTML do
login, autentica com cookie real, percorre o fluxo completo e compara a página com a BD;
apaga a conta no fim. Inclui o `Service-Worker-Allowed`, os content-types, o JSON do
manifest, os quatro ícones acessíveis, e as escritas reais (URL, nota, cascata).

### Verificação no browser real (Chrome, viewport Android 390×844)

| Verificação | Resultado observado |
|---|---|
| Registo do service worker | `scope: http://127.0.0.1:8000/pwa/`, estado `activated`, página controlada |
| Caches | `estante-estaticos-2026-10-11.3` e `estante-dados-2026-10-11.3`, só estas |
| Pré-cache de estáticos | pwa.css, pwa.js, 2 ícones, manifest, página offline |
| Instalabilidade (`Page.getInstallabilityErrors`) | **lista vazia** — a app é instalável |
| Alvos de toque | 8 alvos, mínimo **44 px**, nenhum abaixo |
| Scroll horizontal a 390 px | não (`scrollWidth == innerWidth == 390`) |
| Barra inferior | `position: fixed`; conteúdo com 84 px reservados + safe-area |
| Título muito longo (medido com elemento injetado) | trunca (visível 322 px de 789 px de texto), dentro do cartão |
| Escrita ponta a ponta | criar livro pelo telemóvel → ficha aberta com a mensagem |
| Convite a instalar | aparece (`beforeinstallprompt` disparou no Chrome de teste) |

### Offline (servidor desligado, não emulado)

A emulação de rede por CDP (`Network.emulateNetworkConditions offline`) **não** afeta os
pedidos feitos pelo próprio service worker — esse teste não prova nada. A verificação foi
feita **desligando o servidor**:

| Cenário | Resultado observado |
|---|---|
| Lista já visitada, sem servidor | vem da cache, com faixa «Sem ligação — a mostrar dados guardados em 11/10/2026, 20:34:07» |
| Posição da faixa | topo 58 px (mesmo ponto onde acaba a barra), sem sobrepor conteúdo, `sticky` |
| Página nunca guardada, sem servidor | cai na página de recurso «Sem ligação / Não há rede e esta página ainda não tinha sido guardada» |
| Servidor de volta | faixa desaparece e a página volta a ser servida pela rede |

### Defeitos encontrados e corrigidos nesta fase

1. **App instalada abria em cadeia.** Sem sessão, `/pwa/` redirecionava para `/entrar/`, o
   login do **site desktop**, e daí para `/livros/`. Corrigido com `login_url` próprio nas
   views da PWA (`LOGIN_PWA`). Apanhado por teste, não por inspeção.
2. **Título longo esticava o cartão em vez de ser cortado.** `min-width: auto` nos itens
   flex: o cartão crescia até 825 px dentro de uma página de 390 px. Corrigido com
   `min-width: 0` (aplica-se ao shell mobile e aos cartões do site desktop).
3. **Faixa de aviso fora do ecrã.** O service worker injetava o aviso antes de `</body>`,
   ou seja depois da barra inferior fixa: existia no DOM e não se via. Passou a ser
   injetado a seguir a `</header>`, dentro do fluxo. (A primeira tentativa, logo após
   `<body>`, ficava por baixo da barra de topo — também corrigida.)
4. **O teste de offline não testava nada.** Ver nota acima; a metodologia passou a ser
   desligar o servidor.

### Versões da cache (regra)

`PWA_CACHE_VERSION` subiu três vezes nesta fase: `.1` inicial, `.2` depois da correção de
`min-width` no CSS, `.3` depois do estilo da faixa de aviso. **Regra: qualquer alteração a
`pwa.css`, `pwa.js` ou aos ícones exige subir a constante**, e o telemóvel só adota a nova
versão quando o browser deteta o novo service worker (numa visita ou recarga seguinte) —
confirmado ao forçar `registration.update()` e ver a cache antiga desaparecer no `activate`.

### Ainda não verificado

- **Instalação real num telemóvel**: exige HTTPS (localhost não conta para o telefone).
  Fica para a fase 5, com o domínio DuckDNS.
- **iOS/Safari**: só está previsto o aviso com as instruções de «Adicionar ao ecrã
  principal»; não foi testado em iOS.
- **Leitor de ecrã / acessibilidade medida**: não testado com ferramenta.
- **PWA em produção**: nada disto corre ainda fora desta máquina.
