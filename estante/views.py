"""Views transversais ao projeto (fora do domínio dos livros)."""

from django.contrib.auth.decorators import login_required
from django.db import connection
from django.db.utils import DatabaseError
from django.http import JsonResponse
from django.shortcuts import redirect


@login_required
def home(request):
    """A raiz leva sempre à lista de livros (quem não está autenticado é
    encaminhado para o login pelo próprio @login_required)."""
    return redirect("livros:lista")


def saude(request):
    """Healthcheck público para o deploy e para o monitor de serviço."""
    estado_bd = "ok"
    codigo = 200
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        estado_bd = "erro"
        codigo = 503

    return JsonResponse(
        {"status": "ok" if codigo == 200 else "erro", "bd": estado_bd}, status=codigo
    )
