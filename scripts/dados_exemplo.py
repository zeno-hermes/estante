"""Dados de exemplo para demonstração e verificação visual.

Cria (ou reinicia) uma conta descartável com livros variados, para ver a
interface com dados reais sem mexer na conta do dono.

    .venv/bin/python scripts/dados_exemplo.py
    .venv/bin/python scripts/dados_exemplo.py --utilizador revisao --limpar

A password da conta de exemplo é aleatória e nunca é impressa: serve apenas
para verificação interna, não para uso humano.
"""

import argparse
import os
import secrets
import sys
from datetime import date, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "estante.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

from livros.models import LinkLivro, Livro, NotaLivro  # noqa: E402

EXEMPLOS = [
    {
        "titulo": "Ensaio sobre a Cegueira",
        "autor": "José Saramago",
        "data_leitura": date(2026, 8, 14),
        "avaliacao": 5,
        "estado": "lido",
        "urls": [("https://pt.wikipedia.org/wiki/Ensaio_sobre_a_Cegueira", "Wikipedia")],
        "notas": ["A cegueira branca como metáfora da indiferença. Brutal do início ao fim."],
    },
    {
        "titulo": "Dune",
        "autor": "Frank Herbert",
        "data_leitura": date(2026, 6, 2),
        "avaliacao": 4,
        "estado": "lido",
        "urls": [("https://www.goodreads.com/book/show/44767458-dune", "Goodreads")],
        "notas": ["Ecologia, política e religião entrelaçadas. As últimas 100 páginas valem o livro."],
    },
    {
        "titulo": "O Nome da Rosa",
        "autor": "Umberto Eco",
        "data_leitura": date(2026, 3, 21),
        "avaliacao": 5,
        "estado": "lido",
        "urls": [],
        "notas": [
            "Um romance policial dentro de uma biblioteca medieval.",
            "Vale a pena ler com um bloco de notas ao lado, para as citações em latim.",
        ],
    },
    {
        "titulo": "Sapiens",
        "autor": "Yuval Noah Harari",
        "data_leitura": date(2025, 11, 9),
        "avaliacao": 3,
        "estado": "lido",
        "urls": [],
        "notas": ["Bom panorama, mas repetitivo a partir de metade."],
    },
    {
        "titulo": "Cem Anos de Solidão",
        "autor": "Gabriel García Márquez",
        "data_leitura": date(2025, 7, 30),
        "avaliacao": 5,
        "estado": "lido",
        "urls": [("https://pt.wikipedia.org/wiki/Cem_Anos_de_Solid%C3%A3o", "Wikipedia")],
        "notas": ["Vale uma segunda leitura com uma árvore genealógica à mão."],
    },
    {
        "titulo": "A Insustentável Leveza do Ser",
        "autor": "Milan Kundera",
        "data_leitura": date(2025, 2, 17),
        "avaliacao": 2,
        "estado": "abandonado",
        "urls": [],
        "notas": ["Abandonado a meio: não me agarrou."],
    },
    {
        "titulo": "O Problema dos Três Corpos",
        "autor": "Liu Cixin",
        "data_leitura": None,
        "avaliacao": None,
        "estado": "a_ler",
        "urls": [],
        "notas": [],
    },
    {
        "titulo": "História de Portugal",
        "autor": "Rui Ramos",
        "data_leitura": date(2026, 1, 5),
        "avaliacao": 4,
        "estado": "lido",
        "urls": [],
        "notas": [],
    },
]


def main():
    parser = argparse.ArgumentParser(description="Cria dados de exemplo para a Estante.")
    parser.add_argument("--utilizador", default="revisao", help="conta descartável (default: revisao)")
    parser.add_argument("--limpar", action="store_true", help="apaga os livros desta conta antes de recriar")
    args = parser.parse_args()

    Utilizador = get_user_model()
    utilizador, _ = Utilizador.objects.get_or_create(
        username=args.utilizador, defaults={"email": ""}
    )
    if not utilizador.has_usable_password():
        utilizador.set_password(secrets.token_urlsafe(32))
        utilizador.save(update_fields=["password"])

    if args.limpar:
        apagados, _ = Livro.objects.filter(utilizador=utilizador).delete()
        print(f"Removidos {apagados} registos da conta {utilizador.username}.")

    criados = 0
    for exemplo in EXEMPLOS:
        dados = {chave: valor for chave, valor in exemplo.items() if chave not in {"urls", "notas"}}
        livro, novo = Livro.objects.get_or_create(utilizador=utilizador, **dados)
        if not novo:
            continue
        criados += 1
        for url, descricao in exemplo["urls"]:
            LinkLivro.objects.create(livro=livro, url=url, descricao=descricao)
        for texto in exemplo["notas"]:
            NotaLivro.objects.create(livro=livro, texto=texto)

    total = Livro.objects.filter(utilizador=utilizador).count()
    print(f"Conta '{utilizador.username}': {criados} livros criados, {total} no total.")
    print(f"Datas de referência: hoje é {date.today()} (ano {date.today().year}).")
    print(f"Janela de exemplo: {date.today() - timedelta(days=400)} a {date.today()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
