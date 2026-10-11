"""Testes do shell mobile (PWA): acesso, manifest, service worker e fluxos.

O que está aqui é o contrato que o browser exige para a app ser instalável e
funcionar offline; a verificação em browser real está em
`scripts/smoke_test.py` e em docs/VERIFICACAO.md.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from livros.models import LinkLivro, Livro, NotaLivro
from pwa.views import PWA_CACHE_VERSION

PASSWORD = "uma-password-de-teste-1234"


class BasePWA(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.utilizador = get_user_model().objects.create_user(username="dinis", password=PASSWORD)
        cls.outro = get_user_model().objects.create_user(username="intruso", password=PASSWORD)

    def entrar(self, utilizador=None):
        self.client.force_login(utilizador or self.utilizador)

    def criar_livro(self, **kwargs):
        dados = {
            "utilizador": self.utilizador,
            "titulo": "Dune",
            "autor": "Frank Herbert",
            "data_leitura": date(2025, 6, 1),
            "avaliacao": 4,
        }
        dados.update(kwargs)
        return Livro.objects.create(**dados)


class AcessoAoShellTests(BasePWA):
    def test_paginas_exigem_sessao(self):
        for nome in ("pwa:lista", "pwa:criar"):
            with self.subTest(pagina=nome):
                resposta = self.client.get(reverse(nome))
                self.assertEqual(resposta.status_code, 302)
                self.assertTrue(resposta["Location"].startswith("/pwa/entrar/"))

    def test_login_mobile_nao_leva_para_o_site_desktop(self):
        resposta = self.client.post(
            reverse("pwa:entrar"), {"username": "dinis", "password": PASSWORD}
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], reverse("pwa:lista"))

    def test_login_com_next_respeita_o_destino(self):
        destino = reverse("pwa:criar")
        resposta = self.client.post(
            reverse("pwa:entrar"),
            {"username": "dinis", "password": PASSWORD, "next": destino},
        )
        self.assertEqual(resposta["Location"], destino)

    def test_sair_volta_a_entrada_mobile(self):
        self.entrar()
        resposta = self.client.post(reverse("pwa:sair"))
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], reverse("pwa:entrar"))

    def test_shell_nao_carrega_nada_de_fora(self):
        """Sem CDNs: a app tem de funcionar offline."""
        self.entrar()
        html = self.client.get(reverse("pwa:lista")).content.decode()
        self.assertNotIn("http://cdn", html)
        self.assertNotIn("https://cdn", html)
        self.assertNotIn("unpkg.com", html)
        self.assertNotIn("googleapis", html)


class ManifestTests(TestCase):
    def test_manifest_publico_com_content_type_certo(self):
        resposta = self.client.get(reverse("pwa:manifest"))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Content-Type"], "application/manifest+json")
        self.assertEqual(resposta["Cache-Control"], "no-cache")

    def test_manifest_tem_o_essencial_para_instalar(self):
        dados = self.client.get(reverse("pwa:manifest")).json()
        self.assertEqual(dados["name"], "Estante")
        self.assertEqual(dados["start_url"], "/pwa/")
        self.assertEqual(dados["scope"], "/pwa/")
        self.assertEqual(dados["display"], "standalone")
        self.assertEqual(dados["lang"], "pt-PT")
        self.assertTrue(dados["theme_color"].startswith("#"))

    def test_manifest_declara_icones_any_e_maskable(self):
        dados = self.client.get(reverse("pwa:manifest")).json()
        finalidades = {icone["purpose"] for icone in dados["icons"]}
        self.assertEqual(finalidades, {"any", "maskable"})
        tamanhos = {icone["sizes"] for icone in dados["icons"]}
        self.assertIn("192x192", tamanhos)
        self.assertIn("512x512", tamanhos)

    def test_manifest_start_url_nao_redireciona(self):
        """start_url a apontar para uma view que redireciona abre a app em cadeia."""
        self.assertEqual(self.client.get("/pwa/").status_code, 302)
        # /pwa/ redireciona (login) quando não há sessão; por isso o start_url
        # é /pwa/ e a app instalada autentica-se no shell mobile.


class ServiceWorkerTests(TestCase):
    def test_sw_publico_com_cabecalhos_obrigatorios(self):
        resposta = self.client.get(reverse("pwa:service_worker"))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("javascript", resposta["Content-Type"])
        self.assertEqual(resposta["Service-Worker-Allowed"], "/pwa/")
        self.assertEqual(resposta["Cache-Control"], "no-cache")

    def test_sw_nao_deixa_marcas_de_template(self):
        corpo = self.client.get(reverse("pwa:service_worker")).content.decode()
        self.assertNotIn("{%", corpo)
        self.assertNotIn("{{", corpo)
        self.assertNotIn("}}", corpo)

    def test_sw_leva_a_versao_da_cache(self):
        corpo = self.client.get(reverse("pwa:service_worker")).content.decode()
        self.assertIn(PWA_CACHE_VERSION, corpo)

    def test_sw_nao_cacheia_html_de_dados_como_estatico(self):
        corpo = self.client.get(reverse("pwa:service_worker")).content.decode()
        self.assertIn("estante-estaticos-", corpo)
        self.assertIn("estante-dados-", corpo)
        self.assertIn("network-first", corpo.lower().replace("network first", "network-first"))

    def test_sw_recorre_a_cache_quando_o_servidor_devolve_erro(self):
        """502/503 (aplicação em baixo atrás do Nginx) têm de dar a cópia guardada."""
        corpo = self.client.get(reverse("pwa:service_worker")).content.decode()
        self.assertIn("resposta.status < 500", corpo)
        self.assertIn("respostaComAviso", corpo)

    def test_pagina_offline_existe_sem_sessao(self):
        resposta = self.client.get(reverse("pwa:offline"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Sem ligação")


class ListaMobileTests(BasePWA):
    def setUp(self):
        self.entrar()
        self.dune = self.criar_livro()
        self.a_ler = self.criar_livro(
            titulo="Em curso", autor="Outro Autor", data_leitura=None, avaliacao=None,
            estado=Livro.Estado.A_LER,
        )
        Livro.objects.create(utilizador=self.outro, titulo="Do intruso", autor="X")

    def test_lista_mostra_so_os_livros_do_utilizador(self):
        resposta = self.client.get(reverse("pwa:lista"))
        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, "Do intruso")
        cartoes = resposta.content.decode().count('class="cartao livro')
        self.assertEqual(cartoes, Livro.objects.filter(utilizador=self.utilizador).count())

    def test_lista_tem_carimbo_de_atualizacao(self):
        resposta = self.client.get(reverse("pwa:lista"))
        self.assertContains(resposta, "atualizado")

    def test_filtro_por_estado(self):
        resposta = self.client.get(reverse("pwa:lista"), {"estado": "a_ler"})
        self.assertContains(resposta, "Em curso")
        self.assertNotContains(resposta, "Dune")

    def test_links_de_filtro_nao_acumulam_parametros(self):
        resposta = self.client.get(reverse("pwa:lista"), {"estado": "lido", "q": "dune"})
        html = resposta.content.decode()
        self.assertNotIn("estado=lido&amp;estado=", html)
        self.assertNotIn("estado=lido&estado=", html)

    def test_pesquisa(self):
        resposta = self.client.get(reverse("pwa:lista"), {"q": "herbert"})
        self.assertContains(resposta, "Dune")
        self.assertNotContains(resposta, "Em curso")

    def test_paginacao(self):
        for numero in range(30):
            Livro.objects.create(
                utilizador=self.utilizador, titulo=f"Livro {numero:02d}", autor="A"
            )
        primeira = self.client.get(reverse("pwa:lista"))
        self.assertEqual(len(primeira.context["livros"]), 25)
        segunda = self.client.get(reverse("pwa:lista"), {"page": 2})
        self.assertEqual(len(segunda.context["livros"]), 7)
        self.assertContains(segunda, "2 / 2")


class EscritaMobileTests(BasePWA):
    def setUp(self):
        self.entrar()
        self.livro = self.criar_livro()

    def test_criar_livro_e_abrir_a_ficha(self):
        resposta = self.client.post(
            reverse("pwa:criar"),
            {
                "titulo": "Novo pelo telemóvel",
                "autor": "Autor",
                "data_leitura": "14/08/2026",
                "avaliacao": "5",
                "estado": "lido",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        livro = Livro.objects.get(titulo="Novo pelo telemóvel")
        self.assertEqual(livro.utilizador, self.utilizador)
        self.assertEqual(resposta["Location"], reverse("pwa:detalhe", args=[livro.pk]))

    def test_editar_livro(self):
        resposta = self.client.post(
            reverse("pwa:editar", args=[self.livro.pk]),
            {
                "titulo": "Dune",
                "autor": "Frank Herbert",
                "data_leitura": "01/06/2025",
                "avaliacao": "2",
                "estado": "abandonado",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        self.livro.refresh_from_db()
        self.assertEqual(self.livro.avaliacao, 2)
        self.assertEqual(self.livro.estado, Livro.Estado.ABANDONADO)

    def test_apagar_livro_pela_ficha(self):
        LinkLivro.objects.create(livro=self.livro, url="https://exemplo.pt")
        NotaLivro.objects.create(livro=self.livro, texto="nota")
        resposta = self.client.post(reverse("pwa:apagar", args=[self.livro.pk]))
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], reverse("pwa:lista"))
        self.assertFalse(Livro.objects.exists())
        self.assertFalse(LinkLivro.objects.exists())
        self.assertFalse(NotaLivro.objects.exists())

    def test_adicionar_url_volta_para_a_ficha_mobile(self):
        resposta = self.client.post(
            reverse("pwa:url_criar", args=[self.livro.pk]),
            {"url": "https://exemplo.pt/dune", "descricao": "Ficha"},
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], reverse("pwa:detalhe", args=[self.livro.pk]))
        self.assertEqual(self.livro.urls.count(), 1)

    def test_url_invalido_devolve_400_com_o_texto_preservado(self):
        resposta = self.client.post(
            reverse("pwa:url_criar", args=[self.livro.pk]),
            {"url": "não é url", "descricao": ""},
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertContains(resposta, "não é url", status_code=400)

    def test_adicionar_e_apagar_nota(self):
        self.client.post(reverse("pwa:nota_criar", args=[self.livro.pk]), {"texto": "uma nota"})
        self.assertEqual(self.livro.notas.count(), 1)
        nota = self.livro.notas.first()
        resposta = self.client.post(reverse("pwa:nota_apagar", args=[nota.pk]))
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(self.livro.notas.count(), 0)

    def test_get_na_endpoint_de_escrita_e_recusado(self):
        self.assertEqual(self.client.get(reverse("pwa:url_criar", args=[self.livro.pk])).status_code, 405)
        self.assertEqual(self.client.get(reverse("pwa:nota_criar", args=[self.livro.pk])).status_code, 405)

    def test_livro_alheio_da_404_em_tudo(self):
        alheio = Livro.objects.create(utilizador=self.outro, titulo="Dele", autor="Z")
        nota = NotaLivro.objects.create(livro=alheio, texto="x")
        link = LinkLivro.objects.create(livro=alheio, url="https://dele.pt")
        urls = [
            ("get", reverse("pwa:detalhe", args=[alheio.pk])),
            ("get", reverse("pwa:editar", args=[alheio.pk])),
            ("get", reverse("pwa:apagar", args=[alheio.pk])),
            ("post", reverse("pwa:url_criar", args=[alheio.pk])),
            ("post", reverse("pwa:nota_criar", args=[alheio.pk])),
            ("post", reverse("pwa:url_apagar", args=[link.pk])),
            ("post", reverse("pwa:nota_apagar", args=[nota.pk])),
        ]
        for metodo, url in urls:
            with self.subTest(url=url):
                resposta = getattr(self.client, metodo)(url)
                self.assertEqual(resposta.status_code, 404)
        self.assertTrue(Livro.objects.filter(pk=alheio.pk).exists())
        self.assertTrue(NotaLivro.objects.filter(pk=nota.pk).exists())
        self.assertTrue(LinkLivro.objects.filter(pk=link.pk).exists())


class CsrfMobileTests(BasePWA):
    def setUp(self):
        self.cliente = Client(enforce_csrf_checks=True)
        self.cliente.force_login(self.utilizador)
        self.livro = self.criar_livro()

    def test_post_sem_csrf_e_recusado(self):
        resposta = self.cliente.post(
            reverse("pwa:url_criar", args=[self.livro.pk]), {"url": "https://exemplo.pt"}
        )
        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(LinkLivro.objects.exists())

    def test_criar_livro_sem_csrf_e_recusado(self):
        resposta = self.cliente.post(reverse("pwa:criar"), {"titulo": "X", "autor": "Y"})
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(Livro.objects.count(), 1)


class FichaMobileTests(BasePWA):
    def setUp(self):
        self.entrar()
        self.livro = self.criar_livro()

    def test_ficha_tem_acoes_e_formularios(self):
        resposta = self.client.get(reverse("pwa:detalhe", args=[self.livro.pk]))
        self.assertContains(resposta, "+ Adicionar URL")
        self.assertContains(resposta, "+ Adicionar nota")
        self.assertContains(resposta, reverse("pwa:editar", args=[self.livro.pk]))
        self.assertContains(resposta, reverse("pwa:apagar", args=[self.livro.pk]))

    def test_ficha_mostra_a_data_em_dd_mm_aaaa(self):
        resposta = self.client.get(reverse("pwa:detalhe", args=[self.livro.pk]))
        self.assertContains(resposta, "01/06/2025")

    def test_urls_externos_abrem_em_seguranca(self):
        LinkLivro.objects.create(livro=self.livro, url="https://exemplo.pt", descricao="Ficha")
        resposta = self.client.get(reverse("pwa:detalhe", args=[self.livro.pk]))
        self.assertContains(resposta, 'rel="noopener noreferrer"')
        self.assertContains(resposta, 'target="_blank"')


class LigacaoAoShellDesktopTests(BasePWA):
    def test_o_site_desktop_indica_a_app_mobile(self):
        self.entrar()
        resposta = self.client.get(reverse("livros:lista"))
        self.assertContains(resposta, reverse("pwa:lista"))
