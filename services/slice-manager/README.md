# Slice Manager

Proceso FastAPI independiente: **intención del usuario y autorización**. No ejecuta despliegues: los
delega en el `platform-manager` (D-12). Dueño de la relación slice → dueño/curso (SQLite en `SLICE_DB_PATH`).

## Rutas (todas exigen Bearer de IAM; el gateway las expone igual)

| Ruta | Autorización | Acción |
|---|---|---|
| `POST /v1/slices` + `Idempotency-Key` | IAM `slice.create` sobre `course_id` | llama al platform-manager con el token de servicio; guarda dueño y curso |
| `GET /v1/slices` | usuario activo | admin ve todos; el resto, solo los propios. Estado real tomado del platform-manager |
| `GET /v1/slices/{id}` | dueño o admin (si no, **404**) | estado y últimos eventos |
| `DELETE /v1/slices/{id}` + `Idempotency-Key` | dueño o admin (si no, **404**) | encola el borrado en el platform-manager |
| `GET /v1/capabilities` | IAM `platform.read` | `slice_lifecycle` = platform-manager configurado |

- El platform-manager recibe **solo** el token de servicio (`PLATFORM_TOKEN_FILE`), nunca el del usuario.
- La `Idempotency-Key` se combina con el id del usuario (SHA-256) antes de enviarla: dos usuarios con la misma
  clave no colisionan; el reintento del mismo usuario devuelve el mismo slice.
- Errores de validación del platform-manager → 422 `invalid_spec: <motivo>`; caída → 503; tiempo → 504.
- Sin `PLATFORM_MANAGER_URL` el servicio arranca igual y las rutas de slices responden 503 `platform_unavailable`.

## Variables

`IAM_URL`, `PLATFORM_MANAGER_URL`, `PLATFORM_TOKEN_FILE` (token ≥ 32 caracteres), `SLICE_DB_PATH`,
`PLATFORM_TIMEOUT_SECONDS` (20).

## Pendiente

- Registrar cada slice como recurso en IAM y asignarlo a alumnos (`slice.read`, `vm.console`): requiere una
  identidad de servicio en IAM, que hoy solo admite roles humanos.
- Aplicar `professor_can_modify` y las cuotas del curso antes de crear o borrar.
- Consola por VM y edición de slices a través del gateway.

[Guía de ejecución](../../deploy/README.md) · [Políticas IAM](../../deploy/IAM.md)
