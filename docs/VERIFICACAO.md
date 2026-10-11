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
