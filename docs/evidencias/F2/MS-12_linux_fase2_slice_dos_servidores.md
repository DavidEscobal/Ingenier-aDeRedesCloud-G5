# MS-12 — Slice Linux (R2) en el clúster de fase 2: 2 VMs en servidores distintos

- **Fecha:** 2026-11-13. **Ejecutó:** Claude Code desde la PC del usuario (núcleo `g5` en proceso + `SSHBackend`,
  `config/cluster.json` provisional de fase 2). Aún **no** pasa por el platform-manager del app server.
- **Slice:** `cd1054493fbe48949abfdd5bb263fb77`. vm1 en server1 (192.168.12.10), vm2 en server2 (192.168.12.11),
  enlace `link12` (C-VLAN 112, S-VLAN 1000), imagen `cirros-0.6.2-x86_64-disk.img`
  (SHA-256 `07e44a73e54c94d9…`), 1 vCPU / 512 MiB / 1 GiB cada una. Sin Internet ni publicaciones.

## Preparación previa (2026-11-12/13)
- Inventario de solo lectura; QEMU 4.2.1 instalado por el usuario; agente EX1 instalado con sudo limitado;
  `doctor` y `bootstrap` OK en server1–4. Roles provisionales como EX1 (server1–3 workers, server4 puerta).
- El switch de fase 2 no es accesible, pero transporta QinQ: prueba `diag_datapath` (802.1ad + 802.1q) 3/3.
  Driver ajustado: switch administrado opcional (57d17e9).

## Problema encontrado y corrección
- 1.ª y 2.ª prueba (agente anterior): READY, pero ping vm1↔vm2 0/3 y ~40 tramas MLD/s por VM en `ens4`.
  Prueba de eco sin slice: cada broadcast llegó 1 vez a cada servidor → **la red no tiene bucles**; el tráfico lo
  generaban las VMs. Causa: CirrOS ≥ 0.6 usa `dhcpcd` (el agente de EX1 solo detenía `udhcpc`).
- Corrección (3ed9636, 4ff5a39): `guest_setup` detiene `dhcpcd` y `udhcpc` y desactiva IPv6 antes de fijar la IP;
  tope de 10 Mbit/s por TAP en OVS (`ingress_policing`); diagnósticos `diag_datapath`, `diag_capture`, `diag_ovs`.

## Resultado (agente 3a48240c… en los 4 servidores)
| Comprobación | Resultado |
|---|---|
| Despliegue | READY (un reintento de `guest_setup` por VM mientras CirrOS terminaba de arrancar) |
| Vigilante: tramas VLAN en `ens4` de server2, 10 s | **0** |
| Ping vm1 → vm2 | **3/3**, 1,9–9,4 ms |
| Ping vm2 → vm1 | **3/3**, 2,3–2,8 ms |
| Procesos DHCP en vm2 | ninguno |
| Vecino de vm2 | 192.168.12.10 REACHABLE |
| Borrado | DELETED; sin QEMU ni puertos `g5*` en server1, server2 ni server4 |

## Límites
- El tope por TAP se aplicó sin error (la orden falla si OVS lo rechaza), pero no se midió con tráfico.
- No probado aún: salida a Internet por server4, publicación SSH, consola VNC, topologías de más de 2 VMs,
  integración con el platform-manager / web.
