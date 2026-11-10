# ESTADO DEL PROYECTO — PUCP Private Cloud Orchestrator G5

> **Leer primero en cada sesión nueva.** Última actualización: 2026-11-08 (integración `app`, Docker en el app server, D-10).

## Estado general
- **F0 (auditoría) y F1 (núcleo de Slice Manager agnóstico + driver OpenStack) terminadas.**
  Crear, consultar y borrar un slice en OpenStack desde la API G5 funciona y está probado en el clúster real.
- Código en `github.com/DavidEscobal/Ingenier-aDeRedesCloud-G5`, rama **`fase2`** (integra la rama `app`: gateway, IAM, slice-manager; `main` = EX1 sin tocar).
  El repositorio es **público**; el enunciado pide privado (lo decide el dueño, David Escobal).
- Suite automática: **89 pruebas OK** del núcleo (`PYTHONPATH=tools/winshim python -m unittest discover -s tests`)
  y **14 OK** de los servicios `app` (`tests/app`, requiere las dependencias de `services/*/requirements.lock`).
- **Arquitectura: microservicios en Docker Compose (D-08) + interfaz web (D-10).** Slice Manager NO está completo:
  falta conectarlo al platform-manager, Topology Manager, borradores, edición, VM Placement
  y red/seguridad en OpenStack (ver "Próxima sesión").

## Implementación actual (rama `fase2`)
| Componente | Archivo | Estado |
|---|---|---|
| API REST (multiproveedor), auth por token, OpenAPI 2.1.0 | `g5/api.py`, `api/openapi.json` | Implementado |
| Validación genérica + por proveedor | `g5/model.py`, `g5/drivers/*` | Implementado |
| Contrato `ProviderDriver` + `OpContext` | `g5/drivers/base.py`, `g5/domain.py` | Implementado |
| Driver Linux (EX1: QEMU/OVS/QinQ/NAT) | `g5/drivers/linux.py`, `g5/agent.py` | Implementado (config de fase 1; falta `cluster.json` de fase 2) |
| Driver OpenStack (proyecto por slice, VLAN, puertos, VMs, consola) | `g5/drivers/openstack/` | Implementado y probado en real |
| Store: reservas, idempotencia, `provider`, diario `resources` | `g5/store.py` | Implementado |
| Engine: cola local, reintentos, compensación, estados | `g5/engine.py` | Implementado |
| CLI / demo / web mínima (EX1) | `g5/cli.py`, `g5/demo.py`, `g5/web.py` | Existente (web solo plantillas Linux) |
| Plantillas | `templates/ex1.json`, `lineal.json`, `anillo.json` (Linux, fijas), `templates/os-lineal.json` | Fijas; sin generadores |

Historial de la auditoría F0 del código EX1: commit `b04a466`; limitaciones originales: worker obligatorio,
plantillas escritas a mano, secuencia Linux fija (resuelto con `LinuxDriver`), web con token admin, sin Topology
Manager / Placement / IAM con login.

## Estado de la infraestructura (para no romper nada)
- **App server** (`ssh g5-app`, 10.20.11.248): EX1/F1 en `~/g5-orchestrator` (commit f23b9cb),
  credenciales locales de la API en `config/` (600), base de la prueba en `state-f1/`. **API temporal detenida (2026-11-08).**
  Credenciales OpenStack en `~/.g5/openstack.env` (600, no leer ni imprimir).
- **Docker 28.1.1 + Compose v2.35.1** instalados (2026-11-08); `ubuntu` en el grupo `docker`; linger activado.
  Código de microservicios en `~/g5-app` (copia de `fase2`, revisión en `~/g5-app/REVISION`); imágenes
  `g5-app-{gateway,iam,slice-manager,platform-manager}` construidas. Ningún contenedor levantado aún.
- **Microservicios corriendo (2026-11-10):** `iam`, `slice-manager`, `gateway` en Docker, los tres *healthy*; solo el
  gateway publica `127.0.0.1:8000`. IAM inicializado (admin `admin123`; contraseña solo la conoce el usuario).
  Salud, 401 sin credenciales, login, rol admin y revocación verificados: `docs/evidencias/F2/MS-01_*.md` (7/7 OK).
  El volumen `g5-app_iam-data` lo creó una revisión manual (aviso inofensivo de Compose); contiene `iam.db` y `jwt.key`.
- **Platform-manager + os-tunnel corriendo (2026-11-10):** perfil `platform`; `os-tunnel` (sidecar elegido por el
  usuario) reenvía 5000/8774/9696/9292/6080 vía gateway dentro de la red `control`; `g5-tunnels` del host intacto.
  Config en `~/g5-app/deploy/platform-config/` (700/600). API autenticada y Keystone/Nova/Neutron/Glance
  verificados desde el contenedor, solo lectura: `docs/evidencias/F2/MS-02_*.md`.
- **Despliegue desde el contenedor (2026-11-10):** MS-03 falló por falta de disco (flavor de 4 GB; compensación
  correcta). Con autorización se creó el flavor público **`g5-1c-512m-1g`** (1 GB raíz) y `templates/os-lineal-1g.json`:
  **MS-04 READY en 20 s** (3 VMs ACTIVE, VLAN 215/574, IP fijas) y borrado limpio en 20 s.
  Capacidad de los computes: 9 GB de disco c/u; las VMs de `lab5` y `topo1_lab6` ocupan casi todo worker1 y worker2.
- **Paso 5 hecho (MS-05, 2026-11-10):** login → crear `os-lineal-1g` **por el gateway** → READY en 20 s → listado con
  dueño/curso → borrado DELETED en 15 s, 8/8 OK; OpenStack limpio. Curso `TEL141` creado en IAM. Identidad de servicio
  `slice-manager` en `platform-config/keys.json` (token 644 en carpeta 700).
- **Roles en real (MS-06, 2026-11-10):** prof1 crea y borra un slice real; prof2 y alumno1 aislados (404), alumno y
  curso ajeno rechazados (403), admin ve todo: 13/13. IAM tiene `prof1`, `prof2`, `alumno1` en TEL141 (contraseñas
  aleatorias desconocidas; el admin las restablece si se necesitan para la demo).
- **Web parte 1 desplegada (2026-11-10):** servicio `web` (React + Vite, nginx sin privilegios) en `127.0.0.1:8080`
  del app server; `/api` → gateway. Login, menú por rol, Mis slices (estado en vivo, borrar), detalle con eventos y
  Nuevo slice (plantilla os-lineal-1g). Acceso: `ssh -N -L 8080:127.0.0.1:8080 g5-app`. **MS-07:** el usuario creó y borró `os-lineal-grupo5`
  desde el navegador (READY y borrado limpio).
- **Paso 6 implementado (2026-11-10):** servicio `topology-manager` (FastAPI + SQLite, volumen `topology-data`):
  generadores lineal/anillo/malla/árbol/bus/estrella, combinación, borradores versionados, import/export y
  compilación a spec (10.60.k.0/24). Web parte 2: Topologías + editor React Flow + desplegar como slice. 8 servicios
  healthy en el app server. **MS-08:** el usuario combinó anillo + árbol, guardó v1/v2, exportó/importó, desplegó
  6 VMs (READY en worker1-3) y borró; OpenStack limpio.
- **Consola por VM desde la web (MS-09, 2026-11-10):** botón Consola en el detalle; noVNC vía `/console/` de la web.
- **Siguiente:** pendientes de R1B — asignación de slices a alumnos (IAM), edición de slices desplegados, consumo de
  recursos (D-13), importar imágenes.
- `fase2` local va **varios commits por delante** de `origin/fase2`, sin push (pendiente de autorización).
- Túneles: servicio de usuario `g5-tunnels` activo (`systemctl --user status g5-tunnels`).
- **Gateway** (`ssh g5-gw`): llave del app server autorizada solo para túneles; respaldo en
  `~/.ssh/authorized_keys.bak-20261103`. No se tocó iptables.
- **OpenStack** (2026-11-08): ningún recurso `g5-*`. Existen proyectos de laboratorio `lab5` (2 VMs) y `topo1_lab6`
  (3 VMs, 3 redes) que no son del orquestador: no tocarlos; ocupan capacidad de los workers.
- Acceso desde la PC del usuario: alias `g5-app` y `g5-gw` en `~/.ssh/config` con la llave `id_ed25519_g5`.

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
(Windows con stubs, OpenStack falso). Publicado en `origin/fase2`.

Prueba real en el clúster (código f23b9cb desplegado en `~/g5-orchestrator` del app server, API temporal en
127.0.0.1:8085, base `state-f1`):
- **TC-1.5.3 PASS** — `templates/os-lineal.json` creado por la API G5 en 20,3 s: proyecto `g5-be4b301b…`,
  redes vlan/physnet1 (VLAN 103 y 345, sin túneles), 4 puertos con IPs fijas, vm1/vm3 en worker2 y vm2 en
  worker1 (enlaces entre hosts), todas ACTIVE. Evidencia: `docs/evidencias/F1/TC-1.5.3_*.json`.
  Horizon: `docs/evidencias/F1/TC-1.5.4_horizon_resumen_uso.png` (faltan capturas de Instances/Topology y ping).
- **TC-1.7.2 PASS** — borrado por la API G5 en 18,1 s: sin proyecto, servidores, redes, subredes ni puertos
  `g5-*`; diario con 12 recursos DELETED; OpenStack quedó igual que antes (solo lab5 y la red external).
  Evidencia: `docs/evidencias/F1/TC-1.7.2_*.json`. API temporal detenida.
- Riesgo observado: con 3 VMs de 4 GB el disco de worker1/worker2 llega a 8/9 GB. Coordinar pruebas.

## LAB6 2026-2 (guía `GUIA_LAB6_TEL141_2026-2`)
- **Informe previo: jueves 5 de noviembre de 2026.** Evaluación continua (explicación del plan): domingo 8 de noviembre, 23:59.
  Las fechas del enunciado del proyecto son de 2025-2 y no se usan para el calendario.
- Actividad 2: `docs/pruebas/PLAN_PRUEBAS_SLICE_MANAGER.md` y `.docx` — 51 casos (12 PASS [REAL], 22 PASS [AUT],
  17 NT por funciones pendientes de F2–F4). El plan está redactado; Slice Manager **no** está completo.
- Actividad 1: la ejecuta el grupo en el headnode con `docs/pruebas/LAB6_ACTIVIDAD1_GUIA_EJECUCION.md`.

## Pendientes que dependen del grupo o de permisos
| Pendiente | Quién | Nota |
|---|---|---|
| Informe previo LAB6 (Actividad 1 en el headnode + pasar el plan al template PAIDEIA) | Grupo | **Jueves 5 nov** |
| Explicación del plan de pruebas (evaluación continua) | Grupo | Domingo 8 nov 23:59 |
| Agregar `permitopen="192.168.202.1:8778"` (Placement) a la llave del gateway | Usuario | Necesario en F3 |
| Aclarar autoría de las reglas `LAB5_DIRECT` (origen 10.8.0.168) en el gateway | Grupo | D-05 en pausa hasta entonces |
| Repositorio privado + coach `fernandoguzmann` como colaborador (triage) | David Escobal | Requisito del enunciado |
| No recrear `cloud_admin`, no tocar proyectos `g5-*`, abrir túneles LAB6 en laptops (no en el app server) | Grupo | Evita romper el orquestador |
| Decidir qué nodo Linux hace de gateway de slices en fase 2 | Grupo | Necesario para el `cluster.json` Linux |
| Carpeta `requerimientos_md/Imagenes/` sin commitear (captura de un portal externo) | Usuario | Decidir si se versiona |

## Próxima sesión: microservicios en el app server y servicio web (D-08, D-10)
Pasos (cada uno con tests y commit propio; autorización antes de cambios remotos):
1. ~~Levantar `iam`, `slice-manager`, `gateway`~~ **Hecho 2026-11-10** (MS-01, 7/7 OK).
2. ~~Platform-manager en compose + acceso a OpenStack~~ **Hecho 2026-11-10** (sidecar `os-tunnel`, MS-02).
3. ~~Paso 5: slice-manager → platform-manager~~ **Hecho 2026-11-10** (D-12, MS-05, 8/8 OK).
4. **Web, parte 1** (D-10): login, menú por rol y "Mis slices" (listar, desplegar Linux/OpenStack, estado, borrar, consola).
5. **Topology-manager + web, parte 2**: generadores lineal, malla, árbol, anillo, bus (esquema versionado); borradores
   (combinar predefinidas, agregar nodos/enlaces, capacidad por VM); exportar/importar; lienzo con React Flow.
   Casos 1.3.2–1.3.5 y 1.2.5.
6. **Edición de slices desplegados** con control de versión (409 si la versión es obsoleta). Casos 1.11.1–1.11.2.
7. **Web, parte 3**: cursos/usuarios (IAM), importar imágenes (image-catalog, solo metadatos), consumo de recursos.
Luego: placement (D-07, cuando se decida la heurística) y monitoreo → `cluster.json` Linux de fase 2 → R5 con
`SwitchController` (D-09).

## Decisiones aprobadas (2026-11-03)
| ID | Decisión | Motivo | Pendiente de verificar |
|---|---|---|---|
| D-01 | El orquestador G5 corre en la VM **app server** de la topología de fase 2 (no en headnode ni en server4). | La topología grupal prevé `app` para la aplicación; headnode queda solo para el control de OpenStack. Reemplaza la propuesta del HLD §3.6 (contradicción C6). | Versión de Python, acceso desde `app` a MGMT 1 (192.168.201.0/24) y MGMT 2 (192.168.202.0/24), resolución de `controller`, puertos expuestos. |
| D-02 | El driver OpenStack usa un **cliente REST propio** (biblioteca estándar `urllib`, igual que el resto de EX1) contra Keystone, Nova, Neutron y Glance; no `openstacksdk`. | Transparencia del uso de tokens y APIs (rúbrica LAB6) y facilidad para simular con mocks. | Microversión de Nova soportada (descubrirla, no fijarla). |
| D-03 | **Un proyecto OpenStack por slice.** | Permite ver cada slice por separado en Horizon (R3, EX2-R3-D-05 / R3-I-06) y simplifica el borrado. | Permisos del usuario de servicio para crear proyectos y asignar roles en el dominio `Cloud`. |
| D-06 | **Vigente:** el app server accede a las APIs OpenStack por **túneles SSH a través del gateway** (puerto 22): `127.0.0.1:55000/58774/59696/59292/56080/50080` → `192.168.202.1:5000/8774/9696/9292/6080/80`. D-05 queda **en pausa**. | En el gateway hay 4 reglas DNAT activas no guardadas (`LAB5_DIRECT`, origen 10.8.0.168) de autoría desconocida; no se toca iptables hasta que el grupo aclare quién las puso y por qué. Los túneles además cifran el tráfico. | Mantener los túneles vivos (reinicio automático); confirmar con el grupo el origen de `LAB5_DIRECT`. |
| D-05 | (En pausa) El app server accede a las APIs OpenStack mediante **DNAT en el gateway** (alternativa LAB6 §4.3), restringido a origen `10.20.11.248`: 55000→5000, 58774→8774, 59696→9696, 59292→9292, 56080→6080, 50080→80 hacia `192.168.202.1`. Aprobado por el grupo y el profesor ("con mucho cuidado"). | El app server no tiene interfaz en MGMT 2; el gateway sí (ens5 192.168.202.10) y ya hace DNAT de SSH. Evita depender de túneles. | Riesgo aceptado: tráfico HTTP sin cifrar en 10.20.11.0/24 (credenciales/tokens). Mitigación: origen restringido, respaldo de reglas antes de cambiar, `netfilter-persistent save` solo tras verificar. Vigilar cambio de IP del app server (DHCP) y recreación del gateway. |
| D-07 | **Pendiente:** heurística de VM Placement **aún no definida**; el módulo no se implementa todavía. | El grupo presentó WFD en una reunión previa; el HLD §4.7 describe BFD y el contexto de Codex (8-nov) propone BFD. Insumo para decidir: `jupyter notebooks-20261106/07_heuristicas_placement.ipynb` (FFD/BFD/WFD vs CP-SAT, misma instancia). | Definir objetivo (balancear vs consolidar), puntuación multidimensional y admisión por slice completo; luego alinear HLD §4.7 (§4.7.1, §4.7.4, §4.7.9, §4.7.10). |
| D-08 | **Microservicios con Docker Compose en el app server.** Implementación inicial: `gateway`, `iam`, `slice-manager` (de la rama `app`), `platform-manager` (núcleo de `fase2`: API, Engine, drivers) y `console`. Después: `topology-manager`, `image-catalog` (solo metadatos), `placement` y `monitoring`. Sin AWS ni NoSQL; cola en base de datos. | El diseño define ~16 módulos lógicos; se implementan los que tienen datos o ciclo de vida propios. Dueños de datos: IAM (usuarios, roles, cursos, asignaciones), slice-manager (borradores y plantillas), platform-manager (slices desplegados, operaciones, reservas, recursos del proveedor). Networking queda dentro de los drivers (como G2). | Verificar CPU/RAM/disco y Docker en el app server; acceso de contenedores a los túneles; credenciales montadas como secretos. |
| D-09 | **Control dinámico de ovs1/ovs2 (R5-I-06) por SSH desde el driver** detrás de una interfaz `SwitchController`; migrar a un servicio `network-controller` por la Control Network solo si el jefe de práctica confirma ese uso. | Funciona con la red de gestión actual (ovs1 192.168.201.5, ovs2 192.168.202.5) y reutiliza el agente de EX1 (candado y registro por slice). | Hoy la S-VLAN es por slice (filtra por slice, no por enlace): evaluar una S-VLAN por enlace. ovs2 lo comparte OpenStack: tocar solo VLANs de slices G5. Inspección de solo lectura y autorización antes de cambiar switches. |
| D-11 | Flavor público **`g5-1c-512m-1g`** (1 vCPU, 512 MB, 1 GB) para slices CirrOS; las plantillas OpenStack usan `disk_gb: 1`. | Con 4 GB por VM y computes de 9 GB solo caben 6 VMs en el clúster (MS-03). CirrOS ocupa 44 MB virtuales. | Si se usan imágenes más grandes (Ubuntu), crear flavors acordes o pedir más disco. |
| D-12 | **Paso 5: slice-manager → platform-manager con token de servicio.** El usuario llama al gateway; el slice-manager obtiene identidad y rol de IAM (`/v1/auth/me`) y autoriza la creación con `slice.create` sobre el curso; llama al platform-manager con su propio token (rol `service` en `keys.json`) y guarda slice → dueño/curso en su SQLite. Consultar/borrar: dueño o admin (404 a terceros). El platform-manager no cambia. | Separa intención (slice-manager) de ejecución (platform-manager) sin exponer el token del usuario al núcleo; reutiliza el control de idempotencia existente (clave derivada por usuario). | IAM aún no tiene identidad de servicio: el slice no se registra como recurso IAM (asignación a alumnos, `professor_can_modify` y cuotas pendientes). |
| D-13 | **Monitoreo: PENDIENTE de decisión.** Opción intermedia propuesta: servicio `monitoring` propio que lee Nova (`os-hypervisors`) y el platform-manager y expone `/metrics`; Prometheus como almacén con historial; `node_exporter` solo en nodos Linux; la web muestra el consumo por rol; Grafana opcional solo para admin. | La rúbrica pide ver el consumo en la UI; el historial sirve al placement (D-07). | Confirmar con el JP si se puede instalar `node_exporter`; retención según el disco del app server (6 GB libres). |
| D-10 | **Interfaz web como microservicio `web`** en el mismo compose: React + Vite compilado a estáticos y servido por un contenedor ligero (nginx); lienzo de topologías con React Flow. Solo habla con el gateway. Diseño propio de G5 (G2 es referencia de funcionalidad, no de apariencia). | R1B (12 pts) es la UI: predefinidas, edición, borradores, exportar/importar, capacidad por VM, mis slices, consumo, consola. La demo final debe mostrar el flujo visual ejecutado de verdad sobre el clúster. No toca la lógica probada del núcleo. | Node.js para desarrollo local; el gateway debe exponer las rutas de slices, borradores y consola; TLS en el punto de entrada antes de exponerlo. |
| D-04 | Primera fase de implementación: F0 (auditoría) y luego F1 (núcleo de Slice Manager agnóstico + driver OpenStack mínimo: crear, consultar y eliminar un slice lineal). | Cubre la experiencia del LAB6, R3-I y R1B-I-01, y fija el modelo del que dependen R1B, R4 y R5. | — |

## Restricciones
- No inventar funcionalidades implementadas.
- No declarar pruebas como aprobadas sin evidencia real.
- No modificar infraestructura sin autorización.
- No exponer credenciales ni tokens.
- Mantener trazabilidad entre requerimientos, módulos, pruebas y evidencias.
