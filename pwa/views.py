"""Views da aplicação mobile (PWA) servida em /pwa/.

Mantém-se isolada do site desktop: shell próprio, templates próprios e rotas
próprias, para poder ser instalada no telemóvel e funcionar offline sem que o
site principal dependa do service worker.
"""

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from livros.forms import LinkLivroForm, LivroForm, NotaLivroForm
from livros.models import LinkLivro, Livro, NotaLivro

# Subir esta constante SEMPRE que pwa.css, pwa.js ou os ícones mudarem: os
# estáticos são servidos a partir da cache do service worker e, sem este passo,
# o telemóvel continua a mostrar o que tinha guardado (parece que a alteração
# não pegou).
PWA_CACHE_VERSION = "2026-10-11.3"

PAGINA_TAMANHO = 25

NOME_CURTO = "Estante"
DESCRICAO = "Registo pessoal dos livros lidos."

# O login da app é o do shell mobile. Sem isto, um pedido sem sessão a /pwa/
# cai no LOGIN_URL global (/entrar/, o login do site desktop) e a app instalada
# abre em cadeia: /pwa/ -> login do desktop -> /livros/.
LOGIN_PWA = reverse_lazy("pwa:entrar")


# --------------------------------------------------------------------------
# Autenticação
# --------------------------------------------------------------------------


class EntrarView(auth_views.LoginView):
    """Login dentro do shell mobile (não salta para o login do site desktop)."""

    template_name = "pwa/entrar.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        return self.get_redirect_url() or reverse("pwa:lista")


class SairView(auth_views.LogoutView):
    next_page = reverse_lazy("pwa:entrar")


# --------------------------------------------------------------------------
# Livros
# --------------------------------------------------------------------------


def livro_do_utilizador(request, pk):
    """O livro, ou 404 se for de outra pessoa (mesma regra do site desktop)."""
    return get_object_or_404(Livro, pk=pk, utilizador=request.user)


class LivrosDoUtilizadorMixin(LoginRequiredMixin):
    login_url = LOGIN_PWA
    redirect_field_name = "next"

    def get_queryset(self):
        return Livro.objects.filter(utilizador=self.request.user)


class ListaView(LivrosDoUtilizadorMixin, ListView):
    template_name = "pwa/lista.html"
    context_object_name = "livros"
    paginate_by = PAGINA_TAMANHO

    def get_queryset(self):
        qs = Livro.objects.filter(utilizador=self.request.user).annotate(
            total_notas=Count("notas", distinct=True), total_urls=Count("urls", distinct=True)
        )
        pesquisa = (self.request.GET.get("q") or "").strip()
        if pesquisa:
            qs = qs.filter(
                Q(titulo__icontains=pesquisa)
                | Q(autor__icontains=pesquisa)
                | Q(notas__texto__icontains=pesquisa)
            ).distinct()
        estado = self.request.GET.get("estado")
        if estado in Livro.Estado.values:
            qs = qs.filter(estado=estado)
        return qs.order_by("-data_leitura", "-criado_em")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        parametros = self.request.GET
        contexto["pesquisa"] = (parametros.get("q") or "").strip()
        contexto["estado_ativo"] = parametros.get("estado") or ""
        contexto["atualizado_em"] = timezone.localtime()
        contexto["total"] = contexto["paginator"].count if contexto.get("paginator") else 0

        # Links de filtro construídos sem acumular o parâmetro (evita ?estado=a&estado=b)
        base = parametros.copy()
        base.pop("page", None)
        base.pop("estado", None)
        contexto["filtros_url"] = []
        for valor, etiqueta in [("", "Todos")] + list(Livro.Estado.choices):
            copia = base.copy()
            if valor:
                copia["estado"] = valor
            codificada = copia.urlencode()
            contexto["filtros_url"].append(
                {"valor": valor, "etiqueta": etiqueta, "url": f"?{codificada}" if codificada else "?"}
            )

        pagina = parametros.copy()
        pagina.pop("page", None)
        contexto["querystring"] = pagina.urlencode()
        return contexto


class DetalheView(LivrosDoUtilizadorMixin, DetailView):
    template_name = "pwa/detalhe.html"
    context_object_name = "livro"

    def get_queryset(self):
        return super().get_queryset().prefetch_related("urls", "notas")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.setdefault("form_url", LinkLivroForm())
        contexto.setdefault("form_nota", NotaLivroForm())
        return contexto


class CriarView(LivrosDoUtilizadorMixin, CreateView):
    model = Livro
    form_class = LivroForm
    template_name = "pwa/form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["utilizador"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["titulo_pagina"] = "Novo livro"
        contexto["texto_botao"] = "Guardar"
        return contexto

    def form_valid(self, form):
        form.instance.utilizador = self.request.user
        messages.success(self.request, f"«{form.instance.titulo}» guardado.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("pwa:detalhe", args=[self.object.pk])


class EditarView(LivrosDoUtilizadorMixin, UpdateView):
    model = Livro
    form_class = LivroForm
    template_name = "pwa/form.html"

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
        return reverse("pwa:detalhe", args=[self.object.pk])


class ApagarView(LivrosDoUtilizadorMixin, DeleteView):
    model = Livro
    template_name = "pwa/confirmar_apagar.html"
    context_object_name = "livro"

    def form_valid(self, form):
        messages.success(self.request, f"«{self.object.titulo}» foi apagado.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("pwa:lista")


# --------------------------------------------------------------------------
# URLs e notas (1:N) — mesmos formulários do desktop, respostas em mobile
# --------------------------------------------------------------------------


def ficha_contexto(livro, form_url=None, form_nota=None):
    return {
        "livro": livro,
        "form_url": form_url or LinkLivroForm(),
        "form_nota": form_nota or NotaLivroForm(),
    }


@login_required(login_url=LOGIN_PWA)
@require_POST
def url_criar(request, pk):
    livro = livro_do_utilizador(request, pk)
    form = LinkLivroForm(request.POST)
    if form.is_valid():
        link = form.save(commit=False)
        link.livro = livro
        link.save()
        messages.success(request, "URL adicionado.")
        return redirect("pwa:detalhe", pk=livro.pk)
    return render(request, "pwa/detalhe.html", ficha_contexto(livro, form_url=form), status=400)


@login_required(login_url=LOGIN_PWA)
@require_POST
def url_apagar(request, pk):
    link = get_object_or_404(LinkLivro, pk=pk, livro__utilizador=request.user)
    livro = link.livro
    link.delete()
    messages.success(request, "URL removido.")
    return redirect("pwa:detalhe", pk=livro.pk)


@login_required(login_url=LOGIN_PWA)
@require_POST
def nota_criar(request, pk):
    livro = livro_do_utilizador(request, pk)
    form = NotaLivroForm(request.POST)
    if form.is_valid():
        nota = form.save(commit=False)
        nota.livro = livro
        nota.save()
        messages.success(request, "Nota adicionada.")
        return redirect("pwa:detalhe", pk=livro.pk)
    return render(request, "pwa/detalhe.html", ficha_contexto(livro, form_nota=form), status=400)


@login_required(login_url=LOGIN_PWA)
@require_POST
def nota_apagar(request, pk):
    nota = get_object_or_404(NotaLivro, pk=pk, livro__utilizador=request.user)
    livro = nota.livro
    nota.delete()
    messages.success(request, "Nota removida.")
    return redirect("pwa:detalhe", pk=livro.pk)


# --------------------------------------------------------------------------
# Manifest e service worker
#
# Servidos por views (e não como ficheiros em static/) porque ambos precisam de
# content-type e cabeçalhos próprios: um .webmanifest em static/ sai com
# content-type errado e o browser ignora-o; e o service worker só pode
# controlar /pwa/ se for servido daí com Service-Worker-Allowed.
# São públicos de propósito: o browser pede-os antes de haver sessão.
# --------------------------------------------------------------------------


def manifest(request):
    resposta = render(
        request,
        "pwa/manifest.webmanifest",
        {
            "nome": NOME_CURTO,
            "nome_curto": NOME_CURTO,
            "descricao": DESCRICAO,
        },
        content_type="application/manifest+json",
    )
    resposta["Content-Type"] = "application/manifest+json"
    resposta["Cache-Control"] = "no-cache"
    return resposta


def service_worker(request):
    resposta = render(
        request,
        "pwa/sw.js",
        {"cache_version": PWA_CACHE_VERSION},
        content_type="application/javascript",
    )
    resposta["Content-Type"] = "application/javascript"
    resposta["Service-Worker-Allowed"] = "/pwa/"
    resposta["Cache-Control"] = "no-cache"
    return resposta


def offline(request):
    """Página de recurso quando não há rede nem nada em cache."""
    return render(request, "pwa/offline.html")
