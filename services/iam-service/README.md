# IAM Service

Identidad, sesiones JWT revocables, RBAC y relaciones académicas del HLD G5.
Paquete independiente `g5_iam`. No importa código de Gateway, Slice Manager o R2.

- `settings.py`: configuración y lectura de clave privada del servicio.
- `models.py`: contratos de entrada/salida.
- `store.py`: esquema SQLite versionado y transacciones.
- `security.py`: hashing, sesión, firma y validación JWT.
- `policy.py`: reglas por rol, curso, profesor a cargo y asignación.
- `main.py`: endpoints y auditoría.
- `cli.py`: bootstrap interactivo del primer administrador.

Configuración: IAM_DB_PATH, IAM_SECRET_FILE e IAM_TOKEN_TTL_SECONDS (900 por defecto).
La API requiere inicialización; no hay cuenta ni clave de firma por defecto.

[Ejecutar la APP](../../deploy/README.md) · [Políticas y pruebas](../../deploy/IAM.md)
