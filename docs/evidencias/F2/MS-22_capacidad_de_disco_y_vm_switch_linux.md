# MS-22 — Disco de los servidores Linux, VM Placement y VM switch entre servidores

- **Fecha:** 19–20/11/2026. Despliegues autorizados por el usuario.
- **Revisiones:** de ebae57b a fb245a8 (rama `fase2`).
- **Agente:** reinstalado por el usuario en server1–4 (sha256 `bc24a0cd…`, commit ce95c4a).

## 1. Por qué una VM «no cabe» en un servidor Linux

### Lo que ocupa una VM en el disco

- **Imagen base:** el archivo de la imagen. Se guarda **una vez por servidor** y la comparten las VMs de ese
  servidor.
- **Disco de la VM:** un archivo QCOW2 *overlay*. Es *thin*: empieza en unos KB y crece a medida que la VM escribe,
  hasta el tamaño pedido.

### Lo que exige el agente antes de crear la VM

El agente reserva el **peor caso**. Así evita que, si los discos crecen a la vez, el servidor se llene y las VMs se
congelen o corrompan.

> disco libre real ≥ crecimiento completo de los discos reservados + imágenes base que falten + margen de 2 GB

Por eso, aunque QCOW2 es *thin*, la admisión se calcula como si el disco fuera completo. OpenStack hace lo mismo:
Nova descuenta el disco completo del flavor de los 9 GB de cada compute.

### El tamaño mínimo del disco

El disco de la VM no puede ser menor que el **disco virtual de la imagen**. Si lo fuera, el agente responde «Disco
menor que la imagen base».

| Imagen | Archivo (base) | Disco virtual | Disco mínimo de la VM |
|---|---|---|---|
| CirrOS 0.6.2 (`cirros-062`) | 20 MB | 0,11 GiB | 1 GB |
| Ubuntu 20.04 (`focal-server-cloudimg-amd64`) | 942 MB | 2,2 GiB | **2,5 GB** |
| Ubuntu 24.04 minimal | 1 447 MB | 3,5 GiB | 4 GB |

### Números reales (20/11/2026, servidores vacíos)

| Servidor | Disco libre real | Disponible tras el margen de 2 GB |
|---|---|---|
| server1 | 5 714 MB | 3 666 MB |
| server2 | 5 991 MB | 3 943 MB |
| server3 | 5 697 MB | 3 649 MB |

Lo que necesita cada Ubuntu para entrar en esos números:

| Ubuntu | Cálculo | Total | ¿Cabe? |
|---|---|---|---|
| 20.04 con 2,5 GB | 2 560 + 942 (imagen) | 3 502 MB | ✅ en cualquiera de los tres |
| 20.04 con 2 GB | — | — | ❌ menor que su disco virtual |
| 24.04 con 4 GB | 4 096 + 1 447 | 5 543 MB | ❌ en ninguno |
| 24.04 con 2,5 GB | — | — | ❌ menor que su disco virtual |

**Consecuencia:** en Linux, una Ubuntu tiene que ser la 20.04 con 2,5 GB, y queda **sola** en su servidor. Una
CirrOS más ya no entra: 3 502 + 1 024 supera los ~3,9 GB disponibles.

## 2. Corrección del VM Placement (25875bd)

**Antes:** para Linux, el placement usaba la capacidad configurada en `cluster.json` (6 GB por servidor).

- Creía que la Ubuntu y las dos CirrOS cabían en un servidor y las juntaba.
- Después, el agente medía el disco real y rechazaba el slice entero.
- Le pasó al usuario dos veces el 19/11 (slices `lineal-3` en server1 y server2).

**Ahora:** el placement aplica la misma cuenta que el agente:

> disco disponible = disco libre real − margen de 2 GB − discos ya reservados − imágenes base del slice

- La cuenta es conservadora: supone que cada servidor podría necesitar todas las imágenes del slice.
- Si el monitoreo no trae el disco libre, se usa la capacidad configurada.

**Prueba en seco con los datos reales** (sin desplegar). Slice VM1 (CirrOS) – VM2 (Ubuntu 20.04, 2,5 GB) – VM3
(CirrOS):

| VM | Servidor que eligió el placement |
|---|---|
| VM1 | server1 |
| VM2 | **server2** (sola) |
| VM3 | server1 |

El placement **llena un servidor y pasa al siguiente** sin que el usuario fije nada.

## 3. Otros arreglos que salieron de esta prueba

| Commit | Arreglo |
|---|---|
| ebae57b | Disco decimal (2,5 GB) en el slice-manager. Antes, el placement lo truncaba a 2 GB y la vista del slice fallaba |
| ed77be8 | En Linux, una VM Ubuntu **con Internet** perdía el usuario y la contraseña del slice y el despliegue fallaba |
| 2812c9a | Las imágenes con nombre de versión de Canonical (`focal`, `jammy`, `noble`) se reconocen como Ubuntu |
| fb245a8 | El editor web ofrece el tamaño «Ubuntu 20.04 · 1 vCPU · 1 GB · 2,5 GB (Linux)». OpenStack no tiene flavor de 2,5 GB |

## 4. VM switch entre servidores (OVS en VM2) — pendiente

**Topología:** VM1 – VM2 – VM3 en server1, server2 y server3. VM2 es Ubuntu con Open vSwitch y une los enlaces
l12 y l23, que no tienen IP. VM1 tiene 10.100.10.1 y VM3 tiene 10.100.10.3.

**Resultado:** el ping de VM1 a VM3 falla con «Destination Host Unreachable», aunque el OVS de VM2 aprende las dos
MAC.

### Corrección hecha (ce95c4a): una S-VLAN por enlace

Antes, todos los enlaces de un slice compartían una sola VLAN externa. El `br-int` de server2 aprendía la MAC de VM1
en su propio puerto local y descartaba la respuesta. Ahora cada enlace tiene su S-VLAN: l12 → 1000, l23 → 1001,
Internet → 1002.

### Capturas en las tarjetas físicas (`tcpdump` en `ens4`, 20/11, 04:43–04:47)

| Punto | Lo que se vio |
|---|---|
| server3 | Llega el ARP de VM1 por la VLAN 1001; **VM3 responde** (`Reply 10.100.10.3`) por la VLAN 1001 |
| server2 | Llega el Reply por la VLAN 1001 y **sale por la VLAN 1000** hacia VM1 (el OVS de VM2 lo reenvía) |
| server1 | **Nunca llega el Reply**; solo se ven los ARP de VM1 |

**Conclusión:** la trama se pierde dentro del **switch físico del laboratorio**.

- Ese switch aprende las MAC sin separar por VLAN.
- Al ver la MAC de VM1 entrar también por el puerto de server2 (la copia que reenvía VM2), cree que VM1 está en
  server2.
- Por eso descarta la respuesta, que llega justamente por ese puerto.

**Pendiente:**

- que el switch aprenda por VLAN (lo configura el laboratorio); o
- que el orquestador lleve el tráfico entre servidores en **túneles VXLAN**, para que el switch solo vea las MAC de
  los servidores. El MTU de las VMs ya es 1450, lo que requiere VXLAN.

**Topologías que no se ven afectadas:**

- las comunes, sin una VM que haga de switch;
- una VM switch cuyas vecinas estén en su mismo servidor.

### Relación con OpenStack (MS-21)

En OpenStack falló el mismo paso (Ex2 15e) con el mismo patrón:

- La respuesta sale del OVS de vm4 y se pierde entre worker2 y worker1.
- Si se quita del bridge el enlace hacia la VM del otro compute, funciona.

En OpenStack cada red ya usaba su propia VLAN, y aun así falló. Eso indica que el switch físico de los computes
también aprende las MAC sin separar por VLAN.
