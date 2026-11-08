import secrets
from pathlib import Path
from g5_iam.models import UserCreate
from g5_iam.security import PASSWORDS
from g5_iam.store import Store


def initialize(directory):
    path = Path(directory)
    secret = secrets.token_hex(32)
    key = path / "jwt.key"
    key.write_text(secret, encoding="utf-8")
    database = path / "iam.db"
    store = Store(database)
    store.initialize()
    password = secrets.token_urlsafe(24)
    store.bootstrap(UserCreate(username="admin", password=password, display_name="Test Admin", role="admin"),
                    PASSWORDS.hash(password))
    return {"IAM_DB_PATH": str(database), "IAM_SECRET_FILE": str(key)}, password, secret
