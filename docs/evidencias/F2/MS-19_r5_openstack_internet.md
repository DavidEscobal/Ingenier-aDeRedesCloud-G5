# MS-19 — R5 en OpenStack: salida a Internet y acceso por la red provider `external`

- **Fecha:** 2026-11-15 (UTC). Autorizada por el usuario.
- **Revisión en el app server:** 0efd775 (código R5: e022c9c).
- **Comando** (el usuario escribió las contraseñas; no se muestran ni se guardan):
  `python3 scripts/smoke_gateway_slices.py --user admin123 --template templates/ubuntu-2vm.json --provider openstack --guest-user alumno --internet vm1 --hold 600 --timeout 900`
- **Red `external` (inventario de solo lectura, mismo día):** flat/physnet0, compartida, `router:external`, subred
  10.60.10.0/24 (rango OpenStack de G5), gateway 10.60.10.1, DHCP .10–.250, DNS 8.8.8.8; sin routers ni floating IPs.

## Resultado del script: 10/10 OK (slice ad39f93b, READY en 20 s, borrado en 10 s)

| Comprobación | vm1 (`internet: true`) | vm2 |
|---|---|---|
| Puertos (Neutron) | `g5-ad39f93b-vm1-inet` en `external`, **10.60.10.229**, port security ✓, 1 grupo; `vm1-link12` 192.168.21.10 sin port security | `vm2-link12` 192.168.21.11 sin port security |
| Grupo `g5-ad39f93b-internet` | entrada **tcp/22** e **icmp** desde 0.0.0.0/0; salida libre (reglas por defecto) | — |
| Consola (cloud-init, config drive) | `ens3` 10.60.10.229/24, ruta por defecto **10.60.10.1**; `ens4` 192.168.21.10/27 | `ens3` 192.168.21.11/27, **sin ruta por defecto** |
| Prueba del usuario por VNC | `sudo apt update` ✅ | — |
| Borrado | puerto `-inet` y grupo eliminados; `external` intacta (0 puertos, 0 routers, 0 floating IPs) | — |

## Pendientes observados

1. **SSH desde fuera (paso 17): timeout.** La VPN del usuario instala rutas por 10.8.0.1 hacia 10.20.10–14.0/24 y
   **10.60.9.0/24**, pero **no hacia 10.60.10.0/24** (rango OpenStack de G5): el tráfico sale por Internet y se pierde.
   Desde el app server tampoco hay ruta (10.60.10.229 vía 10.20.11.1, sin respuesta). Consulta al JP: que la VPN
   publique 10.60.10.0/24 y que el headnode VNRT la enrute hacia physnet0.
2. **`ping google.com`: «Temporary failure in name resolution».** `apt update` sí resolvió nombres, por lo que el DNS
   funcionaba al menos en ese momento; queda por repetir en vm1 (`resolvectl status ens3`, `ping 8.8.8.8`) para
   descartar que la prueba se hiciera en vm2 (sin salida) o una demora de systemd-resolved.
3. El grupo admite SSH/ICMP desde cualquier origen (`external_allowed_sources` por defecto); restringirlo a la red de
   los clientes VPN cuando se conozca.
