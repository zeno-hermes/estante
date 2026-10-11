# Estante — registo de livros lidos (plano de implementação)

> **For Hermes:** plano para execução por fases. Dinis quer feedback após cada fase implementada; não avançar para a fase seguinte sem OK.
> **Nota:** este plano é a fase de desenho. Nada foi criado em disco ainda.

**Goal:** Uma aplicação web pessoal para registar os livros lidos — CRUD de livros (título, autor, data de leitura, avaliação, estado) com URLs e notas associados em 1:N, autenticação de utilizador único, interface desktop limpa e moderna e uma PWA instalável no telemóvel que parece uma app nativa.

**Architecture:** Projeto Django único, com duas superfícies separadas:
1. **Site desktop** (`livros/`) — HTML renderizado no servidor, shell com topbar, lista em cartões, forms clássicos e autenticação por sessão do próprio Django.
2. **PWA mobile** (`pwa/`, montada em `/pwa/`) — shell próprio mobile-first, manifest, service worker e tab bar fixa no fundo, isolada do site principal e replicando o padrão já validado no DjangoClaw (`/home/claw/projects/web/django-project/pwa`).

Camada de dados: modelos Django com `ForeignKey` para o utilizador (tudo scoped por `request.user` desde o primeiro dia, mesmo sendo só uma conta — é o que evita uma migração dolorosa mais tarde).

**Tech Stack:** Python 3.12 (via `uv`), Django 6.1.2, SQLite, templates Django + CSS próprio (sem CDN, sem framework JS), WhiteNoise para estáticos, Gunicorn apenas na fase de publicação.

---

## 1. Contexto e decisões (com o porquê)

### Respostas do Dinis
| Pergunta | Resposta |
|---|---|
| Onde usar | Local nesta máquina **+ publicar na internet no fim** (HTTPS, instalável no telemóvel) |
| Contas | **Só a conta do Dinis**, criada por mim; registo público desligado |
| Campos extra | **Avaliação (1-5)** e **Estado (a ler / lido / abandonado)** |
| Data de leitura | **Data única** (dia em que acabou o livro) |
| Interface mobile de referência | A app `/pwa/` do DjangoClaw — **seguir o mesmo padrão** |

### Porque Django + SQLite (e não FastAPI/Flask/Postgres/Laravel)
- **Django**: autenticação (hash de password, sessões, login/logout, CSRF, `login_required`) e o CRUD com forms e validação vêm feitos. Em FastAPI/Flask isto é código escrito à mão — mais superfície para bugs e mais trabalho, sem qualquer ganho num CRUD de um utilizador.
- **SQLite**: é uma lista pessoal de livros, escrita rara, um utilizador. Zero administração de servidor de BD, backup = copiar um ficheiro (`db.sqlite3`), e o `smoke_test` corre contra ficheiro real sem infraestrutura. PostgreSQL só faria sentido com escrita concorrente/multiusuário; nesse dia, a migração em Django são 4 linhas em `settings.py`.
- **Não Laravel**: já há Laravel no ClearDraw, mas para este caso obrigaria a PHP + Artisan + Composer + base de dados, tudo para replicar o que o Django já dá de fábrica. Mais atrito, nenhum benefício.
- **Python 3.12 do sistema** (não o 3.14 do Hermes nem o `python3.14` do cache): Django 6.1 suporta 3.12–3.14, e 3.12 é o que o Ubuntu 24.04 mantém com patches de segurança. O venv é criado com `uv venv --python 3.12`.

### Restrição técnica que já conhecemos
A PWA **só é instalável (ícone no launcher) em `localhost` ou HTTPS**. Em `http://192.168.x.x` a LAN não conta como contexto seguro: o browser não regista o service worker nem oferece instalação. Isto condiciona a fase de publicação — não é um bug a resolver, é como os browsers funcionam. Em desenvolvimento valido com `localhost:8000`; a instalação real no telemóvel acontece na fase 5, quando houver HTTPS.

---

## 2. Estrutura de ficheiros (alvo)

```
/home/claw/projects/web/estante/           # raiz do projeto, repo git (branch main)
├── .env.example                           # variáveis documentadas, sem segredos
├── .gitignore                             # .venv/, db.sqlite3, .env, __pycache__, media/
├── README.md                              # o que é, como correr, como testar
├── manage.py
├── requirements.txt                       # versões fixadas
├── db.sqlite3                             # fora do git
├── estante/                               # pacote do projeto
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py / asgi.py
│   └── views.py                           # home (redirect), /saude/
├── livros/                                # app do domínio
│   ├── models.py                          # Livro, LinkLivro, NotaLivro
│   ├── forms.py                           # LivroForm, LinkLivroForm, NotaLivroForm
│   ├── views.py                           # lista, detalhe, criar, editar, apagar, urls, notas
│   ├── urls.py
│   ├── admin.py                           # registo para inspeção/debug
│   ├── migrations/
│   ├── tests/
│   │   ├── test_models.py
│   │   ├── test_views_crud.py
│   │   ├── test_views_auth.py
│   │   └── test_relacoes.py               # URLs e notas 1:N
│   └── templates/livros/
│       ├── base.html
│       ├── entrar.html
│       ├── lista.html  detalhe.html  form.html  confirmar_apagar.html
├── pwa/                                   # app PWA mobile
│   ├── views.py                           # páginas + manifest + sw.js + PWA_CACHE_VERSION
│   ├── urls.py
│   ├── templates/pwa/
│   │   ├── base.html                      # shell mobile (sem CDNs)
│   │   ├── manifest.webmanifest
│   │   ├── sw.js
│   │   ├── entrar.html  lista.html  detalhe.html  form.html
│   └── static/pwa/
│       ├── pwa.css  pwa.js
│       ├── icons/  (icon-192.png, icon-512.png, maskable-192.png, maskable-512.png)
│       └── scripts/generate_icons.py      # Pillow, gera os ícones
├── scripts/
│   ├── create_admin.py                    # cria/atualiza a conta do Dinis
│   └── smoke_test.py                      # verificação HTTP real (stdlib urllib + cookiejar)
└── docs/
    ├── PLANO.md                           # este plano (cópia dentro do repo)
    └── VERIFICACAO.md                     # o que foi verificado e como, por fase
```

---

## 3. Modelo de dados

```python
# livros/models.py
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Livro(models.Model):
    class Estado(models.TextChoices):
        A_LER = "a_ler", "A ler"
        LIDO = "lido", "Lido"
        ABANDONADO = "abandonado", "Abandonado"

    utilizador = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="livros"
    )
    titulo = models.CharField("título", max_length=300)
    autor = models.CharField("autor", max_length=200)
    data_leitura = models.DateField(
        "data de leitura", null=True, blank=True,
        help_text="Dia em que acabaste o livro (vazio enquanto estiveres a ler).",
    )
    avaliacao = models.PositiveSmallIntegerField(
        "avaliação", null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.LIDO)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data_leitura", "-criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["utilizador", "titulo", "autor", "data_leitura"],
                name="unico_por_utilizador_titulo_autor_data",
            )
        ]

    def __str__(self):
        return f"{self.titulo} — {self.autor}"


class LinkLivro(models.Model):
    """URL associado a um livro: 1 livro -> N URLs."""
    livro = models.ForeignKey(Livro, on_delete=models.CASCADE, related_name="urls")
    url = models.URLField("endereço")
    descricao = models.CharField("descrição", max_length=150, blank=True)

    class Meta:
        ordering = ["id"]


class NotaLivro(models.Model):
    """Nota de texto sobre um livro: 1 livro -> N notas."""
    livro = models.ForeignKey(Livro, on_delete=models.CASCADE, related_name="notas")
    texto = models.TextField("nota")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
```

Notas de desenho:
- **`UniqueConstraint` (utilizador, título, autor, data_leitura)** — releituras são permitidas (mesmo livro, datas diferentes); o que não pode é o registo exato duplicado. `data_leitura` é nullable (livro a ler), e em SQL `NULL` não colide com `NULL` — dois livros "a ler" com o mesmo título/autor passam, o que é aceitável.
- **`estado` com default `lido`** — é "livros que tenho lido"; `a_ler` e `abandonado` foram pedidos como opção.
- **`data_leitura` nullable** — coerente com um livro em `a_ler`.
- **Cascade** em URLs e notas: apagar o livro apaga o que lhe pertence (nada de órfãos).

---

## 4. Mapa de rotas

### Site desktop
| Rota | Nome | O que faz |
|---|---|---|
| `/` | `home` | 302 → `/livros/` (ou `/entrar/` se anónimo) |
| `/entrar/` | `login` | form de login (template próprio em pt-PT) |
| `/sair/` | `logout` | POST, faz logout e volta a `/entrar/` |
| `/livros/` | `livro_lista` | lista paginada (20/pág.) com `?q=`, `?estado=`, `?avaliacao=`, `?order=` |
| `/livros/novo/` | `livro_criar` | criar livro + URLs/notas iniciais (inline formset) |
| `/livros/<pk>/` | `livro_detalhe` | ficha do livro, URLs clicáveis, notas |
| `/livros/<pk>/editar/` | `livro_editar` | editar campos + gerir URLs/notas existentes |
| `/livros/<pk>/apagar/` | `livro_apagar` | confirmação → POST → apaga |
| `/livros/<pk>/urls/novo/` | `url_criar` | acrescentar URL |
| `/urls/<pk>/apagar/` | `url_apagar` | remover URL |
| `/livros/<pk>/notas/nova/` | `nota_criar` | acrescentar nota |
| `/notas/<pk>/apagar/` | `nota_apagar` | remover nota |
| `/saude/` | `saude` | JSON `{"status":"ok","bd":"ok"}` — público, para deploy/monitor |

### PWA mobile (`/pwa/`)
| Rota | O que faz |
|---|---|
| `/pwa/` | lista de livros (cartões, tab bar; caminho do dia-a-dia) |
| `/pwa/entrar/` | login dentro do shell mobile |
| `/pwa/livro/<pk>/` | detalhe + notas + URLs |
| `/pwa/livro/<pk>/editar/` | edição rápida (mobile) |
| `/pwa/novo/` | criar livro |
| `/pwa/manifest.webmanifest` | manifest com `Content-Type: application/manifest+json`, `scope`/`start_url` = `/pwa/` |
| `/pwa/sw.js` | service worker com `Service-Worker-Allowed: /pwa/`, `Cache-Control: no-cache` |

Tudo autenticado (`LoginRequiredMixin` / `@login_required`), nada de `staff` obrigatório — a PWA é a app do Dinis, não um painel de administração. Login de um utilizador anónimo em `/pwa/` faz 302 para `/pwa/entrar/`, não para o login do site desktop (evita a "abertura em cadeia" da app instalada).

---

## 5. Plano por fases

> Cada fase termina com **verificação real** e um **relatório curto ao Dinis** (o que ficou feito, saída dos testes, o que ficou por verificar). Sem OK explícito, não começo a fase seguinte.

### Fase 0 — Fundação (repo, Django, modelo, migração)
Objetivo: projeto a arrancar e o modelo de dados criado. Nada de UI ainda.

1. `mkdir -p /home/claw/projects/web/estante && cd` lá; `git init -b main`.
2. `uv venv --python 3.12 .venv` e `uv pip install --python .venv/bin/python django==6.1.2 "Pillow==11.*" whitenoise`.
3. `django-admin startproject estante .` e `manage.py startapp livros`.
4. `settings.py`: `LANGUAGE_CODE="pt-pt"`, `TIME_ZONE="Europe/Lisbon"`, `USE_TZ=True`, `INSTALLED_APPS += ["livros"]`, `LOGIN_URL="/entrar/"`, `LOGIN_REDIRECT_URL="/livros/"`, `LOGOUT_REDIRECT_URL="/entrar/"`, `SECRET_KEY` e `DEBUG` lidos de `.env`, `WhiteNoise` no MIDDLEWARE. **Nenhum segredo no repositório** — `.env` no `.gitignore`, `.env.example` versionado.
5. Escrever `livros/models.py` (secção 3) + `makemigrations livros && migrate`.
6. Admin registado (útil para inspeção; não é a interface do dia-a-dia).
7. `.gitignore`, `README.md` inicial, primeiro commit.

**Verificação:** `.venv/bin/python manage.py check` → `System check identified no issues`; `migrate` sem erros; `manage.py shell -c "from livros.models import Livro; print(Livro.objects.count())"` → `0`.

### Fase 1 — Núcleo: autenticação + CRUD de livros (desktop)
Objetivo: já dá para entrar e gerir livros pelo browser.

1. `livros/forms.py`: `LivroForm` (ModelForm, widgets com `type="date"`, estrelas 1-5, placeholder e `aria-label` nos campos) — rejeita avaliação fora de 1-5 e data futura.
2. `livros/views.py` + `urls.py`: lista (com `q`, `estado`, `avaliacao`, `order`, paginação 20), criar, detalhe, editar, apagar (POST). Queryset sempre filtrado por `request.user` — **teste obrigatório: o utilizador A não vê nem abre o livro do utilizador B (404, não 403)**.
3. Templates `livros/base.html` + as páginas, com shell próprio: topbar sticky (título, "Novo livro", utilizador, sair) e conteúdo centrado com largura máxima.
4. `static/css/estante.css` — sistema de desenho próprio, sem CDN: variáveis CSS (cores, espaçamento, raio, sombra), tipografia `system-ui`, cartões com sombra suave, badges de estado com cor (a ler = azul, lido = verde, abandonado = cinzento), estrelas como SVG inline, **estados de foco visíveis** em todos os campos, e `@media (prefers-color-scheme: dark)` para modo escuro automático. Formulários com etiquetas acima do campo e erros junto ao campo.
5. Testes: `test_views_auth.py` (anónimo → 302 para `/entrar/`; login inválido não autentica), `test_views_crud.py` (criar/editar/apagar, validação de avaliação, paginação, filtros), `test_models.py`.

**Verificação:** `.venv/bin/python manage.py test -v 2` → todos os testes passam; depois, no browser real a `localhost:8000`, entrar e ver a lista renderizada com o número de livros igual a `Livro.objects.count()`.

### Fase 2 — URLs e notas (1:N) no site desktop
Objetivo: as duas relações pedidas, geridas a partir da ficha do livro.

1. Forms `LinkLivroForm` / `NotaLivroForm`; vistas de criar/apagar (URL e nota pertencem sempre a um livro do utilizador autenticado — mesma regra de scoping da fase 1).
2. Na ficha do livro: secção "Links" (com domínio visível e `target="_blank" rel="noopener noreferrer"`) e secção "Notas" (mais recente primeiro), cada uma com o seu pequeno form de adicionar e um botão de apagar por linha.
3. `LivroForm` usa `inlineformset_factory` para permitir acrescentar 1-2 URLs/notas logo na criação (o resto na ficha).
4. Testes `test_relacoes.py`: criar livro com 2 URLs e 2 notas; apagar o livro remove os filhos (`cascade`); apagar um URL não toca nas notas; URLs de outro utilizador → 404.

**Verificação:** `manage.py test` verde + inspeção na BD: `manage.py shell -c` a contar `LinkLivro`/`NotaLivro` de um livro de teste == o que aparece no HTML (comparação programática, não a olho).

### Fase 3 — PWA mobile (`/pwa/`)
Objetivo: a interface que parece uma app no telemóvel, seguindo o padrão do DjangoClaw.

1. App `pwa` em `INSTALLED_APPS`, `path("pwa/", include("pwa.urls"))`.
2. Shell `pwa/templates/pwa/base.html`: **sem CDNs** (Bootstrap/Font Awesome por CDN quebram offline), ícones SVG inline, app bar `sticky` no topo e tab bar `fixed` no fundo (Livros / Novo / Estado), com `padding-bottom: calc(var(--tabbar-h) + env(safe-area-inset-bottom))` no conteúdo.
3. Vistas `manifest` e `sw.js` a devolver os content-types e headers corretos (`application/manifest+json`; `application/javascript` + `Service-Worker-Allowed: /pwa/` + `Cache-Control: no-cache`). `.webmanifest` em `static/` sai com content-type errado — por isso é view.
4. `sw.js`: estáticos cache-first com `PWA_CACHE_VERSION` (uma linha, a subir sempre que `pwa.css`/`pwa.js`/ícones mudarem — senão o browser serve CSS velho e parece que a alteração não pegou), **dados network-first** com fallback em cache e carimbo "Atualizado dd/mm/aaaa hh:mm:ss" para o Dinis saber que está a ver dados antigos.
5. Páginas mobile: lista em cartões com borda esquerda colorida por estado, detalhe com notas/URLs, form de edição com campos grandes. **Alvos de toque ≥44 px**, medidos com `getBoundingClientRect()` em viewport emulado 390x844 (não a olho). Título longo com `text-overflow: ellipsis` e truncagem verificada (`scrollWidth > clientWidth`). `@media (prefers-reduced-motion: reduce)` desativa animações.
6. Ícones: `pwa/static/pwa/scripts/generate_icons.py` (Pillow) gera 192/512 `any` e 192/512 **maskable** (fundo full-bleed, glifo dentro da zona segura ~80 % — reutilizar o ícone `any` como maskable corta o logo no launcher).
7. `scripts/smoke_test.py` (stdlib `urllib` + `http.cookiejar`) contra o `runserver` real: login com CSRF extraído do HTML, e validar nº de linhas == `Livro.objects.count()`, contadores, filtros, ordenação, detalhe, content-types do manifest e do sw, `Service-Worker-Allowed`, ausência de `{%`/`{{` no sw renderizado, e 302 (não 200) para anónimo em `/pwa/`.

**Verificação:** smoke test todo verde; no browser real (CDP) — `navigator.serviceWorker.getRegistration('/pwa/')` devolve scope/active/state, `caches.keys()` mostra só a versão nova, viewport Android emulado sem scroll horizontal (`document.documentElement.scrollWidth <= window.innerWidth`), e ecrã do `/pwa/` revisto a olho com screenshot.

### Fase 4 — Verificação final e entrega
1. Suite completa (`manage.py test`) + `manage.py check --deploy` sobre um settings de produção (avisa o que falta: `SECURE_HSTS_SECONDS`, `CSRF_COOKIE_SECURE`, `SESSION_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`).
2. Carga de 10-15 livros reais de exemplo para o Dinis ver a interface com dados (pergunto se ele prefere começar do zero).
3. `docs/VERIFICACAO.md` com a lista do que foi verificado por fase e o que ficou só "razoável" (trade-offs visuais reportados separadamente, não escondidos).
4. `README.md` final: como correr, como testar, como fazer backup (`cp db.sqlite3`), como criar conta.
5. Push para o GitHub privado via SSH com a conta `zeno-hermes` (runbook em `~/.hermes/skills/github/github-auth/references/zeno-hermes-github-access.md`).

### Fase 5 — Publicação com HTTPS (só quando o Dinis disser)
Objetivo: a PWA instalável no telemóvel e acessível de qualquer lado. Desenhada, não executada nesta ronda.
- **Opção A — Render** (como o DjangoClaw): push para `main` publica; `build-deploy.sh` com `collectstatic` (WhiteNoise serve os estáticos), `gunicorn estante.wsgi`, `DEBUG=false`, `SECRET_KEY` e `ALLOWED_HOSTS` em variáveis de ambiente. Menos trabalho, mais dependência de terceiros.
- **Opção B — VM Oracle** (a que já usamos no crypto-news-monitor): utilizador dedicado, `/opt/estante/{current,venv}`, systemd, Nginx + Certbot HTTPS, `/saude/` no healthcheck, script idempotente `deploy-estante`.
- Em qualquer das duas: `db.sqlite3` é a base de produção e **tem de ter backup** com a app a correr (o SQLite em disco de VM com snapshot não é backup).

---

## 6. Riscos e trade-offs

| Risco | Mitigação |
|---|---|
| Cache do service worker a servir CSS/JS antigo | `PWA_CACHE_VERSION` numa linha comentada, sempre a subir; smoke test confirma `caches.keys()` |
| Ícones maskable cortados no launcher | ícone maskable gerado à parte (não reutilizar o `any`) |
| Instalação no telemóvel falhar em `http://` | só localhost/HTTPS; a fase 5 é que traz HTTPS — digo-o em vez de prometer instalação na LAN |
| Unicidade (utilizador, título, autor, data) impedir releituras | **Resolvido**: a constraint inclui a data, logo releituras passam; o form mostra erro amigável no caso de duplicado exato |
| `db.sqlite3` em produção sem backup | documentado na fase 5; backup = cópia com a app parada ou `.backup` do SQLite |
| Site desktop "moderno" mas genérico | CSS próprio e contido; mostro ecrãs para revisão **antes** de commitar a fase |
| Django 6.1 recente | fixado em `requirements.txt`; 3.12 é suportado oficialmente (classifier do PyPI) |

## 7. Questões abertas (não bloqueiam o arranque)
1. **Nome**: proponho **Estante** (`/home/claw/projects/web/estante/`). Alternativas: `biblioteca`, `livros`, `leituras`. Digo-o uma vez e sigo com `estante` se não houver objeção.
2. **Releituras**: manter a unicidade título+autor (um registo por livro) ou permitir o mesmo livro várias vezes com datas diferentes?
3. **Dados existentes**: tens já uma lista (Goodreads, Excel, Notion) para importar? Se sim, faço uma fase extra só para o import — e nesse caso o ponto 2 tem de ser decidido antes.
4. **Ecrãs de referência**: queres que a estética desktop puxe pelo DjangoClaw (sidebar escura) ou mais limpa tipo "app de leitura" (fundo claro, cartões, tipografia grande)? Resolvo mostrando 2 variantes antes de fixar.

## 8. Ordem de execução e estimativa

| Fase | Entrega | Estimativa |
|---|---|---|
| 0 | Projeto a arrancar, modelo criado, migração aplicada | ~20 min |
| 1 | Entrar + CRUD de livros no browser (desktop) | ~1h30 |
| 2 | URLs e notas (1:N) na ficha do livro | ~40 min |
| 3 | PWA mobile instalável + smoke test | ~1h30 |
| 4 | Verificação completa, docs, push para GitHub | ~40 min |
| 5 | Publicação HTTPS (decisão do Dinis) | ~1-2h |

Entre a fase 1 e a 3 há **marcos visíveis**: ao fim da fase 1 o Dinis já usa a app no browser; ao fim da fase 3 já a tem no telemóvel (em `localhost` via túnel/HTTPS, ou já publicado se ele quiser saltar a ordem).
