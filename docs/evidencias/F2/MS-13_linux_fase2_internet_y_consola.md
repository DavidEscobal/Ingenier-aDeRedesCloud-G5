# MS-13 — Slice Linux de fase 2: Internet selectivo por server4 y consola VNC

- **Fecha:** 2026-11-13. **Ejecutó:** Claude Code desde la PC del usuario (núcleo `g5` en proceso + `SSHBackend`,
  agente 3a48240c… en server1–4). Aún no pasa por el platform-manager.
- **Slice:** `e6cd6ed9d8bd4c3092ca3054c5ad7e5f`, CirrOS 0.6.2.
  - vm1 (server1): `access0` 192.168.101.10/27 (`access1`, C-VLAN 301, `internet: true`) + `to-vm2` 192.168.12.10/27.
  - vm2 (server2): `to-vm1` 192.168.12.11/27, `internet: false`.
  - Puerta del slice: namespace propio en server4 (NAT/firewall), `.1` de `access1`.

## Resultados
| Comprobación | Resultado |
|---|---|
| Despliegue | READY; vigilante de ráfagas en `ens4` de server2: 0 tramas en 10 s |
| Ruta por defecto de vm1 | `default via 192.168.101.1 dev access0` |
| vm1 → puerta del slice 192.168.101.1 | 3/3 |
| **vm1 → Internet (8.8.8.8)** | **3/3**, 37–44 ms, TTL 109 |
| vm1 → vm2 (enlace entre servidores) | 3/3 |
| **vm2 → Internet** | **sin ruta** (`Network is unreachable`), como se pidió |
| **Consola VNC vm1 / vm2** | túnel SSH al puerto VNC del worker (5900): servidor responde `RFB 003.008` en ambas |
| Borrado | DELETED; sin QEMU, puertos `g5*` ni namespaces `g5*` en server1, server2 ni server4 |

## Límites y notas
- La consola se validó a nivel de túnel + protocolo RFB, no con noVNC en el navegador.
- `Consoles.issue` falló **solo en la PC Windows**: `backend.tunnel` usa `timeout` de coreutils y en Windows se
  resuelve `timeout.exe` del sistema. En el contenedor Linux del platform-manager existe el correcto; se verificará
  al integrar.
- No probado: publicación SSH desde fuera (DNAT), topologías de más de 2 VMs, integración con web/platform-manager.
