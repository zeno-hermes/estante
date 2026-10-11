"""Testes de autenticação: o que está fechado tem de estar mesmo fechado."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

PASSWORD = "uma-password-de-teste-1234"


class AcessoAnonimoTests(TestCase):
    def test_raiz_encaminha_para_o_login(self):
        resposta = self.client.get("/")
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("entrar"), resposta["Location"])

    def test_lista_de_livros_exige_autenticacao(self):
        resposta = self.client.get(reverse("livros:lista"))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("entrar"), resposta["Location"])
        self.assertIn(reverse("livros:lista"), resposta["Location"])

    def test_criar_livro_exige_autenticacao(self):
        resposta = self.client.get(reverse("livros:criar"))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("entrar"), resposta["Location"])

    def test_detalhe_e_edicao_exigem_autenticacao(self):
        utilizador = get_user_model().objects.create_user(username="dono", password=PASSWORD)
        from livros.models import Livro

        livro = Livro.objects.create(utilizador=utilizador, titulo="X", autor="Y")
        for url in (
            reverse("livros:detalhe", args=[livro.pk]),
            reverse("livros:editar", args=[livro.pk]),
            reverse("livros:apagar", args=[livro.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)

    def test_pagina_de_entrar_esta_acessivel_e_em_portugues(self):
        resposta = self.client.get(reverse("entrar"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Entrar na Estante")
        self.assertContains(resposta, 'name="csrfmiddlewaretoken"', html=False)

    def test_nao_existe_registo_publico(self):
        for caminho in ("/registar/", "/registro/", "/signup/", "/accounts/signup/"):
            with self.subTest(caminho=caminho):
                self.assertEqual(self.client.get(caminho).status_code, 404)


class FluxoDeLoginTests(TestCase):
    def setUp(self):
        self.utilizador = get_user_model().objects.create_user(
            username="dinis", password=PASSWORD
        )

    def test_login_valido_entra_e_encaminha_para_a_lista(self):
        resposta = self.client.post(
            reverse("entrar"), {"username": "dinis", "password": PASSWORD}
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], reverse("livros:lista"))
        self.assertEqual(self.client.get(reverse("livros:lista")).status_code, 200)

    def test_login_invalido_nao_autentica(self):
        resposta = self.client.post(
            reverse("entrar"), {"username": "dinis", "password": "errada-à-força"}
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        # A mensagem de erro do Django aparece em português ou inglês, mas tem de existir.
        self.assertTrue(resposta.context["form"].errors)

    def test_utilizador_autenticado_nao_ve_a_pagina_de_login(self):
        self.client.force_login(self.utilizador)
        resposta = self.client.get(reverse("entrar"))
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], reverse("livros:lista"))

    def test_sair_por_post_termina_a_sessao(self):
        self.client.force_login(self.utilizador)
        resposta = self.client.post(reverse("sair"))
        self.assertEqual(resposta.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.get(reverse("livros:lista")).status_code, 302)

    def test_sair_por_get_e_recusado(self):
        self.client.force_login(self.utilizador)
        resposta = self.client.get(reverse("sair"))
        self.assertEqual(resposta.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)


class HealthcheckTests(TestCase):
    def test_saude_responde_json_publico(self):
        resposta = self.client.get("/saude/")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Content-Type"], "application/json")
        self.assertEqual(resposta.json(), {"status": "ok", "bd": "ok"})
