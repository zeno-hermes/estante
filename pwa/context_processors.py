"""Valores do PWA disponíveis em todos os templates."""

from .views import PWA_CACHE_VERSION


def versao_offline(request):
    """Versão da cache, usada pelo shell mobile para limpar dados ao sair."""
    return {"pwa_cache_version": PWA_CACHE_VERSION}
