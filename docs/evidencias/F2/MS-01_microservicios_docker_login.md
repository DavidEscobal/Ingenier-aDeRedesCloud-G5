# MS-01 — Microservicios en Docker: salud, rechazo sin credenciales, login y revocación

- **Fecha:** 2026-11-10 · **Host:** app server (`10.20.11.248`), Docker 28.1.1, Compose v2.35.1
- **Código:** `~/g5-app` = rama `fase2` (commit `5dbc612` + `scripts/smoke_gateway_login.py`)
- **Despliegue:** `docker compose -f deploy/compose.yaml up -d` (servicios `iam`, `slice-manager`, `gateway`;
  `platform-manager` en perfil aparte, no levantado). IAM inicializado por el usuario con `g5_iam.cli init`.
- **Tipo:** [REAL] ejecutado en el app server. Sin contraseñas ni tokens en este registro.

## 1. Contenedores

| Servicio | Estado | Puertos |
|---|---|---|
| gateway | Up (healthy) | `127.0.0.1:8000->8000/tcp` |
| iam | Up (healthy) | `8000/tcp` (solo red interna `control`) |
| slice-manager | Up (healthy) | `8000/tcp` (solo red interna `control`) |

`docker port` de iam y slice-manager: vacío (no publicados). `ss -ltn`: solo `127.0.0.1:8000`.

## 2. Pruebas sin credenciales (curl al gateway, ejecutadas por Claude)

| Petición | HTTP | Respuesta |
|---|---|---|
| `GET /healthz` | 200 | `{"service":"gateway","status":"ok"}` |
| `GET /readyz` | 200 | dependencias `iam: ok`, `slice-manager: ok` |
| `GET /v1/platform/capabilities` sin token | 401 | `invalid_credentials` |
| `GET /v1/platform/capabilities` token falso | 401 | `invalid_credentials` |
| `GET /v1/iam/users` sin token | 401 | `invalid_credentials` |
| `POST /v1/auth/login` contraseña incorrecta | 401 | `invalid_credentials` |
| `POST /v1/auth/login` usuario inexistente | 401 | `invalid_credentials` (no revela si el usuario existe) |

## 3. Login y revocación (`scripts/smoke_gateway_login.py`, ejecutado por el usuario)

```
OK   1. login                                         HTTP 200 (esperado 200) expira en 900s
OK   2. /v1/auth/me                                   HTTP 200 (esperado 200) usuario=admin123 rol=admin
OK   3. capacidades (gateway -> slice-manager -> IAM) HTTP 200 (esperado 200) servicio=slice-manager fase=bootstrap
OK   4. listar usuarios (requiere admin)              HTTP 200 (esperado 200) usuarios=1
OK   5. logout                                        HTTP 200 (esperado 200)
OK   6. mismo token tras logout (revocado)            HTTP 401 (esperado 401)
OK   7. capacidades con token revocado                HTTP 401 (esperado 401)

Resultado: 7/7 OK
```

## Conclusión y límites

Los tres microservicios corren en contenedores separados, se comunican por la red interna y aplican
autenticación (JWT de 15 min), autorización por rol y revocación inmediata de sesión. **No cubre** creación de
slices: slice-manager está en fase `bootstrap` y aún no llama al platform-manager (paso siguiente).
