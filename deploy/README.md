# APP G5 — Gateway, IAM y Slice Manager

Implementación incremental del HLD. Hay tres procesos independientes comunicados
por HTTP. IAM implementa identidad y permisos académicos; Slice Manager aún no
crea slices ni reserva capacidad. R2 permanece en `g5/` y no se invoca en esta etapa.

## Windows: preparar y ejecutar

Se requiere Python 3.12. Todos los comandos parten de la raíz del repositorio.
Si los procesos de la versión anterior siguen abiertos, detenerlos con Ctrl+C
para cargar el nuevo código. No ejecutar dos copias sobre los mismos puertos.

Preparación en una nueva máquina (en esta computadora las dependencias ya se
instalaron en `.venv` mediante uv):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r services/gateway/requirements.lock -r services/slice-manager/requirements.lock -r services/iam-service/requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e services/gateway -e services/slice-manager -e services/iam-service
```

Inicializar **una sola vez** la identidad del administrador:

```powershell
.\.venv\Scripts\python.exe -m g5_iam.cli init
```

El asistente pide usuario y contraseña (15 a 128 caracteres), con confirmación.
Crea `state/iam/iam.db` y una clave aleatoria en `state/iam/jwt.key`, ambos ignorados
por Git. No hay usuario ni contraseña de fábrica. Una segunda ejecución no
sobrescribe cuentas. IAM no arranca sin inicialización; nunca genera claves
nuevas silenciosamente al reiniciar. En Windows, conservar estos archivos dentro
del perfil del usuario con los permisos del sistema adecuados.

**Terminal 1 — IAM (puerto 8002):**

```powershell
.\.venv\Scripts\python.exe -m uvicorn g5_iam.main:app --host 127.0.0.1 --port 8002
```

**Terminal 2 — Slice Manager (puerto 8001):**

```powershell
$env:IAM_URL = "http://127.0.0.1:8002"
.\.venv\Scripts\python.exe -m uvicorn g5_slice_manager.main:app --host 127.0.0.1 --port 8001
```

**Terminal 3 — Gateway (puerto 8000):**

```powershell
$env:IAM_URL = "http://127.0.0.1:8002"
$env:SLICE_MANAGER_URL = "http://127.0.0.1:8001"
.\.venv\Scripts\python.exe -m uvicorn g5_gateway.main:app --host 127.0.0.1 --port 8000
```

Las variables son por terminal. `.env.example` documenta valores; no se carga
automáticamente. Las rutas de estado de IAM son relativas a la raíz del proyecto.

## Primera prueba desde Swagger

1. Abrir http://127.0.0.1:8000/docs.
2. Ejecutar `GET /v1/platform/capabilities` sin autorización: devuelve **401**.
3. Ejecutar `POST /v1/auth/login` con el usuario y contraseña creados en `init`.
   Responde `access_token`, `token_type=bearer` y `expires_in=900`.
4. Pulsar **Authorize** y pegar únicamente el valor de `access_token`.
5. Ejecutar `GET /v1/auth/me`: muestra identidad y rol obtenidos de IAM.
6. Ejecutar `GET /v1/platform/capabilities`: responde 200 con `iam=true`.
   `persistence=false` se refiere a la persistencia de slices, aún pendiente;
   IAM sí persiste usuarios, sesiones, membresías y auditoría.
7. Ejecutar `POST /v1/auth/logout`. Repetir `GET /v1/auth/me` con el mismo token:
   responde 401. Volver a iniciar sesión para continuar.

El token vence a los 15 minutos por defecto y no tiene renovación automática.
Cambiar contraseña, cambiar rol o desactivar cuenta revoca todas sus sesiones.

Para probar roles, cursos y recursos seguir [la guía IAM](IAM.md).

## Comprobaciones de disponibilidad

```powershell
Invoke-RestMethod http://127.0.0.1:8000/healthz
Invoke-RestMethod http://127.0.0.1:8000/readyz
```

`healthz` solo comprueba el proceso. `readyz` comprueba dependencias y devuelve
`slice-manager=ok` e `iam=ok` cuando están disponibles. Si IAM cae, las rutas
protegidas rechazan la solicitud; no hay modo de omitir la autenticación.
Si se accede directamente al puerto 8001, Slice Manager también exige una sesión
válida: no confía en cabeceras X-Role/X-User-Id ni en que el Gateway ya verificó.

## Docker Compose / App Server

Docker no está instalado en la computadora de desarrollo: el despliegue real en
contenedores debe verificarse en un host con Docker. No se ha desplegado en el
App Server ni publicado el servicio.

Desde la raíz del repositorio, inicialización del estado del contenedor:

```sh
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml run --rm --no-deps iam python -m g5_iam.cli init
docker compose -f deploy/compose.yaml up -d
docker compose -f deploy/compose.yaml ps
docker compose -f deploy/compose.yaml logs --tail=100
```

El volumen `iam-data` tiene su propio estado; no reutiliza automáticamente la BD
local de Windows. La inicialización anterior se hace una vez por volumen nuevo.
No se incluyen claves ni contraseñas dentro de las imágenes.
IAM y Slice Manager no publican puertos al host. Gateway solo publica
`127.0.0.1:8000`; esta configuración es de laboratorio por loopback/túnel.
El acceso remoto se puede inspeccionar con el SSH asignado, por ejemplo:

```sh
ssh -N -L 18000:127.0.0.1:8000 USUARIO@APP_SERVER
```

Sustituir los marcadores y usar el puerto, salto o VPN asignados. Abrir
http://127.0.0.1:18000/docs en la laptop. Antes de exponer a usuarios se necesita
TLS en el punto de entrada y transporte protegido entre hosts. La red Compose
local usa HTTP privado; no implementa TLS interno ni alta disponibilidad.

```sh
docker compose -f deploy/compose.yaml down
```

`down` conserva el volumen. No usar `down -v` para una parada normal: eliminaría
el estado IAM. Respaldar BD y clave juntas con IAM detenido antes de migraciones.
Las políticas `unless-stopped` reinician procesos; los healthchecks detectan
fallos pero no reinician por sí solos un proceso vivo. Docker debe arrancar
con el sistema si se espera recuperación tras reinicio del host.

## Pruebas y contratos

```powershell
.\.venv\Scripts\python.exe scripts/export_app_contracts.py
.\.venv\Scripts\python.exe -m unittest discover -s tests/app -v
```

Las pruebas usan bases temporales, cuentas aleatorias y procesos en puertos
locales temporales. No crean usuarios en tu BD real ni invocan SSH/R2/OpenStack.
Se comprueban sesiones, RBAC, aislamiento por curso/recurso, revocación, hashes,
auditoría, persistencia y comunicación real entre los tres servicios.

Las dependencias de cada servicio están fijadas en `requirements.lock`.
Para actualizar una resolución, usar `uv pip compile` sobre su `pyproject.toml`
con `--python-version 3.12 --universal`, regenerar contratos y ejecutar pruebas.
La imagen base `python:3.12-slim` no está fijada por digest.

## Siguiente integración

Slice Manager deberá mantener la verdad del recurso, registrar/sincronizar sus
relaciones académicas con IAM mediante una identidad de servicio de alcance
limitado y revalidar permisos antes de cada operación. El registro manual actual
solo permite ensayar políticas: no acredita existencia de una VM/slice real.
Las cuotas registradas por IAM se aplicarán en la admisión transaccional de Slice
Manager junto con capacidad y reservas. Cola, outbox, PlatManager y R2 siguen
siendo incrementos posteriores.
