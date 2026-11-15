# MS-17 — VM Placement (R4) de punta a punta en Linux y OpenStack

- **Fecha:** 2026-11-15 (UTC). Autorizada por el usuario.
- **Revisión en el app server:** 837020c, con el script de humo y la plantilla de 079ef0c en adelante.
- **Flujo probado:** login por el gateway → slice-manager → monitoreo → vm-placement (BCDP v2) → spec con `host` por VM →
  platform-manager (reserva atómica) → proveedor → borrado.
- **Comandos** (el usuario escribió la contraseña; no se muestra ni se guarda):
  - `python3 scripts/smoke_gateway_slices.py --user admin123 --provider linux --provider openstack --hold 60`
    (plantilla `os-lineal-1g`);
  - `python3 scripts/smoke_gateway_slices.py --user admin123 --template templates/lineal-3vm.json --provider linux --hold 60`;
  - `python3 scripts/smoke_gateway_slices.py --user admin123 --delete <slice_id>`.

## OpenStack (slice 82f98ad7, `os-lineal-1g`, 3 VMs CirrOS de 1 vCPU · 512 MB · 1 GB)

| Paso | Resultado |
|---|---|
| Placement | `PLAN_FOUND`, BCDP v2, 0,6 ms, 1 intento: vm1, vm2, vm3 → **worker1** (consolida en 1 host) |
| READY | 25 s; eventos `OS_PLACED: vm1@worker1, vm2@worker1, vm3@worker1` |
| Comprobación independiente en Nova | `OS-EXT-SRV-ATTR:host` = worker1 en las 3 (`g5-82f98ad7-vm1..3`, flavor `g5-1c-512m-1g`) |
| Borrado | DELETED en 15 s |

Resultado del script: 10/11 OK; el único FAIL fue el intento Linux con la misma plantilla (ver abajo).

## Linux (slice ff4e9646, `lineal-3vm`, 3 VMs CirrOS)

| Paso | Resultado |
|---|---|
| Plantilla `os-lineal-1g` | 422 del platform-manager: redes /28 (Linux exige /20../27). Se agregó `templates/lineal-3vm.json` |
| 1.ª versión de `lineal-3vm` | 422: IPs fuera del rango de hosts (Linux exige .10 en adelante). Corregida y validada con el validador real |
| Placement | `PLAN_FOUND`, BCDP v2, 0,3 ms, 1 intento: vm1, vm2, vm3 → **server3** |
| Reserva atómica | `allocations`: vm1, vm2, vm3 en server3 (1 vCPU, 512 MB, 1 GB c/u) |
| Comprobación en el servidor | procesos `qemu-system-x86_64 -name g5-ff4e9646…-vm1..3` solo en server3 |
| READY | **10 min 16 s** (el script se rindió a los 600 s y el borrado se rechazó con 409 por seguir en DEPLOYING) |
| Borrado | `--delete`: DELETED en 5 s |

**Causa de la lentitud (no es del placement):** la consola de vm1 muestra 181 s sin actividad entre la NIC arriba
(4,4 s) y `random: nonblocking pool is initialized` (185 s). La imagen Linux es CirrOS 0.4 (12,7 MB, kernel 4.x); su
kernel no toma la entropía de `virtio-rng` sin `rngd`, y las VMs de un mismo servidor se crean en serie (≈200 s c/u).
Antes, con una VM por servidor, el slice quedaba READY en 57 s. Pendiente: imagen CirrOS ≥ 0.5 en el almacén Linux o
crear en paralelo las VMs de un mismo servidor.

## Aceleración de Linux (2026-11-15, autorizada; platform-manager en 9274ddf)

Cambio 509a6dd: cada worker enciende **todas** sus VMs y después configura los invitados (antes, una VM no se encendía
hasta que la anterior terminaba de arrancar). Prueba `test_worker_powers_on_all_vms_before_guest_setup`.
Misma topología `lineal-3vm` (3 VMs en un servidor), por el gateway con `--image`:

| Imagen | Servidor (placement) | NETWORK_READY → READY | READY total | Antes (MS-17) | Resultado |
|---|---|---|---|---|---|
| `cirros` (CirrOS 0.4, 12,7 MB) | server1 ×3 | 209 s | **222 s** | 616 s | 10/10 OK |
| `cirros-062` (CirrOS 0.6.2, 21 MB) | server1 ×3 | 30 s | **45,5 s** | — | 10/10 OK |

- Con 0.4 sigue pagándose una espera de entropía (~3 min), ahora una sola vez por servidor. Con 0.6.2 desaparece.
- La primera vez, `cirros-062` se trajo de Glance al almacén Linux (queda en caché; `cirros` intacta).
- Borrado del slice con 0.4: un `RETRY` en server4 (`ip link del g5wc7c3e4e78a: Cannot find device`); el reintento
  terminó y quedó DELETED en 5 s. Conviene que el borrado del agente tolere una interfaz ya inexistente.

## Estado final verificado

- server1–4: sin procesos QEMU, sin namespaces, sin directorios de VMs ni de slices.
- OpenStack: solo los proyectos `admin`, `cloud_admin` y `service`; sin VMs; solo la red `external`.
- platform-manager: ningún slice vivo; 0 reservas y 0 S-VLAN asignadas.
