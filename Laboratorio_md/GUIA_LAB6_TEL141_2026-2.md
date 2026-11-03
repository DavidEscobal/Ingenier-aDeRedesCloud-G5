# TEL141 — Ingeniería de Redes Cloud

## Laboratorio 6 (semestre 2026-2): Despliegue de slices usando las APIs de OpenStack

> **Institución:** Pontificia Universidad Católica del Perú (PUCP), Facultad de Ciencias e Ingeniería.  
> **Profesor:** Rubén Córdova.  
> **Jefe de práctica:** German Espinoza — g.espinozat@pucp.edu.pe.  
> **Fuente:** `GUIA_LAB-6_TEL141_2026-2(2).pdf`, 15 páginas del archivo recibido.  
> **Naturaleza de este archivo:** conversión estructurada a Markdown de la guía. Se reproducen sus instrucciones, preguntas, comandos, tablas y rúbrica, sin inventar soluciones ni resultados experimentales. Las figuras originales se conservan como imágenes en `assets/`. Las referencias a páginas indican la página física del PDF; las páginas 14 y 15 muestran numeración impresa 25 y 26 respectivamente.

## Índice

1. [Indicaciones generales, aprendizajes y objetivos (p. 1)](#1-indicaciones-generales-aprendizajes-y-objetivos-página-1)
2. [Escenario de la segunda parte del ciclo (pp. 2–3)](#2-escenario-para-la-segunda-parte-del-ciclo-páginas-2-y-3)
3. [Marco teórico: plan de pruebas y APIs de OpenStack (pp. 4–8)](#3-marco-teórico-páginas-4-a-8)
4. [Informe previo: indicaciones y actividad previa (pp. 9–10)](#4-informe-previo-páginas-9-y-10)
5. [Informe previo, actividad 1: CLI y APIs (pp. 11–13)](#5-informe-previo--actividad-1-funcionamiento-de-las-apis-de-openstack-páginas-11-a-13)
6. [Informe previo, actividad 2: plan de pruebas (p. 13)](#6-informe-previo--actividad-2-elaboración-del-plan-de-pruebas-de-un-módulo-página-13)
7. [Evaluación continua (p. 14)](#7-evaluación-continua-página-14)
8. [Rúbrica completa (p. 15)](#8-rúbrica-de-evaluación-página-15)
9. [Relación y límites documentales de las actividades](#9-relación-entre-actividades-y-aclaraciones-para-la-lectura)
10. [Figuras y recursos gráficos](#10-figuras-y-recursos-gráficos)

---

## 1. Indicaciones generales, aprendizajes y objetivos (página 1)

### 1.1 Identificación

| Campo | Información |
|---|---|
| Curso | TEL141 — Ingeniería de Redes Cloud |
| Laboratorio | N.° 6 |
| Semestre | 2026-2 |
| Tema | Despliegue de slices usando las APIs de OpenStack |
| Profesor | Rubén Córdova |
| Jefe de práctica | German Espinoza (g.espinozat@pucp.edu.pe) |

### 1.2 Indicaciones generales

- Entregar el **IP (Informe Previo)** antes de su sesión de laboratorio.
- Entregar el **RF (Reporte Final)** al finalizar la sesión de laboratorio.
- Seguir atentamente las indicaciones del docente y jefes de práctica.
- Utilizar los materiales asignados y recomendados por los jefes de práctica.
- Revisar previamente las normas de seguridad del laboratorio.
- Cualquier falta a la integridad académica, incluido el plagio, se reportará de inmediato a la Facultad.

### 1.3 Resultados de aprendizaje

Al finalizar el laboratorio, el estudiante será capaz de:

1. Comprender y utilizar las APIs de OpenStack para la creación y administración de redes y VMs.
2. Adquirir herramientas necesarias para definir un plan de pruebas que permita validar el correcto funcionamiento de la implementación del proyecto del curso.

### 1.4 Objetivos del laboratorio

1. Consolidar el uso de la API de OpenStack.
2. Comprender y utilizar las APIs de OpenStack para la creación de redes y máquinas virtuales.
3. Adquirir herramientas necesarias para definir el plan de pruebas a seguir para validar el correcto funcionamiento de la implementación del proyecto.

---

## 2. Escenario para la segunda parte del ciclo (páginas 2 y 3)

### 2.1 Infraestructura VNRT y slices

La sección de Ingeniería de las Telecomunicaciones cuenta con una nube privada que ejecuta **VNRT (Virtual Network Research Testbed)**, desarrollado por miembros del **GIRA**, para crear y asignar *slices* de cómputo. Un slice es un conjunto de máquinas virtuales interconectadas en **capa 2** que emulan una red real. Después del examen parcial, se asignó a cada grupo un slice con la topología ilustrada a continuación.

![Topología asignada en la segunda parte del ciclo: Linux Cluster, OpenStack Cluster, switches y gateway. Figura de la página 2.](assets/pagina_02_original.png)

**Elementos visibles en el diagrama:** servidor `app`, conexión a la red de la PUCP, `gateway`, clúster Linux, clúster OpenStack, switches `OVS_1` y `OVS_2`, switches de gestión y redes de administración (`MGMT 1`, `MGMT 2`). La imagen original permite consultar enlaces y colores; este texto no reemplaza su topología gráfica.

Las VMs `app` y `gateway` tienen direcciones IP accesibles desde la red de la PUCP. Para acceder a las demás VMs, el tráfico pasa a través del `gateway`, con un puerto específico por VM.

### 2.2 Puertos de acceso a las VMs desde el gateway

| Clúster | Dispositivo | Puerto de acceso indicado |
|---|---|---:|
| Linux | `server1` | `5811` |
| Linux | `server2` | `5812` |
| Linux | `server3` | `5813` |
| Linux | `server4` | `5814` |
| Linux | `ovs1` | `5815` |
| OpenStack | `headnode` | `5821` |
| OpenStack | `worker1` | `5822` |
| OpenStack | `worker2` | `5823` |
| OpenStack | `worker3` | `5824` |
| OpenStack | `ovs2` | `5825` |

> **Normalización de la tabla:** el PDF coloca los rótulos «PUERTO» y «DISPOSITIVO» en orden invertido respecto de sus valores. En esta tabla se aclara que `server1`, `headnode`, etc. son dispositivos y `5811`, `5821`, etc. son puertos, conservando las asignaciones numéricas.

**Ejemplo de conexión al HeadNode** (con `IP_Gateway` como marcador que debe sustituirse por la IP real asignada):

```bash
ssh ubuntu@IP_Gateway -p 5821
```

---

## 3. Marco teórico (páginas 4 a 8)

### 3.1 Plan de pruebas (página 4)

El plan de pruebas es un documento técnico que define la **estrategia, metodología y criterios** para validar el funcionamiento de una solución desplegada. Su finalidad es garantizar que cada módulo implementado satisfaga los requerimientos **funcionales, operacionales y de rendimiento** del proyecto.

**Tipos de pruebas presentados en la guía:**

| Tipo de prueba | ¿Qué valida? | Ejemplos de la guía |
|---|---|---|
| **Unitaria** | Módulos individuales. | Validación del parser de topologías; algoritmo de VM Placement. |
| **Integración** | Comunicación entre módulos. | UI ↔ Slice Manager; Slice Manager ↔ clúster OpenStack; backend ↔ base de datos. |
| **Funcional** | Cumplimiento de requerimientos del sistema. | Crear slices lineales y anillo; desplegar VMs en OpenStack; crear redes y reglas de seguridad; eliminar slices. |
| **Rendimiento** | Carga y concurrencia. | Despliegue simultáneo de múltiples VMs; tiempo de creación de slices; consumo de CPU y memoria. |

![Tabla original de tipos de pruebas, página 4.](assets/pagina_04_original.png)

### 3.2 Estructura básica de una prueba (página 5)

El plan se **organiza por módulos** de la solución. Cada módulo cuenta con su propia sección de pruebas para validar sus funcionalidades y facilitar la identificación de errores.

La nomenclatura de un caso es **`X.Y.Z TEST_NAME`**, donde:

- `X`: módulo principal.
- `Y`: sección o funcionalidad evaluada.
- `Z`: prueba específica realizada.

Ejemplo: `2.1.3` identifica la tercera prueba de la funcionalidad 1 del módulo 2.

Cada caso debe contener, como mínimo, estos **nueve campos**:

1. Número de caso.
2. Tipo de prueba.
3. Objetivos.
4. Prerrequisitos.
5. Procedimiento.
6. Resultados esperados.
7. Resultado obtenido.
8. Evidencias.
9. Comentarios u observaciones.

### 3.3 Plantilla de ejemplo: `3.1.2 DESPLIEGUE DE UNA VM` (página 6)

| Campo | Contenido del ejemplo oficial |
|---|---|
| **Número de caso** | `3.1.2` |
| **Tipo de prueba** | Funcional / Integración |
| **Objetivos** | Verificar el correcto despliegue de una VM dentro de la infraestructura OpenStack mediante el uso del orquestador y sus APIs. |
| **Prerrequisitos** | Tener una sesión de bash activa en la red PUCP. Tener una sesión activa del CLI del orquestador. |
| **Procedimiento** | 1) Ingresar al sistema. 2) Seleccionar la opción de creación de slice. 3) Definir parámetros de la VM: nombre, imagen, red y flavor. 4) Ejecutar el despliegue. 5) Verificar el estado de la VM mediante OpenStack CLI o Horizon. |
| **Resultados esperados** | La VM se creó correctamente; la instancia aparece en estado `ACTIVE`; la VM obtiene conectividad de red; no se generan errores durante el despliegue. |
| **Resultados obtenidos** | **PASS:** los resultados obtenidos son iguales a los esperados. **FAIL:** los resultados obtenidos no son iguales a los esperados. **NT:** el test no fue realizado porque cambiaron los requerimientos del cliente o no se cumplieron los requisitos. |
| **Evidencias** | Capturas de Horizon y resultados de pruebas de conectividad. |
| **Comentarios y observaciones** | (1) Este test es un ejemplo muy simplificado. (2) Se deben crear casos de prueba que verifiquen las funcionalidades exigidas en los requisitos. |

![Plantilla original de prueba 3.1.2, página 6.](assets/pagina_06_original.png)

> **Nota de fidelidad:** `PASS`, `FAIL` y `NT` aparecen como **descripciones de clasificación** en el ejemplo oficial, no como resultados de una prueba realizada y documentada en el PDF.

### 3.4 APIs de OpenStack (página 7)

OpenStack administra recursos virtualizados mediante una arquitectura de **APIs REST**, que permite automatizar autenticación, proyectos, redes y máquinas virtuales a través de solicitudes HTTP.

| Servicio | Responsabilidad | Puerto |
|---|---|---:|
| **Keystone** | Autenticación y autorización | `5000` |
| **Nova** | Administración de máquinas virtuales | `8774` |
| **Neutron** | Administración de redes virtuales | `9696` |
| **Glance** | Gestión de imágenes de VM | `9292` |

### 3.5 Flujo general de aprovisionamiento de un slice (páginas 7 y 8)

Según la guía, los scripts del laboratorio siguen esta secuencia:

1. Obtener token administrativo (`admin_cloud`).
2. Crear proyecto en OpenStack.
3. Crear o asociar un usuario propietario del proyecto.
4. Asignar roles sobre el proyecto.
5. Obtener token *scoped* para el proyecto.
6. Crear red(es) virtual(es) (`networks`).
7. Crear subred(es) virtual(es) (`subnets`).
8. Crear puertos virtuales (`ports`).
9. Crear instancia(s) VM (`instances`).
10. Obtener acceso a consola remota.

**Diagrama de la página 8:** representa un ejemplo de tres VMs (`VM_1`, `VM_2`, `VM_3`) conectadas mediante tres enlaces (`link_1`, `link_2`, `link_3`) que forman un triángulo. Los enlaces utilizan subredes diferenciadas (`subnet_1`, `subnet_2`, `subnet_3`) y seis puertos (`p1`–`p6`). En la parte superior aparecen los pasos previos de creación del proyecto y asignación de usuario/rol, seguidos por la creación de redes, subredes, puertos, instancias y acceso a consola.

![Flujo original de aprovisionamiento de un slice OpenStack, página 8.](assets/pagina_08_original.png)

**Conectividad mostrada en el ejemplo visual:**

| Enlace lógico | Subred | VMs conectadas | Puertos según figura |
|---|---|---|---|
| `link_1` | `subnet_1` | `VM_1` y `VM_2` | `p1`, `p2` |
| `link_2` | `subnet_2` | `VM_2` y `VM_3` | `p3`, `p4` |
| `link_3` | `subnet_3` | `VM_3` y `VM_1` | `p5`, `p6` |

> Esta tabla adicional describe elementos visibles en la figura para facilitar su consulta textual. No representa resultados de un despliegue ejecutado.

---

## 4. Informe previo (páginas 9 y 10)

### 4.1 Indicaciones generales del Informe Previo

- **Puntaje total: 5 puntos.**
- Desarrollo **grupal**.
- Se utiliza una copia del archivo `TEL141_Lab6_IP_Template.docx`, disponible en **PAIDEIA → Laboratorio 6 → INFORME PREVIO [TODOS LOS HORARIOS]**.
- Al finalizar, guardar el informe como **`TEL141_Lab6_IP_GXX.pdf`**, donde `XX` es el identificador del grupo de proyecto.
- Se entrega **en PDF mediante PAIDEIA**, en un plazo indicado de **una semana**; la guía señala que no se admiten entregas posteriores ni por otros medios.
- Corresponde revisar y practicar los conceptos previamente para desarrollar las actividades.

> La indicación general de la página 1 exige entregar el IP **antes de la sesión de laboratorio**; la sección de Informe Previo menciona además el plazo de **una semana**. Se conservan ambas expresiones tal como aparecen y no se infiere una nueva fecha límite.

### 4.2 ACTIVIDAD PREVIA — Conceptos previos (**0 puntos**)

**Objetivo:** agregar túneles SSH para reenviar el tráfico desde `localhost` hacia el HeadNode.

| Puerto en Local Host | Puerto en HeadNode | Servicio (correspondencia según tabla de APIs) |
|---:|---:|---|
| `55000` | `5000` | Keystone |
| `58774` | `8774` | Nova |
| `59696` | `9696` | Neutron |
| `59292` | `9292` | Glance |
| `51080` | `80` | Servicio web, usado para acceder al panel cuando esté configurado |

**Comandos de la guía** (son cinco comandos individuales; reemplazar `X` por el valor asignado):

```bash
ssh -NL 55000:127.0.0.1:5000 ubuntu@10.20.12.X -p 5821
ssh -NL 58774:127.0.0.1:8774 ubuntu@10.20.12.X -p 5821
ssh -NL 59696:127.0.0.1:9696 ubuntu@10.20.12.X -p 5821
ssh -NL 59292:127.0.0.1:9292 ubuntu@10.20.12.X -p 5821
ssh -NL 51080:127.0.0.1:80 ubuntu@10.20.12.X -p 5821
```

### 4.3 Alternativa opcional — DNAT desde el gateway

La guía presenta como **opcional** configurar DNAT para llegar a las APIs expuestas por el HeadNode a través de `<IP_GATEWAY>:<PUERTO>`.

**a) Habilitar el reenvío IPv4:**

```bash
sudo sysctl -w net.ipv4.ip_forward=1
```

**b) Crear una regla DNAT:**

```bash
sudo iptables -t nat -A PREROUTING -p tcp --dport <PUERTO> -j DNAT --to-destination <IP_HEADNODE>:<PUERTO>
```

**c) Permitir forwarding:**

```bash
sudo iptables -A FORWARD -p tcp --dport <PUERTO> -j ACCEPT
```

> Los valores entre `<...>` son marcadores de posición de la propia guía; no deben ejecutarse literalmente sin sustituirlos. Estas reglas modificarían la red real, por lo que su carácter opcional no significa que deban aplicarse sin autorización.

### 4.4 Prerrequisitos asumidos por la guía (página 10)

Para **los pasos siguientes**, se presupone que el estudiante ya creó:

- Dominio `Cloud`.
- Proyecto `cloud_admin`.
- Usuario `cloud_admin`.
- Archivo `cloud-admin-openrc` en `env-scripts`.
- Al menos **un flavor** y **una imagen**.

---

## 5. Informe previo — Actividad 1: Funcionamiento de las APIs de OpenStack (páginas 11 a 13)

**Puntaje: 2 puntos.**

Primero, conectarse al HeadNode y cargar credenciales para usar la CLI:

```bash
. ~/env-scripts/cloud-admin-openrc
```

### 5.1 PASO 1 — Comparar la CLI normal y `--debug` (página 11)

Ejecutar:

```bash
openstack server list
openstack --debug server list
```

**Preguntas para responder en el template:**

1. ¿Qué información adicional aparece al usar `--debug`?
2. ¿Cuántas llamadas HTTP se realizaron en total para listar los servidores?
3. ¿A qué servicios de OpenStack se conectó el CLI y en qué orden?
4. ¿Por qué se contacta más de un servicio para ejecutar un solo comando?

**Entrega parcial indicada:** completar el Paso 1 de la Actividad 1 del `TEL141_LAB6_IP_Template`.

### 5.2 PASO 2 — Token de autenticación de Keystone (página 11)

Ejecutar y observar el debug:

```bash
openstack --debug token issue
```

**Preguntas para el template:**

1. ¿En qué header HTTP viaja el token en las siguientes llamadas?
2. ¿A qué endpoint de Keystone se conectó para obtener el token?

**Entrega parcial indicada:** completar el Paso 2 de la Actividad 1 del template.

### 5.3 PASO 3 — Relación entre debug y documentación de Neutron (página 12)

Ejecutar:

```bash
openstack --debug network list
```

Consultar la documentación de la API Neutron que señala la guía:

<https://docs.openstack.org/api-ref/network/v2>

**Preguntas para el template:**

1. ¿Cuál es la URL completa del request que hizo el CLI a Neutron?
2. Busque el endpoint `/v2.0/networks` en la documentación: ¿qué parámetros opcionales acepta?
3. ¿Cómo modificaría el comando CLI para filtrar redes por nombre?

**Entrega parcial indicada:** completar el Paso 3 de la Actividad 1 del template.

### 5.4 PASO 3.5 — Reproducir la llamada REST usando `curl` (página 12)

Tras observar `openstack --debug network list`, identificar en su salida la URL y token usados. Repetir la llamada manualmente:

**Obtener el token:**

```bash
openstack token issue -f value -c id
```

**Replicar la llamada del CLI con `curl`:**

```bash
curl -s -X GET http://192.168.202.1:9696/v2.0/networks \
  -H "X-Auth-Token: <token_obtenido>" | python3 -m json.tool
```

**Preguntas para el template:**

1. ¿El resultado de `curl` es igual al de `openstack network list`? ¿Por qué?
2. ¿Qué hace el CLI con la respuesta JSON que devuelve la API?
3. ¿Qué cambios aplica el CLI a las respuestas frente a las respuestas de la API?

**Entrega parcial indicada:** completar el Paso 3.5 de la Actividad 1 del template.

> El token es un secreto temporal. No conviene incorporarlo a capturas publicadas ni subirlo al repositorio. La guía incluye el marcador `<token_obtenido>`, no un token real.

### 5.5 PASO 4 — Interpretar un error HTTP de Nova (página 13)

Ejecutar el siguiente comando **con un ID inexistente**:

```bash
openstack --debug server show 00000000-0000-0000-0000-000000000000
```

**Preguntas para el template:**

1. ¿Qué código HTTP retornó la API?
2. ¿Qué significa ese código según la documentación de Nova API?
3. ¿En qué parte del output debug se puede ver el cuerpo completo del error?

**Entrega parcial indicada:** completar el Paso 4 de la Actividad 1 del template.

### 5.6 PASO 5 — Explicar el funcionamiento interno de la CLI (página 13)

**Enunciado de la guía:** un compañero afirma que «la CLI de OpenStack simplemente muestra resultados en pantalla». A partir de lo observado en los pasos anteriores y de la documentación oficial de las APIs, **redactar una explicación de máximo siete líneas** sobre lo que hace realmente la CLI por debajo cada vez que se ejecuta un comando.

**Entrega parcial indicada:** completar el Paso 5 de la Actividad 1 del template.

> **Alcance de esta conversión:** las preguntas de los pasos 1–5 se han mantenido sin respuestas. Deben responderse con datos de las ejecuciones reales cuando la pregunta así lo requiera.

---

## 6. Informe previo — Actividad 2: Elaboración del plan de pruebas de un módulo (página 13)

**Puntaje: 3 puntos.**

### 6.1 Objetivo y enunciado

> El objetivo de esta actividad es elaborar un **Plan de Pruebas** que permita validar el comportamiento y funcionamiento de **uno de los módulos del proyecto de curso**. Es importante considerar los requerimientos evaluados durante la presentación parcial (**EX1**) y los que serán evaluados en la presentación final (**EX2**), según el documento oficial del proyecto.

**Tarea expresamente indicada en la guía:**

> Elabore el plan de pruebas del módulo **«Slice Manager»** correspondiente a su proyecto de curso.

**Observación de la guía:** el nombre del módulo puede variar según la arquitectura propuesta por cada grupo.

### 6.2 Formato aplicable

El formato general del capítulo 3 (páginas 5–6 de esta guía) se aplica al plan: organizar por módulo, identificar los casos con nomenclatura `X.Y.Z`, e incluir número, tipo, objetivos, prerrequisitos, procedimiento, resultados esperados, resultado obtenido, evidencias y observaciones.

**No se especifica en la actividad 2** un número fijo de casos de prueba ni que deban haberse ejecutado todos antes de la entrega del plan. El template sí dispone de un campo para «Resultados obtenidos». Esta distinción procede de la redacción de la guía; no equivale a una dispensa de entregar las evidencias que pida otra evaluación del curso.

---

## 7. Evaluación continua (página 14)

### 7.1 Indicaciones generales

- **Puntaje total: 4 puntos.**
- Documento de avance **grupal**, entregado en formato PDF.
- **Nombre exacto especificado:** `TEL141_LAB4_AP_GXX.pdf`, donde `XX` identifica al grupo. **Nota:** la guía del Laboratorio 6 utiliza literalmente `LAB4` en ese nombre; no se corrige automáticamente.
- **Plazo explícito:** hasta las **23:59 del domingo 8 de noviembre** (en el contexto del semestre 2026-2).
- Entrega mediante **PAIDEIA**; después de la fecha, la guía indica que no se reciben informes por otro medio.
- Calificación compuesta por **2 puntos individuales** y **2 puntos grupales**, determinada por el coach de cada grupo.

### 7.2 Avance del Proyecto (**2 puntos**, grupal)

La guía solicita:

> **Explicación clara y concisa del plan de pruebas elaborado en el Informe Previo.**

### 7.3 Desempeño en el Laboratorio (**2 puntos**, individual)

Evaluación personal basada en el desempeño en el laboratorio.

---

## 8. Rúbrica de evaluación (página 15)

La siguiente tabla conserva los **productos, criterios y descripciones** de la rúbrica. La columna «Comentario» está vacía en el documento fuente.

| Producto | Puntaje | Criterio de evaluación | Descripción / requerimientos de la rúbrica |
|---|---:|---|---|
| **Informe previo** | **5 pts** | Investigación y análisis | Identifica los factores que intervienen en la interacción entre la CLI (modo debug) y las APIs de OpenStack, usando como referencia la documentación de las APIs. |
| **Experiencia de laboratorio — Ejecución** | **3 pts** | Ejecución y resolución | (1) Despliega recursos: redes, puertos y VMs, usando las APIs de OpenStack. (2) Automatiza la creación de escenarios virtuales usando scripts de Python que interactúen con la API de OpenStack. |
| **Experiencia de laboratorio — Análisis** | **3 pts** | Análisis | (3) Mapea el diseño de su orquestador (proyecto), de utilizar el driver del clúster Linux al driver de OpenStack, fundamentando los cambios arquitectónicos necesarios para asegurar la compatibilidad del sistema. |
| **Evaluación personal del laboratorio** | **2 pts** | Comprensión del proceso | (1) Responde las consultas durante el laboratorio sobre la interacción con APIs, demostrando dominio de la arquitectura. (2) Justifica el uso de tokens en la comunicación con APIs y su impacto en seguridad y autenticación de la nube privada. |
| **Evaluación continua — Proyecto** | **2 pts** | Presentación | Define un plan de pruebas donde el resultado realmente permite validar lo indicado. |
| **Evaluación de clases** | **5 pts** | Comprensión de teoría | Demuestra comprensión de los fundamentos teóricos utilizados para entender lo visto en la experiencia de laboratorio. |

![Rúbrica original de evaluación de la guía LAB6, página 15 del PDF (página impresa 26).](assets/pagina_15_original.png)

### 8.1 Experiencia de Laboratorio (6 pts): criterios exactos que deben tenerse en cuenta

En la rúbrica, la **Experiencia de Laboratorio** se divide en dos bloques:

**Ejecución y resolución (3 puntos):**

1. Desplegar recursos **redes, puertos y VMs** utilizando las **APIs de OpenStack**.
2. Automatizar la creación de escenarios virtuales con **scripts Python** que interactúen con la **API de OpenStack**.

**Análisis (3 puntos):**

3. Mapear/adaptar el diseño del orquestador desde el **driver del clúster Linux** al **driver OpenStack**, **fundamentando los cambios arquitectónicos** para asegurar la compatibilidad.

**Importante:** las páginas disponibles del PDF definen estos criterios en la rúbrica, pero **no incluyen una secuencia práctica paso a paso adicional para la Experiencia de Laboratorio**, ni código Python oficial que pueda transcribirse. Los pasos de aprovisionamiento de la página 7 son parte del marco teórico general.

---

## 9. Relación entre actividades y aclaraciones para la lectura

Esta sección sirve como **índice de correspondencia** entre las partes del documento, no agrega nuevos requisitos:

| Parte de la guía | Entregable / tarea | ¿En qué se apoya? | Página fuente |
|---|---|---|---|
| **Actividad previa (0 pts)** | Establecer los túneles SSH a servicios OpenStack. | Topología y puertos del clúster. | 9–10 |
| **Informe Previo — Actividad 1 (2 pts)** | Ejecutar CLI/`--debug`/`curl` y responder preguntas de APIs. | Credenciales y OpenStack ya configurado. | 11–13 |
| **Informe Previo — Actividad 2 (3 pts)** | Elaborar plan de pruebas del Slice Manager considerando EX1 y EX2. | Marco de plan de pruebas y requisitos del proyecto. | 4–6, 13 |
| **Experiencia de laboratorio (6 pts)** | Despliegue con APIs, automatización Python y mapeo driver Linux→OpenStack. | Rúbrica de ejecución y análisis. | 15 |
| **Evaluación continua — Proyecto (2 pts)** | Explicar el plan de pruebas del IP. | Actividad 2 del Informe Previo. | 14–15 |
| **Evaluación personal (2 pts)** | Sustentar interacción con APIs y tokens de autenticación. | Conceptos y experiencia de laboratorio. | 15 |

**Advertencias de interpretación:**

- La guía **no exige explícitamente** implementar todo Slice Manager para realizar los criterios de API/Python de la Experiencia de Laboratorio; no obstante, sí espera conocer la arquitectura del orquestador para el análisis.
- La guía **no presenta evidencia real de ejecución**: estados `PASS` y capturas de Horizon en el template son ejemplos o categorías, no resultados registrados.
- La página 14 contiene un nombre de archivo `TEL141_LAB4_AP_GXX.pdf` pese a tratarse del Laboratorio 6; se conserva el texto original para evitar sustituir silenciosamente un requisito.
- El plazo de entrega del Informe Previo mencionado como «una semana» no sustituye la indicación de entregarlo antes de la sesión. La fecha exacta en PAIDEIA debe verificarse en el curso.

---

## 10. Figuras y recursos gráficos

Se incluyen imágenes de las páginas donde un diagrama, tabla compleja o rúbrica aporta información visual independiente:

| Archivo | Página del PDF | Contenido |
|---|---:|---|
| `assets/pagina_02_original.png` | 2 | Infraestructura asignada (Linux + OpenStack). |
| `assets/pagina_04_original.png` | 4 | Tipos de pruebas y ejemplos. |
| `assets/pagina_06_original.png` | 6 | Plantilla oficial del caso 3.1.2. |
| `assets/pagina_08_original.png` | 8 | Secuencia y diagrama del slice con tres enlaces y puertos. |
| `assets/pagina_15_original.png` | 15 | Rúbrica de evaluación. |

Para utilizar este documento en Claude Code, mantener **este `.md` y la carpeta `assets/` en el mismo directorio padre**, de modo que funcionen las referencias Markdown como `![...](assets/pagina_08_original.png)`.

**Fin de la conversión de la guía del Laboratorio 6, TEL141, semestre 2026-2.**
