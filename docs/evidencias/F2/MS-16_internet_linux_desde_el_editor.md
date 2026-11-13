# MS-16 — Salida a Internet por VM desde el editor (Linux)

- **Fecha:** 2026-11-13. **Ejecutó:** el usuario en la web: topología lineal de 2 nodos (CirrOS), casilla
  **«Salida a Internet»** solo en `n1`, proveedor Linux. Lo confirmó por la consola; Claude verificó con el agente.
- **Slice:** `46e2cd034c5d4d2e8f557319ccef5e5b` (código 24abd2b).
  - `n1` (server1): `inet0` 10.200.1.10 en `inet1` (red de acceso propia) + `n1-n2` 192.168.1.11.
  - `n2` (server2): `n1-n2` 192.168.1.12, sin Internet.

## Resultado
| Prueba | Resultado |
|---|---|
| n1 → puerta del slice 10.200.1.1 (server4) | 3/3 |
| **n1 → Internet 8.8.8.8** | **3/3** |
| n1 → n2 (enlace dibujado) | 3/3 |
| **n2 → Internet** | **`Network is unreachable`** (sin ruta, como se pidió) |
| n2 → n1 | 3/3 |

## Notas
- Un slice creado antes de esta función (sin red de acceso) no gana Internet: hay que crearlo de nuevo.
- OpenStack: el editor rechaza «Internet» con un aviso (pendiente de R5).
- Acceso desde fuera (SSH publicado, R2-I-09) sigue pendiente: requiere la ruta de 10.60.9.0/24 en el gateway.
