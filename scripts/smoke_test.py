"""Verificação HTTP real da PWA, contra um servidor a correr.

    .venv/bin/python manage.py runserver 127.0.0.1:8000
    .venv/bin/python scripts/smoke_test.py http://127.0.0.1:8000

Usa apenas a biblioteca padrão (urllib + http.cookiejar), como um browser:
cria um utilizador descartável, extrai o CSRF do HTML do login, autentica com
cookie real, percorre o fluxo e compara o que a página mostra com o que está na
base de dados. O utilizador temporário é apagado no fim.
"""

import json
import os
import re
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "estante.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

from livros.models import LinkLivro, Livro, NotaLivro  # noqa: E402
from pwa.views import PWA_CACHE_VERSION  # noqa: E402

VERDE = "\033[92m"
VERMELHO = "\033[91m"
FIM = "\033[0m"

falhas = []
verificacoes = 0


def verificar(descricao, condicao, detalhe=""):
    global verificacoes
    verificacoes += 1
    if condicao:
        print(f"  {VERDE}ok{FIM}   {descricao}")
    else:
        print(f"  {VERMELHO}FALHA{FIM} {descricao} {detalhe}")
        falhas.append(descricao)


class Sessao:
    """Cliente HTTP com cookies e tratamento de CSRF, mínimo mas real."""

    def __init__(self, base):
        self.base = base.rstrip("/")
        self.jar = CookieJar()
        self.abridor = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar),
            SemRedirecionar(),
        )

    def _pedido(self, caminho, dados=None, metodo=None):
        url = f"{self.base}{caminho}"
        corpo = urllib.parse.urlencode(dados).encode() if dados else None
        pedido = urllib.request.Request(url, data=corpo, method=metodo)
        if corpo:
            pedido.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with self.abridor.open(pedido) as resposta:
                return resposta.status, dict(resposta.headers), resposta.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as erro:
            return erro.code, dict(erro.headers), erro.read().decode("utf-8", "replace")

    def get(self, caminho):
        return self._pedido(caminho)

    def post(self, caminho, dados):
        return self._pedido(caminho, dados)

    def csrf(self, caminho):
        _, _, html = self.get(caminho)
        encontrado = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
        return encontrado.group(1) if encontrado else ""


class SemRedirecionar(urllib.request.HTTPRedirectHandler):
    """Não segue redirecionamentos: quero verificá-los, não atravessá-los."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    utilizador_nome = f"smoke_{secrets.token_hex(4)}"
    password = secrets.token_urlsafe(24)
    Utilizador = get_user_model()
    Utilizador.objects.filter(username=utilizador_nome).delete()

    print(f"\n== Fase 3 — PWA em {base} (conta {utilizador_nome}) ==\n")

    try:
        utilizador = Utilizador.objects.create_user(username=utilizador_nome, password=password)
        livro = Livro.objects.create(
            utilizador=utilizador,
            titulo="Livro de fumo",
            autor="Autor de fumo",
            data_leitura=None,
            estado=Livro.Estado.A_LER,
        )
        sessao = Sessao(base)

        print("Público e sem sessão:")
        estado, _, _ = sessao.get("/pwa/")
        verificar("GET /pwa/ sem sessão devolve 302 (não serve dados)", estado == 302, f"(obtido {estado})")
        estado, _, html = sessao.get("/pwa/entrar/")
        verificar("GET /pwa/entrar/ devolve 200", estado == 200, f"(obtido {estado})")
        verificar("a página de entrada é a do shell mobile", "Estante" in html and "pwa.js" in html)
        verificar("a página de entrada não expõe o site desktop", "/livros/" not in html)

        estado, cabecalhos, corpo = sessao.get("/pwa/manifest.webmanifest")
        verificar("manifest devolve 200", estado == 200, f"(obtido {estado})")
        verificar(
            "manifest com content-type application/manifest+json",
            cabecalhos.get("Content-Type", "").startswith("application/manifest+json"),
            f"(obtido {cabecalhos.get('Content-Type')})",
        )
        try:
            manifest = json.loads(corpo)
            valido = True
        except json.JSONDecodeError:
            manifest, valido = {}, False
        verificar("manifest é JSON válido", valido)
        verificar("manifest: start_url no prefixo /pwa/", manifest.get("start_url") == "/pwa/", f"({manifest.get('start_url')})")
        verificar("manifest: scope /pwa/", manifest.get("scope") == "/pwa/", f"({manifest.get('scope')})")
        verificar("manifest: display standalone", manifest.get("display") == "standalone")
        icones = manifest.get("icons", [])
        verificar("manifest: 4 ícones declarados", len(icones) == 4, f"({len(icones)})")
        verificar(
            "manifest: há ícones maskable",
            any(i.get("purpose") == "maskable" for i in icones),
        )
        for icone in icones:
            estado_icone, _, _ = sessao.get(icone["src"])
            verificar(f"ícone {icone['src']} acessível", estado_icone == 200, f"(obtido {estado_icone})")

        estado, cabecalhos, corpo = sessao.get("/pwa/sw.js")
        verificar("sw.js devolve 200", estado == 200, f"(obtido {estado})")
        verificar(
            "sw.js com content-type de JavaScript",
            "javascript" in cabecalhos.get("Content-Type", ""),
            f"(obtido {cabecalhos.get('Content-Type')})",
        )
        verificar(
            "sw.js com Service-Worker-Allowed: /pwa/",
            cabecalhos.get("Service-Worker-Allowed") == "/pwa/",
            f"(obtido {cabecalhos.get('Service-Worker-Allowed')})",
        )
        verificar("sw.js sem cache", cabecalhos.get("Cache-Control") == "no-cache")
        verificar("sw.js sem restos de template ({% ou {{)", "{%" not in corpo and "{{" not in corpo)
        verificar("sw.js tem a versão da cache atual", PWA_CACHE_VERSION in corpo, f"({PWA_CACHE_VERSION})")

        estado, _, _ = sessao.get("/pwa/offline/")
        verificar("página offline acessível sem sessão", estado == 200, f"(obtido {estado})")

        print("\nSessão e dados:")
        token = sessao.csrf("/pwa/entrar/")
        verificar("token CSRF extraído do HTML do login", bool(token))
        estado, cabecalhos, _ = sessao.post(
            "/pwa/entrar/", {"csrfmiddlewaretoken": token, "username": utilizador_nome, "password": password}
        )
        verificar("login aceita as credenciais", estado == 302, f"(obtido {estado})")
        verificar(
            "login encaminha para a lista mobile",
            cabecalhos.get("Location", "").endswith("/pwa/"),
            f"({cabecalhos.get('Location')})",
        )

        estado, _, html = sessao.get("/pwa/")
        verificar("GET /pwa/ devolve 200 com sessão", estado == 200, f"(obtido {estado})")
        cartoes = html.count('class="cartao livro')
        na_bd = Livro.objects.filter(utilizador=utilizador).count()
        verificar(f"cartões no HTML == livros na BD ({cartoes} / {na_bd})", cartoes == na_bd)
        verificar("mostra o livro criado", "Livro de fumo" in html)
        verificar("tem carimbo de atualização", "atualizado" in html)
        verificar("tem barra de navegação inferior", 'class="tabbar"' in html)
        verificar("não há scroll horizontal declarado por CSS fixo", "overflow-x: scroll" not in html)
        verificar("lista não expõe o site desktop", "Os meus livros" not in html)

        estado, _, html = sessao.get("/pwa/?q=fumo")
        verificar("pesquisa devolve resultados", "Livro de fumo" in html, "")
        estado, _, html = sessao.get("/pwa/?q=inexistente")
        verificar("pesquisa sem resultados não mostra o livro", "Livro de fumo" not in html)
        estado, _, html = sessao.get("/pwa/?estado=lido")
        verificar("filtro por estado filtra", "Livro de fumo" not in html)
        estado, _, html = sessao.get("/pwa/?estado=a_ler")
        verificar("filtro pelo estado correto mostra o livro", "Livro de fumo" in html)

        estado, _, html = sessao.get(f"/pwa/livro/{livro.pk}/")
        verificar("ficha do livro devolve 200", estado == 200, f"(obtido {estado})")
        verificar("ficha mostra o título", "Livro de fumo" in html)
        verificar(
            "ficha tem os dois formulários de acrescentar",
            "+ Adicionar URL" in html and "+ Adicionar nota" in html,
        )

        print("\nEscrita pela interface (POST com CSRF real):")
        token = sessao.csrf("/pwa/novo/")
        estado, cabecalhos, _ = sessao.post(
            "/pwa/novo/",
            {
                "csrfmiddlewaretoken": token,
                "titulo": "Escrito pelo smoke",
                "autor": "Autor de fumo",
                "data_leitura": "01/09/2026",
                "avaliacao": "4",
                "estado": "lido",
            },
        )
        verificar("criar livro devolve 302", estado == 302, f"(obtido {estado})")
        criado = Livro.objects.filter(utilizador=utilizador, titulo="Escrito pelo smoke").first()
        verificar("livro criado na BD", criado is not None)
        if criado:
            verificar("data gravada como 01/09/2026", str(criado.data_leitura) == "2026-09-01", f"({criado.data_leitura})")
            verificar("avaliação gravada", criado.avaliacao == 4, f"({criado.avaliacao})")

            token = sessao.csrf(f"/pwa/livro/{criado.pk}/")
            estado, _, _ = sessao.post(
                f"/pwa/livro/{criado.pk}/urls/novo/",
                {"csrfmiddlewaretoken": token, "url": "https://exemplo.pt/fumo", "descricao": "Fumo"},
            )
            verificar("adicionar URL devolve 302", estado == 302, f"(obtido {estado})")
            verificar("URL gravado na BD", LinkLivro.objects.filter(livro=criado).count() == 1)

            token = sessao.csrf(f"/pwa/livro/{criado.pk}/")
            estado, _, _ = sessao.post(
                f"/pwa/livro/{criado.pk}/notas/nova/",
                {"csrfmiddlewaretoken": token, "texto": "Nota do smoke test."},
            )
            verificar("adicionar nota devolve 302", estado == 302, f"(obtido {estado})")
            verificar("nota gravada na BD", NotaLivro.objects.filter(livro=criado).count() == 1)

            link = LinkLivro.objects.get(livro=criado)
            token = sessao.csrf(f"/pwa/livro/{criado.pk}/")
            estado, _, _ = sessao.post(f"/pwa/urls/{link.pk}/apagar/", {"csrfmiddlewaretoken": token})
            verificar("apagar URL devolve 302", estado == 302, f"(obtido {estado})")
            verificar("URL removido da BD", not LinkLivro.objects.filter(pk=link.pk).exists())
            verificar("notas intactas depois de apagar o URL", NotaLivro.objects.filter(livro=criado).count() == 1)

            token = sessao.csrf(f"/pwa/livro/{criado.pk}/")
            estado, _, _ = sessao.post(f"/pwa/livro/{criado.pk}/apagar/", {"csrfmiddlewaretoken": token})
            verificar("apagar livro devolve 302", estado == 302, f"(obtido {estado})")
            verificar("livro removido da BD", not Livro.objects.filter(pk=criado.pk).exists())
            verificar("nota removida em cascata", not NotaLivro.objects.filter(livro=criado).exists())

        print("\nSegurança:")
        estado, _, _ = sessao.post("/pwa/livro/%d/urls/novo/" % livro.pk, {"url": "https://x.pt"})
        verificar("POST sem CSRF é recusado (403)", estado == 403, f"(obtido {estado})")
        estado, _, _ = sessao.get(f"/pwa/livro/{livro.pk}/urls/novo/")
        verificar("GET num endpoint de escrita devolve 405", estado == 405, f"(obtido {estado})")

        outro = Utilizador.objects.create_user(username=f"outro_{utilizador_nome}", password=password)
        alheio = Livro.objects.create(utilizador=outro, titulo="De outra pessoa", autor="X")
        estado, _, _ = sessao.get(f"/pwa/livro/{alheio.pk}/")
        verificar("livro de outro utilizador devolve 404", estado == 404, f"(obtido {estado})")
        estado, _, _ = sessao.get(f"/pwa/livro/{alheio.pk}/editar/")
        verificar("editar livro alheio devolve 404", estado == 404, f"(obtido {estado})")
        Utilizador.objects.filter(username=outro.username).delete()

        token = sessao.csrf("/pwa/")
        estado, cabecalhos, _ = sessao.post("/pwa/sair/", {"csrfmiddlewaretoken": token})
        verificar("sair devolve 302", estado == 302, f"(obtido {estado})")
        verificar("sair encaminha para a entrada mobile", "/pwa/entrar/" in cabecalhos.get("Location", ""))
        estado, _, _ = sessao.get("/pwa/")
        verificar("depois de sair, /pwa/ volta a exigir sessão", estado == 302, f"(obtido {estado})")

    finally:
        Utilizador.objects.filter(username__startswith=utilizador_nome).delete()
        Utilizador.objects.filter(username__startswith="outro_smoke_").delete()
        print("\n(conta temporária removida)")

    print(f"\n{verificacoes - len(falhas)}/{verificacoes} verificações passaram.")
    if falhas:
        print(f"{VERMELHO}falhas:{FIM}")
        for descricao in falhas:
            print(f"  - {descricao}")
        return 1
    print(f"{VERDE}smoke test: tudo ok{FIM}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
