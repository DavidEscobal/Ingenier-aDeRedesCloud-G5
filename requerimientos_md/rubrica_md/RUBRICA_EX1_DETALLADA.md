# Rúbrica completa EX1 — TEL141

> **Fuente oficial:** `TEL141-Proyecto_del_curso-2025-2-V1(6).pdf`, secciones 10 y 11, páginas 15–18. El documento fuente dice 2025-2; el usuario ha confirmado que el mismo enunciado se utiliza en su curso 2026-2. Se conserva esta distinción y no se alteran los criterios.
>
> **Metodología:** transcripción desde las tablas incrustadas como imágenes en el PDF. Los identificadores EX1-... / EX2-... y los cálculos de puntos equivalentes se añadieron para trazabilidad y **no** forman parte de la rúbrica original. Los campos de evidencia están vacíos por defecto.


**EX1: 100 puntos** repartidos en 88 puntos de arquitectura/diseño y 12 puntos de implementación de R2. Los ítems especiales de rendimiento adicionales (al final de la página 16) se muestran aparte; no se suman automáticamente al total de 100.

## Resumen de puntajes

| Bloque | Tipo | Puntaje máximo | Fuente |
|---|---|---:|---|
| R0 | Arquitectura / Diseño | 8,00 | p. 15 |
| R1 | Arquitectura / Diseño | 40,00 | p. 15 |
| R1B | Arquitectura / Diseño | 6,00 | p. 15 |
| R1C | Arquitectura / Diseño | 18,00 | p. 15 |
| R2 | Arquitectura / Diseño | 6,00 | p. 16 |
| R5 | Arquitectura / Diseño | 10,00 | p. 16 |
| R2 | Implementación | 12,00 | p. 16 |
| **Total** | | **100,00** | |

## R0 — presentación y documentación — 8,00 puntos

*Página 15 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Puntos | ¿Cumplió? | Evidencia / ubicación |
|---|---|---:|---|---|
| `EX1-R0-D-01` | Claridad y buena organización de la exposición | 1,50 | N/A — evaluación del jurado | Pendiente |
| `EX1-R0-D-02` | Manejo de medios | 1,00 | N/A — evaluación del jurado | Pendiente |
| `EX1-R0-D-03` | Porcentaje de cobertura de requerimientos | 2,00 | N/A — evaluación del jurado | Pendiente |
| `EX1-R0-D-04` | Cohesión y trabajo en equipo (sinergia) | 0,50 | N/A — evaluación del jurado | Pendiente |
| `EX1-R0-D-05` | Orden y redacción en la documentación | 1,50 | N/A — evaluación del jurado | Pendiente |
| `EX1-R0-D-06` | Especificación de APIs | 1,50 | N/A — evaluación del jurado | Pendiente |
| **Subtotal R0-D** | | **8,00** | | |


## R1 — arquitectura genérica — 40,00 puntos

*Página 15 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Puntos | ¿Cumplió? | Evidencia / ubicación |
|---|---|---:|---|---|
| `EX1-R1-D-01` | Separación adecuada de plataformas (AWS, OpenStack, Linux Cluster, etc.) | 5,00 | Pendiente de verificar | Pendiente |
| `EX1-R1-D-02` | Modularidad (General) | 2,00 | Pendiente de verificar | Pendiente |
| `EX1-R1-D-03` | Modularidad - permite agregar/remover hardware fácilmente y sin detener la operatividad del sistema. | 3,00 | Pendiente de verificar | Pendiente |
| `EX1-R1-D-04` | Modularidad - Permite actualizar módulos independientemente y sin detener la operatividad del sistema (p.ej., DevOps) | 4,00 | Pendiente de verificar | Pendiente |
| `EX1-R1-D-05` | Modularidad - Enfoque de Seguridad (minimizar la exposición de cada módulo, y minimizar el impacto de un módulo/servicio comprometido) | 4,00 | Pendiente de verificar | Pendiente |
| `EX1-R1-D-06` | Escalabilidad - permite dimensionar cada módulo de manera independiente en respuesta a altas cargas (número de pedidos concurrentes) | 2,00 | Pendiente de verificar | Pendiente |
| `EX1-R1-D-07` | Escalabilidad - módulos pueden estar desplegados en máquinas distintas en casos de alta carga: capacidad para la comunicación en red de los módulos. | 2,00 | Pendiente de verificar | Pendiente |
| `EX1-R1-D-08` | Capacidad para almacenar de forma persistente la información de slices | 3,00 | Pendiente de verificar | Pendiente |
| `EX1-R1-D-09` | Capacidad para retomar la edición de una slice en un momento posterior | 3,00 | Pendiente de verificar | Pendiente |
| `EX1-R1-D-10` | Performance: Capacidad para permitir concurrencia/paralelismo al editar slices | 3,00 | Pendiente de verificar | Pendiente |
| `EX1-R1-D-11` | Performance: Capacidad para permitir concurrencia/paralelismo al desplegar slices | 4,00 | Pendiente de verificar | Pendiente |
| `EX1-R1-D-12` | Soporta la creación de logs | 5,00 | Pendiente de verificar | Pendiente |
| **Subtotal R1-D** | | **40,00** | | |


## R1B — interfaz de usuario, diseño — 6,00 puntos

*Página 15 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Puntos | ¿Cumplió? | Evidencia / ubicación |
|---|---|---:|---|---|
| `EX1-R1B-D-01` | Capacidad para soportar concurrencia de usuarios | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R1B-D-02` | Capacidad para editar, listar, y eliminar slices | 0,50 | Pendiente de verificar | Pendiente |
| `EX1-R1B-D-03` | Capacidad para configurar slices con topologías predefinidas (num nodos, num cores, MEM, almacenamiento, etc.) | 0,50 | Pendiente de verificar | Pendiente |
| `EX1-R1B-D-04` | Capacidad para componer y editar slices arbitrarias con el apoyo de topologías predefinidas | 2,00 | Pendiente de verificar | Pendiente |
| `EX1-R1B-D-05` | Capacidad de exportar plantillas con la configuración de un slice y capacidad de importar estas plantillas para sobre la base de ella crear una nueva slice. | 0,50 | Pendiente de verificar | Pendiente |
| `EX1-R1B-D-06` | Capacidad para visualizar el consumo de recursos | 0,50 | Pendiente de verificar | Pendiente |
| `EX1-R1B-D-07` | Capacidad para importar imágenes | 0,50 | Pendiente de verificar | Pendiente |
| `EX1-R1B-D-08` | Capacidad para proveer tokens de acceso a la consola virtual de las VMs | 0,50 | Pendiente de verificar | Pendiente |
| **Subtotal R1B-D** | | **6,00** | | |


## R1C — Slice Manager, diseño — 18,00 puntos

*Página 15 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Puntos | ¿Cumplió? | Evidencia / ubicación |
|---|---|---:|---|---|
| `EX1-R1C-D-01` | Flujo de trabajo completo (produce un slice que cumple todos los requerimientos) y en el orden correcto | 4,00 | Pendiente de verificar | Pendiente |
| `EX1-R1C-D-02` | Paralelismo/rapidez en el despliegue de slices | 2,00 | Pendiente de verificar | Pendiente |
| `EX1-R1C-D-03` | No tiene "race condition" u "overcommitting" de recursos. | 2,00 | Pendiente de verificar | Pendiente |
| `EX1-R1C-D-04` | Capacidad para monitorear los recursos asignados | 4,00 | Pendiente de verificar | Pendiente |
| `EX1-R1C-D-05` | Capacidad para validar la consistencia de los recursos asignados | 3,00 | Pendiente de verificar | Pendiente |
| `EX1-R1C-D-06` | Capacidad para validar que los requests vengan de un módulo autorizado y/o hayan sido hechos por un usuario autenticado y que tenga autorización para realizar la acción | 3,00 | Pendiente de verificar | Pendiente |
| **Subtotal R1C-D** | | **18,00** | | |


## R2 — soporte Linux, diseño — 6,00 puntos

*Página 16 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Puntos | ¿Cumplió? | Evidencia / ubicación |
|---|---|---:|---|---|
| `EX1-R2-D-01` | Selección de las tecnologías adecuadas para implementar el cluster | 1,50 | Pendiente de verificar | Pendiente |
| `EX1-R2-D-02` | Robustez de diseño / Error handling de las API del cluster | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-D-03` | Seguridad - minimiza la exposición de información/recursos del cluster a terceros. | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-D-04` | Permite agregar/remover nodos (workers) con la mínima disrupción/necesidad de cambios. | 0,50 | Pendiente de verificar | Pendiente |
| `EX1-R2-D-05` | Capacidad para monitoreo de recursos utilizados | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-D-06` | Permite el acceso a las VMs por consola virtual | 0,50 | Pendiente de verificar | Pendiente |
| `EX1-R2-D-07` | Capacidad para realizar el troubleshooting de cada slice por separado | 0,50 | Pendiente de verificar | Pendiente |
| **Subtotal R2-D** | | **6,00** | | |


## R5 — networking y seguridad, diseño — 10,00 puntos

*Página 16 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Puntos | ¿Cumplió? | Evidencia / ubicación |
|---|---|---:|---|---|
| `EX1-R5-D-01` | Capacidad para proveer salida a redes externas | 3,00 | Pendiente de verificar | Pendiente |
| `EX1-R5-D-02` | Capacidad para permitir el acceso desde el exterior (equivalente a una IP pública) a las VMs que lo requieran (selectivamente, brindando seguridad a las VMs frente a accesos no autorizados) | 3,00 | Pendiente de verificar | Pendiente |
| `EX1-R5-D-03` | Capacidad para utilizar VLANs en vez de túneles | 2,00 | Pendiente de verificar | Pendiente |
| `EX1-R5-D-04` | Capacidad para reconfigurar el switch de la infraestructura | 2,00 | Pendiente de verificar | Pendiente |
| **Subtotal R5-D** | | **10,00** | | |


## R2 — soporte Linux, implementación — 12,00 puntos

*Página 16 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Puntos | ¿Cumplió? | Evidencia / ubicación |
|---|---|---:|---|---|
| `EX1-R2-I-01` | Pudo desplegar las VMs en los servidores seleccionados, usando tecnologías de linux | 1,50 | Pendiente de verificar | Pendiente |
| `EX1-R2-I-02` | Pudo desplegar los enlaces entre VMs alojadas en diferentes servidores | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-I-03` | Implementa completamente la API diseñada | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-I-04` | Lidia con errores/reintentos | 0,50 | Pendiente de verificar | Pendiente |
| `EX1-R2-I-05` | Implementa el envío/manejo de imágenes para las VMs | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-I-06` | Implementa el borrado de las VMs y demás recursos (p.ej., interfaces TUN/TAP, OVSes, etc.) | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-I-07` | Implementa un mecanismo de acceso a las VMs vía consola virtual, proveyendo los tokens necesarios. | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-I-08` | Implementa la salida internet a las VMs que lo requieran | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-I-09` | Implementa el acceso desde internet (vía IP públicas) a las VMs que lo requieran | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-I-10` | Uso eficiente del espacio en disco usando el formato QCOW | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-I-11` | Escalabilidad: Soporta pedidos concurrentes | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-I-12` | Realiza borrado inteligente, es decir, elimina imágenes de VMs que no están siendo usadas (en los servidores). | 1,00 | Pendiente de verificar | Pendiente |
| **Subtotal R2-I** | | **12,00** | | |


## Características adicionales de Linux Cluster (página 16)

**Estos ítems están separados del bloque ordinario R2 de 12 puntos.** El PDF presenta una fila sin puntaje y otra con `3` puntos; se reproducen sin asumir que cambien el total oficial de EX1.

| ID agregado | Característica adicional | Puntaje visible en fuente |
|---|---|---|
| `EX1-R2-EXTRA-01` | Maneja un cache de imágenes que balancea el espacio en disco versus la velocidad para desplegar VMs | No indicado |
| `EX1-R2-EXTRA-02` | Uso e implementación de QinQ para no tener la limitante de 2^12 enlaces aprox. | 3,00 |

## Imágenes originales de EX1

![EX1, tabla de arquitectura y diseño, página 15](TEL141_Proyecto_Cloud_assets/rubrica_EX1_pagina_15.png)

![EX1, continuación de diseño e implementación de Linux, página 16](TEL141_Proyecto_Cloud_assets/rubrica_EX1_pagina_16.png)

---
**Nota de fidelidad:** se conservó el criterio «No tiene race condition u overcommitting» tal como aparece en EX1, aunque otras partes del proyecto admitan sobreasignación controlada. Esa diferencia se debe analizar, no corregir silenciosamente.
