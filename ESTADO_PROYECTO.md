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

## Inventario de fase 2 verificado (2026-11-03, solo lectura)
- app server: `app`, 10.20.11.248/24 (DHCP), Ubuntu 20.04.2, Python 3.8.10; sin interfaz en MGMT 1/2.
- gateway: 10.20.11.245 (ens3), 192.168.201.10 (ens4, MGMT 1), 192.168.202.10 (ens5, MGMT 2); `ip_forward=1`;
  `iptables-persistent` instalado; FORWARD policy ACCEPT; MASQUERADE de salida por ens3.
- Gestión (de `/etc/iptables/rules.v4`, mayo 2025): server1–4 = 192.168.201.1–4, ovs1 = .201.5;
  headnode = 192.168.202.1, worker1–3 = .202.2–4, ovs2 = .202.5.
- Desde el gateway responden Keystone (300), Nova (200), Neutron (200), Glance (300), noVNC (404 en raíz), Horizon (200).
- Desde el app server no responde ninguna API (sin ruta a 192.168.202.0/24, sin DNAT de APIs).
- Control Network (diagrama de fase 2, líneas rojas app↔OVS_1/OVS_2): el app server tiene `ens4` y `ens5`
  UP **sin IP**; el gateway tiene `ens6` y `ens7` DOWN (probables troncales hacia OVS_1/OVS_2). Sin configurar.
  Relevante para R5-I-06 (control dinámico del switch) y R5-I-04 (salida a Internet); se planifica en F4.
- Túneles D-06 activos en el app server (llave `~/.ssh/id_ed25519_g5_gw`, autorizada en el gateway con
  `restrict`, `from="10.20.11.248"` y `permitopen` a los 6 puertos). Keystone respondió 201 con token
  acotado a `cloud_admin`/`Cloud` (roles admin, member, reader). El catálogo anuncia `http://controller:<puerto>`
  y también Placement en :8778, que aún no tiene túnel.
- Los túneles corren como servicio systemd de usuario `g5-tunnels` (`~/.config/systemd/user/g5-tunnels.service`,
  `Restart=always`, 10 s, máx. 20 reinicios en 10 min). Probado: tras matar el proceso se relanzó solo (NRestarts=1).
  **Pendiente:** `sudo loginctl enable-linger ubuntu` (Linger=no) para que arranque tras reiniciar el app server sin sesión abierta.

## Inventario OpenStack (2026-11-03, solo lectura)
Evidencia: `docs/evidencias/F0/inventario_openstack_20261103.json` (sin tokens).
- Servicios: Keystone, Nova (conductor/scheduler en headnode; compute en worker1–3, todos `up`),
  Neutron (agentes OVS en headnode y workers, DHCP, L3, metadata vivos), Glance, Placement en catálogo.
- Nova API v2.1, microversión 2.1–**2.87** (permite fijar host ≥2.74).
- Zonas: `nova` = worker1–3; `internal` = headnode. No hay más zonas definidas.
- Hypervisors (4 vCPU, 3935 MB, **9 GB disco** cada uno): worker1 y worker3 con 1 VM (4 GB disco usados),
  worker2 vacío. El disco es el recurso más escaso.
- Redes: `link_1` (lab5) **vlan / physnet1 / VLAN 319**, port security desactivado; `external` flat/physnet0
  172.20.15.0/24 compartida. No hay redes VXLAN ni routers.
- Proyectos del dominio `Cloud`: `cloud_admin`, `lab5` (instance_1 en worker1, instance_2 en worker3; no tocar).
- Flavor `512MBRAM_1VCPUs_4GBRoot`; imagen `cirros` (qcow2, pública).
- Cuotas `cloud_admin`: 10 instancias, 20 cores, 50 GB RAM; Neutron 100 redes / 500 puertos.

## Fase 1 — implementación y primera prueba real (2026-11-03)
Commits en `fase2`: refactor `LinuxDriver` (08534ef), Store multiproveedor (8ddde75), cliente REST
OpenStack (6d30f56), driver OpenStack (9fd8024), API multiproveedor (f23b9cb). 83 pruebas automáticas OK
(Windows con stubs, OpenStack falso). No se ha hecho push.

Prueba real en el clúster (código f23b9cb desplegado en `~/g5-orchestrator` del app server, API temporal en
127.0.0.1:8085, base `state-f1`):
- **TC-1.5.3 PASS** — `templates/os-lineal.json` creado por la API G5 en 20,3 s: proyecto `g5-be4b301b…`,
  redes vlan/physnet1 (VLAN 103 y 345, sin túneles), 4 puertos con IPs fijas, vm1/vm3 en worker2 y vm2 en
  worker1 (enlaces entre hosts), todas ACTIVE. Evidencia: `docs/evidencias/F1/TC-1.5.3_*.json`.
  Capturas de Horizon y ping realizadas por el usuario (pendiente incorporarlas a `docs/evidencias/F1/`).
- **TC-1.7.2 PASS** — borrado por la API G5 en 18,1 s: sin proyecto, servidores, redes, subredes ni puertos
  `g5-*`; diario con 12 recursos DELETED; OpenStack quedó igual que antes (solo lab5 y la red external).
  Evidencia: `docs/evidencias/F1/TC-1.7.2_*.json`. API temporal detenida.
- Riesgo observado: con 3 VMs de 4 GB el disco de worker1/worker2 llega a 8/9 GB. Coordinar pruebas.

## LAB6 2026-2 (guía `GUIA_LAB6_TEL141_2026-2`)
- **Informe previo: jueves 5 de noviembre de 2026.** Evaluación continua (explicación del plan): domingo 8 de noviembre, 23:59.
  Las fechas del enunciado del proyecto son de 2025-2 y no se usan para el calendario.
- Actividad 2: `docs/pruebas/PLAN_PRUEBAS_SLICE_MANAGER.md` y `.docx` — 51 casos (9 PASS [REAL], 25 PASS [AUT],
  17 NT por funciones pendientes de F2–F4). El plan está redactado; Slice Manager **no** está completo.
- Actividad 1: la ejecuta el grupo en el headnode con `docs/pruebas/LAB6_ACTIVIDAD1_GUIA_EJECUCION.md`.

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
| D-06 | **Vigente:** el app server accede a las APIs OpenStack por **túneles SSH a través del gateway** (puerto 22): `127.0.0.1:55000/58774/59696/59292/56080/50080` → `192.168.202.1:5000/8774/9696/9292/6080/80`. D-05 queda **en pausa**. | En el gateway hay 4 reglas DNAT activas no guardadas (`LAB5_DIRECT`, origen 10.8.0.168) de autoría desconocida; no se toca iptables hasta que el grupo aclare quién las puso y por qué. Los túneles además cifran el tráfico. | Mantener los túneles vivos (reinicio automático); confirmar con el grupo el origen de `LAB5_DIRECT`. |
| D-05 | (En pausa) El app server accede a las APIs OpenStack mediante **DNAT en el gateway** (alternativa LAB6 §4.3), restringido a origen `10.20.11.248`: 55000→5000, 58774→8774, 59696→9696, 59292→9292, 56080→6080, 50080→80 hacia `192.168.202.1`. Aprobado por el grupo y el profesor ("con mucho cuidado"). | El app server no tiene interfaz en MGMT 2; el gateway sí (ens5 192.168.202.10) y ya hace DNAT de SSH. Evita depender de túneles. | Riesgo aceptado: tráfico HTTP sin cifrar en 10.20.11.0/24 (credenciales/tokens). Mitigación: origen restringido, respaldo de reglas antes de cambiar, `netfilter-persistent save` solo tras verificar. Vigilar cambio de IP del app server (DHCP) y recreación del gateway. |
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