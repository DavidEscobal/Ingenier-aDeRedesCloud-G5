# Contratos HTTP APP — v0.2.0

`http/gateway.openapi.json`, `http/iam.openapi.json` y
`http/slice-manager.openapi.json` son contratos generados desde las APIs.
El contrato R2 en `api/openapi.json` permanece independiente.

Login JSON en `/v1/auth/login` devuelve un JWT. Las rutas privadas requieren
`Authorization: Bearer <token>`. Swagger usa el esquema HTTPBearer.
La salud `/healthz` y `/readyz`, el contrato y Swagger son públicos.
`GET /v1/platform/capabilities` del Gateway y `/v1/capabilities` del Slice Manager
ahora requieren autorización. IAM se consulta en ambos puntos.

`POST /v1/iam/authorize` recibe acción y referencia de curso/recurso; nunca rol ni
identidad elegidos por el solicitante. Devuelve decisión, no ejecuta la operación.
IAM resuelve relación y pertenencia desde su estado persistido. Campos desconocidos
se rechazan. La matriz está en [deploy/IAM.md](../deploy/IAM.md).

Respuestas: 401 sesión inválida/expirada/revocada; 403 sin permiso; 404 ausente;
409 conflicto; 422 entrada inválida; 429 límite de login; 502 respuesta upstream
inválida; 503 dependencia no disponible; 504 timeout del Gateway. Los errores
no devuelven cuerpos arbitrarios del upstream ni valores de contraseñas.

No hay todavía contrato de creación de slices, comandos/resultados de cola,
credenciales de servicio ni emisión de sesiones de consola. Los recursos de IAM
son metadatos de autorización administrados explícitamente, no VMs desplegadas.

Regenerar con el entorno de desarrollo instalado:

```powershell
.\.venv\Scripts\python.exe scripts/export_app_contracts.py
.\.venv\Scripts\python.exe -m unittest discover -s tests/app -v
```
