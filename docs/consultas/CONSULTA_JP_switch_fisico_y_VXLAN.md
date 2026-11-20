# Consulta al JP: el switch físico del clúster Linux y la VM switch entre servidores

**Grupo 5 · TEL141 · 21/11/2026**

## 1. Resumen

- **Qué falla:** una topología donde una VM hace de switch (OVS) entre VMs de **distintos servidores** no funciona
  sobre el switch físico del laboratorio. Es el paso 15e del Ex2.
- **Dónde se pierde el tráfico:** demostramos con capturas, en la tarjeta física de cada servidor, que la respuesta se
  pierde **dentro del switch físico**.
- **Lo que probamos:** una alternativa con **túneles VXLAN entre servidores**. Así funciona.
- **El conflicto:** la rúbrica pide usar VLANs y **no túneles** en el clúster Linux (EX2-R5-I-01). Por eso
  necesitamos el criterio del JP.

## 2. Cómo debía funcionar (diseño original, con el switch físico)

```
   VM1            VM2 (OVS)            VM3
 server1           server2           server3
    │                 │                 │
    └──── switch físico del laboratorio ┘
          (cada enlace del slice = una VLAN)
```

- Cada enlace del slice viaja por el switch físico dentro de una **VLAN** (QinQ: VLAN externa + VLAN interna).
- Es lo que pide la rúbrica:
  - EX2-R5-I-01 (15 %): usar VLANs, no túneles;
  - EX1-R2-EXTRA-02: QinQ;
  - EX2-R5-I-06 (25 %): configurar dinámicamente el switch físico.

## 3. Qué pasa

**Prueba (20/11/2026):** VM1 hace ping a VM3 y la respuesta nunca llega («Destination Host Unreachable»). Topología
probada: VM1 (server1) – VM2 Ubuntu con OVS (server2) – VM3 (server3).

### Cómo aprende un switch

- El switch anota «la MAC X está en el puerto N» según la **MAC de origen** de cada trama que entra.
- Si el destino está en el mismo puerto por el que entró la trama, la **descarta**.

### Paso a paso

| Paso | Qué ocurre | Tabla del switch |
|---|---|---|
| 1 | VM1 envía un ARP (broadcast) por la VLAN del enlace l12 → entra por el puerto de **server1** | VM1 → puerto server1 ✔ |
| 2 | VM2 (OVS) lo reenvía por el enlace l23: sale de server2 **con la MAC de VM1** | **VM1 → puerto server2** ✘ (sobrescribe) |
| 3 | VM3 responde a VM1; el switch la manda a server2 (correcto: debe pasar por VM2) | — |
| 4 | VM2 reenvía la respuesta hacia VM1: entra por el puerto de server2 | Destino VM1 = puerto de entrada → **descartada** |

Si el switch tuviera **una tabla de MAC por VLAN**, en el paso 2 anotaría a VM1 en server2 **solo para la VLAN de
l23**, y la conservaría en server1 para la VLAN de l12. La respuesta llegaría. Por eso concluimos que **el switch
aprende las MAC en una sola tabla para todas las VLANs**.

## 4. Evidencia

**Capturas** con `tcpdump -eni ens4` en las tarjetas físicas, filtradas por la MAC de VM1. Fecha: 20/11/2026,
04:43–04:47.

| Servidor | Lo que se vio | Conclusión |
|---|---|---|
| server3 | Llega el ARP por la VLAN externa 1001 y **VM3 responde** por la 1001 | VM3 funciona |
| server2 | Entra la respuesta (VLAN 1001) y **sale hacia VM1 por la VLAN 1000** | VM2 y su OVS funcionan |
| server1 | **Nunca llega la respuesta**; solo se ven los ARP de VM1 | Se pierde **en el switch físico** |

- **Antes de las capturas:** ya habíamos cambiado el orquestador para usar **una VLAN externa distinta por enlace**
  (antes era una por slice). La falla siguió igual, así que no depende de cómo asignemos las VLANs.
- **También en OpenStack (15/11/2026):** el paso 15e falla con el mismo patrón entre worker1 y worker2, aunque
  Neutron ya usa una VLAN por red. Si se quita del bridge el enlace hacia el otro compute, funciona.
- **Lo que no se afecta:** las topologías comunes (lineal, anillo, malla, sin VM switch), porque cada MAC entra
  siempre por el mismo puerto.

## 5. Lo que probamos: túneles VXLAN

Cada servidor mete las tramas de las VMs **dentro de un paquete UDP** dirigido al otro servidor. El switch físico solo
ve las MAC de los **servidores**, que nunca cambian de puerto:

```
[ MAC server1 → MAC server4 | UDP 4789 | VNI 1000 | trama original de VM1 ]
```

- Los túneles forman una estrella con centro en server4, que es la puerta de los slices. Así no hay lazos.
- Van por la red de gestión (192.168.201.x).
- **Resultado:** el ping de VM1 a VM3 **funciona** a través de la VM switch.

**Problema:** usar túneles en el clúster Linux contradice **EX2-R5-I-01**. Y al no pasar las VLANs del slice por el
switch, **EX2-R5-I-06 pierde sentido**: sería configurar el switch para limitar broadcasts que ya no lo atraviesan.

## 6. Opciones

| Opción | Cumple la rúbrica (VLAN, R5-I-06) | VM switch entre servidores (15e) | Quién actúa |
|---|---|---|---|
| **A. Configurar el switch físico** para que aprenda por VLAN | ✅ | ✅ | JP / laboratorio, o nosotros con acceso al switch |
| **B. VXLAN** (lo que funciona hoy) | ❌ R5-I-01 y R5-I-06 | ✅ | Ya implementado |
| **C. VLAN por defecto y VXLAN solo como opción para la VM switch** | Parcial | ✅ con VXLAN | Ya implementado (una línea de configuración) |
| **D. VLAN, y en la demo poner la VM switch y sus vecinas en el mismo servidor** | ✅ | ✅ en ese caso | Ya posible (fijar servidores) |

Notas:

- **Opción A.** Es la única que cumple todo. Además, EX2-R5-I-06 exige que el orquestador **configure el switch
  físico**, así que de todos modos necesitamos acceso a él. Desde el gateway, 192.168.201.5 (ovs1) responde «No route
  to host».
- **Opción D.** Hoy no cabe: cada servidor tiene ~6 GB libres, y la Ubuntu de la VM switch más dos CirrOS superan lo
  disponible. El paso 3 del Ex2 además fija servidores distintos.

**Nuestra propuesta: A.** Mientras se resuelve, usar **C**: QinQ por defecto, conforme a la rúbrica, y VXLAN solo
para demostrar el 15e, explicando por qué.

## 7. Preguntas para el JP

1. **¿Cómo está configurado el switch físico del clúster Linux?** ¿Es ovs1 (192.168.201.5) u otro equipo? ¿Aprende
   las MAC por VLAN o con una tabla compartida? ¿Interpreta el QinQ (802.1ad)?
2. **¿Se puede configurar para que aprenda por VLAN?** O, ¿se nos puede dar acceso para hacerlo? (También lo
   necesitamos para EX2-R5-I-06.)
3. **¿Se acepta VXLAN** al menos para el caso de la VM switch entre servidores, explicando la limitación del switch?
   ¿O el 15e debe hacerse solo con VLANs?
4. **En la demo del 15e**, ¿la VM switch y sus vecinas pueden estar en servidores distintos? ¿O se espera que el JP
   elija la ubicación?
5. **En OpenStack**, el 15e falla igual entre computes. ¿Es la misma situación del switch físico? ¿Se puede revisar?

## 8. Estado actual del orquestador

| Aspecto | Estado |
|---|---|
| Transporte entre servidores Linux | Configurable con `transport`: `qinq` (una VLAN externa por enlace) o `vxlan`. **Hoy está en `vxlan`** en el app server |
| Volver a QinQ | Cambiar una línea de la configuración (respaldo `cluster.json.bak-20261120`) y reiniciar el platform-manager |
| Evidencia detallada | `docs/evidencias/F2/MS-22_capacidad_de_disco_y_vm_switch_linux.md` (capturas y números) |
| Commit de VXLAN | `6aae2db` (aún no subido a GitHub) |
