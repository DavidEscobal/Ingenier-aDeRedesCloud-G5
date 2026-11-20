# Consulta al JP: la VM switch entre servidores (Ex2 paso 15e)

**Grupo 5 · TEL141 · 21/11/2026**

## 0. Guion para explicarlo en 1 minuto

> «En el paso 15 una VM hace de switch con OVS. Cuando esa VM y sus vecinas quedan en **servidores distintos**, el
> ping no responde.
>
> Lo diagnosticamos con `tcpdump` en la tarjeta de datos de cada servidor:
>
> - el ARP llega a la VM destino y esta responde;
> - la VM switch reenvía la respuesta hacia la VM de origen;
> - pero la respuesta **nunca llega** al servidor de origen. Se pierde en el switch que une los servidores.
>
> La causa es que ese switch aprende las MAC **en una sola tabla para todas las VLANs**. Cuando la VM switch reenvía
> una trama de VM1 desde otro servidor, el switch ve la MAC de VM1 entrar por un segundo puerto. Cree que VM1 se
> mudó, y la respuesta dirigida a VM1 la descarta, porque llega por el mismo puerto donde cree que está VM1.
>
> No es un error del orquestador:
>
> - las topologías normales funcionan;
> - con las VMs en el mismo servidor funciona;
> - usamos una VLAN distinta por enlace y siguió fallando.
>
> Probamos túneles VXLAN y funcionó, porque el switch ya no ve las MAC de las VMs. Pero la rúbrica pide no usar
> túneles, así que lo dejamos solo como opción. Necesitamos que el switch aprenda por VLAN, o más disco para poner
> la VM switch y sus vecinas en el mismo servidor.»

**Si pregunta «¿cómo sabes que es el switch?»:** las capturas muestran la respuesta saliendo de server2 por la VLAN
correcta y no llegando nunca a server1. Entre esos dos puntos solo está el switch.

**Si pregunta «¿por qué una sola tabla?»:** si aprendiera por VLAN, anotaría a VM1 en server2 solo para la VLAN del
otro enlace, y la conservaría en server1 para la suya. La respuesta llegaría.

## 1. Lo que se evalúa: el paso 15 se hace en OpenStack

Según el documento del Ex2 (2026-1, de referencia):

- **Paso 3:** VMs sueltas en servidores fijados, en Linux y en OpenStack. No hay VM switch.
- **Paso 11:** la topología del Anexo se despliega **solo en OpenStack**.
- **Paso 15 (b–e):** VM4 hace de switch OVS y VM1 hace ping a VM5, **sobre el despliegue de OpenStack**.

En el examen, la VM switch **se evalúa en OpenStack**. En Linux usamos VLANs (QinQ) como pide la rúbrica.

## 2. Qué pasa (igual en Linux y en OpenStack)

| Paso | Qué ocurre | Tabla del switch |
|---|---|---|
| 1 | VM1 envía un ARP (broadcast) por la VLAN de su enlace → entra por el puerto de **su servidor** | VM1 → puerto del servidor de VM1 ✔ |
| 2 | La VM switch lo reenvía por otro enlace: sale de **su** servidor **con la MAC de VM1** | **VM1 → puerto del servidor de la VM switch** ✘ (sobrescribe) |
| 3 | El destino responde a VM1; el switch la manda a la VM switch (correcto) | — |
| 4 | La VM switch reenvía la respuesta hacia VM1: entra por su propio puerto | Destino = puerto de entrada → **descartada** |

**Cuándo ocurre:**

| Ubicación | Resultado |
|---|---|
| VM switch y todas sus vecinas en el **mismo** servidor | ✅ Siempre funciona: nada cruza el switch |
| Una vecina en otro servidor | ⚠️ Intermitente: se corta cuando esa vecina hace broadcast |
| VM switch sola, o vecinas en otros servidores | ❌ Falla |
| Topologías sin VM switch | ✅ Funcionan: cada MAC entra siempre por el mismo puerto |

## 3. Evidencia

### Linux (20/11/2026)

- **Topología:** VM1 en server1, VM2 Ubuntu con OVS en server2, VM3 en server3.
- **Capturas:** `tcpdump -eni ens4` en cada servidor.
- **Configuración:** el orquestador ya usaba **una VLAN externa distinta por enlace**.

| Servidor | Lo que se vio |
|---|---|
| server3 | Llega el ARP (VLAN 1001) y **VM3 responde** por la 1001 |
| server2 | Entra la respuesta (VLAN 1001) y **sale hacia VM1 por la VLAN 1000** |
| server1 | **Nunca llega la respuesta** |

### OpenStack (15/11/2026)

- **Mismo patrón:** la respuesta sale del OVS de vm4 (worker2) y no llega a vm1 (worker1).
- **Contraprueba:** si se quita del bridge el enlace hacia la VM del otro compute, funciona.
- **Configuración:** cada red de Neutron ya tiene su propia VLAN.

### Dato adicional para el JP

Las tarjetas de datos y de gestión de server1–4 tienen MAC `fa:16:3e:…`, el prefijo de puertos de **OpenStack**.
Nuestros «servidores» son VMs de la infraestructura del laboratorio, y el «switch físico» probablemente sea una **red
virtual**. Si esa red trata nuestras etiquetas VLAN como datos y aprende todas las MAC juntas, eso explica la falla.

## 4. Alternativa probada: túneles VXLAN (solo Linux)

- **Cómo funciona:** cada servidor mete las tramas de las VMs dentro de un paquete UDP hacia otro servidor. El switch
  solo ve las MAC de los servidores.
- **Resultado:** **funcionó** el 20/11/2026 (ping de VM1 a VM3 a través de la VM switch).
- **Problema:** contradice **EX2-R5-I-01** (no usar túneles en Linux) y deja sin sentido **EX2-R5-I-06** (configurar
  el switch físico).
- **Decisión:** se volvió a **QinQ** (21/11/2026). VXLAN queda solo como opción (`"transport": "vxlan"`).
- **OpenStack:** el transporte lo decide Neutron (VLAN), así que VXLAN no aplica.

## 5. Opciones para el paso 15e en OpenStack

| Opción | ¿Funciona? | Quién |
|---|---|---|
| **A. El switch de los computes aprende por VLAN** | ✅ en cualquier ubicación | JP / laboratorio |
| **B. VM4, VM1, VM3 y VM5 en el mismo compute** | ✅ | Necesita **≥ 12 GB** (4 × 3 GB); hoy hay **9 GB** → JP (más disco) |
| **C. VMs más chicas en la demo** (CirrOS para VM1, VM3, VM5) | ✅ si caben en un compute | Que el JP lo acepte |
| D. VXLAN en Neutron | ✅ | ❌ Contradice la rúbrica («no self-service») |

En Linux, la opción B también es posible: el agente reservaría disco *thin* para las VMs pequeñas, o bajaría su
margen de 2 GB. Es un cambio nuestro.

## 6. Preguntas para el JP

1. El «switch» que une los servidores de Linux y los computes de OpenStack, **¿es un equipo físico o una red
   virtual** de la infraestructura (las MAC `fa:16:3e` lo sugieren)? ¿Aprende las MAC por VLAN?
2. ¿Se puede **configurar para que aprenda por VLAN**, o darnos acceso? (También lo pide EX2-R5-I-06.)
3. Para el 15e, **¿la VM switch y sus vecinas pueden ir en el mismo compute?** Si es así, ¿se puede ampliar el disco
   de los computes (9 GB) o usar VMs más chicas?
4. ¿Se acepta **VXLAN en Linux** como alternativa documentada, o debe ser solo VLAN?
5. ¿Hay alguna configuración del laboratorio de ciclos anteriores que debamos conocer?

## 7. Estado actual del orquestador

| Aspecto | Estado |
|---|---|
| Transporte en Linux | **QinQ**, una VLAN externa por enlace (desde el 21/11/2026). VXLAN disponible con `"transport": "vxlan"` |
| Evidencia detallada | `docs/evidencias/F2/MS-21_ovs_15b_openstack.md` (OpenStack) y `MS-22_capacidad_de_disco_y_vm_switch_linux.md` (Linux) |
