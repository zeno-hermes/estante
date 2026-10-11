from django.urls import path

from . import views

app_name = "pwa"

urlpatterns = [
    path("", views.ListaView.as_view(), name="lista"),
    path("entrar/", views.EntrarView.as_view(), name="entrar"),
    path("sair/", views.SairView.as_view(), name="sair"),
    path("novo/", views.CriarView.as_view(), name="criar"),
    path("livro/<int:pk>/", views.DetalheView.as_view(), name="detalhe"),
    path("livro/<int:pk>/editar/", views.EditarView.as_view(), name="editar"),
    path("livro/<int:pk>/apagar/", views.ApagarView.as_view(), name="apagar"),
    path("livro/<int:pk>/urls/novo/", views.url_criar, name="url_criar"),
    path("urls/<int:pk>/apagar/", views.url_apagar, name="url_apagar"),
    path("livro/<int:pk>/notas/nova/", views.nota_criar, name="nota_criar"),
    path("notas/<int:pk>/apagar/", views.nota_apagar, name="nota_apagar"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="service_worker"),
    path("offline/", views.offline, name="offline"),
]
