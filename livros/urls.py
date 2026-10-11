from django.urls import path

from . import views

app_name = "livros"

urlpatterns = [
    path("", views.LivroListView.as_view(), name="lista"),
    path("novo/", views.LivroCriarView.as_view(), name="criar"),
    path("<int:pk>/", views.LivroDetalheView.as_view(), name="detalhe"),
    path("<int:pk>/editar/", views.LivroEditarView.as_view(), name="editar"),
    path("<int:pk>/apagar/", views.LivroApagarView.as_view(), name="apagar"),
    # URLs do livro (1:N)
    path("<int:pk>/urls/novo/", views.url_criar, name="url_criar"),
    path("urls/<int:pk>/apagar/", views.url_apagar, name="url_apagar"),
    # Notas do livro (1:N)
    path("<int:pk>/notas/nova/", views.nota_criar, name="nota_criar"),
    path("notas/<int:pk>/apagar/", views.nota_apagar, name="nota_apagar"),
]
