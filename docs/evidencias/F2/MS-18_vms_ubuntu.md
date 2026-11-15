# MS-18 — VMs Ubuntu 24.04 minimal con credenciales (Ex2 pasos 3–4 y 15)

- **Fecha:** 2026-11-15 (UTC). Autorizada por el usuario.
- **Revisión en el app server:** b71e467 (servicios) y el script de humo de la rama `fase2` posterior.
- **Imagen:** `ubuntu-24.04-minimal-cloudimg-amd64` importada por la web (tras subir el límite a 2048 MB):
  1 516 896 256 bytes, disco virtual 3,5 GiB; MD5 `b49679eb…` y SHA-512 `0e9a5dea…` de Glance **idénticos** al
  archivo local.
- **Plantilla:** `templates/ubuntu-2vm.json` (2 VMs, 1 vCPU · 1 GB · 4 GB, enlace 192.168.21.0/27 sin DHCP, IPs .10/.11).
- **Comando** (el usuario escribió la contraseña de las VMs y la de admin123; no se muestran ni se guardan):
  `python3 scripts/smoke_gateway_slices.py --user admin123 --template templates/ubuntu-2vm.json --provider <p> --guest-user alumno`

## OpenStack (slice 955b7d5e) — OK

| Paso | Resultado |
|---|---|
| Placement | `PLAN_FOUND`, BCDP v2: vm1, vm2 → worker1 |
| READY | 40,5 s (flavor `g5-1c-1g-4g`, creado con autorización) |
| Servidores en Nova | `config_drive=True`, `user_data` con el usuario `alumno` (solo hash SHA-512 crypt) |
| Consola serie (Nova) | cloud-init 24.4.1 terminó a los 24 s, `Datasource DataSourceConfigDrive`; `ens3` 192.168.21.10/27 y 192.168.21.11/27 (subred sin DHCP: la IP llegó por el config drive); `login:` |
| Consola VNC (usuario) | login con `alumno`, ping entre VMs, `stress-ng` y `tcpdump` presentes; la imagen trae Open vSwitch |
| Borrado | el del script falló con 401 (el token de 900 s caducó durante `--hold 900`); `--delete` → DELETED en 5 s. Script corregido: `--hold` se limita a la vida del token |

Intentos previos sin efectos: 401 en el login (contraseña mal escrita) y 422 del slice-manager (contraseña de VM de
menos de 8 caracteres; el gateway solo mostró `slice_manager_error`). El script ahora valida 8..72 antes del login.

## Linux (slice daa5755c) — FALLÓ, sin recursos creados

1. **504 `platform_timeout`:** la primera vez, el platform-manager trae la imagen de Glance (1,5 GB) dentro de la
   petición de creación; el slice-manager corta a los 20 s (`PLATFORM_TIMEOUT_SECONDS`). El platform-manager terminó
   igual (respuesta perdida: `BrokenPipeError`), así que el slice se creó sin quedar registrado en el slice-manager.
   La imagen quedó en el almacén Linux; la próxima vez no hay descarga.
2. **FAILED_CLEANED:** `server1/prepare: Disco insuficiente para bases pendientes y crecimiento ya reservado`
   (3 intentos). El agente reserva el disco completo de cada VM: 4 GiB + base 1,52 GB + margen `disk_margin_gb` 2 GiB
   ≈ 7,96 GB, y server1 tiene 6,49 GB libres (server2 6,82, server3 6,48; discos de 9,7 GB). Limpieza confirmada,
   0 reservas.

**Consecuencia:** con la reserva completa, ningún servidor Linux admite una VM Ubuntu de 4 GB; el paso 3 (2 VMs en
server2) necesitaría ≈ 10,1 GB aun sin margen. Opciones: discos más grandes (JP), aprovisionamiento delgado
(reservar el uso real del qcow2 con un factor de sobreasignación) o un margen menor (solo alcanza para 1 VM).
