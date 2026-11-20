# Ex2: capacidad para el Anexo, la VM switch (paso 15) y el placement

**Grupo 5 · TEL141 · 21/11/2026.**

Los números de capacidad salen del monitoreo del orquestador (Nova y agentes Linux) y de pruebas reales. El orden de
los pasos y los tamaños de las VMs salen del documento del Ex2 2026-1, que usamos como referencia: el de 2026-2
puede variar.

---

## 1. ¿Por qué no cabe el Anexo si antes se despliega el paso 3?

### Lo que pide cada paso

| Paso | Qué se despliega | VMs en OpenStack | Imagen | Tamaño |
|---|---|---|---|---|
| 3 | VMs sueltas en servidores fijados | worker1: 2 · worker2: 1 · worker3: libre | Ubuntu 24.04 minimal | 1 vCPU · 1 GB RAM |
| 11 | Topología del Anexo (6 VMs) | Las decide el placement | 24.04 (VM1, 3, 4, 5) y 20.04 (VM2, 6) | 1 vCPU · 0,5 GB RAM · 2,5 GB disco |

### El disco es el recurso que falta

- **Disco por compute:** cada compute de OpenStack tiene **9 GB** de disco local.
- **Disco por VM Ubuntu 24.04:** necesita un disco de **al menos 4 GB**.
  - Su disco virtual mide 3,5 GiB, y Nova no acepta un disco menor que la imagen.
  - Los flavors de Nova usan GB enteros.
  - Por eso los 2,5 GB del Anexo no alcanzan para la 24.04.
- **Ubuntu 20.04:** su disco virtual mide 2,2 GiB. Con 3 GB bastaría, pero el flavor más cercano que existe es de
  4 GB.

| | worker1 | worker2 | worker3 | Total |
|---|---|---|---|---|
| Capacidad | 9 GB | 9 GB | 9 GB | 27 GB |
| Ocupado por el paso 3 | 8 GB (2 VMs) | 4 GB (1 VM) | 0 | 12 GB |
| **Libre para el Anexo** | **1 GB** | **5 GB** | **9 GB** | **15 GB** |
| VMs de 4 GB que caben | 0 | 1 | 2 | **3** |
| **El Anexo necesita** | | | | **6 VMs = 24 GB** |

**Conclusión:** con el paso 3 desplegado, el Anexo **no cabe**. Faltan 9 GB, o sea, 3 VMs. El placement lo rechaza
antes de crear nada, con el motivo «disco insuficiente».

- **La RAM sí alcanza:** el paso 3 usa 3 GB y el Anexo 3 GB, sobre ~11,8 GB entre los tres computes.
- **Sin el paso 3, sí cabe:** prueba en seco del 21/11/2026, sección 3.

### En el clúster Linux también hay límite

- Cada servidor tiene ~6 GB libres de disco real.
- El agente exige, para cada VM: su disco completo, más la imagen base, más 2 GB de margen.
- Una Ubuntu 24.04 de 4 GB necesita ~7,5 GB, así que **no cabe en ningún servidor Linux**.
- El paso 3 en Linux (2 VMs en server2 y 1 en server3, todas Ubuntu 24.04) tampoco puede cumplirse con el disco
  actual.
- Solo cabe la Ubuntu 20.04 con 2,5 GB, y una por servidor (evidencia MS-22).

### Lo que necesitamos del JP

- Más disco en los computes y en los servidores Linux; o
- autorización para que las VMs arranquen desde un volumen (OpenStack); o
- confirmar si el Anexo se despliega **después de borrar** las VMs del paso 3.

---

## 2. ¿Por qué falla la VM switch (paso 15e)?

### Qué se espera

VM4 hace de switch con OVS y une a VM1, VM3 y VM5. Desde VM1 se hace `ping 10.100.10.5`:

- VM1 envía un **ARP request** (broadcast): «¿quién tiene 10.100.10.5?».
- VM4 lo reenvía (*forward*) a VM3 y VM5. Las dos lo reciben (15d ✅).
- VM5 contesta con un **ARP reply** (unicast) dirigido a VM1.
- VM4 debería reenviar ese reply hacia VM1. **Ese reply nunca llega a VM1**, y el ping falla con «Destination Host
  Unreachable».

El OVS de VM4 sí reenvía bien la respuesta. **La que se pierde es la trama, en el switch que une los computes.**

### Cómo aprende un switch

Un switch guarda una tabla «MAC → puerto»:

- la llena mirando la **MAC de origen** de cada trama que le entra;
- envía cada trama solo por el puerto donde está la **MAC de destino**;
- si el destino está en el **mismo puerto por donde entró**, la **descarta**.

### Lo que pasa, paso a paso

Ubicación que elige el placement: VM1 en worker1, VM4 en worker2, VM5 en worker3.

```
 worker1 (VM1)          worker2 (VM4 = OVS)          worker3 (VM5)
      │ puerto A               │ puerto B                 │ puerto C
      └──────────── switch que une los computes ──────────┘
```

| # | Qué ocurre | Tabla del switch |
|---|---|---|
| 1 | VM1 envía el ARP request; entra por **A** | VM1 → A ✔ |
| 2 | VM4 lo reenvía hacia VM5: sale de worker2 **con la MAC de VM1** y entra por **B** | **VM1 → B** ✘ (sobrescribe) |
| 3 | VM5 responde (ARP reply) a VM1; el switch lo manda a **B** (correcto: debe pasar por VM4) | VM5 → C |
| 4 | VM4 reenvía el reply hacia VM1: entra por **B**, y el switch cree que VM1 está en **B** | Destino = puerto de entrada → **descartado** ✘ |

**El problema no es el OVS de VM4.** Es que el switch físico **aprende las MAC en una sola tabla para todas las
VLANs**. Si tuviera una tabla por VLAN, en el paso 2 anotaría a VM1 en B solo para la VLAN del enlace VM4–VM5, y la
seguiría teniendo en A para la VLAN del enlace VM1–VM4. El reply llegaría.

### Evidencia

- **OpenStack (15/11/2026):** la respuesta sale de vm4 y no llega a vm1. Si se quita del bridge el enlace hacia la
  VM del otro compute, el ping funciona. Cada red de Neutron tiene su propia VLAN, y aun así falla.
- **Linux (20/11/2026):** `tcpdump` en la tarjeta de datos de los tres servidores:
  - server3: VM3 responde;
  - server2: la respuesta entra y sale hacia VM1 por la VLAN correcta;
  - server1: la respuesta **nunca llega**.

### Cuándo pasa y cuándo no

| Ubicación de las VMs | Resultado |
|---|---|
| VM switch y **todas** sus vecinas en el mismo servidor | ✅ Funciona: las tramas no cruzan el switch |
| Una o más vecinas en otro servidor | ❌ Falla (o intermitente) |
| Topologías sin VM switch (lineal, anillo, malla…) | ✅ Funcionan: cada MAC entra siempre por el mismo puerto |

**Por qué no lo vimos en el LAB3:** es la misma infraestructura (`br-int` en cada servidor, `ens4` y el switch
central OFS), pero ahí ninguna VM reenviaba tramas de otras.

**Por qué G2 no lo reporta:** su documento dice que «no se enfocaron en la configuración de capa 2». Configuraron la
VM como OVS (pp. 87–88), pero no muestran ping ni capturas entre servidores.

### Soluciones posibles (cumpliendo el Ex2: VLANs, sin túneles)

| Opción | Funciona | Quién |
|---|---|---|
| El switch central aprende por VLAN, o inunda las VLANs de los slices en vez de aprender | ✅ Con cualquier ubicación | JP / laboratorio |
| VM4, VM1, VM3 y VM5 en el mismo compute | ✅ | Necesita 16 GB en un compute (hay 9) → JP |
| Túneles VXLAN | ✅ (probado en Linux) | ❌ La rúbrica lo penaliza (EX2-R5-I-01) |

---

## 3. ¿Cómo decide nuestro placement?

### Qué recibe y qué devuelve

- **Recibe:**
  - del monitoreo, el estado actual de cada servidor: capacidad, uso, salud, zona;
  - la lista de VMs del slice, con vCPU, RAM, disco y servidor fijado (si lo hay).
- **Devuelve:** el servidor de cada VM, o un rechazo con el motivo. En OpenStack el plan se cumple con
  `availability_zone = "zona:host"`.

### Reglas

| Recurso | Regla |
|---|---|
| vCPU asignadas | Hasta 2 por núcleo |
| CPU real usada | ≤ 85 % de los núcleos |
| RAM | Sin sobreasignar |
| Disco | Sin sobreasignar. En Linux se descuentan, además, el margen de 2 GB y las imágenes base |
| Zona | Solo servidores de la zona pedida, sanos y con datos de monitoreo de ≤ 15 s |
| Slice completo | O caben todas las VMs o no se crea ninguna |

### Algoritmo (BCDP v2)

Objetivo: **ocupar la menor cantidad de servidores vacíos**, para dejar servidores libres para otros slices.

1. Ubica primero las VMs que el usuario fijó en un servidor.
2. **Llena primero los servidores que ya están en uso.** No aumenta el número de servidores ocupados.
3. Si hay que abrir un servidor vacío, elige el que más VMs puede absorber.
4. Revisa el plan con un verificador independiente y lo reserva de forma atómica. Si otro slice ganó el espacio,
   vuelve a calcular.

### Prueba en seco del Anexo (21/11/2026, computes vacíos, sin desplegar)

| Compute | VMs |
|---|---|
| worker1 | VM1, VM2 |
| worker2 | VM3, **VM4** |
| worker3 | VM5, VM6 |

El plan es válido: 2 VMs de 4 GB por compute. VM4 queda con VM3, pero **separada de VM1 y VM5**, así que el 15e
fallará por el problema de la sección 2.

### Si hubiera recursos suficientes para el paso 3 y el Anexo juntos

- **Orden de llenado:** el placement completaría primero los computes ya ocupados por el paso 3 (worker1 y worker2)
  y abriría worker3 solo si hiciera falta. No reparte las VMs «una en cada uno».
- **Zona:** si se pide una zona (paso 2: servidores 2–4), solo considera esos servidores. Los demás aparecen como
  «descartados» con su motivo.
- **Lo que no hace hoy:** el placement no sabe que **VM4 es un switch** que conviene ubicar con sus vecinas. Puede
  juntarlas por casualidad, pero no lo garantiza. Mejora propuesta: una regla de afinidad «la VM switch y sus vecinas
  en el mismo servidor», que solo sirve si caben.

---

## 4. Otros puntos importantes para la presentación

| Tema | Situación |
|---|---|
| Paso 2: zona con servidores 2–4 | El placement filtra por zona. En el clúster solo existe la zona `nova` de OpenStack; crear zonas requiere permisos de administración (JP) |
| Paso 6: procesos QEMU en los workers de OpenStack | No tenemos SSH a los workers |
| Paso 17: SSH desde fuera a VM4 y VM5 | Funciona pasando por el gateway (`ssh -J g5-gw`). La VPN no tiene ruta a 10.60.10.0/24 |
| Imágenes | Están cargadas: Ubuntu 24.04 minimal y 20.04 (`focal-server-cloudimg-amd64`). La 20.04 se reconoce como Ubuntu |
| Disco del Anexo (2,5 GB) | En OpenStack se usa 4 GB (GB enteros en Nova; la 24.04 necesita ≥ 3,5 GiB). En Linux, la 20.04 sí acepta 2,5 GB |
| Transporte en el clúster Linux | QinQ, con una VLAN externa por enlace (cumple EX2-R5-I-01). VXLAN implementado como opción, no activo |
| Infraestructura | Las tarjetas de los servidores tienen MAC `fa:16:3e…`: los servidores son VMs del laboratorio, y el «switch físico» probablemente sea una red virtual. Preguntar al JP |
| EX2-R5-I-06 (configurar el switch para limitar broadcasts) | Pendiente: requiere acceso al switch central |

### Prueba que puede hacer el JP

Durante el ping del 15e, ejecutar en el switch central:

```
ovs-appctl fdb/show <bridge>
```

Si la MAC de VM1 aparece en una sola entrada que **cambia de puerto**, el diagnóstico queda confirmado en su propio
equipo.

## Documentos relacionados

- `docs/consultas/CONSULTA_JP_switch_fisico_y_VXLAN.md`: la consulta, con un guion de 1 minuto.
- `docs/evidencias/F2/MS-21_ovs_15b_openstack.md`: paso 15 en OpenStack.
- `docs/evidencias/F2/MS-22_capacidad_de_disco_y_vm_switch_linux.md`: disco y capturas en Linux.
