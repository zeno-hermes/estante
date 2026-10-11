"""Rotas do projeto Estante.

- /: encaminha para a lista (ou para o login, se anónimo)
- /entrar/ e /sair/: autenticação (registo público desligado)
- /livros/: site desktop
- /pwa/: aplicação mobile instalável (fase 3)
- /saude/: healthcheck público (deploy e monitorização)
"""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from .views import home, saude

urlpatterns = [
    path("", home, name="home"),
    path(
        "entrar/",
        auth_views.LoginView.as_view(
            template_name="livros/entrar.html", redirect_authenticated_user=True
        ),
        name="entrar",
    ),
    path("sair/", auth_views.LogoutView.as_view(), name="sair"),
    path("livros/", include("livros.urls")),
    path("pwa/", include("pwa.urls")),
    path("admin/", admin.site.urls),
    path("saude/", saude, name="saude"),
]
