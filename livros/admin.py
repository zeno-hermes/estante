from django.contrib import admin

from .models import LinkLivro, Livro, NotaLivro


class LinkLivroInline(admin.TabularInline):
    model = LinkLivro
    extra = 0


class NotaLivroInline(admin.TabularInline):
    model = NotaLivro
    extra = 0


@admin.register(Livro)
class LivroAdmin(admin.ModelAdmin):
    list_display = ("titulo", "autor", "data_leitura", "avaliacao", "estado", "utilizador")
    list_filter = ("estado", "avaliacao", "utilizador")
    search_fields = ("titulo", "autor")
    date_hierarchy = "data_leitura"
    inlines = [LinkLivroInline, NotaLivroInline]
