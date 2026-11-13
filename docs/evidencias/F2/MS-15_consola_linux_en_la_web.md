# MS-15 — Consola noVNC de VMs Linux desde la web

- **Fecha:** 2026-11-13. **Ejecutó:** el usuario en la web (`http://127.0.0.1:18080`): slice Linux
  `5cd6584417964d87a5c933bb741b2c81` (lineal de 2 nodos, CirrOS), botón **Consola** en `n1` y `n2`.
  **Resultado reportado por el usuario: la consola funciona.**
- **Cadena:** web (`/lconsole/`, nginx) → websockify + noVNC dentro del platform-manager (:6080, solo red `control`,
  token propio que vence) → túnel SSH del platform-manager por el gateway del lab → `127.0.0.1:59xx` del worker.

## Problemas encontrados y corregidos en esta prueba
| Síntoma | Causa | Corrección |
|---|---|---|
| Sin botón Consola en Linux | La web solo lo mostraba para OpenStack | 52b96ad |
| "Failed to connect to server" | Ruta del WebSocket duplicada (`/lconsole/lconsole/websockify`) | e04e381 (ruta relativa a la página) |
| "Failed to connect to server" | La llave del orquestador en server1–4 tenía `no-port-forwarding` (fase A) | El usuario cambió la línea a `permitopen="127.0.0.1:*"` (respaldo `authorized_keys.bak-consola`) |

## Verificación desde el contenedor
- Túnel al VNC de server1 y server2: `RFB 003.008`.
- Restricción vigente: reenviar a otro equipo (server1 → 192.168.201.2:22) → `administratively prohibited`.

## Límites
- El túnel de cada consola dura 10 min (máximo del diseño EX1); luego se vuelve a pulsar Consola.
- Credenciales de CirrOS públicas de la imagen (`cirros` / `gocubsgo`).
