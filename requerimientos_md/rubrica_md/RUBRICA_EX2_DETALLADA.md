# Rúbrica completa EX2 — TEL141

> **Fuente oficial:** `TEL141-Proyecto_del_curso-2025-2-V1(6).pdf`, secciones 10 y 11, páginas 15–18. El documento fuente dice 2025-2; el usuario ha confirmado que el mismo enunciado se utiliza en su curso 2026-2. Se conserva esta distinción y no se alteran los criterios.
>
> **Metodología:** transcripción desde las tablas incrustadas como imágenes en el PDF. Los identificadores EX1-... / EX2-... y los cálculos de puntos equivalentes se añadieron para trazabilidad y **no** forman parte de la rúbrica original. Los campos de evidencia están vacíos por defecto.


**EX2: 100 puntos.** En esta plantilla la columna **«Peso»** expresa porcentajes dentro de cada bloque; **no son puntos directos**. La columna «Puntos equivalentes» es una cuenta auxiliar: `puntaje del bloque × peso / 100`.

## Distribución de puntos EX2

| Bloque | Puntaje máximo | Página fuente |
|---|---:|---|
| R0 — presentación, documentación y diseño | 14,00 | 17 |
| R3 — diseño del despliegue OpenStack | 12,00 | 17 |
| R4 — diseño de VM Placement | 18,00 | 17 |
| R1B — implementación de interfaz y ciclo de vida | 12,00 | 18 |
| R3 — implementación OpenStack | 18,00 | 18 |
| R4 — implementación de VM Placement | 12,00 | 18 |
| R5 — implementación de networking y seguridad | 14,00 | 18 |
| **Total** | **100,00** | |

> **Advertencia documental:** la sección 9 del enunciado menciona R1C en la composición de EX2, mientras que la plantilla detallada de EX2 (págs. 17–18) no tiene una fila/bloque R1C independiente. No se ha añadido ni reasignado puntaje a R1C en esta transcripción. Debe confirmarse con el docente si existe una versión actualizada de la rúbrica.

## R0 — presentación, documentación y diseño — 14,00 puntos

*Página 17 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Peso dentro del bloque (%) | Puntos equivalentes | ¿Cumplió? | Evidencia |
|---|---|---:|---:|---|---|
| `EX2-R0-D-01` | Claridad de exposición y respuesta a preguntas | 35,00 | 4,90 | N/A — evaluación del jurado | Pendiente |
| `EX2-R0-D-02` | High Level Software Design claramente documentado | 35,00 | 4,90 | N/A — evaluación del jurado | Pendiente |
| `EX2-R0-D-03` | Reporte de pruebas: completo y bien documentado | 30,00 | 4,20 | N/A — evaluación del jurado | Pendiente |
| **Subtotal R0-D** | | **100,00** | **14,00** | | |


## R3 — diseño del despliegue OpenStack — 12,00 puntos

*Página 17 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Peso dentro del bloque (%) | Puntos equivalentes | ¿Cumplió? | Evidencia |
|---|---|---:|---:|---|---|
| `EX2-R3-D-01` | Consideración en diseño y fundamentación de los mínimos servicios requeridos (Keystone, Horizon, Nova, Neutron & ML2 Plugin, Glance) | 20,00 | 2,40 | Pendiente de verificar | Pendiente |
| `EX2-R3-D-02` | Uso eficiente (p.ej., paralelo, manejo de errores, auth de módulos, uso de caché) de APIs de OpenStack en el despliegue de VMs sobre OpenStack | 25,00 | 3,00 | Pendiente de verificar | Pendiente |
| `EX2-R3-D-03` | Permite orquestar VM usando OpenStack (Topologías personalizadas y predefinidas) | 25,00 | 3,00 | Pendiente de verificar | Pendiente |
| `EX2-R3-D-04` | Diseño permite crear topologías capa 2. | 20,00 | 2,40 | Pendiente de verificar | Pendiente |
| `EX2-R3-D-05` | Permite visualizar los proyectos desplegados por usuario (p.ej., en Horizon) | 10,00 | 1,20 | Pendiente de verificar | Pendiente |
| **Subtotal R3-D** | | **100,00** | **12,00** | | |


## R4 — diseño de VM Placement — 18,00 puntos

*Página 17 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Peso dentro del bloque (%) | Puntos equivalentes | ¿Cumplió? | Evidencia |
|---|---|---:|---:|---|---|
| `EX2-R4-D-01` | Estrategia de monitoreo de recursos es consistente con el algoritmo a desarrollar y con el evitar superar el máximo nivel de congestión permitido. | 15,00 | 2,70 | Pendiente de verificar | Pendiente |
| `EX2-R4-D-02` | Algoritmo de aprovisionamiento de VMs tiene función objetivo bien definida y sustentada. | 20,00 | 3,60 | Pendiente de verificar | Pendiente |
| `EX2-R4-D-03` | Algoritmo considera uso eficiente (utilización) de recursos para aquellas cargas dinámicas que no consumen (en todo momento) el 100% de recursos y pueden soportar que sus recursos (p.ej., cores físicos) sean compartidos. | 15,00 | 2,70 | Pendiente de verificar | Pendiente |
| `EX2-R4-D-04` | Algoritmo considera no solo la utilización actual, sino el estimado de la congestión durante el ciclo de vida del slice. Tanto el impacto de un número grande de asignaciones de VMs con baja utilización (pero que podrían variar/aumentar en el tiempo), como el impacto de asignaciones recientes cuyo uso aún no se ve reflejado en las mediciones (p.ej., aún no bootea la VM). | 15,00 | 2,70 | Pendiente de verificar | Pendiente |
| `EX2-R4-D-05` | Algoritmo de aprovisionamiento de VMs considera slices como un todo, y no VMs individuales. | 15,00 | 2,70 | Pendiente de verificar | Pendiente |
| `EX2-R4-D-06` | Algoritmo considera/limita el tiempo de ejecución para instancias (osea, slices) grandes | 10,00 | 1,80 | Pendiente de verificar | Pendiente |
| `EX2-R4-D-07` | Considera la zona de disponibilidad pedida al colocar las VMs. | 10,00 | 1,80 | Pendiente de verificar | Pendiente |
| **Subtotal R4-D** | | **100,00** | **18,00** | | |


## R1B — implementación de interfaz y ciclo de vida — 12,00 puntos

*Página 18 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Peso dentro del bloque (%) | Puntos equivalentes | ¿Cumplió? | Evidencia |
|---|---|---:|---:|---|---|
| `EX2-R1B-I-01` | Ser independiente de la capa de infraestructura (cluster de servidores Linux, OpenStack, AWS, etc.). | 10,00 | 1,20 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-02` | Implementación soporta concurrencia de usuarios | 10,00 | 1,20 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-03` | Permite seleccionar slices con topologías predefinidas: lineal, malla, árbol, anillo, y bus. | 10,00 | 1,20 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-04` | Permite editar slices (aún no desplegadas) combinando topologías predefinidas | 10,00 | 1,20 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-05` | Permite editar slices (aún no desplegadas) agregando nodos y enlaces. | 10,00 | 1,20 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-06` | Permite grabar slices (aún no desplegadas) para posterior edición | 5,00 | 0,60 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-07` | Permite exportar topologías | 5,00 | 0,60 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-08` | Permite importar topologías | 5,00 | 0,60 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-09` | Permite crear nuevos slices sobre la base de editar topologías importadas | 5,00 | 0,60 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-10` | Permite especificar la configuración (capacidad) de cada máquina virtual (VM) creada. | 5,00 | 0,60 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-11` | Lista la información necesaria de los slices que le pertenecen al usuario. | 5,00 | 0,60 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-12` | Permite visualizar el consumo de recursos del sistema | 5,00 | 0,60 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-13` | Permite borrar o editar slices previamente instanciados | 5,00 | 0,60 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-14` | Permite importar imágenes de VMs en forma independiente de la plataforma | 5,00 | 0,60 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-15` | Provee los tokens/credenciales necesarias para que el dueño del slice pueda acceder a la consola virtual de cada VM. | 5,00 | 0,60 | Pendiente de verificar | Pendiente |
| **Subtotal R1B-I** | | **100,00** | **12,00** | | |


## R3 — implementación OpenStack — 18,00 puntos

*Página 18 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Peso dentro del bloque (%) | Puntos equivalentes | ¿Cumplió? | Evidencia |
|---|---|---:|---:|---|---|
| `EX2-R3-I-01` | Implementó OpenStack con al menos los mínimos servicios requeridos (Keystone, Horizon, Nova, Neutron & ML2 plugin, Glance) | 20,00 | 3,60 | Pendiente de verificar | Pendiente |
| `EX2-R3-I-02` | Orquesta Topologías (predefinidas y personalizadas) usando OpenStack | 30,00 | 5,40 | Pendiente de verificar | Pendiente |
| `EX2-R3-I-03` | Orquesta slices/topologías en capa 2 | 20,00 | 3,60 | Pendiente de verificar | Pendiente |
| `EX2-R3-I-04` | Uso eficiente (p.ej., paralelo) de APIs de OpenStack en el despliegue de VMs sobre OpenStack | 10,00 | 1,80 | Pendiente de verificar | Pendiente |
| `EX2-R3-I-05` | Borrado slices | 10,00 | 1,80 | Pendiente de verificar | Pendiente |
| `EX2-R3-I-06` | Permite visualizar máquinas virtuales desplegadas en Horizon | 10,00 | 1,80 | Pendiente de verificar | Pendiente |
| **Subtotal R3-I** | | **100,00** | **18,00** | | |


## R4 — implementación de VM Placement — 12,00 puntos

*Página 18 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Peso dentro del bloque (%) | Puntos equivalentes | ¿Cumplió? | Evidencia |
|---|---|---:|---:|---|---|
| `EX2-R4-I-01` | Lista recursos(servidores) disponibles en ambas plataformas (Linux Cluster y OpenStack) | 20,00 | 2,40 | Pendiente de verificar | Pendiente |
| `EX2-R4-I-02` | Entrega una asignación de VMs a servidores de acuerdo al algoritmo diseñado en caso haya capacidad. | 50,00 | 6,00 | Pendiente de verificar | Pendiente |
| `EX2-R4-I-03` | Rechaza la asignación de VMs cuando no hay recursos disponibles, indicando la razón de la falla (logs o consola) | 20,00 | 2,40 | Pendiente de verificar | Pendiente |
| `EX2-R4-I-04` | Las VMs son asignadas a servidores en la zonas de disponibilidad elegida por el usuario. | 10,00 | 1,20 | Pendiente de verificar | Pendiente |
| **Subtotal R4-I** | | **100,00** | **12,00** | | |


## R5 — implementación de networking y seguridad — 14,00 puntos

*Página 18 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Peso dentro del bloque (%) | Puntos equivalentes | ¿Cumplió? | Evidencia |
|---|---|---:|---:|---|---|
| `EX2-R5-I-01` | Usa VLANs para segmentar los enlaces/subredes minimizando el overhead (p.ej., no usa túneles en el Linux cluster ni redes "self-service" en OpenStack) | 15,00 | 2,10 | Pendiente de verificar | Pendiente |
| `EX2-R5-I-02` | Implementa las reglas de seguridad requeridas en los slices en el Linux cluster | 15,00 | 2,10 | Pendiente de verificar | Pendiente |
| `EX2-R5-I-03` | Implementa las reglas de seguridad requeridas en los slices en Openstack | 10,00 | 1,40 | Pendiente de verificar | Pendiente |
| `EX2-R5-I-04` | Provee de salida a internet a la máquinas que lo requieran (Linux Cluster y Openstack) | 15,00 | 2,10 | Pendiente de verificar | Pendiente |
| `EX2-R5-I-05` | Provee acceso desde internet (p.ej., SSH) a máquinas virtuales que lo requieran (Linux Cluster y Openstack) | 20,00 | 2,80 | Pendiente de verificar | Pendiente |
| `EX2-R5-I-06` | Configuran dinámicamente el switch físico para limitar los broadcasts de cada enlace virtual a los servidores que realmente los necesiten | 25,00 | 3,50 | Pendiente de verificar | Pendiente |
| **Subtotal R5-I** | | **100,00** | **14,00** | | |


## Imágenes originales de EX2

![EX2, presentación y diseño, página 17](TEL141_Proyecto_Cloud_assets/rubrica_EX2_pagina_17.png)

![EX2, implementación, página 18](TEL141_Proyecto_Cloud_assets/rubrica_EX2_pagina_18.png)

---

**Nota:** los textos de esta rúbrica se presentan como criterios de evaluación, no como afirmaciones de que el código G5 ya los cumple.
