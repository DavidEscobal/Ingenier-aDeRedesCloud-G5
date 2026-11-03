# PUCP PRIVATE CLOUD ORCHESTRATOR

**Pontificia Universidad Católica del Perú — Facultad de Ciencias e Ingeniería**  
**Curso:** Ingeniería de Redes Cloud  
**Lugar y fecha del documento:** Lima, Perú | Octubre, 2026

![Escudo de la Pontificia Universidad Católica del Perú](media/image4.jpg)

**Integrantes (según el documento):**

- Cris David Escobal Huayana
- Christian Luis Gonzales Fernández
- Edgar Diaz Zevillanos
- Cesar Fabricio Tirado Vera

**Coach:** Fernando Williams Guzman Coras  
**Profesor:** Rubén Francisco Córdova Alvarado

---

> **Nota de conversión:** transcripción estructurada del documento Word *G5_Documentacion_Ex1_actualizada_Fase2(2).docx* (74 páginas). Se conserva el contenido técnico y sus imágenes; se adaptan las tablas y títulos a Markdown. Las figuras se guardan en `media/` y los números de página corresponden al archivo original. La sección 6 distingue las capacidades implementadas, los resultados históricos y el diseño pendiente.

## Guía de navegación (estructura original)

- **1. Resumen**
- **2. Introducción**
- **3. Arquitectura general del sistema**
- **4. Diseño de alto nivel (HLD)**
- **5. Flujos integrados del sistema**
- **6. Implementación y estado de integración**

Los encabezados internos conservan su numeración original. Los diagramas de los flujos F1–F10 están en la carpeta `media/` y las tablas de pasos se mantienen como texto. Las fórmulas ilustradas cuentan además con una transcripción accesible.

---

# 1. Resumen

## 1.1 Descripción general del proyecto

El PUCP Private Cloud Orchestrator automatiza el ciclo de vida de slices: conjuntos de máquinas virtuales, interfaces y redes de laboratorio. La fase 2 utiliza una topología grupal compartida por el proyecto y los laboratorios, con un clúster Linux y otro OpenStack. La arquitectura conserva módulos de interacción, seguridad, planificación y ejecución para gestionar ambos proveedores con una misma intención de servicio. La base de código entregada implementa la ruta Linux mediante QEMU/KVM, OVS y agentes SSH; el laboratorio ya aporta una plataforma OpenStack y dos instancias registradas. La integración del driver OpenStack y la heurística propia de VM Placement se especifican en este documento como trabajo de fase 2, sin equipararlas a funciones ya implementadas.

## 1.2 Objetivo de la solución

El objetivo es gestionar de manera centralizada slices sobre los clústeres Linux y OpenStack, con aislamiento, acceso autorizado y asignación de recursos verificable. La interfaz recibe la topología; Slice Manager coordina su admisión; VM Placement propone destinos; Networking e IMS preparan red e imágenes; PlatManager ejecuta mediante el driver del proveedor. El plan concreta la solicitud en recursos, identificadores, dependencias y operaciones de API o de agente, y verifica sus resultados. Se consideran concurrencia, persistencia, trazabilidad y uso real de recursos además de su asignación nominal.

## 1.3 Alcance de la implementación.

La documentación conserva la arquitectura y el prototipo R2 de EX1 e incorpora el diseño de fase 2: soporte OpenStack (R3), VM Placement (R4), evolución de la interfaz (R1B) y networking y seguridad (R5) para ambos clústeres. El estado se distingue en tres niveles: código presente en el ZIP, resultados históricos registrados en el contexto LAB5 y capacidades definidas para desarrollar. La existencia de servicios OpenStack no demuestra su integración en G5. AWS y la alta disponibilidad distribuida permanecen como extensiones de arquitectura.

Por tanto, el alcance de esta entrega comprende:

- La arquitectura general de la plataforma.

- El diseño de alto nivel de R1, R1B, R1C, R2, R3, R4 y R5.

- La base Linux implementada y la integración proyectada de OpenStack.

- La gestión del ciclo de vida de los slices.

- La gestión de las máquinas virtuales y sus conexiones de red.

- La definición de autenticación, autorización, concurrencia, reservas, monitoreo y decisiones de placement basadas en asignaciones y demanda prevista.

- La integración de los módulos mediante una arquitectura modular y desacoplada.

# 2. Introducción

## 2.1. Contexto y problemática

La Pontificia Universidad Católica del Perú (PUCP) cuenta con un conjunto de servidores físicos DELL PowerEdge R630 que pueden ser utilizados como infraestructura para el despliegue de máquinas virtuales y diferentes topologías de red. Debido a la naturaleza académica del entorno, esta infraestructura puede ser utilizada por distintos cursos, grupos y sesiones de laboratorio que requieren disponer de recursos virtualizados de acuerdo con las actividades que realizan. El despliegue de estos entornos requiere realizar varias tareas, como crear máquinas virtuales, asignarles recursos de procesamiento y memoria, configurar sus conexiones de red, establecer la topología que deben utilizar y posteriormente liberar los recursos cuando dejan de ser necesarios. Cuando estas actividades se realizan de manera manual, el proceso se vuelve más complejo a medida que aumenta la cantidad de máquinas virtuales y usuarios. Esta situación puede generar problemas como errores durante la configuración, asignación incorrecta de recursos, dificultad para mantener un registro de las operaciones y una mayor carga de trabajo para el administrador de la infraestructura. El problema se vuelve aún más importante cuando varios usuarios necesitan realizar operaciones simultáneamente sobre un conjunto limitado de servidores. Además, el proyecto contempla trabajar con diferentes plataformas de infraestructura. La fase 1 utilizó Linux; la fase 2 dispone de una topología compartida con Linux y OpenStack. El prototipo Linux usa QEMU/KVM directamente y OVS; OpenStack administra cómputo y red mediante sus servicios. Debido a que cada plataforma posee sus propios mecanismos para administrar máquinas virtuales y redes, gestionar directamente cada infraestructura puede hacer que la administración sea más compleja. Por estas razones, se plantea la necesidad de contar con una solución que permita automatizar y centralizar la administración de los entornos virtuales, con menos tareas manuales y con una forma uniforme de gestionar los recursos disponibles. Esta necesidad da origen al PUCP Private Cloud Orchestrator.

## 2.2. Motivación de la solución

La principal motivación del proyecto es facilitar la utilización de la infraestructura de servidores mediante la automatización del ciclo de vida de los slices. Un slice representa un entorno virtual compuesto por máquinas virtuales y las conexiones de red necesarias para que estas puedan comunicarse entre sí. Desde la perspectiva del usuario, la intención es que pueda solicitar un slice sin tener que conocer todos los detalles relacionados con la infraestructura física donde finalmente serán desplegadas sus máquinas. Para conseguirlo, **se plantea una arquitectura que separa las diferentes responsabilidades del sistema**. Por ejemplo, una parte de la solución recibe las solicitudes del usuario, otra coordina las operaciones y otras se encargan de seleccionar los recursos y ejecutar las acciones sobre la infraestructura. Esta separación permite que las operaciones puedan ser gestionadas de manera más ordenada y que los diferentes componentes puedan evolucionar de forma independiente. También permite ocultar las diferencias existentes entre las plataformas de infraestructura, de modo que el usuario pueda trabajar con el concepto de slice sin tener que preocuparse por si este será desplegado sobre Linux y OpenStack. Otro aspecto importante es la necesidad de soportar varios usuarios y operaciones simultáneas. Por ello, la solución contempla mecanismos de concurrencia, persistencia del estado y registro de las operaciones, para que los recursos sean utilizados de forma controlada y que las acciones realizadas puedan ser posteriormente consultadas o diagnosticadas. En consecuencia, la solución no busca únicamente automatizar la creación de máquinas virtuales, sino proporcionar una forma centralizada y organizada de administrar todo el ciclo de vida de los entornos virtuales.

## 2.3. Objetivos del proyecto

### Objetivo general

Diseñar e implementar un orquestador de nube privada que gestione slices en Linux y OpenStack sobre la infraestructura grupal de fase 2, con una interfaz común, control de acceso y decisiones de recursos verificables.

### Objetivos específicos

- Gestionar el ciclo de vida de los slices, con funciones de creación, edición, visualización y eliminación.

- Diseñar una arquitectura modular en la que los diferentes requerimientos del sistema puedan ser gestionados mediante componentes independientes.

- Proporcionar una capa de adaptación que permita ocultar las diferencias entre las distintas plataformas de infraestructura.

- Implementar mecanismos de autenticación y autorización para controlar las operaciones que puede realizar cada usuario.

- Permitir el funcionamiento multiusuario y concurrente, sin conflictos durante la asignación de recursos.

- Seleccionar destinos dentro del clúster y zona solicitados mediante Best Fit Decreasing, sujeto a recursos reservados, uso real, demanda por franja horaria y límites de contención.

- Automatizar el despliegue y la eliminación de VMs y redes en Linux y OpenStack mediante adaptadores propios de cada plataforma.

- Proporcionar mecanismos de monitoreo, persistencia y registro que permitan conocer el estado de los recursos y realizar tareas de diagnóstico.

## 2.4. Alcance y limitaciones

La fase 2 mantiene ambos clústeres en la misma infraestructura de desarrollo utilizada por los laboratorios. Los avances del LAB5 se incorporan al proyecto, pero se verifica por separado la integración del software G5. La configuración 10.0.10.0/24 del ZIP y el rol de server4 como gateway pertenecen a la base de fase 1; no constituyen el inventario vigente de fase 2.

Linux utiliza QEMU/KVM, QCOW2, TAP y OVS en el prototipo; libvirt es una alternativa de administración contemplada en el HLD, no la ruta ejecutada por el agente adjunto. OpenStack aporta Keystone, Glance, Nova, Placement, Neutron ML2/OVS y Horizon. Su driver G5 debe persistir los identificadores y manejar el ciclo de vida mediante APIs nativas.

El alcance de la solución comprende:

- Gestión del ciclo de vida de los slices.

- Administración de máquinas virtuales y sus recursos.

- Configuración de topologías de red.

- Selección de servidores para el despliegue de las VMs.

- Gestión de usuarios y permisos.

- Manejo de solicitudes concurrentes.

- Persistencia del estado de los slices.

- Registro de operaciones para facilitar la trazabilidad y el diagnóstico.

- Despliegue de slices sobre Linux e integración de despliegue sobre OpenStack.

- Acceso a las máquinas virtuales mediante consola virtual.

- Configuración de networking y mecanismos de seguridad.

Como limitación, la solución depende de los recursos físicos disponibles en el clúster. Por lo tanto, la cantidad de máquinas virtuales que pueden desplegarse simultáneamente está condicionada por la capacidad de procesamiento, memoria, almacenamiento y recursos de red disponibles.

El driver OpenStack, el editor completo, VM Placement y la telemetría temporal requieren desarrollo e integración. La migración automática de VMs existentes no forma parte de esta versión del módulo de placement; las alertas generan recomendaciones. No se suman recursos libres de ambos clústeres para completar un mismo slice.

## 2.5 Concepto de operación

El funcionamiento del sistema puede entenderse a partir de una idea sencilla: el usuario solicita qué entorno virtual necesita y el orquestador se encarga de realizar las operaciones necesarias sobre la infraestructura. De manera general, el proceso comienza cuando el usuario se autentica en el sistema y realiza una solicitud, por ejemplo, crear un nuevo slice. La solicitud es recibida por el componente encargado de gestionar el ciclo de vida de los slices, que verifica que el usuario tenga los permisos necesarios y que la solicitud sea válida. Una vez validada, la operación se procesa de acuerdo con los recursos disponibles. El sistema determina dónde pueden desplegarse las máquinas virtuales y posteriormente utiliza el adaptador correspondiente para ejecutar las acciones sobre la infraestructura. En el caso del clúster Linux, estas acciones pueden involucrar la creación de máquinas virtuales mediante KVM/QEMU y libvirt, así como la configuración de las conexiones de red mediante Open vSwitch y VLANs. Finalmente, el sistema actualiza el estado del slice, registra la operación y proporciona al usuario la información necesaria para acceder y administrar los recursos que le fueron asignados.

Este mismo concepto permite realizar diferentes operaciones durante el ciclo de vida del slice, como crear, editar, consultar y eliminar recursos.

Además, la arquitectura considera que varias operaciones pueden ocurrir al mismo tiempo. Para ello se utilizan mecanismos de gestión de concurrencia que permiten ordenar las solicitudes y evitar conflictos durante la utilización de los recursos compartidos.

## 2.6. Usuarios del sistema

El sistema contempla diferentes tipos de usuarios, cada uno con un conjunto de permisos de acuerdo con sus responsabilidades. Esta separación permite controlar qué operaciones puede realizar cada usuario y evita que un usuario pueda acceder o modificar recursos que no le corresponden.

| **Actor**     | **Descripción**                                                                                    | **Principales permisos**                                                                                                                                                        |
|---------------|----------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Administrador | Responsable de la administración general de la plataforma y de la infraestructura.                 | Gestionar cuentas, roles y zonas; crear, asignar, editar y eliminar slices; consultar el estado y acceder a la consola de cualquier slice; monitorear los recursos.             |
| Profesor      | Usuario encargado de preparar y administrar los entornos virtuales utilizados en sus cursos.       | Crear y asignar slices de sus cursos; consultar su estado y consumo; editar o eliminar sus slices de acuerdo con las políticas establecidas; acceder a las consolas de sus VMs. |
| Alumno        | Usuario que utiliza los recursos que le fueron asignados para realizar sus actividades académicas. | Visualizar sus slices asignados; consultar su estado y consumo; acceder a las consolas de las VMs asignadas. No puede crear ni modificar slices.                                |
| Sistema       | Conjunto de procesos automáticos que ejecutan tareas internas del orquestador.                     | Validar autenticación y autorización, registrar operaciones, gestionar el despliegue y liberar recursos que ya no sean utilizados.                                              |

**Roles y permisos**

La distribución de permisos puede resumirse de la siguiente manera:

| **Acción**                       | **Administrador** | **Profesor**             | **Alumno**       |
|----------------------------------|-------------------|--------------------------|------------------|
| Gestionar cuentas, roles y zonas | Gestión global    | Sin acceso               | Sin acceso       |
| Crear y asignar slices           | Todos los slices  | Slices de sus cursos     | Sin creación     |
| Consultar estado y consola       | Todos los slices  | Slices a su cargo        | Slices asignados |
| Editar o eliminar slices         | Gestión global    | Según política del curso | Sin modificación |

La creación define el slice y sus recursos; la asignación vincula el entorno con usuarios o cursos autorizados. Ambas acciones se validan de forma independiente, aunque una interfaz pueda ofrecerlas dentro de un mismo flujo.

## 2.7 Casos de Uso

El orquestador está pensado para ser utilizado en diferentes actividades académicas que requieren disponer de entornos virtualizados. En lugar de construir manualmente cada laboratorio, el usuario puede solicitar un entorno compuesto por máquinas virtuales, redes y otros recursos necesarios para realizar la actividad.

Los principales casos de uso considerados son los siguientes:

| **Caso de uso**               | **Entorno solicitado**                         | **Aporte del orquestador**                                                                                                                                                                                                 |
|-------------------------------|------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| SDN y OpenFlow                | Controlador SDN, switches virtuales y hosts.   | Permite desplegar una topología aislada para cada curso o alumno, con separación de las redes de control y datos. Las configuraciones pueden reutilizarse mediante plantillas sin afectar otros slices.                    |
| Proveedor de red              | Routers y hosts de prueba.                     | Permite desplegar escenarios de interconexión para realizar prácticas de routing, configuración de protocolos y análisis de conectividad. La topología puede reproducirse mediante una configuración previamente definida. |
| Redes móviles 5G / NFV        | Core, gNodeB y usuarios simulados.             | Permite crear entornos independientes para desplegar funciones de red virtualizadas y usuarios simulados, con interfaces conectadas y los recursos necesarios asignados.                                                   |
| Ciberseguridad                | Atacante, firewall y objetivo.                 | Permite construir laboratorios aislados para realizar prácticas de seguridad, con los elementos del escenario conectados y las reglas de red correspondientes.                                                             |
| Cloud y sistemas distribuidos | Balanceador, servidores y base de datos.       | Permite desplegar entornos distribuidos compuestos por diferentes máquinas virtuales, con las conexiones necesarias entre sus componentes.                                                                                 |
| Machine Learning              | Notebook, entorno de entrenamiento y datasets. | Permite proporcionar un entorno virtual aislado con los recursos de cómputo, almacenamiento y red necesarios para realizar actividades de Machine Learning.                                                                |

# 3. Arquitectura general del sistema

## 3.1. Visión general de la arquitectura

El PUCP Private Cloud Orchestrator transforma solicitudes académicas en planes controlados de cómputo y red. La UI/CLI accede al API Gateway y a IAM; Slice Manager coordina Topology Manager, VM Placement, Networking e IMS. El plan contiene ubicaciones, recursos, dependencias y verificaciones y se entrega a la cola y a PlatManager. En fase 2, Linux y OpenStack son los proveedores del proyecto; AWS permanece como extensión. Esta vista describe responsabilidades lógicas: el ZIP agrupa varias de ellas en un prototipo local Linux y aún no implementa todos los servicios como procesos independientes.

![Arquitectura general del orquestador por cinco capas y servicios transversales](media/image15.png)

*Figura. Vista lógica actualizada del orquestador: cinco capas funcionales y servicios transversales. Elaboración propia a partir del HLD del Grupo 5.*

## 3.2. Principios de diseño

### Modularidad y responsabilidad única

Cada módulo atiende un dominio funcional identificable. IAM concentra identidad, usuarios, roles y asignaciones académicas; IMS administra el ciclo de vida de las imágenes; Slice Manager orquesta los slices y PlatManager ejecuta el plan. La separación permite modificar las políticas de un servicio sin reescribir los demás.

### Abstracción de proveedores

Los servicios de control producen un plan independiente del proveedor. El Driver Linux lo materializa en acciones cerradas del agente, como preparar overlays, conectar TAP a OVS y arrancar QEMU. El Driver OpenStack lo materializará en solicitudes a Nova, Neutron y Glance, con registro de los UUID devueltos y consulta de estados. Esta adaptación concreta recursos y dependencias; no consiste en sustituir mecánicamente un comando Linux por una llamada HTTP.

### Seguridad y mínimo privilegio

Las solicitudes pasan por el API Gateway y se someten a validación de autenticación y autorización. IAM administra identidades, roles, pertenencia a cursos y permisos sobre slices. Los drivers y el almacenamiento no se exponen directamente a usuarios finales; los accesos a consola requieren autorización sobre la VM concreta.

### Concurrencia y consistencia

El API Gateway y los servicios de aplicación deben atender varias solicitudes concurrentes. La cola desacopla operaciones prolongadas, pero no reemplaza los mecanismos de reserva: Slice Manager coordina la admisión y los estados y debe garantizar que dos peticiones no asignen simultáneamente los mismos recursos. VM Placement aporta propuestas de ubicación sujetas a verificación de capacidad y reservas.

### Recuperación, idempotencia y trazabilidad

PlatManager y los drivers deben registrar cada paso, su resultado y el identificador de operación; ante fallos, se requieren reintentos acotados, comprobación del estado real y acciones de compensación cuando sean seguras. Las acciones críticas deben diseñarse para evitar duplicados después de reintentos.

### Escalabilidad y observabilidad

La arquitectura admite conceptualmente varias instancias de servicios sin modificar las VMs desplegadas. Las métricas y eventos se recolectan por vías independientes del canal de aprovisionamiento para respaldar la supervisión, el troubleshooting y las futuras decisiones de VM Placement.

## 3.3. Capas de la arquitectura

La vista por capas es una agrupación lógica de responsabilidades. Las cinco capas no implican obligatoriamente cinco servidores diferentes; su despliegue físico depende de los recursos disponibles. Persistencia y monitoreo se representan como servicios transversales, no como una sexta capa.

**Capa 1 — Interacción**

Comprende a los usuarios y la UI/CLI. El administrador gestiona configuración y supervisión global; el profesor solicita y asigna slices dentro de sus cursos y cuotas; el alumno consulta y utiliza únicamente las VMs autorizadas. La interfaz permite consultar estados, topologías, métricas y accesos a consola de acuerdo con los permisos.

### Capa 2 — Entrada y seguridad

Incluye API Gateway e IAM Service. El Gateway recibe, valida preliminarmente y enruta solicitudes; IAM autentica usuarios, administra cuentas y roles, relaciona personas con cursos y laboratorios y registra cuotas. La autorización considera rol, curso, relación vigente con el slice y acción solicitada. Las cuotas describen límites asignados; su comprobación no sustituye la disponibilidad efectiva ni las reservas de infraestructura.

### Capa 3 — Control y planificación

Contiene Slice Manager como coordinador, Topology Manager para plantillas, VM Placement para destinos, Networking Service para conectividad y políticas, e IMS para catálogo, importación, disponibilidad, distribución y retención de imágenes. El Slice Manager integra dichas decisiones y genera un plan coherente, con dependencias y validaciones.

### Capa 4 — Ejecución y adaptación

La cola de operaciones transporta trabajos y resultados de forma asíncrona. PlatManager coordina la ejecución, verifica dependencias y delega en Driver Linux, Driver OpenStack o Driver AWS. El driver concreto realiza operaciones sobre la plataforma seleccionada y comunica resultados, fallos e identificadores de recursos.

### Capa 5 — Infraestructura

La capa de infraestructura agrupa los cuatro servers Linux elegibles según inventario y los tres workers OpenStack. Headnode aloja servicios de control OpenStack y se propone para el orquestador G5, sin contabilizarlo como compute de tenants. ovs1 y ovs2 pertenecen a la red. Linux ejecuta QEMU/KVM y OVS; OpenStack utiliza Nova Compute, su hipervisor y Neutron. AWS queda fuera de la implementación de fase 2.

### Servicios transversales — Persistencia y observabilidad

Persistencia SQL conserva usuarios, roles, cursos, plantillas, slices, cuotas, reservas y estado de operaciones; el repositorio físico de imágenes es distinto de SQL. Persistencia NoSQL puede almacenar eventos, registros e históricos. Monitoreo recoge CPU, RAM, disco y salud de VMs/workers para consultas y diagnóstico. Cada servicio debe acceder a los datos de su dominio de forma controlada.

## 3.4. Módulos principales y responsabilidades

| **Capa** | **Módulo**                     | **Responsabilidad Principal**                                                                                                           |
|----------|--------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------|
| 1        | UI/CLI                         | Solicitudes, seguimiento, gestión de slices autorizados, importación de imágenes y acceso a consola                                     |
| 2        | API Gateway                    | Punto lógico de entrada; validación preliminar, control de exposición, rutas y atención concurrente                                     |
| 2        | IAM Service                    | Autenticación y autorización; cuentas, roles, cursos, laboratorios, permisos y cuotas                                                   |
| 3        | Topology Manager               | Catálogo de plantillas, edición de modelos de topología e importación/exportación de plantillas.                                        |
| 3        | Slice Manager                  | Ciclo de vida, admisión, reservas, estados, dependencias y planificación global del slice.                                              |
| 3        | Networking Service             | Segmentación, IPAM, VLAN, conectividad L2/L3, seguridad y acceso externo selectivo.                                                     |
| 3        | VM Placement                   | Best Fit Decreasing por slice y zona; Calibración de Sobreasignación; ratios efectivos, uso real, demanda horaria y motivos de rechazo. |
| 3        | Image Management Service (IMS) | Catálogo, importación QCOW2, distribución, caché, uso de imágenes base y limpieza segura.                                               |
| 4        | Cola de operaciones            | Entrega asíncrona de comandos, resultados, estados y fallos.                                                                            |
| 4        | PlatManager                    | Ejecuta y verifica el plan, ordena tareas, gestiona fallos/reintentos y selecciona drivers                                              |
| 4        | Driver Linux                   | Ejecuta cómputo y red mediante QEMU/KVM, QCOW2, TAP, OVS y agentes SSH; libvirt es una opción del HLD.                                  |
| 4        | Driver OpenStack               | Integración de fase 2 con Keystone, Nova, Neutron y Glance; inventarios de Placement y verificación del host real.                      |
| 4        | Driver AWS                     | Adaptador de extensión futura, fuera del alcance de implementación de fase 2.                                                           |
| T        | Persistencia SQL               | Datos transaccionales de identidad, slice, topologías, capacidad, cuotas y estados.                                                     |
| T        | Persistencia NoSQL             | Eventos, logs e históricos de telemetría cuando se configure                                                                            |
| T        | Monitoreo                      | Recolección y consulta de métricas, estado y salud de infraestructura/VMs                                                               |

## 3.5. Comunicación entre módulos

Los mecanismos de comunicación se seleccionan según la naturaleza de la operación; las flechas del HLD representan responsabilidades de invocación y respuesta, no acceso irrestricto entre módulos.

**Control síncrono (REST/HTTPS)**

La UI/CLI accede mediante API Gateway. El Gateway consulta/valida los datos de identidad y autorización con IAM y dirige peticiones hacia el servicio responsable. Slice Manager solicita modelos de topología, alternativas de ubicación, plan de red y preparación de imágenes a sus servicios especializados. La comprobación final de cuotas y reservas es responsabilidad del flujo de admisión.

**Ejecución asíncrona (cola de operaciones)**

Una vez admitida la solicitud, Slice Manager publica operaciones planificadas. PlatManager organiza las dependencias y los drivers las ejecutan, y comunican progresos, errores y resultados. El Slice Manager registra la transición de estado del slice. La cola no impone por sí sola exclusión mutua: se requieren controles explícitos de concurrencia y reservas.

**Interacción de IMS con la ejecución**

Durante la planificación, IMS verifica la identidad, formato y disponibilidad de la imagen requerida por cada VM. Con el destino propuesto por VM Placement, coordina que la imagen base esté disponible en el worker. La transferencia, preparación de discos diferenciales y eliminación efectiva se ejecutan mediante el driver. Al eliminar una VM se retira su disco propio, pero la imagen base solo se limpia si ninguna dependencia activa la necesita y la política de retención lo permite.

**Monitoreo y auditoría**

El plano de infraestructura reporta métricas y eventos al servicio de monitoreo de forma separada de la cola de ejecución. Se conserva información asociada al slice_id, vm_id, worker_id y operación para permitir diagnóstico por slice. La autorización de consola virtual debe ser revisada por IAM y gestionada mediante acceso temporal y restringido.

**Acceso controlado a persistencia**

IAM administra los datos de identidad y asignaciones académicas; Topology Manager sus plantillas; Slice Manager los slices/estados; IMS el catálogo de imágenes. El acceso a SQL/NoSQL se realiza por dominios y con privilegios adecuados. Un servicio no debe modificar arbitrariamente los datos internos de otro.

## 3.6. Arquitectura física de despliegue

La distribución física de fase 2 diferencia usuario, App Server lógico, gateway, redes de administración, switches y cómputo de ambos clústeres. MGMT 1 es 192.168.201.0/24 para Linux y MGMT 2 es 192.168.202.0/24 para OpenStack. El diagrama de infraestructura distingue ambos planos de gestión, los trunks de datos y la red de control. Los roles del ZIP de fase 1 deben adaptarse mediante inventario, sin inferir equivalencias entre serverN y workerN.

**Equipo del usuario**

El navegador o cliente CLI presenta operaciones autorizadas y se comunica por HTTPS con el API Gateway. El acceso a consola se realiza mediante una sesión controlada; no implica exposición indiscriminada de puertos VNC de workers.

**Plano de control / App Server**

El App Server representa el alojamiento lógico de Gateway, IAM, Slice Manager, planificación, IMS, PlatManager, cola y persistencia. Se propone ubicar inicialmente G5 en headnode OpenStack, con una reserva para el consumo de control y sin crear allí VMs de tenants. Esta decisión de despliegue no convierte headnode en gateway Linux ni demuestra que G5 ya haya sido instalado en él.

**Administración Linux y headnode OpenStack**

Headnode/controller (192.168.202.1) administra OpenStack. La administración Linux accede a server1–server4 por su red de gestión; antes de migrar el prototipo se confirman IP, rol y conectividad de cada nodo. server4 Linux y headnode OpenStack son nodos distintos. Si un server Linux aloja servicios de control, sus reservas y consumo se descuentan de su capacidad elegible.

**Workers Linux**

Los servidores Linux ejecutan VMs mediante QEMU/KVM y recursos de red mediante OVS. Los workers OpenStack ejecutan Nova Compute y el hipervisor. El inventario registra clúster, zona, salud, CPUs visibles, memoria, almacenamiento e interfaces por nodo. Se comprueban cores, SMT y virtualización anidada; cuatro CPU visibles no acreditan cuatro cores físicos exclusivos.

### Inventario y accesos de fase 2

| **Clúster y nodo**        | **SSH externo** | **Rol y capacidad de referencia**                        |
|---------------------------|-----------------|----------------------------------------------------------|
| Linux server1–server3     | 5811–5813       | Cómputo elegible; 4 CPU visibles y 3.8 GiB RAM por nodo. |
| Linux server4             | 5814            | Cómputo elegible; 4 CPU visibles y 7.4 GiB RAM.          |
| Linux ovs1                | 5815            | Red; no se cuenta como capacidad de VMs.                 |
| OpenStack headnode        | 5821            | Control en 192.168.202.1; sin VMs de tenant.             |
| OpenStack worker1–worker3 | 5822–5824       | Cómputo en 192.168.202.2–4; 4 CPU y 3.8 GiB por nodo.    |
| OpenStack ovs2            | 5825            | Red; no se cuenta como capacidad de VMs.                 |

El gateway registrado para el acceso es 10.20.11.245. Los puertos SSH son de gestión, no cupos de VMs. Las capacidades son referencias del diseño de placement y deben contrastarse con inventario y ocupación actuales; la elegibilidad depende del rol y de la zona. El diagrama y la tabla de accesos provienen de Cambios Fase1 a Fase 2 (final) + Requerimientos a evaluar.pdf; las IP OpenStack proceden del contexto LAB5.

![Topología física grupal de fase 2: Linux y OpenStack](media/image21.png)

*Figura. Infraestructura grupal de fase 2: gestión, trunks de datos y red de control. Fuente: Cambios Fase1 a Fase 2 (final) + Requerimientos a evaluar.pdf, página 5.*

# 4. Diseño de alto nivel (HLD)

## 4.1 R1 — Control y gestión del ciclo de vida de slices

### 4.1.1 Propósito, alcance y arquitectura lógica

R1 establece la arquitectura modular encargada de recibir solicitudes, organizar el ciclo de vida de los slices y abstraer las distintas infraestructuras. El usuario interactúa únicamente con UI/CLI; API Gateway concentra el acceso HTTP; IAM aporta identidad y alcance académico; Slice Manager mantiene la intención y el estado lógico; PlatManager controla la ejecución a través de los drivers. La observabilidad y la persistencia operan de forma transversal.

![Flujo lógico R1: UI/CLI, Gateway, Slice Manager, cola, PlatManager y drivers](media/image16.png)

Figura Vista resumida del flujo arquitectónico de R1. Las conexiones no representan todos los contratos

Slice Manager conserva la intención y el ciclo de vida del slice; PlatManager recibe trabajos y selecciona el driver. En fase 2 se desarrolla la integración de Linux y OpenStack; AWS queda como extensión. El contrato superior mantiene una misma lógica de slices, pero cada driver conserva sus mecanismos de identificación, estado y compensación. La base EX1 implementa la rama Linux y no demuestra todavía las demás capacidades del HLD.

| Capa | Modulo | Responsabilidad de diseño | Limitación |
| --- | --- | --- | --- |
| Interacción | (UI/CLI) | Capturar intención, mostrar estado y abrir consolas autorizadas | No invoca drivers ni recibe credenciales del proveedor |
| Acceso | -Gateway -IAM | Validación de datos, autenticación, RBAC, roles, cursos y cuotas asignadas. | La autorización no supone disponibilidad de recursos. |
| Planificación | -Topology Manager. -Slice Manager. -Networking Service. -VM Placement. -IMS | Versionar topología; proponer redes, ubicaciones e imágenes; admitir recursos. | Topology Manager, Networking Service, VM Placement e IMS no crean directamente VMs. |
| Ejecución | -Cola -PlatManager -Drivers | Entregar comandos, ejecutar pasos ordenados, verificar resultados y reintentos. | Un acuse de cola no equivale a desplegado. |
| Infraestructura | Infraestructura Linux y OpenStack | Ejecutar VMs y redes en el proveedor elegido; AWS como extensión. | La plataforma OpenStack está documentada; su integración en G5 sigue pendiente. |
| Transversal | -SQL -NoSQL -Monitoreo | Estado transaccional, reservas, métricas, logs y auditoría. | Telemetría no arbitra ni confirma reservas. |


### 4.1.2 Modularidad y administración de infraestructura

La arquitectura **permite incorporar servidores mediante su registro en el inventario de workers**, la verificación de conectividad y la actualización de recursos disponibles para VM Placement. Para retirar un worker, este pasa al estado de mantenimiento (DRAINING), **lo que impide nuevas asignaciones**. Si contiene VMs activas, el retiro se posterga hasta su liberación o reubicación mediante mecanismos compatibles. De esta manera, el orquestador y los demás servidores operan sin interrupciones. Asimismo, los módulos pueden actualizarse independientemente mediante APIs versionadas y contratos compatibles. Para evitar detener el servicio durante una actualización, el diseño contempla réplicas y despliegues graduales y sustitución de instancias solo cuando las nuevas estén disponibles y verificadas.

### 4.1.3. Seguridad y aislamiento entre módulos

El API Gateway e IAM verifican la identidad, **los permisos y el acceso a cada slice y emiten un token JWT**. El API-gateway autoriza cada solicitud según el rol y el acceso al slice. Los servicios internos utilizan **conexiones protegidas y credenciales específicas**, mientras que los drivers y **la infraestructura permanecen inaccesibles directamente para los usuarios**. La arquitectura aplica el principio de mínimo privilegio y separa las redes de administración de las redes de los laboratorios. Esto limita los recursos a los que puede acceder cada componente y reduce el impacto de un posible compromiso de seguridad.

### 4.1.4 Escalabilidad y distribución de módulos

Los módulos pueden ejecutarse en máquinas diferentes y comunicarse mediante interfaces de red, sin depender de un único servidor de aplicaciones. El diseño contempla escalamiento horizontal independiente, mediante múltiples instancias de los servicios que experimenten mayor carga. Un balanceador distribuye las solicitudes entre réplicas disponibles, mientras que la persistencia compartida y el control de concurrencia mantienen la consistencia de las operaciones. Así, es posible ampliar la capacidad del API Gateway o de los ejecutores sin necesidad de incrementar todos los componentes del sistema.

### 4.1.5. Persistencia y recuperación del estado

La persistencia SQL conserva la configuración de los slices, sus recursos, propietarios, estados y operaciones. Esta información permite recuperarlos después de cerrar sesión o reiniciar un servicio. Para retomar una edición posteriormente, el diseño contempla guardar configuraciones como borradores persistentes, asociados a un usuario, un slice y una versión. Al regresar, el usuario recupera su último borrador y continúa con su modificación sin perder el trabajo anterior. Cuando se confirma una edición, Slice Manager valida la versión, los permisos y los recursos antes de actualizar la configuración almacenada. La edición posterior está definida en el HLD, aunque no forma parte de los endpoints implementados actualmente en EX1.

### 4.1.6 Concurrencia en la gestión de slices

La arquitectura permite atender múltiples usuarios mediante solicitudes independientes y una cola de operaciones. Para evitar conflictos de edición simultánea, cada slice mantiene un número de versión. Antes de guardar cambios, Slice Manager verifica que dicha versión siga vigente; si otro usuario modificó el slice, rechaza la actualización incompatible y solicita revisar los cambios. Para los despliegues concurrentes, Slice Manager valida y reserva los recursos mediante transacciones SQL, para impedir que dos solicitudes asignen la misma capacidad o identificadores de red. Posteriormente, la cola distribuye los trabajos entre ejecutores, mientras que las claves de idempotencia y el control por slice evitan duplicaciones y operaciones incompatibles.

### 4.1.7 Registro de operaciones y manejo de errores

El orquestador registra las solicitudes, los cambios de estado, las acciones ejecutadas y los errores mediante logs asociados a identificadores como slice_id, operation_id y worker_id. Estos registros permiten seguir una operación entre módulos e identificar dónde ocurrió una falla. Ante errores, PlatManager verifica el estado real de los recursos antes de realizar reintentos o compensaciones, mientras Slice Manager actualiza el estado persistente del slice. La arquitectura contempla centralizar los registros y eventos para facilitar auditoría, monitoreo y troubleshooting sin depender de la revisión manual de cada servidor.

## 4.2 R1B — Interfaz de usuario para gestión de slices

### 4.2.1 Propósito y arquitectura de la interfaz

R1B describe cómo administradores, profesores y alumnos acceden a funciones del orquestador según su rol y vinculación académica. La interfaz agrupa tres funciones visibles: solicitar laboratorios y gestionar plantillas, consultar estados y métricas, y acceder a las consolas de VMs autorizadas. El diseño amplía estas funciones para importar imágenes mediante IMS y para importar o exportar plantillas JSON por Topology Manager, sin confundir ambos tipos de archivo. Todas las acciones administrativas se comunican con el API Gateway; **no se exponen los drivers directamente al usuario.**

![Módulos consultados por la interfaz de usuario R1B](media/image1.png)

Figura Componentes y servicios consultados por la UI, con IAM como servicio unificado.

| **Función de interfaz**  | **Funciones de R1B**                                                                                                                                                            | **Servicios que intervienen**                                       |
|--------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------|
| Solicitudes y plantillas | Elegir plantilla y versión, curso, alumnos, proveedor; solicitar CRUD autorizado de slices; importar/exportar plantillas JSON; enviar imagen QCOW2 si el flujo está habilitado. | Gateway, IAM, Topology Manager, Slice Manager e IMS.                |
| Seguimiento y vistas     | Consultar catálogo, estados de slices, operation_id, errores y métricas autorizadas.                                                                                            | Gateway, Slice Manager, Monitoreo.                                  |
| Acceso a laboratorio     | Solicitar acceso a una VM asignada y establecer sesión temporal con el mecanismo propio del proveedor (p. ej. VNC).                                                             | Gateway, IAM, Slice Manager, PlatManager/driver y proxy de consola. |

### 4.2.2 Gestión multiusuario y permisos

La interfaz contempla el acceso simultáneo de administradores, profesores y alumnos, con sesiones independientes y funciones limitadas por sus permisos. IAM verifica el rol, la pertenencia al curso y la autorización sobre cada slice. Cuando varios usuarios realizan operaciones sobre un mismo recurso, Slice Manager aplica los mecanismos de control de versiones y concurrencia definidos en R1, para impedir modificaciones incompatibles.

### 4.2.3 Gestión del ciclo de vida de slices

La interfaz permite visualizar los slices autorizados y realizar operaciones de creación, consulta, edición y eliminación según el rol del usuario. Cada slice presenta su configuración, las máquinas virtuales asociadas y su estado actual. Las solicitudes se envían mediante el API Gateway hacia Slice Manager, que valida la operación y coordina su procesamiento. Para modificar un slice existente, la interfaz recupera su configuración y envía los cambios para su validación antes de aplicarlos.

### 4.2.4 Configuración de topologías predefinidas y personalizadas

El diseño de la interfaz debe ofrecer topologías lineal, malla, árbol, anillo y bus, además de combinarlas o editarlas antes del despliegue. El usuario configura imagen, vCPU, RAM, disco e interfaces por VM y añade o elimina nodos y enlaces. Puede guardar borradores, exportar e importar la topología y crear un nuevo slice a partir de ella. Topology Manager valida el grafo; Slice Manager verifica permisos y recursos. El ZIP aporta ex1, lineal y anillo: las demás plantillas y el editor completo son capacidades por desarrollar.

### 4.2.5 Importación y exportación de plantillas e imágenes

En el HLD propuesto, la interfaz permite exportar la configuración declarativa de un slice como plantilla JSON mediante Topology Manager. El archivo incluye versión del esquema, topología, nodos, interfaces y enlaces, recursos solicitados por VM (vCPU, RAM y disco), referencias a imágenes del catálogo y servicios o políticas de red requeridos. Se excluyen identificadores operativos del despliegue, reservas activas, credenciales, tokens y direcciones asignadas dinámicamente. La exportación no incluye discos ni imágenes QCOW2, memoria o estado de ejecución: permite reproducir la configuración, no clonar una VM en funcionamiento.

Al importar, Topology Manager valida el esquema y su versión, la unicidad de nodos e interfaces, la consistencia de enlaces y los límites de recursos. IAM verifica los permisos; IMS comprueba que las referencias de imágenes existan y sean accesibles. Una referencia no disponible debe resolverse o rechazarse con un error explícito, sin desplegar parcialmente. Tras la validación, el usuario puede guardar o editar la plantilla y solicitar un slice nuevo con identificadores propios; Slice Manager realiza nuevamente admisión, reserva y planificación según la capacidad actual. La importación por sí sola no despliega ni garantiza disponibilidad.

La carga de imágenes QCOW2 es un flujo independiente gestionado por IMS, que valida el formato, registra metadatos y disponibilidad y coordina su preparación en los workers. La portabilidad de la plantilla no supone exportar esas imágenes. Como verificación prevista, se exportará un slice, se importará el JSON y se compararán nodos, enlaces y recursos; también se probarán esquema inválido, referencia de imagen ausente y falta de permisos. Estas comprobaciones describen el diseño y no constituyen evidencia de ejecución.

### 4.2.6 Visualización del estado y consumo de recursos

La interfaz contempla un panel de monitoreo que permite visualizar el estado de los slices y los recursos utilizados por sus máquinas virtuales. Para cada slice se muestra su estado de operación (por ejemplo, READY, STOPPED o FAILED), las VMs asociadas y los recursos asignados, como vCPU, memoria RAM y almacenamiento. Asimismo, el usuario puede consultar el consumo real de recursos, como la utilización de CPU, memoria y almacenamiento, además de métricas de red cuando estén disponibles. **Esta información permite diferenciar entre los recursos reservados para una VM y los que realmente utiliza durante su funcionamiento**. Para obtener estos datos, la interfaz realiza solicitudes mediante el API Gateway. El Slice Manager proporciona la configuración y el estado de los slices, mientras que el módulo de Monitoreo recopila periódicamente información de los workers y las máquinas virtuales. De esta manera, también es posible visualizar la capacidad total, utilizada y disponible de los servidores. Finalmente, IAM controla la información que puede consultar cada usuario: el administrador supervisa toda la infraestructura, mientras que profesores y alumnos visualizan únicamente los recursos autorizados. Esto facilita la supervisión de los laboratorios, la planificación de nuevos despliegues y la identificación de posibles problemas de rendimiento.

### 4.2.7. Acceso a consolas virtuales mediante tokens

La interfaz permite acceder a las consolas de las máquinas virtuales mediante un mecanismo de acceso remoto basado en VNC/noVNC. Cuando un usuario solicita una consola, el API Gateway e IAM verifican sus permisos sobre la VM y se genera un token temporal que autoriza dicha conexión. El navegador se comunica con un proxy de consola, el cual establece una conexión segura con el hipervisor del worker donde se encuentra alojada la VM. En el clúster Linux, esta comunicación utiliza la red de administración MGMT 1 (192.168.201.0/24) mediante un túnel SSH hacia el servicio VNC correspondiente. De esta manera, el tráfico de consola se mantiene separado de las redes de datos de los slices y no requiere exponer directamente los puertos VNC de los servidores físicos. El acceso queda restringido a la VM autorizada y a la vigencia del token. En OpenStack, el driver solicitará la consola de Nova y entregará su URL temporal autorizada; no reutilizará directamente los puertos VNC ni los tokens del backend Linux.

## 4.3 R1C — Slice Manager / Gestor de despliegue

### 4.3.1 Propósito y arquitectura lógica

El requerimiento R1C establece al **Slice Manager** como el módulo responsable de coordinar la creación, modificación y eliminación de slices. Su función principal es transformar las solicitudes de los usuarios en planes de despliegue que puedan ejecutarse sobre la infraestructura. Para ello, interactúa con Topology Manager, VM Placement, Networking Service e IMS. El Slice Manager no crea directamente las máquinas virtuales, sino que coordina su planificación y delega la ejecución al PlatManager mediante la cola de operaciones.

![Flujo de validación, admisión y recuperación del Slice Manager R1C](media/image18.png)

Componentes lógicos del Slice Manager, admisión y recuperación.

### 4.3.2 Validación de solicitudes y topologías

Antes de procesar una solicitud, el sistema verifica la identidad y los permisos del usuario mediante API Gateway e IAM. Posteriormente, Slice Manager valida que la operación sea compatible con el estado actual del slice. Asimismo, consulta a **Topology Manager** para comprobar la estructura de la topología solicitada, con máquinas virtuales, interfaces y enlaces. También verifica los requisitos de cómputo, red e imágenes, y rechaza solicitudes incompletas o incompatibles antes de comprometer recursos.

### 4.3.3 Planificación y orden de despliegue

Una vez validada la solicitud, el Slice Manager coordina los módulos especializados para elaborar un plan de despliegue que determine los recursos necesarios y el orden en que deben crearse. Primero, Topology Manager proporciona la estructura de la topología, con las máquinas virtuales, interfaces y enlaces solicitados. A partir de esta información, VM Placement propone los servidores físicos donde se alojarán las VMs, según los ratios efectivos, su capacidad disponible y el estado operativo. Paralelamente, Networking Service define los segmentos de red, VLANs, direccionamiento y conexiones necesarias, mientras que Image Management Service (IMS) verifica la disponibilidad y compatibilidad de las imágenes requeridas en los workers seleccionados. Con estos resultados, Slice Manager construye un plan de ejecución con dependencias, que especifica qué operaciones deben completarse antes de iniciar otras. Por ejemplo, se debe garantizar la disponibilidad de las imágenes base y preparar los segmentos de red antes de iniciar las VMs que dependen de ellos. Asimismo, deben configurarse correctamente las interfaces virtuales y sus conexiones para que las máquinas puedan comunicarse según la topología solicitada. Una vez aprobadas las reservas de recursos, el plan se envía mediante la cola de operaciones hacia PlatManager, encargado de coordinar su ejecución. Este componente delega las tareas al driver correspondiente y verifica su resultado antes de habilitar las operaciones dependientes. Las tareas independientes pueden ejecutarse en paralelo, mientras que aquellas con dependencias deben respetar el orden establecido. Finalmente, los resultados se comunican al Slice Manager para actualizar el estado del slice. De esta manera, la arquitectura evita ejecutar operaciones sobre recursos inexistentes y permite identificar las etapas que requieren verificación o recuperación ante posibles fallos.

### 4.3.4 Reserva de recursos y concurrencia

Antes del despliegue, Slice Manager revalida cuotas, inventario y el plan completo del slice. Las reservas transaccionales incluyen CPU asignada, RAM, disco y recursos de red; se contabilizan las existentes y las pendientes. VM Placement realiza una simulación provisional al evaluar cada VM, pero la confirmación global corresponde a Slice Manager. En OpenStack esta reserva G5 no es una transacción distribuida con Nova: el driver vuelve a comprobar capacidad, registra las asignaciones del proveedor y compensa solo los recursos del intento que falle.

### 4.3.5 Ejecución y recuperación ante fallos

Una vez admitida la solicitud, Slice Manager registra el estado del slice y envía el trabajo a la cola de operaciones. **PlatManager coordina la ejecución mediante los drivers** y comunica los resultados obtenidos. El diseño contempla un despliegue de tipo todo o nada: el slice solo alcanza el estado READY cuando sus recursos y conexiones han sido verificados. Si ocurre una falla parcial, **se ejecutan acciones de compensación para retirar los recursos exclusivos** creados durante la operación. Cuando no es posible confirmar la limpieza, el slice permanece en un estado de error recuperable y conserva las reservas necesarias hasta resolver la inconsistencia.

### 4.3.6 Monitoreo y consistencia de recursos

Slice Manager **mantiene el estado lógico de los slices**, mientras que Monitoreo recopila información sobre el estado real de las máquinas virtuales y los workers, con recursos asignados y métricas de utilización. **Esta información permite comparar la configuración esperada con los recursos efectivamente desplegados.** Cuando se detectan diferencias, Slice Manager puede iniciar un proceso de reconciliación, mientras que PlatManager verifica o corrige los recursos mediante el driver correspondiente. Así, el sistema evita considerar exitoso un despliegue únicamente porque sus comandos fueron aceptados, sin comprobar el resultado sobre la infraestructura.

### 4.3.7 Actualización y eliminación de slices

Para modificar un slice, Slice Manager compara la configuración solicitada con la existente y determina los recursos que deben agregarse, actualizarse o eliminarse. Los incrementos de capacidad se reservan antes de aplicar los cambios. El proceso de eliminación respeta las dependencias del despliegue y retira las máquinas virtuales, sus discos exclusivos y las conexiones correspondientes. **IMS verifica las referencias de las imágenes base para evitar eliminar archivos compartidos por otras VMs**. Finalmente, las reservas se liberan únicamente cuando se confirma que los recursos correspondientes han sido retirados correctamente.

## 4.4 R2 — Soporte del clúster de servidores Linux

### 4.4.1 Propósito y alcance de R2

El requerimiento R2 establece el soporte necesario para administrar máquinas virtuales sobre un clúster de servidores Linux. Su objetivo es permitir que el orquestador cree, configure, supervise y elimine recursos virtualizados mediante un mecanismo independiente de los demás proveedores de infraestructura. Para ello, el diseño contempla el uso de KVM/QEMU para la virtualización, libvirt para administrar el ciclo de vida de las VMs, Open vSwitch (OVS) para la conectividad de red y QCOW2 para gestionar los discos virtuales.

![Arquitectura lógica del soporte Linux R2](media/image8.png)

Figura Vista lógica propuesta del soporte Linux.

### 4.4.2 Infraestructura y responsabilidad

La arquitectura distingue un plano de control, un nodo de administración (***Headnode***) y los servidores Linux encargados de ejecutar las máquinas virtuales (*workers*). El PlatManager recibe los planes de despliegue y delega las operaciones al Driver Linux, que traduce las instrucciones del orquestador en acciones sobre los servidores físicos. En el diseño, libvirt proporciona una interfaz de administración para crear, iniciar, detener y consultar dominios virtuales gestionados mediante QEMU/KVM. Los workers utilizan Open vSwitch para establecer las conexiones de red y almacenamiento QCOW2 para conservar los discos de las máquinas virtuales. Esta separación permite gestionar varios servidores desde una misma arquitectura de control.

### 4.4.3 Aprovisionamiento de VMs y gestión de imágenes

Para crear una máquina virtual, el Driver Linux recibe las especificaciones de recursos y el servidor de destino definido en el plan de despliegue. Posteriormente, verifica la disponibilidad de la imagen base, prepara el disco virtual y configura las interfaces de red necesarias. El diseño considera utilizar libvirt para definir y administrar las VMs sobre KVM/QEMU, mientras que OVS proporciona los bridges y conexiones correspondientes a la topología solicitada. La máquina se inicia después de preparar sus dependencias y se verifica su estado antes de confirmar la operación. Por otro lado, IMS administra el catálogo de imágenes QCOW2 y coordina su distribución. Mediante discos diferenciales (overlays), varias VMs pueden reutilizar una misma imagen base sin duplicarla completamente. Durante la eliminación, se retiran los discos exclusivos y se conservan las imágenes compartidas mientras existan referencias activas.

### 4.4.4 Administración de workers y monitoreo

La arquitectura contempla incorporar workers mediante su registro, verificación de conectividad y actualización de capacidades disponibles. Para retirarlos, primero se deshabilitan nuevas asignaciones y se establece un estado de mantenimiento (DRAINING). El retiro se completa cuando sus VMs han finalizado o se han reubicado mediante mecanismos compatibles. El módulo de Monitoreo recopila periódicamente información de los servidores y máquinas virtuales, como utilización de CPU, memoria RAM, almacenamiento y estado operativo. Estos datos permiten identificar fallas, consultar la disponibilidad de recursos y proporcionar información a VM Placement para futuras decisiones de ubicación.

### 4.4.5 Seguridad y acceso a consolas virtuales

La administración del clúster se realiza mediante conexiones restringidas, credenciales de servicio y mecanismos seguros como SSH. Los usuarios no acceden directamente a los servidores físicos ni reciben sus credenciales administrativas. Para acceder a una VM, la interfaz solicita autorización mediante API Gateway e IAM. Una vez validada, se genera un token temporal que permite establecer una sesión VNC/noVNC hacia la consola proporcionada por el hipervisor. En el clúster Linux, el tráfico entre el proxy de consola y el worker utiliza la red de administración MGMT 1, con separación de las redes de datos de los slices y sin exposición directa de puertos VNC.

### 4.4.6 Manejo de errores y troubleshooting por slice

El Driver Linux contempla mecanismos de verificación, reintentos controlados y registro de resultados para gestionar fallas de conexión, recursos insuficientes o errores durante el aprovisionamiento. Antes de repetir una operación, PlatManager y el driver deben comprobar el estado real de los recursos para evitar duplicaciones. Si ocurre una falla parcial, se ejecutan acciones de compensación sobre los recursos exclusivos del slice, y se conservan aquellos que aún estén en uso. Para facilitar el troubleshooting, cada operación se relaciona con identificadores como slice_id, operation_id, vm_id y worker_id. Esto permite consultar los eventos registrados, identificar el servidor involucrado y verificar el estado de las VMs, discos e interfaces de red sin afectar otros slices.

### 4.4.7 Cobertura de los criterios de diseño de R2

| **Criterio de rúbrica**   | **Evidencia de diseño que debe mostrarse**                                                     |
|---------------------------|------------------------------------------------------------------------------------------------|
| Selección tecnología      | KVM/QEMU, libvirt, OVS, QCOW2 y mecanismos de acceso administrativo seguros.                   |
| Robustez / error handing  | Timeout, clasificación de errores, reintentos idempotentes, verificación y rollback selectivo. |
| Seguridad del clúster     | Acceso a workers limitado, red de gestión separada y VNC mediado por autorización.             |
| alta / baja de workers    | Registro, mantenimiento/drain y actualización de inventario y Placement.                       |
| Monitoreo                 | Recolección y consulta de CPU, RAM, disco, estado de VM y salud de worker.                     |
| Consola                   | Autorización por VM, referencia expirable y canal protegido a VNC                              |
| Troubleshooting por slice | IDs de correlación, diario SQL (operaciones) y métricas/logs vinculados al slice.              |

## 4.5 R5 — Networking y Seguridad

### 4.5.1 Objetivo, alcance y responsabilidades

R5 define cómo la plataforma prepara, materializa y verifica la conectividad de las máquinas virtuales dentro de un slice; interconexión L2, servicios L3 cuando correspondan, aislamiento entre entornos, salida a redes externas y acceso externo selectivo. La solución mantiene dos responsabilidades: Network Service especifica la intención y produce un plan de red; PlatManager y el Driver Linux aplican ese plan en los Workers y notifican sus resultados.

### 4.5.2 Funciones Internas del Networking Service

El servicio agrupa cuatro capacidades conceptuales. Su implementación puede organizarse como clases, paquetes o funciones dentro del mismo módulo, sin la fragmentación artificial del sistema en varios microservicios.

| **Función**                          | **Entrada principal**                                                      | **Salida principal**                                                                                |
|--------------------------------------|----------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------|
| Segmentación y direccionamiento      | Grafo, enlaces, inventario de VLAN/IP y restricciones por curso/proveedor. | Segmentos L2, candidatos VLAN, subredes y direcciones; recursos a reservar.                         |
| Conectividad L3 y acceso externo     | Servicios declarados en la plantilla y política de conectividad.           | Gateway, rutas, DHCP/DNS y NAT si resultan necesarios.                                              |
| Políticas de seguridad y aislamiento | Ámbitos de slice, tráfico permitido y condiciones de enlace.               | Reglas de filtrado, aislamiento, control del broadcast y comprobaciones.                            |
| Construcción y validación del plan   | Propuestas anteriores, destinos de Placement y capacidades del driver.     | network_plan versionado con interfaces, dependencias, puertos, validaciones y acciones de limpieza. |

El resultado lógico de Network Service es un “network_plan”. Indicará, como mínimo, la identificación del slice y del proveedor; los segmentos requeridos; la relación VM-interfaz-segmento; los identificadores o rangos propuestos; los puntos previstos para DHCP, enrutamiento, NAT o filtrado; las dependencias entre acciones; y las comprobaciones que permitirán confirmar un resultado correcto. Un identificador propuesto no puede considerarse reservado hasta su confirmación por el mecanismo transaccional de admisión del slice manager.

### 4.5.3 Arquitectura lógica y límites de comunicación

![Arquitectura lógica del servicio Networking R5](media/image10.png)

Figura Diseño lógico de R5: el plan de red se prepara antes de la ejecución; los cambios sobre Linux atraviesan la cola, PlatManager y Driver Linux.

Topology Manager aporta el grafo de nodos, interfaces y enlaces de la plantilla. Slice Manager solicita la planificación, incorpora sus resultados y confirma los recursos junto con los demás reservas del slice. VM-Placement propone los workers donde se alojan las VMs; esa ubicación permite determinar qué conexiones son locales y cuáles atraviesan varios servidores. Los datos de Monitoreo ayudan a validar capacidad y estado, pero no constituyen un mecanismo de reserva.

### 4.5.4 Segmentación L2 con VLAN 802.1Q y QinQ

![Segmentación VLAN L2 sobre Linux y Open vSwitch](media/image3.png)

Figura Vista física conceptual de R5 sobre Linux: dos segmentos L2 separados que atraviesan workers mediante OVS y transporte compatible; el acceso externo se controla en el gateway previsto.

En cada worker, el Driver Linux utiliza mecanismos como TAP/veth e interfaces virtuales conectadas a bridges OVS para incorporar las VMs a los segmentos definidos. Una VM únicamente debe vincularse a los segmentos declarados en su topología. Si las VMs de un mismo segmento residen en workers diferentes, el enlace entre ellos debe transportar las VLANs necesarias sobre el switch y los enlaces físicos. El diseño debe verificar previamente los puertos troncales, la compatibilidad de la configuración y el comportamiento del dominio broadcast.

En Linux se conserva la segmentación VLAN 802.1Q y QinQ compatible con el prototipo, sin sustituirla por túneles. En OpenStack se requieren redes self-service y puertos Neutron por enlace, según la configuración ML2/OVS realmente habilitada. No se impone a ambos clústeres la misma tecnología de transporte ni se identifica automáticamente una red OpenStack como VXLAN, GRE o VLAN. Deben consultarse el tipo de red y su segmentación antes de configurar o documentar el plano de datos.

Cuando se requiera ampliar el espacio de segmentación, se propone QinQ: una etiqueta externa S-VLAN identifica el contexto de transporte y una etiqueta interna C-VLAN distingue el segmento dentro de ese contexto. La pareja S-VLAN/C-VLAN debe ser única en su ámbito; los equipos de borde agregan o retiran la etiqueta externa y los tramos intermedios preservan ambas etiquetas según el plan. Se validarán soporte 802.1ad, TPID, modo de puertos y MTU para la sobrecarga de etiquetas en OVS, interfaces y switch. No basta con habilitar QinQ en un único extremo.

La verificación prevista incluye conectividad entre VMs del mismo segmento alojadas en workers distintos, rechazo de tráfico entre segmentos no autorizados y captura de etiquetas en el enlace físico. Para QinQ se probará además el mismo C-VLAN bajo S-VLAN diferentes y se comprobará que no exista fuga entre contextos. Si el hardware no soporta QinQ, se informará la limitación y se mantendrá el alcance disponible con 802.1Q, sin sustituirlo silenciosamente por túneles ni afirmar que QinQ está implementado.

### 4.5.5 Aislamiento, seguridad y control de broadcast

El aislamiento se define en dos planos complementarios. En el plano académico, IAM controla qué usuario puede gestionar o acceder a un slice; en el plano de datos, las VLANs, puertos OVS, tablas de flujo y políticas L3 limitan qué máquinas virtuales pueden intercambiar tráfico. Que un profesor esté autorizado para administrar su laboratorio no le concede privilegios sobre otros slices ni sobre la red de gestión de los servidores.

Los broadcasts y el tráfico desconocido deben limitarse a los servidores que contienen extremos del enlace. Networking deriva el conjunto de puertos participantes a partir del grafo y de la ubicación de las VMs; el adaptador aplica permisos de VLAN y, cuando sea necesario, reglas de forwarding por segmento. Admitir una S-VLAN en todos los trunks no demuestra restricción por enlace. Las capturas deben comprobar recepción en los puertos requeridos y ausencia en los restantes, sin alterar los segmentos de otros slices.

Las reglas de firewall deben instalarse en el recorrido efectivo del tráfico. En particular, una regla iptables sobre la cadena FORWARD del host no necesariamente controla paquetes exclusivamente conmutados por OVS; para ese caso puede requerirse una política de flujo de OVS o un mecanismo equivalente. El HLD evita prometer aislamiento por el simple hecho de haber creado VLANs o reglas de firewall: contempla pruebas de tráfico permitido, denegado y broadcast.

### 4.5.6 Conectividad L3, Internet y acceso externo selectivo

En el HLD propuesto, la salida externa se habilita solo para slices autorizados. El recorrido previsto es VM → interfaz TAP/OVS → segmento VLAN del slice → interfaz interna del gateway → interfaz externa → red externa. La VM utiliza el gateway como siguiente salto y el gateway dispone de reenvío IP y ruta hacia la red externa. En su salida se aplica SNAT a la dirección externa asignada; MASQUERADE es una alternativa cuando esa dirección sea dinámica. El seguimiento de conexiones permite asociar las respuestas con la VM original y aplicar la traducción inversa.

La política de forwarding deniega por defecto y permite únicamente los orígenes, destinos y servicios aprobados, junto con respuestas de conexiones establecidas o relacionadas. El plan identifica el gateway, las subredes, rutas, interfaz de salida y reglas NAT y de filtrado; mantiene aislada la red de administración. Se comprobarán resolución DNS cuando corresponda, ruta efectiva, conectividad externa, contadores de reglas y tráfico de retorno. La salida a Internet no habilita por sí sola acceso entrante ni acceso a consola.

El acceso externo selectivo de fase 2 utiliza los rangos privados asignados al grupo G5: 10.60.9.0/24 en Linux y 10.60.10.0/24 en OpenStack. Son alcanzables mediante la VPN y las rutas del Headnode del VNRT; no son IP públicas ni se garantiza su acceso directo desde la red interna de la universidad. Solo las VMs solicitadas explícitamente reciben exposición. La solución debe registrar asignación de IP, ruta de retorno y filtrado; DHCP puede utilizarse si el segmento lo requiere. No se inventa un gateway ni un pool de hosts no documentado.

Networking registra slice, VM, dirección, protocolo, puertos, orígenes permitidos y vigencia. En Linux, DNAT puede publicar un servicio si el diseño de acceso lo requiere; en OpenStack se utilizará el mecanismo de Neutron configurado y autorizado, con sus reglas de seguridad. La salida a Internet, la entrada SSH mediante VPN y la consola noVNC son servicios diferentes. Cada publicación requiere retorno correcto y revocación verificable; una traducción NAT no sustituye la política de firewall.

La aceptación prevista exige una conexión desde un origen externo permitido, rechazo desde un origen no autorizado y a puertos no publicados, y comprobación de revocación y retorno. Se conservarán configuración efectiva, contadores y registros asociados a la operación. Estos son criterios de validación del diseño: solo capturas, comandos y resultados obtenidos en la infraestructura pueden acreditar implementación.

### 4.5.7 Reconfiguración verificable y reversible del switch físico

PlatManager invoca el adaptador de administración del switch según el network_plan. Networking calcula segmentos y mapa enlace–servidores–puertos; el adaptador modifica únicamente los puertos participantes y utiliza la gestión segura disponible. En fase 2 deben inventariarse ovs1 y ovs2 y su correspondencia con los enlaces reales; no se reutiliza sin validación el mapa OFS de fase 1. La configuración debe preservar gestión, tráfico ajeno y referencias compartidas.

Antes de cambiar el equipo se consulta su configuración y capacidades, se valida el mapa worker–puerto, el modo access/trunk, VLANs permitidas, QinQ y MTU, y se preservan los puertos y VLANs de administración. Se registra una instantánea de la configuración relevante y un plan de diferencias y reversión, asociado a slice_id y operation_id. Un bloqueo por dispositivo o por recurso compartido evita cambios concurrentes incompatibles; la comprobación del estado actual permite reintentos idempotentes.

La aplicación modifica solo los recursos autorizados, sin reemplazar globalmente las listas de VLANs utilizadas por otros slices. Tras cada fase se consulta la configuración efectiva y el estado de los puertos. La operación se confirma únicamente después de verificar conectividad entre workers, aislamiento, etiquetas y continuidad de gestión. Cuando el dispositivo lo soporte se utilizará confirmación con reversión temporizada; en otro caso el adaptador ejecutará las acciones inversas registradas y comprobará la recuperación.

Ante fallo se restauran los valores previos de los recursos modificados, con respeto a cambios ajenos y referencias activas; se verifica el estado resultante antes de liberar las reservas. Si no puede comprobarse la reversión, la operación queda en error y requiere reconciliación, sin declarar éxito. Al borrar un slice se eliminan únicamente VLANs, etiquetas o permisos de puertos que ya no tengan usuarios. La evidencia de implementación deberá incluir configuración antes/después, diferencia aplicada, lectura posterior y una prueba de fallo con reversión; este apartado especifica el procedimiento propuesto y no afirma que ya se haya ejecutado.

### 4.5.8 Fallos, reversión y liberación de recursos

| **Riesgo o evento**                        | **Respuesta propuesta**                                                                                                                  |
|--------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------|
| VLAN o IP ya comprometida                  | Rechazar/replantear la admisión. La asignación no se confirma dos veces.                                                                 |
| Worker o switch sin capacidad requerida    | No crear VMs/redes incompatibles; informar motivo y solicitar nueva ubicación o revisión del plan.                                       |
| Timeout al crear bridge/puerto             | Consultar estado real por identificador antes de reintentar; evitar crear recursos duplicados.                                           |
| Fallo parcial al configurar NAT o firewall | Detener tareas dependientes, registrar cambios realizados y ejecutar compensación autorizada.                                            |
| Pérdida de conectividad entre workers      | Marcar verificación fallida, conservar logs y no publicar READY sin conectividad comprobada.                                             |
| Eliminación del slice                      | Retirar puertos, reglas y segmentos exclusivos en orden de dependencia; preservar interfaces/bridges compartidos y confirmar liberación. |

Los registros deben permitir seguir una incidencia por identificador de slice, operación, VM, worker y recurso de red. Slice Manager mantiene el estado lógico; PlatManager conserva el diario de pasos realizados; Driver Linux entrega el resultado observado. Las reservas no se liberan solo por un timeout: se requiere constatar el estado real o completar una compensación segura.

## 4.6 R3 — Soporte del clúster OpenStack

### 4.6.1 Propósito y servicios

R3 integra el segundo clúster mediante sus APIs nativas. Se conserva la separación entre planificación G5 y ejecución del proveedor: la solicitud identifica clúster y zona; el driver autentica en Keystone, consulta recursos e imágenes, ejecuta el plan y persiste los UUID. La plataforma instalada durante LAB5 aporta la base operativa, mientras el adaptador G5 sigue por desarrollar.

| **Servicio**           | **Responsabilidad y uso en el driver**                                                             |
|------------------------|----------------------------------------------------------------------------------------------------|
| Keystone               | Tokens, proyectos, dominios y catálogo de endpoints. IAM G5 conserva la autorización académica.    |
| Glance                 | Imágenes y metadatos; mapear la imagen lógica G5 al UUID accesible por el proyecto.                |
| Nova                   | Flavors, instancias, acciones de ciclo de vida, host real y consolas.                              |
| Placement de OpenStack | Inventarios, reservas del proveedor y allocations; no sustituye la heurística G5.                  |
| Neutron ML2/OVS        | Redes self-service, subredes, puertos, seguridad y conectividad L3 cuando se solicite.             |
| Horizon                | Visualizar recursos del proyecto y contrastar topología y ubicación; no es un API de orquestación. |

### 4.6.2 Plan y ejecución de un slice

El driver resuelve proyecto, zona, imágenes y flavors; crea las redes y subredes declaradas, un puerto por vNIC y las instancias asociadas a esos puertos. Una topología predefinida y una personalizada recorren el mismo plan validado. Los enlaces L2 usan segmentos Neutron separados; un enlace sin servicio L3 no necesita gateway y puede tener DHCP desactivado. Los puertos de una VM multihomed no deben confundirse con puertos físicos exclusivos.

La creación se ordena por dependencias y paraleliza únicamente recursos independientes con un límite configurable. Se cachean catálogos estables con caducidad, pero se revalidan disponibilidad, cuotas y reservas antes de cada creación. El adaptador persiste UUID, propietario, slice y operación, consulta estados hasta ACTIVE o ERROR y aplica timeout y reintentos acotados. Ante una respuesta incierta consulta los recursos del intento antes de repetir; no presume idempotencia nativa de un POST de Nova.

### 4.6.3 Aplicación del destino y verificación

VM Placement de G5 decide el host; OpenStack Placement suministra inventarios y Nova Scheduler aplica sus filtros. El diseño solicita el destino calculado mediante host/hypervisor_hostname de Nova desde microversión 2.74, sujeto a soporte y permisos comprobados. La zona limita candidatos, pero por sí sola no impone nuestra heurística. Se verifica el host efectivo y se registra cualquier rechazo o discrepancia; no se cambia silenciosamente de zona ni se declara aplicado el algoritmo si Nova eligió libremente.

La reserva G5 y la de Nova no son atómicas entre sí. Si aparece contención externa, se consulta el estado, se compensa exclusivamente el intento afectado y se recalcula sin liberar capacidad incierta. La eliminación retira instancias, puertos y redes propios en orden inverso y confirma su ausencia. Imágenes, redes o recursos compartidos se conservan mientras tengan referencias.

### 4.6.4 Seguridad y evidencia

Las credenciales de servicio permanecen en el driver; el usuario recibe únicamente datos autorizados y consolas temporales. Neutron aplica políticas por puerto y security groups según la topología. Desactivar port security, cuando una práctica lo requiera, exige justificar y reemplazar las protecciones necesarias. La aceptación incluye despliegue L2, ubicación esperada, visualización por proyecto en Horizon, acceso noVNC, fallo controlado y borrado sin afectar recursos ajenos.

## 4.7 R4 — VM Placement

### 4.7.1 Objetivo y alcance

Se adopta Best Fit Decreasing con demanda estocástica por franja horaria y un submódulo de Calibración de Sobreasignación dentro de VM Placement. La calibración propone ratios de CPU y disco a partir del historial; el plan utiliza los ratios efectivos, la telemetría reciente y las restricciones de recursos. La prioridad es limitar la contención; entre planes admisibles se favorece consolidar VMs en hosts ya ocupados. Todas las VMs del slice pertenecen a un único clúster y a la zona solicitada, o se devuelve un rechazo explicado. Con iguales entradas y versiones, la decisión es reproducible. La realocación automática queda como extensión.

Consolidar significa concentrar VMs compatibles para maximizar los hosts sin VMs de tenant, tras satisfacer todas las restricciones del slice. La sección 4.7.9 formaliza esta función objetivo y la 4.7.10 la compara con un solver. Liberar un host no garantiza ahorro eléctrico si permanece encendido con el mismo consumo de reposo; no se reportan watts ahorrados sin un modelo medido y una reducción real del consumo.

### 4.7.2 Recursos reales y política de asignación

| **Parámetro**       | **Política definida**                         | **Condición**                                                                                 |
|---------------------|-----------------------------------------------|-----------------------------------------------------------------------------------------------|
| CPU asignada        | 2.0 por defecto (200 %), configurable         | vCPU compartidas; límite contable más filtro de demanda real y prevista.                      |
| RAM                 | 1.0 fijo (100 %)                              | Respaldar la RAM comprometida y reservar memoria para host e hipervisor.                      |
| Disco               | Configurable en diseño; 1.0 en implementación | Ratio \> 1 solo con almacenamiento thin y crecimiento acotado; sin evidencia se conserva 1.0. |
| CPU prevista        | Máximo 85 %                                   | Percentil 99 y picos conocidos en todas las franjas relevantes.                               |
| CPU observada       | Admisión ≤ 85 %                               | Métrica vigente y ausencia de otros bloqueos de recursos.                                     |
| Sobrecarga          | \> 90 % durante 30 s                          | Evento OVERLOAD y recomendación; sin migración automática.                                    |
| Muestreo y vigencia | 5 s y 15 s                                    | Datos vencidos o desconocidos no habilitan admisión.                                          |
| Riesgo objetivo     | 1 % por host y minuto                         | Objetivo local; no garantía global de toda la sesión.                                         |
| Reserva mínima      | RAM ≥ 1 GiB; disco ≥ 1 GiB                    | Ajustar al SO, servicios, QEMU, imágenes y cachés.                                            |
| Historial mínimo    | 1 día completo (24 h)                         | Primera propuesta provisional; cobertura y validación posterior obligatorias.                 |

La capacidad neta es el total elegible menos la reserva del host. El techo contable es capacidad neta × ratio; de él se descuentan asignaciones existentes y pendientes. El porcentaje total asignable equivale a ratio × 100: 1.0 significa 100 % y 2.0 significa 200 % total, es decir, 100 % adicional. Ningún ratio incrementa la capacidad física ni sustituye los controles de consumo real. Los valores son políticas del proyecto; no se presupone que coincidan con los valores por defecto de Nova.

CPU: ratio inicial 2.0 configurable. La CPU se multiplexa en el tiempo: una vCPU ociosa deja turnos de ejecución disponibles para otras. El valor 2.0 constituye el punto inicial del proyecto para cargas intermitentes, con el doble de asignación nominal y sin aumento de capacidad física. La calibración puede sugerir un valor menor o mayor según las cargas, los picos, la espera y la latencia; no presupone que 2.0 sea óptimo. El administrador aprueba la política y el adaptador confirma su valor efectivo. Sin historial representativo se presupuesta la demanda completa de las vCPU. El techo nominal nunca sustituye al filtro de CPU real y prevista del 85 %. Las CPU dedicadas no se sobreasignan.

RAM: ratio fijo 1.0 tanto en diseño como en implementación. La memoria comprometida debe caber en la capacidad neta después de la reserva para SO, servicios y sobrecarga de QEMU, con un mínimo de 1 GiB que puede aumentar según las mediciones. La memoria activa necesita respaldo físico; el intercambio de turnos de CPU no libera sus páginas. La sobreasignación puede provocar swap, latencia y terminaciones por falta de memoria. El diseño no incorpora recuperación garantizada de memoria que justifique ni siquiera un ratio ligeramente superior a 1.0. El historial de RAM sirve para ajustar reservas, comprobar presión y detectar cuellos de botella de los planes de CPU y disco; no autoriza nueva asignación de memoria ya comprometida. También se verifica MemAvailable en tiempo real.

Disco: ratio configurable en diseño y fijo en 1.0 en la implementación de esta fase. Los archivos thin o sparse, como QCOW2, permiten estudiar compromisos virtuales superiores al espacio físico, pero los datos persisten y pueden crecer hasta el tamaño declarado. La Calibración de Sobreasignación propone un ratio por pool a partir del tamaño virtual, la ocupación física, las tasas de crecimiento, la vida prevista de los slices y la capacidad de respuesta operativa. Un día de bajo uso no justifica por sí solo un aumento. Sin una previsión suficiente se sugiere 1.0. Las recomendaciones de disco se conservan como resultados de diseño y no modifican la política efectiva de implementación. \[6\]

Para elegir el ratio de disco se verifican dos límites independientes: el tamaño virtual total comprometido debe caber en capacidad neta × ratio; y la ocupación física actual más el crecimiento previsto de todos los discos, nuevas imágenes, snapshots y metadatos debe dejar un margen libre explícito. Cada consumo se cuenta una sola vez. El margen cubre el crecimiento posible durante el tiempo de detección y respuesta, además de la incertidumbre; se conserva al menos 1 GiB y se aumenta cuando esa estimación lo exige. Sin previsión fiable para toda la vida del slice, o si los huéspedes pueden llenar sus discos sin un control de respuesta suficiente, se utiliza 1.0. También se comprueban IOPS y latencia: sobreasignar capacidad no aumenta el rendimiento de E/S.

Ejemplo de diseño, no capacidad acreditada: un pool con 20 GiB físicos y 2 GiB excluidos como reserva y margen tiene 18 GiB netos. Un ratio 1.5 admite como techo contable 27 GiB virtuales. Solo sería admisible si la ocupación física conjunta prevista, incluidos crecimiento y sobrecargas, se mantiene dentro de 18 GiB con controles verificables. Si puede alcanzar los 27 GiB, el plan se rechaza o se amplía el almacenamiento. Este 150 % ilustra el criterio; no es el valor adoptado para implementación, que sigue en 100 %.

Aplicación y cambios de política. La calibración sugiere; el administrador aprueba; el adaptador verifica la política efectiva. CPU parte de 2.0 configurable; RAM permanece en 1.0; disco solo permite un ratio distinto de 1.0 en el diseño. El plan registra ratios, reservas y versión de política. En OpenStack se comprueban cpu_allocation_ratio, ram_allocation_ratio y disk_allocation_ratio en el inventario efectivo de Placement; una modificación en G5 no cambia Nova. Los parámetros initial\_\* solo inicializan registros nuevos. Una reducción de ratio no elimina VMs ni libera compromisos: el host cierra nuevas admisiones si excede el techo aprobado. Una propuesta pendiente nunca se usa como capacidad disponible. \[7\]

Se inventarían NICs, uplinks, ancho de banda por sentido, vNIC/TAP, puertos Neutron/OVS, IP, VLAN/VNI, cuotas y publicaciones TCP/UDP. Las vNIC comparten uplinks; no consumen un puerto físico exclusivo. Se comprueba MemAvailable y demanda de memoria, además de RAM comprometida. Si red, imagen, salud, capacidad o conectividad no están verificadas, no se promete la colocación.

### 4.7.3 Demanda estocástica y perfiles horarios

![Modelo estocástico de carga CPU y probabilidad de sobrecarga](media/image22.png)

**Ecuación de la figura (transcripción):** $S_{h,b}=B_{h,b}+\sum_{i\in h}X_{i,b}$ y $\Pr(S_{h,b}>0.90C_h)\leq 0.01$.

*Modelo de demanda y objetivo de riesgo por host y bloque temporal. Fuente: Módulo de VM Placement G5, sección 3.*

C es la capacidad CPU en unidades lógicas comparables; X es la demanda de cada VM en cores equivalentes (vCPU × fracción de uso); B es el fondo del SO y servicios no incluido en X. S incluye VMs de todos los slices. No se suma de nuevo el uso agregado del host a las mismas VMs. El objetivo limita la probabilidad de superar el 90 %; la regla operativa de admisión conserva un margen más estricto al 85 %.

El mínimo para iniciar la calibración es un día completo de observación, equivalente a 24 horas, en lugar de siete días. Se conserva una ventana móvil máxima de 28 días, con muestras sincronizadas cada 5 s y máximos de la suma por minuto, por hora de Lima y tipo de día. El requisito anterior de 300 bloques por franja se sustituye por cobertura explícita: el informe declara minutos válidos y huecos por hora, cargas presentes y tipos de día observados. No se rellenan huecos con ceros. Una hora completa contiene como máximo 60 bloques de un minuto en un solo día; no demuestra por sí sola un percentil extremo estable. La primera propuesta se marca PROVISIONAL y se contrasta con observaciones posteriores. Un día habilita el análisis, pero no acredita todos los patrones semanales ni garantiza un riesgo del 1 %.

Sin historial representativo, con franjas o tipos de día sin cobertura, dependencia desconocida, cambios de carga o datos afectados por saturación o tiempo de CPU no recibido, se presupuesta la demanda completa de las vCPU afectadas. Una VM nueva exige un perfil validado de su carga; compartir flavor no basta. Arranque, estrés conocido y cargas constantes se evalúan a demanda completa. Las series conservan la coincidencia temporal de picos y no presuponen independencia ni normalidad. Los compromisos recientes se incorporan aunque todavía no aparezcan en la telemetría.

![Regla de admisión con percentil 99 y pico conocido](media/image23.png)

**Ecuación de la figura (transcripción):** $R_h=\max_{b\in H}\{Q_{0.99}(S_{h,b}),K_{h,b}\}\leq 0.85C_h$.

*Regla de admisión para todas las franjas de la vida prevista del slice. Fuente: Módulo de VM Placement G5, sección 3.*

Q₀.₉₉ representa el percentil empírico 99 de la demanda agregada y K el pico conocido, incluido el fondo. H contiene las franjas que alcanzará el slice. Una VM persistente creada de noche también se evalúa contra las horas diurnas. Solo una duración acotada y controlada permite limitar H; no se admite una VM bajo el supuesto de una migración posterior que esta versión no implementa.

### 4.7.4 Heurística, reservas y tiempo de cálculo

Antes de ordenar las VMs se obtiene una instantánea de inventario, reservas, ratios efectivos y telemetría vigente. Las recomendaciones de calibración sin aprobación no alteran esa instantánea. BFD ordena las VMs por demanda CPU prevista en su peor franja, después vCPU, RAM, disco e identificador. Cada candidato debe cumplir clúster, zona, salud, imagen, conectividad, cuotas, puertos, límites nominales y consumo real y previsto. Entre hosts admisibles se prefiere uno ya ocupado y luego el que quede más cerca del 85 % sin excederlo. Los desempates usan menor RAM libre reservable, menor disco libre reservable e ID estable. Cada asignación provisional actualiza los compromisos y la demanda antes de evaluar la siguiente VM.

Los filtros contables son V_cpu + v_cpu ≤ C_neta × r_cpu, M_comp + m_vm ≤ M_neta × 1.0 y D_virt + d_vm ≤ D_neto × r_disco. Las letras mayúsculas representan compromisos existentes y pendientes; las minúsculas, la nueva VM. Cada recurso se contabiliza una sola vez. r_cpu y r_disco son valores efectivos por host o pool; en implementación r_disco = 1.0. El pool compartido se cuenta una sola vez para todos sus hosts.

Además se exige CPU real ≤ 85 % y R_h ≤ 0.85 C_h en todas las franjas relevantes, con el fondo del host incluido una sola vez. C_h conserva la capacidad CPU de referencia del modelo; el ratio no multiplica el denominador del porcentaje real. MemAvailable, presión de memoria, espacio físico proyectado, E/S, red y salud deben ser admisibles. Una recomendación histórica favorable no anula un bloqueo en tiempo real.

![Diagrama de flujo de Best Fit Decreasing (BFD)](media/image24.png)

*Flujo de la heurística BFD. Las reservas provisionales son del cálculo; Slice Manager confirma el plan completo. Fuente: Módulo de VM Placement G5, sección 4.*

Si alguna VM queda sin destino, no se ejecuta un plan parcial ni quedan reservas durables del intento. Slice Manager revalida inventario, métricas y versión de política al confirmar el slice completo; cualquier cambio concurrente obliga a recalcular. El resultado incluye host por VM, consumo por franja, ratios efectivos, identificador de calibración si existe y motivos de descarte. BFD es una heurística: la ausencia de un plan no demuestra que no exista otra combinación factible.

Para limitar el tiempo de planificación se usan una instantánea coherente, escenarios precalculados, consultas paralelas acotadas y un plazo máximo configurable para todo el intento, incluidos sus recálculos. Se comprueba el plazo durante la búsqueda y se devuelve PLANNING_TIMEOUT si vence, sin reservas parciales. El presupuesto se fija y valida con mediciones del servicio; el ZIP no lo implementa aún. Con N VMs, M hosts y H franjas, la búsqueda evita enumerar todas las combinaciones y evalúa hasta N × M × H casos, más el costo acotado de los escenarios y la ordenación.

### 4.7.5 Monitoreo y respuesta

Monitoreo proporciona dos funciones complementarias: consultar_estado_actual(alcance) y consultar_historial(alcance, inicio, fin, resolución). Son contratos internos de diseño, no endpoints ya presentes en el ZIP. La primera devuelve una instantánea por host, VM y pool con fecha, edad, calidad, salud y causas de bloqueo; la segunda devuelve series, cobertura y eventos para perfiles y calibración. La telemetría sigue una ruta independiente de la cola de despliegue.

Los recolectores muestrean cada 5 s. En Linux obtienen contadores del host, proceso QEMU y almacenamiento; el adaptador OpenStack relaciona las VMs y los pools con fuentes de métricas autorizadas. CPU se deriva del incremento de tiempo de CPU dividido por el intervalo y se normaliza a CPU equivalentes; también se registran espera, presión y tiempo de CPU no recibido. RAM incluye MemAvailable, memoria comprometida, consumo residente, swap y eventos de falta de memoria. Disco incluye tamaño virtual comprometido, bytes físicos, espacio libre, crecimiento positivo, imágenes base, snapshots, IOPS y latencia. Red incluye tasas por sentido, errores, puertos y capacidad de uplinks. Las métricas del invitado solo se usan si una fuente válida las proporciona.

Cada muestra identifica worker_id, vm_id, slice_id cuando corresponda, pool_id, instante UTC, fuente, unidad e intervalo. Se descartan duplicados; los reinicios de contadores y las muestras tardías se marcan. Un dato ausente no equivale a cero. Una edad superior a 15 s, una unidad incompatible o la pérdida de una métrica necesaria impide nuevas admisiones afectadas. El estado vigente alimenta VM Placement y la UI; los compromisos proceden del registro transaccional y del proveedor, no de una estimación por consumo.

El repositorio histórico conserva las muestras de 5 s durante al menos la ventana de análisis de 28 días y produce bloques de un minuto. Para CPU guarda el máximo de la suma sincronizada; para RAM, mínimo de MemAvailable y máximo de presión; para disco, ocupación, crecimiento y mínimo libre; para red, máximos por sentido. Las reservas, cambios de política y alertas quedan fechados para reconstruir las decisiones. Se mantienen métricas actuales y perfiles agregados separados, con retención y acceso por rol.

CPU real superior al 85 % bloquea nuevas colocaciones. Si supera 90 % durante 30 s continuos con datos válidos, Monitoreo emite OVERLOAD, invalida el perfil que subestimó la carga y solicita nueva calibración. La readmisión exige dos minutos por debajo de 80 %, métricas vigentes, recálculo y resolución de los demás bloqueos. Un hueco de telemetría no acredita continuidad. MemAvailable insuficiente, presión de memoria, espacio o crecimiento de disco incompatibles, espera CPU, E/S o red saturadas y fallos de salud también cierran la admisión. Los límites operativos de E/S y red se configuran por recurso a partir de su capacidad y latencia aceptable; no se presume un porcentaje universal.

La extensión de realocación reservaría destinos admisibles antes de mover VMs y verificaría recursos, red, coste de migración y riesgo en origen y destino. En esta fase solo se conserva la recomendación. La UI debe mostrar simultáneamente vCPU asignadas, ratio, CPU real y prevista, antigüedad de datos y explicación de la decisión.

### 4.7.6 Dimensionamiento y capacidad efectiva

El perfil de diseño es un slice de tres VMs, cada una con 2 vCPU, 512 MiB RAM, 3 GiB disco y dos vNIC en promedio: 6 vCPU, 1.5 GiB RAM, 9 GiB disco y seis puertos virtuales por slice, más recursos auxiliares de red. Es una referencia, no una media medida ni una topología obligatoria. La meta inicial es un slice Linux y uno OpenStack simultáneos, sujeta a verificación de recursos.

| **Cota de referencia**          | **Linux**         | **OpenStack**     |
|---------------------------------|-------------------|-------------------|
| Hosts de cómputo elegibles      | 4 servers         | 3 workers         |
| CPU visibles / vCPU con ratio 2 | 16 / 32           | 12 / 24           |
| RAM total de referencia         | 18.8 GiB          | 11.4 GiB          |
| Meta inicial                    | 1 slice / 3 VMs   | 1 slice / 3 VMs   |
| Techo con disco preparado       | 5 slices / 15 VMs | 4 slices / 12 VMs |

La tabla utiliza CPU 2.0, RAM 1.0 y disco 1.0. La última fila supone hosts sin compromisos de tenant, perfiles admisibles y almacenamiento preparado de 20 GiB por compute. Si cada host dispone de 9.6 GiB con 4.9 GiB ocupados y se conserva 1 GiB, cabría a lo sumo un disco nuevo de 3 GiB por host antes de cachés y crecimiento adicional: la cota por disco baja a un slice por clúster. Son escenarios condicionados, no un inventario certificado de los siete nodos. Con cargas constantes a demanda completa, el límite del 85 % también reduce la cota a una VM de 2 vCPU por host. Estas cotas se recalculan si cambia el ratio efectivo de CPU; no se extrapolan a partir de una recomendación pendiente.

La capacidad operativa se obtiene del mínimo entre CPU asignada, RAM, disco, puertos, cuotas y demanda prevista, seguido del empaquetamiento por host. Se restan VMs y reservas existentes. La captura de RAM usada no acredita MemAvailable suficiente. Escalar requiere añadir computes e inventariarlos por zona, con un responsable de reservas; subir ratios no resuelve un límite de CPU real, disco o red.

### 4.7.7 Integración y pruebas del módulo

La integración requiere funciones de recolección, consulta de estado e historial, calibración, propuesta BFD y confirmación de reservas. La función calibrar_sobreasignacion se incorpora dentro de VM Placement; no exige otro microservicio. model/config admitirán clúster, zona, perfil y duración sin host obligatorio. agent y los adaptadores aportarán métricas normalizadas; store conservará políticas, recomendaciones y reservas; engine y backends verificarán el destino. La primera implementación permitirá sobreasignación solo de CPU, con 2.0 inicial configurable, y mantendrá RAM y disco en 1.0. El historial de los tres recursos sí se recopila desde esta fase; el cálculo de disco puede evaluarse como propuesta de diseño sin activar sobreasignación de disco.

Las pruebas del módulo deben cubrir: 24 horas con cobertura completa y con huecos; franjas sin evidencia; picos simultáneos; aumento y reducción de ratios; CPU nominal de 200 % con demanda real admisible; presión de RAM; crecimiento y agotamiento del pool; datos vencidos; cambio de versión durante la admisión; y dos solicitudes concurrentes sin doble reserva. Una recomendación de disco superior a 1.0 no debe modificar el límite efectivo de implementación. Los resultados deben contrastar previsión, uso posterior y duración de sobrecargas. Estos casos son pruebas previstas, no resultados ya obtenidos.

### 4.7.8 Calibración de Sobreasignación

Propósito y contrato. calibrar_sobreasignacion(alcance, ventana, perfiles, horizonte, politica) analiza el historial de CPU, RAM y disco y devuelve recomendaciones por host o grupo homogéneo de CPU y por pool de disco. Alcance incluye clúster, zona e inventario; horizonte expresa la vida prevista de las cargas y el tiempo de respuesta operativa. No se mezclan hosts de distinta capacidad ni pools compartidos como si fueran independientes. La función no crea VMs, no reserva capacidad y no cambia por sí sola el hipervisor.

Activación y evidencia. El análisis comienza tras al menos 24 horas de observación. Luego se recalcula cada día y tras cambios de hardware, carga, reservas o alertas. El informe distingue edad del historial, cobertura por franja, calidad y representatividad. Sin el día mínimo devuelve EVIDENCIA_INSUFICIENTE; con un día puede emitir una propuesta PROVISIONAL. Las franjas ausentes se evalúan a demanda completa de CPU y con crecimiento de disco conservador. La ventana máxima sigue en 28 días y los datos posteriores sirven para validar la propuesta; no se exige esperar siete días para emitirla.

Procedimiento de CPU. Se ensaya una lista finita de ratios candidatos autorizada por el administrador, con 1.0 como referencia y 2.0 como valor inicial del proyecto. Para cada candidato se reconstruyen mezclas de carga representativas hasta su techo nominal, con series sincronizadas, reservas y picos conocidos. Si el conjunto de pruebas no alcanza ese compromiso o no representa sus cargas, no respalda un aumento hasta ese ratio. Se comprueban el techo nominal, R_h ≤ 0.85 C_h, RAM, disco, red, espera y latencia. Para nuevas cargas sin perfil se usa la demanda completa. No se calcula un ratio como el inverso de la utilización media ni se duplica una traza sin justificar su correlación. El máximo candidato que cumple todos los escenarios exigidos constituye una recomendación acotada a esas cargas y a ese horizonte; no acredita cualquier combinación futura de flavors.

Expresión de CPU. Para una mezcla evaluada A, V(A) es la suma de vCPU y C_neta la capacidad elegible después de las reservas de CPU. Su ratio nominal requerido es r_req(A) = V(A) / C_neta. Una mezcla solo aporta evidencia si supera todos los filtros reales y previstos. r_cpu_sugerido es el mayor candidato cuya envolvente de cargas declarada supera esos filtros; el informe registra también V(A), R_h y los casos de rechazo. El plan de cada nuevo slice se evalúa de nuevo aunque cumpla el ratio sugerido. Sin evidencia para un valor superior se sugiere 1.0 o la reducción necesaria; si ni 1.0 resulta admisible, se bloquean nuevas admisiones.

Procedimiento de disco. Para cada pool se compara el compromiso virtual D_virt con D_neto y se proyecta la ocupación física durante todo el horizonte T. La condición física es U_actual + G(T) + O_nueva ≤ D_total − M, donde G(T) incluye el crecimiento conservador de discos existentes y propuestos; O_nueva reúne imágenes, snapshots y metadatos aún no incluidos; M comprende reserva y margen operativo. Cada componente se cuenta una sola vez. La estimación utiliza tasas positivas y picos de escritura, no cancela crecimiento con borrados ni presupone que un borrado libere bloques físicos. El margen cubre crecimiento durante detección y respuesta, incertidumbre y al menos 1 GiB.

Expresión de disco. Cada candidato se ensaya con compromisos virtuales hasta su techo y crecimiento compatible con esa ocupación; el estado actual aislado no acredita un techo mayor. Debe cumplir D_virt ≤ D_neto × r_disco y la condición física anterior, además de los límites de E/S. r_disco_sugerido es el mayor candidato válido para los perfiles, horizonte y controles declarados. Un día de historial permite la primera estimación, pero no acredita el crecimiento de toda la vida del slice. Si no existe previsión fiable o los huéspedes pueden llenar sus discos antes de una respuesta eficaz, se considera ese llenado completo y no se propone un ratio superior a 1.0. Un disco thin no constituye evidencia suficiente. En implementación se fija r_disco_efectivo = 1.0 aunque la recomendación de diseño sea mayor.

Papel de RAM. Su historial verifica presión, picos, swap y sobrecarga del host para ajustar reservas y descartar mezclas de CPU o disco inviables. r_ram_sugerido = r_ram_efectivo = 1.0. Un consumo bajo durante un día no garantiza recuperación de páginas ni respaldo para un pico simultáneo; por eso no se propone un ratio bajo de sobreasignación como 1.1. Esta restricción pertenece al diseño y a la implementación.

Salida y aprobación. Cada resultado incluye calibration_id, fecha, ventana, cobertura, estado de evidencia, alcance, perfiles, horizonte, reservas, ratios actuales y sugeridos, límites ensayados, motivos, métricas de rechazo y versión de política. Se distinguen ratio sugerido, ratio aprobado y ratio efectivo. La aprobación administrativa y la comprobación del adaptador preceden a cualquier uso en admisión. La política se reevalúa al día siguiente o antes si cambian sus supuestos. Una alerta, pérdida de cobertura o cambio de carga invalida su evidencia; la admisión aplica el modo conservador hasta nueva evaluación.

Ejemplo de CPU. Con C_neta = C_h = 4 CPU equivalentes, una mezcla de ocho vCPU requiere ratio 2.0. Si su percentil 99 agregado es 2.9 y el pico conocido es 3.2, R_h = 3.2 ≤ 3.4; podría respaldar ese candidato si también cumplen RAM, disco, red, salud y consumo actual. Si otra mezcla de doce vCPU requiere ratio 3.0 y alcanza R_h = 3.8, ese candidato se descarta. El ejemplo ilustra el procedimiento; no representa una medición del clúster ni garantiza que ocho vCPU de cualquier carga sean admisibles.

Ejemplo de disco. Un pool de 20 GiB con 2 GiB de reserva y margen tiene 18 GiB netos. Un compromiso de 27 GiB requiere ratio 1.5. Solo puede sustentar una recomendación de diseño si U_actual + G(T) + O_nueva ≤ 18 GiB durante todo T y existe capacidad de respuesta suficiente. Si el llenado posible alcanza 27 GiB sin control, se descarta 1.5. La implementación conserva el techo virtual de 18 GiB con ratio 1.0.

### 4.7.9 Función objetivo y modelo de optimización

Objetivo operativo. Maximizar el número de hosts de cómputo que quedan sin VMs de tenant después de colocar el slice completo. De forma equivalente, minimizar los hosts ocupados y, con destinos existentes fijos, los hosts adicionales que se ocupan. La admisibilidad es obligatoria: el algoritmo no sacrifica RAM, disco, conectividad o riesgo para mejorar este valor. Un host libre puede conservar servicios del sistema y permanecer encendido; el objetivo cuantifica consolidación, no kWh ni ingresos.

Variables y alcance. I contiene las VMs nuevas del slice; H, los hosts del clúster y la zona de la solicitud. x_ih vale 1 si la VM i se asigna al host h; y_h vale 1 si el host queda con alguna VM de tenant; e_h indica ocupación previa. Las VMs y reservas existentes conservan su destino. Los hosts no admisibles tienen x_ih = 0 y aportan solo una constante al objetivo. Las VMs nuevas se asignan todas o se rechaza el slice completo.

máx Z(x,y) = Σ_h (1 − y_h) = \|H\| − Σ_h y_h, con x_ih, y_h ∈ {0,1}.

Se exige Σ_h x_ih = 1 para cada VM; x_ih ≤ y_h; e_h ≤ y_h ≤ e_h + Σ_i x_ih; y x_ih ≤ a_ih. El parámetro a_ih expresa compatibilidad y elegibilidad tras verificar zona, salud, imagen y telemetría reciente. El valor Z es un número de hosts; una ganancia de una unidad equivale a un host adicional sin VMs. Minimizar Σ_h y_h en el solver produce el mismo placement óptimo que maximizar Z. \[8, 9\]

Relación con la imagen de mochila. Si todas las VMs son obligatorias, Σ_h Σ_i v_i x_ih = Σ_i v_i: el beneficio total de la imagen es constante y no distingue placements. Por eso se usa el costo de ocupar hosts. La restricción de exclusividad debe sumar sobre hosts: Σ_h x_ih = 1 por VM; no sobre las VMs de un host. Si en el futuro se seleccionan solicitudes opcionales, se necesita una variable de admisión por slice y una prioridad explícita; maximizar hosts libres sin exigir admisión permitiría la solución trivial de rechazar todo.

Restricciones contables. V_h + Σ_i vCPU_i x_ih ≤ C_neta,h r_cpu,h; M_h + Σ_i RAM_i x_ih ≤ RAM_neta,h; D_p + Σ_h∈H_p Σ_i disco_i x_ih ≤ D_neto,p r_disco,p. V_h, M_h y D_p incluyen compromisos existentes y pendientes una sola vez. H_p contiene los hosts que usan el pool p. Los ratios son efectivos y quedan fijos durante cada cálculo: CPU configurable, RAM 1.0 y disco 1.0 en implementación. La capacidad física de disco y su crecimiento se verifican además según 4.7.8. Las restricciones de puertos, cuotas, RAM disponible y red completan la admisión; si el plan de red cambia, debe revalidarse antes de confirmar.

Restricción estocástica. Para la franja b y el escenario sincronizado ω se utiliza S_hbω(x) = B_hbω + L_hbω + Σ_i X_ibω x_ih. B es el fondo; L reúne la demanda de VMs y reservas existentes; X representa las VMs nuevas. Se exige Q_0.99(S_hb(x)) ≤ 0.85 C_h y K_hb(x) ≤ 0.85 C_h para cada franja relevante. Los hosts cuya carga previa ya impide añadir demanda se excluyen antes del cálculo. Las series conservan los picos simultáneos; el ratio no aumenta C_h. Un cambio de estado actual o de política invalida la instantánea.

Formulación empírica para el solver. Con N_b escenarios de igual peso y percentil por rango más próximo, Q_0.99 es el dato de orden ⌈0.99 N_b⌉. Una formulación lineal entera utiliza z_hbω binaria, S_hbω(x) ≤ 0.85 C_h + M_hbω z_hbω y Σ_ω z_hbω ≤ ⌊0.01 N_b⌋. M_hbω es una cota superior válida y ajustada del exceso posible, calculada con los límites de carga; no representa memoria RAM. Los escenarios de picos conocidos se exigen sin excepciones. Con 60 bloques por franja, el percentil empírico 99 es el máximo y no permite excepciones: todas las filas de CPU son lineales sin variables z. Este hecho facilita la prueba siguiente, pero no certifica un percentil poblacional con un día de datos.

Energía y valor económico. La consolidación puede facilitar una política futura de bajo consumo, pero y_h describe ocupación y no el estado eléctrico. El ahorro sería E_ref − E_plan en kWh durante el mismo horizonte y con la misma carga atendida, con potencia por estado, utilización y costo de transiciones medidos. El costo evitado requeriría además una tarifa; la ganancia financiera necesitaría ingresos y costos de operación. Esos datos no constan en esta evaluación, por lo que no se asignan watts, soles ni porcentajes de ahorro al resultado.

Papel de BFD y del modelo estocástico. BFD aproxima el objetivo: cada elección de un host ya ocupado evita incrementar Σ_h y_h; el mejor ajuste reduce el espacio residual y puede facilitar la consolidación posterior. Los perfiles estocásticos determinan qué combinaciones son admisibles según su demanda conjunta. El término pertinente es optimización discreta y cuantificación del objetivo; no se redondea una solución continua. La heurística no garantiza el máximo Z ni elimina el carácter combinatorio. Su calidad se mide contra un óptimo certificado mediante Δhosts = hosts_BFD − hosts_óptimo y con la tasa de solicitudes factibles que BFD no resuelve.

### 4.7.10 Evaluación reproducible con solver

Se ejecutó el 31 de octubre de 2026 una prueba sintética de la función objetivo con scipy.optimize.milp y HiGHS. Se ensayaron 40 instancias: diez por tamaño y tres repeticiones por instancia, para 120 ejecuciones de cada método. Las semillas fueron 20261031 a 20261040 por tamaño. Se excluyeron importación, generación de datos y una ejecución previa de calentamiento. El entorno fue Linux, Python 3.12.14, SciPy 1.17.0, NumPy 2.3.5 y CPU AMD EPYC 9V74; HiGHS usó un hilo, presolve, brecha relativa solicitada de cero y límite interno de 3 s por ejecución. El entorno es compartido, no un worker VNRT. \[8, 10\]

Entradas y alcance. Cada host sintético tiene 4 CPU de referencia, techo de 8 vCPU, 2.8 GiB de RAM neta, 18 GiB de disco neto, 12 puertos virtuales y 100 Mbit/s. Las VMs usan 1 o 2 vCPU, 0.5/0.75/1 GiB de RAM, 2/3/4 GiB de disco, dos puertos y 10/20/30 Mbit/s. Se usan 24 franjas con 60 escenarios de un minuto por franja y tres escenarios adicionales de estrés, con un factor temporal común para conservar dependencia. Parte de las instancias incluye una VM previa fija, incompatibilidades o un host con telemetría vencida. Se fijan ratios CPU 2.0, RAM 1.0 y disco 1.0. Son perfiles artificiales; no equivalen a 24 horas de monitoreo real ni validan la calibración del clúster.

El modelo compara exactamente el mismo objetivo y los mismos límites de la prueba que BFD. RAM disponible y admisibilidad de E/S se presuponen válidas dentro de la capacidad sintética; la red se reduce a puertos y ancho de banda aditivos, con almacenamiento local por host. No se prueban topologías de red completas, pools compartidos, APIs, reservas concurrentes ni despliegues. Los casos de 8 y 12 hosts son escenarios de escalabilidad, no inventario disponible. El código y las entradas completas acompañan este documento en G5_Evaluacion_Placement_Solver.zip.

Tiempos medidos. La media es t̄ = (1/R) Σ_r t_r. Se cronometra cada intento con perf_counter. El total MILP incluye construcción de matriz, llamada al solver y comprobación independiente de la solución devuelta. BFD mide el cálculo del plan; su comprobación independiente queda fuera de ese reloj. No se incluyen adquisición de métricas, red ni despliegue, y las fronteras de medición no son idénticas. La tabla incluye intentos factibles, inviables y detenidos por tiempo; no es el tiempo medio hasta certificar el óptimo en todos los casos.

| **Hosts / VMs** | **MILP media ms** | **MILP P95 ms** | **BFD media ms** | **Óptimo / inviable / límite** |
|-----------------|-------------------|-----------------|------------------|--------------------------------|
| 3 / 6           | 63.04             | 108.60          | 0.208            | 8 / 2 / 0                      |
| 4 / 9           | 476.93            | 1523.98         | 0.373            | 6 / 4 / 0                      |
| 8 / 18          | 2854.43           | 3131.71         | 1.105            | 0 / 1 / 9                      |
| 12 / 27         | 3254.54           | 3321.89         | 2.470            | 0 / 0 / 10                     |

Cada fila resume 30 mediciones; los tres recuentos finales corresponden a diez instancias distintas. P95 es el percentil descriptivo de los tiempos de ejecución, distinto del percentil 99 de demanda de CPU. Si se cuentan solo ejecuciones con óptimo certificado, las medias totales fueron 73.78 ms para 3 hosts/6 VMs y 481.13 ms para 4 hosts/9 VMs. No existe esa media para los dos tamaños mayores, pues ninguna instancia recibió certificado de optimalidad dentro del límite. El límite interno de 3 s no es un plazo duro para todo el proceso.

Calidad observada. De 14 instancias con óptimo certificado, BFD produjo un plan en 13: coincidió con el óptimo en 12 y usó un host adicional en una. En la restante no encontró un placement factible. En los 40 casos, BFD devolvió 26 planes; en cuatro de sus rechazos el solver sí encontró un plan factible, aunque solo uno tenía óptimo certificado. Siete casos tuvieron inviabilidad certificada y tres rechazos quedaron sin resolución. Los 19 casos detenidos por tiempo no permiten afirmar optimalidad; algunos sí incluyen una solución factible. Los estados, incumbentes y cotas constan en raw.json.

Control independiente. Cada plan devuelto se verificó contra las capacidades, compatibilidades y todos los escenarios de CPU. Tres instancias pequeñas adicionales coincidieron con enumeración completa de las 3⁵ asignaciones posibles por instancia. También se comprobó un contraejemplo: con capacidad de admisión 3.4 CPU, fondo de 0.2 y seis picos simultáneos de 1.92, 1.60, 0.96, 0.64, 0.64 y 0.64 CPU, BFD ocupa tres hosts. El solver usa dos con grupos (1.92, 0.64, 0.64) y (1.60, 0.96, 0.64), cuyo total más fondo es 3.4 por host. Con solo dos hosts, BFD rechaza ese mismo caso factible. Los perfiles del contraejemplo varían en el tiempo y conservan esos picos conjuntos.

Conclusión de diseño. La prueba respalda BFD como primer intento de baja latencia para aproximar la consolidación, pero no como garantía de óptimo ni como prueba de falta de capacidad. El componente estocástico aporta el filtro de riesgo; no corrige por sí solo decisiones voraces deficientes. En clústeres pequeños, estos tiempos también hacen razonable evaluar el solver como respaldo si BFD falla, dentro del plazo global. Si el solver termina sin certificado, se distingue solución factible, inviabilidad demostrada y estado no resuelto. Cualquier respaldo debe conservar ratios, restricciones, atomicidad del slice y revalidación de reservas; su integración sigue pendiente.

La validación posterior requiere trazas reales de CPU, RAM y disco, mediciones fuera de la ventana de ajuste, estado efectivo del proveedor y tiempos en el entorno objetivo. El ahorro de energía solo podrá cuantificarse con un modelo de potencia validado y acciones reales sobre el estado de los hosts. Los resultados de esta sección no acreditan ahorro eléctrico, disponibilidad en producción ni cumplimiento de la validación de implementación EX2.

# 5. Flujos integrados del sistema

Los diez flujos F1–F10 conservan las relaciones del HLD y se amplían a R3 y R4. Los diagramas de ejecución detallan la rama Linux; en OpenStack, los pasos de cómputo, red, imágenes y consola corresponden al Driver OpenStack descrito en 4.6. Los flujos expresan el diseño objetivo y no acreditan por sí mismos endpoints o servicios ya integrados. F3 y F9 concentran planificación, reservas, ejecución y verificación; la sección 6 distingue el código Linux disponible de la integración de fase 2.

## 5.1 Convenciones

Los diagramas siguen el formato de secuencia por carriles: cada columna es un módulo y el tiempo avanza hacia abajo. Las flechas **verdes continuas** son llamadas síncronas REST/HTTPS y las **verdes discontinuas**, sus respuestas; las **rojas** son mensajes asíncronos que atraviesan la cola de operaciones (punto rojo); las **azules**, telemetría o supervisión; y las **grises punteadas**, acceso a datos. Los recuadros amarillos son acciones internas de un módulo. Los marcos rojos **«alt»** muestran el camino ante un rechazo o fallo, con pasos marcados con letra (por ejemplo, 17a); los marcos ámbar **«opt»**, pasos opcionales.

La tabla resume las responsabilidades funcionales que intervienen en los flujos; cada proveedor las materializa mediante su driver, con los controles de autorización, reservas y recuperación.

| **Módulo**                    | **Funciones que intervienen en los flujos**                                                                                             |
|-------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------|
| **UI / CLI**                  | Captura de solicitudes y plantillas · seguimiento de estados y métricas · acceso a consolas.                                            |
| **API Gateway**               | Entrada y validación de solicitudes · contexto de seguridad · enrutamiento y respuesta.                                                 |
| **IAM Service**               | Identidad y sesiones · roles y pertenencia a cursos · permisos por recurso y accesos temporales.                                        |
| **Topology Manager**          | Catálogo y versiones de plantillas · validación de la topología · modelo de despliegue.                                                 |
| **Slice Manager**             | Validación de solicitudes · planificación del ciclo de vida · admisión y reservas · trabajos y estados · recuperación y reconciliación. |
| **Networking Service**        | Segmentación y direccionamiento · conectividad L3 · políticas y aislamiento · construcción del plan de red.                             |
| **VM Placement**              | Calibración histórica de ratios; filtros por clúster y zona, BFD con datos actuales y perfiles; plan completo y rechazo explicado.      |
| **IMS**                       | Catálogo de imágenes QCOW2 · distribución y caché en workers · limpieza de bases sin referencias.                                       |
| **Cola de operaciones**       | Canal de trabajos · canal de resultados · reentregas y mensajes no procesables.                                                         |
| **PlatManager**               | Recepción y diario de ejecución · ejecución por dependencias · selección del driver · verificación y compensación.                      |
| **Drivers Linux / OpenStack** | Acciones QEMU/OVS por agente o recursos Nova/Neutron/Glance; estados, identificadores y consola del proveedor.                          |
| **Monitoreo**                 | Recolección cada 5 s; estado vigente, calidad, histórico y cobertura para calibración y admisión.                                       |
| **Persistencia SQL / NoSQL**  | Identidad, catálogos, slices, reservas y operaciones (SQL) · series de métricas e históricos (NoSQL).                                   |

Resumen de los flujos y de los requerimientos con los que se relacionan:

| **Flujo** | **Propósito**                                               | **Requerimientos**  |
|-----------|-------------------------------------------------------------|---------------------|
| **F1**    | Inicio de sesión y autorización de cada acción              | R1, R1B             |
| **F2**    | Creación, importación y consulta de plantillas e imágenes   | R1B                 |
| **F3**    | Despliegue completo de un slice                             | R1C, R2, R3, R4, R5 |
| **F4**    | Consulta de estado y seguimiento                            | R1B, R1C            |
| **F5**    | Acceso a la consola de una VM                               | R1B, R2, R3         |
| **F6**    | Monitoreo continuo y consulta de históricos                 | R1, R2, R3, R4      |
| **F7**    | Modificación de un slice existente                          | R1C, R1B, R4        |
| **F8**    | Detención y reanudación de un slice                         | R1C, R2, R3         |
| **F9**    | Eliminación y liberación de recursos                        | R1C, R2, R3, R5     |
| **F10**   | Recuperación ante la caída del plano de control (extensión) | R1                  |

## 5.2 F1 - Inicio de sesión y autorización por acción

**Objetivo.** Garantizar que solo usuarios activos accedan al orquestador y que cada acción se autorice según rol, curso y relación con el recurso. La sesión acredita quién es el usuario; IAM y el servicio de destino deciden qué puede hacer sobre cada slice.

> **Usuarios:** Administrador, Profesor y Alumno. **Precondición:** cuenta creada por el Administrador y vinculada a sus cursos. **Resultado:** sesión con vencimiento y decisiones de acceso auditadas.

![F1: inicio de sesión y autorización por acción](media/image6.png)

*Figura 5.1. F1 · Inicio de sesión y autorización por acción.*

> • **Pasos 1→6 · Inicio de sesión.** Las credenciales llegan por HTTPS al API Gateway, que valida su formato y las dirige a IAM. IAM compara la credencial con su hash, revisa el estado de la cuenta y obtiene roles y cursos. Si la identidad no es válida, no se emite token (5a); si lo es, entrega una sesión con vencimiento.
>
> • **Pasos 7→12 · Cada acción posterior.** La solicitud viaja con el token (y con Idempotency-Key si modifica un slice). El Gateway nunca acepta el rol declarado por el cliente: IAM valida la sesión, consulta la asignación vigente y registra la decisión. Sin permiso se responde 401 o 403 sin tocar recursos (10a); con permiso, la solicitud se enruta con la identidad propagada.
>
> • **Paso 13 y opción 14–15.** El servicio de destino revalida su propio recurso, porque ocultar un botón en la UI no reemplaza la autorización. La administración de cuentas solo procede con rol Administrador y queda auditada.

## 5.3 F2 - Creación, importación y consulta de plantillas

**Objetivo.** Permitir que el profesor defina, valide, versione, importe y exporte plantillas de laboratorio (como las topologías lineal y anillo) y mantener el catálogo de imágenes QCOW2 que referencian. Guardar una plantilla no despliega VMs ni reserva recursos.

> **Usuarios:** Profesor; Administrador para imágenes. **Precondición:** sesión válida y pertenencia al curso. **Resultado:** plantilla versionada e inmutable, reutilizable por F3.

![F2: creación, importación y consulta de plantillas](media/image11.png)

*Figura 5.2. F2 · Creación, importación y consulta de plantillas.*

> • **Pasos 1→7 · Recepción y autorización.** El profesor define el grafo (VMs, interfaces, enlaces, imagen y recursos) o importa un JSON. El servidor repite todas las validaciones de la UI, IAM confirma que es profesor del curso y Topology Manager consulta a IMS si las imágenes referenciadas existen.
>
> • **Paso 8 · Validación.** Topology Manager comprueba identificadores únicos, extremos existentes, interfaces no duplicadas y recursos positivos, y distingue errores de condiciones intencionales de la práctica (un anillo o un nodo aislado son válidos). Si la definición es inválida, se devuelven los errores y puede guardarse un borrador (8a–8b).
>
> • **Pasos 9→14 · Versión y consulta.** Cada cambio crea una versión inmutable con huella de contenido; las versiones que ya usan otros despliegues no se alteran y los conflictos de edición se detectan. La exportación entrega el JSON sin credenciales ni identificadores de ejecución.
>
> • **Opción 15→17 · Imágenes.** El administrador importa una imagen QCOW2; IMS valida formato e integridad por hash y la publica solo cuando la transferencia terminó. Una imagen corrupta o inexistente nunca se sustituye en silencio.

## 5.4 F3 - Despliegue completo de un slice

**Objetivo.** Transformar la solicitud de un profesor en un slice operativo: VMs, discos, redes y accesos creados en los workers, aislados de otros slices y verificados antes de declararlos disponibles. El recorrido se aplica a cada alumno; un lote genera operaciones independientes, de modo que el fallo de una instancia no destruye las que ya funcionan.

> **Usuarios:** Profesor o Administrador. **Precondición:** sesión válida, plantilla o topología definida e imágenes en el catálogo. **Resultado:** slice READY con sus recursos vinculados a slice_id y operation_id, o rechazo explicado sin residuos.

El flujo tiene dos fases separadas por la cola. En la **parte 1**, síncrona, el orquestador decide si puede desplegar y reserva lo necesario; responde en segundos con HTTP 202. En la **parte 2**, asíncrona, PlatManager ejecuta el plan en los workers, lo verifica y comunica el resultado.

### Parte 1: Solicitud, planificación y admisión

![F3 parte 1: solicitud, planificación y admisión del slice](media/image14.png)

*Figura 5.3. F3 · Despliegue, parte 1: solicitud, planificación y admisión.*

| **Paso** | **Interacción**                          | **Descripción**                                                                                                                                                                                                                |
|----------|------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1→2      | UI/CLI → API Gateway · IAM               | El profesor solicita plantilla, curso, usuarios, clúster, zona, perfil y duración con Idempotency-Key. Gateway valida el esquema e IAM comprueba identidad y acción.                                                           |
| 2a       | API Gateway → UI/CLI                     | Solicitud inválida (400), sin token (401) o sin permiso (403): se rechaza sin reservar nada.                                                                                                                                   |
| 3→4      | Gateway → Slice Manager                  | Slice Manager recibe la solicitud con su correlation_id, verifica asignación, versión e idempotencia y registra slice_id y operation_id. El slice queda DEFINED.                                                               |
| 4a       | Slice Manager → UI/CLI                   | Si la misma Idempotency-Key ya existe, devuelve la operación original en lugar de crear otra.                                                                                                                                  |
| 5→6      | Slice Manager ↔ Topology Manager         | Recupera la versión fija de la plantilla y recibe un modelo inmutable con VMs, interfaces, enlaces e imágenes.                                                                                                                 |
| 7→8      | Slice Manager ↔ Networking               | Networking propone segmentos, VLAN y direccionamiento candidatos. Son propuestas: aún no están reservadas.                                                                                                                     |
| 9→12     | Slice Manager ↔ VM Placement ↔ Monitoreo | Placement evalúa todas las VMs con ratios efectivos, inventario, compromisos, métricas vigentes y perfiles. Revalida la evidencia de calibración y devuelve destinos y causas de descarte dentro de la zona; no crea recursos. |
| 13→14    | Slice Manager ↔ Networking               | Con las ubicaciones, Networking completa el plan: distingue enlaces locales de enlaces entre workers, que transportan su VLAN entre servidores.                                                                                |
| 15→16    | Slice Manager ↔ IMS                      | IMS indica, por worker, si la imagen base ya está en caché o debe distribuirse.                                                                                                                                                |
| 17       | Slice Manager                            | Slice Manager revalida y reserva atómicamente el plan G5 completo. Guarda plan y trabajo pendiente; en OpenStack se revalida además contra Nova antes de crear recursos.                                                       |
| 17a→17b  | Slice Manager → UI/CLI                   | Ante un conflicto de reserva se revierte la transacción y se replanifica; si no hay solución válida, se rechaza con 409 sin recursos parciales.                                                                                |
| 18       | Slice Manager → UI/CLI                   | HTTP 202 con operation_id; el slice pasa a PROVISIONING. El 202 confirma el registro del trabajo, no que el laboratorio esté listo.                                                                                            |

### Parte 2: Ejecución, verificación y resultado

![F3 parte 2: ejecución, verificación y resultado del slice](media/image20.png)

*Figura 5.4. F3 · Despliegue, parte 2: ejecución, verificación y resultado.*

| **Paso** | **Interacción**                    | **Descripción**                                                                                                                                                                                                                          |
|----------|------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 19→20    | Slice Manager → PlatManager (cola) | El trabajo se publica desde la outbox; si la cola cae, queda pendiente sin perderse. PlatManager lo registra en su diario antes de confirmar la recepción, de modo que una reentrega o un reinicio no lo duplican.                       |
| 21→22    | PlatManager → Driver → workers     | Verifica conexiones y capacidades del backend: QEMU/KVM y OVS en Linux; APIs, servicios y recursos del proyecto en OpenStack.                                                                                                            |
| 23→24    | PlatManager → Driver → workers     | Si falta la imagen base en el worker, se copia y verifica; luego se crea un overlay QCOW2 por VM que referencia a la base.                                                                                                               |
| 25→26    | PlatManager → Driver → workers     | Se crean las interfaces TAP y los puertos OVS de cada VM en su segmento (VLAN); en el gateway, NAT y publicaciones si el plan los requiere.                                                                                              |
| 27→29    | PlatManager → Driver → workers     | Linux arranca QEMU por el agente del prototipo; libvirt es la alternativa del HLD. OpenStack crea servidores Nova sobre puertos Neutron y comprueba el host real. Registra IDs por VM.                                                   |
| 30→31    | PlatManager ↔ Driver               | Se verifica el estado real de dominios, conexiones y aislamiento: la aceptación de un comando no basta para declarar éxito.                                                                                                              |
| 31a→31b  | PlatManager → Slice Manager        | Si la preparación no se confirma, se envía la evidencia y Slice Manager decide: reintento acotado (solo para fallos temporales), compensación o atención.                                                                                |
| 31c→31d  | PlatManager → Driver               | La compensación retira en orden inverso solo los recursos exclusivos de la operación. Sin residuos, la operación termina FAILED; con efectos inciertos, el slice queda DEGRADED y la operación NEEDS_ATTENTION, y conserva las reservas. |
| 32→33    | PlatManager → Slice Manager (cola) | Los resultados llegan por paso. Slice Manager descarta duplicados, convierte reservas en asignaciones sin contarlas dos veces y marca READY y SUCCEEDED.                                                                                 |
| 34→36    | UI/CLI ↔ Slice Manager · Monitoreo | La UI consulta la operación por su operation_id hasta el estado final. La telemetría sigue su ruta independiente y no reserva capacidad.                                                                                                 |

### Estados, controles y fallos

| **Momento**                        | **Slice**    | **Operación**             |
|------------------------------------|--------------|---------------------------|
| Solicitud registrada (4)           | DEFINED      | PENDING                   |
| Admisión confirmada (17–18)        | PROVISIONING | PENDING → RUNNING         |
| Reintento o compensación (31b–31c) | PROVISIONING | RETRY_WAIT / COMPENSATING |
| Verificación correcta (33)         | READY        | SUCCEEDED                 |
| Fallo compensado sin residuos      | FAILED       | FAILED                    |
| Fallo con efectos inciertos        | DEGRADED     | NEEDS_ATTENTION           |

> • **Puntos de control:** idempotencia (paso 4), admisión atómica (17), registro durable en outbox y diario (17 y 20), verificación del estado real (30–31) y confirmación sin duplicados (33).
>
> • **Fallos sin reintento:** un permiso o una plantilla inválidos se rechazan antes de reservar; reintentar no cambiaría el resultado.
>
> • **Timeout después de crear:** se busca la VM por su identificador estable; si existe se registra, si no existe se reintenta y si no se sabe se conserva la incertidumbre, sin crear una segunda copia.
>
> • **Cola o ejecutor caídos:** la outbox reenvía lo pendiente y el diario permite retomar; el receptor deduplica por message_id. Una caída de Monitoreo excluye destinos sin datos recientes, pero no apaga VMs.

## 5.5 F4 - Consulta de estado y seguimiento

**Objetivo.** Consultar el avance de un slice o de una operación sin iniciar acciones sobre la infraestructura, con acceso de cada usuario solo a lo que le corresponde.

> **Usuarios:** Administrador, Profesor y Alumno. **Precondición:** sesión válida y alcance sobre el recurso. **Resultado:** estado autorizado y trazable, con su instante de actualización.

![F4: consulta de estado y seguimiento](media/image2.png)

*Figura 5.5. F4 · Consulta de estado y seguimiento.*

> • **Pasos 1→4 · Autorización.** La UI consulta un slice o una operación por su identificador e IAM determina el alcance: el alumno ve sus slices, el profesor los de su curso y el administrador todos. Sin permiso se responde 403 o 404, sin exponer datos (3a).
>
> • **Pasos 5→9 · Consulta.** Slice Manager lee de SQL el estado lógico, los pasos confirmados y el error visible, y lo devuelve con su instante de actualización. La UI distingue operación pendiente, completada y acceso disponible. Una operación permanece disponible para consulta aunque la cola o un driver estén caídos.
>
> • **Opción 10–11.** El consumo de recursos se consulta a Monitoreo dentro del alcance autorizado (F6).

## 5.6 F5 - Acceso a la consola de una VM

**Objetivo.** Dar acceso temporal a la consola de una VM asignada sin entregar credenciales de la infraestructura ni exponer los puertos VNC de los servidores.

> **Usuarios:** Alumno; Profesor o Administrador para soporte. **Precondición:** slice READY y VM asignada al usuario. **Resultado:** sesión limitada a una VM y a la vigencia de su token.

![F5: acceso a consola virtual de VM](media/image7.png)

*Figura 5.6. F5 · Acceso a la consola de una VM.*

> • **Pasos 1→5 · Autorización.** La UI solicita la consola de una VM. IAM valida que la VM esté asignada al usuario y audita la solicitud (sin permiso, 3a); Slice Manager comprueba que el slice esté en un estado compatible (READY, nunca DELETING).
>
> • **Pasos 6→11 · Preparación.** Se registra un trabajo de acceso; el driver ubica el puerto VNC del dominio en su worker y devuelve una referencia temporal. Las credenciales privadas quedan en el adaptador; la UI recibe un token con vencimiento.
>
> • **Pasos 12→15 · Sesión.** El proxy noVNC revalida usuario, VM y vigencia (un token vencido se rechaza, 13a) y abre un túnel SSH por la red de administración hacia el VNC. La sesión interactiva no atraviesa Slice Manager ni la cola. Revocar la asignación impide nuevas sesiones.

## 5.7 F6 - Monitoreo continuo y consulta de históricos

**Objetivo.** Proporcionar estado reciente para la admisión de VMs e históricos de CPU, RAM, disco y red para perfiles, diagnóstico y Calibración de Sobreasignación. Monitoreo informa; VM Placement evalúa; Slice Manager confirma reservas.

> **Usuarios:** Sistema (recolección); usuarios (consulta). **Precondición:** recolectores activos en los workers. **Resultado:** observaciones normalizadas e históricos autorizados.

![F6: monitoreo continuo y consulta de históricos](media/image19.png)

*Figura 5.7. F6 · Monitoreo continuo y consulta de históricos.*

> • **Pasos 1→3 · Recolección.** Los adaptadores recopilan muestras cada 5 s con origen, instante, unidades e identificadores de host, VM, slice y pool. Monitoreo valida calidad, actualiza el estado vigente y almacena las series y su cobertura. Un contador reiniciado, una muestra ausente o una edad superior a 15 s se marcan de forma explícita.
>
> • **Pasos 4→5a · Planificación.** VM Placement combina ratios efectivos, compromisos y telemetría vigente con perfiles por franja. La calibración recomienda ratios después de al menos un día de historial; no sustituye la aprobación ni los filtros de cada slice. CPU real \> 85 % bloquea nuevas admisiones; \> 90 % durante 30 s válidos genera OVERLOAD y revisión del perfil. La reapertura exige dos minutos bajo 80 %, datos vigentes, recálculo y ausencia de otros bloqueos. No hay migración automática.
>
> • **Pasos 6→10 · Históricos.** Gateway e IAM autorizan las consultas. Monitoreo devuelve series, agregados, huecos y cobertura. Calibración utiliza el historial de CPU, RAM y disco para proponer ratios de CPU y disco y justificar RAM 1.0. La UI muestra estado actual, causa de bloqueo, ratio efectivo y recomendación pendiente con su evidencia. Las recomendaciones de disco permanecen en el diseño durante esta fase.

## 5.8 F7 - Modificación de un slice existente

**Objetivo.** Aplicar cambios a un slice desplegado (agregar o quitar VMs, enlaces o recursos) sin alterar la versión activa hasta verificar el resultado. Editar una plantilla (F2) no altera los slices existentes.

> **Usuarios:** Profesor responsable o Administrador. **Precondición:** slice READY y versión esperada vigente. **Resultado:** nueva configuración verificada, o la anterior conservada si la compensación lo permite.

![F7: modificación de un slice existente](media/image17.png)

*Figura 5.8. F7 · Modificación de un slice existente.*

> • **Pasos 1→3a · Control de versión.** Los cambios llegan con la versión que el profesor tenía al editar. Slice Manager obtiene la exclusión del slice; si otro usuario lo modificó o hay una operación incompatible, responde 409 y pide revisar los cambios.
>
> • **Pasos 4→7 · Plan incremental.** Se calcula la diferencia entre el modelo objetivo y el actual; Networking y Placement planifican solo los incrementos, que se reservan sin alterar las asignaciones existentes (UPDATING).
>
> • **Pasos 8→13 · Ejecución.** Primero se crean y verifican las adiciones y después se retiran los reemplazos, para no dejar el laboratorio sin conectividad. Si el cambio no se verifica, se compensan los cambios reversibles y un resultado parcial queda DEGRADED (10a); un disco eliminado no se recupera sin copia previa (10b).

## 5.9 F8 - Detención y reanudación de un slice

**Objetivo.** Detener o reanudar las VMs de un slice sin perder discos ni configuración. Detener no es eliminar: los recursos siguen asignados.

> **Usuarios:** Profesor responsable o Administrador. **Precondición:** slice READY (detener) o STOPPED (reanudar). **Resultado:** slice STOPPED con sus asignaciones, o READY tras reanudar.

![F8: detención y reanudación de un slice](media/image12.png)

*Figura 5.9. F8 · Detención y reanudación de un slice.*

> • **Pasos 1→4 · Solicitud.** Se solicita detener o reanudar el slice. Slice Manager valida propietario, estado y ausencia de operaciones incompatibles y publica un plan sobre los recursos existentes, con sus mismos identificadores.
>
> • Pasos 5→8a · Ejecución. El driver detiene o reanuda las mismas VMs mediante el mecanismo del proveedor y consulta su estado. En Linux, el prototipo usa acciones de agente sobre QEMU; en OpenStack se utilizarán acciones de Nova. Una respuesta incierta exige reconciliación antes de repetir, sin crear VMs duplicadas ni liberar reservas.
>
> • **Pasos 9→11 · Resultado.** Se registra STOPPED o READY. La política base conserva la capacidad mientras el slice está detenido; liberarla exigiría una nueva admisión antes de arrancar.

## 5.10 F9 - Eliminación y liberación de recursos

**Objetivo.** Eliminar un slice mediante el retiro de solo sus recursos exclusivos (VMs, discos overlay, interfaces, segmentos, reglas y, si quedan sin uso, las imágenes base en la caché de cada worker), liberar la capacidad solo con evidencia y conservar su historial y auditoría.

> **Usuarios:** Profesor responsable o Administrador. **Precondición:** slice en READY, STOPPED o DEGRADED sin otra operación incompatible. **Resultado:** slice DELETED con capacidad liberada, o DELETING con los pendientes visibles.

Igual que F3, F9 tiene una **parte 1** síncrona (autorizar, bloquear y planificar; responde 202) y una **parte 2** asíncrona (ejecutar en orden inverso, verificar y liberar).

### Parte 1: Autorización, bloqueo y plan

![F9 parte 1: autorización y planificación de eliminación](media/image5.png)

*Figura 5.10. F9 · Eliminación, parte 1: autorización, bloqueo y plan.*

| **Paso** | **Interacción**            | **Descripción**                                                                                                                                                                                                                 |
|----------|----------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1→3      | UI/CLI → API Gateway ↔ IAM | Se solicita la eliminación del slice con una Idempotency-Key. IAM comprueba que sea el profesor responsable o un administrador; el alumno no puede eliminar. Una eliminación excepcional del slice de un alumno queda auditada. |
| 2a       | API Gateway → UI/CLI       | Sin permiso, 403; recurso inexistente o ajeno, 404. El slice no cambia.                                                                                                                                                         |
| 4→5      | Gateway → Slice Manager    | Slice Manager adquiere el bloqueo del slice en almacenamiento compartido, rechaza cambios incompatibles y marca DELETING.                                                                                                       |
| 5a       | Slice Manager → UI/CLI     | Si hay otra operación en curso, 409 por estado incompatible; si se repite la misma clave, se devuelve la operación original.                                                                                                    |
| 6        | Slice Manager → IAM        | IAM deja de autorizar nuevas sesiones de consola sobre las VMs del slice.                                                                                                                                                       |
| 7→8      | Slice Manager ↔ Networking | Networking indica qué puertos, reglas y segmentos son exclusivos del slice (se retiran) y cuáles compartidos (se preservan).                                                                                                    |
| 9→10     | Slice Manager ↔ IMS        | IMS informa, por worker, qué imágenes base usa el slice y si otras VMs aún las usan. Solo las que quedarán sin referencias son candidatas a limpieza.                                                                           |
| 11→12    | Slice Manager → UI/CLI     | El plan se construye en orden inverso al despliegue y se persiste con el trabajo pendiente (outbox). Se responde HTTP 202 con operation_id.                                                                                     |

### Parte 2: Ejecución en orden inverso y liberación

![F9 parte 2: eliminación y liberación de recursos](media/image13.png)

*Figura 5.11. F9 · Eliminación, parte 2: ejecución en orden inverso y liberación.*

| **Paso** | **Interacción**                    | **Descripción**                                                                                                                                                                                                     |
|----------|------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 13→14    | Slice Manager → PlatManager (cola) | PlatManager recibe el trabajo, lo registra en su diario y ordena los pasos según las dependencias inversas: un disco no se borra mientras una VM lo usa y una base no se borra mientras un overlay dependa de ella. |
| 15→16    | PlatManager → Driver → workers     | Se detienen y eliminan las VMs mediante el driver: procesos QEMU identificados en el prototipo Linux o servidores Nova en OpenStack. No se invoca virsh sobre VMs ajenas al adaptador.                              |
| 17→18    | PlatManager → Driver → workers     | Se eliminan los overlays QCOW2 exclusivos; la imagen base no se toca en este paso.                                                                                                                                  |
| 19→20    | PlatManager → Driver → workers     | Se retiran TAP, puertos OVS y VLAN exclusivos y, en el gateway, NAT y publicaciones del slice. Lo compartido se preserva.                                                                                           |
| 21→22    | PlatManager → Driver → workers     | Se retiran bases de caché solo sin referencias y según retención. Una imagen compartida en Glance no se elimina al borrar un slice; el catálogo tiene un ciclo de vida independiente.                               |
| 23→24    | PlatManager ↔ Driver               | Se verifica la ausencia de cada recurso: sin proceso QEMU, sin disco y sin puertos. Un recurso ya ausente cuenta como eliminado si su identidad y pertenencia están comprobadas.                                    |
| 24a→24b  | PlatManager → Slice Manager        | Si algo queda pendiente o un worker no responde, Slice Manager lanza un nuevo trabajo de limpieza o marca NEEDS_ATTENTION. El slice sigue DELETING y la capacidad incierta no vuelve al saldo.                      |
| 25→26    | PlatManager → Slice Manager        | Con la limpieza confirmada, se liberan CPU, RAM, disco, VLAN e IP de los recursos ausentes, el slice pasa a DELETED y se conserva el historial.                                                                     |
| 27→28    | UI/CLI ↔ Slice Manager             | La UI consulta la operación y obtiene SUCCEEDED con el slice DELETED.                                                                                                                                               |

## 5.11 F10 - Recuperación ante la caída del plano de control

**Objetivo. Extensión propuesta para alta disponibilidad, fuera de la implementación prevista para esta fase: si cae un nodo del plano de control, otro retoma las operaciones pendientes sin duplicar recursos ni liberar capacidad a ciegas. Supone servicios distribuidos en tres nodos físicos distintos (H1, H2 y H3) con SQL y cola replicados.**

![F10: recuperación tras caída del plano de control](media/image9.png)

*Figura 5.12. F10 · Recuperación ante la caída del plano de control (extensión propuesta).*

> • **Pasos 1→2a · Detección y protección.** Una supervisión externa retira el nodo caído del balanceo, comprueba el quorum de SQL y cola y aísla al ejecutor anterior. Sin SQL se detienen las admisiones; sin cola se conserva la outbox; sin exclusión no se reasignan operaciones.
>
> • **Pasos 3→9a · Reconciliación.** Las réplicas sanas recuperan planes, reservas y diario, publican la outbox, deduplican reentregas y consultan el estado real de los recursos. Si no puede confirmarse, se conserva la incertidumbre (NEEDS_ATTENTION) sin duplicar ni liberar.
>
> • **Pasos 10→12 · Continuación.** Slice Manager decide, PlatManager ejecuta y verifica los pendientes y el resultado vuelve a ser visible. La caída del control no apaga las VMs.

# 6. Implementación y estado de integración

## 6.1. Descripción y alcance de la implementación

<span class="mark">El ZIP adjunto contiene la implementación R2 de EX1 para slices sobre tres workers Linux. La API valida la solicitud, reserva recursos, registra un trabajo y coordina agentes remotos; el resultado se consulta por operación. Esta sección conserva su contrato y documenta la distancia respecto del diseño de fase 2.</span>

<span class="mark">El ejemplo de configuración conserva server4 como control/gateway y server1–server3 como workers de fase 1. Su uso en fase 2 exige actualizar inventario, redes, interfaces, rol de gateway y capacidades; no basta con sustituir nombres. La instalación OpenStack del laboratorio y la propuesta de alojamiento de G5 en headnode se describen separadamente en 6.10.</span>

| **Incluido en la demo**                                                          | **Fuera del alcance de esta API**                                          |
|----------------------------------------------------------------------------------|----------------------------------------------------------------------------|
| API HTTP para crear, consultar, detener, iniciar, reconciliar y eliminar slices. | API Gateway general e IAM/Keycloak integrados como microservicios.         |
| Administración de imágenes QCOW2, workers, diagnósticos y acceso noVNC.          | VM Placement automático y servicios de planificación completos.            |
| Reservas y ejecución concurrente con SQLite y cola local.                        | RabbitMQ, alta disponibilidad distribuida y ejecución sobre OpenStack/AWS. |

## 6.2. Arquitectura de implementación del Driver Linux

La configuración incluida en el ZIP utiliza server4 para API/ejecutor y gateway y server1–server3 para VMs. Es una referencia de la implementación Linux original, no un inventario de fase 2. El agente materializa recursos mediante QEMU/KVM y OVS, sin utilizar libvirt en esta ruta.

| **Elemento**               | **Ubicación y Responsabilidad**                                                                              |
|----------------------------|--------------------------------------------------------------------------------------------------------------|
| server4 — API y ejecutor   | Recibe solicitudes HTTP, valida, admite y reserva recursos; mantiene la cola local y coordina el despliegue. |
| Persistencia               | SQLite en state/cluster.db. El catálogo de imágenes base se mantiene en state/images/.                       |
| server1, server2 y server3 | Workers con QEMU/KVM, discos QCOW2, interfaces TAP y Open vSwitch.                                           |
| Gateway y OFS              | server4 aplica redes, NAT y publicaciones. OFS transporta las VLAN de cliente/proveedor mediante QinQ.       |
| Consolas                   | noVNC en server4; tokens temporales y túneles SSH hacia el VNC de cada worker.                               |
| Clientes de la API         | g5.cli, g5.demo u otro módulo que implemente el mismo contrato HTTP.                                         |

La solicitud exige worker en cada VM; la API valida capacidad sin escoger automáticamente el destino. El desarrollo de R4 debe retirar esa obligación de la solicitud de alto nivel y convertir el host en resultado del plan. También debe adaptar Store y Agent.prepare: el agente actual limita la suma de vCPU a las CPU visibles, por lo que aumentar solo la capacidad del JSON no habilita de forma coherente CPU configurable con valor inicial 2.0. RAM y disco conservan 1.0 en la implementación de fase 2; el disco configurable del HLD no se presenta como capacidad incorporada al ZIP.

## 6.3. Comunicación y autenticación de la API

La API emplea HTTP y mensajes JSON en UTF-8 para la mayor parte de las operaciones. La importación de imágenes utiliza transferencia binaria QCOW2. En el servidor, el acceso local se realiza a través de http://127.0.0.1:8085; la consola web noVNC utiliza http://127.0.0.1:6080. Para consumir estos servicios desde otro equipo se utiliza un túnel SSH, salvo que se habilite explícitamente una configuración segura de transporte remoto.

Las llamadas protegidas usan la cabecera Authorization: Bearer con un token opaco definido localmente. El servidor calcula su hash SHA-256 y lo contrasta con config/keys.json. No utiliza JWT para este servicio ni dispone de endpoints de inicio de sesión o renovación de tokens. El perfil user administra sus propios slices; admin y service pueden realizar operaciones globales, como gestionar workers e imágenes.

Las operaciones que crean, eliminan, detienen, inician o reconcilian un slice requieren además Idempotency-Key, una clave que permite reconocer solicitudes repetidas sin duplicar recursos. Cuando una operación se acepta, la API normalmente devuelve HTTP 202 y un objeto Operation. Ese código confirma la admisión y el registro del trabajo, no la finalización del despliegue.

| **Convención**       | **Comportamiento documentado**                                               |
|----------------------|------------------------------------------------------------------------------|
| Autenticación        | Bearer token opaco; solo GET /healthz es público.                            |
| Roles                | user sobre recursos propios; admin/service para operaciones administrativas. |
| Idempotencia         | Clave obligatoria en operaciones que modifican el ciclo de vida del slice.   |
| Seguimiento          | Consultar GET /v1/operations/{op} hasta SUCCEEDED o FAILED.                  |
| Seguridad de consola | Token noVNC distinto del token API; expira y autoriza una VM concreta.       |

## 6.4. Operaciones y endpoints implementados

La versión documentada expone 21 operaciones HTTP. La siguiente tabla presenta su alcance sin repetir todas las estructuras JSON y códigos de error de la referencia técnica.

| **Grupo**               | **Rutas**                                                                      | **Finalidad**                                                            |
|-------------------------|--------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| Salud y capacidades     | GET /healthz; GET /openapi.json; GET /v1/capabilities                          | Disponibilidad del proceso, contrato y capacidades configuradas.         |
| Administración de nodos | GET /v1/nodes; PATCH /v1/nodes/{node}; POST /v1/nodes/{node}/cache/gc          | Consultar workers, habilitar su admisión y limpiar cachés no utilizadas. |
| Imágenes                | GET /v1/images; PUT /v1/images/{sha256}; DELETE /v1/images/{sha256}            | Consultar, importar y retirar imágenes base del catálogo.                |
| Slices                  | GET /v1/slices; POST /v1/slices; GET /v1/slices/{sid}; DELETE /v1/slices/{sid} | Listar, crear, consultar y eliminar slices.                              |
| Ciclo de vida           | POST /v1/slices/{sid}/stop; /start; /reconcile                                 | Detener, reanudar y reconciliar slices existentes.                       |
| Observación             | GET /v1/slices/{sid}/events; GET /v1/slices/{sid}/diagnostics                  | Consultar eventos y verificar recursos reales por nodo.                  |
| Acceso y sondeo         | POST /v1/slices/{sid}/vms/{vm}/console; /probe                                 | Solicitar consola noVNC o ejecutar sondeos cerrados compatibles.         |
| Trabajos                | GET /v1/operations/{op}                                                        | Consultar el estado final o error de una operación asíncrona             |

## 6.5. Gestión de VMs, imágenes y networking

### 6.5.1. Máquinas virtuales y recursos

Una solicitud de creación incluye el nombre del slice, sus redes, las máquinas virtuales y, de forma opcional, las publicaciones externas. Cada VM declara explícitamente el worker de destino, la imagen SHA-256, la cantidad de vCPU, memoria, disco y las interfaces de red. El sistema valida el modelo y verifica la disponibilidad antes de aceptar el trabajo.

Durante el despliegue, el ejecutor prepara los discos, configura las interfaces, inicia la VM y verifica el resultado. El estado READY indica que se confirmaron los recursos QEMU y de red del host; no demuestra por sí solo que el sistema operativo invitado haya terminado su inicialización ni que el tráfico extremo a extremo funcione

### 6.5.2. Imágenes y almacenamiento

Las imágenes base QCOW2 se importan al catálogo de server4 y se identifican mediante el hash SHA-256 de su contenido. La base se distribuye a un worker cuando una VM la necesita. El sistema utiliza discos diferenciales sobre la base reutilizable, lo que evita copiar una imagen completa para cada VM. El ahorro físico de un overlay no equivale a capacidad autorizada para sobreasignar: la política de implementación reserva el tamaño virtual con ratio de disco 1.0, más las reservas y sobrecargas correspondientes.

Al eliminar una VM se retiran sus recursos exclusivos y su disco diferencial. La limpieza de las imágenes base se realiza solo cuando no existen referencias activas y se cumple la política de retención. La API permite gestionar tanto el catálogo central como la caché de los workers.

### 6.5.3. Segmentación, conectividad y acceso externo

Cada red del slice dispone de un nombre, una subred IPv4 privada y una etiqueta C-VLAN. El servicio asigna otros identificadores internos, como S-VLAN y parámetros de tránsito, y utiliza la infraestructura de OVS y OFS para transportar la segmentación mediante QinQ. La creación del segmento y sus interfaces no debe confundirse con la verificación de conectividad entre las VMs.

El gateway de server4 administra la salida a Internet y las publicaciones selectivas de servicios. Cada publicación declara la VM, el protocolo, los puertos y los orígenes autorizados. Una VM puede tener acceso de salida sin que ello implique estar publicada para conexiones entrantes. La consola noVNC constituye un mecanismo independiente del acceso externo a los servicios de la VM.

## 6.6. Manejo de errores y concurrencia

La API diferencia los errores detectados antes de aceptar una solicitud de los que aparecen durante el despliegue. En el primer caso responde con un estado HTTP de error; en el segundo, el cliente debe consultar la operación y sus eventos para conocer si terminó correctamente o falló

| **HTTP**  | **Interpretación principal**                                          | **Qué debe hacer el cliente**                                   |
|-----------|-----------------------------------------------------------------------|-----------------------------------------------------------------|
| 400 / 413 | Modelo o cabeceras inválidos / tamaño permitido excedido.             | Corregir la solicitud o reducir la carga.                       |
| 401 / 403 | Token faltante o incorrecto / permisos insuficientes.                 | Revisar credenciales y rol autorizado.                          |
| 404       | Ruta o recurso inexistente; también puede ocultarse un recurso ajeno. | Revisar identificador, ruta y titularidad                       |
| 409       | Estado incompatible, conflicto de capacidad o de idempotencia.        | Consultar el estado vigente antes de reintentar                 |
| 500 / 503 | Error interno / fallo de preflight, SSH o acción remota.              | Inspeccionar eventos y diagnóstico; no asumir que nada se creó. |

Para reducir duplicaciones, las solicitudes del ciclo de vida emplean Idempotency-Key. Si una respuesta se pierde por timeout, el cliente debe repetir exactamente la petición con la misma clave. Antes de reintentar acciones remotas, el ejecutor consulta el estado real para evitar recrear recursos que podrían haber quedado activos.

La reserva de capacidad se realiza mediante transacciones cortas de SQLite. La configuración inicial documenta cuatro ejecutores de operaciones, hasta tres tareas remotas en paralelo y hasta tres intentos remotos; en un mismo worker, las VMs del plan se inician secuencialmente. Esta es concurrencia local controlada, no alta disponibilidad distribuida.

Las operaciones del slice incluyen estados de ejecución y recuperación. Por ejemplo, un fallo de creación puede terminar como FAILED_CLEANED si se confirmó la compensación, mientras que un error de eliminación puede conservar reservas en ERROR_CLEANUP hasta verificar la limpieza. Esto evita liberar recursos solo por una respuesta incompleta

## 6.7. Plantillas EX1, lineal y anillo

El generador g5.demo prepara las plantillas ex1, lineal y anillo con imágenes, claves y orígenes autorizados. La tabla conserva la topología histórica EX1 definida en el ZIP: seis VMs sobre tres workers. Es una referencia de compatibilidad del backend, no el perfil promedio ni una restricción para el diseño de VM Placement de fase 2.

| **VM** | **Imagen** | **Worker** | **vCPU** | **RAM** | **Disco GiB** |
|--------|------------|------------|----------|---------|---------------|
| VM1    | Ubuntu     | Server 1   | 1        | 512 MiB | 2.2           |
| VM2    | CirrOs     | Server 2   | 1        | 512 MiB | 1             |
| VM3    | Ubuntu     | Server 3   | 1        | 512 MiB | 2.2           |
| VM4    | Ubuntu     | Server 1   | 1        | 512 MiB | 2.2           |
| VM5    | Ubuntu     | Server 2   | 1        | 512 MiB | 2.2           |
| VM6    | CirrOs     | Server 3   | 1        | 512 MiB | 1             |

Los seis enlaces lógicos son VM1–VM2, VM2–VM3, VM1–VM4, VM3–VM4, VM4–VM5 y VM5–VM6. Cada enlace tiene una C-VLAN. VM1 y VM3 disponen además de redes de acceso diferenciadas y publicaciones TCP en los puertos externos 22001 y 22003 hacia SSH (puerto 22). El generador también prepara lineal.json y anillo.json. Estos archivos representan topologías predefinidas que se pueden solicitar a la API, pero la documentación no aporta resultados de una ejecución real exitosa de las tres topologías sobre el clúster. Para la sustentación es necesario mostrar, por separado, las evidencias obtenidas en los workers.

## 6.8. Verificación y resultados de implementación

La revisión del 30 de octubre de 2026 ejecutó las 60 pruebas existentes del ZIP mediante unittest: todas pasaron. Utilizan simulación y mocks; no validan por sí solas SSH real, KVM, OVS ni conectividad VNRT. Además se comprobó GET /openapi.json con autenticación en un servidor HTTP local simulado: respondió 200 y entregó las 21 operaciones del contrato. El error 500 de la versión previa de esta documentación queda superado para el código adjunto.

| **Comprobación y ámbito**       | **Resultado verificado o límite**                                     |
|---------------------------------|-----------------------------------------------------------------------|
| Suite existente tests/          | 60 pruebas correctas; backend simulado y mocks.                       |
| GET /openapi.json autenticado   | 200 en HTTP local simulado; contrato con 21 operaciones.              |
| Autenticación y permisos        | Cubiertos por la suite local; no equivalen a IAM académico integrado. |
| Reservas, reintentos y limpieza | Regresiones locales correctas; no certifican el clúster real.         |
| QEMU, OVS y SSH en fase 2       | No ejecutados en esta revisión documental.                            |
| Conectividad y exposición VPN   | Requieren evidencias reales por clúster y slice.                      |
| VM Placement y driver OpenStack | Diseño definido; no implementados en el ZIP inspeccionado.            |

La aceptación operativa requiere contrastar procesos/instancias, discos, puertos, conectividad, consola, publicaciones y limpieza en los nodos reales. Las pruebas locales respaldan el contrato y la lógica simulada, sin convertir resultados históricos del laboratorio en una inspección actual de infraestructura.

## 6.9. Limitaciones de la versión implementada

La versión adjunta es el prototipo Linux de EX1. Las siguientes limitaciones se mantienen al integrarla con fase 2:

- La autenticación se realiza con tokens opacos locales. No hay login HTTP, emisión o renovación de tokens ni integración funcional de IAM/Keycloak.

- El worker de cada VM se indica en la solicitud. No se ejecuta selección automática de VM Placement ni migración en vivo.

- La cola y las reservas son locales, soportadas por SQLite; no hay RabbitMQ ni alta disponibilidad distribuida en esta API.

- No existe edición PATCH de un slice desplegado, cancelación de trabajos ni transmisión de eventos por WebSocket.

- El ZIP implementa SSHBackend y MemoryBackend. No incluye un driver de APIs OpenStack ni AWS; la plataforma OpenStack del LAB5 es un avance distinto de la integración G5.

- El modelo Linux admite subredes /20 a /27 y reserva direcciones iniciales; no acepta directamente la /28 usada por link_1 en el RF. La abstracción común requiere validadores específicos por proveedor.

- La telemetría disponible no incluye todavía el historial funcional, la calibración ni el riesgo por franja definidos en R4. Se requiere al menos un día de datos para emitir propuestas provisionales. El promedio de carga no sustituye al porcentaje de CPU; el control de broadcast de fabric_add tampoco demuestra restricción por enlace. La sobreasignación efectiva inicial se limita a CPU; RAM y disco permanecen en 1.0.

La integración debe mantener el contrato Linux operativo, introducir el adaptador OpenStack, conectar inventario y monitoreo con placement y validar las reservas y compensaciones por proveedor. No se considera implementada una función solo por estar descrita en el HLD o por existir un servicio equivalente dentro de OpenStack.

## 6.10. Estado OpenStack y adaptación de fase 2

El contexto consolidado del 24 de octubre registra Keystone, Glance, Placement, Nova, Neutron y Horizon operativos durante LAB5. Nova reportó conductor y scheduler en headnode y tres computes; Neutron registró agentes de red activos. RabbitMQ pertenece a la plataforma OpenStack y no sustituye automáticamente la cola G5. Estos resultados son históricos: primero se consulta la salud actual, sin reinstalar ni recrear recursos existentes.

| **Instancia registrada** | **Estado y ubicación** | **Red y dirección** |
|--------------------------|------------------------|---------------------|
| instance_1               | ACTIVE en worker1      | link_1 · 10.0.39.97 |
| instance_2               | ACTIVE en worker3      | link_1 · 10.0.39.98 |

Las dos instancias son CirrOS y comparten subnet_link_1 (10.0.39.96/28), sin DHCP ni gateway. Los IDs Nova registrados son 77482432-1314-46fe-bc23-02d6f253b5ef y cafe6276-a124-4362-ad8c-07cfb9ddcb72, respectivamente. Se obtuvieron URLs noVNC; no hay evidencia final legible del ping, vecinos o captura P2P en Horizon. La IP registrada en Neutron no demuestra por sí sola configuración en el invitado. El tipo de red y port_security_enabled requieren consulta; no se hereda VLAN 1000 de fase 1.

| **Servicio**                 | **Acceso externo registrado**      | **Endpoint interno**             |
|------------------------------|------------------------------------|----------------------------------|
| SSH headnode                 | 10.20.11.245:5821                  | headnode / controller            |
| Keystone                     | 10.20.11.245:55000/v3              | controller:5000/v3               |
| Nova                         | 10.20.11.245:58774/v2.1            | controller:8774/v2.1             |
| Horizon                      | 10.20.11.245:50080/horizon         | headnode:80/horizon              |
| noVNC                        | 10.20.11.245:56080                 | controller:6080                  |
| Glance / Neutron / Placement | Sin publicación externa registrada | 9292 / 9696 / 8778 en controller |

El RF trabajó en dominio Cloud y proyecto lab5; el destino fue elegido por Nova Scheduler. Eso no acredita la heurística G5. El valor 2.87 consignado en el cliente no verifica la microversión soportada: el adaptador debe descubrirla y comprobar las operaciones que usará. Las credenciales de infraestructura permanecen fuera de plantillas y exportaciones de slices.

La adaptación debe actualizar la configuración Linux de fase 1, completar IP y roles de sus cuatro servers, mapear ambos switches, desarrollar el driver OpenStack y reconciliar recursos existentes. g5.web ofrece una consola local con plantillas y seguimiento, pero no implementa el editor completo, sesiones académicas ni la portabilidad entre proveedores. La red /28 del RF y el rango externo G5 son recursos distintos y no deben reutilizarse como si fueran la misma subred.

## 6.11. Trazabilidad de requisitos de fase 2

La matriz relaciona los criterios de Cambios Fase1 a Fase 2 (final) + Requerimientos a evaluar.pdf con el diseño y la evidencia disponible. Una cobertura de diseño no equivale a un criterio de implementación aprobado.

| **Requisito**        | **Cobertura en este documento**                                                                                                       | **Estado y evidencia pendiente**                                                                                            |
|----------------------|---------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------|
| R0 documentación     | Capítulos 1–6: arquitectura, HLD, flujos, contrato y estado de pruebas.                                                               | La sustentación y el reporte de pruebas reales requieren resultados de la plataforma; la suite local no los sustituye.      |
| R1B interfaz         | 4.2 y F2/F4/F5/F7: proveedores, concurrencia, plantillas, borradores, edición, importación/exportación, recursos, imágenes y consola. | Consola local Linux presente. Faltan editor completo, malla/árbol/bus, borradores y autorización académica integrada.       |
| R3 OpenStack         | 4.6 y 6.10: servicios, uso eficiente de APIs, topologías L2, recursos por proyecto, verificación y borrado.                           | Servicios y dos instancias históricos. Falta despliegue y limpieza integral desde G5, con evidencia de Horizon y host real. |
| R4 diseño            | 4.7: ratios CPU/disco, RAM 1.0, historial de 24 h, función objetivo y comparación con solver.                                         | Prototipo de evaluación sintética en 4.7.10; integración y mediciones en VNRT pendientes.                                   |
| R4 implementación    | 4.7.7 y F3/F6: inventario de ambas plataformas, destino por VM, rechazo explicado y zona.                                             | El ZIP exige worker. Faltan decisión automática, series temporales y reservas coordinadas con el proveedor.                 |
| R5 redes y seguridad | 4.5 y 4.6: VLAN Linux, self-service OpenStack, políticas, Internet, acceso VPN selectivo y broadcast por enlace.                      | La base Linux tiene QinQ/NAT. Faltan validación de fase 2 y control del switch limitado a los servidores participantes.     |

## 6.12. Referencias documentales y alcance de evidencias

\[1\] G5_Documentación_Ex1.docx: estructura, arquitectura, flujos y contrato Linux de base. \[2\] Ingenier-aDeRedesCloud-G5-main.zip: código, configuración, plantillas y 60 pruebas locales revisadas. \[3\] CONTEXTO_PROYECTO_G5_FASE2_EL_RF.md: estado histórico de infraestructura y avances del LAB5, corte 24 de octubre de 2026. \[4\] Modulo_VM_Placement_G5_Fase2.docx: base de la política de placement, versión del 28 de octubre de 2026; los ratios y su calibración se precisan en 4.7.2 y 4.7.8. \[5\] Cambios Fase1 a Fase 2 (final) + Requerimientos a evaluar.pdf: fases, topología, accesos, rangos externos G5 y criterios R1B/R3/R4/R5.

\[6\] OpenStack Nova, Configuration Options, disk_allocation_ratio: relación entre capacidad virtual y física y control del espacio libre. https://docs.openstack.org/nova/latest/configuration/config.html#DEFAULT.disk_allocation_ratio (consulta: 30 de octubre de 2026).

\[7\] OpenStack Nova, Compute schedulers, Allocation ratios: configuración e inventario efectivo por compute. https://docs.openstack.org/nova/latest/admin/scheduling.html#allocation-ratios (consulta: 30 de octubre de 2026). Los ratios y márgenes elegidos en 4.7.2 son decisiones de diseño de G5, no garantías del proveedor.

\[8\] SciPy, scipy.optimize.milp. Formulación MILP, estados, cotas y límites. https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html (consulta: 31 de octubre de 2026).

\[9\] Google OR-Tools, The Bin Packing Problem. Asignación obligatoria y objetivo de mínimo número de contenedores. https://developers.google.com/optimization/pack/bin_packing (consulta: 31 de octubre de 2026).

\[10\] HiGHS, List of options. Hilos, límite temporal y brecha MIP. https://ergo-code.github.io/HiGHS/dev/options/definitions/ (consulta: 31 de octubre de 2026).

**Enlace del repositorio github** https://github.com/DavidEscobal/Ingenier-aDeRedesCloud-G5
