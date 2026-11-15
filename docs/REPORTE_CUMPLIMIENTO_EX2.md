# Reporte de cumplimiento — Rúbrica del EX2 (G5)

**Fecha:** 2026-11-15 · **Rama:** `fase2` · **Fuente de la rúbrica:** `requerimientos_md/TEL141_Proyecto_PUCP_Private_Cloud_Orchestrator.md`
(ítems `EX2-*`). Las evidencias reales están en `docs/evidencias/F2/` (MS-01 a MS-17).

**Leyenda:** ✅ cumplido y verificado en el clúster · 🟡 parcial o sin demostrar · ❌ falta.

> En el EX2, **R2 (Linux) no se evalúa como ítem propio** (fue parte del EX1); Linux sí aparece dentro de R4, R5 y en
> la demostración (`Contexto_md/Ex2_Validacion_de_Implementacion.md`).

## Resumen

- **R1B, R1C, R2 y R3 están casi completos; R4 implementado y probado en real (MS-17, 2026-11-15).** R1C y R2 se
  revisan con los criterios del EX1 (ver la contradicción anotada en R1C).
- **Implementación (56 pts):** ✅ ≈35,7 · 🟡 ≈12,6 · ❌ ≈7,7 (sumando los puntos de cada ítem según su estado).
- **Mayor riesgo en puntos:** diseño y documentación (R0 14 pts, R4-D ≈18, R3-D 12: el HLD no refleja lo implementado),
  R5 (reglas en OpenStack, acceso desde Internet, switch: 7,7 pts en ❌) e imágenes Ubuntu para la demo.

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
| EX2-R1B-I-12 | Ver el consumo de recursos del sistema | 0,6 | ✅ | Página Recursos (monitoreo D-13): Linux y OpenStack, historial (2026-11-15) |
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
| EX2-R4-I-01 | Listar los servidores disponibles en ambas plataformas | 2,4 | ✅ | Monitoreo: server1–3 y worker1–3 con capacidad, compromiso, CPU real y salud (MS-17) |
| EX2-R4-I-02 | Asignar VMs según el algoritmo diseñado | 6,0 | ✅ | BCDP v2 en `vm-placement`; Linux y OpenStack respetan el plan (MS-17) |
| EX2-R4-I-03 | Rechazar si no hay recursos, con la razón | 2,4 | ✅ | 409 con el recurso que falta (p. ej. «CPU real insuficiente: se piden 1200 y quedan 1017») |
| EX2-R4-I-04 | Respetar la zona de disponibilidad elegida | 1,2 | 🟡 | Implementado (zona en la web y en el placement); hoy solo hay una zona por proveedor (`linux`, `nova`): faltan las zonas reales |

### R5 — Redes y seguridad (14 pts)

| Ítem | Descripción | Pts | Estado | Nota |
|---|---|---|---|---|
| EX2-R5-I-01 | VLANs sin túneles ni redes self-service | 2,1 | ✅ | Linux QinQ; OpenStack provider VLAN |
| EX2-R5-I-02 | Reglas de seguridad en Linux | 2,1 | 🟡 | Firewall por slice fijo; el usuario no define reglas |
| EX2-R5-I-03 | Reglas de seguridad en OpenStack | 1,4 | ❌ | |
| EX2-R5-I-04 | Salida a Internet (Linux y OpenStack) | 2,1 | 🟡 | Linux ✅ (MS-16); OpenStack ❌ (falta router Neutron) |
| EX2-R5-I-05 | Acceso desde Internet (Linux y OpenStack) | 2,8 | ❌ | Linux: ruta 10.60.9.0/24; OpenStack: IP flotante |
| EX2-R5-I-06 | Configurar dinámicamente el switch físico para limitar broadcasts | 3,5 | ❌ | En fase 2 el switch (192.168.201.5) no es accesible |

### R1C — Slice Manager (referencia: criterios del EX1)

> **Contradicción en el enunciado:** la «Nota de EX2» dice que el EX2 evalúa la implementación de R1B y **R1C**, pero la
> rúbrica detallada del EX2 (págs. 17–18) no tiene bloque R1C y suma 100 pts sin él (el propio documento lo advierte).
> Conviene confirmarlo con el JP. Se evalúa aquí con los criterios `EX1-R1C-D-*`, los únicos detallados.

| Criterio (EX1) | Estado | Nota |
|---|---|---|
| R1C-D-01 Flujo completo y en orden correcto | ✅ | Slice-manager → platform-manager; orden y compensación (MS-05, MS-14) |
| R1C-D-02 Paralelismo / rapidez | ✅ | VMs en paralelo; Linux 3 VMs en un servidor: 45 s con CirrOS 0.6.2 (MS-17) |
| R1C-D-03 Sin race conditions ni sobreasignación | ✅ | Reservas atómicas en SQLite; rechazo previo si falta capacidad o flavor |
| R1C-D-04 Monitorear recursos asignados | ✅ | Monitoreo D-13 y página Recursos (asignado y uso real por VM) |
| R1C-D-05 Validar consistencia de los recursos | ✅ | `inspect`, diagnósticos y reconciliación por slice |
| R1C-D-06 Peticiones de módulos autorizados y usuarios autenticados | ✅ | Tokens de servicio entre microservicios + IAM (roles) |

### R2 — Clúster Linux (referencia: criterios del EX1, re-verificados en fase 2)

> R2 se evaluó en el EX1 (topología individual). Aquí se verifica que siga cumpliéndose en el clúster de fase 2, ya que
> la demo del EX2 lo usa.

| Criterio (EX1) | Estado | Nota |
|---|---|---|
| R2-I-01 VMs en los servidores seleccionados | ✅ | Servidor elegible por VM desde el editor |
| R2-I-02 Enlaces entre VMs de servidores distintos | ✅ | QinQ; ping 3/3 (MS-12, MS-14) |
| R2-I-03 API diseñada completa | ✅ | Platform-manager; la web expone el ciclo de vida |
| R2-I-04 Errores y reintentos | ✅ | Reintentos, compensación, diagnósticos por slice |
| R2-I-05 Envío y manejo de imágenes | ✅ | Desde Glance al almacén Linux con SHA-256 y `qemu-img` |
| R2-I-06 Borrado de VMs y recursos (TAP, OVS…) | ✅ | Sin QEMU, puertos ni namespaces tras borrar |
| R2-I-07 Consola virtual con tokens | ✅ | noVNC en la web (MS-15) |
| R2-I-08 Salida a Internet a las VMs que lo requieran | ✅ | MS-13, MS-16 |
| R2-I-09 Acceso desde Internet (IP pública) | ❌ | DNAT programado; falta la ruta 10.60.9.0/24 |
| R2-I-10 Uso eficiente del disco (qcow2) | ✅ | Capa por VM sobre una base compartida |
| R2-I-11 Pedidos concurrentes | 🟡 | Soportado por diseño; falta demostrarlo en fase 2 |
| R2-I-12 Borrado inteligente de imágenes | ✅ | 0 bases en caché tras borrar |
| Diseño: monitoreo de recursos (R2-D-05) | ✅ | Acción `metrics` del agente y microservicio `monitoring` |
| Diseño: troubleshooting por slice (R2-D-07) | ✅ | `diag_console`, `diag_capture`, `diag_ovs`, `diag_datapath` |

## Diseño y documentación (evaluación del jurado)

| Bloque | Pts | Estado | Nota |
|---|---|---|---|
| EX2-R0-D-01/02/03 — exposición, HLD documentado, reporte de pruebas | 14 | 🟡 | Hay evidencias MS-01 a MS-17; **HLD y reporte de pruebas sin actualizar** |
| EX2-R3-D-01..05 — servicios mínimos, uso eficiente de APIs, topologías, capa 2, ver proyectos | 12 | 🟡 | Casi todo implementado; falta sustentarlo en el HLD |
| EX2-R4-D-01..07 — monitoreo, función objetivo, sobreaprovisionamiento, congestión, slice como un todo, tiempo límite, zona | ≈18 | 🟡 | Implementado: monitoreo, función objetivo Z, ratio 2,0 y límite 85 %, slice completo, 1 s, zona. **Falta sustentarlo en el HLD (dice BFD)** |

## Prioridades

1. ~~**R4:** inventario y monitoreo + algoritmo integrado~~ **Hecho (MS-17)**; queda definir las zonas reales.
2. **R0 y R4-D:** actualizar el HLD con la arquitectura real (D-08 a D-16, BCDP v2, monitoreo) y armar el reporte de
   pruebas con MS-01 a MS-17.
3. **R5:** router e IP flotante en OpenStack, reglas de seguridad, acceso desde Internet.
4. **Consultas al JP:** ruta 10.60.9.0/24, disco en OpenStack, enlaces sin IP en Nova, router/IPs flotantes, zona de
   disponibilidad, **cómo cumplir R5-I-06 sin acceso al switch físico** y **si R1C se evalúa en el EX2**.
