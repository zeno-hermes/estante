"""Rotas do projeto Estante.

- /entrar/ e /sair/: autenticação (fase 1)
- /livros/: site desktop (fase 1) — URLs e notas na fase 2
- /pwa/: aplicação mobile instalável (fase 3)
- /saude/: healthcheck público (deploy e monitorização)
"""

from django.contrib import admin
from django.urls import path

from .views import saude

urlpatterns = [
    path("admin/", admin.site.urls),
    path("saude/", saude, name="saude"),
]
