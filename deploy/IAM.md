# IAM G5: alcance, políticas y pruebas manuales

## Correspondencia con el HLD

Basado en G5 Documentación EX1 pp. 8–9 (roles), 15 (datos por dominio) y 34–36
(flujo F1); presentación pp. 4, 6 y 7. IAM almacena identidad y relación académica;
Gateway delega autenticación/autorización; el destino revalida el acceso.

Implementación inicial: FastAPI + pwdlib/Argon2id + PyJWT, SQLite de uso exclusivo
IAM. Keycloak era un candidato y no se ha instalado. Se puede incorporar OIDC
posteriormente conservando las políticas académicas; no se promete que esa
migración sea automática. SQLite es una decisión provisional para una instancia
del laboratorio; PostgreSQL y migraciones futuras requieren evaluación explícita.
El esquema inicial está versionado con `PRAGMA user_version=1` y se rechazan
versiones desconocidas. La BD de R2 nunca se abre ni modifica desde IAM.

## Matriz de permisos implementada

| Acción | Administrador | Profesor | Alumno |
|---|---|---|---|
| Gestionar cuentas, roles, cursos, membresías y cuotas | Global | No | No |
| Consultar identidad propia / cambiar contraseña propia | Sí | Sí | Sí |
| Evaluar creación de slice / escritura de plantilla | Curso existente | Solo curso vigente | No |
| Consultar estado/métricas de slice | Recurso registrado | Curso y profesor a cargo | Curso vigente y slice asignado |
| Editar, borrar, iniciar o detener slice | Recurso registrado | A cargo y política del curso habilitada | No |
| Asignar alumno a slice/VM | Sí | Slice a cargo y alumno activo del curso | No |
| Evaluar acceso a consola VM | VM registrada | Curso y profesor a cargo | Asignación vigente del slice y de esa VM |
| Evaluar gestión de imágenes/infraestructura | Sí | No | No |
| Consultar auditoría | Sí | No | No |

Las acciones sobre slices, plantillas, imágenes e infraestructura son **decisiones
de autorización** para integrar más adelante; no ejecutan esas operaciones.
Las cuotas son límites declarados (0 significa sin capacidad asignada), no reservas
ni prueba de disponibilidad. El listado de cursos/recursos filtra por usuario.
La política conservadora adoptada para "slices a cargo" exige coincidencia con
`professor_id`, no basta ser otro profesor del mismo curso. Los permisos de
modificación se fijan al crear el curso con `professor_can_modify`.

## Flujo manual: admin → profesor → alumno

Primero iniciar los tres servicios y entrar como administrador en Swagger según
[README](README.md). Usar contraseñas propias de 15–128 caracteres; no se suministran
contraseñas por defecto. Los ejemplos siguientes usan marcadores a sustituir.

1. `POST /v1/iam/users`: crear un profesor y dos alumnos. Guardar los UUID de las
   respuestas. Ejemplo (sustituir la contraseña):

```json
{
  "username": "profesor1",
  "display_name": "Profesor de prueba",
  "password": "<elige-una-contraseña-propia>",
  "role": "professor"
}
```

Para alumnos, usar `role: "student"` y otros nombres únicos.

2. `POST /v1/iam/courses`:

```json
{"id":"TEL141","name":"Ingeniería de Redes Cloud","professor_can_modify":true}
```

3. Para cada usuario, `PUT /v1/iam/courses/TEL141/members/{user_id}`:

```json
{"quotas":{"max_slices":2,"max_vcpus":4,"max_ram_mb":4096,"max_disk_gb":20}}
```

4. Como administrador, registrar metadatos de autorización con
   `POST /v1/iam/resources`. **Esto no crea un slice real.**

```json
{"id":"slice-demo","kind":"slice","course_id":"TEL141","professor_id":"<UUID-profesor>"}
```

Registrar después la VM lógica para probar permisos de consola:

```json
{"id":"vm-demo","kind":"vm","course_id":"TEL141","professor_id":"<UUID-profesor>","parent_slice_id":"slice-demo"}
```

5. Iniciar sesión como profesor y sustituir el token en **Authorize**. Asignar
   únicamente al primer alumno mediante:
   - `PUT /v1/iam/resources/slice-demo/assignments/{UUID-alumno-1}`.
   - `PUT /v1/iam/resources/vm-demo/assignments/{UUID-alumno-1}`.
   Estas operaciones no requieren body.
6. Iniciar sesión como alumno 1. En `POST /v1/iam/authorize`, comprobar:

```json
{"action":"slice.read","resource_id":"slice-demo"}
```

Debe devolver `allowed: true`. Con `action: "slice.delete"`, devuelve false.
Con `{"action":"vm.console","resource_id":"vm-demo"}`, devuelve true.
**No se emite aún ningún token noVNC ni se abre una consola real.**
7. Como alumno 2, las mismas consultas de slice/consola devuelven false aunque
   pertenezca al mismo curso. `GET /v1/iam/users` devuelve 403.
8. Como administrador, desactivar alumno 1 con
   `PATCH /v1/iam/users/{UUID-alumno-1}`, body `{"active":false}`. Su token previo
   deja de servir inmediatamente. Reactivarlo no restaura sesiones viejas.
9. `GET /v1/iam/audit` permite al administrador ver decisiones y operaciones sin
   contraseñas, hashes ni tokens.

El endpoint `/authorize` responde 200 con `allowed: false` para una consulta válida
pero denegada; las rutas que ejecutan acciones restringidas devuelven 403. Un token
inválido/expirado/revocado devuelve 401. Campos como `role`, `actor_id` o `user_id`
no se aceptan en el body de autorización: el sujeto se obtiene de la sesión.

## Sesiones y controles

- JWT HS256 con clave aleatoria de 256 bits mantenida solo en IAM. Gateway y
  Slice Manager consultan IAM; no tienen la clave de firma.
- Validación de firma, algoritmo fijo, emisor, audiencia, expiración, nbf, iat,
  sujeto y jti; se exige además una sesión persistida y un usuario activo.
- Duración 15 minutos por defecto, configurable entre 60 y 3600 segundos.
- `POST /v1/auth/logout` revoca esa sesión. Cambio de contraseña, cambio de rol
  y desactivación revocan todas las sesiones del usuario.
- `POST /v1/auth/password` cambia contraseña propia verificando la actual.
  Admin puede restablecerla con `POST /v1/iam/users/{id}/password`.
- Eliminación de membresía y asignación se refleja en cada consulta, con el
  mismo JWT; no se guardan permisos estáticos en el token.
- Protección del último administrador activo mediante transacción.
- Cinco intentos de login por nombre normalizado en 60 segundos, persistidos;
  después se responde 429. Es un control inicial por cuenta, no una defensa
  completa ante abuso distribuido. Usuario inexistente, clave errónea y cuenta
  desactivada comparten respuesta genérica.
- Hashes Argon2id con sal individual; no hay credenciales en argumentos del CLI,
  logs, OpenAPI ni respuestas de validación. Respuestas con `Cache-Control: no-store`.
- IDs de rutas restringidos para evitar reinterpretación de rutas al hacer proxy.

## Límites pendientes

No hay frontend de login, SSO/Keycloak, MFA, refresh tokens, recuperación por correo,
provisión de usuarios de OpenStack/Keystone ni identidad máquina-a-máquina.
El acceso temporal a consola y su revocación se integrarán con PlatManager/driver.
El registro administrativo de metadatos no constituye integración con Slice Manager.
Los servicios deben usar datos de recurso propios al consultar IAM; nunca aceptar
como prueba la respuesta `/authorize` que les envíe un cliente.

IAM tiene una instancia y una BD SQLite local. La auditoría es persistente, pero
no un registro externo inmutable; retención y centralización quedan pendientes.
El almacenamiento requiere backups y permisos de archivo. TLS/proxy y operación
multiusuario pública en App Server se validarán antes de publicar.

## Referencias de implementación

- [FastAPI: hashing y JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/).
- [PyJWT: validación de claims](https://pyjwt.readthedocs.io/en/stable/usage.html).
- [OWASP: autenticación](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html).
