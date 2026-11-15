# MS-21 — Ex2 pasos 15b–e en OpenStack: VM4 como OVS

- **Fecha:** 2026-11-15 (UTC). Autorizado por el usuario (despliegue, clave SSH de diagnóstico, recreación del slice).
- **Revisión en el app server:** b483468 (MTU 1400 y enlaces «sin IP» con subred de relleno). Arreglo posterior,
  9e32610 (la IP de relleno se quita también del netplan), probado a mano en vm4; **no desplegado**.
- **Slice:** `templates/ovs-15b.json` (vm1, vm3 y vm5 con un enlace «sin IP» hacia vm4; vm4 con salida a Internet),
  Ubuntu 24.04 minimal 1 vCPU / 1 GB / 4 GB. Slice `71c11812…`: vm1 y vm3 en **worker1**, vm4 y vm5 en **worker2**.
- **Acceso de diagnóstico:** clave ed25519 generada en `g5-gw` (la privada no sale de ahí), pasada al slice con
  `--ssh-key`; SSH a vm4 por la red `external` (10.60.10.219) y de ahí a vm1/vm3/vm5 por IPv6 de enlace local.
- **Red OpenStack (solo lectura):** ML2/Open vSwitch, redes de enlace VLAN, firewall nativo de OVS; los puertos de
  datos tienen `port_security_enabled: false`.

## Resultados

| Comprobación | Resultado |
|---|---|
| MTU 1400 en la NIC de Internet sin intervención (`ip link show ens3`) | ✅ `mtu 1400`; `/etc/netplan/90-g5-mtu.yaml` escrito; `apt` instaló `openvswitch-switch` |
| Enlaces «sin IP» al arrancar (`ip -br a`) | ✅ ens4–ens6 de vm4 y ens3 de vm1/vm3/vm5 solo con IPv6 de enlace local |
| La IP de relleno no reaparece | ❌ en b483468: volvió al instalar OVS (`netplan apply`); ✅ con 9e32610 probado en vm4 |
| 15b: `br0` con ens4, ens5, ens6 (sin ens3 de Internet) | ✅ `ovs-vsctl show` |
| 15c: 10.100.10.1/3/5 en vm1/vm3/vm5 | ✅ |
| 15d: vm3 ve el ARP broadcast de vm1 y ningún ICMP | ✅ (`tcpdump` en vm3: 3 `Request who-has 10.100.10.5 tell 10.100.10.1`) |
| 15e: `ping -c3 10.100.10.5` desde vm1 | ❌ 0/3, «Destination Host Unreachable» |

## Diagnóstico del 15e

Capturas simultáneas (`tcpdump -en`) durante el ping:

- vm5 recibe el ARP de vm1 y responde `Reply 10.100.10.5 is-at fa:16:3e:eb:b5:21` (dirigido a la MAC de vm1).
- En vm4, esa respuesta **entra por ens6** (hacia vm5) **y sale por ens4** (hacia vm1): el OVS reenvía bien; su tabla
  MAC (`ovs-appctl fdb/show br0`) tiene vm1 en el puerto de ens4 y vm5 en el de ens6.
- vm1 **no recibe** ninguna respuesta: la trama se pierde entre worker2 y worker1.

**Contraprueba:** con `br0` solo con ens4 y ens6 (sin el enlace hacia vm3, que está en worker1), el mismo ping
recibe respuesta (ARP resuelto, `ICMP echo reply` en vm1).

**Interpretación:** con ens5 en el bridge, el broadcast de vm1 vuelve a worker1 por la VLAN del enlace vm3–vm4 con la
MAC de origen de vm1. Todo indica que el tramo físico entre los workers aprende MACs de forma compartida entre VLANs
y pasa a creer que vm1 está detrás de worker2; entonces descarta el unicast hacia vm1 que sale de worker2. Neutron
(OVS, VLAN) aprende por VLAN, así que el problema está fuera de nuestro código. No hay acceso a los workers ni al
switch para confirmarlo; queda para el JP.

**Mitigaciones posibles (sin implementar):** (1) que el JP ajuste el aprendizaje de MAC por VLAN en el tramo físico;
(2) ubicar la VM switch y sus vecinas de enlaces «sin IP» en el mismo compute (con 0,5 GB por VM, como el Anexo, las
cuatro caben en uno), con afinidad en el VM Placement o fijando `host` en la topología.
