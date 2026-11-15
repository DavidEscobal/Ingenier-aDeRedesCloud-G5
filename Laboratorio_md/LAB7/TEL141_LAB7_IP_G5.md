# TEL141 — Laboratorio 7: Informe previo — Grupo 5

**Tema:** Módulo de VM Placement y pruebas unitarias · **Semestre:** 2026-2 · **Proyecto:** PUCP Private Cloud Orchestrator

> **Cómo leer este informe.** El módulo de VM Placement de G5 ya está implementado (microservicio `vm-placement`),
> integrado al Slice Manager y probado de punta a punta en ambos clústeres (evidencia MS-17, 15/11/2026). Cada
> respuesta distingue tres niveles: **[Implementado]** (código en la rama `fase2`, con prueba), **[Probado en el
> clúster]** (evidencia real) y **[Diseño]** (propuesta aún no implementada). Las rutas citadas son del repositorio.

---

## ACTIVIDAD PREVIA: túneles SSH desde Localhost hacia el Head Node (0 ptos)

El head node de OpenStack se alcanza por el gateway de la topología de G5 (`10.20.11.245`, puerto `5821`, según la
tabla de accesos de la guía del LAB6). Cada túnel publica en `localhost` un servicio del controlador:

| Puerto local | Puerto en el head node | Servicio | Uso en el módulo de placement |
|---|---|---|---|
| 55000 | 5000 | Keystone | Token para consultar Nova |
| 58774 | 8774 | Nova (compute) | `os-hypervisors` (capacidad y uso), `os-aggregates` (zonas), crear VMs con zona/host |
| 58778 | 8778 | Placement API | Inventario y asignaciones por proveedor de recursos (consulta) |
| 59696 | 9696 | Neutron | Redes, puertos y grupos de seguridad del slice |
| 59292 | 9292 | Glance | Imágenes |
| 56080 | 6080 | noVNC | Consola de las VMs |
| 50080 | 80 | Horizon | Verificación visual (proyecto y host de cada VM) |

```bash
ssh -NL 55000:127.0.0.1:5000 ubuntu@10.20.11.245 -p 5821
ssh -NL 58774:127.0.0.1:8774 ubuntu@10.20.11.245 -p 5821
ssh -NL 58778:127.0.0.1:8778 ubuntu@10.20.11.245 -p 5821
ssh -NL 59696:127.0.0.1:9696 ubuntu@10.20.11.245 -p 5821
ssh -NL 59292:127.0.0.1:9292 ubuntu@10.20.11.245 -p 5821
ssh -NL 56080:127.0.0.1:6080 ubuntu@10.20.11.245 -p 5821
ssh -NL 50080:127.0.0.1:80   ubuntu@10.20.11.245 -p 5821
```

Equivalente en un solo proceso: `ssh -N -L 55000:127.0.0.1:5000 -L 58774:127.0.0.1:8774 -L 58778:127.0.0.1:8778 -L 59696:127.0.0.1:9696 -L 59292:127.0.0.1:9292 -L 56080:127.0.0.1:6080 -L 50080:127.0.0.1:80 ubuntu@10.20.11.245 -p 5821`.

**[Implementado]** En el despliegue del orquestador estos túneles no los abre una persona: el contenedor `os-tunnel`
(`services/os-tunnel/entrypoint.sh`) mantiene `ssh -N -L 0.0.0.0:<p>:<controller>:<p>` para 5000, 8774, 9696, 9292 y
6080, con `ExitOnForwardFailure` y reinicio automático, visibles solo en la red interna de Docker. El 8778
(Placement API) aún no está habilitado en la llave del gateway (`permitopen`); el placement de G5 no lo necesita
porque toma el inventario de `os-hypervisors`.

---

## 1) INTRODUCCIÓN (0.5 ptos)

### a) Necesidad de un módulo de VM Placement

Un slice es un conjunto de VMs que deben quedar distribuidas sobre servidores físicos con capacidad finita (en
nuestro clúster: 3 servidores Linux de 4 CPU / 3,8 GB de RAM / ~9,7 GB de disco y 3 computes OpenStack de
4 vCPU / 3,9 GB / 9 GB). El módulo resuelve **a qué servidor va cada VM** de modo que:

- ninguna dimensión de ningún servidor se exceda (vCPU comprometidas, CPU real, RAM, disco);
- se respeten las restricciones del usuario (zona de disponibilidad, VMs fijadas a mano);
- el slice se admita **completo o se rechace con un motivo**, sin quedar desplegado a medias;
- se use la menor cantidad posible de servidores nuevos (consolidación).

**Consecuencias de un placement deficiente**, varias observadas en nuestro propio clúster:

| Problema | Efecto |
|---|---|
| Sobrecompromiso de CPU o RAM | Contención de CPU, latencia y, en RAM, *swapping* o el OOM killer matando QEMU. |
| Disco sobreasignado | Un qcow2 que crece llena el disco del servidor y se pausan todas sus VMs. En el clúster Linux una Ubuntu de 4 GB necesita ≈ 8 GB reservables y hay ≈ 6,5 GB libres (MS-18): sin control, el fallo aparece a mitad del despliegue. |
| Fragmentación | Hay capacidad total suficiente pero repartida en trozos que no alojan ninguna VM: se rechazan slices que sí cabían. La heurística BFD del HLD rechazó 170 de 360 instancias factibles. |
| Hosts encendidos de más | Más consumo y menos capacidad libre para slices grandes. |
| Decisión delegada a ciegas | Sin host forzado, Nova elige con sus propios ratios (16 : 1,5 : 1) y criterios, distintos de los de G5. |
| Condiciones de carrera | Dos slices simultáneos que ven la misma capacidad libre y la consumen dos veces. |

### b) Objetivos funcionales del módulo e impacto dentro del orquestador

**Decisiones que automatiza [Implementado]:**

1. **Filtrado** de candidatos: zona pedida, salud del host, telemetría vigente (≤ 15 s).
2. **Asignación** `{vm → host}` de todo el slice con BCDP v2, minimizando los hosts nuevos que se ocupan.
3. **Admisión o rechazo** con estado (`PLAN_FOUND`, `HEURISTIC_NO_PLAN`, `PLANNING_TIMEOUT`, `INVALID_OR_ERROR`) y
   motivo legible (p. ej. «RAM insuficiente: se piden 3072 y quedan 2048 libres»).
4. **Respeto de VMs fijadas** por el usuario (paso 3 del Ex2: «2 VMs en server2»), que se descuentan primero.
5. **Validación** independiente de todo plan antes de responder.
6. **Elección de la plataforma** cuando el usuario pide modo automático: se planifica en Linux y en OpenStack y se
   despliega donde ocupe menos servidores nuevos (ver 4 b).

**Ventajas de un módulo unificado para Linux y OpenStack:**

- **Una sola función objetivo y unas mismas reglas**: el mismo slice recibe un plan comparable en ambos
  backends; las pruebas se escriben una vez.
- **Un modelo de host normalizado** (CPU, RAM, disco, uso, zona, salud): las diferencias de cada plataforma quedan
  en el adaptador de inventario (microservicio de monitoreo), no en el algoritmo.
- **Control del orquestador**: en OpenStack el host elegido se fuerza en Nova; así la decisión es de G5 y no del
  scheduler de OpenStack, y el comportamiento es el mismo que en Linux, donde no hay scheduler.
- **Desacople**: es un servicio sin estado; se puede cambiar la heurística (BFD → BCDP v2 se hizo así) sin tocar el
  Slice Manager ni los drivers.

---

## 2) ANÁLISIS DEL CLÚSTER LINUX (0.5 ptos)

### a) Recursos a considerar y factores de discriminación

**[Implementado]** Cada host se describe en **cuatro dimensiones** y cada una tiene su límite
(`services/vm-placement/src/g5_placement/planner.py`, `host_vectors`):

| Dimensión | Capacidad | Uso actual | Demanda de la VM |
|---|---|---|---|
| vCPU nominal | `ratio_cpu (2,0) × núcleos`, acotado por `vcpus_max` del servidor | vCPU comprometidas | `vcpus` |
| CPU real (centésimas) | `85 % × 100 × núcleos` | CPU medida del host | CPU prevista; sin perfil, `100 × vcpus` |
| RAM (MB) | RAM neta (ratio 1,0; ya descontada la reserva del host) | RAM comprometida | `memory_mb` |
| Disco (MB) | disco neto reservable (ratio 1,0) | disco comprometido | `disk_gb × 1024` |

**Factores que discriminan** (filtros previos, `eligible`):

- **Zona de disponibilidad** pedida por el usuario.
- **Estado del nodo**: habilitado en el registro y con agente respondiendo (`healthy`).
- **Antigüedad de la telemetría**: más de 15 s → se descarta («telemetría vencida»).
- **Rol del nodo**: el gateway del slice y los nodos de gestión no son candidatos (no figuran como workers).
- **Ocupación** (`occupied`): no filtra, pero prioriza los hosts ya ocupados para no abrir nuevos.

Se separan **compromiso** (lo reservado por slices, sale del registro transaccional) y **consumo medido** (CPU
real). El compromiso protege RAM y disco, que no admiten sobreasignación; la CPU real permite compartir núcleos entre
cargas que no usan el 100 % todo el tiempo (ver 4 e).

### b) Recolección de la información desde los nodos físicos

**[Implementado y probado en el clúster]**

1. **Agente en cada servidor** (`g5/agent.py`, acción `metrics`, solo lectura): mide la CPU como incremento de
   `/proc/stat` en 1 s (centésimas de CPU), la CPU de cada proceso QEMU de G5, `MemAvailable` de `/proc/meminfo` y el
   disco libre del almacén de VMs.
2. **Platform-manager** (`GET /v1/metrics`): consulta en paralelo a todos los agentes por SSH a través del gateway y
   añade, por servidor, la **capacidad** (`config/cluster.json`) y lo **asignado** (tabla `allocations`, registro
   transaccional de reservas). Para OpenStack añade `os-hypervisors` y la zona de cada host (`os-aggregates`).
3. **Microservicio de monitoreo** (`services/monitoring`): muestrea `/v1/metrics` cada 10 s, normaliza al modelo de
   host del placement (`normalize.py`), guarda historial en SQLite y publica `GET /v1/monitoring/state` (estado actual
   con `age_s`) y `/v1/monitoring/history`. La web lo muestra en la página «Recursos».

Ejemplo real (15/11/2026): `server1 libre 6494 MB de 9749 | reservable 6 GB, asignado 0`.

### c) Estrategias de placement posibles

| Estrategia | Idea | Ventaja | Desventaja |
|---|---|---|---|
| Round-Robin | Turnos entre hosts | Trivial, reparte | Ignora capacidades; falla con VMs heterogéneas (era el reparto provisional del adaptador Linux antes de R4) |
| First-Fit | Primer host donde cabe | Rápido | Fragmenta; depende del orden |
| Best-Fit | Host que queda más lleno | Consolida | Deja huecos pequeños inútiles |
| Worst-Fit / spread | Host más libre | Equilibra carga | Ocupa todos los hosts; no consolida |
| FFD / BFD (decreasing) | Ordena VMs de mayor a menor y aplica First/Best-Fit | Mejor que sin ordenar | Una sola dimensión de orden; en 4 dimensiones falla mucho (BFD del HLD: 170/360 sin plan) |
| Producto punto (tipo Tetris) | Elige la VM cuya demanda se alinea con lo libre del host | Multidimensional | Codicioso, sin corrección posterior |
| **BCDP v2 (elegida)** | Llena host por host con producto punto, refina con intercambios, repara y elimina hosts | 1/360 sin plan, +0,05 hosts sobre el óptimo, 95 % óptimo | Más lento (≈ 170 ms en 240 VMs; límite de 1 s) |
| Solver exacto (CP-SAT) | Programación entera | Óptimo | Tiempo impredecible; usado solo como referencia |

La comparación se hizo contra CP-SAT en 360 instancias de 6 a 240 VMs y 3 a 40 hosts
(`vm-placement_md/G5_Documentacion_Ex1_Fase2_DETALLADA_Claude.md`, sección 2).

### d) Sin un componente central: evitar conflictos, optimizar y facilitar la orquestación

En Linux no hay un scheduler como el de Nova; G5 crea el equivalente con **un único escritor** del estado de
capacidad y **optimismo con verificación**:

1. **Reserva atómica en un solo lugar [Implementado].** El platform-manager es el único que escribe reservas: en una
   transacción SQLite comprueba que las VMs caben en `capacity` de cada servidor y las inserta en `allocations`. Si
   otro slice ganó el hueco, responde **409** y no queda nada a medias.
2. **Planificación serializada por proveedor [Implementado].** El Slice Manager planifica y envía bajo un candado por
   proveedor; si la reserva devuelve 409 por capacidad, vuelve a planificar (hasta 3 intentos).
3. **Registro de planes recientes [Implementado].** Como la telemetría puede tener hasta 10 s, los planes admitidos en
   los últimos 90 s se suman como compromiso al inventario antes de planificar (evita doble asignación entre dos
   peticiones seguidas).
4. **Verificación local en el agente [Implementado].** Antes de crear, el agente vuelve a comprobar CPU, memoria y
   disco reales del servidor (`prepare`); si no alcanzan, el slice falla y se compensa (MS-18: «Disco insuficiente…»,
   FAILED_CLEANED sin restos).
5. **Idempotencia [Implementado].** Toda creación lleva `Idempotency-Key`: un reintento no duplica el slice.
6. **Optimización**: el algoritmo consolida (min. hosts nuevos) y la consolidación se mide en cada plan
   (`hosts_opened`).

---

## 3) ANÁLISIS DEL CLÚSTER OPENSTACK (1 pto)

### a) Mecanismos para influenciar el placement y su uso en el proyecto

| Mecanismo | Qué es | ¿Lo usamos? | Sustento |
|---|---|---|---|
| **Availability Zones** | Agregado de hosts con metadato `availability_zone`, visible para el usuario; Nova lo hace cumplir (filtro de zona) | **Sí, como mecanismo principal** | La zona es el concepto que G5 expone al usuario en ambos clústeres; el monitoreo la lee de `os-aggregates` y el placement filtra por ella |
| **Host Aggregates** | Agrupación de hosts con metadatos arbitrarios (p. ej. `ssd=true`), usada por filtros como `AggregateInstanceExtraSpecsFilter` vía flavors | Indirectamente | Las AZ son agregados con metadato de zona. No usamos metadatos de afinidad por flavor: crearían un flavor por combinación |
| **Scheduler hints / host forzado** | `availability_zone="zona:host"` (requiere rol admin) o el campo `host` (API ≥ 2.74); hints como `different_host`, `same_host` | **Sí, para hacer cumplir el host elegido** | Sin forzar el host, Nova reelegiría con sus ratios (16 : 1,5 : 1). G5 usa `zona:host`: la decisión de G5 se cumple **dentro** de la zona |
| **Placement API** | Proveedores de recursos, inventarios y asignaciones (lo que consulta el scheduler) | Solo como referencia | El placement de G5 toma el inventario de `os-hypervisors` (vCPU, RAM, `local_gb_used`) por el túnel ya disponible; escribir asignaciones en Placement duplicaría lo que Nova hace al crear la VM |

**[Probado en el clúster]** El driver OpenStack crea cada servidor con `availability_zone = "<zona>:<host>"`
(`g5/drivers/openstack/driver.py`) y en MS-17 Nova respetó el plan: `vm1, vm2, vm3 → worker1`, verificado con
`OS-EXT-SRV-ATTR:host`.

### b) ¿Por qué Availability Zones como mecanismo principal de enforcement?

1. **Es el concepto del usuario.** El Ex2 pide desplegar «en la zona de disponibilidad elegida»; la AZ es el único
   mecanismo de los cuatro pensado para que el usuario (no el administrador) lo elija.
2. **Nova la hace cumplir de forma nativa.** Aunque el host forzado fallara o se omitiera, la VM no puede salir de la
   zona pedida.
3. **Mapea a Linux.** Un servidor Linux también tiene una etiqueta `zone` (hoy `linux`), así que la misma regla
   («solo hosts de la zona pedida») sirve en ambos backends. Es la abstracción común que pide 4 b.
4. **Dominio de fallo y gobierno.** Permite separar hosts por mantenimiento, por grupo o por capacidad sin tocar el
   algoritmo.
5. **Compatibilidad con el host forzado.** La sintaxis `zona:host` combina ambos: la AZ acota y el host concreta la
   decisión de BCDP v2.

### c) Cómo se usan las zonas como decisión final dentro del VM Placement

**[Implementado]**

1. La web ofrece las zonas reales del proveedor (las que publica el monitoreo); el usuario elige una o «cualquiera».
2. El Slice Manager pasa `zone` al placement. **Filtro duro**: los hosts de otra zona se descartan con el motivo
   «fuera de la zona X» (`discarded_hosts` en la respuesta).
3. BCDP v2 elige el host **solo entre los de esa zona**. Si ninguno alcanza: `HEURISTIC_NO_PLAN`, «no hay servidores
   candidatos en la zona X», y el slice se rechaza (409) sin crear nada.
4. Con plan, el Slice Manager escribe en cada VM `host` y, en OpenStack, la `zone` de ese host; el driver crea el
   servidor con `availability_zone = "<zona>:<host>"`.
5. Si se pide zona sin que el placement esté activo, el Slice Manager rechaza en vez de ignorarla.

**Estado real del clúster.** Hoy Nova tiene una sola zona de cómputo (`nova`, worker1–3). El mecanismo está
probado con zonas simuladas (`zona-a` en las pruebas) y con `nova` en el clúster real. **[Diseño]** Para la demo se
propone crear dos agregados con zona (p. ej. `g5-az1` = worker1–2 y `g5-az2` = worker3) y, en Linux, etiquetar
server2–4 como la zona del paso 2 del Ex2. Ambos requieren permiso de administración (consulta al JP).

---

## 4) COMPARACIÓN Y DECISIONES DE DISEÑO (1 pto)

### a) Diferencias y similitudes

| Aspecto | Clúster Linux (G5) | OpenStack |
|---|---|---|
| Scheduler propio | No hay: el placement de G5 es el único que decide | Nova scheduler (filtros y pesos) |
| Inventario | Agente por SSH + `cluster.json` + registro `allocations` | `os-hypervisors` (+ `os-aggregates` para zonas) |
| CPU real medida | Sí (agente, `/proc/stat`) | No (sin acceso a los workers): se asume demanda completa |
| Ratios de sobreasignación | G5: CPU 2,0, RAM 1,0, disco 1,0 | Nova configurado 16,0 / 1,5 / 1,0 (distintos: por eso se fuerza el host) |
| Disco | Reserva completa del qcow2 + base + margen en el agente | `local_gb_used` = suma de flavors |
| Zonas | Etiqueta `zone` por servidor (hoy `linux`) | Availability Zones (hoy solo `nova`) |
| Ejecución de la decisión | El driver crea la VM en el servidor indicado | `availability_zone="zona:host"` |
| Reserva / carrera | Transacción del platform-manager | Nova reclama recursos al crear; G5 serializa por proveedor |

**Equivalencias que se abstraen:** host ↔ hipervisor; zona ↔ AZ; compromiso ↔ uso según Nova; salud ↔
`state=up, status=enabled` o agente respondiendo; capacidad neta ↔ capacidad del hipervisor. El adaptador
(`services/monitoring/src/g5_monitoring/normalize.py`) produce para ambos el **mismo modelo de host**: `id, zone,
cpu_cores, vcpus_max, ram_mb, disk_mb, vcpus_used, ram_used_mb, disk_used_mb, cpu_real_cent, occupied, healthy, age_s`.

### b) Lógica de decisión unificada

- **Campos mínimos de entrada**: por VM `id, vcpus, ram_mb, disk_mb` (opcionales `cpu_cent` y `host`); del slice
  `provider` y `zone`; el inventario normalizado; la política (ratios, límite de CPU real, edad máxima, tiempo).
- **Reglas antes de delegar al backend**:
  1. validar la especificación (nombres, tamaños, redes) en el compilador de topologías y el platform-manager;
  2. comprobar flavors e imágenes del backend (preflight de OpenStack) y la imagen en el almacén Linux;
  3. filtrar hosts (zona, salud, telemetría) y descontar las VMs fijadas;
  4. BCDP v2 + validador;
  5. reserva atómica en el platform-manager.
- **¿Dónde se decide el backend?** **[Implementado]** El usuario elige en la web Linux, OpenStack o
  **Automático**, y el valor viaja en la especificación del slice (`provider`). Con un proveedor concreto, el
  placement se ejecuta sobre los hosts de ese proveedor.
  **[Implementado] Modo automático** (`provider: "auto"`, `Planner.admit_auto` en
  `services/slice-manager/src/g5_slice_manager/placement.py`): el Slice Manager toma los candados de ambos
  proveedores en orden fijo, pide un plan para cada uno con la misma zona y ordena así:
  1. solo proveedores con `PLAN_FOUND`;
  2. menor número de hosts nuevos ocupados (`hosts_opened`, la función objetivo Z);
  3. menor número de hosts usados;
  4. desempate fijo: Linux y luego OpenStack.
  Envía el mejor al platform-manager. Si este lo rechaza por una causa que no es capacidad (imagen o red no
  admitidas, flavor ausente), prueba el siguiente; si lo rechaza por capacidad (otro slice ganó el hueco), vuelve a
  planificar. Si ninguno puede, responde 409 con el motivo de cada proveedor. La respuesta indica la plataforma
  elegida, los candidatos con su Z y los descartados, y la web lo muestra en el detalle del slice.
  Una VM fijada a un servidor determina la plataforma, porque ese servidor solo es candidato en su proveedor.

### c) Interfaz del módulo: entrada y salida

**[Implementado]** Servicio HTTP (FastAPI) sin estado, autenticado con token de servicio:
`POST /v1/placements` (contrato en `contracts/http/vm-placement.openapi.json`).

Entrada:

```json
{
  "provider": "openstack",
  "zone": "nova",
  "hosts": [{"id": "worker1", "zone": "nova", "cpu_cores": 4, "ram_mb": 3936, "disk_mb": 9216,
             "vcpus_used": 0, "ram_used_mb": 512, "disk_used_mb": 0, "cpu_real_cent": null,
             "occupied": false, "healthy": true, "age_s": 3.2}],
  "vms": [{"id": "vm1", "vcpus": 1, "ram_mb": 1024, "disk_mb": 4096},
          {"id": "vm2", "vcpus": 1, "ram_mb": 1024, "disk_mb": 4096, "host": "worker1"}],
  "policy": {"cpu_ratio": 2.0, "cpu_limit": 0.85, "max_age_s": 15, "timeout_s": 1.0}
}
```

Salida:

```json
{"status": "PLAN_FOUND", "algorithm": "BCDP v2", "plan": {"vm1": "worker1", "vm2": "worker1"},
 "hosts_used": ["worker1"], "hosts_opened": 1, "discarded_hosts": [], "reason": null, "elapsed_ms": 0.6}
```

Con rechazo: `status = HEURISTIC_NO_PLAN` y `reason` explica el recurso que falta o por qué no hay reparto.

**Quién la usa:** el **Slice Manager** (invoca, escribe `host`/`zone` en la especificación y guarda el resumen);
el **platform-manager** (reserva y ejecuta); la **web** (muestra el plan y los hosts descartados en el detalle del
slice). También es invocable como función (`g5_placement.planner.plan(request)`), que es como lo prueban los tests.

### d) Qué decide el orquestador y qué la plataforma

| Decisión | Quién | Comentario |
|---|---|---|
| Zona | Orquestador (elegida por el usuario, filtrada por el placement) | Nova además la hace cumplir |
| Host de cada VM | **Orquestador** (BCDP v2) | Forzado en ambos backends (`zona:host` en Nova). Se decidió no dejarlo a Nova porque sus ratios y su objetivo son otros y el slice no se trataría como un todo |
| Admisión del slice completo | Orquestador (placement + reserva atómica) | Todo o nada |
| Comprobación final de recursos | Plataforma | Nova filtra al crear; el agente Linux verifica disco y memoria reales |
| Creación de VMs, redes, discos | Plataforma (drivers) | Con compensación si algo falla |

---

## PROPUESTA FINAL (2 ptos)

### e) Algoritmo general de decisión

**Función objetivo** (HLD 4.7.2): abrir la menor cantidad de hosts vacíos.

```
min Z = Σ_h (1 − a_h) · y_h
```

`a_h = 1` si el host ya estaba ocupado; `y_h = 1` si queda ocupado tras el plan. Restricciones, para todo host `h` y
dimensión `q`: `uso_h,q + Σ_{v→h} dem_v,q ≤ cap_h,q`; cada VM en exactamente un host; las VMs fijadas en su host; solo
hosts candidatos.

**Pasos [Implementado, `engine.py` y `planner.py`]:**

1. **Filtrar** candidatos: zona, salud, telemetría ≤ 15 s. Los descartados se informan con su motivo.
2. **Construir vectores** de capacidad, uso y demanda (4 dimensiones, enteros, mismas unidades). Sin telemetría de
   CPU se usa la demanda completa de lo comprometido (un dato ausente no es cero).
3. **Descontar VMs fijadas** por el usuario y marcar su host como ocupado.
4. **BCDP v2** sobre el resto, **con el slice entero como unidad**:
   1. llenar primero los hosts ya ocupados (no aumentan Z);
   2. llenar un host eligiendo la VM cuyo vector de demanda tiene el mayor producto punto con la capacidad libre
      normalizada;
   3. refinar: intercambiar una VM colocada por una o dos pendientes que ocupen mejor el host (pesos por escasez);
   4. abrir un host nuevo simulando el llenado de los 3 vacíos más grandes y abriendo el que más absorbe;
   5. reparar: mover VMs del mismo slice para hacer sitio a una que quedó sin host;
   6. eliminar: intentar vaciar el host nuevo menos cargado;
   7. respaldo con otros parámetros antes de rechazar.
   Nunca mueve VMs en ejecución; es determinista; respeta el límite de 1 s.
5. **Validar** el plan con un validador independiente; si falla → `INVALID_OR_ERROR`.
6. **Explicar** el rechazo: recurso total insuficiente, VM que no cabe en ningún host o capacidad fragmentada.
7. **Construir la decisión por plataforma**: Linux → `worker = host` por VM; OpenStack → `host` y `zone` por VM →
   `availability_zone="zona:host"`.
8. **Reservar** de forma atómica; si se pierde la carrera (409), volver al paso 1.

**Uso eficiente de recursos con cargas dinámicas.** La CPU se trata en **dos dimensiones**: las vCPU nominales
admiten una sobreasignación 2:1 (dos vCPU por núcleo), mientras que la CPU **real** medida debe quedar por debajo del
85 %. Así, VMs que no usan el 100 % de su CPU todo el tiempo comparten núcleos, pero el host no se satura. RAM y
disco no se sobreasignan.

**[Diseño] Congestión durante el ciclo de vida del slice.** El HLD (4.7.5) prevé reemplazar la CPU prevista
puntual por un percentil alto (P99) del perfil de uso de cada tipo de VM, estimado con el historial que ya guarda el
monitoreo, para no admitir slices que caben hoy pero saturarían en su pico. Hoy se usa la demanda completa cuando no
hay perfil (el caso conservador); falta construir los perfiles.

### f) Diagrama de flujo del módulo de placement

```mermaid
flowchart TD
    A([Solicitud de slice: VMs, proveedor, zona]) --> B{¿VMs con worker ya asignado?}
    B -- Sí --> Z1[Se envía sin placement]
    B -- No --> C[Slice Manager: candado por proveedor]
    C --> D[Monitoreo: estado normalizado de los hosts<br/>+ planes admitidos en los últimos 90 s]
    D --> E[VM Placement: filtrar por zona, salud y telemetría ≤ 15 s]
    E --> F{¿Hay candidatos?}
    F -- No --> R1[HEURISTIC_NO_PLAN: sin servidores en la zona]
    F -- Sí --> G[Descontar VMs fijadas por el usuario]
    G --> H{¿La VM fijada cabe?}
    H -- No --> R2[HEURISTIC_NO_PLAN: VM fijada no cabe]
    H -- Sí --> I[BCDP v2 con el slice completo<br/>límite 1 s]
    I --> J{¿Plan?}
    J -- Tiempo agotado --> R3[PLANNING_TIMEOUT]
    J -- No --> R4[HEURISTIC_NO_PLAN + motivo del recurso escaso]
    J -- Sí --> K[Validador independiente]
    K -- Inválido --> R5[INVALID_OR_ERROR]
    K -- Válido --> L{Proveedor}
    L -- Linux --> M1[worker = host por VM]
    L -- OpenStack --> M2[host y zona por VM<br/>availability_zone = zona:host]
    M1 --> N[Platform-manager: reserva atómica]
    M2 --> N
    N --> O{¿Reserva aceptada?}
    O -- 409 capacidad, intento < 3 --> D
    O -- Sí --> P[Registrar plan 90 s + despliegue por el driver]
    P --> Q([Slice READY con las VMs en los hosts del plan])
    R1 --> X([409 al usuario con el motivo])
    R2 --> X
    R3 --> X
    R4 --> X
    R5 --> X
```

### g) Plan de pruebas (unit testing)

Las pruebas se ejecutan con `python -m unittest discover -s tests/app` (y el script `scripts/verificar.sh` antes de
cada integración). Todas usan inventarios sintéticos y deterministas, sin tocar el clúster.

**Pruebas unitarias del algoritmo y del servicio** (`tests/app/test_placement.py`) **[Implementado, en verde]**

| # | Caso | Entrada | Salida esperada | Test |
|---|---|---|---|---|
| U1 | Caso de control del HLD | 6 demandas 1,92 / 1,60 / 0,96 / 0,64 ×3 en 2 y 3 hosts de 3,4 CPU | Z = 2 en ambos | `test_control_hld_z2` |
| U2 | Línea base BFD peor que BCDP | Mismo caso | BFD da Z = 3 o sin plan | `test_bfd_peor_en_control` |
| U3 | Regresión | Instancias del generador (60/10, 120/20; holgura 1,5 / 1,2 / 1,0) | Plan en todas; Z medio de la guía | `test_regresion_guia` |
| U4 | Validador | Plan correcto / VM sin host / host excedido en cada dimensión | Pasa / falla / falla | `test_validador` |
| U5 | **Host con recursos suficientes (Linux)** | 3 VMs de 2 vCPU sin perfil de CPU en server1–3 (4 CPU c/u) | `PLAN_FOUND`, una VM por host (el 85 % de CPU real admite una sola de 2 vCPU) | `test_slice_referencia_sin_telemetria` |
| U6 | Consolidación con CPU prevista | 5 VMs de 1 vCPU con CPU prevista 0,40 | Todas en 1 host (`hosts_opened` = 1) | `test_consolida_con_cpu_prevista` |
| U7 | Prefiere hosts ocupados | Un host ya ocupado con hueco | El plan lo usa antes de abrir otro | `test_prefiere_host_ocupado` |
| U8 | VM fijada | VM con `host` | Respetada; si no cabe, rechazo con motivo | `test_vm_fijada` |
| U9 | **Zona de disponibilidad** (regla que usa OpenStack; igual en Linux) | Hosts en `z1` y `z2`; se pide `z1` | Solo hosts de `z1`; el de `z2` en `discarded_hosts`. Sin hosts sanos en `z1`: `HEURISTIC_NO_PLAN` «… en la zona z1» | `test_zona_salud_y_telemetria` |
| U10 | Salud y telemetría | Host caído y host con telemetría de 60 s | Descartados con su motivo | `test_zona_salud_y_telemetria` |
| U11 | **Ningún host cumple** | 4 VMs de 2 vCPU en 3 hosts; 3 VMs en un host con tope de 2 vCPU | `HEURISTIC_NO_PLAN` con el motivo («recurso más ajustado: CPU real», «vCPU insuficiente») | `test_slice_referencia_sin_telemetria`, `test_tope_de_vcpu` |
| U12 | Tiempo límite | Instancia grande con límite mínimo | `PLANNING_TIMEOUT` | `test_timeout` |
| U13 | Determinismo | Misma solicitud dos veces | Mismo plan | `test_determinista` |
| U14 | Seguridad de la API | Sin token / token inválido | 401 | `test_requiere_token` |
| U15 | Contrato HTTP | Petición válida; petición con un ID de VM repetido | 200 con plan (respeta la VM fijada) / 422 | `test_plan`, `test_valida_entrada` |

**Pruebas de integración con el Slice Manager** (`tests/app/test_slice_placement.py`) **[Implementado, en verde]**

| # | Caso | Esperado |
|---|---|---|
| I1 | El plan se escribe en la especificación | Cada VM con `host`; en OpenStack también `zone` (`test_plan_escribe_host_y_zona`) |
| I2 | Sin recursos | 409 con el motivo del placement (`test_sin_recursos_rechaza_con_motivo`) |
| I3 | Dos slices seguidos con telemetría vieja | El segundo ve el compromiso del primero (`test_registro_de_planes_recientes_evita_doble_asignacion`) |
| I4 | La reserva pierde la carrera | Se vuelve a planificar (`test_reintenta_si_la_reserva_fallo_por_capacidad`) |
| I5 | VM fijada por el usuario | Se respeta (`test_vm_fijada_por_el_usuario`) |
| I6 | Monitoreo caído o especificación incompleta | 503 / 422 sin desplegar (`test_monitoreo_caido_o_spec_incompleta`) |

**Pruebas del driver OpenStack** (`tests/test_openstack_driver.py`, con un OpenStack falso):
`test_placement_host_and_zone_force_the_compute` comprueba que el servidor se crea con
`availability_zone="zona-a:worker2"` y queda en ese host, y que pedir zona sin host se rechaza;
`test_hypervisors_inventory_with_zones` comprueba que las zonas se leen de los agregados.

**Selección automática de plataforma** (`tests/app/test_slice_placement.py`, clase `AutoProvider`)
**[Implementado, en verde]**

| # | Entrada (`provider: "auto"`) | Esperado | Test |
|---|---|---|---|
| A1 | Linux sin RAM libre; OpenStack con capacidad | Elige OpenStack; cada VM con `host` worker y `zone`; Linux en `rejected` | `test_a1_elige_el_unico_proveedor_con_capacidad` |
| A2 | Linux tendría que ocupar un servidor vacío (Z = 1); OpenStack tiene uno ya ocupado con hueco (Z = 0) | Elige OpenStack, `hosts_opened` = 0; candidatos `{openstack: 0, linux: 1}` | `test_a2_elige_el_que_abre_menos_hosts_nuevos` |
| A3 | Ambos con el mismo Z | Desempate: Linux (sin `zone` de Nova en la spec) | `test_a3_empate_prefiere_linux` |
| A4 | Ninguno con plan | 409 con el motivo de `linux:` y de `openstack:` | `test_a4_ninguno_puede_rechaza_con_el_motivo_de_cada_uno` |
| A5 | El platform-manager rechaza la spec en Linux (imagen no admitida) | Prueba OpenStack y lo despliega allí; el motivo queda en `rejected` | `test_a5_si_la_plataforma_rechaza_la_spec_prueba_la_siguiente` |
| A6 | Una VM fijada en `worker1`; y una reserva que pierde la carrera | Elige OpenStack; con la carrera perdida vuelve a planificar (`attempts` = 2) | `test_vm_fijada_decide_la_plataforma_y_carrera_perdida_replanifica` |

El compilador de topologías acepta `auto` y valida las VMs fijadas contra los servidores de ambos clústeres
(`tests/app/test_topology.py`).

**Demostración en ambos entornos [Probado en el clúster, MS-17]:**

| Clúster | Slice | Plan | Comprobación independiente |
|---|---|---|---|
| OpenStack | 3 VMs CirrOS (1 vCPU, 512 MB, 1 GB) | `PLAN_FOUND`, 0,6 ms, vm1–3 → worker1 (consolida) | Nova `OS-EXT-SRV-ATTR:host` = worker1 en las 3 |
| Linux | 3 VMs CirrOS | `PLAN_FOUND`, 0,3 ms, vm1–3 → server3 | Procesos `qemu-system-x86_64` solo en server3; `allocations` coincide |

Criterio de aceptación del módulo: todas las pruebas U, I y del driver en verde; en el clúster, el host de cada VM
coincide con el plan en ambos backends; ningún slice sin plan deja recursos creados.

---

## Limitaciones y pendientes declarados

- Zonas reales: el clúster tiene solo `nova` (OpenStack) y `linux`; crear agregados con zona requiere al JP.
- Selección automática de plataforma: implementada y probada con tests (A1–A6); falta probarla en el clúster real.
- Perfil P99 de CPU por tipo de VM: diseño; hoy demanda completa sin perfil.
- Disco en Linux: con reserva completa, una VM Ubuntu de 4 GB no cabe en servidores con ≈ 6,5 GB libres; se
  evalúa aprovisionamiento delgado o ampliar disco (consulta al JP).
- Sin migración en vivo: la consolidación ocurre solo al admitir.
