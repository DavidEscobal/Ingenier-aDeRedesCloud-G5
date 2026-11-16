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

![Diagrama de flujo del módulo de VM Placement](diagramas/flujo_vm_placement.png)

*Versión vectorial para ampliar: [`diagramas/flujo_vm_placement.svg`](diagramas/flujo_vm_placement.svg).*

**Cómo leer el diagrama:**

- **Símbolos:** óvalos para el inicio y el fin, un paralelogramo para la entrada, rectángulos para los procesos,
  rombos para las decisiones y círculos «A» como conectores.
- **Colores:** cada color indica qué componente del orquestador hace el paso (ver la leyenda).
- **Camino central (hacia abajo):** el slice que sí se despliega.
- **Columna de la derecha:** todos los rechazos. Terminan en un mismo fin donde el usuario recibe el motivo, sin
  recursos creados.
- **Línea de la izquierda:** el reintento cuando otra solicitud ocupó el espacio entre el cálculo y la reserva
  (máximo 3 intentos).
- **Recuadro punteado:** cómo se aplica el mismo flujo en modo automático.

### g) Plan de pruebas (unit testing)

#### Cómo se prueba el módulo

El módulo de VM Placement se prueba como una **caja negra**. Se le da una entrada, se lee su salida y se compara
con la salida esperada, escrita de antemano:

- **Entrada:**
  - la lista de servidores, cada uno con su capacidad (núcleos, RAM, disco), lo que ya tiene en uso, su zona y si
    está sano;
  - la lista de VMs del slice, con sus vCPU, RAM y disco;
  - opcionalmente, la zona pedida y la plataforma (Linux, OpenStack o automático).
- **Salida:**
  - un **plan** que indica a qué servidor va cada VM (por ejemplo, «vm1 → server2»); o
  - un **rechazo** con el motivo (por ejemplo, «no hay servidores candidatos en la zona z1»).

Cada caso usa escenarios pequeños e inventados, armados para que la respuesta correcta se pueda calcular a mano. Las
pruebas automáticas no tocan el clúster real, así que siempre dan el mismo resultado. Al final se demuestra el
módulo en los dos clústeres reales (casos VP-10 a VP-12).

**Datos de referencia de los escenarios** (salvo que el caso indique otros valores):

- **Servidor estándar:** 4 núcleos, 2,75 GB de RAM y 5 GB de disco.
- **VM estándar:** 1 vCPU, 512 MB de RAM y 1 GB de disco.

**Reglas que el módulo debe respetar:**

- La CPU realmente usada en un servidor no puede pasar del **85 %** de sus núcleos (3,4 de 4 núcleos).
- Se pueden asignar hasta **2 vCPU por núcleo**.
- La RAM y el disco no se sobreasignan.
- Si no se sabe cuánto usará una VM, se supone que usará todas sus vCPU.

**Resultados obtenidos:**

- **VP-01 a VP-09:** se ejecutaron el **16/11/2026** con 37 pruebas automáticas, todas aprobadas. La salida de la
  ejecución está en [`evidencias/ejecucion_pruebas_vm_placement.txt`](evidencias/ejecucion_pruebas_vm_placement.txt).
- **VP-10 a VP-12:** se hicieron en los clústeres reales el 15/11/2026.

**Leyenda de resultados:**

- **PASS:** los resultados obtenidos son iguales a los esperados.
- **FAIL:** los resultados obtenidos no son iguales a los esperados.
- **NT:** la prueba no se realizó.

#### Resumen

| Caso | Nombre | Tipo | Resultado |
|---|---|---|---|
| VP-01 | Selección de servidores con recursos suficientes en Linux | Unitaria | PASS |
| VP-02 | Restricción de zona de disponibilidad | Unitaria | PASS |
| VP-03 | Traducción de la decisión a OpenStack (zona:host) | Integración | PASS |
| VP-04 | Ningún servidor cumple con los recursos pedidos | Unitaria / Integración | PASS |
| VP-05 | Selección automática de plataforma | Unitaria / Integración | PASS |
| VP-06 | Calidad del algoritmo frente a la alternativa clásica | Unitaria | PASS |
| VP-07 | Robustez: verificador, tiempo límite y resultado repetible | Unitaria | PASS |
| VP-08 | Seguridad y entradas inválidas | Unitaria | PASS |
| VP-09 | El módulo dentro del orquestador | Integración | PASS |
| VP-10 | Demostración en el clúster OpenStack | Funcional | PASS |
| VP-11 | Demostración en el clúster Linux | Funcional | PASS |
| VP-12 | Modo automático en los clústeres reales | Funcional | PASS |

#### VP-01 · Selección de servidores con recursos suficientes en Linux

| Campo | Detalle |
|---|---|
| **Número de caso** | VP-01 |
| **Tipo de prueba** | Unitaria |
| **Objetivos** | Verificar que el módulo elige servidores Linux con CPU y RAM suficientes, sin saturar ninguno, y que aprovecha bien los servidores. |
| **Prerrequisitos** | • Código del orquestador con las dependencias instaladas.<br>• No se necesita acceso al clúster. |
| **Procedimiento** | 1. Escenario A: 3 servidores estándar vacíos y 3 VMs de 2 vCPU cada una.<br>2. Escenario B: los mismos servidores y 5 VMs de 1 vCPU que usan el 40 % de su CPU.<br>3. Escenario C: server1 vacío y server2 ya ocupado con espacio libre; llega 1 VM.<br>4. Escenario D: el usuario fija vm1 en server2; vm2 no está fijada.<br>5. Pedir el plan al módulo en cada escenario y compararlo con el esperado. |
| **Resultados esperados** | • A: **una VM por servidor**. Dos VMs de 2 vCPU sumarían 4 CPU, más que el límite de 3,4.<br>• B: **las 5 VMs en un solo servidor**, porque consumen poco.<br>• C: **vm1 → server2**; no se ocupa ningún servidor vacío.<br>• D: **vm1 → server2**, como pidió el usuario, y vm2 también va a server2. |
| **Resultados obtenidos** | **PASS**. Los cuatro escenarios dieron exactamente el plan esperado. |
| **Evidencias** | Salida de la ejecución de las pruebas automáticas. |
| **Comentarios y/o observaciones** | El escenario A también muestra la regla del 85 %: con 4 VMs de 2 vCPU el slice ya no cabe (ver VP-04). |

#### VP-02 · Restricción de zona de disponibilidad

| Campo | Detalle |
|---|---|
| **Número de caso** | VP-02 |
| **Tipo de prueba** | Unitaria |
| **Objetivos** | Verificar que el módulo solo considera servidores de la zona pedida, sanos y con información actualizada, y que explica por qué descarta los demás. |
| **Prerrequisitos** | • Igual que VP-01. |
| **Procedimiento** | 1. Preparar 4 servidores:<br>   • server1 en la zona z2;<br>   • server2 caído;<br>   • server3 con datos de monitoreo de hace 40 s;<br>   • server4 sano y al día en z1.<br>2. Pedir un plan para 1 VM en la **zona z1**.<br>3. Repetir sin server4. |
| **Resultados esperados** | • Paso 2: **vm1 → server4**. Los otros tres servidores aparecen como descartados, cada uno con su motivo: «fuera de la zona z1», «host no saludable o en mantenimiento» y «telemetría vencida (40 s)».<br>• Paso 3: **rechazo** «no hay servidores candidatos en la zona z1». La VM no se coloca en otra zona. |
| **Resultados obtenidos** | **PASS**. |
| **Evidencias** | Salida de la ejecución de las pruebas automáticas. |
| **Comentarios y/o observaciones** | La misma regla de zonas se aplica en Linux y en OpenStack. En el clúster real solo existe la zona `nova` de OpenStack (ver Limitaciones). |

#### VP-03 · Traducción de la decisión a OpenStack (zona:host)

| Campo | Detalle |
|---|---|
| **Número de caso** | VP-03 |
| **Tipo de prueba** | Integración (con un OpenStack simulado) |
| **Objetivos** | Verificar que la decisión del módulo («VM → compute, zona») se convierte correctamente en la orden que entiende OpenStack, y que cada VM queda en el compute elegido. |
| **Prerrequisitos** | • Igual que VP-01.<br>• Se usa un OpenStack simulado que responde como Nova y Neutron. |
| **Procedimiento** | 1. Crear un slice de 3 VMs con esta decisión:<br>   • vm1 → worker2 en zona-a;<br>   • vm2 → worker3 en la zona por defecto;<br>   • vm3 sin decisión.<br>2. Revisar la orden enviada a OpenStack para cada VM y el compute donde quedó.<br>3. Enviar una VM con zona pero sin compute. |
| **Resultados esperados** | • vm1 se crea con `availability_zone = "zona-a:worker2"` y queda en worker2.<br>• vm2 se crea con `"nova:worker3"` y queda en worker3.<br>• vm3 no lleva zona; la ubica OpenStack.<br>• La VM del paso 3 se **rechaza** antes de enviarla. |
| **Resultados obtenidos** | **PASS**. |
| **Evidencias** | Salida de la ejecución de las pruebas automáticas. |
| **Comentarios y/o observaciones** | El mismo mecanismo se comprobó en el clúster real en VP-10. |

#### VP-04 · Ningún servidor cumple con los recursos pedidos

| Campo | Detalle |
|---|---|
| **Número de caso** | VP-04 |
| **Tipo de prueba** | Unitaria e integración |
| **Objetivos** | Verificar que, cuando el slice no cabe, el módulo lo rechaza completo, indica qué recurso falta y no deja nada creado. |
| **Prerrequisitos** | • Igual que VP-01. |
| **Procedimiento** | 1. Pedir un plan para 4 VMs de 2 vCPU en 3 servidores estándar.<br>2. Fijar en server1 una VM que pide 9999 MB de RAM.<br>3. Usar un servidor que admite como máximo 2 vCPU con 3 VMs de 1 vCPU.<br>4. Fijar una VM en un servidor que no existe (server9).<br>5. A través del orquestador completo, crear un slice que no cabe en ningún servidor. |
| **Resultados esperados** | 1. Rechazo: «recurso más ajustado: CPU real».<br>2. Rechazo: «no cabe (RAM)».<br>3. Rechazo: «vCPU insuficiente».<br>4. Rechazo.<br>5. El usuario recibe un error con el motivo, la solicitud **no llega a la plataforma** y no se crea ninguna VM. |
| **Resultados obtenidos** | **PASS**. |
| **Evidencias** | Salida de la ejecución de las pruebas automáticas. |
| **Comentarios y/o observaciones** | Un slice nunca se despliega a medias: o caben todas sus VMs o no se crea ninguna. |

#### VP-05 · Selección automática de plataforma

| Campo | Detalle |
|---|---|
| **Número de caso** | VP-05 |
| **Tipo de prueba** | Unitaria e integración |
| **Objetivos** | Verificar que, cuando la entrada indica plataforma «automático», el módulo elige bien entre Linux y OpenStack. Regla: se elige la que ocupa menos servidores vacíos; en caso de empate, Linux. |
| **Prerrequisitos** | • Igual que VP-01.<br>• Se simulan ambos clústeres. |
| **Procedimiento** | Pedir un slice en modo automático en cada situación:<br>1. Linux sin RAM libre; OpenStack con espacio.<br>2. Linux tendría que ocupar un servidor vacío; en OpenStack cabe en uno que ya está en uso.<br>3. Ambas plataformas necesitan lo mismo.<br>4. Ninguna de las dos tiene capacidad.<br>5. Linux tiene espacio pero no admite la imagen pedida.<br>6. El usuario fijó una VM en worker1, que es un compute de OpenStack.<br>7. Otro slice ocupa el espacio entre el cálculo y la reserva. |
| **Resultados esperados** | 1. OpenStack; Linux queda descartado con su motivo.<br>2. OpenStack (0 servidores nuevos frente a 1).<br>3. Linux, por la regla de empate.<br>4. Rechazo con el motivo de cada plataforma.<br>5. Se intenta Linux, se recibe su rechazo y se despliega en OpenStack.<br>6. OpenStack, porque la VM fijada determina la plataforma.<br>7. Se vuelve a calcular el plan (2.º intento) en lugar de fallar. |
| **Resultados obtenidos** | **PASS** en las 7 situaciones. |
| **Evidencias** | Salida de la ejecución de las pruebas automáticas. |
| **Comentarios y/o observaciones** | El caso 5 también se reprodujo en el clúster real (VP-12). |

#### VP-06 · Calidad del algoritmo frente a la alternativa clásica

| Campo | Detalle |
|---|---|
| **Número de caso** | VP-06 |
| **Tipo de prueba** | Unitaria |
| **Objetivos** | Verificar que el algoritmo elegido (BCDP v2) aprovecha mejor los servidores que el clásico *Best Fit Decreasing* (BFD) y que un cambio futuro en el código no empeora sus resultados. |
| **Prerrequisitos** | • Igual que VP-01. |
| **Procedimiento** | 1. **Caso de control:** 6 VMs que consumen 1,92 / 1,60 / 0,96 / 0,64 / 0,64 / 0,64 núcleos, en 2 y en 3 servidores con 3,4 núcleos útiles. Resolverlo con BCDP v2 y con BFD.<br>2. **Escenarios grandes:** 60 VMs en 10 servidores y 120 VMs en 20 servidores, con 10 variantes aleatorias de cada uno y distintos márgenes de capacidad. |
| **Resultados esperados** | • Paso 1: BCDP v2 usa **2 servidores**; BFD usa 3 o no encuentra plan.<br>• Paso 2: hay plan en todas las variantes y el promedio de servidores usados coincide con el valor de referencia obtenido al diseñar el algoritmo. |
| **Resultados obtenidos** | **PASS**. |
| **Evidencias** | Salida de la ejecución de las pruebas automáticas. |
| **Comentarios y/o observaciones** | Usar menos servidores deja más capacidad libre para los slices siguientes. |

#### VP-07 · Robustez: verificador, tiempo límite y resultado repetible

| Campo | Detalle |
|---|---|
| **Número de caso** | VP-07 |
| **Tipo de prueba** | Unitaria |
| **Objetivos** | Verificar que un plan incorrecto nunca llega al clúster, que el módulo responde a tiempo y que sus decisiones se pueden reproducir. |
| **Prerrequisitos** | • Igual que VP-01. |
| **Procedimiento** | 1. Dar al verificador independiente tres planes: uno correcto, uno con una VM sin servidor y uno que excede la capacidad de un servidor.<br>2. Pedir un plan para 1500 VMs y 200 servidores con un límite de 0,05 s.<br>3. Hacer la misma solicitud dos veces. |
| **Resultados esperados** | 1. Correcto / incorrecto / incorrecto.<br>2. Rechazo por **tiempo agotado**, con respuesta en menos de 2 s.<br>3. Exactamente el mismo plan las dos veces. |
| **Resultados obtenidos** | **PASS**. |
| **Evidencias** | Salida de la ejecución de las pruebas automáticas. |
| **Comentarios y/o observaciones** | En operación normal el límite es 1 s. En el clúster real, los planes se calcularon en menos de 1 ms (VP-10 y VP-11). |

#### VP-08 · Seguridad y entradas inválidas

| Campo | Detalle |
|---|---|
| **Número de caso** | VP-08 |
| **Tipo de prueba** | Unitaria |
| **Objetivos** | Verificar que solo los componentes autorizados del orquestador pueden pedir un plan y que las entradas mal formadas se rechazan antes de calcular. |
| **Prerrequisitos** | • Igual que VP-01. |
| **Procedimiento** | 1. Pedir un plan sin credencial y con una credencial falsa.<br>2. Pedir un plan con credencial válida y una VM fijada.<br>3. Pedir un plan con dos VMs con el mismo nombre. |
| **Resultados esperados** | 1. Acceso denegado.<br>2. Plan encontrado, respetando la VM fijada.<br>3. Solicitud rechazada por datos inválidos. |
| **Resultados obtenidos** | **PASS**. |
| **Evidencias** | Salida de la ejecución de las pruebas automáticas. |
| **Comentarios y/o observaciones** | — |

#### VP-09 · El módulo dentro del orquestador

| Campo | Detalle |
|---|---|
| **Número de caso** | VP-09 |
| **Tipo de prueba** | Integración |
| **Objetivos** | Verificar que el plan llega correctamente al despliegue y que el orquestador se comporta bien en situaciones de concurrencia y de falla. |
| **Prerrequisitos** | • Igual que VP-01.<br>• Se simulan el monitoreo y la plataforma. |
| **Procedimiento** | 1. Crear un slice y revisar lo que se envía a desplegar.<br>2. Crear dos slices seguidos antes de que el monitoreo registre el primero.<br>3. Simular que la reserva falla porque otro slice ocupó el espacio.<br>4. Simular que el monitoreo no responde. |
| **Resultados esperados** | 1. Cada VM va con el servidor del plan y, en OpenStack, también con la zona.<br>2. El segundo slice tiene en cuenta lo asignado al primero; no se asigna dos veces el mismo espacio.<br>3. Se vuelve a calcular el plan y se reintenta.<br>4. El orquestador avisa que el servicio no está disponible y no despliega sin información. |
| **Resultados obtenidos** | **PASS**. |
| **Evidencias** | Salida de la ejecución de las pruebas automáticas. |
| **Comentarios y/o observaciones** | — |

#### VP-10 · Demostración en el clúster OpenStack

| Campo | Detalle |
|---|---|
| **Número de caso** | VP-10 |
| **Tipo de prueba** | Funcional / Integración (clúster real) |
| **Objetivos** | Demostrar que, en OpenStack, las VMs quedan en el compute que decidió el módulo. |
| **Prerrequisitos** | • Orquestador desplegado en el app server.<br>• Sesión iniciada en la interfaz web.<br>• Acceso de solo lectura a OpenStack para verificar. |
| **Procedimiento** | 1. Ingresar al sistema.<br>2. Crear un slice de 3 VMs CirrOS (1 vCPU, 512 MB, 1 GB) en OpenStack.<br>3. Anotar el plan que devuelve el módulo.<br>4. Consultar a OpenStack en qué compute quedó cada VM (atributo *host* de la instancia).<br>5. Borrar el slice. |
| **Resultados esperados** | • Plan encontrado.<br>• El compute que informa OpenStack para cada VM coincide con el plan.<br>• Las instancias quedan en estado ACTIVE. |
| **Resultados obtenidos** | **PASS** (15/11/2026). El plan se calculó en 0,6 ms y puso vm1–vm3 en worker1, consolidando en un solo compute. OpenStack informó worker1 para las 3 VMs. |
| **Evidencias** | Registro de la prueba en el clúster (evidencia MS-17 del proyecto) con la respuesta del módulo y la consulta a OpenStack. |
| **Comentarios y/o observaciones** | El slice se borró en 15 s. |

#### VP-11 · Demostración en el clúster Linux

| Campo | Detalle |
|---|---|
| **Número de caso** | VP-11 |
| **Tipo de prueba** | Funcional / Integración (clúster real) |
| **Objetivos** | Demostrar que, en el clúster Linux, las VMs se ejecutan en el servidor que decidió el módulo. |
| **Prerrequisitos** | • Igual que VP-10.<br>• Agentes del orquestador activos en los servidores Linux. |
| **Procedimiento** | 1. Ingresar al sistema.<br>2. Crear un slice de 3 VMs CirrOS en Linux.<br>3. Anotar el plan.<br>4. Revisar en cada servidor qué procesos de VM (`qemu-system-x86_64`) están corriendo.<br>5. Borrar el slice. |
| **Resultados esperados** | • Plan encontrado.<br>• Los procesos de las 3 VMs corren solo en el servidor del plan.<br>• Las reservas del orquestador coinciden con el plan. |
| **Resultados obtenidos** | **PASS** (15/11/2026). El plan se calculó en 0,3 ms y puso vm1–vm3 en server3. Los procesos de las 3 VMs corrían solo en server3. |
| **Evidencias** | Registro de la prueba en el clúster (evidencia MS-17 del proyecto). |
| **Comentarios y/o observaciones** | — |

#### VP-12 · Modo automático en los clústeres reales

| Campo | Detalle |
|---|---|
| **Número de caso** | VP-12 |
| **Tipo de prueba** | Funcional / Integración (clúster real) |
| **Objetivos** | Demostrar que, en modo automático, el orquestador decide la plataforma con los clústeres reales y que pasa a la otra si la elegida rechaza la solicitud. |
| **Prerrequisitos** | • Igual que VP-10. |
| **Procedimiento** | 1. Crear un slice CirrOS con plataforma «automático», con una red que el clúster Linux no admite.<br>2. Revisar qué plataforma eligió el módulo, el motivo del rechazo y dónde quedó el slice. |
| **Resultados esperados** | • Linux rechaza la solicitud e indica el motivo.<br>• El orquestador despliega el slice en OpenStack sin intervención del usuario. |
| **Resultados obtenidos** | **PASS** (15/11/2026). Linux ganó el desempate, pero rechazó la red privada pedida. El slice se desplegó en OpenStack. |
| **Evidencias** | Registro de la prueba en el clúster (evidencia MS-20 del proyecto). |
| **Comentarios y/o observaciones** | Corresponde a la situación 5 de VP-05, ahora con los clústeres reales. |

#### Criterio de aceptación del módulo

El módulo se considera validado si se cumplen las tres condiciones:

- los casos VP-01 a VP-09 dan PASS;
- en ambos clústeres reales, cada VM queda en el servidor que indicó el plan (VP-10 a VP-12);
- ningún slice rechazado deja recursos creados.

**Estado al 16/11/2026: los 12 casos en PASS.**

---

## Limitaciones y pendientes declarados

- Zonas reales: el clúster tiene solo `nova` (OpenStack) y `linux`; crear agregados con zona requiere al JP.
- Selección automática de plataforma: implementada, con pruebas automáticas (VP-05) y probada en los clústeres reales (VP-12).
- Perfil P99 de CPU por tipo de VM: diseño; hoy demanda completa sin perfil.
- Disco en Linux: con reserva completa, una VM Ubuntu de 4 GB no cabe en servidores con ≈ 6,5 GB libres; se
  evalúa aprovisionamiento delgado o ampliar disco (consulta al JP).
- Sin migración en vivo: la consolidación ocurre solo al admitir.
