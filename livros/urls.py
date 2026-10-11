from django.urls import path

from . import views

app_name = "livros"

urlpatterns = [
    path("", views.LivroListView.as_view(), name="lista"),
    path("novo/", views.LivroCriarView.as_view(), name="criar"),
    path("<int:pk>/", views.LivroDetalheView.as_view(), name="detalhe"),
    path("<int:pk>/editar/", views.LivroEditarView.as_view(), name="editar"),
    path("<int:pk>/apagar/", views.LivroApagarView.as_view(), name="apagar"),
]
