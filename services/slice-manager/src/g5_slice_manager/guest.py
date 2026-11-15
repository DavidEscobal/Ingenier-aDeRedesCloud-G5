"""Credenciales de acceso a las VMs Ubuntu del slice (Ex2: consola VNC y SSH entre VMs).

La web envía usuario, contraseña y llaves SSH opcionales. Aquí la contraseña se convierte en un hash SHA-512 crypt
(`$6$`, el formato de /etc/shadow que entiende cloud-init) y solo ese hash viaja al platform-manager; el texto plano
no se guarda ni se registra. Implementación pura en Python (el módulo `crypt` desaparece en 3.13).
"""
import hashlib
import hmac
import re

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

ALPHABET = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
SSH_KEY = re.compile(r"^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp(?:256|384|521)) [A-Za-z0-9+/]+={0,3}(?: |$)")
RESERVED = {"root", "daemon", "bin", "sys", "nobody"}
ORDER = [(0, 21, 42), (22, 43, 1), (44, 2, 23), (3, 24, 45), (25, 46, 4), (47, 5, 26), (6, 27, 48), (28, 49, 7),
         (50, 8, 29), (9, 30, 51), (31, 52, 10), (53, 11, 32), (12, 33, 54), (34, 55, 13), (56, 14, 35),
         (15, 36, 57), (37, 58, 16), (59, 17, 38), (18, 39, 60), (40, 61, 19), (62, 20, 41)]


class GuestAccess(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,30}$", description="Usuario que se crea en cada VM Ubuntu")
    password: SecretStr = Field(min_length=8, max_length=72, description="Contraseña de consola; no se guarda")
    ssh_authorized_keys: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("username")
    @classmethod
    def not_reserved(cls, value):
        if value in RESERVED:
            raise ValueError("usuario reservado")
        return value

    @field_validator("ssh_authorized_keys")
    @classmethod
    def public_keys(cls, keys):
        keys = [k.strip() for k in keys if k.strip()]
        for key in keys:
            if len(key) >= 8192 or "\n" in key or not SSH_KEY.match(key):
                raise ValueError("clave SSH pública inválida")
        return keys

    @field_validator("password")
    @classmethod
    def printable(cls, value):
        if any(ord(c) < 32 for c in value.get_secret_value()):
            raise ValueError("la contraseña no puede tener caracteres de control")
        return value


def sha512_crypt(password: str, salt: str, rounds: int = 5000) -> str:
    """SHA-512 crypt de Drepper (glibc `$6$`), con las rondas por defecto (5000)."""
    p, s = password.encode(), salt[:16].encode()
    b = hashlib.sha512(p + s + p).digest()
    a = hashlib.sha512(p + s)
    n = len(p)
    while n > 64:
        a.update(b)
        n -= 64
    a.update(b[:n])
    i = len(p)
    while i:
        a.update(b if i & 1 else p)
        i >>= 1
    a = a.digest()
    dp = hashlib.sha512(p * len(p)).digest()
    p_seq = (dp * (len(p) // 64 + 1))[:len(p)]
    s_seq = hashlib.sha512(s * (16 + a[0])).digest()[:len(s)]
    c = a
    for r in range(rounds):
        h = hashlib.sha512(p_seq if r & 1 else c)
        if r % 3:
            h.update(s_seq)
        if r % 7:
            h.update(p_seq)
        h.update(c if r & 1 else p_seq)
        c = h.digest()

    def b64(b2, b1, b0, count):
        w = (b2 << 16) | (b1 << 8) | b0
        out = []
        for _ in range(count):
            out.append(ALPHABET[w & 0x3F])
            w >>= 6
        return "".join(out)

    encoded = "".join(b64(c[x], c[y], c[z], 4) for x, y, z in ORDER) + b64(0, 0, c[63], 2)
    return "$6$%s$%s" % (salt[:16], encoded)


def salt_for(seed: str) -> str:
    """Sal estable por petición: un reintento con la misma Idempotency-Key produce la misma especificación."""
    digest = hmac.new(b"g5-guest-salt", seed.encode(), hashlib.sha256).digest()
    return "".join(ALPHABET[x & 0x3F] for x in digest[:16])


def with_guest(spec: dict, access: GuestAccess | None, seed: str) -> dict:
    """Devuelve la especificación con el bloque `guest` del slice (solo el hash); sin credenciales, intacta."""
    if access is None:
        return spec
    password_hash = sha512_crypt(access.password.get_secret_value(), salt_for(seed))
    return dict(spec, guest={"username": access.username, "password_hash": password_hash,
                             "ssh_authorized_keys": list(access.ssh_authorized_keys)})
