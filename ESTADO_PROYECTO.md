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
- **Asignación profesor → alumno (MS-10, 2026-11-10, D-14):** prof1 creó y asignó un slice real; alumno1 lo vio y abrió la
  consola; IAM auditó cada acceso. `prof1`/`alumno1` tienen contraseñas que conoce el usuario (demo).
- **Importar imágenes (MS-11, 2026-11-10, D-15):** el admin importó `cirros-062` desde la web a Glance (20 MB, SHA-256
  registrado) y desplegó 2 VMs con ella (ACTIVE). 9 servicios healthy.
- **Punto de reanudación (2026-11-10, cierre de sesión):** R1B casi completo (pausados: editar slices desplegados por
  decisión del usuario; consumo de recursos espera D-13). R3 completo. R4 y R5 sin implementar; el grupo aún no define
  la heurística (D-07). En el clúster sigue activo el slice `lineal-2` (2 VMs `cirros-062` en worker3): borrarlo.
- **Plan acordado para la próxima sesión (sin depender de la heurística):**
  1. Probar que Nova acepta un host forzado (`availability_zone` `nova:<worker>`) con 1 VM temporal — **pedir
     autorización** (crea recursos).
  2. Inventario de recursos de ambas plataformas (OpenStack `os-hypervisors`; Linux vía agente) + marco de placement con
     contrato (slice completo → asignación o rechazo con motivo, límite de tiempo) y algoritmo **provisional** (WFD)
     intercambiable. Base también de D-13 y del consumo en la web.
  3. R5 en OpenStack: reglas de seguridad por slice, salida a Internet y SSH desde fuera (revisar qué permite el lab).
  4. R0: actualizar HLD y reporte de pruebas con MS-01..MS-11.
  Opcional: propuesta escrita de heurística para que el grupo decida D-07. Linux de fase 2 requiere que el grupo
  elija el nodo gateway de slices y autorizar SSH gateway→nodos e instalar el agente. **Pendiente por decisión del usuario (2026-11-10):** edición de slices ya
  desplegados (requiere aplicar diferencias en OpenStack con compensación). Consumo de recursos: espera D-13.
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

## Inventario Linux de fase 2 (2026-11-12, solo lectura, R2)
- server1–4 = 192.168.201.1–4 (`ens3` gestión; `ens4` UP sin IP = red de datos hacia el switch). Acceso solo con
  contraseña (`ssh -J g5-gw ubuntu@…`); nuestra llave no está autorizada; `sudo` pide contraseña.
- server1–3: 4 vCPU, 3,9 GB RAM, ~6,7 GB de disco libre. server4: 4 vCPU, **7,9 GB RAM**, 6,7 GB libres.
- Los 4: `/dev/kvm`, Open vSwitch 2.13.8, salida a Internet. **QEMU 4.2.1, qemu-utils y genisoimage instalados por el usuario (2026-11-12)**. Alias SSH `g5-s1..4` (llave `id_ed25519_g5` autorizada en los 4).
- Switch (192.168.201.5): no responde desde el gateway ("No route to host").
- **Agente EX1 instalado en server1–4 (2026-11-12)** por el usuario (sudo limitado al agente; `g5qemu` en workers).
  `config/cluster.json` provisional de fase 2 (gitignored; roles como EX1). `manage doctor`: los 4 nodos `ok`.
- **Prueba del switch (2026-11-12):** VLAN 1000 en `ens4` server1↔server2: ping 3/3. El switch de fase 2 ya deja
  pasar tramas etiquetadas sin configurarlo; interfaces de prueba borradas (verificado).
- **Switch administrado opcional** en el driver Linux (commit 57d17e9; test `test_phase2_without_managed_switch_skips_fabric`).
  `cluster.json` de fase 2 sin `switch`. **`manage bootstrap` OK en server1–4 (2026-11-12):** `br-int` con `ens4`,
  QinQ habilitado; `ip_forward=1` solo en server4 (puerta). Siguiente: desplegar `lineal` de prueba desde la PC.
- **MS-12 (2026-11-13): slice Linux de 2 VMs (server1↔server2) con ping 3/3 en ambos sentidos.** Antes falló por
  `dhcpcd` de CirrOS 0.6 (ráfagas MLD, ARP sin respuesta); corregido en el agente (dhcpcd/IPv6 fuera, tope 10 Mbit/s
  por TAP, diagnósticos sin sudo del usuario). Pendiente R2: Internet por server4, SSH publicado, VNC, integración
  con el platform-manager (requiere ampliar `permitopen` del gateway hacia 192.168.201.1-4:22).
- **MS-13 (2026-11-13): Internet selectivo y consola en Linux de fase 2.** vm1 sale a 8.8.8.8 (3/3) por el
  namespace del slice en server4; vm2 sin ruta, como se pidió; VNC de ambas responde `RFB 003.008` por túnel SSH.
  Borrado sin restos (ni namespaces). Pendiente: SSH publicado, topología de más VMs, integración con la web.
- **Integración R2, fase A (2026-11-13, autorizada por el usuario):** llave exclusiva `id_ed25519_linux` en
  `platform-config/ssh/` del app server (no sale de ahí). Gateway: línea nueva `restrict,port-forwarding,
  command="/bin/false",from="10.20.11.248"` con `permitopen` solo a 192.168.201.1-4:22 (respaldo
  `~/.ssh/authorized_keys.bak-20261113`; línea de OpenStack intacta; no ejecuta comandos, verificado).
  server1–4: la llave solo se acepta `from="192.168.201.10"` (respaldos `.bak-20261113`). `platform-config/ssh/config`
  con salto `g5gw`; known_hosts con huellas ECDSA verificadas contra cada servidor (server3=server4 y
  server1=gateway comparten llave de host: imágenes clonadas). `cluster.json` del app server con la sección Linux de
  fase 2 (respaldo `.bak-20261113`), OpenStack intacto. Código del app server actualizado a 55d7f20; solo se
  reconstruyó `platform-manager`. `doctor` desde el contenedor: server1–4 ok. Siguiente: fase B (imagen CirrOS en el
  almacén Linux) y fase C (compilador/web/consola Linux).
- **MS-14 (2026-11-13): slice Linux creado y borrado DESDE LA WEB** (editor → proveedor Linux). Adaptador neutral→Linux
  en el platform-manager (C-VLAN, reparto rotativo provisional server1–3, CirrOS), imagen traída de Glance y
  verificada con `qemu-img` (a8772ca). Ping 3/3 en ambos sentidos; borrado sin restos. READY tardó 391 s por los
  reintentos de `guest_setup`. **Pendientes R2:** acelerar `guest_setup` (esperar fin de arranque), consola Linux
  en el navegador, Internet/publicaciones desde el editor, placement real (D-07).
- **Arranque de CirrOS acelerado (2026-11-13): de 391 s a 57 s hasta READY, sin reintentos.** Diagnóstico con el
  registro de consola nuevo (`console.log` + `diag_console`): (1) el agente tomaba una línea del arranque por prompt y
  escribía el payload a los 3 s → ahora confirma el shell con `echo G5RDY$((6*7))`; (2) CirrOS 0.6 exige meta-data
  NoCloud en JSON (`json2fstree`) → corregido, `datasource: nocloud local`, 0 reintentos EC2 (antes 20, ~55 s);
  (3) virtio-rng para entropía. Ping 3/3 en ambos sentidos, vigilante 1 trama/10 s. Agente 0214bacb en server1–3;
  server4 reinstalado después (0214bacb en los 4). Orquestador: llamada a guest_setup > espera del agente (cdef4d7).
- **MS-15 (2026-11-13): consola noVNC de VMs Linux desde la web.** `/lconsole/` (nginx) → websockify+noVNC en el
  platform-manager (:6080, red interna, token que vence; túnel de 10 min) → túnel SSH al VNC del worker. Llave del
  orquestador en server1–4 ahora `from="192.168.201.10",no-agent-forwarding,no-X11-forwarding,permitopen="127.0.0.1:*"`
  (cambio hecho por el usuario; respaldo `authorized_keys.bak-consola`); reenviar a otros equipos sigue prohibido
  (verificado).
- **MS-16 (2026-11-13): salida a Internet por VM desde el editor (Linux).** Casilla en el editor; el adaptador da a
  cada VM con Internet una red de acceso propia (`10.200.i.0/27`, NIC `inet0`) hacia la puerta del slice (24abd2b).
  n1 → 8.8.8.8 3/3; n2 sin ruta; enlace n1↔n2 3/3. Pendiente R2: SSH publicado (ruta 10.60.9.0/24 en el gateway,
  coordinar con el JP), topología grande y concurrencia, placement (D-07).
- Gateway: `ens6` DOWN; **`ens7` ahora UP con 172.31.255.1/30** y existe la ruta `10.60.10.0/24 via 192.168.202.1`
  (cambios ajenos a esta sesión, posteriores al 2026-11-03: averiguar quién los hizo). No hay ruta para `10.60.9.0/24`.
- Para R2 falta: autorizar llave en los servidores, resolver sudo para el agente, instalar QEMU, ubicar el switch,
  decidir el nodo puerta de los slices Linux y escribir `cluster.json` de fase 2.

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

## Brecha frente a la demo del Ex2 (referencia: `Contexto_md/Ex2_Validacion_de_Implementacion.md`, 2026-11-13)
El documento es el **Ex2 de 2026-1** (13/07/2026): sirve como referencia de lo que se pedirá; el de 2026-2 puede variar.
Estado por paso: ✅ hecho · 🟡 parcial · ❌ falta.

| Paso | Pide | Estado | Nota |
|---|---|---|---|
| 2 | Zona de disponibilidad con servidores 2–4 (sin server1) | ❌ | Sin concepto de zona; hoy server4 es puerta y server1–3 workers (al revés de lo pedido) |
| 3 | VMs en servidores indicados, Ubuntu 24.04 minimal, 1 GB/1 vCPU | 🟡 | **Servidor por VM en el editor (ce6aafd); host forzado de Nova probado: vm1@worker1 (2026-11-13)**. Falta Ubuntu |
| 4 | Carga con `stress-ng` (80 % RAM/CPU) | 🟡 | Manual por consola; requiere Ubuntu |
| 5 | Módulo de monitoreo (asignado y usado) de ambos clústeres | ❌ | D-13 pausado: **bloqueante** |
| 6 | Procesos QEMU en workers OpenStack | 🟡 | Manual; confirmar acceso SSH a los workers |
| 7 | Explicar placement, no fijo | ❌ | Hoy reparto por turnos; falta R4 (BFD/BCDP) con datos del monitoreo |
| 8 | Crear `Ex2_GXX_test` en el editor sin desplegar | ✅ | Nombres con mayúsculas y `_` (ce6aafd) |
| 9 | Exportar la topología y explicar parámetros | ✅ | Exportar JSON |
| 10 | Importar como `Ex2_GXX_test_2` | ✅ | Importar + nombres del examen (ce6aafd) |
| 11 | Desplegar en OpenStack según placement | ❌ | Depende de R4 |
| 12 | Horizon (proyecto y VMs por worker) + QEMU | ✅ | Proyecto `g5-…` por slice |
| 13 | Errores y reintentos | ✅ | Reintentos y compensación |
| 14 | Enlaces punto a punto en Horizon | ✅ | Una red por enlace |
| 15a | VNC a todas las VMs | ✅ | Consola web en Linux y OpenStack |
| 15b | VM4 como OVS con 3 interfaces **sin IP** | 🟡 | Enlaces «Sin IP» en el editor (OpenStack: red sin subred; Linux: interfaz sin dirección; ce6aafd). Falta probar en real y reinstalar el agente Linux (fab95970) |
| 15c–e | IPs manuales 10.100.10.x, tcpdump, ping | 🟡 | Depende de 15b y de Ubuntu (CirrOS no trae tcpdump/OVS) |
| 16 | Internet en VM4 y VM5 | 🟡 | Linux ✅ (MS-16); OpenStack ❌ (R5) |
| 17 | SSH desde fuera a VM4 y VM5 | ❌ | Ambos clústeres; depende del rango 10.60.x (consulta al JP) |
| 18 | Borrar y mostrar QEMU | ✅ | — |

**Anexo 1** (6 VMs: anillo VM1–VM2–VM3–VM4 + VM4–VM5–VM6; Internet en VM4 y VM5): la forma se dibuja en el editor ✅;
pide Ubuntu 24.04 minimal y Ubuntu 20.04 con 2,5 GB de disco.

**Pendientes, por prioridad**
1. **Bloqueantes:** monitoreo (D-13); placement R4 con BFD/BCDP alimentado por el monitoreo; imágenes Ubuntu
   (Linux: habilitar en el adaptador el camino cloud-init de EX1 con usuario/contraseña/llave; OpenStack: **sin disco**,
   computes con 1–2 GB libres y Ubuntu pide 2,5–3,5 GB → tratar con el JP `lab5`/`topo1_lab6` o más disco).
   Verificar con la imagen real que 2,5 GB alcanza (Nova solo admite GB enteros y Ubuntu minimal ronda 3,5 GB virtuales).
2. **Necesarios:** zona de disponibilidad y roles Linux (server2–4 alojan VMs, puerta en otro nodo, según decida el grupo);
   elegir servidor por VM (incluye host forzado en Nova); nombres con mayúsculas y `_`; enlaces sin IP en el editor;
   R5 en OpenStack (Internet y SSH desde fuera) y SSH desde fuera en Linux.
3. **Menores:** acceso a los workers de OpenStack para mostrar QEMU.

**Para llevar al JP:** espacio en los computes de OpenStack; ruta y rango 10.60.9.0/24 (y 10.60.10.0/24) para acceso
externo; qué nodo Linux puede hacer de puerta si server2–4 deben alojar VMs; si la zona de disponibilidad es de Linux,
de OpenStack o de ambos.

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
| D-14 | **Asignación de slices a alumnos vía IAM.** Cuando un profesor crea un slice, el slice-manager lo registra en IAM (slice + VMs como recursos) por una ruta interna `PUT /v1/iam/internal/slices/{id}` que solo acepta un token de servicio (no expuesta por el gateway). Asignar/quitar usa las reglas existentes de IAM (`slice.assign`); el alumno asignado ve el slice y abre consolas (`slice.read`, `vm.console`), sin poder borrarlo. Nuevas consultas: alumnos del curso y asignaciones de un recurso. | Reutiliza el modelo académico ya implementado en IAM y separa permisos humanos de la identidad de servicio. | Slices creados por admin no se registran (IAM exige profesor del curso); cuotas aún sin aplicar. |
| D-15 | **Importar imágenes: servicio `image-catalog`** (FastAPI + SQLite, solo metadatos). Solo admin (`image.manage`). La subida viaja en streaming web → gateway → image-catalog → platform-manager → Glance (pública, qcow2/raw, hasta 1 GB), sin tocar el disco del app server; el driver verifica la cabecera qcow2, calcula SHA-256 y borra la imagen si algo falla. Lista para todos: imágenes públicas activas de Glance + metadatos del catálogo; el editor las ofrece. | Cumple "importar imágenes en forma independiente de la plataforma": el catálogo es de G5 y el proveedor materializa. | Linux: la materialización (qcow2 en los nodos) queda para cuando exista su configuración de fase 2; borrar imágenes, pendiente. |
| D-16 | **Direccionamiento interno de los slices: `192.168.k.0/24`** (k = segmento, 1..200; nodo i = `.10+i`), en Linux y OpenStack. `10.60.0.0/16` queda solo para el acceso externo (G5: `10.60.9.0/24` Linux, `10.60.10.0/24` OpenStack). | El documento de cambios reserva `10.60.1–8` para los grupos 1–4: usar `10.60.k` dentro de los slices chocaría con sus rutas al implementar acceso externo (R5, R2-I-09). k ≤ 200 evita las redes de gestión 192.168.201/202. | Confirmar con el grupo; los slices ya creados conservan su direccionamiento. |
| D-10 | **Interfaz web como microservicio `web`** en el mismo compose: React + Vite compilado a estáticos y servido por un contenedor ligero (nginx); lienzo de topologías con React Flow. Solo habla con el gateway. Diseño propio de G5 (G2 es referencia de funcionalidad, no de apariencia). | R1B (12 pts) es la UI: predefinidas, edición, borradores, exportar/importar, capacidad por VM, mis slices, consumo, consola. La demo final debe mostrar el flujo visual ejecutado de verdad sobre el clúster. No toca la lógica probada del núcleo. | Node.js para desarrollo local; el gateway debe exponer las rutas de slices, borradores y consola; TLS en el punto de entrada antes de exponerlo. |
| D-04 | Primera fase de implementación: F0 (auditoría) y luego F1 (núcleo de Slice Manager agnóstico + driver OpenStack mínimo: crear, consultar y eliminar un slice lineal). | Cubre la experiencia del LAB6, R3-I y R1B-I-01, y fija el modelo del que dependen R1B, R4 y R5. | — |

## Restricciones
- No inventar funcionalidades implementadas.
- No declarar pruebas como aprobadas sin evidencia real.
- No modificar infraestructura sin autorización.
- No exponer credenciales ni tokens.
- Mantener trazabilidad entre requerimientos, módulos, pruebas y evidencias.
