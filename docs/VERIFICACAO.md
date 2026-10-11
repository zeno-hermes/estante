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
