# MS-20 — Modo automático de plataforma (LAB7) y `stress-ng` en OpenStack (Ex2 paso 4)

- **Fecha:** 2026-11-15 (UTC). Despliegue y pruebas autorizados por el usuario.
- **Revisión en el app server:** db92390 (código del modo automático: 3648b85). Servicios reconstruidos:
  slice-manager, topology-manager, web; los 10 contenedores sanos tras el despliegue.
- Las contraseñas las escribió el usuario en la terminal; no se muestran ni se guardan.

## 1. Modo automático (`provider: "auto"`)

Comando: `python3 scripts/smoke_gateway_slices.py --user admin123 --provider auto --timeout 900`
(plantilla por defecto `templates/os-lineal-1g.json`, 3 VMs CirrOS).

- Script: login, curso, creación 202, plan `PLAN_FOUND` (BCDP v2, 1 host nuevo), READY en 25 s con
  vm1–vm3@worker1, detalle coherente con el plan, lista, 404, borrado 202.
- Decisión guardada por el slice-manager para el slice `e23a7a18…` (columna `placement`):

```json
{"provider": "openstack", "mode": "auto", "attempts": 1, "hosts_opened": 1,
 "candidates": [{"provider": "linux", "hosts_opened": 1, "hosts_used": 1},
                {"provider": "openstack", "hosts_opened": 1, "hosts_used": 1}],
 "rejected": [{"provider": "linux", "reason": "invalid_spec: Red privada RFC1918 con prefijo /20../27 requerida"}]}
```

- **Lectura:** ambos proveedores tenían plan con el mismo Z (1 host nuevo), así que el desempate eligió Linux;
  el platform-manager rechazó la especificación en Linux (la plantilla usa una red que el driver Linux no admite)
  y el Slice Manager desplegó en OpenStack sin intervención. Es el caso A5 de los tests, observado en el clúster.
- **Límite conocido:** los rechazos que el agente Linux detecta durante el despliegue (p. ej. disco insuficiente
  para una Ubuntu de 4 GB) ocurren después de aceptar el slice, por lo que el modo automático no los ve; con
  Ubuntu conviene elegir OpenStack explícitamente hasta que el JP resuelva el disco de los servidores Linux.

## 2. `stress-ng` en una VM Ubuntu de OpenStack

Comando: `python3 scripts/smoke_gateway_slices.py --user admin123 --template templates/ubuntu-2vm.json --provider openstack --guest-user alumno --internet vm1 --hold 720 --timeout 900`

- Slice `b154c438…` READY en 20 s; vm1 y vm2 en worker1 (Ubuntu 24.04 minimal, 1 vCPU / 1 GB / 4 GB).
- En la consola de vm1 (salida a Internet por la red `external`):
  - `sudo apt update && sudo apt install -y stress-ng`: la primera vez quedó en «Waiting for headers»; al repetirlo
    terminó con «stress-ng is already the newest version», es decir, la instalación sí se completó.
  - `stress-ng --cpu 1 --cpu-load 80 --vm 1 --vm-bytes 80% --timeout 180s --metrics-brief`: terminó con
    «successful run completed».
- **Página Recursos (worker1, según lo anotado por el usuario):** con el slice activo, vCPU comprometida 2/8,
  RAM 2560/3935 MB, disco 8.0/90 GB, 2 VMs, **CPU real: «sin dato»**; tras borrar el slice volvió a 0 VMs y 512 MB.
  **Corrección:** lo que subió es la capacidad **asignada** al crear el slice, no el uso que provoca `stress-ng`.
  En OpenStack el monitoreo no mide la CPU real de los computes (sin acceso a los workers,
  `services/monitoring/src/g5_monitoring/normalize.py` deja `cpu_real_cent` en `None`), así que la carga de
  `stress-ng` no se ve en Recursos. Para el paso 4/5 («asignado y usado») falta una fuente de uso real en OpenStack
  (p. ej. diagnósticos de Nova por servidor, o el acceso SSH a los workers que está pedido al JP).
- **MTU:** apt solo descargó tras `sudo ip link set ens3 mtu 1400` (la red `external` anuncia 1500 y el camino a
  Internet no lo soporta: la conexión se abre y las respuestas grandes se pierden, «Waiting for headers»).
  Corrección en el orquestador: la NIC de salida recibe MTU 1400 por cloud-init (`bootcmd` que la ubica por MAC y
  deja `/etc/netplan/90-g5-mtu.yaml` para los siguientes arranques; configurable con `external_mtu`). Probado con
  tests; falta verificarlo en el clúster.
- **Pendiente:** captura de Recursos (no se adjuntó); uso real de CPU/RAM en OpenStack.

## 3. Uso medido en OpenStack (mismo día, más tarde)

- **Código:** 039761c y 1345564, desplegados (platform-manager, monitoring, web). El platform-manager pide a Nova los
  diagnósticos de cada VM de G5 (`GET /servers/{id}/diagnostics`, formato de libvirt: `cpuN_time` en ns y memoria en
  KiB) y la carga de cada compute (`/os-hypervisors/{id}/uptime`). CPU de la VM = incremento del tiempo de CPU entre
  muestras; RAM usada = `memory-available − memory-usable` (vista del invitado). El formato estándar 2.48 se descartó:
  da la RAM en GiB enteros. La CPU real del compute completo sigue sin dato (compartido); el VM Placement no cambia.
- **Prueba:** slice `8a59a8db…` (`ubuntu-2vm`, vm1 con Internet, ambas en worker1). Por SSH desde `g5-gw` con la clave
  de diagnóstico: MTU 1400 de fábrica, `apt-get install stress-ng` sin intervención y
  `stress-ng --cpu 1 --cpu-load 80 --vm 1 --vm-bytes 80% --timeout 300s` (21:59:56–22:04:56 UTC).
- **Muestras del servicio de monitoreo (worker1; CPU en centésimas, RAM usada / total en MB):**

| Hora UTC | Carga 1 min | vm1 CPU | vm1 RAM | vm2 CPU | vm2 RAM |
|---|---|---|---|---|---|
| 22:03:25 | 1,07 | 99 | 537 / 1024 | 0 | 281 / 1024 |
| 22:03:35 | 1,06 | 100 | 371 / 1024 | 1 | 281 / 1024 |
| 22:04:55 | 1,01 | 99 | 572 / 1024 | 0 | 281 / 1024 |
| 22:05:06 | 0,86 | 9 | 313 / 1024 | 1 | 281 / 1024 |
| 22:05:16 | 0,80 | 1 | 263 / 1024 | 0 | 281 / 1024 |

- **Lectura:** con `stress-ng` vm1 marca 1 CPU completa (80 % de carga más el trabajador de memoria) y su RAM oscila
  por el trabajador `--vm`; al terminar baja a ≈ 0. vm2, sin carga, se mantiene en 0. La página Recursos muestra
  «VMs G5: X CPU» y la carga en la columna CPU real, la curva en el historial y el detalle por VM (solo admin).
