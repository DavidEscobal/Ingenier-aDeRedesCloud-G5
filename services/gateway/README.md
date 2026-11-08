# API Gateway

Proceso FastAPI independiente que se comunica por HTTP con IAM y Slice Manager.
No importa código de negocio de otros servicios ni tiene la clave de firma JWT.

- `/healthz`: proceso vivo; `/readyz`: disponibilidad de dependencias.
- `/v1/auth/*`: login, identidad, logout y contraseña mediante IAM.
- `/v1/iam/*`: rutas explícitas de administración y consulta de permisos;
  IAM valida sesión y rol en cada petición.
- `/v1/platform/capabilities`: exige autorización IAM y propaga únicamente el
  token a Slice Manager, que vuelve a comprobarlo.

IAM_URL (http://127.0.0.1:8002), SLICE_MANAGER_URL (http://127.0.0.1:8001),
UPSTREAM_TIMEOUT_SECONDS (3). Swagger usa HTTP Bearer: obtener token mediante
login JSON y pegarlo en Authorize. No se confía en X-Role ni X-User-Id.
Los DTO de iam_models.py representan la frontera HTTP; los contratos OpenAPI y
las pruebas verifican compatibilidad, sin imports entre servicios.

[Guía de ejecución](../../deploy/README.md) · [Pruebas IAM](../../deploy/IAM.md)
