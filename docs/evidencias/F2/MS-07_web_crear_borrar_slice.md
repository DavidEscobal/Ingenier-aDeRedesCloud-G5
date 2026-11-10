# MS-07 — Interfaz web: un usuario crea y borra un slice real desde el navegador

- **Fecha:** 2026-11-10 · **Host:** app server · **Código:** `fase2` `a097e7f` (servicio `web`, D-10)
- **Acceso:** túnel SSH a `127.0.0.1:8080` del app server; navegador → nginx (`web`) → `/api` → gateway →
  slice-manager ⇄ IAM → platform-manager → os-tunnel → OpenStack.
- **Ejecución:** el usuario inició sesión como `admin123` (contraseña solo tecleada por él), creó el slice
  `os-lineal-grupo5` desde **Nuevo slice** (curso TEL141, plantilla "Lineal de 3 VMs") y luego lo borró desde el detalle.
- **Tipo:** [REAL].

## Verificaciones previas (Claude, sin credenciales reales)

| Prueba | Resultado |
|---|---|
| `GET /` · `GET /slices` (recarga de ruta interna) | 200 · 200 |
| `GET /api/healthz` vía nginx | 200 `{"service":"gateway","status":"ok"}` |
| `GET /api/v1/slices` sin token | 401 |
| Cabeceras | `Content-Security-Policy` estricta, `X-Frame-Options: DENY` |
| Login vacío (navegador) | "Escribe tu usuario y tu contraseña." |
| Login con usuario inexistente (valor de prueba) | "Usuario o contraseña incorrectos, o la sesión expiró." |

## Creación desde la web (estado leído de la página de detalle)

| Campo | Valor |
|---|---|
| Slice | `os-lineal-grupo5` — **Listo** |
| Proveedor / Curso / Dueño | OpenStack / TEL141 / admin123 |
| Menú mostrado | "Todos los slices", "Nuevo slice", etiqueta *Administrador* |
| Historial | 18 eventos; último: "Listo — Instancias ACTIVE en Nova: vm1@worker3, vm2@worker3, vm3@worker3" (12:30:57) |

Verificación en OpenStack (lectura vía `os-tunnel`): proyecto `g5-ba9193e29a7e47e6ab8bdf89379a03b4`;
vm1 192.168.11.2, vm2 192.168.11.3 / 192.168.12.2, vm3 192.168.12.3, todas ACTIVE en worker3.

## Borrado desde la web

| Campo | Valor |
|---|---|
| Estado final en la página | **Borrado** — "Eliminación confirmada en todos los destinos; reservas liberadas" (12:39:27) |
| Registro del slice-manager | `POST /v1/slices` 202 y `DELETE /v1/slices/ba9193e2…` 202 (las dos únicas peticiones de la sesión) |
| OpenStack después | 0 proyectos, servidores y redes `g5-*`; 5 VMs de laboratorio intactas |

## Ajuste derivado

El evento `OS_DELETED` se mostraba con su nombre técnico: se añadió su etiqueta ("Recurso borrado") y se
redesplegó la web.
