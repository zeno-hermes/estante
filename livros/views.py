"""Views do site desktop: lista, ficha e CRUD de livros, URLs e notas.

Regra transversal: tudo é filtrado por `utilizador=request.user`. Um livro de
outro utilizador não existe para quem pergunta — devolve 404, não 403. A mesma
regra aplica-se em cadeia: um URL ou uma nota só é acessível através de um
livro do próprio utilizador.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import LinkLivroForm, LivroForm, NotaLivroForm
from .models import LinkLivro, Livro, NotaLivro

PAGINA_TAMANHO = 20

ORDEM_MAPA = {
    "recentes": ("-data_leitura", "-criado_em"),
    "antigos": ("data_leitura", "-criado_em"),
    "titulo": ("titulo",),
    "autor": ("autor", "titulo"),
    "avaliacao": ("-avaliacao", "-data_leitura"),
}

ORDEM_ETIQUETAS = {
    "recentes": "Mais recentes",
    "antigos": "Mais antigos",
    "titulo": "Título (A-Z)",
    "autor": "Autor (A-Z)",
    "avaliacao": "Melhor avaliados",
}


class LivrosDoUtilizadorMixin(LoginRequiredMixin):
    """Base comum: restringe o queryset aos livros do utilizador autenticado."""

    def get_queryset(self):
        return Livro.objects.filter(utilizador=self.request.user)


class LivroListView(LivrosDoUtilizadorMixin, ListView):
    template_name = "livros/lista.html"
    context_object_name = "livros"
    paginate_by = PAGINA_TAMANHO

    def querystring_sem(self, *chaves):
        """Querystring atual sem as chaves indicadas (evita parâmetros duplicados)."""
        parametros = self.request.GET.copy()
        for chave in chaves:
            parametros.pop(chave, None)
        codificada = parametros.urlencode()
        return f"?{codificada}" if codificada else "?"

    def get_queryset(self):
        qs = self.get_base_queryset()
        parametros = self.request.GET
        pesquisa = (parametros.get("q") or "").strip()
        if pesquisa:
            qs = qs.filter(
                Q(titulo__icontains=pesquisa)
                | Q(autor__icontains=pesquisa)
                | Q(notas__texto__icontains=pesquisa)
                | Q(urls__descricao__icontains=pesquisa)
            ).distinct()
        estado = parametros.get("estado")
        if estado in Livro.Estado.values:
            qs = qs.filter(estado=estado)
        avaliacao = parametros.get("avaliacao")
        if avaliacao == "sem":
            qs = qs.filter(avaliacao__isnull=True)
        elif avaliacao and avaliacao.isdigit() and 1 <= int(avaliacao) <= 5:
            qs = qs.filter(avaliacao=int(avaliacao))
        ordem = parametros.get("order") if parametros.get("order") in ORDEM_MAPA else "recentes"
        return qs.order_by(*ORDEM_MAPA[ordem])

    def get_base_queryset(self):
        return (
            Livro.objects.filter(utilizador=self.request.user)
            .annotate(total_notas=Count("notas", distinct=True), total_urls=Count("urls", distinct=True))
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        parametros = self.request.GET
        ordem = parametros.get("order") if parametros.get("order") in ORDEM_MAPA else "recentes"

        contexto["pesquisa"] = (parametros.get("q") or "").strip()
        contexto["estado_ativo"] = parametros.get("estado") or ""
        contexto["avaliacao_ativa"] = parametros.get("avaliacao") or ""
        contexto["ordem_ativa"] = ordem
        contexto["estados"] = Livro.Estado.choices
        contexto["ordens"] = [
            {"chave": chave, "etiqueta": etiqueta, "url": f"{self.querystring_sem('order', 'page')}order={chave}"}
            for chave, etiqueta in ORDEM_ETIQUETAS.items()
        ]
        contexto["querystring"] = self.querystring_sem("page")[1:]

        # Contadores sobre TODOS os livros do utilizador (não apenas a página filtrada).
        todos = Livro.objects.filter(utilizador=self.request.user)
        agregados = todos.aggregate(media=Avg("avaliacao"))
        contexto["resumo"] = {
            "total": todos.count(),
            "lidos": todos.filter(estado=Livro.Estado.LIDO).count(),
            "a_ler": todos.filter(estado=Livro.Estado.A_LER).count(),
            "abandonados": todos.filter(estado=Livro.Estado.ABANDONADO).count(),
            "media": round(agregados["media"], 1) if agregados["media"] else None,
            "este_ano": todos.filter(data_leitura__year=timezone.localdate().year).count(),
        }
        contexto["total_filtrado"] = contexto["paginator"].count if contexto.get("paginator") else 0
        return contexto


class LivroDetalheView(LivrosDoUtilizadorMixin, DetailView):
    template_name = "livros/detalhe.html"
    context_object_name = "livro"

    def get_queryset(self):
        return super().get_queryset().prefetch_related("urls", "notas")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.setdefault("form_url", LinkLivroForm())
        contexto.setdefault("form_nota", NotaLivroForm())
        return contexto


class LivroCriarView(LivrosDoUtilizadorMixin, CreateView):
    model = Livro
    form_class = LivroForm
    template_name = "livros/form.html"
    success_url = reverse_lazy("livros:lista")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["utilizador"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["titulo_pagina"] = "Novo livro"
        contexto["texto_botao"] = "Guardar livro"
        return contexto

    def form_valid(self, form):
        form.instance.utilizador = self.request.user
        messages.success(
            self.request,
            f"«{form.instance.titulo}» guardado na estante. "
            "Abre a ficha do livro para juntar URLs e notas.",
        )
        return super().form_valid(form)


class LivroEditarView(LivrosDoUtilizadorMixin, UpdateView):
    model = Livro
    form_class = LivroForm
    template_name = "livros/form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["utilizador"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["titulo_pagina"] = "Editar livro"
        contexto["texto_botao"] = "Guardar alterações"
        return contexto

    def get_success_url(self):
        messages.success(self.request, "Alterações guardadas.")
        return reverse("livros:detalhe", args=[self.object.pk])


class LivroApagarView(LivrosDoUtilizadorMixin, DeleteView):
    model = Livro
    template_name = "livros/confirmar_apagar.html"
    context_object_name = "livro"
    success_url = reverse_lazy("livros:lista")

    def form_valid(self, form):
        messages.success(self.request, f"«{self.object.titulo}» foi apagado.")
        return super().form_valid(form)


# --------------------------------------------------------------------------
# URLs e notas do livro (relações 1:N)
#
# Os formulários de adicionar vivem na própria ficha do livro e falam com
# estas vistas; se a validação falhar, a ficha é redesenhada com os erros e o
# que o utilizador escreveu, em vez de perder o texto.
# --------------------------------------------------------------------------


def livro_do_utilizador(request, pk):
    """O livro pedido, ou 404 se for de outra pessoa (ou não existir)."""
    return get_object_or_404(Livro, pk=pk, utilizador=request.user)


def ficha_contexto(livro, form_url=None, form_nota=None):
    return {
        "livro": livro,
        "form_url": form_url or LinkLivroForm(),
        "form_nota": form_nota or NotaLivroForm(),
    }


@login_required
@require_POST
def url_criar(request, pk):
    livro = livro_do_utilizador(request, pk)
    form = LinkLivroForm(request.POST)
    if form.is_valid():
        link = form.save(commit=False)
        link.livro = livro
        link.save()
        messages.success(request, "URL adicionado ao livro.")
        return redirect("livros:detalhe", pk=livro.pk)
    return render(request, "livros/detalhe.html", ficha_contexto(livro, form_url=form), status=400)


@login_required
@require_POST
def url_apagar(request, pk):
    link = get_object_or_404(LinkLivro, pk=pk, livro__utilizador=request.user)
    livro = link.livro
    link.delete()
    messages.success(request, "URL removido.")
    return redirect("livros:detalhe", pk=livro.pk)


@login_required
@require_POST
def nota_criar(request, pk):
    livro = livro_do_utilizador(request, pk)
    form = NotaLivroForm(request.POST)
    if form.is_valid():
        nota = form.save(commit=False)
        nota.livro = livro
        nota.save()
        messages.success(request, "Nota adicionada ao livro.")
        return redirect("livros:detalhe", pk=livro.pk)
    return render(request, "livros/detalhe.html", ficha_contexto(livro, form_nota=form), status=400)


@login_required
@require_POST
def nota_apagar(request, pk):
    nota = get_object_or_404(NotaLivro, pk=pk, livro__utilizador=request.user)
    livro = nota.livro
    nota.delete()
    messages.success(request, "Nota removida.")
    return redirect("livros:detalhe", pk=livro.pk)
