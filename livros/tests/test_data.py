"""Testes do formulário de data (dd/mm/aaaa com máscara e calendário).

O campo nativo do browser não serve para escrever (mostra o formato do sistema):
o que guarda é um campo de texto em dd/mm/aaaa, com `static/js/data-br.js` a
inserir as barras e um campo `type="date"` ao lado só para abrir o calendário.
Esse campo nativo **não pode ter `name`**, senão haveria dois valores de data no
mesmo formulário.
"""

import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from livros.forms import DataBRWidget, LivroForm

PASSWORD = "uma-password-de-teste-1234"


class WidgetDataBRTests(TestCase):
    def html_do_campo(self, valor=None):
        form = LivroForm(utilizador=get_user_model().objects.create_user("t", password=PASSWORD))
        if valor is not None:
            form.initial["data_leitura"] = valor
        return str(form["data_leitura"])

    def test_campo_de_escrita_e_de_texto_com_ajuda_para_o_telemovel(self):
        html = self.html_do_campo()
        self.assertIn('data-campo-data-br="1"', html)
        self.assertIn('inputmode="numeric"', html)
        self.assertIn('placeholder="dd/mm/aaaa"', html)
        self.assertIn('maxlength="10"', html)
        self.assertIn("pattern=", html)

    def test_tem_um_campo_de_calendario_ao_lado(self):
        html = self.html_do_campo()
        self.assertIn('type="date"', html)
        self.assertIn("data-campo-data-calendario", html)
        self.assertIn("aria-label", html)

    def test_o_campo_do_calendario_nao_e_submetido(self):
        """Sem `name` não entra no POST: quem guarda a data é o campo de texto."""
        html = self.html_do_campo()
        nativo = re.search(r"<input type=\"date\"[^>]*>", html).group(0)
        self.assertNotIn("name=", nativo)
        self.assertIn("data-para=", nativo)  # liga o calendário ao campo certo

    def test_data_existente_aparece_em_dd_mm_aaaa_nos_dois_campos(self):
        from datetime import date

        html = self.html_do_campo(valor=date(2026, 8, 14))
        self.assertIn('value="14/08/2026"', html)   # campo de texto
        self.assertIn('value="2026-08-14"', html)   # campo do calendário (ISO)

    def test_valor_iso_aceita_o_que_o_utilizador_escreveu(self):
        widget = DataBRWidget()
        self.assertEqual(widget.valor_iso("14/08/2026"), "2026-08-14")
        self.assertEqual(widget.valor_iso("2026-08-14"), "2026-08-14")
        self.assertEqual(widget.valor_iso("data inválida"), "")
        self.assertEqual(widget.valor_iso(None), "")

    def test_mascara_e_script_estao_ligados_nas_duas_interfaces(self):
        for caminho in ("livros/entrar.html", "pwa/entrar.html"):
            with self.subTest(template=caminho):
                self.assertTrue(caminho.endswith(".html"))
        for nome in ("livros:lista", "pwa:lista"):
            with self.subTest(pagina=nome):
                utilizador = get_user_model().objects.create_user(f"u{nome[4:]}", password=PASSWORD)
                self.client.force_login(utilizador)
                html = self.client.get(reverse(nome)).content.decode()
                self.assertIn("/static/js/data-br.js", html)


class FormularioComDataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.utilizador = get_user_model().objects.create_user(username="dinis", password=PASSWORD)

    def setUp(self):
        self.client.force_login(self.utilizador)

    def test_formulario_mobile_tem_mascara_e_calendario(self):
        resposta = self.client.get(reverse("pwa:criar"))
        html = resposta.content.decode()
        self.assertIn("campo-data", html)
        self.assertIn('data-campo-data-calendario', html)
        self.assertIn("/static/js/data-br.js", html)

    def test_formulario_desktop_tem_mascara_e_calendario(self):
        resposta = self.client.get(reverse("livros:criar"))
        html = resposta.content.decode()
        self.assertIn("campo-data", html)
        self.assertIn("data-campo-data-calendario", html)

    def test_so_se_escrever_numeros_a_data_e_aceite(self):
        """O que o utilizador escreve no telemóvel: 14 08 2026 -> 14/08/2026."""
        resposta = self.client.post(
            reverse("pwa:criar"),
            {"titulo": "Com data", "autor": "Autor", "data_leitura": "14/08/2026",
             "avaliacao": "", "estado": "lido"},
        )
        self.assertEqual(resposta.status_code, 302)
        from livros.models import Livro

        self.assertEqual(str(Livro.objects.get(titulo="Com data").data_leitura), "2026-08-14")

    def test_script_da_mascara_insere_barras(self):
        """O ficheiro estático existe e sabe formatar (checagem de contrato)."""
        from django.contrib.staticfiles import finders

        caminho = finders.find("js/data-br.js")
        self.assertIsNotNone(caminho, "static/js/data-br.js não encontrado")
        with open(caminho, encoding="utf-8") as ficheiro:
            conteudo = ficheiro.read()
        self.assertIn("slice(0, 2) + '/' + d.slice(2)", conteudo)
        self.assertIn("data-campo-data-calendario", conteudo)
