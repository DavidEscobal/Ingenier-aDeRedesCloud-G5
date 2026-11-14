# Reporte de cumplimiento — Rúbrica del EX2 (G5)

**Fecha:** 2026-11-14 · **Rama:** `fase2` · **Fuente de la rúbrica:** `requerimientos_md/TEL141_Proyecto_PUCP_Private_Cloud_Orchestrator.md`
(ítems `EX2-*`). Las evidencias reales están en `docs/evidencias/F2/` (MS-01 a MS-16).

**Leyenda:** ✅ cumplido y verificado en el clúster · 🟡 parcial o sin demostrar · ❌ falta.

> En el EX2, **R2 (Linux) no se evalúa como ítem propio** (fue parte del EX1); Linux sí aparece dentro de R4, R5 y en
> la demostración (`Contexto_md/Ex2_Validacion_de_Implementacion.md`).

## Resumen

- **R1B y R3 están casi completos.**
- **Mayor riesgo en puntos:** R4 completo (≈12 pts de implementación + ≈18 de diseño), R0 documentación (14 pts) y R5
  (acceso desde Internet, reglas de seguridad y configuración dinámica del switch, 3,5 pts).

## Implementación

### R1B — Interfaz de usuario (12 pts)

| Ítem | Descripción | Pts | Estado | Nota |
|---|---|---|---|---|
| EX2-R1B-I-01 | Independiente de la infraestructura | 1,2 | ✅ | Drivers Linux y OpenStack intercambiables |
| EX2-R1B-I-02 | Concurrencia de usuarios | 1,2 | 🟡 | Cola de operaciones y reservas atómicas; falta demostrarlo en real |
| EX2-R1B-I-03 | Topologías predefinidas (lineal, malla, árbol, anillo, bus) | 1,2 | ✅ | También estrella |
| EX2-R1B-I-04 | Editar combinando topologías predefinidas | 1,2 | ✅ | «Combinar» en el editor |
| EX2-R1B-I-05 | Editar agregando nodos y enlaces | 1,2 | ✅ | |
| EX2-R1B-I-06 | Grabar para editar después | 0,6 | ✅ | Borradores en el topology-manager |
| EX2-R1B-I-07 | Exportar topologías | 0,6 | ✅ | JSON |
| EX2-R1B-I-08 | Importar topologías | 0,6 | ✅ | JSON |
| EX2-R1B-I-09 | Crear slices desde topologías importadas | 0,6 | ✅ | |
| EX2-R1B-I-10 | Capacidad de cada VM | 0,6 | ✅ | 5 tamaños predefinidos (opción A) |
| EX2-R1B-I-11 | Listar los slices del usuario | 0,6 | ✅ | |
| EX2-R1B-I-12 | Ver el consumo de recursos del sistema | 0,6 | ❌ | Depende del monitoreo (D-13) |
| EX2-R1B-I-13 | Borrar o editar slices instanciados | 0,6 | 🟡 | Borrar ✅; editar desplegados, pausado |
| EX2-R1B-I-14 | Importar imágenes independiente de la plataforma | 0,6 | ✅ | Catálogo propio; Glance y almacén Linux |
| EX2-R1B-I-15 | Credenciales para la consola de cada VM | 0,6 | ✅ | Token de consola que vence (Linux y OpenStack) |

### R3 — OpenStack (18 pts)

| Ítem | Descripción | Pts | Estado | Nota |
|---|---|---|---|---|
| EX2-R3-I-01 | Keystone, Horizon, Nova, Neutron/ML2, Glance | 3,6 | ✅ | Uso por API |
| EX2-R3-I-02 | Topologías predefinidas y personalizadas | 5,4 | ✅ | Lineal y anillo probados en real |
| EX2-R3-I-03 | Slices en capa 2 | 3,6 | 🟡 | Enlaces con IP ✅; enlaces sin IP bloqueados por Nova (exige IP fija) |
| EX2-R3-I-04 | Uso eficiente o paralelo de la API | 1,8 | 🟡 | Crea las VMs en paralelo; falta demostrarlo |
| EX2-R3-I-05 | Borrado de slices | 1,8 | ✅ | Sin restos; compensación ante fallos |
| EX2-R3-I-06 | Ver las VMs en Horizon | 1,8 | ✅ | Un proyecto por slice |

### R4 — VM Placement (12 pts)

| Ítem | Descripción | Pts | Estado | Nota |
|---|---|---|---|---|
| EX2-R4-I-01 | Listar los servidores disponibles en ambas plataformas | 2,4 | ❌ | Falta el inventario de recursos |
| EX2-R4-I-02 | Asignar VMs según el algoritmo diseñado | 6,0 | ❌ | Hoy reparto por turnos (Linux) o Nova decide (OpenStack) |
| EX2-R4-I-03 | Rechazar si no hay recursos, con la razón | 2,4 | 🟡 | Linux rechaza con motivo; falta como parte del placement |
| EX2-R4-I-04 | Respetar la zona de disponibilidad elegida | 1,2 | 🟡 | Solo elección manual del servidor (host forzado probado) |

### R5 — Redes y seguridad (14 pts)

| Ítem | Descripción | Pts | Estado | Nota |
|---|---|---|---|---|
| EX2-R5-I-01 | VLANs sin túneles ni redes self-service | 2,1 | ✅ | Linux QinQ; OpenStack provider VLAN |
| EX2-R5-I-02 | Reglas de seguridad en Linux | 2,1 | 🟡 | Firewall por slice fijo; el usuario no define reglas |
| EX2-R5-I-03 | Reglas de seguridad en OpenStack | 1,4 | ❌ | |
| EX2-R5-I-04 | Salida a Internet (Linux y OpenStack) | 2,1 | 🟡 | Linux ✅ (MS-16); OpenStack ❌ (falta router Neutron) |
| EX2-R5-I-05 | Acceso desde Internet (Linux y OpenStack) | 2,8 | ❌ | Linux: ruta 10.60.9.0/24; OpenStack: IP flotante |
| EX2-R5-I-06 | Configurar dinámicamente el switch físico para limitar broadcasts | 3,5 | ❌ | En fase 2 el switch (192.168.201.5) no es accesible |

## Diseño y documentación (evaluación del jurado)

| Bloque | Pts | Estado | Nota |
|---|---|---|---|
| EX2-R0-D-01/02/03 — exposición, HLD documentado, reporte de pruebas | 14 | 🟡 | Hay evidencias MS-01 a MS-16; **HLD y reporte de pruebas sin actualizar** |
| EX2-R3-D-01..05 — servicios mínimos, uso eficiente de APIs, topologías, capa 2, ver proyectos | 12 | 🟡 | Casi todo implementado; falta sustentarlo en el HLD |
| EX2-R4-D-01..07 — monitoreo, función objetivo, sobreaprovisionamiento, congestión, slice como un todo, tiempo límite, zona | ≈18 | ❌ | D-07 y D-13 pendientes; la propuesta BFD/BCDP del equipo cubre parte |

## Prioridades

1. **R4:** inventario y monitoreo + algoritmo (BFD o BCDP) integrado + zona de disponibilidad.
2. **R0:** actualizar el HLD con la arquitectura real (D-08 a D-16) y armar el reporte de pruebas con MS-01 a MS-16.
3. **R5:** router e IP flotante en OpenStack, reglas de seguridad, acceso desde Internet.
4. **Consultas al JP:** ruta 10.60.9.0/24, disco en OpenStack, enlaces sin IP en Nova, router/IPs flotantes, zona de
   disponibilidad y **cómo cumplir R5-I-06 sin acceso al switch físico**.
