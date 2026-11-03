# Matriz de trazabilidad EX2 — G5 (plantilla de trabajo)

> **Origen:** criterios y pesos de las páginas 17–18 del enunciado oficial, transcritos en `RUBRICA_EX2_DETALLADA.md`.
> **Columnas propuestas por el asistente:** módulo sugerido, prueba y evidencia. Estos campos **no** son texto oficial. No equivalen a funcionalidad implementada, test aprobado ni evidencia recogida.
> **Estado inicial:** todos los casos sin verificación real permanecen `NO VERIFICADO`. Para cambiar a `PASS` se exige código ejecutado, salida comprobable y archivo de evidencia.

## Criterio para actualizar el estado

- **DISEÑADO:** documentación/contrato establecido, sin implementación comprobada.
- **IMPLEMENTADO SIN VALIDAR:** existe código pero aún no hay prueba suficiente.
- **PASS:** prueba ejecutada y evidencia identificable.
- **FAIL:** prueba ejecutada con resultado distinto al esperado.
- **NT:** prueba no realizada y motivo documentado; no implica cumplimiento.

## Matriz de los 46 criterios EX2

| ID | Bloque | Criterio oficial | Máx. puntos equivalentes | Módulo sugerido | Prueba propuesta | Evidencia propuesta | Estado inicial | Ruta evidencia real |
|---|---|---|---:|---|---|---|---|---|
| `EX2-R0-D-01` | R0-D | Claridad de exposición y respuesta a preguntas | 4,90 | Documentación / Equipo | `TC-R0-D-01` — Revisión de presentación | Guion y acta de sustentación | NO VERIFICADO | Por completar |
| `EX2-R0-D-02` | R0-D | High Level Software Design claramente documentado | 4,90 | Documentación / Equipo | `TC-R0-D-02` — Revisión documental | Sección y páginas de HLD actualizadas | NO VERIFICADO | Por completar |
| `EX2-R0-D-03` | R0-D | Reporte de pruebas: completo y bien documentado | 4,20 | Documentación / Equipo | `TC-R0-D-03` — Revisión documental | Plan de pruebas + resultados firmados/fechados | NO VERIFICADO | Por completar |
| `EX2-R3-D-01` | R3-D | Consideración en diseño y fundamentación de los mínimos servicios requeridos (Keystone, Horizon, Nova, Neutron & ML2 Plugin, Glance) | 2,40 | Driver OpenStack + Arquitectura | `TC-R3-D-01` — Revisión de HLD | Diagrama de servicios OpenStack y justificación de cada uno | NO VERIFICADO | Por completar |
| `EX2-R3-D-02` | R3-D | Uso eficiente (p.ej., paralelo, manejo de errores, auth de módulos, uso de caché) de APIs de OpenStack en el despliegue de VMs sobre OpenStack | 3,00 | Driver OpenStack + Arquitectura | `TC-R3-D-02` — Revisión técnica | Diagrama de flujo SDK/REST; control de errores, caché y paralelismo | NO VERIFICADO | Por completar |
| `EX2-R3-D-03` | R3-D | Permite orquestar VM usando OpenStack (Topologías personalizadas y predefinidas) | 3,00 | Driver OpenStack + Arquitectura | `TC-R3-D-03` — Revisión de HLD | Diagrama de secuencia y contrato de topologías | NO VERIFICADO | Por completar |
| `EX2-R3-D-04` | R3-D | Diseño permite crear topologías capa 2. | 2,40 | Driver OpenStack + Arquitectura | `TC-R3-D-04` — Revisión de HLD | Modelo de enlaces / VLAN provider / Neutron ML2 | NO VERIFICADO | Por completar |
| `EX2-R3-D-05` | R3-D | Permite visualizar los proyectos desplegados por usuario (p.ej., en Horizon) | 1,20 | Driver OpenStack + Arquitectura | `TC-R3-D-05` — Revisión de HLD | Plan de proyectos y permisos; capturas Horizon previstas | NO VERIFICADO | Por completar |
| `EX2-R4-D-01` | R4-D | Estrategia de monitoreo de recursos es consistente con el algoritmo a desarrollar y con el evitar superar el máximo nivel de congestión permitido. | 2,70 | VM Placement + Resource Monitoring | `TC-R4-D-01` — Revisión de HLD | Diseño de telemetría y umbrales | NO VERIFICADO | Por completar |
| `EX2-R4-D-02` | R4-D | Algoritmo de aprovisionamiento de VMs tiene función objetivo bien definida y sustentada. | 3,60 | VM Placement + Resource Monitoring | `TC-R4-D-02` — Revisión matemática | Ecuación, variables, restricciones y justificación | NO VERIFICADO | Por completar |
| `EX2-R4-D-03` | R4-D | Algoritmo considera uso eficiente (utilización) de recursos para aquellas cargas dinámicas que no consumen (en todo momento) el 100% de recursos y pueden soportar que sus recursos (p.ej., cores físicos) sean compartidos. | 2,70 | VM Placement + Resource Monitoring | `TC-R4-D-03` — Revisión matemática | Supuestos de uso dinámico y modelo de sobreaprovisionamiento | NO VERIFICADO | Por completar |
| `EX2-R4-D-04` | R4-D | Algoritmo considera no solo la utilización actual, sino el estimado de la congestión durante el ciclo de vida del slice. Tanto el impacto de un número grande de asignaciones de VMs con baja utilización (pero que podrían variar/aumentar en el tiempo), como el impacto de asignaciones recientes cuyo uso aún no se ve reflejado en las mediciones (p.ej., aún no bootea la VM). | 2,70 | VM Placement + Resource Monitoring | `TC-R4-D-04` — Revisión matemática | Modelo de demanda futura y reservas pendientes | NO VERIFICADO | Por completar |
| `EX2-R4-D-05` | R4-D | Algoritmo de aprovisionamiento de VMs considera slices como un todo, y no VMs individuales. | 2,70 | VM Placement + Resource Monitoring | `TC-R4-D-05` — Revisión matemática | Ejemplo de decisión conjunta para un slice | NO VERIFICADO | Por completar |
| `EX2-R4-D-06` | R4-D | Algoritmo considera/limita el tiempo de ejecución para instancias (osea, slices) grandes | 1,80 | VM Placement + Resource Monitoring | `TC-R4-D-06` — Revisión de diseño | Complejidad y resultados de benchmarking para slices grandes | NO VERIFICADO | Por completar |
| `EX2-R4-D-07` | R4-D | Considera la zona de disponibilidad pedida al colocar las VMs. | 1,80 | VM Placement + Resource Monitoring | `TC-R4-D-07` — Revisión de diseño | Regla de filtrado por zona / availability zone | NO VERIFICADO | Por completar |
| `EX2-R1B-I-01` | R1B-I | Ser independiente de la capa de infraestructura (cluster de servidores Linux, OpenStack, AWS, etc.). | 1,20 | UI/CLI + API Gateway + Topology/Slice Manager | `TC-R1B-I-01` — Prueba de integración | Misma solicitud funcionando sobre dos drivers o pruebas de contrato | NO VERIFICADO | Por completar |
| `EX2-R1B-I-02` | R1B-I | Implementación soporta concurrencia de usuarios | 1,20 | UI/CLI + API Gateway + Topology/Slice Manager | `TC-R1B-I-02` — Prueba concurrente | Solicitudes simultáneas con IDs independientes | NO VERIFICADO | Por completar |
| `EX2-R1B-I-03` | R1B-I | Permite seleccionar slices con topologías predefinidas: lineal, malla, árbol, anillo, y bus. | 1,20 | UI/CLI + API Gateway + Topology/Slice Manager | `TC-R1B-I-03` — Prueba funcional | UI con cinco topologías y JSON generado | NO VERIFICADO | Por completar |
| `EX2-R1B-I-04` | R1B-I | Permite editar slices (aún no desplegadas) combinando topologías predefinidas | 1,20 | UI/CLI + API Gateway + Topology/Slice Manager | `TC-R1B-I-04` — Prueba funcional | UI con cinco topologías y JSON generado | NO VERIFICADO | Por completar |
| `EX2-R1B-I-05` | R1B-I | Permite editar slices (aún no desplegadas) agregando nodos y enlaces. | 1,20 | UI/CLI + API Gateway + Topology/Slice Manager | `TC-R1B-I-05` — Prueba funcional | UI y JSON antes/después de agregar nodos/enlaces | NO VERIFICADO | Por completar |
| `EX2-R1B-I-06` | R1B-I | Permite grabar slices (aún no desplegadas) para posterior edición | 0,60 | UI/CLI + API Gateway + Topology/Slice Manager | `TC-R1B-I-06` — Prueba funcional | Guardar borrador, reiniciar aplicación, recuperar edición | NO VERIFICADO | Por completar |
| `EX2-R1B-I-07` | R1B-I | Permite exportar topologías | 0,60 | UI/CLI + API Gateway + Topology/Slice Manager | `TC-R1B-I-07` — Prueba funcional | Archivo exportado y validación de esquema | NO VERIFICADO | Por completar |
| `EX2-R1B-I-08` | R1B-I | Permite importar topologías | 0,60 | UI/CLI + API Gateway + Topology/Slice Manager | `TC-R1B-I-08` — Prueba funcional | Importación con JSON y validación | NO VERIFICADO | Por completar |
| `EX2-R1B-I-09` | R1B-I | Permite crear nuevos slices sobre la base de editar topologías importadas | 0,60 | UI/CLI + API Gateway + Topology/Slice Manager | `TC-R1B-I-09` — Prueba funcional | Topología importada, editada y convertida en nuevo slice | NO VERIFICADO | Por completar |
| `EX2-R1B-I-10` | R1B-I | Permite especificar la configuración (capacidad) de cada máquina virtual (VM) creada. | 0,60 | UI/CLI + API Gateway + Topology/Slice Manager | `TC-R1B-I-10` — Prueba funcional | Formulario de vCPU/RAM/disco + payload | NO VERIFICADO | Por completar |
| `EX2-R1B-I-11` | R1B-I | Lista la información necesaria de los slices que le pertenecen al usuario. | 0,60 | UI/CLI + API Gateway + Topology/Slice Manager | `TC-R1B-I-11` — Prueba funcional | Consulta de slices por usuario y prueba de aislamiento | NO VERIFICADO | Por completar |
| `EX2-R1B-I-12` | R1B-I | Permite visualizar el consumo de recursos del sistema | 0,60 | UI/CLI + API Gateway + Topology/Slice Manager | `TC-R1B-I-12` — Prueba funcional | Panel con métricas verificadas contra inventario | NO VERIFICADO | Por completar |
| `EX2-R1B-I-13` | R1B-I | Permite borrar o editar slices previamente instanciados | 0,60 | UI/CLI + API Gateway + Topology/Slice Manager | `TC-R1B-I-13` — Prueba funcional | Estado y recursos antes/después de editar o eliminar | NO VERIFICADO | Por completar |
| `EX2-R1B-I-14` | R1B-I | Permite importar imágenes de VMs en forma independiente de la plataforma | 0,60 | UI/CLI + API Gateway + Topology/Slice Manager | `TC-R1B-I-14` — Prueba de integración | Misma solicitud funcionando sobre dos drivers o pruebas de contrato | NO VERIFICADO | Por completar |
| `EX2-R1B-I-15` | R1B-I | Provee los tokens/credenciales necesarias para que el dueño del slice pueda acceder a la consola virtual de cada VM. | 0,60 | UI/CLI + API Gateway + Topology/Slice Manager | `TC-R1B-I-15` — Prueba funcional | Credenciales temporales y prueba de consola sin revelar token | NO VERIFICADO | Por completar |
| `EX2-R3-I-01` | R3-I | Implementó OpenStack con al menos los mínimos servicios requeridos (Keystone, Horizon, Nova, Neutron & ML2 plugin, Glance) | 3,60 | OpenStack Driver + APIs Keystone/Nova/Neutron/Glance | `TC-R3-I-01` — Prueba de infraestructura | openstack service list + endpoints + Horizon | NO VERIFICADO | Por completar |
| `EX2-R3-I-02` | R3-I | Orquesta Topologías (predefinidas y personalizadas) usando OpenStack | 5,40 | OpenStack Driver + APIs Keystone/Nova/Neutron/Glance | `TC-R3-I-02` — Prueba end-to-end | API G5 -> driver OpenStack -> Nova/Neutron; VMs reales | NO VERIFICADO | Por completar |
| `EX2-R3-I-03` | R3-I | Orquesta slices/topologías en capa 2 | 3,60 | OpenStack Driver + APIs Keystone/Nova/Neutron/Glance | `TC-R3-I-03` — Prueba de red | Neutron networks/ports, VLANs y prueba L2 | NO VERIFICADO | Por completar |
| `EX2-R3-I-04` | R3-I | Uso eficiente (p.ej., paralelo) de APIs de OpenStack en el despliegue de VMs sobre OpenStack | 1,80 | OpenStack Driver + APIs Keystone/Nova/Neutron/Glance | `TC-R3-I-04` — Prueba de rendimiento | Trazas HTTP y tiempos de despliegue | NO VERIFICADO | Por completar |
| `EX2-R3-I-05` | R3-I | Borrado slices | 1,80 | OpenStack Driver + APIs Keystone/Nova/Neutron/Glance | `TC-R3-I-05` — Prueba de limpieza | IDs de recursos antes/después; ausencia de huérfanos | NO VERIFICADO | Por completar |
| `EX2-R3-I-06` | R3-I | Permite visualizar máquinas virtuales desplegadas en Horizon | 1,80 | OpenStack Driver + APIs Keystone/Nova/Neutron/Glance | `TC-R3-I-06` — Prueba de infraestructura | Captura de VMs en Horizon y correspondencia con slice_id | NO VERIFICADO | Por completar |
| `EX2-R4-I-01` | R4-I | Lista recursos(servidores) disponibles en ambas plataformas (Linux Cluster y OpenStack) | 2,40 | VM Placement + Resource Service | `TC-R4-I-01` — Prueba funcional | Inventario de servidores de ambos clústeres | NO VERIFICADO | Por completar |
| `EX2-R4-I-02` | R4-I | Entrega una asignación de VMs a servidores de acuerdo al algoritmo diseñado en caso haya capacidad. | 6,00 | VM Placement + Resource Service | `TC-R4-I-02` — Prueba funcional | Plan de placement, capacidades y nodos resultantes | NO VERIFICADO | Por completar |
| `EX2-R4-I-03` | R4-I | Rechaza la asignación de VMs cuando no hay recursos disponibles, indicando la razón de la falla (logs o consola) | 2,40 | VM Placement + Resource Service | `TC-R4-I-03` — Prueba negativa | Respuesta de rechazo, causa y sin reservas residuales | NO VERIFICADO | Por completar |
| `EX2-R4-I-04` | R4-I | Las VMs son asignadas a servidores en la zonas de disponibilidad elegida por el usuario. | 1,20 | VM Placement + Resource Service | `TC-R4-I-04` — Prueba funcional | Solicitud de AZ y comprobación de host final | NO VERIFICADO | Por completar |
| `EX2-R5-I-01` | R5-I | Usa VLANs para segmentar los enlaces/subredes minimizando el overhead (p.ej., no usa túneles en el Linux cluster ni redes "self-service" en OpenStack) | 2,10 | Networking Service + Linux/OpenStack Drivers + OVS | `TC-R5-I-01` — Prueba de red | Neutron provider VLAN + ovs-vsctl / ovs-ofctl; sin túneles | NO VERIFICADO | Por completar |
| `EX2-R5-I-02` | R5-I | Implementa las reglas de seguridad requeridas en los slices en el Linux cluster | 2,10 | Networking Service + Linux/OpenStack Drivers + OVS | `TC-R5-I-02` — Prueba de seguridad | Reglas y prueba de tráfico permitido/denegado en Linux | NO VERIFICADO | Por completar |
| `EX2-R5-I-03` | R5-I | Implementa las reglas de seguridad requeridas en los slices en Openstack | 1,40 | Networking Service + Linux/OpenStack Drivers + OVS | `TC-R5-I-03` — Prueba de seguridad | Security groups y prueba tráfico permitido/denegado | NO VERIFICADO | Por completar |
| `EX2-R5-I-04` | R5-I | Provee de salida a internet a la máquinas que lo requieran (Linux Cluster y Openstack) | 2,10 | Networking Service + Linux/OpenStack Drivers + OVS | `TC-R5-I-04` — Prueba de conectividad | Ping/HTTP desde VMs autorizadas de ambos clústeres | NO VERIFICADO | Por completar |
| `EX2-R5-I-05` | R5-I | Provee acceso desde internet (p.ej., SSH) a máquinas virtuales que lo requieran (Linux Cluster y Openstack) | 2,80 | Networking Service + Linux/OpenStack Drivers + OVS | `TC-R5-I-05` — Prueba de conectividad | SSH desde red autorizada + rechazo no autorizado | NO VERIFICADO | Por completar |
| `EX2-R5-I-06` | R5-I | Configuran dinámicamente el switch físico para limitar los broadcasts de cada enlace virtual a los servidores que realmente los necesiten | 3,50 | Networking Service + Linux/OpenStack Drivers + OVS | `TC-R5-I-06` — Prueba de red | Configuración del switch físico antes/después y captura de broadcasts | NO VERIFICADO | Por completar |

## Registro de pruebas y evidencia para GitHub

Ruta sugerida para resultados: `docs/pruebas/EX2/TC-EX2-<BLOQUE>-<NN>.md`. Cada ficha debe contener: objetivo, requisitos previos, versión de código/commit, comandos o requests ejecutados, entradas, resultados esperados, salidas obtenidas, PASS/FAIL/NT, fecha y referencias a imágenes/logs.

Guardar evidencias en `docs/evidencias/EX2/` usando IDs consistentes. Quitar secretos, contraseñas y tokens de los logs antes de subirlos. La propuesta de un repositorio privado GitHub viene de la sección 5 del enunciado; no se debe suponer que el repositorio esté creado.

## Contradicciones o verificaciones pendientes

- La sección 9 del PDF menciona R1C en EX2, pero el template de las páginas 17–18 no muestra un bloque independiente R1C; consultar al docente si se actualizó la plantilla.
- El documento general se identifica 2025-2; el usuario indicó que el enunciado sigue vigente para 2026-2. Conservar ambas referencias.
- Para R5 se exige VLAN provider y minimizar túneles: revisar la configuración OpenStack real antes de implementar redes self-service.
- No usar los resultados del grupo G2 como evidencia propia de G5; G2 sirve solo de ejemplo de estructura documental.

## Estructura sugerida del repositorio

```text
IngenieriaDeRedesCloud-G5/
├── CLAUDE.md
├── README.md
├── requerimientos_md/
│   ├── TEL141_Proyecto_PUCP_Private_Cloud_Orchestrator_COMPLETO_EX1_EX2.md
│   ├── RUBRICA_EX1_DETALLADA.md
│   ├── RUBRICA_EX2_DETALLADA.md
│   └── MATRIZ_TRAZABILIDAD_EX2_G5.md
├── Arquitectura_md/
├── Laboratorio_md/
├── docs/
│   ├── pruebas/EX2/
│   ├── evidencias/EX2/
│   └── informe-final/
├── src/
├── tests/
└── scripts/
```

Ajustar esta estructura al repositorio EX1 real antes de mover código.
