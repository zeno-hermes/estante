"""Cria (ou atualiza) a conta do utilizador no Estante.

A password é pedida de forma oculta e nunca é escrita no histórico do shell
nem em qualquer ficheiro.

    .venv/bin/python scripts/create_admin.py                 # pede a password
    .venv/bin/python scripts/create_admin.py --utilizador eu # outro nome

Idempotente: se o utilizador já existir, atualiza a password.
"""

import argparse
import getpass
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "estante.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.password_validation import validate_password  # noqa: E402
from django.core.exceptions import ValidationError  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Cria ou atualiza a conta do Estante.")
    parser.add_argument("--utilizador", default="dinis", help="nome de utilizador (default: dinis)")
    parser.add_argument("--email", default="felixdinis@gmail.com", help="email associado")
    args = parser.parse_args()

    Utilizador = get_user_model()
    utilizador, criado = Utilizador.objects.get_or_create(
        username=args.utilizador, defaults={"email": args.email}
    )
    if not criado and args.email and utilizador.email != args.email:
        utilizador.email = args.email

    for tentativa in range(3):
        password = getpass.getpass(f"Password para '{args.utilizador}': ")
        confirmacao = getpass.getpass("Repete a password: ")
        if password != confirmacao:
            print("As passwords não coincidem. Tenta outra vez.")
            continue
        try:
            validate_password(password, utilizador)
        except ValidationError as erro:
            for mensagem in erro.messages:
                print(f"  - {mensagem}")
            continue
        break
    else:
        print("Não foi possível definir a password. Nada foi alterado.")
        return 1

    utilizador.set_password(password)
    utilizador.is_staff = True
    utilizador.is_superuser = True
    utilizador.save()
    print(f"{'Conta criada' if criado else 'Password atualizada'}: {utilizador.username}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
