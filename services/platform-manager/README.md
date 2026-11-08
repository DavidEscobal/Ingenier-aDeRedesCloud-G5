# Platform Manager

Núcleo de ejecución del orquestador (paquete `g5/` de la raíz, sin dependencias
externas). Recibe la orden de desplegar un slice **ya definido** en un proveedor
(`linux` u `openstack`), la encola (tabla `jobs` en SQLite), la ejecuta con el
driver correspondiente desde el `Engine`, sigue su estado y compensa si falla.

Es dueño de: slices desplegados, operaciones/eventos, reservas y el journal de
recursos por proveedor. **No** es dueño de: usuarios y permisos (IAM), borradores
y plantillas (slice-manager / topology-manager), ni de la decisión de placement
(D-07, pendiente).

## Contenedor

- Imagen construida desde la raíz del repo (`.dockerignore` en lista blanca: solo
  `g5/`, `api/`, `templates/`). No contiene configuración ni secretos.
- Escucha en `0.0.0.0:8000` con `--internal-network`: HTTP sin TLS permitido solo
  porque el servicio **no publica puertos** y vive en la red interna `control`.
  El Bearer sigue siendo obligatorio (salvo `/healthz`).
- Estado persistente en el volumen `platform-data` (`/app/state`).
- Corre como `appuser` con el UID del dueño de la clave SSH (`G5_UID`, por defecto 1000).

## Montajes (solo lectura) — directorio `$G5_PLATFORM_CONFIG` del host

Por defecto `deploy/platform-config/` (ignorado por Git, permisos 700). El servicio
está en el perfil `platform`: `docker compose up -d` no lo arranca;
se levanta con `docker compose --profile platform up -d` cuando la carpeta está lista.

| Archivo en el host | En el contenedor | Nota |
|---|---|---|
| `cluster.json` | `/run/g5/cluster.json` | `ssh_key` como `~/.ssh/<clave>` → `/home/appuser/.ssh/<clave>` |
| `keys.json` | `/run/g5/keys.json` | identidades API (hash SHA-256 del token), incluida la de servicio para slice-manager |
| `openstack.env` | `/run/g5/openstack.env` | `OS_*`, permisos 600. **Debe existir** (vacío si solo se usa Linux); si falta, Docker crea un directorio |
| `ssh/` | `/home/appuser/.ssh` | clave privada (600) y `known_hosts` con las huellas de los nodos (`StrictHostKeyChecking=yes`) |

## Pendiente (no implementado)

- **Acceso a las API de OpenStack desde el contenedor.** Hoy los túneles
  (`g5-tunnels`) escuchan en `127.0.0.1` del host, inalcanzable desde la red
  Docker. Opciones: (a) un servicio *sidecar* de túneles en la red `control`
  (`endpoint_map` → `http://os-tunnel:55000`, …), sin tocar el host; (b) atar los
  túneles del host a la IP del puente Docker y usar `host-gateway`. Requiere decisión.
- **Consola noVNC del driver Linux.** Los reenvíos SSH escuchan en `127.0.0.1` del
  proceso; el futuro servicio `console` (websockify) debe compartir su espacio de
  red (`network_mode: service:platform-manager`) o se rediseña el reenvío.
- **Llamada desde slice-manager** con token de servicio y autorización IAM (paso 5).
- No se ha construido ni ejecutado la imagen: el app server aún no tiene Docker
  verificado y esta PC no tiene Docker.
