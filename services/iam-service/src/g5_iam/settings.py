import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database: Path
    secret_file: Path
    issuer: str = "g5-iam"
    audience: str = "g5-app"
    ttl_seconds: int = 900
    service_token_file: Path | None = None

    @classmethod
    def load(cls):
        ttl = int(os.getenv("IAM_TOKEN_TTL_SECONDS", "900"))
        if not 60 <= ttl <= 3600:
            raise ValueError("IAM_TOKEN_TTL_SECONDS must be between 60 and 3600")
        service = os.getenv("IAM_SERVICE_TOKEN_FILE")
        return cls(Path(os.getenv("IAM_DB_PATH", "state/iam/iam.db")),
                   Path(os.getenv("IAM_SECRET_FILE", "state/iam/jwt.key")),
                   ttl_seconds=ttl, service_token_file=Path(service) if service else None)

    def read_secret(self):
        secret = self.secret_file.read_text(encoding="utf-8").strip()
        if len(secret) < 64:
            raise ValueError("Initialize IAM with a random secret of at least 64 characters")
        return secret

    def service_token_hash(self):
        """SHA-256 del token de servicio del Slice Manager (D-14); None si no está configurado."""
        if not self.service_token_file:
            return None
        token = self.service_token_file.read_text(encoding="utf-8").strip()
        if len(token) < 32:
            raise ValueError("IAM_SERVICE_TOKEN_FILE must contain a service token of at least 32 characters")
        import hashlib
        return hashlib.sha256(token.encode()).hexdigest()
