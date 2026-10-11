"""Testes do modelo de dados: validação, unicidade, relações 1:N e ordenação."""

from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from livros.models import LinkLivro, Livro, NotaLivro


class LivroModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.utilizador = get_user_model().objects.create_user(
            username="teste", password="uma-password-de-teste-1234"
        )

    def criar(self, **kwargs):
        dados = {
            "utilizador": self.utilizador,
            "titulo": "Ensaio sobre a Cegueira",
            "autor": "José Saramago",
            "data_leitura": date(2024, 3, 12),
        }
        dados.update(kwargs)
        return Livro.objects.create(**dados)

    def test_criar_livro_e_ler_campos(self):
        livro = self.criar(avaliacao=5, estado=Livro.Estado.LIDO)
        self.assertEqual(livro.titulo, "Ensaio sobre a Cegueira")
        self.assertEqual(livro.autor, "José Saramago")
        self.assertEqual(livro.data_leitura, date(2024, 3, 12))
        self.assertEqual(livro.avaliacao, 5)
        self.assertEqual(str(livro), "Ensaio sobre a Cegueira — José Saramago")

    def test_avaliacao_superior_a_cinco_e_invalida(self):
        livro = Livro(
            utilizador=self.utilizador,
            titulo="X",
            autor="Y",
            data_leitura=date(2024, 1, 1),
            avaliacao=6,
        )
        with self.assertRaises(ValidationError):
            livro.full_clean()

    def test_avaliacao_inferior_a_um_e_invalida(self):
        livro = Livro(
            utilizador=self.utilizador,
            titulo="X",
            autor="Y",
            data_leitura=date(2024, 1, 1),
            avaliacao=0,
        )
        with self.assertRaises(ValidationError):
            livro.full_clean()

    def test_avaliacao_e_data_sao_opcionais(self):
        livro = Livro(utilizador=self.utilizador, titulo="A ler", autor="Alguém")
        livro.full_clean()
        livro.save()
        self.assertIsNone(livro.avaliacao)
        self.assertIsNone(livro.data_leitura)
        self.assertEqual(livro.estado, Livro.Estado.LIDO)

    def test_estado_por_omissao_e_lido(self):
        self.assertEqual(self.criar().estado, Livro.Estado.LIDO)

    def test_estado_planeado_para_o_que_ainda_nao_comecei(self):
        """«Planeado» é um estado próprio e anda sem data de leitura."""
        livro = self.criar(
            titulo="A ler em breve",
            autor="Alguém",
            data_leitura=None,
            estado=Livro.Estado.PLANEADO,
        )
        livro.refresh_from_db()
        self.assertEqual(livro.estado, "planeado")
        self.assertEqual(livro.get_estado_display(), "Planeado")
        self.assertIsNone(livro.data_leitura)
        self.assertEqual([valor for valor, _ in Livro.Estado.choices].count("planeado"), 1)

    def test_estrelas_representa_a_avaliacao(self):
        self.assertEqual(self.criar(avaliacao=3).estrelas, "★★★☆☆")
        self.assertEqual(self.criar(titulo="Outro", avaliacao=None).estrelas, "☆☆☆☆☆")

    def test_registo_exatamente_duplicado_e_rejeitado(self):
        self.criar()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.criar()

    def test_releitura_com_data_diferente_e_aceite(self):
        self.criar(data_leitura=date(2024, 3, 12))
        releitura = self.criar(data_leitura=date(2026, 1, 5))
        self.assertEqual(
            Livro.objects.filter(titulo="Ensaio sobre a Cegueira").count(), 2
        )
        self.assertEqual(releitura.data_leitura, date(2026, 1, 5))

    def test_livros_de_utilizadores_diferentes_nao_colidem(self):
        outro = get_user_model().objects.create_user(
            username="outro", password="uma-password-de-teste-1234"
        )
        self.criar()
        Livro.objects.create(
            utilizador=outro,
            titulo="Ensaio sobre a Cegueira",
            autor="José Saramago",
            data_leitura=date(2024, 3, 12),
        )
        self.assertEqual(Livro.objects.count(), 2)

    def test_ordenacao_por_data_de_leitura_descendente(self):
        self.criar(titulo="Antigo", data_leitura=date(2020, 1, 1))
        self.criar(titulo="Recente", data_leitura=date(2026, 1, 1))
        self.criar(titulo="Sem data", data_leitura=None)
        titulos = list(Livro.objects.values_list("titulo", flat=True))
        self.assertEqual(titulos, ["Recente", "Antigo", "Sem data"])


class RelacoesUmParaMuitosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.utilizador = get_user_model().objects.create_user(
            username="teste", password="uma-password-de-teste-1234"
        )

    def setUp(self):
        self.livro = Livro.objects.create(
            utilizador=self.utilizador,
            titulo="Dune",
            autor="Frank Herbert",
            data_leitura=date(2025, 6, 1),
        )

    def test_livro_tem_varios_urls(self):
        LinkLivro.objects.create(livro=self.livro, url="https://exemplo.pt/dune", descricao="Ficha")
        LinkLivro.objects.create(livro=self.livro, url="https://exemplo.pt/critica")
        self.assertEqual(self.livro.urls.count(), 2)
        self.assertEqual(self.livro.urls.first().descricao, "Ficha")

    def test_livro_tem_varias_notas_ordenadas_da_mais_recente(self):
        NotaLivro.objects.create(livro=self.livro, texto="Primeira nota")
        segunda = NotaLivro.objects.create(livro=self.livro, texto="Segunda nota")
        self.assertEqual(self.livro.notas.count(), 2)
        self.assertEqual(self.livro.notas.first().pk, segunda.pk)

    def test_apagar_livro_apaga_urls_e_notas(self):
        LinkLivro.objects.create(livro=self.livro, url="https://exemplo.pt/dune")
        NotaLivro.objects.create(livro=self.livro, texto="Uma nota")
        self.livro.delete()
        self.assertEqual(LinkLivro.objects.count(), 0)
        self.assertEqual(NotaLivro.objects.count(), 0)

    def test_apagar_uma_nota_nao_toca_nas_outras_nem_nos_urls(self):
        nota = NotaLivro.objects.create(livro=self.livro, texto="Descartável")
        NotaLivro.objects.create(livro=self.livro, texto="Fica")
        LinkLivro.objects.create(livro=self.livro, url="https://exemplo.pt/dune")
        nota.delete()
        self.assertEqual(self.livro.notas.count(), 1)
        self.assertEqual(self.livro.urls.count(), 1)
        self.assertTrue(Livro.objects.filter(pk=self.livro.pk).exists())

    def test_url_invalido_e_rejeitado(self):
        link = LinkLivro(livro=self.livro, url="não é um url")
        with self.assertRaises(ValidationError):
            link.full_clean()
