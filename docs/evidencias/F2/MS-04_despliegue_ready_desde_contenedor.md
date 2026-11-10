# MS-04 — Despliegue real desde el contenedor platform-manager: crear → READY → borrar → limpio

- **Fecha:** 2026-11-10 · **Host:** app server · **Código:** `fase2` + `templates/os-lineal-1g.json`
- **Cambio en OpenStack autorizado por el usuario:** flavor público `g5-1c-512m-1g` (1 vCPU, 512 MB, **1 GB** de disco
  raíz), para no desperdiciar disco (CirrOS: 12 MB, 44 MB virtuales). Motivo: MS-03 (sin capacidad con 4 GB por VM).
- **Tipo:** [REAL]. Registros: `MS-04_create_*.json`, `MS-04_delete_*.json` (sin tokens).

## Creación (`scripts/pm_slice_e2e.py create`)

| t | Estado |
|---|---|
| 0 s | `QUEUED` (HTTP 202) |
| 5 s | `DEPLOYING` |
| **20 s** | **`READY`**: "Instancias ACTIVE en Nova: vm1@worker3, vm2@worker3, vm3@worker3" |

## Verificación en OpenStack (lectura vía `os-tunnel`)

| Recurso | Resultado |
|---|---|
| Proyecto | `g5-69dd110e3bc94713abca89803a436824` (uno por slice) |
| vm1 | ACTIVE, worker3, `link12` 192.168.11.2 |
| vm2 | ACTIVE, worker3, `link12` 192.168.11.3 y `link23` 192.168.12.2 |
| vm3 | ACTIVE, worker3, `link23` 192.168.12.3 |
| Redes | `link12` VLAN 215 y `link23` VLAN 574, `physnet1` |
| Subredes | 192.168.11.0/28 y 192.168.12.0/28, DHCP, sin gateway |
| `GET /v1/slices/{id}/diagnostics` | `ok: true`, los 3 servidores ACTIVE |

Las IP coinciden con las fijadas en la plantilla. Nova ubicó las 3 VMs en worker3, el único con disco libre
(placement G5 aún pendiente, D-07).

## Borrado (`scripts/pm_slice_e2e.py delete`)

| t | Estado |
|---|---|
| 0 s | `DELETING` |
| 20 s | `DELETED`: "Eliminación confirmada en todos los destinos; reservas liberadas" |

Verificación posterior: 0 proyectos, servidores, redes y puertos `g5-*`; las 5 VMs de laboratorio siguen ACTIVE.

## Conclusión

El núcleo de ejecución **dentro de Docker** despliega y elimina un slice multi-VM en OpenStack de punta a punta
(proyecto, VLANs, subredes, puertos con IP fija, servidores), vía el sidecar `os-tunnel`. Pendiente: que la
petición llegue desde el gateway y el slice-manager con autorización IAM (paso 5).
