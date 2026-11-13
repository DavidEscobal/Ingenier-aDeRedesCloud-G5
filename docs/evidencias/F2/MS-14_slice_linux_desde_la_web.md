# MS-14 — Slice Linux creado y borrado desde la web (cadena completa de fase 2)

- **Fecha:** 2026-11-13. **Ejecutó:** el usuario en la web (`http://127.0.0.1:18080`, túnel al app server):
  editor → topología lineal de 2 nodos → Desplegar → proveedor **Linux**. Claude verificó por el agente.
- **Cadena:** web → gateway → slice-manager → platform-manager (código a8772ca) → SSH por el gateway del lab
  (llave `id_ed25519_linux`, fase A) → agentes de server1, server2 y server4.
- **Slice:** `9e306ea8a4b74fe9adb07522fd4827fc` (`lineal-2`). Imagen elegida en el editor: `cirros` de Glance,
  traída al almacén Linux del platform-manager (SHA-256 `a8dd75ecffd4…`, verificada con `qemu-img`).

## Resultado
| Comprobación | Resultado |
|---|---|
| Adaptador | `n1` → server1 (10.60.1.11), `n2` → server2 (10.60.1.12); C-VLAN 100; reparto rotativo provisional |
| Tiempos | aceptado 0 s · preparado 5 s · red lista 12 s · **READY 391 s** |
| Configuración de CirrOS | 2 reintentos de `guest_setup` por VM (plazo de 180 s agotado mientras arranca) |
| Ping n1 → n2 / n2 → n1 | **3/3** / **3/3** |
| `dhcpcd` en n2 | no corre |
| Vigilante en `ens4` de server2 | 0 tramas en 10 s |
| **Borrado desde la web** | DELETED en 2 s; sin QEMU, puertos `g5*` ni namespaces en server1, server2, server4 |

## Pendientes detectados
- **Lentitud:** `guest_setup` debe esperar el fin del arranque de CirrOS en lugar de agotar el plazo (≈6,5 min
  hoy); la web debería mostrar el paso en curso.
- Consola Linux en el navegador (noVNC) aún no conectada; Internet y publicaciones no se exponen en el editor.
- El reparto por turnos es provisional hasta el placement (D-07).
