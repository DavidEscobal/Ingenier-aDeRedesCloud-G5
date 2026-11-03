# ESTADO DEL PROYECTO — PUCP Private Cloud Orchestrator G5

## Estado general
Actualmente estamos en fase de análisis y planificación de implementación.

## Objetivo inmediato
Comenzar la implementación real de la arquitectura del proyecto,
alineada con los criterios de EX1 y EX2, y con especial prioridad
en los componentes necesarios para el plan de pruebas de Slice Manager
solicitado en el Laboratorio 6.

## Documentación disponible
- CLAUDE.md
- AGENTS.md
- Arquitectura_md/
- Laboratorio_md/
- requerimientos_md/
- requerimientos_md/rubrica_md/
- requerimientos_md/trazabilidad_md/

## Implementación actual
Auditoría F0 (2026-11-03) del repositorio EX1
`github.com/DavidEscobal/Ingenier-aDeRedesCloud-G5`, commit `b04a466` (12-oct-2026).
Clonado solo para lectura; todavía no está integrado en este workspace.

- Paquete `g5/` (~2 800 líneas, solo biblioteca estándar; `websockify` para la consola):
  `api`, `model`, `store`, `engine`, `backend`, `agent`, `console`, `cli`, `demo`, `web`, `manage`.
- Suite `tests/`: 60 pruebas, **OK** en Windows con Python 3.12 usando stubs de `fcntl`/`pwd`
  (sin bloqueo real entre procesos). No se ejecutó en Linux ni sobre la infraestructura.
- Reutilizable: agente Linux (QEMU/OVS/QinQ/NAT/dnsmasq), reservas SQLite atómicas,
  idempotencia, compensación, tokens de consola, cliente HTTP.
- Limitaciones verificadas en código: el `worker` es obligatorio por VM y la capacidad sale
  del JSON de configuración; plantillas ex1/lineal/anillo escritas a mano (VMs, IPs, CVIDs y
  workers fijos); secuencia de despliegue Linux fija en `engine.py`; modelo de solicitud
  ligado a Linux (CVID, IP manual, SO ubuntu/cirros, /20–/27); la web usa siempre el token
  admin; no hay Topology Manager, VM Placement, driver OpenStack, IAM con login ni monitoreo
  histórico. La configuración de ejemplo es de fase 1 (10.0.10.0/24, server4 como gateway, OFS).

## Prioridades
1. Auditar la arquitectura G5.
2. Revisar cobertura de criterios EX1 y EX2.
3. Proponer plan maestro de implementación por fases.
4. Identificar los componentes mínimos para comenzar a probar Slice Manager.
5. Diseñar estructura de repositorio y estrategia de documentación final.

## Decisiones aprobadas (2026-11-03)
| ID | Decisión | Motivo | Pendiente de verificar |
|---|---|---|---|
| D-01 | El orquestador G5 corre en la VM **app server** de la topología de fase 2 (no en headnode ni en server4). | La topología grupal prevé `app` para la aplicación; headnode queda solo para el control de OpenStack. Reemplaza la propuesta del HLD §3.6 (contradicción C6). | Versión de Python, acceso desde `app` a MGMT 1 (192.168.201.0/24) y MGMT 2 (192.168.202.0/24), resolución de `controller`, puertos expuestos. |
| D-02 | El driver OpenStack usa un **cliente REST propio** (`requests`) contra Keystone, Nova, Neutron y Glance; no `openstacksdk`. | Transparencia del uso de tokens y APIs (rúbrica LAB6) y facilidad para simular con mocks. | Microversión de Nova soportada (descubrirla, no fijarla). |
| D-03 | **Un proyecto OpenStack por slice.** | Permite ver cada slice por separado en Horizon (R3, EX2-R3-D-05 / R3-I-06) y simplifica el borrado. | Permisos del usuario de servicio para crear proyectos y asignar roles en el dominio `Cloud`. |
| D-04 | Primera fase de implementación: F0 (auditoría) y luego F1 (núcleo de Slice Manager agnóstico + driver OpenStack mínimo: crear, consultar y eliminar un slice lineal). | Cubre la experiencia del LAB6, R3-I y R1B-I-01, y fija el modelo del que dependen R1B, R4 y R5. | — |

## Restricciones
- No inventar funcionalidades implementadas.
- No declarar pruebas como aprobadas sin evidencia real.
- No modificar infraestructura sin autorización.
- No exponer credenciales ni tokens.
- Mantener trazabilidad entre requerimientos, módulos, pruebas y evidencias.

## Próximo paso
Fase 0: incorporar al workspace el código fuente real de EX1 (ZIP o repositorio
GitHub), ejecutar su suite de pruebas y mapearlo a los módulos de la arquitectura.
Después, inventario de solo lectura de la infraestructura (con autorización) para
verificar los puntos pendientes de D-01 a D-03.