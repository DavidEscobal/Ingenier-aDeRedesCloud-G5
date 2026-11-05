# Plan de pruebas — Módulo 1: Slice Manager (R1C)

**Proyecto:** PUCP Private Cloud Orchestrator — Grupo 5 · TEL141 2026-2
**Entregable:** LAB6 (guía `GUIA_LAB6_TEL141_2026-2`), Informe Previo, Actividad 2: plan de pruebas del módulo «Slice Manager» considerando los requerimientos de EX1 y EX2. Entrega: jueves 5 de noviembre de 2026.
**Versión del código evaluada:** rama `fase2`, commit `70966bc` (driver Linux EX1 + driver OpenStack de fase 2).
**Fecha de corte de resultados:** 2026-11-05.

> Formato de la guía LAB6 (§3.2): casos `X.Y.Z` con 9 campos. `X = 1` es el módulo Slice Manager.
> Tipos de prueba de la guía (§3.1): Unitaria, Integración, Funcional y Rendimiento.
> Resultado: **PASS** (obtenido = esperado), **FAIL** (distinto), **NT** (no realizado: cambiaron los requerimientos o no se cumplieron los requisitos; se indica el motivo).
> Solo se marca PASS con salida verificable. Se distingue el entorno de cada resultado:
> **[AUT]** prueba automática con backend simulado (MemoryBackend / OpenStack falso), Windows + stubs;
> **[REAL]** ejecución sobre el clúster OpenStack de la topología de fase 2.
> Un caso con ambas ejecuciones se cuenta como [REAL] en el resumen.

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

### 0.1 Estado de implementación de Slice Manager (corte 2026-11-03)

El plan cubre **todas** las funciones que el HLD (§4.3) y las rúbricas EX1/EX2 asignan a Slice Manager.
Las que todavía no están implementadas se incluyen con su resultado esperado y quedan **NT** («no se
cumplieron los requisitos» de la guía): se ejecutarán cuando la fase correspondiente esté lista.

| Función de Slice Manager | Estado | Fase |
|---|---|---|
| API REST, autenticación por token, validación del body | Implementado (EX1) | — |
| Modelado OOP del slice y contrato de driver (Linux / OpenStack) | Implementado | F1 |
| Admisión atómica, reservas, idempotencia | Implementado (EX1) | — |
| Ejecución asíncrona con reintentos, compensación y estados | Implementado (EX1 + OpenStack) | F1 |
| Despliegue y borrado en OpenStack | Implementado y probado en el clúster | F1 |
| Roles académicos (admin/profesor/alumno), login y cuotas | Pendiente | F2 |
| Topology Manager: 5 topologías, combinación, borradores, importar/exportar | Pendiente (hay ex1/lineal/anillo fijas) | F2 |
| Edición de un slice desplegado con control de versión | Pendiente | F2 |
| Selección de destinos con VM Placement y zona de disponibilidad | Pendiente (worker manual en Linux; Nova elige en OpenStack) | F3 |
| Vista de consumo de recursos del sistema | Parcial (`/v1/nodes` en Linux) | F3 |
| Plan de red y seguridad (salida a Internet, security groups, acceso externo) | Pendiente en OpenStack; existe en Linux EX1 | F4 |

## Resumen de resultados

| Sección | Casos | PASS [REAL] | PASS [AUT] | NT |
|---|---:|---:|---:|---:|
| 1.1 Autenticación y autorización | 5 | 1 | 2 | 2 |
| 1.2 Validación del body | 5 | 1 | 3 | 1 |
| 1.3 Modelado, topologías y borradores | 5 | 1 | 1 | 3 |
| 1.4 Admisión, reservas, concurrencia y placement | 8 | 0 | 5 | 3 |
| 1.5 Creación de slices | 5 | 2 | 2 | 1 |
| 1.6 Consulta, seguimiento y acceso | 5 | 3 | 1 | 1 |
| 1.7 Eliminación | 5 | 1 | 4 | 0 |
| 1.8 Fallos, reintentos y compensación | 4 | 1 | 3 | 0 |
| 1.9 Rendimiento | 4 | 2 | 0 | 2 |
| 1.10 Ciclo de vida (detener/reanudar) | 1 | 0 | 1 | 0 |
| 1.11 Edición de slices desplegados | 2 | 0 | 0 | 2 |
| 1.12 Red y seguridad del slice | 2 | 0 | 0 | 2 |
| **Total** | **51** | **12** | **22** | **17** |

En 1.6.4 se cuenta el resultado [REAL] (OpenStack); su parte Linux es [AUT].

---

## 1.1 Autenticación y autorización

### 1.1.1 RECHAZO DE PETICIONES SIN TOKEN VÁLIDO
| Campo | Contenido |
|---|---|
| Número de caso | 1.1.1 |
| Tipo de prueba | Integración (API ↔ identidad) |
| Objetivos | Verificar que ninguna operación protegida se ejecuta sin un Bearer token válido y que los tokens no se guardan en claro. |
| Prerrequisitos | API levantada; `keys.json` con hashes SHA-256 de tokens. |
| Procedimiento | 1) Levantar la API G5 con keys.json, que guarda solo el hash SHA-256 de cada token. 2) Enviar GET /v1/slices con la cabecera Authorization: Bearer bad. 3) Abrir keys.json y revisar su contenido. |
| Resultados esperados | La API responde HTTP 401 «Token inválido»; No se ejecuta ninguna operación ni se crea ningún recurso; keys.json no contiene ningún token en claro, solo hashes. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_real_http_auth_create_poll_and_diagnostics`, `test_token_never_stored_in_plaintext` (log de la suite). |
| Comentarios | Trazabilidad: EX1-R1C-D-06. |

### 1.1.2 AISLAMIENTO ENTRE USUARIOS
| Campo | Contenido |
|---|---|
| Número de caso | 1.1.2 |
| Tipo de prueba | Funcional (seguridad) |
| Objetivos | Comprobar que un usuario no ve ni opera slices ajenos (se responde 404 para no revelar su existencia). |
| Prerrequisitos | Un slice creado por `profesor` (admin); token de `alumno` (rol user). |
| Procedimiento | 1) Con el token del administrador (profesor), consultar GET /v1/slices/{id} de un slice existente. 2) Con el token del alumno, consultar el mismo slice. 3) Con el token del alumno, listar GET /v1/slices. 4) Con el token del alumno, intentar DELETE /v1/slices/{id}. 5) Repetir una consulta con un token inválido. |
| Resultados esperados | El administrador recibe HTTP 200 con los datos del slice; El alumno recibe HTTP 404 «Slice inexistente» al consultar y al borrar, sin revelar que el slice existe; El listado del alumno no incluye slices ajenos; El token inválido recibe HTTP 401; El slice no cambia de estado. |
| Resultado obtenido | **PASS [REAL]** — API G5 en el app server (2026-11-05): el alumno recibe 404 al consultar y al borrar el slice del profesor y ve 0 slices; el admin recibe 200; un token inválido recibe 401. También **PASS [AUT]**. |
| Evidencias | `docs/evidencias/F1/TC-1.1.2_aislamiento_real_20261105.json`; `test_user_cannot_read_another_slice`, `test_template_lifecycle_over_http`. |
| Comentarios | EX2-R1B-I-11. |

### 1.1.3 OPERACIONES ADMINISTRATIVAS SOLO PARA ADMIN
| Campo | Contenido |
|---|---|
| Número de caso | 1.1.3 |
| Tipo de prueba | Funcional (seguridad) |
| Objetivos | Verificar que un usuario sin rol admin/service no administra workers ni imágenes. |
| Prerrequisitos | Token de rol `user`. |
| Procedimiento | 1) Con un token de rol user, enviar PATCH /v1/nodes/server1 con {"enabled": false}. 2) Consultar el estado del worker con un token de administrador. |
| Resultados esperados | La API responde HTTP 403 «Requiere rol admin/service»; server1 sigue habilitado para recibir VMs. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_user_cannot_administer_nodes`. |
| Comentarios | EX1-R1C-D-06. |

### 1.1.4 ROLES ACADÉMICOS (ALUMNO NO CREA SLICES)
| Campo | Contenido |
|---|---|
| Número de caso | 1.1.4 |
| Tipo de prueba | Funcional (seguridad) |
| Objetivos | Verificar que un alumno no puede crear ni borrar slices (HLD §2.6). |
| Prerrequisitos | Roles admin/profesor/alumno en IAM. |
| Procedimiento | 1) Iniciar sesión con una cuenta de alumno. 2) Enviar POST /v1/slices con una plantilla válida. 3) Listar los slices del curso con una cuenta de profesor. |
| Resultados esperados | La API responde HTTP 403; No se crea ningún slice ni reserva; La decisión queda registrada para auditoría. |
| Resultado obtenido | **NT** |
| Evidencias | — |
| Comentarios | La implementación actual solo distingue `user` y `admin/service`; los roles académicos y el login se implementan en la fase F2. |

### 1.1.5 CUOTAS POR CURSO
| Campo | Contenido |
|---|---|
| Número de caso | 1.1.5 |
| Tipo de prueba | Funcional (seguridad) |
| Objetivos | Impedir que un profesor supere la cuota de vCPU, RAM o VMs asignada a su curso. |
| Prerrequisitos | IAM con cursos y cuotas (F2). |
| Procedimiento | 1) Como administrador, asignar al curso una cuota de 4 vCPU. 2) Como profesor del curso, crear un slice de 2 vCPU. 3) Crear un segundo slice de 2 vCPU. 4) Crear un tercer slice de 1 vCPU. |
| Resultados esperados | Los dos primeros slices se aceptan con HTTP 202; El tercero se rechaza con HTTP 409 y el motivo «cuota del curso excedida»; No quedan reservas del slice rechazado. |
| Resultado obtenido | **NT** — función pendiente de implementación. |
| Evidencias | — |
| Comentarios | HLD §3.3 (capa 2). La cuota no sustituye la verificación de capacidad real. |

## 1.2 Validación del body de las solicitudes

### 1.2.1 CAMPOS DESCONOCIDOS E INYECCIÓN
| Campo | Contenido |
|---|---|
| Número de caso | 1.2.1 |
| Tipo de prueba | Unitaria |
| Objetivos | Rechazar campos no previstos y nombres con caracteres de shell. |
| Prerrequisitos | Ninguno. |
| Procedimiento | 1) Preparar una solicitud de slice válida. 2) Agregarle el campo desconocido "command": "id" y enviarla. 3) Cambiar el nombre de una VM a "vm;touch /tmp/pwned" y enviarla. |
| Resultados esperados | Ambas solicitudes se rechazan con HTTP 400 indicando el campo o el identificador inválido; No se reserva capacidad; No se ejecuta ningún comando en los nodos. |
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
| Procedimiento | 1) Linux: repetir la IP de una NIC en otra VM del mismo segmento. 2) Linux: usar como subred la red de gestión 10.0.10.0/24 o el pool de tránsito 172.30.0.0/16. 3) OpenStack: asignar a una VM la IP 192.168.12.15, fuera del /28 192.168.12.0/28. 4) OpenStack: declarar dos subredes que se solapan. |
| Resultados esperados | Cada solicitud se rechaza con HTTP 400 y un mensaje específico (IP repetida, subred superpuesta o IP fuera de la subred); No se crea ninguna reserva. |
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
| Procedimiento | 1) Enviar una VM con "vcpus": true. 2) Enviar disk_gb con los valores NaN, infinito, -1, "2.2" (texto) y 0. 3) Enviar una VM Ubuntu con un hash de contraseña inválido o una clave SSH con salto de línea. 4) Enviar disk_gb = 2.2 (válido). |
| Resultados esperados | Los valores inválidos se rechazan con HTTP 400; disk_gb = 2.2 se acepta y se convierte exactamente a 2 362 232 320 bytes. |
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
| Procedimiento | 1) Registrar la cantidad de slices existentes. 2) Enviar POST /v1/slices con provider openstack y la imagen "imagen-inexistente-g5". 3) Volver a listar los slices. 4) Driver Linux: enviar una VM con una imagen SHA-256 no registrada en el catálogo. |
| Resultados esperados | OpenStack: HTTP 409 «Imagen Glance inexistente o ambigua» antes de admitir la solicitud; Linux: HTTP 404 «Imagen no registrada»; La cantidad de slices y las tablas de reservas no cambian; No se crea ningún recurso en OpenStack. |
| Resultado obtenido | **PASS [REAL]** — con Glance real: imagen `imagen-inexistente-g5` rechazada con HTTP 409 antes de admitir; slices antes = después = 1; nada creado en OpenStack. También **PASS [AUT]** (Linux). |
| Evidencias | `docs/evidencias/F1/TC-1.2.4_imagen_inexistente_real_20261105.json`; `test_missing_image_and_no_partial_reservations`, `test_unknown_image_is_rejected_before_admission`. |
| Comentarios | HLD §4.2.5 (referencia de imagen no disponible: rechazo explícito). |

### 1.2.5 IMPORTACIÓN DE UNA TOPOLOGÍA CON ESQUEMA INVÁLIDO
| Campo | Contenido |
|---|---|
| Número de caso | 1.2.5 |
| Tipo de prueba | Unitaria |
| Objetivos | Rechazar plantillas JSON importadas con versión de esquema desconocida, nodos repetidos o enlaces a nodos inexistentes. |
| Prerrequisitos | Topology Manager con importación (F2). |
| Procedimiento | 1) Exportar una plantilla válida. 2) Cambiar su schema_version a una versión inexistente e importarla. 3) Duplicar un nodo e importarla. 4) Agregar un enlace hacia un nodo ausente e importarla. |
| Resultados esperados | Cada importación se rechaza con HTTP 400 y el error correspondiente; No se guarda la plantilla; No se crea ningún slice. |
| Resultado obtenido | **NT** — función pendiente de implementación. |
| Evidencias | — |
| Comentarios | EX2-R1B-I-08; HLD §4.2.5. |

## 1.3 Modelado (OOP), topologías y borradores

### 1.3.1 ORDEN CORRECTO DE CREACIÓN EN OPENSTACK
| Campo | Contenido |
|---|---|
| Número de caso | 1.3.1 |
| Tipo de prueba | Integración (Slice Manager ↔ clúster OpenStack) |
| Objetivos | Verificar que el plan crea los elementos en orden de dependencias: proyecto → rol → redes → subredes → puertos → instancias → verificación. |
| Prerrequisitos | Túneles activos; credenciales en `~/.g5/openstack.env`. |
| Procedimiento | 1) Verificar que los túneles hacia OpenStack estén activos. 2) Enviar POST /v1/slices con templates/os-lineal.json. 3) Esperar a que la operación termine en SUCCEEDED. 4) Consultar GET /v1/slices/{id}/events. 5) Comparar con los recursos listados en Keystone, Neutron y Nova. |
| Resultados esperados | Los eventos siguen el orden proyecto, rol, redes, subredes, puertos, instancias, ubicación (OS_PLACED) y READY; Ninguna instancia se crea antes que sus puertos; Los recursos de OpenStack coinciden con los eventos. |
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
| Procedimiento | 1) Cargar las plantillas ex1, lineal y anillo. 2) Validar cada una con el validador del driver Linux. 3) Contar los enlaces de cada red y el grado de cada VM. |
| Resultados esperados | ex1: exactamente 6 enlaces (VM1–VM2, VM2–VM3, VM1–VM4, VM3–VM4, VM4–VM5, VM5–VM6); Lineal: grados [1, 2, 2, 2, 2, 1]; Anillo: grado 2 en todas las VMs; Cada red tiene una C-VLAN distinta. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_edges_and_broadcast_domains`, `test_lineal_and_ring_have_correct_degrees`. |
| Comentarios | Malla, árbol y bus se agregan en F2 (EX2-R1B-I-03). |

### 1.3.3 TOPOLOGÍAS MALLA, ÁRBOL Y BUS
| Campo | Contenido |
|---|---|
| Número de caso | 1.3.3 |
| Tipo de prueba | Unitaria |
| Objetivos | Generar las topologías predefinidas restantes con el grafo correcto para N nodos. |
| Prerrequisitos | Generadores de topologías (F2). |
| Procedimiento | 1) Generar una malla de 4 nodos. 2) Generar un árbol de 4 nodos. 3) Generar un bus de 4 nodos. 4) Validar las tres topologías. |
| Resultados esperados | Malla: 6 enlaces (todos con todos); Árbol: 3 enlaces y ningún ciclo; Bus: un único segmento compartido por las 4 VMs; Las tres son válidas para Linux y OpenStack. |
| Resultado obtenido | **NT** — función pendiente de implementación. |
| Evidencias | — |
| Comentarios | EX2-R1B-I-03. |

### 1.3.4 COMBINAR TOPOLOGÍAS Y AGREGAR NODOS Y ENLACES A UN BORRADOR
| Campo | Contenido |
|---|---|
| Número de caso | 1.3.4 |
| Tipo de prueba | Funcional |
| Objetivos | Editar un slice aún no desplegado combinando dos topologías y agregando nodos y enlaces. |
| Prerrequisitos | Borradores y editor (F2). |
| Procedimiento | 1) Crear un borrador lineal de 3 nodos. 2) Agregarle un anillo de 3 nodos. 3) Unir ambas topologías con un enlace. 4) Agregar un nodo y un enlace adicionales. 5) Validar el borrador sin desplegarlo. |
| Resultados esperados | El borrador tiene 7 nodos y los enlaces esperados; La validación es correcta; No se crea ningún recurso en la infraestructura. |
| Resultado obtenido | **NT** — función pendiente de implementación. |
| Evidencias | — |
| Comentarios | EX2-R1B-I-04/05; EX1-R1B-D-04. |

### 1.3.5 GUARDAR UN BORRADOR Y RETOMAR LA EDICIÓN
| Campo | Contenido |
|---|---|
| Número de caso | 1.3.5 |
| Tipo de prueba | Funcional |
| Objetivos | Verificar que un borrador persiste y se recupera para seguir editándolo. |
| Prerrequisitos | Borradores persistentes (F2). |
| Procedimiento | 1) Guardar un borrador. 2) Reiniciar la API. 3) Recuperar el borrador. 4) Editarlo. 5) Desplegarlo como slice. |
| Resultados esperados | El borrador recuperado es idéntico al guardado; Al editarlo aumenta su versión; El slice desplegado corresponde a la versión editada. |
| Resultado obtenido | **NT** — función pendiente de implementación. |
| Evidencias | — |
| Comentarios | EX2-R1B-I-06/09; EX1-R1-D-09. |

## 1.4 Admisión, reservas, concurrencia y placement

### 1.4.1 ADMISIÓN ATÓMICA (TODO O NADA)
| Campo | Contenido |
|---|---|
| Número de caso | 1.4.1 |
| Tipo de prueba | Integración (Slice Manager ↔ base de datos) |
| Objetivos | Verificar que si una VM no cabe, no queda reservada ninguna otra del mismo slice. |
| Prerrequisitos | Worker con 2 GB reservables. |
| Procedimiento | 1) Configurar un worker con 2048 MB de RAM reservable. 2) Pedir un slice cuya segunda VM requiere 4096 MB. 3) Revisar la tabla de reservas (allocations). 4) Repetir con un puerto externo que ya está reservado por otro slice. |
| Resultados esperados | Respuesta HTTP 409 «Capacidad reservable insuficiente en server…»; No queda ninguna reserva del slice, ni siquiera la de la primera VM; Con el puerto ocupado: HTTP 409 y tampoco quedan reservas parciales. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_capacity_failure_rolls_back_entire_request`, `test_duplicate_public_port_rejected_atomically`. |
| Comentarios | EX1-R1C-D-03 (sin race condition ni overcommitting). |

### 1.4.2 SOLICITUDES CONCURRENTES POR LA ÚLTIMA CAPACIDAD
| Campo | Contenido |
|---|---|
| Número de caso | 1.4.2 |
| Tipo de prueba | Rendimiento (concurrencia) |
| Objetivos | Verificar que 12 solicitudes simultáneas no reservan más de lo disponible. |
| Prerrequisitos | Capacidad para exactamente 2 slices. |
| Procedimiento | 1) Configurar capacidad para exactamente 2 slices del mismo diseño. 2) Lanzar 12 solicitudes simultáneas (12 hilos) con claves de idempotencia distintas. 3) Contar las solicitudes aceptadas. 4) Sumar las vCPU reservadas en cada worker. |
| Resultados esperados | Exactamente 2 solicitudes se aceptan y las otras 10 se rechazan con HTTP 409; Las vCPU reservadas por worker son iguales a su capacidad y nunca la superan. |
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
| Procedimiento | 1) Enviar una creación con la Idempotency-Key K. 2) Reenviar la misma solicitud con K. 3) Enviar 12 copias simultáneas con K. |
| Resultados esperados | Todas las respuestas devuelven el mismo operation_id; Existe un solo slice y un solo juego de reservas. |
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
| Procedimiento | 1) Crear un slice con la Idempotency-Key K. 2) Reenviar con K pero cambiando el nombre del slice. |
| Resultados esperados | Respuesta HTTP 409 «Idempotency-Key reutilizada con otra petición»; El primer slice no se modifica. |
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
| Procedimiento | 1) Como administrador, enviar PATCH /v1/nodes/server1 con {"enabled": false}. 2) Crear un slice que usa server1. 3) Reabrir el Store con una configuración sin server1 mientras tiene reservas. |
| Resultados esperados | La creación se rechaza con HTTP 409 «Worker en mantenimiento»; El Store se niega a retirar el worker: HTTP 409 «No retire workers con reservas». |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_drain_worker_blocks_new_requests`, `test_readding_store_cannot_remove_reserved_worker`. |
| Comentarios | EX1-R1-D-03 / EX1-R2-D-04. |

### 1.4.6 ASIGNACIÓN AUTOMÁTICA DE HOSTS POR VM PLACEMENT EN LA ZONA PEDIDA
| Campo | Contenido |
|---|---|
| Número de caso | 1.4.6 |
| Tipo de prueba | Integración (Slice Manager ↔ VM Placement) |
| Objetivos | Verificar que Slice Manager obtiene un destino por VM sin que el usuario indique el worker, dentro de la zona solicitada, y que el host real coincide. |
| Prerrequisitos | VM Placement (F3); zonas definidas; fijación de host en Nova (microversión ≥ 2.74). |
| Procedimiento | 1) Definir una zona de disponibilidad Z con sus hosts. 2) Crear un slice sin indicar worker y pidiendo la zona Z. 3) Leer el plan de VM Placement. 4) Verificar el host real de cada VM en Nova o en el agente. |
| Resultados esperados | Todas las VMs quedan en hosts de la zona Z; El host real coincide con el planificado; Las reservas se confirman una sola vez. |
| Resultado obtenido | **NT** — función pendiente de implementación. |
| Evidencias | — |
| Comentarios | EX2-R4-I-02/04. |

### 1.4.7 RECHAZO EXPLICADO POR FALTA DE CAPACIDAD
| Campo | Contenido |
|---|---|
| Número de caso | 1.4.7 |
| Tipo de prueba | Funcional |
| Objetivos | Rechazar un slice que no cabe completo, indicando la razón, sin reservas residuales. |
| Prerrequisitos | VM Placement (F3). |
| Procedimiento | 1) Pedir un slice cuya demanda total supera la capacidad de la zona. 2) Revisar la respuesta y los registros. 3) Revisar las reservas y OpenStack. |
| Resultados esperados | Respuesta HTTP 409 con el motivo por recurso (CPU, RAM o disco) y por host descartado; No queda ninguna reserva; No se crea ningún recurso. |
| Resultado obtenido | **NT** — función pendiente de implementación. |
| Evidencias | — |
| Comentarios | EX2-R4-I-03. Hoy existe el rechazo por capacidad por worker en Linux (caso 1.4.1). |

### 1.4.8 LÍMITE DE TIEMPO DE PLANIFICACIÓN
| Campo | Contenido |
|---|---|
| Número de caso | 1.4.8 |
| Tipo de prueba | Rendimiento |
| Objetivos | Verificar que la planificación de un slice grande respeta el plazo configurado. |
| Prerrequisitos | VM Placement con plazo configurable (F3). |
| Procedimiento | 1) Configurar un plazo de planificación de 2 s. 2) Planificar un slice de 30 VMs. 3) Medir el tiempo de planificación. |
| Resultados esperados | Se obtiene un plan antes del plazo o el error PLANNING_TIMEOUT; No quedan reservas parciales. |
| Resultado obtenido | **NT** — función pendiente de implementación. |
| Evidencias | — |
| Comentarios | EX2-R4-D-06; HLD §4.7.4. |

## 1.5 Creación de slices

### 1.5.1 SLICE EX1 (6 VMS) EN EL DRIVER LINUX
| Campo | Contenido |
|---|---|
| Número de caso | 1.5.1 |
| Tipo de prueba | Funcional |
| Objetivos | Verificar el ciclo completo de la topología EX1 en el driver Linux. |
| Prerrequisitos | Imágenes Ubuntu y CirrOS registradas. |
| Procedimiento | 1) Registrar las imágenes Ubuntu y CirrOS en el catálogo. 2) Crear el slice con templates/ex1.json. 3) Procesar el trabajo. 4) Revisar los recursos creados. 5) Borrar el slice. |
| Resultados esperados | Slice READY con 6 VMs en los workers indicados; Cada imagen base se copia solo a los workers que la usan; Las 2 VMs CirrOS reciben su configuración de red; Al borrar no quedan VMs, redes ni imágenes sin uso. |
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
| Procedimiento | 1) Crear el cluster.json de fase 2 (server1–4 en 192.168.201.1–4, ovs1). 2) Instalar los agentes y ejecutar el bootstrap. 3) Crear los slices lineal y anillo. 4) Verificar procesos QEMU y puertos OVS en cada server. |
| Resultados esperados | Ambos slices quedan READY; Cada VM tiene un proceso QEMU con su PID; Los puertos OVS llevan la C-VLAN de su enlace; Hay ping entre VMs alojadas en servers distintos. |
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
| Procedimiento | 1) Verificar que el servicio de túneles g5-tunnels esté activo y que existan las credenciales de OpenStack. 2) Ejecutar g5.cli create templates/os-lineal.json (3 VMs CirrOS, 2 enlaces /28 con IPs fijas) con una Idempotency-Key. 3) Ejecutar g5.cli wait con el operation_id recibido. 4) Consultar directamente Keystone, Neutron y Nova: proyecto, redes, puertos, instancias y host de cada VM. 5) Consultar el diagnóstico del slice en G5. |
| Resultados esperados | La creación responde HTTP 202 y la operación termina en SUCCEEDED; El slice queda READY; Existe el proyecto g5-<id> con 2 redes de tipo vlan sobre physnet1 (sin túneles); Los 4 puertos tienen las IPs pedidas; Las 3 instancias están ACTIVE; No se generan errores. |
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
| Procedimiento | 1) Abrir el túnel hacia Horizon (puerto 50080). 2) Iniciar sesión en el dominio Cloud. 3) Revisar Resumen del uso e Identity → Projects. 4) Seleccionar el proyecto g5-<id> y abrir Instances y Network Topology. |
| Resultados esperados | El slice aparece como un proyecto propio, separado de lab5 y cloud_admin; Se ven sus 3 instancias en estado Active; La topología muestra la forma lineal con 2 redes. |
| Resultado obtenido | **PASS [REAL]** — el proyecto `g5-be4b301b…` aparece por separado en Horizon (Resumen del uso: 3 vCPU, 12 GB disco, 1,5 GB RAM), junto a `lab5`. |
| Evidencias | `docs/evidencias/F1/TC-1.5.4_horizon_resumen_uso.png`. |
| Comentarios | EX2-R3-I-06, R3-D-05. Conviene agregar capturas de Compute → Instances y Network Topology del mismo proyecto. |

### 1.5.5 MISMO NÚCLEO PARA LINUX Y OPENSTACK
| Campo | Contenido |
|---|---|
| Número de caso | 1.5.5 |
| Tipo de prueba | Integración (Slice Manager ↔ drivers Linux y OpenStack) |
| Objetivos | Verificar que la misma API, Store y Engine despliegan slices de ambos proveedores. |
| Prerrequisitos | Ninguno. |
| Procedimiento | 1) Registrar una imagen para el driver Linux y preparar el OpenStack de prueba. 2) Crear un slice con provider linux. 3) Crear un slice con provider openstack. 4) Procesar ambos trabajos con el mismo Engine. |
| Resultados esperados | Ambos slices quedan READY con su provider correcto; Los dos usan la misma API, el mismo Store y la misma cola de trabajos. |
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
| Procedimiento | 1) Crear un slice OpenStack. 2) Listar GET /v1/slices con el token del administrador. 3) Consultar el slice con el token del alumno. |
| Resultados esperados | El listado muestra el slice con provider openstack y status READY; El alumno no puede ver el slice (HTTP 404). |
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
| Procedimiento | 1) Enviar la creación y anotar el operation_id de la respuesta 202. 2) Consultar GET /v1/operations/{id} periódicamente. 3) Registrar el estado final y los tiempos de inicio y fin. |
| Resultados esperados | La API responde de inmediato con HTTP 202; La operación pasa de PENDING a SUCCEEDED; Termina en 1 intento y sin error. |
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
| Procedimiento | 1) Con el slice en READY, consultar GET /v1/slices/{id}/diagnostics. 2) Comparar el resultado con Nova. |
| Resultados esperados | El diagnóstico indica ok: true; Lista las 3 instancias en ACTIVE con su host; Los datos coinciden con lo que reporta Nova. |
| Resultado obtenido | **PASS [REAL]** |
| Evidencias | `diagnostico_g5` en la evidencia de 1.5.3. |
| Comentarios | EX1-R1C-D-04/05 (monitorear y validar consistencia). |

### 1.6.4 ACCESO A CONSOLA CON CREDENCIAL TEMPORAL
| Campo | Contenido |
|---|---|
| Número de caso | 1.6.4 |
| Tipo de prueba | Funcional (seguridad) |
| Objetivos | Entregar al dueño una URL de consola temporal sin exponer credenciales de infraestructura. |
| Prerrequisitos | Caso 1.5.3; túnel 56080. |
| Procedimiento | 1) Solicitar POST /v1/slices/{id}/vms/vm1/console para el slice OpenStack. 2) Abrir la URL recibida a través del túnel 56080. 3) Driver Linux: emitir un token de consola, dejarlo vencer y luego revocar otro. |
| Resultados esperados | Se recibe una URL noVNC temporal reescrita a 127.0.0.1:56080, sin credenciales de infraestructura; Con la URL se accede a la consola de la VM; Linux: un token vencido o revocado se rechaza. |
| Resultado obtenido | **PASS [REAL]** (OpenStack) · **PASS [AUT]** (Linux) |
| Evidencias | `consola_vm1_g5` (token omitido) en la evidencia de 1.5.3; `test_console_token_expiration_revocation_and_slice_state`. |
| Comentarios | EX2-R1B-I-15. |

### 1.6.5 CONSUMO DE RECURSOS DEL SISTEMA
| Campo | Contenido |
|---|---|
| Número de caso | 1.6.5 |
| Tipo de prueba | Funcional |
| Objetivos | Mostrar la capacidad total, asignada y disponible por host en ambos clústeres. |
| Prerrequisitos | Inventario y monitoreo de ambos clústeres (F3). |
| Procedimiento | 1) Consultar el inventario de recursos de ambos clústeres. 2) Crear un slice. 3) Volver a consultar el inventario. |
| Resultados esperados | Se muestra la capacidad total, asignada y disponible por host de Linux y de OpenStack; La capacidad asignada aumenta exactamente en lo que pidió el slice. |
| Resultado obtenido | **NT** — función pendiente de implementación. |
| Evidencias | — |
| Comentarios | EX2-R1B-I-12, EX2-R4-I-01. Hoy solo existe `/v1/nodes` para Linux. |

## 1.7 Eliminación

### 1.7.1 BORRADO LINUX CON LIMPIEZA DE IMÁGENES NO USADAS
| Campo | Contenido |
|---|---|
| Número de caso | 1.7.1 |
| Tipo de prueba | Funcional |
| Objetivos | Eliminar VMs, recursos de red y bases sin referencias. |
| Prerrequisitos | Slice Linux READY. |
| Procedimiento | 1) Partir de un slice Linux en READY. 2) Enviar DELETE /v1/slices/{id} con una Idempotency-Key. 3) Procesar el trabajo. 4) Revisar reservas, recursos e imágenes en los workers. |
| Resultados esperados | La operación termina en SUCCEEDED y el slice en DELETED; No quedan reservas; No quedan VMs, interfaces ni imágenes base sin uso en los workers. |
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
| Procedimiento | 1) Partir del slice os-lineal del caso 1.5.3 en READY. 2) Ejecutar g5.cli delete con una Idempotency-Key. 3) Ejecutar g5.cli wait hasta el estado final. 4) Listar en Keystone, Nova y Neutron los proyectos, servidores, redes, subredes y puertos g5-*. 5) Revisar los hypervisors y los proyectos lab5 y cloud_admin. |
| Resultados esperados | La operación termina en SUCCEEDED y el slice en DELETED; No queda ningún proyecto, servidor, red, subred ni puerto g5-*; lab5, cloud_admin y la red external siguen intactos; La capacidad de los workers se libera. |
| Resultado obtenido | **PASS [REAL]** — 18,1 s; 12 recursos DELETED en el diario; OpenStack igual que antes de la prueba. |
| Evidencias | `docs/evidencias/F1/TC-1.7.2_borrado_os-lineal_20261103.json`. |
| Comentarios | EX2-R3-I-05, R1B-I-13. |

### 1.7.3 BORRADO CON OTRA OPERACIÓN EN CURSO
| Campo | Contenido |
|---|---|
| Número de caso | 1.7.3 |
| Tipo de prueba | Unitaria (concurrencia) |
| Objetivos | Impedir operaciones incompatibles sobre el mismo slice. |
| Prerrequisitos | Slice READY con un borrado pendiente. |
| Procedimiento | 1) Partir de un slice en READY. 2) Solicitar su borrado (queda pendiente). 3) Antes de que termine, solicitar reconcile. |
| Resultados esperados | El reconcile se rechaza con HTTP 409 «El slice tiene una operación activa»; El borrado sigue su curso. |
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
| Procedimiento | 1) Crear dos slices A y B. 2) Borrar el slice A. 3) Consultar el slice B. |
| Resultados esperados | A queda DELETED; B sigue READY con todas sus reservas. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_delete_one_slice_preserves_other`. |
| Comentarios | En OpenStack, además, cada slice es un proyecto distinto (verificado en 1.7.2). |

### 1.7.5 BORRADO CON DIARIO INCOMPLETO
| Campo | Contenido |
|---|---|
| Número de caso | 1.7.5 |
| Tipo de prueba | Integración (recuperación) |
| Objetivos | Verificar que el borrado encuentra por nombre recursos creados cuyo UUID no llegó a registrarse (corte a mitad de operación). |
| Prerrequisitos | Slice OpenStack READY; diario de redes y puertos sin UUID. |
| Procedimiento | 1) Partir de un slice OpenStack en READY. 2) Simular un corte: dejar las redes y puertos sin UUID en el diario de recursos. 3) Solicitar el borrado. 4) Revisar OpenStack. |
| Resultados esperados | El slice queda DELETED; El driver encuentra por nombre los recursos sin UUID y los borra; No queda ningún recurso del slice. |
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
| Procedimiento | 1) Inyectar un fallo temporal en la acción network del agente y crear un slice. 2) Revisar los eventos del slice. 3) Inyectar una respuesta 503 en un GET a Nova. 4) Inyectar una respuesta 503 en un POST a Neutron. |
| Resultados esperados | El slice queda READY y se registra un evento RETRY; El GET se reintenta y termina con éxito; El POST no se repite automáticamente (una sola petición) para no duplicar recursos. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_temporary_failure_retries_successfully`, `test_retries_guest_setup_transient_failure`, `test_get_retries_5xx_but_post_does_not`. |
| Comentarios | EX1-R2-I-04, EX2-R3-D-02. |

### 1.8.2 FALLO PERMANENTE SE COMPENSA SIN RESIDUOS
| Campo | Contenido |
|---|---|
| Número de caso | 1.8.2 |
| Tipo de prueba | Integración |
| Objetivos | Si una VM no se puede crear, retirar todo lo creado y liberar reservas. |
| Prerrequisitos | [AUT] fallo permanente inyectado (agente) o instancia en ERROR (Nova); [REAL] API G5 en el app server, `create_flavors=false` y sin flavor de 1 vCPU / 512 MB / 1 GB en OpenStack. |
| Procedimiento | 1) Registrar el estado de OpenStack: proyectos, redes, puertos, servidores y flavors. 2) Enviar POST /v1/slices con 2 VMs OpenStack de disk_gb 1, para las que no existe flavor (create_flavors desactivado). 3) Esperar el estado final de la operación. 4) Revisar los eventos del slice. 5) Comparar OpenStack con el estado inicial. 6) En las pruebas automáticas: inyectar un fallo permanente en el agente o una instancia en ERROR en Nova. |
| Resultados esperados | La operación termina en FAILED y el slice en FAILED_CLEANED; El error indica la causa (falta el flavor o Nova reporta ERROR); Los recursos creados antes del fallo (proyecto, red, subred y puertos) se eliminan; OpenStack queda idéntico al estado inicial y no quedan reservas. |
| Resultado obtenido | **PASS [REAL]** — clúster OpenStack: faltaba el flavor de 1 GB (`create_flavors=false`); se crearon proyecto, red, subred y 2 puertos, falló y compensó en 5,7 s: slice `FAILED_CLEANED`, proyectos, redes, puertos, servidores y flavors idénticos al estado previo. También **PASS [AUT]**. |
| Evidencias | `docs/evidencias/F1/TC-1.8.2_compensacion_real_20261105.json`; `test_permanent_create_failure_compensates`, `test_nova_error_is_compensated`, `test_missing_flavor_without_permission_fails_cleanly`. |
| Comentarios | HLD F3 pasos 31c–31d. |

### 1.8.3 LIMPIEZA INCIERTA CONSERVA RESERVAS
| Campo | Contenido |
|---|---|
| Número de caso | 1.8.3 |
| Tipo de prueba | Integración |
| Objetivos | No liberar capacidad si no se confirma la limpieza. |
| Prerrequisitos | Falla la creación y también el borrado. |
| Procedimiento | 1) Inyectar fallos permanentes en vm_ensure y en delete. 2) Crear el slice. 3) Quitar los fallos y volver a solicitar el borrado. |
| Resultados esperados | Tras el primer intento el slice queda ERROR_CLEANUP y conserva sus reservas; Tras el reintento las reservas se liberan. |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_unknown_cleanup_holds_reservations_until_retry`, `test_reconcile_failure_does_not_destroy_existing_disks`. |
| Comentarios | EX1-R1C-D-05. |

### 1.8.4 REINICIO O RESPUESTA PERDIDA SIN DUPLICADOS
| Campo | Contenido |
|---|---|
| Número de caso | 1.8.4 |
| Tipo de prueba | Integración (recuperación) |
| Objetivos | Verificar que repetir un despliegue (reinicio del ejecutor, respuesta perdida) no duplica VMs ni recursos. |
| Prerrequisitos | Ninguno. |
| Procedimiento | 1) Ejecutar un despliegue, simular el reinicio del ejecutor y reprocesar el trabajo. 2) Perder la respuesta de vm_ensure después de que la VM ya se creó. 3) Volver a ejecutar el despliegue de un slice OpenStack que ya existe. |
| Resultados esperados | El número de VMs y recursos es el mismo que con una sola ejecución; La operación termina en SUCCEEDED. |
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
| Procedimiento | 1) Tomar la hora de creación y de fin de la operación del caso 1.5.3. 2) Calcular la diferencia. |
| Resultados esperados | El slice de 3 VMs queda listo en 120 s o menos; Las VMs se crean en paralelo (hasta 3 a la vez). |
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
| Procedimiento | 1) Tomar la hora de creación y de fin de la operación de borrado del caso 1.7.2. 2) Calcular la diferencia. |
| Resultados esperados | El borrado completo, con verificación, termina en 120 s o menos. |
| Resultado obtenido | **PASS [REAL]** — 18,1 s. |
| Evidencias | `operacion_g5` en la evidencia de 1.7.2. |
| Comentarios | — |

### 1.9.3 SLICES CONCURRENTES EN EL CLÚSTER REAL
| Campo | Contenido |
|---|---|
| Número de caso | 1.9.3 |
| Tipo de prueba | Rendimiento (concurrencia) |
| Objetivos | Crear 2 slices en paralelo y medir tiempos y aislamiento. |
| Prerrequisitos | Disco suficiente en los workers (9 GB c/u). |
| Procedimiento | 1) Crear (con autorización) un flavor de 1 GB de disco. 2) Lanzar 2 creaciones de slice al mismo tiempo. 3) Medir los tiempos y verificar el aislamiento. |
| Resultados esperados | Ambos slices quedan READY; Cada uno en su propio proyecto; Se registran los tiempos de cada uno. |
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
| Procedimiento | 1) Configurar parallel_servers = 1, crear el slice y medir. 2) Configurar parallel_servers = 3, crear el slice y medir. 3) Comparar los tiempos. |
| Resultados esperados | El despliegue en paralelo tarda menos; Ambos producen los mismos recursos. |
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
| Procedimiento | 1) Partir de un slice en READY. 2) Enviar POST /v1/slices/{id}/stop. 3) Verificar el estado y los recursos. 4) Enviar POST /v1/slices/{id}/start. 5) Verificar el estado y los recursos. |
| Resultados esperados | Tras detener: STOPPED, con discos, redes y reservas conservados (en OpenStack las VMs pasan a SHUTOFF); Tras reanudar: READY con la misma cantidad de recursos (en OpenStack las VMs vuelven a ACTIVE). |
| Resultado obtenido | **PASS [AUT]** |
| Evidencias | `test_stop_start_keeps_disks_networks_and_reservations`, `test_stop_and_start_keep_resources`. |
| Comentarios | HLD F8. |

## 1.11 Edición de slices desplegados

### 1.11.1 AGREGAR UNA VM A UN SLICE DESPLEGADO
| Campo | Contenido |
|---|---|
| Número de caso | 1.11.1 |
| Tipo de prueba | Funcional |
| Objetivos | Aplicar un cambio incremental a un slice READY sin afectar las VMs existentes. |
| Prerrequisitos | Edición con plan incremental (F2). |
| Procedimiento | 1) Partir de un slice lineal en READY. 2) Solicitar agregar una VM conectada al último nodo. 3) Esperar el estado final. 4) Verificar las VMs que ya existían. |
| Resultados esperados | El slice pasa por UPDATING y vuelve a READY; La VM nueva queda conectada; Las VMs anteriores conservan su ID y su host. |
| Resultado obtenido | **NT** — función pendiente de implementación. |
| Evidencias | — |
| Comentarios | EX2-R1B-I-13; HLD F7. |

### 1.11.2 EDICIÓN CON VERSIÓN OBSOLETA
| Campo | Contenido |
|---|---|
| Número de caso | 1.11.2 |
| Tipo de prueba | Unitaria |
| Objetivos | Rechazar un cambio basado en una versión que otro usuario ya modificó. |
| Prerrequisitos | Control de versión del slice (F2). |
| Procedimiento | 1) Los usuarios A y B leen la versión v del slice. 2) A guarda su cambio. 3) B envía su cambio basado en la versión v. |
| Resultados esperados | El cambio de A se acepta y el slice pasa a la versión v+1; El de B se rechaza con HTTP 409 y se le pide revisar los cambios. |
| Resultado obtenido | **NT** — función pendiente de implementación. |
| Evidencias | — |
| Comentarios | EX1-R1-D-10; HLD §4.1.6. |

## 1.12 Red y seguridad del slice

### 1.12.1 SALIDA A INTERNET SOLO PARA LAS VMS AUTORIZADAS EN OPENSTACK
| Campo | Contenido |
|---|---|
| Número de caso | 1.12.1 |
| Tipo de prueba | Funcional |
| Objetivos | Verificar que solo las VMs marcadas con salida a Internet la obtienen. |
| Prerrequisitos | Plan de red y router hacia `external` (F4). |
| Procedimiento | 1) Crear un slice con vm1 autorizada para salir a Internet y vm2 sin autorización. 2) Desde la consola de vm1, ejecutar ping 8.8.8.8. 3) Desde la consola de vm2, ejecutar ping 8.8.8.8. |
| Resultados esperados | vm1 recibe respuesta; vm2 no tiene salida. |
| Resultado obtenido | **NT** — función pendiente de implementación. |
| Evidencias | — |
| Comentarios | EX2-R5-I-04. |

### 1.12.2 REGLAS DE SEGURIDAD DEL SLICE EN OPENSTACK
| Campo | Contenido |
|---|---|
| Número de caso | 1.12.2 |
| Tipo de prueba | Funcional |
| Objetivos | Aplicar security groups según lo declarado (p. ej. solo SSH desde un origen). |
| Prerrequisitos | Security groups por slice (F4). |
| Procedimiento | 1) Crear un slice con la regla «TCP 22 desde 10.8.0.0/24». 2) Conectarse por SSH desde un origen permitido. 3) Conectarse por SSH desde un origen no permitido. 4) Revisar el security group del proyecto en OpenStack. |
| Resultados esperados | La conexión permitida se establece; La no permitida se rechaza; La regla aparece en el security group del proyecto. |
| Resultado obtenido | **NT** — función pendiente de implementación. |
| Evidencias | — |
| Comentarios | EX2-R5-I-03. |

---

## Trazabilidad con EX1/EX2

| Criterio | Casos |
|---|---|
| EX1-R1C-D-01 Flujo completo y en orden | 1.3.1, 1.5.1, 1.5.3 |
| EX1-R1C-D-02 Paralelismo | 1.9.1, 1.9.4 |
| EX1-R1C-D-03 Sin race condition / overcommitting | 1.4.1, 1.4.2 |
| EX1-R1C-D-04/05 Monitoreo y consistencia | 1.6.3, 1.8.3 |
| EX1-R1C-D-06 Autenticación y autorización | 1.1.1–1.1.4 |
| EX1-R1-D-09/10 Retomar edición; concurrencia al editar | 1.3.5, 1.11.2 |
| EX2-R1B-I-01 Independencia de la infraestructura | 1.5.5, 1.5.3 |
| EX2-R1B-I-02 Concurrencia de usuarios | 1.4.2, 1.9.3 |
| EX2-R1B-I-03/04/05/06 Topologías, combinar, editar, borradores | 1.3.2–1.3.5 |
| EX2-R1B-I-07/08/09 Exportar/importar topologías | 1.2.5, 1.3.5 |
| EX2-R1B-I-11/12/13/15 Listar, consumo, borrar/editar, consola | 1.6.1, 1.6.5, 1.7.1–1.7.2, 1.11.1, 1.6.4 |
| EX2-R3-I-02/03/04/05/06 OpenStack | 1.5.3, 1.9.1, 1.7.2, 1.5.4 |
| EX2-R4-I-01/02/03/04 VM Placement | 1.6.5, 1.4.6, 1.4.7 |
| EX2-R4-D-06 Tiempo de planificación | 1.4.8 |
| EX2-R5-I-01 VLAN sin túneles | 1.5.3 |
| EX2-R5-I-03/04 Seguridad y salida a Internet | 1.12.2, 1.12.1 |

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
