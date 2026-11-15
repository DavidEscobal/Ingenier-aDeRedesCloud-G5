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
- **Pendiente de confirmar por el usuario:** la subida de CPU/RAM de worker1 en la página Recursos (captura) y
  si fue necesario bajar el MTU de ens3 a 1400 para que apt descargara.
