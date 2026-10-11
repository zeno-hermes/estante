"""Testes do CRUD de livros no site desktop: criação, edição, remoção,
isolamento entre utilizadores, filtros, ordenação e paginação."""

import re
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from livros.models import LinkLivro, Livro, NotaLivro

PASSWORD = "uma-password-de-teste-1234"
MARCADOR_CARTAO = 'class="cartao livro'
# A lista tem duas formas: uma linha por livro (tabela, por omissão) ou cartões.
# A contagem tem de valer nas duas, senão os testes passam a medir o layout.
MARCADOR_LINHA = 'class="tabela__linha'


def contas_no_html(html):
    """Conta os livros apresentados no HTML (evidência do que o browser vê)."""
    return html.count(MARCADOR_CARTAO) + html.count(MARCADOR_LINHA)


class BaseComUtilizador(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.utilizador = get_user_model().objects.create_user(username="dinis", password=PASSWORD)
        cls.outro = get_user_model().objects.create_user(username="intruso", password=PASSWORD)

    def entrar(self, utilizador=None):
        self.client.force_login(utilizador or self.utilizador)

    def criar_livro(self, **kwargs):
        dados = {
            "utilizador": self.utilizador,
            "titulo": "Ensaio sobre a Cegueira",
            "autor": "José Saramago",
            "data_leitura": date(2024, 3, 12),
        }
        dados.update(kwargs)
        return Livro.objects.create(**dados)


class CriarLivroTests(BaseComUtilizador):
    def setUp(self):
        self.entrar()

    def test_formulario_de_criacao_abre(self):
        resposta = self.client.get(reverse("livros:criar"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Novo livro")
        self.assertIn("estrelas", resposta.content.decode())

    def test_criar_com_dados_validos(self):
        resposta = self.client.post(
            reverse("livros:criar"),
            {
                "titulo": "Dune",
                "autor": "Frank Herbert",
                "data_leitura": "01/06/2025",
                "avaliacao": "5",
                "estado": "lido",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        livro = Livro.objects.get(titulo="Dune")
        self.assertEqual(livro.utilizador, self.utilizador)
        self.assertEqual(livro.data_leitura, date(2025, 6, 1))
        self.assertEqual(livro.avaliacao, 5)
        self.assertEqual(livro.estado, Livro.Estado.LIDO)

    def test_data_em_formato_iso_tambem_e_aceite(self):
        # compatibilidade: dados importados ou colados em ISO continuam a entrar
        self.client.post(
            reverse("livros:criar"),
            {"titulo": "Em ISO", "autor": "X", "data_leitura": "2025-06-01", "avaliacao": "", "estado": "lido"},
        )
        self.assertEqual(Livro.objects.get(titulo="Em ISO").data_leitura, date(2025, 6, 1))

    def test_data_escrita_em_formato_errado_da_erro_explicito(self):
        resposta = self.client.post(
            reverse("livros:criar"),
            {"titulo": "Data má", "autor": "X", "data_leitura": "14-08-2026", "avaliacao": "", "estado": "lido"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "formato dd/mm/aaaa")
        self.assertFalse(Livro.objects.filter(titulo="Data má").exists())

    def test_campo_de_data_usa_dd_mm_aaaa_com_calendario_ao_lado(self):
        resposta = self.client.get(reverse("livros:criar"))
        html = resposta.content.decode()
        self.assertIn('placeholder="dd/mm/aaaa"', html)
        # o campo de escrita é de texto (o nativo mostra o formato do sistema)
        campo_texto = re.search(r'<input type="text"[^>]*data-campo-data-br[^>]*>', html)
        self.assertIsNotNone(campo_texto)
        # e há um campo nativo só para o calendário, sem `name` (não é submetido)
        nativo = re.search(r'<input type="date"[^>]*>', html)
        self.assertIsNotNone(nativo)
        self.assertNotIn("name=", nativo.group(0))

    def test_edicao_mostra_a_data_existente_em_dd_mm_aaaa(self):
        livro = self.criar_livro()
        resposta = self.client.get(reverse("livros:editar", args=[livro.pk]))
        self.assertContains(resposta, 'value="12/03/2024"')

    def test_criar_sem_avaliacao_guarda_nulo(self):
        self.client.post(
            reverse("livros:criar"),
            {"titulo": "Sem nota", "autor": "Alguém", "data_leitura": "", "avaliacao": "", "estado": "a_ler"},
        )
        livro = Livro.objects.get(titulo="Sem nota")
        self.assertIsNone(livro.avaliacao)
        self.assertIsNone(livro.data_leitura)
        self.assertEqual(livro.estado, Livro.Estado.A_LER)

    def test_data_no_futuro_e_rejeitada(self):
        futuro = date.today() + timedelta(days=3)
        resposta = self.client.post(
            reverse("livros:criar"),
            {
                "titulo": "Impossível",
                "autor": "X",
                "data_leitura": f"{futuro.day:02d}/{futuro.month:02d}/{futuro.year}",
                "avaliacao": "",
                "estado": "lido",
            },
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "não pode estar no futuro")
        self.assertFalse(Livro.objects.filter(titulo="Impossível").exists())

    def test_titulo_vazio_e_rejeitado(self):
        resposta = self.client.post(
            reverse("livros:criar"),
            {"titulo": "   ", "autor": "Autor", "data_leitura": "", "avaliacao": "", "estado": "lido"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Livro.objects.exists())

    def test_avaliacao_fora_do_intervalo_e_rejeitada(self):
        resposta = self.client.post(
            reverse("livros:criar"),
            {"titulo": "Avaliação má", "autor": "X", "data_leitura": "", "avaliacao": "9", "estado": "lido"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Livro.objects.filter(titulo="Avaliação má").exists())

    def test_duplicado_exato_e_rejeitado_com_erro_no_formulario(self):
        self.criar_livro()
        resposta = self.client.post(
            reverse("livros:criar"),
            {
                "titulo": "Ensaio sobre a Cegueira",
                "autor": "José Saramago",
                "data_leitura": "12/03/2024",
                "avaliacao": "",
                "estado": "lido",
            },
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context["form"].errors)
        self.assertEqual(Livro.objects.count(), 1)

    def test_releitura_com_data_diferente_e_aceite(self):
        self.criar_livro()
        resposta = self.client.post(
            reverse("livros:criar"),
            {
                "titulo": "Ensaio sobre a Cegueira",
                "autor": "José Saramago",
                "data_leitura": "02/02/2026",
                "avaliacao": "4",
                "estado": "lido",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Livro.objects.count(), 2)

    def test_dois_livros_a_ler_com_o_mesmo_titulo_sao_aceites(self):
        # NULL não colide com NULL em SQL: o formulário tem de seguir a BD.
        for _ in range(2):
            resposta = self.client.post(
                reverse("livros:criar"),
                {
                    "titulo": "Em curso",
                    "autor": "Autor",
                    "data_leitura": "",
                    "avaliacao": "",
                    "estado": "a_ler",
                },
            )
            self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Livro.objects.filter(titulo="Em curso").count(), 2)

    def test_editar_sem_mudar_nada_nao_da_erro_de_duplicado(self):
        livro = self.criar_livro()
        resposta = self.client.post(
            reverse("livros:editar", args=[livro.pk]),
            {
                "titulo": "Ensaio sobre a Cegueira",
                "autor": "José Saramago",
                "data_leitura": "12/03/2024",
                "avaliacao": "",
                "estado": "lido",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Livro.objects.count(), 1)

    def test_livro_criado_pertence_sempre_a_quem_esta_autenticado(self):
        self.entrar(self.outro)
        self.client.post(
            reverse("livros:criar"),
            {
                "titulo": "Do intruso",
                "autor": "X",
                "data_leitura": "",
                "avaliacao": "",
                "estado": "lido",
                "utilizador": self.utilizador.pk,  # tentativa de injetar outro dono
            },
        )
        livro = Livro.objects.get(titulo="Do intruso")
        self.assertEqual(livro.utilizador, self.outro)


class EditarEApagarTests(BaseComUtilizador):
    def setUp(self):
        self.entrar()
        self.livro = self.criar_livro()

    def test_editar_livro(self):
        resposta = self.client.post(
            reverse("livros:editar", args=[self.livro.pk]),
            {
                "titulo": "Ensaio sobre a Cegueira",
                "autor": "José Saramago",
                "data_leitura": "12/03/2024",
                "avaliacao": "4",
                "estado": "abandonado",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], reverse("livros:detalhe", args=[self.livro.pk]))
        self.livro.refresh_from_db()
        self.assertEqual(self.livro.avaliacao, 4)
        self.assertEqual(self.livro.estado, Livro.Estado.ABANDONADO)

    def test_pagina_de_apagar_mostra_confirmacao(self):
        resposta = self.client.get(reverse("livros:apagar", args=[self.livro.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Apagar")

    def test_apagar_por_post_remove_o_livro_e_os_filhos(self):
        LinkLivro.objects.create(livro=self.livro, url="https://exemplo.pt/x")
        NotaLivro.objects.create(livro=self.livro, texto="nota")
        resposta = self.client.post(reverse("livros:apagar", args=[self.livro.pk]))
        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(Livro.objects.exists())
        self.assertFalse(LinkLivro.objects.exists())
        self.assertFalse(NotaLivro.objects.exists())

    def test_nao_e_possivel_editar_livro_de_outro_utilizador(self):
        alheio = Livro.objects.create(utilizador=self.outro, titulo="Dele", autor="Z")
        self.assertEqual(
            self.client.get(reverse("livros:editar", args=[alheio.pk])).status_code, 404
        )
        self.assertEqual(
            self.client.post(
                reverse("livros:editar", args=[alheio.pk]),
                {"titulo": "Alterado", "autor": "Z", "data_leitura": "", "avaliacao": "", "estado": "lido"},
            ).status_code,
            404,
        )
        alheio.refresh_from_db()
        self.assertEqual(alheio.titulo, "Dele")

    def test_nao_e_possivel_apagar_livro_de_outro_utilizador(self):
        alheio = Livro.objects.create(utilizador=self.outro, titulo="Dele", autor="Z")
        self.assertEqual(
            self.client.post(reverse("livros:apagar", args=[alheio.pk])).status_code, 404
        )
        self.assertTrue(Livro.objects.filter(pk=alheio.pk).exists())

    def test_nao_e_possivel_ver_detalhe_de_outro_utilizador(self):
        alheio = Livro.objects.create(utilizador=self.outro, titulo="Dele", autor="Z")
        self.assertEqual(
            self.client.get(reverse("livros:detalhe", args=[alheio.pk])).status_code, 404
        )


class ListaEFiltrosTests(BaseComUtilizador):
    def setUp(self):
        self.entrar()
        self.saramago = self.criar_livro(avaliacao=5)
        self.dune = self.criar_livro(
            titulo="Dune", autor="Frank Herbert", data_leitura=date(2025, 6, 1), avaliacao=4
        )
        self.a_ler = self.criar_livro(
            titulo="Ainda a ler",
            autor="Autor Novo",
            data_leitura=None,
            estado=Livro.Estado.A_LER,
            avaliacao=None,
        )
        Livro.objects.create(
            utilizador=self.outro,
            titulo="Livro do intruso",
            autor="Intruso",
            data_leitura=date(2025, 1, 1),
        )

    def test_lista_mostra_apenas_os_livros_do_utilizador(self):
        resposta = self.client.get(reverse("livros:lista"))
        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, "Livro do intruso")
        # o que está no HTML tem de ser igual ao que existe na BD para este utilizador
        self.assertEqual(contas_no_html(resposta.content.decode()), Livro.objects.filter(utilizador=self.utilizador).count())

    def test_lista_em_linhas_por_omissao(self):
        """Uma linha por livro (tabela) é a apresentação de omissão."""
        resposta = self.client.get(reverse("livros:lista"))
        self.assertEqual(resposta.context["vista"], "lista")
        self.assertContains(resposta, 'class="tabela"')
        self.assertEqual(resposta.content.decode().count(MARCADOR_CARTAO), 0)
        self.assertContains(resposta, "Leitura")  # cabeçalho das colunas

    def test_vista_em_cartoes_pelo_parametro(self):
        resposta = self.client.get(reverse("livros:lista"), {"vista": "cartoes"})
        self.assertEqual(resposta.context["vista"], "cartoes")
        self.assertContains(resposta, MARCADOR_CARTAO)
        self.assertEqual(resposta.content.decode().count(MARCADOR_LINHA), 0)

    def test_vista_escolhida_fica_guardada_no_cookie(self):
        """Escolher cartões vale para as visitas seguintes (e para a paginação)."""
        primeira = self.client.get(reverse("livros:lista"), {"vista": "cartoes"})
        self.assertEqual(primeira.cookies["estante_vista"].value, "cartoes")

        seguinte = self.client.get(reverse("livros:lista"))
        self.assertEqual(seguinte.context["vista"], "cartoes")
        self.assertContains(seguinte, MARCADOR_CARTAO)

        # e volta atrás sem ficar preso
        terceira = self.client.get(reverse("livros:lista"), {"vista": "lista"})
        self.assertEqual(terceira.context["vista"], "lista")
        self.assertEqual(terceira.cookies["estante_vista"].value, "lista")

    def test_vista_invalida_cai_na_omissao(self):
        resposta = self.client.get(reverse("livros:lista"), {"vista": "diagonal"})
        self.assertEqual(resposta.context["vista"], "lista")

    def test_links_da_vista_nao_perdem_os_filtros(self):
        resposta = self.client.get(reverse("livros:lista"), {"q": "dune", "order": "titulo"})
        cartoes = [v for v in resposta.context["vistas"] if v["chave"] == "cartoes"][0]
        self.assertIn("vista=cartoes", cartoes["url"])
        self.assertIn("q=dune", cartoes["url"])
        self.assertIn("order=titulo", cartoes["url"])
        self.assertNotIn("vista=", cartoes["url"].replace("vista=cartoes", ""))

    def test_estado_planeado_existe_nos_filtros_e_conta_no_resumo(self):
        planeado = self.criar_livro(
            titulo="Para ler em breve",
            autor="Autor Futuro",
            data_leitura=None,
            estado=Livro.Estado.PLANEADO,
            avaliacao=None,
        )
        resposta = self.client.get(reverse("livros:lista"))
        self.assertEqual(resposta.context["resumo"]["planeados"], 1)
        self.assertContains(resposta, "Planeado")
        self.assertContains(resposta, planeado.titulo)

        filtrado = self.client.get(reverse("livros:lista"), {"estado": "planeado"})
        self.assertEqual(contas_no_html(filtrado.content.decode()), 1)
        self.assertContains(filtrado, planeado.titulo)

    def test_pesquisa_por_titulo_e_autor(self):
        por_titulo = self.client.get(reverse("livros:lista"), {"q": "dune"})
        self.assertEqual(contas_no_html(por_titulo.content.decode()), 1)
        por_autor = self.client.get(reverse("livros:lista"), {"q": "herbert"})
        self.assertEqual(contas_no_html(por_autor.content.decode()), 1)
        sem_resultados = self.client.get(reverse("livros:lista"), {"q": "inexistente"})
        self.assertEqual(contas_no_html(sem_resultados.content.decode()), 0)
        self.assertContains(sem_resultados, "Sem resultados")

    def test_pesquisa_em_notas_e_descricao_de_urls(self):
        NotaLivro.objects.create(livro=self.dune, texto="Fala de especiaria em Arrakis")
        LinkLivro.objects.create(livro=self.dune, url="https://exemplo.pt", descricao="Crítica no blog")
        self.assertEqual(contas_no_html(self.client.get(reverse("livros:lista"), {"q": "especiaria"}).content.decode()), 1)
        self.assertEqual(contas_no_html(self.client.get(reverse("livros:lista"), {"q": "crítica"}).content.decode()), 1)
        # a mesma linha não pode aparecer duplicada por causa das junções
        self.assertEqual(contas_no_html(self.client.get(reverse("livros:lista"), {"q": "arrakis"}).content.decode()), 1)

    def test_filtro_por_estado(self):
        resposta = self.client.get(reverse("livros:lista"), {"estado": "a_ler"})
        self.assertEqual(contas_no_html(resposta.content.decode()), 1)
        self.assertContains(resposta, "Ainda a ler")

    def test_filtro_por_avaliacao_e_sem_avaliacao(self):
        self.assertEqual(contas_no_html(self.client.get(reverse("livros:lista"), {"avaliacao": "5"}).content.decode()), 1)
        sem = self.client.get(reverse("livros:lista"), {"avaliacao": "sem"})
        self.assertEqual(contas_no_html(sem.content.decode()), 1)
        self.assertContains(sem, "Ainda a ler")

    def test_filtro_invalido_e_ignorado(self):
        resposta = self.client.get(reverse("livros:lista"), {"estado": "inventado", "avaliacao": "99", "order": "xyz"})
        self.assertEqual(contas_no_html(resposta.content.decode()), 3)

    def test_ordenacao(self):
        por_titulo = self.client.get(reverse("livros:lista"), {"order": "titulo"})
        titulos = [linha.titulo for linha in por_titulo.context["livros"]]
        self.assertEqual(titulos, sorted(titulos))
        por_avaliacao = self.client.get(reverse("livros:lista"), {"order": "avaliacao"})
        avaliacoes = [linha.avaliacao for linha in por_avaliacao.context["livros"]]
        self.assertEqual(avaliacoes, [5, 4, None])
        recentes = self.client.get(reverse("livros:lista"), {"order": "recentes"})
        datas = [linha.data_leitura for linha in recentes.context["livros"]]
        self.assertEqual(datas[0], date(2025, 6, 1))

    def test_resumo_do_cabecalho_bate_certo_com_a_base_de_dados(self):
        Livro.objects.create(
            utilizador=self.utilizador,
            titulo="Acabado de ler",
            autor="Autor de agora",
            data_leitura=date.today(),
            avaliacao=5,
            estado=Livro.Estado.LIDO,
        )
        resposta = self.client.get(reverse("livros:lista"))
        resumo = resposta.context["resumo"]
        self.assertEqual(resumo["total"], 4)
        self.assertEqual(resumo["lidos"], 3)
        self.assertEqual(resumo["a_ler"], 1)
        self.assertEqual(resumo["media"], round((5 + 4 + 5) / 3, 1))
        self.assertEqual(resumo["este_ano"], 1)
        # contadores coerentes com a BD, não com o que parece
        todos = Livro.objects.filter(utilizador=self.utilizador)
        self.assertEqual(resumo["total"], todos.count())
        self.assertEqual(resumo["este_ano"], todos.filter(data_leitura__year=date.today().year).count())

    def test_paginacao_com_mais_de_vinte_livros(self):
        for numero in range(25):
            Livro.objects.create(
                utilizador=self.utilizador,
                titulo=f"Livro {numero:02d}",
                autor="Autor",
                data_leitura=date(2020, 1, 1) + timedelta(days=numero),
            )
        primeira = self.client.get(reverse("livros:lista"))
        self.assertEqual(len(primeira.context["livros"]), 20)
        self.assertEqual(contas_no_html(primeira.content.decode()), 20)
        segunda = self.client.get(reverse("livros:lista"), {"page": 2})
        self.assertEqual(len(segunda.context["livros"]), 8)
        self.assertContains(segunda, "Página 2 de 2")

    def test_pagina_invalida_nao_rebenta(self):
        self.assertEqual(self.client.get(reverse("livros:lista"), {"page": "999"}).status_code, 404)

    def test_contadores_de_notas_e_urls_por_livro(self):
        NotaLivro.objects.create(livro=self.dune, texto="1")
        NotaLivro.objects.create(livro=self.dune, texto="2")
        LinkLivro.objects.create(livro=self.dune, url="https://exemplo.pt")
        resposta = self.client.get(reverse("livros:lista"))
        livro = next(item for item in resposta.context["livros"] if item.pk == self.dune.pk)
        self.assertEqual(livro.total_notas, 2)
        self.assertEqual(livro.total_urls, 1)

    def test_detalhe_mostra_notas_e_urls(self):
        LinkLivro.objects.create(livro=self.dune, url="https://exemplo.pt/dune", descricao="Ficha")
        NotaLivro.objects.create(livro=self.dune, texto="Melhor ficção científica de sempre")
        resposta = self.client.get(reverse("livros:detalhe", args=[self.dune.pk]))
        self.assertContains(resposta, "Frank Herbert")
        self.assertContains(resposta, "Ficha")
        self.assertContains(resposta, "Melhor ficção científica de sempre")

    def test_lista_vazia_convida_a_registar(self):
        Livro.objects.all().delete()
        resposta = self.client.get(reverse("livros:lista"))
        self.assertContains(resposta, "A estante está vazia")
