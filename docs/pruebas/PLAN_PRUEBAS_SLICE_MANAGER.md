# Plan de pruebas — Módulo 1: Slice Manager (R1C)

**Proyecto:** PUCP Private Cloud Orchestrator — Grupo 5 · TEL141 2026-2
**Entregable:** LAB6, Informe Previo, Actividad 2 (plan de pruebas del módulo «Slice Manager»).
**Versión del código evaluada:** rama `fase2`, commit `70966bc` (driver Linux EX1 + driver OpenStack de fase 2).
**Fecha de corte de resultados:** 2026-11-03.

> Formato de la guía LAB6 (§3.2): casos `X.Y.Z` con 9 campos. `X = 1` es el módulo Slice Manager.
> Resultado: **PASS** (obtenido = esperado), **FAIL** (distinto), **NT** (no realizado; se indica el motivo).
> Solo se marca PASS con salida verificable. Se distingue el entorno de cada resultado:
> **[AUT]** prueba automática con backend simulado (MemoryBackend / OpenStack falso), Windows + stubs;
> **[REAL]** ejecución sobre el clúster OpenStack de la topología de fase 2.

## 0. Alcance y entorno

**Qué es Slice Manager en G5.** No hay un proceso aislado con ese nombre: sus responsabilidades (API de slices,
autenticación y autorización, validación del body, modelado OOP, admisión y reservas, plan ordenado, ejecución
recuperable y estados) están en `g5/api.py`, `g5/model.py`, `g5/store.py`, `g5/engine.py` y en los drivers
`g5/drivers/linux.py` y `g5/drivers/openstack/`. Este plan prueba esas responsabilidades por la API REST
(`/v1/slices`, `/v1/operations`) y directamente sobre sus clases.

| Elemento | Detalle |
|---|---|
| Orquestador | App server (`10.20.11.248`, Ubuntu 20.04, Python 3.8.10), API en `127.0.0.1:8085` |
| Acceso a OpenStack | Túneles SSH app → gateway (servicio `g5-tunnels`): Keystone 55000, Nova 58774, Neutron 59696, Glance 59292, noVNC 56080, Horizon 50080 |
| OpenStack | Victoria: headnode + worker1–3 (4 vCPU, 3,9 GB RAM, 9 GB disco c/u), ML2 VLAN sobre physnet1 |
| Pruebas automáticas | `PYTHONPATH=tools/winshim python -m unittest discover -s tests -v` → 83 pruebas OK (`docs/evidencias/F1/suite_unittest_20261103.txt`) |
| Limitaciones | [AUT] no valida SSH/KVM/OVS reales ni bloqueos `flock` entre procesos. El clúster Linux de fase 2 aún no tiene `cluster.json` propio: los casos Linux reales quedan NT |

## Resumen de resultados

| Sección | Casos | PASS [REAL] | PASS [AUT] | Evidencia por adjuntar | NT |
|---|---:|---:|---:|---:|---:|
| 1.1 Autenticación y autorización | 4 | 0 | 3 | 0 | 1 |
| 1.2 Validación del body | 4 | 0 | 4 | 0 | 0 |
| 1.3 Modelado y orden del plan | 2 | 1 | 1 | 0 | 0 |
| 1.4 Admisión, reservas y concurrencia | 5 | 0 | 5 | 0 | 0 |
| 1.5 Creación de slices | 5 | 1 | 2 | 1 | 1 |
| 1.6 Consulta, seguimiento y acceso | 4 | 3 | 1 | 0 | 0 |
| 1.7 Eliminación | 5 | 1 | 4 | 0 | 0 |
| 1.8 Fallos, reintentos y compensación | 4 | 0 | 4 | 0 | 0 |
| 1.9 Rendimiento | 4 | 2 | 0 | 0 | 2 |
| 1.10 Ciclo de vida (detener/reanudar) | 1 | 0 | 1 | 0 | 0 |
| **Total** | **38** | **8** | **25** | **1** | **4** |

En 1.6.4 se cuenta el resultado [REAL] (OpenStack); su parte Linux es [AUT].

---

## 1.1 Autenticación y autorización

### 1.1.1 RECHAZO DE PETICIONES SIN TOKEN VÁLIDO
| Campo | Contenido |
|---|---|
| Número de caso | 1.1.1 |
| Tipo de prueba | Integración (API HTTP ↔ identidad) |
| Objetivos | Verificar que ninguna operación protegida se ejecuta sin un Bearer token válido y que los tokens no se guardan en claro. |
| Prerrequisitos | API levantada; `keys.json` con hashes SHA-256 de tokens. |
| Procedimiento | 1) `GET /v1/slices` con `Authorization: Bearer bad`. 2) Revisar `keys.json`. |
| Resultados esperados | HTTP 401 sin efectos; `keys.json` solo contiene hashes. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_real_http_auth_create_poll_and_diagnostics`, `test_token_never_stored_in_plaintext` (log de la suite). |
| Comentarios | Trazabilidad: EX1-R1C-D-06. |

### 1.1.2 AISLAMIENTO ENTRE USUARIOS
| Campo | Contenido |
|---|---|
| Número de caso | 1.1.2 |
| Tipo de prueba | Funcional / Seguridad |
| Objetivos | Comprobar que un usuario no ve ni opera slices ajenos (se responde 404 para no revelar su existencia). |
| Prerrequisitos | Un slice creado por `profesor` (admin); token de `alumno` (rol user). |
| Procedimiento | `GET /v1/slices/{id}` con el token del alumno, en un slice Linux y en uno OpenStack. |
| Resultados esperados | HTTP 404 en ambos proveedores. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_user_cannot_read_another_slice`, `test_template_lifecycle_over_http`. |
| Comentarios | EX2-R1B-I-11. |

### 1.1.3 OPERACIONES ADMINISTRATIVAS SOLO PARA ADMIN
| Campo | Contenido |
|---|---|
| Número de caso | 1.1.3 |
| Tipo de prueba | Funcional / Seguridad |
| Objetivos | Verificar que un usuario sin rol admin/service no administra workers ni imágenes. |
| Prerrequisitos | Token de rol `user`. |
| Procedimiento | `PATCH /v1/nodes/server1 {"enabled": false}` con el token de usuario. |
| Resultados esperados | HTTP 403; el worker sigue habilitado. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_user_cannot_administer_nodes`. |
| Comentarios | EX1-R1C-D-06. |

### 1.1.4 ROLES ACADÉMICOS (ALUMNO NO CREA SLICES)
| Campo | Contenido |
|---|---|
| Número de caso | 1.1.4 |
| Tipo de prueba | Funcional / Seguridad |
| Objetivos | Verificar que un alumno no puede crear ni borrar slices (HLD §2.6). |
| Prerrequisitos | Roles admin/profesor/alumno en IAM. |
| Procedimiento | `POST /v1/slices` con token de alumno. |
| Resultados esperados | HTTP 403. |
| Resultado obtenido | **NT** |
| Evidencias | — |
| Comentarios | La implementación actual solo distingue `user` y `admin/service`; los roles académicos y el login se implementan en la fase F2. |

## 1.2 Validación del body de las solicitudes

### 1.2.1 CAMPOS DESCONOCIDOS E INYECCIÓN
| Campo | Contenido |
|---|---|
| Número de caso | 1.2.1 |
| Tipo de prueba | Unitaria |
| Objetivos | Rechazar campos no previstos y nombres con caracteres de shell. |
| Prerrequisitos | Ninguno. |
| Procedimiento | Enviar un slice con `"command": "id"` y una VM llamada `vm;touch /tmp/pwned`. |
| Resultados esperados | HTTP 400 (`Fault`), sin reservas. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_unknown_fields`, `test_injection_names`. |
| Comentarios | R1C: «validar que el body tenga la sintaxis correcta». |

### 1.2.2 DIRECCIONAMIENTO INCONSISTENTE
| Campo | Contenido |
|---|---|
| Número de caso | 1.2.2 |
| Tipo de prueba | Unitaria |
| Objetivos | Rechazar IPs repetidas o fuera de la subred y subredes solapadas o en redes reservadas. |
| Prerrequisitos | Ninguno. |
| Procedimiento | Casos Linux (IP duplicada, red de gestión/tránsito) y OpenStack (IP fuera del /28, subredes solapadas). |
| Resultados esperados | HTTP 400 en todos. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_duplicate_ip_rejected`, `test_management_and_transit_overlap_rejected`, `test_validation_is_provider_specific`. |
| Comentarios | Cada proveedor tiene su validador (Linux /20–/27; OpenStack /16–/29). |

### 1.2.3 RECURSOS DE VM INVÁLIDOS
| Campo | Contenido |
|---|---|
| Número de caso | 1.2.3 |
| Tipo de prueba | Unitaria |
| Objetivos | Rechazar vCPU booleanas, discos no finitos o negativos y credenciales de invitado mal formadas. |
| Prerrequisitos | Ninguno. |
| Procedimiento | `vcpus: true`; `disk_gb` ∈ {NaN, inf, −1, "2.2", 0}; hash de contraseña inválido. |
| Resultados esperados | HTTP 400. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_no_bool_resource`, `test_fractional_disk_exact_sector_size_and_invalid_values`, `test_nic_and_credentials_validation`. |
| Comentarios | EX2-R1B-I-10 (capacidad por VM). |

### 1.2.4 IMAGEN INEXISTENTE SE RECHAZA ANTES DE ADMITIR
| Campo | Contenido |
|---|---|
| Número de caso | 1.2.4 |
| Tipo de prueba | Integración (Slice Manager ↔ catálogo de imágenes / Glance) |
| Objetivos | Verificar que una referencia a imagen inexistente no deja reservas ni recursos parciales. |
| Prerrequisitos | Catálogo Linux y Glance (falso) sin la imagen pedida. |
| Procedimiento | `POST /v1/slices` con imagen inexistente (Linux por SHA-256; OpenStack por nombre). |
| Resultados esperados | Linux 404 / OpenStack 409; tablas `allocations`, `leases` y `slices` sin filas nuevas. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_missing_image_and_no_partial_reservations`, `test_unknown_image_is_rejected_before_admission`. |
| Comentarios | HLD §4.2.5 (referencia de imagen no disponible: rechazo explícito). |

## 1.3 Modelado (OOP) y orden del plan

### 1.3.1 ORDEN CORRECTO DE CREACIÓN EN OPENSTACK
| Campo | Contenido |
|---|---|
| Número de caso | 1.3.1 |
| Tipo de prueba | Integración (Slice Manager ↔ clúster OpenStack) |
| Objetivos | Verificar que el plan crea los elementos en orden de dependencias: proyecto → rol → redes → subredes → puertos → instancias → verificación. |
| Prerrequisitos | Túneles activos; credenciales en `~/.g5/openstack.env`. |
| Procedimiento | Crear `templates/os-lineal.json` y leer `GET /v1/slices/{id}/events`. |
| Resultados esperados | Eventos en ese orden, terminando en `OS_PLACED` y `READY`. |
| Resultado obtenido | **PASS [REAL]** |
| Evidencias | `docs/evidencias/F1/TC-1.3.1_eventos_os-lineal_20261103.json` (eventos con hora UTC y diario de recursos). |
| Comentarios | EX1-R1C-D-01. El modelado está en `ProviderDriver` (contrato) y `LinuxDriver`/`OpenStackDriver`. |

### 1.3.2 TOPOLOGÍAS PREDEFINIDAS CON GRAFO CORRECTO
| Campo | Contenido |
|---|---|
| Número de caso | 1.3.2 |
| Tipo de prueba | Unitaria |
| Objetivos | Verificar enlaces, grados y dominios de broadcast de las plantillas ex1, lineal y anillo. |
| Prerrequisitos | Plantillas en `templates/`. |
| Procedimiento | Validar cada plantilla y contar enlaces y grado por VM. |
| Resultados esperados | ex1: 6 enlaces exactos; lineal: grados [1,2,2,2,2,1]; anillo: grado 2 en todas. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_edges_and_broadcast_domains`, `test_lineal_and_ring_have_correct_degrees`. |
| Comentarios | Malla, árbol y bus se agregan en F2 (EX2-R1B-I-03). |

## 1.4 Admisión, reservas y concurrencia

### 1.4.1 ADMISIÓN ATÓMICA (TODO O NADA)
| Campo | Contenido |
|---|---|
| Número de caso | 1.4.1 |
| Tipo de prueba | Integración (Slice Manager ↔ base de datos) |
| Objetivos | Verificar que si una VM no cabe, no queda reservada ninguna otra del mismo slice. |
| Prerrequisitos | Worker con 2 GB reservables. |
| Procedimiento | Pedir un slice cuya segunda VM requiere 4096 MB. |
| Resultados esperados | HTTP 409 y `allocations` vacía. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_capacity_failure_rolls_back_entire_request`, `test_duplicate_public_port_rejected_atomically`. |
| Comentarios | EX1-R1C-D-03 (sin race condition ni overcommitting). |

### 1.4.2 SOLICITUDES CONCURRENTES POR LA ÚLTIMA CAPACIDAD
| Campo | Contenido |
|---|---|
| Número de caso | 1.4.2 |
| Tipo de prueba | Rendimiento / Concurrencia |
| Objetivos | Verificar que 12 solicitudes simultáneas no reservan más de lo disponible. |
| Prerrequisitos | Capacidad para exactamente 2 slices. |
| Procedimiento | 12 hilos crean el mismo diseño con claves distintas. |
| Resultados esperados | Exactamente 2 aceptadas; uso por worker = capacidad. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_concurrent_admission_cannot_overcommit`. |
| Comentarios | EX1-R1-D-11, EX2-R1B-I-02. Reservas con transacciones `BEGIN IMMEDIATE` de SQLite. |

### 1.4.3 IDEMPOTENCIA DE LA CREACIÓN
| Campo | Contenido |
|---|---|
| Número de caso | 1.4.3 |
| Tipo de prueba | Integración |
| Objetivos | Verificar que repetir una solicitud con la misma `Idempotency-Key` devuelve la misma operación, incluso en paralelo. |
| Prerrequisitos | Ninguno. |
| Procedimiento | Enviar la misma creación 1 y 12 veces en paralelo. |
| Resultados esperados | Un único `operation_id`; reservas de un solo slice. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_duplicate_request_returns_same_operation`, `test_concurrent_same_idempotency_key`. |
| Comentarios | HLD F3 paso 4a. |

### 1.4.4 CLAVE REUTILIZADA CON OTRO CONTENIDO
| Campo | Contenido |
|---|---|
| Número de caso | 1.4.4 |
| Tipo de prueba | Unitaria |
| Objetivos | Rechazar una `Idempotency-Key` usada con un cuerpo distinto. |
| Prerrequisitos | Una creación previa con la clave. |
| Procedimiento | Repetir la clave cambiando el nombre del slice. |
| Resultados esperados | HTTP 409. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_conflicting_idempotency_payload_is_rejected`. |
| Comentarios | — |

### 1.4.5 WORKER EN MANTENIMIENTO NO RECIBE SLICES
| Campo | Contenido |
|---|---|
| Número de caso | 1.4.5 |
| Tipo de prueba | Funcional |
| Objetivos | Verificar que un worker deshabilitado (drain) bloquea nuevas admisiones. |
| Prerrequisitos | Token admin. |
| Procedimiento | `PATCH /v1/nodes/server1 {"enabled": false}` y crear un slice que lo usa. |
| Resultados esperados | HTTP 409. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_drain_worker_blocks_new_requests`, `test_readding_store_cannot_remove_reserved_worker`. |
| Comentarios | EX1-R1-D-03 / EX1-R2-D-04. |

## 1.5 Creación de slices

### 1.5.1 SLICE EX1 (6 VMS) EN EL DRIVER LINUX
| Campo | Contenido |
|---|---|
| Número de caso | 1.5.1 |
| Tipo de prueba | Funcional |
| Objetivos | Verificar el ciclo completo de la topología EX1 en el driver Linux. |
| Prerrequisitos | Imágenes Ubuntu y CirrOS registradas. |
| Procedimiento | Crear `templates/ex1.json` y procesar el trabajo. |
| Resultados esperados | READY con 6 VMs, imágenes distribuidas solo donde se necesitan, CirrOS inicializado. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_full_six_vm_lifecycle_auto_gc`, `test_exact_vm_workers_flavors`. |
| Comentarios | Backend simulado. |

### 1.5.2 SLICE LINUX EN LA TOPOLOGÍA DE FASE 2
| Campo | Contenido |
|---|---|
| Número de caso | 1.5.2 |
| Tipo de prueba | Funcional / Integración |
| Objetivos | Desplegar lineal y anillo en server1–4 de fase 2. |
| Prerrequisitos | `cluster.json` de fase 2 (IPs 192.168.201.1–4, ovs1), agentes instalados, rol de gateway definido. |
| Procedimiento | `g5.cli create` con la plantilla Linux. |
| Resultados esperados | READY; procesos QEMU y puertos OVS verificados. |
| Resultado obtenido | **NT** |
| Evidencias | — |
| Comentarios | Falta adaptar la configuración Linux de fase 1 a fase 2 (inventario ya obtenido). |

### 1.5.3 DESPLIEGUE DE UN SLICE LINEAL EN OPENSTACK
| Campo | Contenido |
|---|---|
| Número de caso | 1.5.3 |
| Tipo de prueba | Funcional / Integración |
| Objetivos | Verificar el despliegue de un slice lineal de 3 VMs en OpenStack mediante el orquestador y sus APIs. |
| Prerrequisitos | Túneles `g5-tunnels` activos; `~/.g5/openstack.env`; imagen `cirros` y flavor `512MBRAM_1VCPUs_4GBRoot`; API G5 en el app server. |
| Procedimiento | 1) `g5.cli create templates/os-lineal.json` con `Idempotency-Key`. 2) `g5.cli wait <operation_id>`. 3) Verificar directamente en Keystone/Neutron/Nova: proyecto, redes, puertos, instancias y host. |
| Resultados esperados | Operación SUCCEEDED; slice READY; 3 instancias ACTIVE en el proyecto `g5-<id>`; 2 redes `vlan`/`physnet1`; IPs fijas pedidas; sin errores. |
| Resultado obtenido | **PASS [REAL]** — 20,3 s; VLAN 103 y 345; vm1 y vm3 en worker2, vm2 en worker1. |
| Evidencias | `docs/evidencias/F1/TC-1.5.3_creacion_os-lineal_20261103.json`. |
| Comentarios | EX2-R3-I-02, R3-I-03, R5-I-01 (VLAN sin túneles), R1B-I-01. |

### 1.5.4 VISUALIZACIÓN DEL SLICE EN HORIZON
| Campo | Contenido |
|---|---|
| Número de caso | 1.5.4 |
| Tipo de prueba | Funcional |
| Objetivos | Verificar que cada slice se ve por separado en Horizon (un proyecto por slice). |
| Prerrequisitos | Caso 1.5.3 activo; túnel 50080. |
| Procedimiento | Iniciar sesión en Horizon (dominio Cloud), seleccionar `g5-<id>`, revisar Instances y Network Topology. |
| Resultados esperados | 3 instancias Active y topología lineal de 2 redes. |
| Resultado obtenido | **Ejecutado — evidencia por adjuntar** |
| Evidencias | Capturas a guardar en `docs/evidencias/F1/` (`TC-1.5.4_*.png`). |
| Comentarios | EX2-R3-I-06, R3-D-05. Se marcará PASS al adjuntar las capturas. |

### 1.5.5 MISMO NÚCLEO PARA LINUX Y OPENSTACK
| Campo | Contenido |
|---|---|
| Número de caso | 1.5.5 |
| Tipo de prueba | Integración (independencia de la infraestructura) |
| Objetivos | Verificar que la misma API, Store y Engine despliegan slices de ambos proveedores. |
| Prerrequisitos | Ninguno. |
| Procedimiento | Crear un slice `provider=linux` y otro `provider=openstack` y procesarlos con el mismo Engine. |
| Resultados esperados | Ambos READY con su `provider` correcto. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_linux_and_openstack_slices_share_the_same_core`. |
| Comentarios | EX2-R1B-I-01, EX1-R1-D-01. |

## 1.6 Consulta, seguimiento y acceso

### 1.6.1 LISTADO DE SLICES CON PROVEEDOR Y ESTADO
| Campo | Contenido |
|---|---|
| Número de caso | 1.6.1 |
| Tipo de prueba | Funcional |
| Objetivos | Listar los slices del usuario con proveedor y estado. |
| Prerrequisitos | Slice OpenStack creado. |
| Procedimiento | `GET /v1/slices`. |
| Resultados esperados | Fila con `provider=openstack` y `status=READY`. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_template_lifecycle_over_http`. |
| Comentarios | EX2-R1B-I-11. |

### 1.6.2 SEGUIMIENTO DE OPERACIÓN ASÍNCRONA
| Campo | Contenido |
|---|---|
| Número de caso | 1.6.2 |
| Tipo de prueba | Funcional |
| Objetivos | Verificar que la creación responde 202 y la operación se consulta hasta su estado final. |
| Prerrequisitos | Caso 1.5.3. |
| Procedimiento | `GET /v1/operations/{id}` hasta SUCCEEDED/FAILED. |
| Resultados esperados | PENDING → SUCCEEDED con 1 intento. |
| Resultado obtenido | **PASS [REAL]** |
| Evidencias | `operacion_g5` en `TC-1.5.3_creacion_os-lineal_20261103.json`. |
| Comentarios | HLD F4. |

### 1.6.3 DIAGNÓSTICO DEL ESTADO REAL
| Campo | Contenido |
|---|---|
| Número de caso | 1.6.3 |
| Tipo de prueba | Integración |
| Objetivos | Contrastar el estado lógico con el real (estado y host de cada instancia en Nova). |
| Prerrequisitos | Caso 1.5.3. |
| Procedimiento | `GET /v1/slices/{id}/diagnostics`. |
| Resultados esperados | `ok: true`, 3 servidores ACTIVE con su host. |
| Resultado obtenido | **PASS [REAL]** |
| Evidencias | `diagnostico_g5` en la evidencia de 1.5.3. |
| Comentarios | EX1-R1C-D-04/05 (monitorear y validar consistencia). |

### 1.6.4 ACCESO A CONSOLA CON CREDENCIAL TEMPORAL
| Campo | Contenido |
|---|---|
| Número de caso | 1.6.4 |
| Tipo de prueba | Funcional / Seguridad |
| Objetivos | Entregar al dueño una URL de consola temporal sin exponer credenciales de infraestructura. |
| Prerrequisitos | Caso 1.5.3; túnel 56080. |
| Procedimiento | `POST /v1/slices/{id}/vms/vm1/console`. Linux: probar expiración y revocación del token. |
| Resultados esperados | OpenStack: URL noVNC de Nova reescrita a `127.0.0.1:56080`. Linux: token vencido o revocado rechazado. |
| Resultado obtenido | **PASS [REAL]** (OpenStack) · **PASS [AUT]** (Linux) |
| Evidencias | `consola_vm1_g5` (token omitido) en la evidencia de 1.5.3; `test_console_token_expiration_revocation_and_slice_state`. |
| Comentarios | EX2-R1B-I-15. |

## 1.7 Eliminación

### 1.7.1 BORRADO LINUX CON LIMPIEZA DE IMÁGENES NO USADAS
| Campo | Contenido |
|---|---|
| Número de caso | 1.7.1 |
| Tipo de prueba | Funcional |
| Objetivos | Eliminar VMs, recursos de red y bases sin referencias. |
| Prerrequisitos | Slice Linux READY. |
| Procedimiento | `DELETE /v1/slices/{id}` y procesar. |
| Resultados esperados | DELETED, sin reservas, sin recursos ni imágenes en los workers. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_full_lifecycle_removes_unused_bases_and_own_resources`, `test_gc_preserves_pinned_image_then_removes_unused`. |
| Comentarios | EX1-R2-I-06/12. |

### 1.7.2 BORRADO DE UN SLICE OPENSTACK SIN HUÉRFANOS
| Campo | Contenido |
|---|---|
| Número de caso | 1.7.2 |
| Tipo de prueba | Funcional / Integración |
| Objetivos | Eliminar en orden inverso servidores, puertos, subredes, redes y proyecto, sin tocar recursos ajenos. |
| Prerrequisitos | Slice del caso 1.5.3 en READY. |
| Procedimiento | 1) `g5.cli delete <slice_id>` con `Idempotency-Key`. 2) `g5.cli wait`. 3) Listar en Keystone/Nova/Neutron proyectos, servidores, redes, subredes y puertos `g5-*`; revisar hypervisors. |
| Resultados esperados | SUCCEEDED; slice DELETED; ningún recurso `g5-*`; `lab5`, `cloud_admin` y `external` intactos. |
| Resultado obtenido | **PASS [REAL]** — 18,1 s; 12 recursos DELETED en el diario; OpenStack igual que antes de la prueba. |
| Evidencias | `docs/evidencias/F1/TC-1.7.2_borrado_os-lineal_20261103.json`. |
| Comentarios | EX2-R3-I-05, R1B-I-13. |

### 1.7.3 BORRADO CON OTRA OPERACIÓN EN CURSO
| Campo | Contenido |
|---|---|
| Número de caso | 1.7.3 |
| Tipo de prueba | Unitaria / Concurrencia |
| Objetivos | Impedir operaciones incompatibles sobre el mismo slice. |
| Prerrequisitos | Slice READY con un borrado pendiente. |
| Procedimiento | Solicitar `reconcile` mientras el borrado está pendiente. |
| Resultados esperados | HTTP 409. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_simultaneous_delete_and_reconcile_are_exclusive`. |
| Comentarios | EX1-R1-D-10. |

### 1.7.4 BORRAR UN SLICE NO AFECTA A OTRO
| Campo | Contenido |
|---|---|
| Número de caso | 1.7.4 |
| Tipo de prueba | Funcional |
| Objetivos | Verificar que el borrado solo toca recursos propios. |
| Prerrequisitos | Dos slices READY. |
| Procedimiento | Borrar el primero. |
| Resultados esperados | El segundo sigue READY con sus reservas. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_delete_one_slice_preserves_other`. |
| Comentarios | En OpenStack, además, cada slice es un proyecto distinto (verificado en 1.7.2). |

### 1.7.5 BORRADO CON DIARIO INCOMPLETO
| Campo | Contenido |
|---|---|
| Número de caso | 1.7.5 |
| Tipo de prueba | Integración / Recuperación |
| Objetivos | Verificar que el borrado encuentra por nombre recursos creados cuyo UUID no llegó a registrarse (corte a mitad de operación). |
| Prerrequisitos | Slice OpenStack READY; diario de redes y puertos sin UUID. |
| Procedimiento | Vaciar `external_id` en el diario y borrar. |
| Resultados esperados | DELETED sin recursos restantes. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_cleanup_finds_resources_missing_from_journal`. |
| Comentarios | HLD §4.3.5. |

## 1.8 Fallos, reintentos y compensación

### 1.8.1 FALLO TEMPORAL SE REINTENTA
| Campo | Contenido |
|---|---|
| Número de caso | 1.8.1 |
| Tipo de prueba | Integración |
| Objetivos | Superar fallos transitorios con reintentos acotados (agentes Linux; GET 5xx en OpenStack). |
| Prerrequisitos | Fallos inyectados. |
| Procedimiento | Un fallo en `network` del agente; un 503 en GET de Nova. |
| Resultados esperados | READY / respuesta correcta y evento RETRY; un POST no se repite automáticamente. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_temporary_failure_retries_successfully`, `test_retries_guest_setup_transient_failure`, `test_get_retries_5xx_but_post_does_not`. |
| Comentarios | EX1-R2-I-04, EX2-R3-D-02. |

### 1.8.2 FALLO PERMANENTE SE COMPENSA SIN RESIDUOS
| Campo | Contenido |
|---|---|
| Número de caso | 1.8.2 |
| Tipo de prueba | Integración |
| Objetivos | Si una VM no se puede crear, retirar todo lo creado y liberar reservas. |
| Prerrequisitos | Fallo permanente inyectado (agente) o instancia en ERROR (Nova). |
| Procedimiento | Crear el slice con el fallo inyectado. |
| Resultados esperados | `FAILED_CLEANED`, sin recursos ni reservas; el error muestra la causa. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_permanent_create_failure_compensates`, `test_nova_error_is_compensated`, `test_missing_flavor_without_permission_fails_cleanly`. |
| Comentarios | HLD F3 pasos 31c–31d. |

### 1.8.3 LIMPIEZA INCIERTA CONSERVA RESERVAS
| Campo | Contenido |
|---|---|
| Número de caso | 1.8.3 |
| Tipo de prueba | Integración |
| Objetivos | No liberar capacidad si no se confirma la limpieza. |
| Prerrequisitos | Falla la creación y también el borrado. |
| Procedimiento | Inyectar ambos fallos, luego quitarlos y reintentar el borrado. |
| Resultados esperados | `ERROR_CLEANUP` con reservas; tras el reintento, reservas liberadas. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_unknown_cleanup_holds_reservations_until_retry`, `test_reconcile_failure_does_not_destroy_existing_disks`. |
| Comentarios | EX1-R1C-D-05. |

### 1.8.4 REINICIO O RESPUESTA PERDIDA SIN DUPLICADOS
| Campo | Contenido |
|---|---|
| Número de caso | 1.8.4 |
| Tipo de prueba | Integración / Recuperación |
| Objetivos | Verificar que repetir un despliegue (reinicio del ejecutor, respuesta perdida) no duplica VMs ni recursos. |
| Prerrequisitos | Ninguno. |
| Procedimiento | Repetir el despliegue tras un reinicio simulado; perder la respuesta de `vm_ensure`; volver a desplegar un slice OpenStack ya creado. |
| Resultados esperados | Mismo número de VMs y recursos que con una sola ejecución. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_restart_replays_running_job_without_duplicate_vms`, `test_lost_response_after_vm_creation_is_idempotent`, `test_replayed_deploy_does_not_duplicate_resources`. |
| Comentarios | El driver OpenStack anota cada recurso antes del POST y lo busca por nombre. |

## 1.9 Rendimiento

### 1.9.1 TIEMPO DE CREACIÓN DE UN SLICE DE 3 VMS
| Campo | Contenido |
|---|---|
| Número de caso | 1.9.1 |
| Tipo de prueba | Rendimiento |
| Objetivos | Medir el tiempo desde la aceptación hasta READY. |
| Prerrequisitos | Caso 1.5.3. |
| Procedimiento | `updated − created` de la operación. |
| Resultados esperados | ≤ 120 s (meta del grupo para 3 VMs CirrOS). |
| Resultado obtenido | **PASS [REAL]** — 20,3 s (VMs creadas en paralelo, límite 3). |
| Evidencias | `operacion_g5` en la evidencia de 1.5.3. |
| Comentarios | EX2-R3-I-04, EX1-R1C-D-02. |

### 1.9.2 TIEMPO DE BORRADO
| Campo | Contenido |
|---|---|
| Número de caso | 1.9.2 |
| Tipo de prueba | Rendimiento |
| Objetivos | Medir el borrado completo con verificación. |
| Prerrequisitos | Caso 1.7.2. |
| Procedimiento | `updated − created` de la operación de borrado. |
| Resultados esperados | ≤ 120 s. |
| Resultado obtenido | **PASS [REAL]** — 18,1 s. |
| Evidencias | `operacion_g5` en la evidencia de 1.7.2. |
| Comentarios | — |

### 1.9.3 SLICES CONCURRENTES EN EL CLÚSTER REAL
| Campo | Contenido |
|---|---|
| Número de caso | 1.9.3 |
| Tipo de prueba | Rendimiento / Concurrencia |
| Objetivos | Crear 2 slices en paralelo y medir tiempos y aislamiento. |
| Prerrequisitos | Disco suficiente en los workers (9 GB c/u). |
| Procedimiento | Dos `create` simultáneos con plantillas pequeñas. |
| Resultados esperados | Ambos READY, sin interferencias; tiempos registrados. |
| Resultado obtenido | **NT** |
| Evidencias | — |
| Comentarios | Con el flavor de 4 GB solo caben ~4 VMs nuevas en el clúster. Requiere un flavor de 1 GB (autorización pendiente). |

### 1.9.4 PARALELO VS SECUENCIAL EN OPENSTACK
| Campo | Contenido |
|---|---|
| Número de caso | 1.9.4 |
| Tipo de prueba | Rendimiento |
| Objetivos | Comparar `parallel_servers=3` con `parallel_servers=1`. |
| Prerrequisitos | Igual que 1.9.3. |
| Procedimiento | Repetir 1.5.3 con ambas configuraciones. |
| Resultados esperados | Menor tiempo en paralelo. |
| Resultado obtenido | **NT** |
| Evidencias | — |
| Comentarios | Programado tras resolver la capacidad de disco. |

## 1.10 Ciclo de vida

### 1.10.1 DETENER Y REANUDAR SIN PERDER RECURSOS
| Campo | Contenido |
|---|---|
| Número de caso | 1.10.1 |
| Tipo de prueba | Funcional |
| Objetivos | Detener un slice (Linux: QMP; OpenStack: `os-stop`) y reanudarlo con los mismos discos, redes y reservas. |
| Prerrequisitos | Slice READY. |
| Procedimiento | `POST .../stop` y luego `POST .../start`. |
| Resultados esperados | STOPPED → READY; mismos recursos. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_stop_start_keeps_disks_networks_and_reservations`, `test_stop_and_start_keep_resources`. |
| Comentarios | HLD F8. |

---

## Trazabilidad con EX1/EX2

| Criterio | Casos |
|---|---|
| EX1-R1C-D-01 Flujo completo y en orden | 1.3.1, 1.5.1, 1.5.3 |
| EX1-R1C-D-02 Paralelismo | 1.9.1, 1.9.4 |
| EX1-R1C-D-03 Sin race condition / overcommitting | 1.4.1, 1.4.2 |
| EX1-R1C-D-04/05 Monitoreo y consistencia | 1.6.3, 1.8.3 |
| EX1-R1C-D-06 Autenticación y autorización | 1.1.1–1.1.4 |
| EX2-R1B-I-01 Independencia de la infraestructura | 1.5.5, 1.5.3 |
| EX2-R1B-I-02 Concurrencia de usuarios | 1.4.2, 1.9.3 |
| EX2-R1B-I-11/13/15 Listar, borrar, consola | 1.6.1, 1.7.1–1.7.2, 1.6.4 |
| EX2-R3-I-02/03/04/05/06 OpenStack | 1.5.3, 1.9.1, 1.7.2, 1.5.4 |
| EX2-R5-I-01 VLAN sin túneles | 1.5.3 |

## Cómo reproducir

```bash
# Pruebas automáticas (Windows: con stubs; Linux: sin PYTHONPATH)
PYTHONPATH=tools/winshim python -m unittest discover -s tests -v

# Casos [REAL] en el app server (~/g5-orchestrator, túneles activos)
python3 -m g5.api --config config/cluster.json --state state-f1 &
python3 -m g5.cli --token-file config/admin.token create templates/os-lineal.json
python3 -m g5.cli --token-file config/admin.token wait <operation_id>
python3 -m g5.cli --token-file config/admin.token diagnostics <slice_id>
python3 -m g5.cli --token-file config/admin.token delete <slice_id>
```
