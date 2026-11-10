# MS-09 — Consola noVNC de cada VM desde la web

- **Fecha:** 2026-11-10 · **Host:** app server · **Código:** `fase2` `300067a`
- **Camino:** navegador → `web` (nginx, `/console/`) → `os-tunnel:6080` → nova-novncproxy → VM. Solo hace falta el
  túnel SSH a la web (`127.0.0.1:8080`); el token de Nova es de vida corta y se pide en cada clic.
- **Autorización:** `POST /v1/slices/{id}/vms/{vm}/console` por gateway → slice-manager (dueño o admin) → platform-manager.
- **Tipo:** [REAL].

## Verificaciones

| Prueba | Resultado |
|---|---|
| `GET /console/vnc_auto.html` y `/console/core/rfb.js` vía la web | 200 · 200 |
| WebSocket `GET /console/?token=…` con `Upgrade: websocket` y `Origin` de la web | 101 Switching Protocols |
| Slice `os-lineal-g5` (creado por el usuario desde la web) | READY: vm1, vm2, vm3 en worker3 |
| Detalle del slice en la web | tabla "Máquinas virtuales" con botón Consola en vm1, vm2, vm3 |
| Clic en **Consola** de vm1 (Claude, en el panel) | noVNC: "Connected (unencrypted) to QEMU (instance-00000020)", prompt `g5-77bac05c-vm1 login:` |
| Registro del motor | eventos `CONSOLE` para `vm1`, `vm2` y `vm3` (consolas abiertas por el usuario) |

## Observaciones

- Una pestaña abierta antes del despliegue seguía usando el JavaScript anterior (`index-8c89mH8Z.js`) y no mostraba
  el botón; tras recargar (`index-Ccei5PjC.js`) apareció. Recomendación para la demo: recargar (F5) antes de empezar.
- Consola disponible para OpenStack; la del driver Linux usa su propio proxy y queda pendiente.
- Permisos de consola iguales a los del slice (dueño/admin); el alumno asignado requiere el registro del slice en IAM.
