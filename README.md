# Estante

Aplicação web pessoal para registar os livros que leio: título, autor, data de leitura,
avaliação (1-5), estado, URLs e notas associados (1:N). Inclui uma PWA instalável no
telemóvel que se comporta como uma app.

Duas superfícies, uma base de dados:

| Superfície | Onde | Para quê |
|---|---|---|
| Site desktop | `/livros/` | Lista com pesquisa e filtros, ficha do livro, URLs e notas |
| App mobile (PWA) | `/pwa/` | Uso no telemóvel: lista, ficha, criar/editar, offline |

## Stack

| Peça | Escolha | Porquê |
|---|---|---|
| Framework | Django 6.1.2 | Autenticação, sessões, CSRF, forms e validação de fábrica |
| Python | 3.12 (venv com `uv`) | Versão do sistema, mantida com patches de segurança |
| BD | SQLite (`db.sqlite3`) | Um utilizador, escrita rara; backup = copiar um ficheiro |
| Frontend | Templates Django + CSS próprio | Sem CDN (a PWA tem de funcionar offline) |
| Estáticos | WhiteNoise | Serve estáticos comprimidos sem Nginx nem serviço extra |
| Produção | Gunicorn + Nginx + systemd (VM Oracle + DuckDNS) | Ver `docs/PLANO.md`, fase 5 |

## Arranque em desenvolvimento

```bash
cd /home/claw/projects/web/estante
cp .env.example .env          # se ainda não existir; gerar SECRET_KEY nova
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```

Site em http://127.0.0.1:8000/ · app mobile em http://127.0.0.1:8000/pwa/ ·
healthcheck em http://127.0.0.1:8000/saude/

Gerar a chave secreta:

```bash
.venv/bin/python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

## Criar a conta

Não há registo público — as contas são criadas por script, com a password pedida de forma
oculta (nunca aparece no histórico do shell nem em ficheiros):

```bash
.venv/bin/python scripts/create_admin.py
```

O script é idempotente: se a conta já existir, atualiza a password.

## URLs e notas

Vivem na ficha do livro (no site e na app): `+ Adicionar URL`, `+ Adicionar nota`, e um
botão «Remover» por item. Apagar o livro apaga os filhos (cascata). Um URL inválido não
apaga o que foi escrito: a ficha volta com o erro e o texto no sítio.

## Formatos

- Datas: sempre `dd/mm/aaaa`, na lista, na ficha e no formulário (campo de texto com
  placeholder; o campo nativo do browser mostraría o formato do sistema do utilizador).
  A entrada aceita também ISO (`aaaa-mm-dd`) por compatibilidade.
- Avaliação: 1 a 5 estrelas, opcional.
- Estados: a ler, lido, abandonado.

## Testes e verificação

```bash
.venv/bin/python manage.py test                       # 120 testes
.venv/bin/python manage.py test livros -v 2           # só o domínio
.venv/bin/python scripts/smoke_test.py http://127.0.0.1:8000   # HTTP real (servidor a correr)
.venv/bin/python manage.py check --deploy             # com DEBUG=false
```

O `smoke_test.py` usa só a biblioteca padrão, cria uma conta descartável, autentica com
cookie e CSRF verdadeiros e compara o que as páginas mostram com o que está na base de
dados. Evidência do que já foi verificado, por fase: `docs/VERIFICACAO.md`.

## Backup

Os dados são um único ficheiro: `db.sqlite3`.

```bash
mkdir -p backups
sqlite3 db.sqlite3 ".backup 'backups/estante-$(date +%Y%m%d-%H%M).sqlite3'"
```

O `.backup` do SQLite é consistente mesmo com a app a correr (não é uma cópia crua do
ficheiro). **Restauro testado**: o backup foi aberto, comparado tabela a tabela com a base
de dados viva (contagens iguais) e validado com `PRAGMA integrity_check` → `ok`.

Em produção o backup é feito por script próprio (runbook privado da VM), nunca por
snapshot da VM — o snapshot não garante a consistência do ficheiro.

## Estrutura

```
estante/             configuração do projeto (settings, urls, wsgi, healthcheck)
livros/              domínio: modelos, forms, views, admin e testes (site desktop)
pwa/                 app mobile instalável: views, templates, sw.js, manifest, ícones
scripts/             create_admin.py, dados_exemplo.py, smoke_test.py
static/css/          sistema de desenho do site desktop
static/img/          favicon do site
docs/PLANO.md        plano de implementação por fases
docs/VERIFICACAO.md  o que foi verificado, como, e o que ficou por verificar
```

## PWA: o que é preciso saber antes de mexer

- `PWA_CACHE_VERSION` (em `pwa/views.py`, uma linha) **tem de subir sempre que `pwa.css`,
  `pwa.js` ou os ícones mudarem**. O service worker serve os estáticos a partir da cache;
  sem isto o telemóvel continua a mostrar o antigo e parece que a alteração não pegou.
- Ícones: `pwa/scripts/generate_icons.py` (Pillow) gera os `any` e os `maskable`.
- A instalação real no telemóvel exige HTTPS (ou `localhost`): em `http://` de rede local o
  browser não regista o service worker nem oferece instalação.
- Estáticos são cache-first; páginas de `/pwa/` são network-first com aviso visível quando
  vêm da cache; `/pwa/entrar/` e respostas redirecionadas nunca entram na cache.

## Produção

**Está em produção: https://estante.duckdns.org/** (VM Oracle Cloud com Nginx + Let's Encrypt,
Gunicorn atrás do proxy, SQLite em disco local da VM).

Variáveis em `/etc/estante/estante.env` (nunca no repositório; valores entre plicas — a chave
do Django tem caracteres que partem o ficheiro sem aspas):

```
DEBUG='false'
SECRET_KEY='<gerada na VM>'
ALLOWED_HOSTS='estante.duckdns.org'
CSRF_TRUSTED_ORIGINS='https://estante.duckdns.org'
DB_PATH='/var/lib/estante/db.sqlite3'
STATIC_ROOT_DIR='/var/lib/estante/staticfiles'
EMAIL_HOST=''          # só se quiseres usar o "recuperar password" do /admin/
```

A base de dados e os estáticos ficam **fora do checkout** (`DB_PATH`, `STATIC_ROOT_DIR`): o
`git reset --hard` do deploy mexe no código, não nos dados.

Publicar uma alteração (na VM):

```bash
sudo deploy-estante        # git fetch + reset, dependências, migrate, collectstatic, restart
                           # e healthcheck que verifica o corpo de /saude/
```

Backup diário automático do SQLite (guarda as 14 cópias mais recentes):

```bash
sudo systemctl start estante-backup.service     # forçar um backup agora
sudo ls -lt /var/backups/estante/ | head
```

Restauro: parar o serviço, repor `db.sqlite3` a partir da cópia, corrigir o dono, arrancar e
confirmar `/saude/`.

Verificado em produção (detalhe em `docs/VERIFICACAO.md`): `check --deploy` sem problemas,
HTTP → HTTPS (301), cabeçalhos HSTS/nosniff/X-Frame-Options, estáticos com hash e gzip
(19 KB → 4,5 KB), PWA instalável (`installabilityErrors` vazio), offline a funcionar com o
serviço parado e restauro de backup conferido contra a base viva.

Os detalhes operacionais (endereços, chaves, caminhos, firewall, certificados e o conteúdo
dos serviços systemd/Nginx) vivem num runbook privado, fora deste repositório. **Atenção ao
`iptables` da Oracle Cloud**: um `REJECT` inicial pode bloquear 80/443 antes do UFW.

## Estado do desenvolvimento

| Fase | Estado |
|---|---|
| 0 — Fundação (projeto, modelos, migrações, healthcheck) | concluída |
| 1 — Autenticação e CRUD de livros (desktop) | concluída |
| 2 — URLs e notas (1:N) na ficha do livro | concluída |
| 3 — PWA mobile (`/pwa/`) | concluída |
| 4 — Verificação final e documentação | concluída |
| 5 — Publicação HTTPS (VM Oracle + DuckDNS) | concluída e em produção |

### Criar dados de exemplo (opcional)

```bash
.venv/bin/python scripts/dados_exemplo.py --limpar   # conta descartável 'revisao'
```

## Repositório

Público em `https://github.com/zeno-hermes/estante` (remoto SSH local: `git@github-zeno:zeno-hermes/estante.git`).
Sem segredos: `.env`, bases de dados e runbooks de infraestrutura ficam fora.
