# Estante

Aplicação web pessoal para registar os livros que leio: título, autor, data de leitura,
avaliação (1-5), estado, URLs e notas associados (1:N). Inclui uma PWA instalável no
telemóvel que se comporta como uma app.

## Stack

| Peça | Escolha | Porquê |
|---|---|---|
| Framework | Django 6.1.2 | Autenticação, sessões, CSRF, forms e validação de fábrica |
| Python | 3.12 (venv com `uv`) | Versão do sistema, mantida com patches de segurança |
| BD | SQLite (`db.sqlite3`) | Um utilizador, escrita rara; backup = copiar um ficheiro |
| Frontend | Templates Django + CSS próprio | Sem CDN (a PWA tem de funcionar offline) |
| Estáticos | WhiteNoise | Serve estáticos sem Nginx nem serviço extra |
| Produção | Gunicorn + Nginx + systemd (VM Oracle) | Ver `docs/PLANO.md`, fase 5 |

## Arranque em desenvolvimento

```bash
cd /home/claw/projects/web/estante
cp .env.example .env          # se ainda não existir; gerar SECRET_KEY nova
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```

Site em http://127.0.0.1:8000/ · healthcheck em http://127.0.0.1:8000/saude/

## Criar a conta

O registo público está desligado (`PERMITIR_REGISTO=false` em `.env`). A conta é criada
por script, com a password pedida de forma oculta (nunca aparece no histórico do shell
nem em ficheiros):

```bash
.venv/bin/python scripts/create_admin.py
```

O script é idempotente: se a conta já existir, atualiza a password.

## Testes

```bash
.venv/bin/python manage.py test            # suite completa
.venv/bin/python manage.py test livros -v 2 # só os testes do domínio
```

## Backup

Os dados são um único ficheiro: `db.sqlite3`.

```bash
# cópia consistente com a app a correr
sqlite3 db.sqlite3 ".backup 'backups/estante-$(date +%Y%m%d-%H%M).sqlite3'"
```

Em produção o backup é feito por script próprio (ver runbook privado da VM), nunca por
snapshot da VM — o snapshot não garante a consistência do ficheiro.

## Estrutura

```
estante/         configuração do projeto (settings, urls, wsgi, healthcheck)
livros/          domínio: modelos, forms, views, admin e testes (site desktop)
pwa/             aplicação mobile instalável, servida em /pwa/
scripts/         create_admin.py (contas) e smoke_test.py (verificação HTTP real)
static/css/      sistema de desenho do site desktop
docs/PLANO.md    plano de implementação por fases
```

## Estado do desenvolvimento

| Fase | Estado |
|---|---|
| 0 — Fundação (projeto, modelos, migrações, healthcheck) | concluída |
| 1 — Autenticação e CRUD de livros (desktop) | pendente |
| 2 — URLs e notas (1:N) na ficha do livro | pendente |
| 3 — PWA mobile (`/pwa/`) | pendente |
| 4 — Verificação final, documentação e GitHub | pendente |
| 5 — Publicação HTTPS (VM Oracle + DuckDNS) | não iniciada (decisão do Dinis) |
