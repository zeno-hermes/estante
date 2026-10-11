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

## Fase 4 — Verificação final e documentação (2026-10-11)

### Suite completa

`manage.py test` → **120/120 `OK`** (0,9 s por teste em média; suite ~65 s).

### `manage.py check --deploy` (defeito real encontrado e corrigido)

Com `DEBUG=false` o Django recusou o arranque: **`mail.E001`** — backend de email de
desenvolvimento (`console`) em produção. Não era um aviso teórico: o Django considera
`console`, `dummy`, `filebased` e `locmem` backends de desenvolvimento. Corrigido:

- `DEBUG=true` → `console` (vê-se o email no terminal, como se quer em desenvolvimento);
- `DEBUG=false` → **SMTP** configurável por `.env` (`EMAIL_HOST`, `EMAIL_PORT`,
  `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`), documentado em `.env.example`.

Depois da correção: `System check identified no issues (0 silenced)`.

Também removi `PERMITIR_REGISTO` do `settings.py` e do `.env.example`: era configuração
morta, já que não existe rota de registo nenhuma (só `scripts/create_admin.py` cria contas).

### Aplicação em modo produção, com pedidos HTTP reais

Servidor a correr na porta 8001 com `DEBUG=false`, `ALLOWED_HOSTS=127.0.0.1,localhost` e
`SECURE_PROXY_SSL_HEADER` (a simular o Nginx com `X-Forwarded-Proto: https`):

| Verificação | Resultado observado |
|---|---|
| HTTP simples | `301` → `https://127.0.0.1:8001/saude/` |
| Atrás do proxy | `200`, `application/json` |
| Cabeçalhos de segurança | `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` |
| Página privada sem sessão | `302` → `/entrar/?next=/livros/` |
| Estáticos (WhiteNoise + manifest) | HTML referencia `estante.25f81d45728e.css` → `200`, `text/css`, 19 159 bytes |
| Compressão | com `Accept-Encoding: gzip` → **4 527 bytes** (era 19 159) |
| Estático inexistente | `404` |
| `collectstatic` | 138 ficheiros copiados, 406 pós-processados (`.gz` + hash no nome) |
| `MAILERS` em produção | `smtp.EmailBackend` |
| `STORAGES` de estáticos | `CompressedManifestStaticFilesStorage` |

### Backup e restauro (testados)

```bash
sqlite3 db.sqlite3 ".backup '…/estante-backup.sqlite3'"   # com a app a correr
cp estante-backup.sqlite3 restaurado.sqlite3
```

Comparação tabela a tabela entre a base de dados viva e o restauro: **14 tabelas, contagens
iguais** (`auth_user` 2, `django_session` 10, `livros_livro` 9, `livros_linklivro` 3,
`livros_notalivro` 7), e `PRAGMA integrity_check` → `ok` nos dois ficheiros.

### Segredos e repositório

| Verificação | Resultado |
|---|---|
| Valor da `SECRET_KEY` em ficheiros versionados | não aparece em nenhum (`git grep` do valor real) |
| `.env` | ignorado (`git check-ignore` → `.gitignore:6`) |
| Ficheiros de dados versionados (`*.sqlite3`, `.env`) | nenhum |
| Tokens GitHub no ambiente ou em ficheiros | nenhum |

### Acesso ao GitHub

- SSH a funcionar: `ssh -T git@github-zeno` → `Hi zeno-hermes! You've successfully authenticated…`
- `gh` **não está autenticado**, não há token no ambiente, no `~/.git-credentials` nem em
  `~/.config/gh/`, e o browser controlado não tem sessão GitHub iniciada (aparece «Sign in»).
- **Falta**: criar o repositório privado vazio `estante` na conta `zeno-hermes`. Depois disso
  o push é imediato (o remoto fica configurado para
  `git@github-zeno:zeno-hermes/estante.git`).

### Ainda por verificar

- Push e repositório no GitHub (bloqueado no ponto acima).
- Fase 5: tudo o que é da VM Oracle, HTTPS, DuckDNS, systemd, Nginx e Certbot.

## Fase 5 — Publicação com HTTPS (2026-10-11)

**URL pública: https://estante.duckdns.org/** — aplicação a correr numa VM Oracle Cloud
partilhada com outro serviço (isolada: utilizador, venv, base de dados, porta, serviço
systemd e vhost Nginx próprios).

Arquitetura: `HTTPS:443 → Nginx (TLS Let's Encrypt) → gunicorn em 127.0.0.1:8124 →
Django (estante.wsgi) + WhiteNoise → SQLite`. Os detalhes operacionais (endereços, chaves,
caminhos, firewall, certificados) ficam num runbook privado, fora do repositório — este
documento regista apenas o que foi verificado.

### Verificação a partir de fora (como um telemóvel qualquer)

| Verificação | Resultado observado |
|---|---|
| Certificado TLS | `subject=CN = estante.duckdns.org`, emitido por Let's Encrypt, válido 89 dias |
| HTTP → HTTPS | `301 https://estante.duckdns.org/` |
| `/saude/` | `200`, `application/json`, `{"status": "ok", "bd": "ok"}` |
| Cabeçalhos de segurança | `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` |
| `/` e `/livros/` sem sessão | `302` → `/entrar/?next=…` |
| `/pwa/` sem sessão | `302` → **`/pwa/entrar/`** (login da app, sem abertura em cadeia) |
| Manifest | `200 application/manifest+json` |
| `sw.js` | `200 application/javascript` + `Service-Worker-Allowed: /pwa/` |
| Estáticos com hash | `estante.25f81d45728e.css` → `200`, `text/css`, 19 159 bytes; com gzip 4 527 bytes |
| Ícone da PWA | `/static/pwa/icons/icon-192.png` → `200` |

### PWA sobre HTTPS (browser real, viewport Android 390×844)

| Verificação | Resultado observado |
|---|---|
| Contexto seguro | `window.isSecureContext: true` |
| Service worker | scope `https://estante.duckdns.org/pwa/`, `activated`, a controlar a página |
| Caches | `estante-estaticos-…` e `estante-dados-…` só com a versão atual |
| Instalabilidade | `Page.getInstallabilityErrors` → **lista vazia** (instalável no telemóvel) |
| Alvos de toque | mínimo 44 px, nenhum abaixo |
| Login e dados reais | a conta do Dinis entrou e «O estrangeiro» apareceu na lista |

### Offline em produção (serviço parado, não emulado)

| Cenário | Resultado observado |
|---|---|
| `systemctl stop estante.service` | `502` do Nginx — tratado como falta de rede pelo service worker |
| Recarregar `/pwa/` | lista da cache com a faixa «Sem ligação — a mostrar dados guardados em 11/10/2026, 21:24:38» e o livro visível |
| URL nunca visitado | página de recurso «Sem ligação / Não há nada guardado…» |
| Serviço religado | faixa desaparece, dados frescos da rede |

### Backup em produção

Cópia diária do SQLite com a API `.backup` (consistente com a aplicação a correr), guardando
as 14 mais recentes. **Restauro verificado**: contagens de `auth_user`, `livros_livro`,
`livros_linklivro` e `livros_notalivro` iguais às da base viva e
`PRAGMA integrity_check` → `ok`.

### Defeitos encontrados e corrigidos nesta fase

1. **Ficheiro de ambiente inválido.** A `SECRET_KEY` do Django contém `(`, `%`, `$`, `^`:
   escrito sem aspas, o ficheiro partia a leitura por shell (`syntax error near unexpected
   token`) e a aplicação não arrancava com as variáveis. Passou a ser escrito com os valores
   entre plicas e a verificação passou a incluir `set -a; . ficheiro` e comprimento de cada
   variável.
2. **A base de dados e os estáticos estavam dentro do checkout Git.** O `git reset --hard`
   do deploy mexe-lhes. Acrescentados `DB_PATH` e `STATIC_ROOT_DIR` (fora do checkout,
   valores por omissão iguais em desenvolvimento).
3. **A app mobile mostrava a página de erro do proxy.** Com o serviço parado o Nginx devolve
   `502` e o service worker só recorria à cache em falha de rede. Agora `5xx` é tratado como
   falta de rede (mostra o que estava guardado, com aviso).
4. **`cache.put()` sem `await`.** O service worker devolvia a resposta e podia ser terminado
   antes de a escrita concluir: a cache de dados ficava vazia e o offline só funcionava por
   sorte. Visto apenas em produção.
5. **O healthcheck do deploy aceitava um `301`.** `curl -f` não falha em redirecionamentos,
   portanto o script dizia «deploy ok» com a aplicação a redirecionar para HTTPS. Passou a
   verificar o **corpo** de `/saude/` (`"status": "ok"`) com `X-Forwarded-Proto: https`.
6. **O plugin Nginx do Certbot não estava instalado** na VM (`python3-certbot-nginx`), o que
   fazia o `certbot --nginx` falhar.

### Ainda por verificar (fase 5)

- **Instalação da app num telemóvel real**: o browser garante que é instalável
  (`installabilityErrors` vazio), mas a instalação em si tem de ser feita no telefone.
- **iOS/Safari**: o aviso com as instruções de «Adicionar ao ecrã principal» existe, mas não
  foi testado em iOS.
- **Avisos de expiração do certificado**: a conta Let's Encrypt foi criada sem email de
  contacto, portanto a renovação é automática mas não há aviso se falhar.
- **Acessibilidade medida** (leitor de ecrã, contraste com ferramenta): não testada.
- **Reinício da VM**: ambos os serviços estão `enabled`, mas não foi feito um reboot real
  (a VM serve outro serviço em produção).

## Correção — campo de data no telemóvel (11/10/2026)

Reportado pelo utilizador: na app mobile não aparecia calendário e o teclado só mostrava
números, sem tecla «/», pelo que era impossível escrever a data. Causa: o campo tinha sido
trocado para texto com `inputmode="numeric"` para garantir `dd/mm/aaaa`, e o teclado numérico
do Android não tem barra.

O que passou a existir (medido em viewport 390x844, no computador e em produção):

| Elemento | Medida |
| --- | --- |
| Campo de escrita | `type=text`, `inputmode=numeric`, `placeholder=dd/mm/aaaa`, 268x47 px |
| Botão de calendário | 48x47 px (toque ≥ 44), ícone SVG de 22x22 px visível |
| Campo nativo por cima | invisível (`opacity: 0`), **sem `name`** (não é submetido), alinhado |
| Escrita só com números | `2` → `24` → `24/0` → `24/09` → `24/09/2026` |
| Ano com dois dígitos | `14/08/26` → ao sair do campo → `14/08/2026` |
| Calendário | escolha de `2026-07-03` → campo passa a `03/07/2026` |
| Clique no botão | chama `showPicker()` do campo nativo (abre o calendário do sistema) |

Gravação verificada de ponta a ponta: livro criado a 24/09/2026 escrito só com números e
outro a 03/07/2026 escolhido no calendário, ambos com a data certa na ficha; a validação
«data no futuro» continua a recusar (apanhou uma tentativa de teste com 24/12/2026).
Em produção (`https://estante.duckdns.org/pwa/novo/`) confirmado o mesmo comportamento, sem
gravar nada. 133 testes verdes.

Dois defeitos encontrados pelo caminho:

1. **O botão do calendário estava vazio.** O indicador nativo do `type="date"`
   (`::-webkit-calendar-picker-indicator`) não é desenhado no Chrome em modo móvel: o botão
   ficava um quadrado branco. Passou a ter ícone SVG próprio, com o campo nativo invisível
   por cima para o toque continuar a abrir o calendário do sistema (iOS não tem `showPicker`).
2. **A cache do service worker guardava CSS/JS antigos.** O `install` fazia
   `cache.addAll(...)` e os pedidos iam à cache HTTP do browser: a cache nova
   (`...-2026-10-12.1`) continha o CSS e o JS **velhos** — o bump de versão parecia não pegar.
   Passou a `cache: 'reload'` em cada pedido, com teste de contrato sobre o `sw.js` renderizado.
   Versão da cache subida para `2026-10-12.2`.

Nada disto se vê em testes de HTML: só por medição no browser (`getBoundingClientRect`,
`getComputedStyle`, `caches.match(...)`) e depois de forçar `registration.update()`.
