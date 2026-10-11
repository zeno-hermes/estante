"""Testes da fase 2: URLs e notas (relações 1:N) geridas a partir da ficha.

Cobre o caminho feliz, a validação, o isolamento entre utilizadores, a
exigência de POST e a proteção CSRF.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from livros.models import LinkLivro, Livro, NotaLivro

PASSWORD = "uma-password-de-teste-1234"


class BaseRelacoes(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.utilizador = get_user_model().objects.create_user(username="dinis", password=PASSWORD)
        cls.outro = get_user_model().objects.create_user(username="intruso", password=PASSWORD)

    def setUp(self):
        self.entrar()
        self.livro = Livro.objects.create(
            utilizador=self.utilizador,
            titulo="Dune",
            autor="Frank Herbert",
            data_leitura=date(2025, 6, 1),
        )

    def entrar(self, utilizador=None):
        self.client.force_login(utilizador or self.utilizador)


class AdicionarUrlTests(BaseRelacoes):
    def test_adicionar_url_simples(self):
        resposta = self.client.post(
            reverse("livros:url_criar", args=[self.livro.pk]),
            {"url": "https://exemplo.pt/dune", "descricao": "Ficha do livro"},
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], reverse("livros:detalhe", args=[self.livro.pk]))
        link = LinkLivro.objects.get()
        self.assertEqual(link.livro, self.livro)
        self.assertEqual(link.descricao, "Ficha do livro")

    def test_adicionar_url_sem_descricao(self):
        self.client.post(reverse("livros:url_criar", args=[self.livro.pk]), {"url": "https://exemplo.pt"})
        self.assertEqual(LinkLivro.objects.get().descricao, "")

    def test_url_invalido_volta_com_erro_e_nao_grava(self):
        resposta = self.client.post(
            reverse("livros:url_criar", args=[self.livro.pk]),
            {"url": "isto não é um endereço", "descricao": ""},
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(LinkLivro.objects.exists())
        self.assertTrue(resposta.context["form_url"].errors)
        # o texto escrito não se perde
        self.assertContains(resposta, "isto não é um endereço", status_code=400)

    def test_varios_urls_no_mesmo_livro(self):
        for numero in range(3):
            self.client.post(
                reverse("livros:url_criar", args=[self.livro.pk]),
                {"url": f"https://exemplo.pt/{numero}", "descricao": f"Link {numero}"},
            )
        self.assertEqual(self.livro.urls.count(), 3)

    def test_get_nao_cria_url(self):
        resposta = self.client.get(reverse("livros:url_criar", args=[self.livro.pk]))
        self.assertEqual(resposta.status_code, 405)
        self.assertFalse(LinkLivro.objects.exists())

    def test_nao_e_possivel_adicionar_url_a_livro_alheio(self):
        alheio = Livro.objects.create(utilizador=self.outro, titulo="Dele", autor="Z")
        resposta = self.client.post(
            reverse("livros:url_criar", args=[alheio.pk]), {"url": "https://exemplo.pt"}
        )
        self.assertEqual(resposta.status_code, 404)
        self.assertFalse(LinkLivro.objects.exists())

    def test_anonimo_e_encaminhado_para_o_login(self):
        self.client.logout()
        resposta = self.client.post(
            reverse("livros:url_criar", args=[self.livro.pk]), {"url": "https://exemplo.pt"}
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("entrar"), resposta["Location"])
        self.assertFalse(LinkLivro.objects.exists())


class ApagarUrlTests(BaseRelacoes):
    def setUp(self):
        super().setUp()
        self.link = LinkLivro.objects.create(livro=self.livro, url="https://exemplo.pt/dune")
        self.nota = NotaLivro.objects.create(livro=self.livro, texto="uma nota")

    def test_apagar_url_mantem_livro_e_notas(self):
        resposta = self.client.post(reverse("livros:url_apagar", args=[self.link.pk]))
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], reverse("livros:detalhe", args=[self.livro.pk]))
        self.assertFalse(LinkLivro.objects.exists())
        self.assertTrue(Livro.objects.filter(pk=self.livro.pk).exists())
        self.assertTrue(NotaLivro.objects.filter(pk=self.nota.pk).exists())

    def test_nao_e_possivel_apagar_url_alheio(self):
        alheio = Livro.objects.create(utilizador=self.outro, titulo="Dele", autor="Z")
        link_alheio = LinkLivro.objects.create(livro=alheio, url="https://dele.pt")
        resposta = self.client.post(reverse("livros:url_apagar", args=[link_alheio.pk]))
        self.assertEqual(resposta.status_code, 404)
        self.assertTrue(LinkLivro.objects.filter(pk=link_alheio.pk).exists())

    def test_get_nao_apaga_url(self):
        self.assertEqual(self.client.get(reverse("livros:url_apagar", args=[self.link.pk])).status_code, 405)
        self.assertTrue(LinkLivro.objects.filter(pk=self.link.pk).exists())


class AdicionarNotaTests(BaseRelacoes):
    def test_adicionar_nota(self):
        resposta = self.client.post(
            reverse("livros:nota_criar", args=[self.livro.pk]),
            {"texto": "A especiaria tem de fluir."},
        )
        self.assertEqual(resposta.status_code, 302)
        nota = NotaLivro.objects.get()
        self.assertEqual(nota.livro, self.livro)
        self.assertEqual(nota.texto, "A especiaria tem de fluir.")

    def test_nota_vazia_e_rejeitada(self):
        resposta = self.client.post(reverse("livros:nota_criar", args=[self.livro.pk]), {"texto": "   "})
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(NotaLivro.objects.exists())
        self.assertTrue(resposta.context["form_nota"].errors)

    def test_varias_notas_no_mesmo_livro_ordenadas_da_mais_recente(self):
        for numero in range(3):
            self.client.post(
                reverse("livros:nota_criar", args=[self.livro.pk]), {"texto": f"Nota {numero}"}
            )
        self.assertEqual(self.livro.notas.count(), 3)
        self.assertEqual(self.livro.notas.first().texto, "Nota 2")

    def test_nao_e_possivel_adicionar_nota_a_livro_alheio(self):
        alheio = Livro.objects.create(utilizador=self.outro, titulo="Dele", autor="Z")
        resposta = self.client.post(reverse("livros:nota_criar", args=[alheio.pk]), {"texto": "x"})
        self.assertEqual(resposta.status_code, 404)
        self.assertFalse(NotaLivro.objects.exists())


class ApagarNotaTests(BaseRelacoes):
    def setUp(self):
        super().setUp()
        self.nota = NotaLivro.objects.create(livro=self.livro, texto="descartável")
        LinkLivro.objects.create(livro=self.livro, url="https://exemplo.pt")

    def test_apagar_nota_mantem_livro_e_urls(self):
        resposta = self.client.post(reverse("livros:nota_apagar", args=[self.nota.pk]))
        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(NotaLivro.objects.exists())
        self.assertTrue(LinkLivro.objects.exists())
        self.assertTrue(Livro.objects.filter(pk=self.livro.pk).exists())

    def test_nao_e_possivel_apagar_nota_alheia(self):
        alheio = Livro.objects.create(utilizador=self.outro, titulo="Dele", autor="Z")
        nota_alheia = NotaLivro.objects.create(livro=alheio, texto="dele")
        resposta = self.client.post(reverse("livros:nota_apagar", args=[nota_alheia.pk]))
        self.assertEqual(resposta.status_code, 404)
        self.assertTrue(NotaLivro.objects.filter(pk=nota_alheia.pk).exists())


class FichaDoLivroTests(BaseRelacoes):
    def test_ficha_mostra_os_formularios_de_acrescentar(self):
        resposta = self.client.get(reverse("livros:detalhe", args=[self.livro.pk]))
        self.assertContains(resposta, "+ Adicionar URL")
        self.assertContains(resposta, "+ Adicionar nota")
        self.assertContains(resposta, reverse("livros:url_criar", args=[self.livro.pk]))
        self.assertContains(resposta, reverse("livros:nota_criar", args=[self.livro.pk]))

    def test_ficha_mostra_botao_de_remover_por_item(self):
        link = LinkLivro.objects.create(livro=self.livro, url="https://exemplo.pt", descricao="Ficha")
        nota = NotaLivro.objects.create(livro=self.livro, texto="Uma nota")
        resposta = self.client.get(reverse("livros:detalhe", args=[self.livro.pk]))
        self.assertContains(resposta, reverse("livros:url_apagar", args=[link.pk]))
        self.assertContains(resposta, reverse("livros:nota_apagar", args=[nota.pk]))

    def test_contadores_da_ficha_batem_certo(self):
        LinkLivro.objects.create(livro=self.livro, url="https://exemplo.pt/1")
        LinkLivro.objects.create(livro=self.livro, url="https://exemplo.pt/2")
        NotaLivro.objects.create(livro=self.livro, texto="1")
        NotaLivro.objects.create(livro=self.livro, texto="2")
        NotaLivro.objects.create(livro=self.livro, texto="3")
        resposta = self.client.get(reverse("livros:detalhe", args=[self.livro.pk]))
        contadores = resposta.context["livro"]
        self.assertEqual(contadores.urls.count(), 2)
        self.assertEqual(contadores.notas.count(), 3)

    def test_urls_externos_abrem_com_rel_noopener(self):
        LinkLivro.objects.create(livro=self.livro, url="https://exemplo.pt", descricao="Ficha")
        resposta = self.client.get(reverse("livros:detalhe", args=[self.livro.pk]))
        self.assertContains(resposta, 'rel="noopener noreferrer"')
        self.assertContains(resposta, 'target="_blank"')

    def test_a_ficha_mostra_a_data_em_dd_mm_aaaa(self):
        resposta = self.client.get(reverse("livros:detalhe", args=[self.livro.pk]))
        self.assertContains(resposta, "01/06/2025")

    def test_apagar_o_livro_apaga_urls_e_notas_pela_interface(self):
        LinkLivro.objects.create(livro=self.livro, url="https://exemplo.pt")
        NotaLivro.objects.create(livro=self.livro, texto="nota")
        self.client.post(reverse("livros:apagar", args=[self.livro.pk]))
        self.assertFalse(LinkLivro.objects.exists())
        self.assertFalse(NotaLivro.objects.exists())


class SemTokenCsrfTests(TestCase):
    """Sem CSRF os POSTs têm de ser recusados (cliente com verificação ligada)."""

    def setUp(self):
        self.utilizador = get_user_model().objects.create_user(username="dinis", password=PASSWORD)
        self.livro = Livro.objects.create(utilizador=self.utilizador, titulo="Dune", autor="F. H.")
        self.cliente = Client(enforce_csrf_checks=True)
        self.cliente.force_login(self.utilizador)

    def test_url_criar_sem_csrf(self):
        resposta = self.cliente.post(
            reverse("livros:url_criar", args=[self.livro.pk]), {"url": "https://exemplo.pt"}
        )
        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(LinkLivro.objects.exists())

    def test_nota_criar_sem_csrf(self):
        resposta = self.cliente.post(
            reverse("livros:nota_criar", args=[self.livro.pk]), {"texto": "x"}
        )
        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(NotaLivro.objects.exists())

    def test_apagar_livro_sem_csrf(self):
        resposta = self.cliente.post(reverse("livros:apagar", args=[self.livro.pk]))
        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(Livro.objects.filter(pk=self.livro.pk).exists())
