# Cambios de la fase 1 (parcial) a la fase 2 (final) y requerimientos a evaluar

> **Documento de referencia:** `Cambios Fase1 a Fase 2 (final) + Requerimientos a evaluar(1).pdf`  
> **Extensión:** 7 páginas.  
> **Objeto de esta conversión:** transcribir el contenido del documento a Markdown, conservando tablas, valores, denominaciones y criterios de evaluación; las figuras originales se incluyen como imágenes vinculadas.  
> **Criterio de fidelidad:** las descripciones de diagramas ayudan a leerlos en texto, pero no sustituyen la imagen original. No se agregan exigencias ajenas al PDF. Los campos de «¿Cumplió?» y «EVIDENCIAS» en la rúbrica están vacíos en el documento y se mantienen sin completar.

## Índice

1. [Fases del proyecto (página 1)](#1-fases-del-proyecto-página-1)
2. [Acceso externo y rangos IP por grupo (página 2)](#2-acceso-externo-y-rangos-ip-por-grupo-página-2)
3. [Infraestructura de la fase 1 (páginas 3 y 4)](#3-infraestructura-de-la-fase-1-páginas-3-y-4)
4. [Infraestructura de la fase 2 (páginas 5 y 6)](#4-infraestructura-de-la-fase-2-páginas-5-y-6)
5. [Rúbrica de evaluación EX2: diseño y documentación (página 7)](#5-rúbrica-de-evaluación-ex2-presentación-documentación-y-diseño-página-7)
6. [Rúbrica de evaluación EX2: implementación (página 7)](#6-rúbrica-de-evaluación-ex2-implementación-página-7)
7. [Figuras originales](#7-figuras-originales)
8. [Notas de lectura y fidelidad](#8-notas-de-lectura-y-fidelidad)

---

## 1. Fases del proyecto (página 1)

**Encabezado original:** «Cambios con respecto a la fase 1(parcial) a fase 2 (final)».

### 2. FASES

El proyecto se desarrollará en dos fases a lo largo del ciclo. Al inicio, cada estudiante contará con una topología individual (Clúster Linux) que le permitirá realizar los laboratorios de manera más holgada y, si lo desea, comenzar a incorporar su código del proyecto. Aunque estas topologías sean individuales, el trabajo del proyecto es grupal desde el inicio, por lo que el código podrá desarrollarse en cualquiera de las topologías asignadas.

Tras el parcial, el trabajo será unificado en una única topología grupal que integrará tanto Clúster Linux como OpenStack. Durante la transición, los estudiantes tendrán un plazo de una semana para migrar y adaptar su código a esta nueva topología. Mayor detalle en la siguiente tabla:

| Fase | Descripción | Duración | Notas |
|---|---|---|---|
| **Fase 1 - Topología individual** | Topologías designadas para elaborar su solución usando tecnologías basadas Linux, asignadas individualmente. Los estudiantes podrán elegir cualquiera de estas topologías para ir incorporando su código del proyecto mientras realizan los laboratorios. | Desde el laboratorio 1 hasta una (1) semana después de la presentación parcial. | Estas topologías se usarán para prácticas de laboratorio y para avanzar en el proyecto de manera preliminar. |
| **Migración** | Migrar y adaptar el avance y código de la topología individual a la topología grupal. | 1 semana después del parcial. | Pasado este plazo, se eliminarán las topologías individuales. |
| **Fase 2 - Topología grupal** | Única topología compartida que incluirá Linux y OpenStack, trabajada en grupo. | Desde el parcial hasta el final del curso. | Trabajo colaborativo sobre una sola topología compartida. |

![Tabla y texto originales sobre fases](assets/imagen_original_p01_01.png)

---

## 2. Acceso externo y rangos IP por grupo (página 2)

Adicionalmente, como parte del requerimiento cinco (R5) se espera que las VMs desplegadas en su solución puedan ser accedidas desde el “exterior”, para esto se han definido rangos de IPs por grupos, las cuales serán seteadas en sus dispositivos (pueden usar DHCP). Considerar que no todas las VMs deben ser vistas desde el exterior, sino sólo las VMs que se indique explícitamente.

### 2.1 Rangos de direccionamiento

| Grupo | Linux Cluster | OpenStack Cluster |
|---:|---|---|
| 1 | `10.60.1.0/24` | `10.60.2.0/24` |
| 2 | `10.60.3.0/24` | `10.60.4.0/24` |
| 3 | `10.60.5.0/24` | `10.60.6.0/24` |
| 4 | `10.60.7.0/24` | `10.60.8.0/24` |
| **5** | **`10.60.9.0/24`** | **`10.60.10.0/24`** |

Como pueden notar, los rangos de IPs mostrados en la tabla anterior corresponden a **IPs privadas**, las cuales **sólo** podrán ser accedidas a través de una **VPN**. Si intentan conectarse a ellas desde dentro de la **UNIVERSIDAD** obtendrán errores de conexión, ya que no están disponibles a nivel **INTERNO** (Universidad), pero **sí** a través de la **VPN**. Cuando se conecte a la VPN, se configurarán rutas que permitan llegar a ellas usando como router el **Headnode del VNRT**.

**Aclaración de lectura del documento:** el acceso «desde el exterior» se describe utilizando una VPN y direcciones privadas; no se declara que estos rangos sean direcciones IP públicas.

![Tabla original de rangos de IP y acceso mediante VPN](assets/imagen_original_p02_01.png)

---

## 3. Infraestructura de la fase 1 (páginas 3 y 4)

### 3.1 Diagrama físico de fase 1 (página 3)

![Diagrama original de la infraestructura de fase 1](assets/imagen_original_p03_01.png)

**Elementos representados:**

- Un `gateway` en la parte superior.
- Cuatro servidores Linux, dibujados como cuatro nodos de cómputo.
- Un dispositivo `OFS` (switch de la topología).
- Un nodo/enlace marcado como `MP LINK`.
- Enlaces de dos tipos, identificados en la leyenda como `physical network 1 (10.0.10.X/24)` y `physical network 2`.
- El diagrama distingue visualmente los recorridos de ambas redes; no detalla las direcciones individuales de los cuatro servidores.

### 3.2 Tabla de acceso de fase 1 (página 4)

| Fase | Clúster | Dispositivo | Puerto SSH |
|---|---|---|---:|
| Fase 1 | Linux | `server1` | `5801` |
| Fase 1 | Linux | `server2` | `5802` |
| Fase 1 | Linux | `server3` | `5803` |
| Fase 1 | Linux | `server4` | `5804` |
| Fase 1 | Linux | `ofs` | `5805` |

> **Nota sobre el original:** la cabecera visual de la tabla dice «PUERTO» encima de los nombres de equipo y «DISPOSITIVO» encima de los números. En esta transcripción se reordenan los rótulos a «Dispositivo» y «Puerto SSH» para que correspondan con los datos, sin cambiar sus valores.

![Tabla original de puertos de fase 1](assets/imagen_original_p04_01.png)

---

## 4. Infraestructura de la fase 2 (páginas 5 y 6)

### 4.1 Diagrama físico de fase 2 (página 5)

![Diagrama original de la infraestructura grupal de fase 2](assets/imagen_original_p05_01.jpeg)

**Elementos que aparecen explícitamente en el diagrama:**

- Un servidor `app`, conectado a la red de la PUCP y al plano de control indicado con líneas rojas.
- Una red `PUCP` y un dispositivo `gateway` en la parte superior.
- Dos entornos diferenciados: `LINUX CLUSTER` (izquierda) y `OPENSTACK CLUSTER` (derecha).
- Cuatro servidores dibujados dentro de Linux Cluster y cuatro nodos dibujados dentro de OpenStack Cluster (la tabla de acceso precisa los nombres de los nodos).
- Dos switches de datos marcados `OVS_1` y `OVS_2`.
- Dos switches de administración marcados `MGMT SWITCH 1` y `MGMT SWITCH 2`.
- Dos redes de administración: `MGMT_1: 192.168.201.0/24` y `MGMT_2: 192.168.202.0/24`.

**Leyenda de la figura:**

| Color/línea en el dibujo | Etiqueta original de la figura | Interpretación descriptiva |
|---|---|---|
| Negra | `Subred LC 1 (Mgmt) 192.168.201.X/24` | Gestión de Linux Cluster |
| Verde grisáceo | `Subred LC 2 (Trunk)` | Troncales del clúster Linux |
| Gris | `Subred OC 1 (Mgmt) 192.168.202.X/24` | Gestión de OpenStack Cluster |
| Verde claro | `Subred OC (Trunk) 2` | Troncales del clúster OpenStack |
| Roja | `Control Network` | Red o enlaces de control representados |

La figura visualiza una **única topología grupal** que integra los dos clústeres. No proporciona en esta página un inventario de direcciones IP individuales ni todos los parámetros de configuración de los switches.

### 4.2 Tabla de acceso de fase 2 (página 6)

| Fase | Clúster | Dispositivo | Puerto SSH |
|---|---|---|---:|
| Fase 2 | Linux | `server1` | `5811` |
| Fase 2 | Linux | `server2` | `5812` |
| Fase 2 | Linux | `server3` | `5813` |
| Fase 2 | Linux | `server4` | `5814` |
| Fase 2 | Linux | `ovs1` | `5815` |
| Fase 2 | OpenStack | `headnode` | `5821` |
| Fase 2 | OpenStack | `worker1` | `5822` |
| Fase 2 | OpenStack | `worker2` | `5823` |
| Fase 2 | OpenStack | `worker3` | `5824` |
| Fase 2 | OpenStack | `ovs2` | `5825` |

![Tabla original de puertos de fase 2](assets/imagen_original_p06_01.png)

**Importante:** estos son los puertos presentados por el documento; el PDF no incluye credenciales de acceso, dirección IP del gateway, ni comandos completos de conexión SSH.

---

## 5. Rúbrica de evaluación EX2: presentación, documentación y diseño (página 7)

**Encabezado de la tabla original:** `11. TEMPLATE DE EVALUACIÓN - EX2`  
**Bloque:** `Presentación, documentación, y diseño`.

La tabla original tiene columnas `Req`, `Descripción`, `Criterios`, `Peso`, `¿Cumplió?` y `EVIDENCIAS (p.ej., sección/página del doc de arq.-diseño donde se explica el feature)`.

En la transcripción, **Peso** reproduce los pesos relativos de los criterios **dentro de cada requerimiento**. Los puntajes del requerimiento se consignan en el título. El PDF no tiene marcadas las casillas de cumplimiento.

### 5.1 R0 — Performance en presentación, temas requeridos y documentación (14 ptos)

| Criterio de evaluación | Peso | ¿Cumplió? | Evidencias |
|---|---:|---|---|
| Claridad de exposición y respuesta a preguntas | 35 | n/a | Sin completar |
| High Level Software Design claramente documentado | 35 | n/a | Sin completar |
| Reporte de pruebas: completo y bien documentado | 30 | n/a | Sin completar |

### 5.2 R3 — Diseño: Despliegue en OpenStack (12 ptos)

| Criterio de evaluación | Peso | ¿Cumplió? | Evidencias |
|---|---:|---|---|
| Consideración en diseño y fundamentación de los mínimos servicios requeridos (`Keystone`, `Horizon`, `Nova`, `Neutron & ML2 Plugin`, `Glance`) | 20 | ☐ | Sin completar |
| Uso eficiente (p. ej., paralelo, manejo de errores, auth de módulos, uso de caché) de APIs de OpenStack en el despliegue de VMs sobre OpenStack | 25 | ☐ | Sin completar |
| Permite orquestar VM usando OpenStack (topologías personalizadas y predefinidas) | 25 | ☐ | Sin completar |
| Diseño permite crear topologías capa 2 | 20 | ☐ | Sin completar |
| Permite visualizar los proyectos desplegados por usuario (p. ej., en Horizon) | 10 | ☐ | Sin completar |

### 5.3 R4 — Diseño: VM Placement (18 ptos)

| Criterio de evaluación | Peso | ¿Cumplió? | Evidencias |
|---|---:|---|---|
| Estrategia de monitoreo de recursos es consistente con el algoritmo a desarrollar y con el evitar superar el máximo nivel de congestión permitido | 15 | ☐ | Sin completar |
| Algoritmo de aprovisionamiento de VMs tiene función objetivo bien definida y sustentada | 20 | ☐ | Sin completar |
| Algoritmo considera uso eficiente (utilización) de recursos para aquellas cargas dinámicas que no consumen (en todo momento) el 100% de recursos y pueden soportar que sus recursos (p. ej., cores físicos) sean compartidos | 15 | ☐ | Sin completar |
| Algoritmo considera no solo la utilización actual, sino el estimado de la congestión durante el ciclo de vida del slice, tanto el impacto de un número grande de asignaciones de VMs con baja utilización (pero que podrían variar/aumentar en el tiempo), como el impacto de asignaciones recientes cuyo uso aún no se ve reflejado en las mediciones (p. ej., aún no bootea la VM) | 15 | ☐ | Sin completar |
| Algoritmo de aprovisionamiento de VMs considera slices como un todo, y no VMs individuales | 15 | ☐ | Sin completar |
| Algoritmo considera/limita el tiempo de ejecución para instancias (p. ej., slices) grandes | 10 | ☐ | Sin completar |
| Considera la zona de disponibilidad pedida al colocar las VMs | 10 | ☐ | Sin completar |

![Rúbrica original de presentación, documentación y diseño EX2](assets/imagen_original_p07_01.jpeg)

---

## 6. Rúbrica de evaluación EX2: implementación (página 7)

**Bloque original:** `Implementación`.

La tabla original contiene columnas de criterio, `Peso`, `¿Cumplió?` y `EVIDENCIAS (p. ej., número/ID de la prueba o pruebas que demuestran el cumplimiento del ítem)`.

### 6.1 R1B — Interfaz de usuario (UI) / gestión del ciclo de vida de slices (12 pts)

| Criterio de evaluación | Peso | ¿Cumplió? | Evidencias |
|---|---:|---|---|
| Ser independiente de la capa de infraestructura (clúster de servidores Linux, OpenStack, AWS, etc.) | 10 | ☐ | Sin completar |
| Implementación soporta concurrencia de usuarios | 10 | ☐ | Sin completar |
| Permite seleccionar slices con topologías predefinidas: lineal, malla, árbol, anillo y bus | 10 | ☐ | Sin completar |
| Permite editar slices (aún no desplegadas) combinando topologías predefinidas | 10 | ☐ | Sin completar |
| Permite editar slices (aún no desplegadas) agregando nodos y enlaces | 10 | ☐ | Sin completar |
| Permite grabar slices (aún no desplegadas) para posterior edición | 5 | ☐ | Sin completar |
| Permite exportar topologías | 5 | ☐ | Sin completar |
| Permite importar topologías | 5 | ☐ | Sin completar |
| Permite crear nuevos slices sobre la base de editar topologías importadas | 5 | ☐ | Sin completar |
| Permite especificar la configuración (capacidad) de cada máquina virtual (VM) creada | 5 | ☐ | Sin completar |
| Lista la información necesaria de los slices que le pertenecen al usuario | 5 | ☐ | Sin completar |
| Permite visualizar el consumo de recursos del sistema | 5 | ☐ | Sin completar |
| Permite borrar o editar slices previamente instanciados | 5 | ☐ | Sin completar |
| Permite importar imágenes de VMs en forma independiente de la plataforma | 5 | ☐ | Sin completar |
| Provee los tokens/credenciales necesarios para que el dueño del slice pueda acceder a la consola virtual de cada VM | 5 | ☐ | Sin completar |

### 6.2 R3 — Soporte de OpenStack (18 ptos)

| Criterio de evaluación | Peso | ¿Cumplió? | Evidencias |
|---|---:|---|---|
| Implementó OpenStack con al menos los mínimos servicios requeridos (`Keystone`, `Horizon`, `Nova`, `Neutron & ML2 Plugin`, `Glance`) | 20 | ☐ | Sin completar |
| Orquesta topologías (predefinidas y personalizadas) usando OpenStack | 30 | ☐ | Sin completar |
| Orquesta slices/topologías en capa 2 | 20 | ☐ | Sin completar |
| Uso eficiente (p. ej., paralelo) de APIs de OpenStack en el despliegue de VMs sobre OpenStack | 10 | ☐ | Sin completar |
| Borrado slices | 10 | ☐ | Sin completar |
| Permite visualizar máquinas virtuales desplegadas en Horizon | 10 | ☐ | Sin completar |

### 6.3 R4 — VM Placement (12 ptos)

| Criterio de evaluación | Peso | ¿Cumplió? | Evidencias |
|---|---:|---|---|
| Lista recursos/servidores disponibles en ambas plataformas (Linux Cluster y OpenStack) | 20 | ☐ | Sin completar |
| Entrega una asignación de VMs a servidores de acuerdo al algoritmo diseñado en caso haya capacidad | 50 | ☐ | Sin completar |
| Rechaza la asignación de VMs cuando no hay recursos disponibles, indicando la razón de la falla (logs o consola) | 20 | ☐ | Sin completar |
| Las VMs son asignadas a servidores en las zonas de disponibilidad elegidas por el usuario | 10 | ☐ | Sin completar |

### 6.4 R5 — Networking y Seguridad (14 ptos)

| Criterio de evaluación | Peso | ¿Cumplió? | Evidencias |
|---|---:|---|---|
| Usa VLANs para segmentar los enlaces/subredes minimizando el overhead (p. ej., no usa túneles en el Linux cluster ni redes «self-service» en OpenStack) | 15 | ☐ | Sin completar |
| Implementa las reglas de seguridad requeridas en los slices en el Linux cluster | 15 | ☐ | Sin completar |
| Implementa las reglas de seguridad requeridas en los slices en OpenStack | 10 | ☐ | Sin completar |
| Provee de salida a Internet a las máquinas que lo requieran (Linux Cluster y OpenStack) | 15 | ☐ | Sin completar |
| Provee acceso desde Internet (p. ej., SSH) a máquinas virtuales que lo requieran (Linux Cluster y OpenStack) | 20 | ☐ | Sin completar |
| Configuran dinámicamente el switch físico para limitar los broadcasts de cada enlace virtual a los servidores que realmente los necesiten | 25 | ☐ | Sin completar |

![Rúbrica original de implementación EX2](assets/imagen_original_p07_02.png)

---

## 7. Figuras originales

Los diagramas y las tablas de evaluación también están disponibles en formato original para contrastar visualmente la transcripción. El PDF incluye los siguientes recursos:

| Página | Recurso | Archivo |
|---:|---|---|
| 1 | Descripción y tabla de fases | `assets/imagen_original_p01_01.png` |
| 2 | R5: rangos IP y acceso mediante VPN | `assets/imagen_original_p02_01.png` |
| 3 | Topología física fase 1 | `assets/imagen_original_p03_01.png` |
| 4 | Tabla de puertos fase 1 | `assets/imagen_original_p04_01.png` |
| 5 | Topología física fase 2 | `assets/imagen_original_p05_01.jpeg` |
| 6 | Tabla de puertos fase 2 | `assets/imagen_original_p06_01.png` |
| 7 | Rúbrica EX2: diseño, presentación y documentación | `assets/imagen_original_p07_01.jpeg` |
| 7 | Rúbrica EX2: implementación | `assets/imagen_original_p07_02.png` |

## 8. Notas de lectura y fidelidad

1. **Este archivo representa el PDF adjunto**, no una reconciliación con otras guías del curso ni con versiones posteriores del proyecto.
2. Los pesos listados en las tablas EX2 se reproducen como aparecen en la rúbrica, y **no son la puntuación absoluta asignada a cada fila**. Cada requerimiento tiene además su propio puntaje total indicado en el encabezado.
3. Las casillas de cumplimiento de las rúbricas originales estaban sin marcar. «Sin completar» no significa aprobado ni desaprobado; simplemente no se aporta evidencia en el PDF.
4. La figura de fase 2 muestra cuatro nodos a la derecha, pero la tabla distingue explícitamente `headnode`, `worker1`, `worker2` y `worker3`: para asignar responsabilidades individuales se debe usar la tabla y verificar el entorno real.
5. La tabla de fase 1 presenta las cabeceras «PUERTO» y «DISPOSITIVO» intercambiadas respecto de sus valores; se mantuvieron **los valores** y se normalizó el orden semántico de columnas en el Markdown.
6. La rúbrica R5 de implementación menciona explícitamente VLANs y el no uso de redes «self-service» en OpenStack. Esta redacción se conserva fielmente incluso si alguna documentación de arquitectura del grupo describe opciones diferentes.
7. Los elementos operativos detallados que **no aparecen en el PDF** (credenciales, scripts, UUID reales, API endpoints, configuración exacta del plano de datos y resultados de pruebas) no se añaden como si fueran parte del documento fuente.

---

**Fin de la conversión.**
