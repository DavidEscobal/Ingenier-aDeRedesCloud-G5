# Slice Manager

Proceso FastAPI independiente. Expone salud y capacidades; aún no admite slices,
reserva recursos ni llama a R2. La bandera `persistence` indica persistencia de
slices, todavía pendiente; la persistencia de identidad pertenece a IAM.

`GET /v1/capabilities` requiere Bearer y consulta `/v1/iam/authorize` con
`action=platform.read`. Valida independientemente de Gateway. `/readyz` verifica
IAM; `/healthz` solo el proceso. IAM_URL por defecto http://127.0.0.1:8002.

Las futuras operaciones de slices deberán revalidar acción y recurso con datos
propios, además de permisos, capacidad y reservas. No basta platform.read para
admitir o modificar un slice.

[Guía de ejecución](../../deploy/README.md) · [Políticas IAM](../../deploy/IAM.md)
