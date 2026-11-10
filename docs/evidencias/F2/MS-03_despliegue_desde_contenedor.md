# MS-03 — Despliegue real desde el contenedor platform-manager: sin capacidad en Nova → compensación

- **Fecha:** 2026-11-10 · **Host:** app server · **Código:** `~/g5-app` = `fase2` + `scripts/pm_slice_e2e.py`
- **Acción autorizada por el usuario:** crear y borrar `os-lineal` (3 VMs CirrOS, flavor `512MBRAM_1VCPUs_4GBRoot`,
  2 redes) desde el contenedor `platform-manager`, vía `os-tunnel`.
- **Tipo:** [REAL]. Registro completo: `MS-03_create_os-lineal_sin_capacidad_20261110.json` (sin tokens).

## Resultado

| t | Estado |
|---|---|
| 0 s | `QUEUED` (HTTP 202, job encolado) |
| 5 s | `DEPLOYING`: proyecto `g5-be6ed2a3…`, rol, redes y subredes `link12`/`link23`, 4 puertos, 3 servidores |
| 30 s | `FAILED_CLEANED`: Nova marcó **ERROR** en vm2 y vm3, *"No valid host was found. There are not enough hosts available."* |

El motor detectó el error, eliminó en orden todo lo creado ("Eliminación confirmada en todos los destinos;
reservas liberadas") y verificamos después en OpenStack: **ningún proyecto `g5-*`** ni servidor del orquestador.

## Causa: capacidad de disco de los computes (lectura de `/os-hypervisors/detail`)

| Compute | vCPU usadas | RAM usada (MB) | Disco usado / total (GB) | Libre | VMs |
|---|---|---|---|---|---|
| worker1 | 2 / 4 | 1536 / 3935 | 8 / 9 | **1 GB** | 2 |
| worker2 | 2 / 4 | 1536 / 3935 | 8 / 9 | **1 GB** | 2 |
| worker3 | 1 / 4 | 1024 / 3935 | 4 / 9 | 5 GB | 1 |

El único flavor (`512MBRAM_1VCPUs_4GBRoot`) reserva 4 GB de disco raíz por VM y cada compute tiene 9 GB:
caben 2 VMs por compute, 6 en total. Las 5 VMs de laboratorio (`lab5`: 2, `topo1_lab6`: 3) ocupan 5 de esas
6 plazas, así que solo cabía 1 de las 3 VMs del slice.

## Conclusión

- El despliegue **desde Docker funciona hasta Nova**: autenticación, proyecto, redes, subredes, puertos y
  creación de servidores vía `os-tunnel` se ejecutaron; el fallo vino del planificador de Nova por capacidad.
- La **compensación** funcionó de verdad desde el contenedor (equivalente real al caso 1.8.2, ahora por
  falta de capacidad y no por fallo forzado).
- **No demuestra READY.** Para eso hace falta liberar capacidad (VMs de laboratorio, decisión del grupo), un
  flavor con menos disco raíz (CirrOS ocupa ~20 MB) o un slice más pequeño.
