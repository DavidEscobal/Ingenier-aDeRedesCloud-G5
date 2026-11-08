"""Local initial administrator bootstrap; no passwords in arguments or logs."""
import argparse
import getpass
import os
import secrets

from pydantic import ValidationError
from .models import UserCreate
from .security import PASSWORDS
from .settings import Settings
from .store import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["init"])
    parser.parse_args()
    settings = Settings.load()
    store = Store(settings.database)
    store.initialize()
    with store.transaction() as db:
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            parser.error("IAM ya inicializado; no se modificó ninguna cuenta")
    username = input("Usuario administrador: ").strip()
    password = getpass.getpass("Contraseña (15 a 128 caracteres): ")
    if password != getpass.getpass("Repetir contraseña: "):
        parser.error("Las contraseñas no coinciden")
    try:
        user = UserCreate(username=username, password=password, display_name="Administrador G5", role="admin")
    except ValidationError:
        parser.error("Usuario inválido o contraseña fuera de longitud 15-128; valores omitidos")
    settings.secret_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(settings.secret_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        settings.read_secret()
    else:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(secrets.token_hex(32))
    store.bootstrap(user, PASSWORDS.hash(password))
    print("IAM inicializado. Credenciales y clave no se imprimen ni se guardan en Git.")


if __name__ == "__main__":
    main()
