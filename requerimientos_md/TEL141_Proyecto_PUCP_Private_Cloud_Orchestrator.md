# PROYECTO: PUCP Private Cloud Orchestrator

**Periodo indicado en el documento fuente:** 2025-2. **Aplicación al curso:** el usuario confirma que este mismo enunciado se utiliza para 2026-2.

> Conversión de las 18 páginas del PDF. Se conservan los textos, tablas y figuras. **Actualización:** se transcribieron a Markdown las rúbricas EX1 (págs. 15–16) y EX2 (págs. 17–18), además de conservar sus imágenes originales. Los identificadores de criterio y puntos equivalentes de EX2 son auxiliares, no forman parte del original. No se modificaron fechas ni exigencias de la fuente.

<!-- Página 1 del PDF original -->

La Pontificia Universidad Católica del Perú cuenta con una serie de servidores DELL Power Edge R630, los cuales planea usar para implementar una nube privada, de manera que pueda ser utilizada para el despliegue de topologías de máquinas virtuales conectadas dinámicamente en capa 2. Dada la cantidad de máquinas virtuales a provisionar, y el dinamismo, se requiere un sistema automatizado que ayude al administrador de la infraestructura con el despliegue y/o administración de los recursos.


Se le pide que implemente una primera versión de este sistema, la cual no necesita tener un entorno gráfico. Su equipo de trabajo debe diseñar una solución que facilite el aprovisionamiento dinámico y minimice la posibilidad de error humano. La visión que se tiene para este proyecto se resume en la siguiente imagen:


**Figura de la visión general: aplicación de control, usuarios y múltiples infraestructuras IaaS conectadas a la red.**
![Figura de la visión general: aplicación de control, usuarios y múltiples infraestructuras IaaS conectadas a la red.](TEL141_Proyecto_Cloud_assets/figura_01_vision_general.png)


---

<!-- Página 2 del PDF original -->

Tal y como se observa en la imagen anterior, se busca tener una solución que nos permita manejar el ciclo de vida de topologías de red en diversos IaaS de manera particular(cada una de ellas puede tener un modo diferente de interacción). El usuario podrá acceder a la solución, la cual se comunicará con los IaaS para poder realizar las tareas que el usuario tenga disponible, dependiendo del rol que posea.


Es importante notar que el proyecto se realizará por fases: (1) Diseño e implementación de orquestador con capacidades de manejo de ciclo de vida y uso de VMs usando tecnologías LINUX, (2) Aumento de funcionalidad para que el mismo orquestador pueda manejar el ciclo de vida y uso de VMs usando OpenStack. Es decir, al final del curso su orquestador deberá poder controlar el ciclo de vida de dos cluster(OpenStack y Linux) de una manera dinámica y accesible para el usuario.


## 1. REQUERIMIENTOS


El presente proyecto consta de 6 requerimientos, los cuales se detallan a continuación :


- R0 [22 pts]: Este requisito calificará la pulcritud de la exposición y la documentación, además de la cohesión y buena organización del grupo. Finalmente, la valoración personal y grupal que el coach realicé será un factor determinante para este puntaje en específico(durante todo el ciclo). Para fines de calificación, la primera parte de R0 se aplicará a la documentación de arquitectura y demás parámetros de calificación mencionados líneas arriba. Finalmente para la segunda parte de R0 se aplicará a la documentación de la implementación.

- R1 [40 pts]: Controlar la creación y el borrado de slices de máquinas virtuales en una infraestructura de nube genérica, ya sea privada (Linux cluster, OpenStack, etc.) o pública (AWS, GCP, etc.).


- R1B [18 pts]: Proveer una interfaz de usuario que permita a un usuario gestionar el ciclo de vida de sus slices (creación, edición, borrado, etc.).

- R1C [18 pts]: Gestionar el despliegue/aprovisionamiento de slices sobre la Infraestructura de nube deseada. Responsable porque los diferentes elementos del slice sean creados en el orden adecuado y en el lugar deseado y que la creación del slice sea completa (no se quede a medias).


- R2 [18 pts]: Soportar la creación/borrado de slices sobre un cluster de servidores Linux.

- R3 [30 pts]: Soportar la creación/borrado de slices sobre un sistema OpenStack.


- R4 [30 pts]: Ejecutar el “VM Placement” (mapeo de VM a servidor físico) tomando en cuenta los recursos disponibles y permitiendo elegir la “zona de disponibilidad” a usar.

- R5 [24 pts]: Proveer soporte de Networking capas 2 y 3, permitiendo definir reglas de ciberseguridad


---

<!-- Página 3 del PDF original -->

Nota: el puntaje total por grupo (200pts) se reparte en partes iguales entre el parcial (Ex1, 100pts) y el final (Ex2, 100pts), como se muestra en la sección 9 (“Calificación”).


Su grupo diseñará e implementará una solución que cubra tantos requerimientos como les sea posible. En función a la calidad de su solución, recibirá un puntaje total (nota) que será repartido entre sus miembros de la manera que los miembros del grupo decidan.


Adicionalmente, como parte del requerimiento cinco (R5) se espera que las VMs desplegadas en su solución puedan ser accedidas desde el “exterior”, para esto se han definido rangos de IPs por grupos, las cuales serán seteadas en sus dispositivos ( pueden usar DHCP). Ahora, no necesariamente todas las VMs deben ser vistas desde el exterior, en realidad, sólo las que ustedes explícitamente decidan.


| GRUPO | LINUX CLUSTER | OPENSTACK CLUSTER |
| --- | --- | --- |
| 1 | 10.60.1.0/24 | 10.60.2.0/24 |
| 2 | 10.60.3.0/24 | 10.60.4.0/24 |
| 3 | 10.60.5.0/24 | 10.60.6.0/24 |
| 4 | 10.60.7.0/24 | 10.60.8.0/24 |
| 5 | 10.60.9.0/24 | 10.60.10.0/24 |
| 6 | 10.60.11.0/24 | 10.60.12.0/24 |


Como pueden notar, las IPs contenidas en el cuadro anterior, son IPs PRIVADAS, las cuales van a poder ser accedidas sólo a través de la VPN. Si por algún motivo intentamos acceder a ellas desde dentro de la UNIVERSIDAD obtendrán errores de conexión, ya que no están disponibles a nivel INTERNO (Universidad), pero SÍ a través de la VPN, ya que se configurarán rutas para que puedan permitir dichas conexiones usando como router al Headnode del VNRT.


---

<!-- Página 4 del PDF original -->

## 2. FASES


El proyecto se desarrollará en dos fases a lo largo del ciclo. Al inicio, cada estudiante contará con una topología individual (Clúster Linux) que le permitirá realizar los laboratorios de manera más holgada y, si lo desea, comenzar a incorporar su código del proyecto. Aunque estas topologías sean individuales, el trabajo del proyecto es grupal desde el inicio, por lo que el código podrá desarrollarse en cualquiera de las topologías asignadas. Tras el parcial, el trabajo será unificado en una única topología grupal que integrará tanto Clúster Linux como OpenStack. Durante la transición, los estudiantes tendrán un plazo de una semana para migrar y adaptar su código a esta nueva topología. Mayor detalle en la siguiente tabla:


| Fase | Descripción | Duración | Notas |
| --- | --- | --- | --- |
| Fase 1 - Topologia individual | Topologías designadas para elaborar su solución usando tecnologías basadas Linux, asignadas individualmente. Los estudiantes podrán elegir cualquiera de estas topologías para ir incorporando su código del proyecto mientras realizan los laboratorios. | Desde el laboratorio 1 hasta una(1) semana después de la presentación parcial. | Estas topologías se usarán para prácticas de laboratorio y para avanzar en el proyecto de manera preliminar. |
| Migración | Migrar y adaptar el avance y código de la topología individual a la topología grupal. | 1 semana después del parcial | Pasado este plazo, se eliminarán las topologías individuales. |
| Fase 2 – Topología Grupal | Única topología compartida que incluirá Linux y OpenStack, trabajada en grupo. | Desde el parcial hasta el final del curso. | Trabajo colaborativo sobre una sola topología compartida. |


A continuación, se muestran los dos tipos de topología a usar en las diferentes fases:


**Esquema de infraestructura Fase 1 (Linux).**
![Esquema de infraestructura Fase 1 (Linux).](TEL141_Proyecto_Cloud_assets/figura_02_fase1.png)


**Esquema de infraestructura Fase 2 (Linux y OpenStack).**
![Esquema de infraestructura Fase 2 (Linux y OpenStack).](TEL141_Proyecto_Cloud_assets/figura_03_fase2.png)


---

<!-- Página 5 del PDF original -->

## 3. ACCESO


Las máquinas virtuales (VMs) app y gateway tienen direcciones IP que son accesibles desde la red de la PUCP. Para acceder a las otras VMs, todo el tráfico debe pasar a través del gateway. Además, se utiliza un puerto específico en el gateway para conectarse a cada VM.


La siguiente tabla muestra qué puerto del gateway corresponde a cada VM:


| FASE | Cluster | PUERTO | DISPOSITIVO |
| --- | --- | --- | --- |
| FASE 1 | Linux | server1 | 5801 |
| FASE 1 | Linux | server2 | 5802 |
| FASE 1 | Linux | server3 | 5803 |
| FASE 1 | Linux | server4 | 5804 |
| FASE 1 | Linux | ofs | 5805 |
| FASE 2 | Linux | server1 | 5811 |
| FASE 2 | Linux | server2 | 5812 |
| FASE 2 | Linux | server3 | 5813 |
| FASE 2 | Linux | server4 | 5814 |
| FASE 2 | Linux | ovs1 | 5815 |
| FASE 2 | OpenStack | headnode | 5821 |
| FASE 2 | OpenStack | worker1 | 5822 |
| FASE 2 | OpenStack | worker2 | 5823 |
| FASE 2 | OpenStack | worker3 | 5824 |
| FASE 2 | OpenStack | ovs2 | 5825 |


Por ejemplo:


Si deseo conectarme al server 3 en la topología de la fase 2, debería ejecutar el siguiente comando:


$ ssh ubuntu@IP_Gateway -p 5813


---

<!-- Página 6 del PDF original -->

## 4. CRITERIOS DE EVALUACIÓN


| Descripción | Criterios |
| --- | --- |
| R0 Performance en presentación, temas requeridos y documentación. (22 pts) | <br>• Claridad de la exposición y manejo de medios. <br>• Cohesión y trabajo en equipo durante el periodo a evaluar. <br>• Desempeño personal constante durante el proyecto. <br>• Orden, redacción, contenido y buena organización de la presentación. <br>• Porcentaje de Cobertura de los requerimientos. |
| R1 Controlar la creación y el borrado de slices de VMs en una infraestructura de nube privada. (40 pts) | <br>• Diseño independiente de la capa de infraestructura (cluster de servidores Linux, OpenStack, AWS, etc.). <br>• Debe tener un módulo para cada uno de los requerimientos subsiguientes: - Debe poder almacenar la información de forma persistente. - Debe permitir la comunicación en red entre módulos. - Debe soportar la creación concurrente (multiusuario) de slices, es decir, manejo de colas. - Debe soportar la creación de logs con la información necesaria para hacer troubleshooting de cada módulo. |
| R1B Interfaz de usuario (UI) que gestiona el ciclo de vida de slices (18 pts) | <br>• Permitir que múltiples usuarios usen la infraestructura de forma concurrente. <br>• Permitir seleccionar slices con topologías predefinidas: lineal, malla, árbol, anillo, y bus. <br>• Permitir editar slices existentes agregando nodos y enlaces. <br>• Permitir especificar la configuración (capacidad) de cada VM a crear. <br>• Listar los slices existentes. <br>• Listar el consumo de recursos del sistema. <br>• Permitir borrar slices previamente creados. <br>• Debe permitir importar imágenes de VMs. <br>• Proveer tokens/credenciales para que el dueño del slice pueda acceder a la consola virtual de cada VM. |
| R1C Gestor de despliegue de slices (“Slice Manager”) (18 pts) | <br>• Expone los APIs del sistema. Puede ser un sólo módulo o varios. <br>• La comunicación del resto de módulos debe pasar por él. <br>• Debe validar que el usuario esté autenticado y tenga autorización de realizar la acción solicitada. <br>• Debe validar que el body de las solicitudes tengan la sintaxis correcta. <br>• Modela los slices y sus elementos (uso de OOP). <br>• Crea los elementos en el orden correcto y lidia con errores y con conflictos por el uso de recursos. |


---

<!-- Página 7 del PDF original -->

| Descripción | Criterios |
| --- | --- |
| R2 Soporte de cluster de servidores Linux (28 pts) | <br>• Orquesta VM sobre servidores corriendo alguna versión de linux. <br>• Ahorro de almacenamiento: debe borrar las imágenes de las VMs que ya no se usen (en los servidores). <br>• Proveer acceso a la consola virtual de cada VM. |
| R3 Soporte de OpenStack (20 pts) | <br>• Usar el OpenStack API. <br>• Implementar al menos Keystone, Horizon, Nova, Neutron (ML2 plugin), y Glance. <br>• Debe permitir ver cada slice creada, por separado, en Horizon. |
| R4 VM Placement (20 pts) | <br>• Asignar las máquinas virtuales a servidores de acuerdo a su criterio de performance. Por ej: - El consumo de recursos sea aceptable de acuerdo a su SLA (p.ej., no exceda un nivel máximo de sobre-aprovisionamiento, el cual sería un parámetro de configuración). - Minimizar el tiempo de espera (de las VMs) en la cola (de servicio de los cores), lo que generalmente resulta en una asignación de carga está balanceada entre los servidores. - Se minimice el consumo de energía - Se maximiza la performance del slice, visto como un todo. <br>• Listar los recursos (servidores) disponibles. <br>• Permitir al usuario definir zonas de disponibilidad. <br>• Permitir al usuario elegir en qué zona de disponibilidad se desplegará un slice. |
| R5 Networking y Seguridad (22 pts) | <br>• Proveer salida a Internet y reglas de seguridad a las VMs que lo requieran. <br>• Debe permitir acceso desde Internet a las máquinas virtuales que lo requieran (equivalente a tener una IP pública). <br>• Usar redes provider (VLANs) en lugar de self-service (tuneles). <br>• Limitar los paquetes de broadcast a aquellos puertos/servidores que tienen VMs que pertenezcan a la subred respectiva (ya sea usando Netcong, Yang, OpenFlow, etc.). |


---

<!-- Página 8 del PDF original -->

## 5. PLAN DE ACCIÓN


El desarrollo del proyecto debe mantenerse de manera constante a lo largo de todo el ciclo académico, con el objetivo de garantizar resultados de calidad y una estructura sólida y coherente del trabajo. Para alcanzar este propósito, se ha establecido un plan de acción cuidadosamente diseñado, que integra de manera articulada los laboratorios, los contenidos teóricos y las sesiones de asesoría, cada una de ellas guiada por los respectivos coaches. Es de suma importancia la asistencia regular a clases, laboratorios y reuniones con los coaches, dado que la comprensión de los conceptos teóricos se encuentra directamente vinculada con las actividades prácticas. Esta interacción constante entre teoría y práctica permite no solo afianzar los conocimientos adquiridos, sino también aplicar soluciones efectivas en los distintos componentes del proyecto, asegurando así un avance progresivo y sostenido. En todas las clases se aplicarán cuestionarios o pruebas de salida, que podrán tomarse al inicio, en el transcurso o al final de la sesión. Para la nota del laboratorio, se considerarán dos cuestionarios principales: uno en la semana previa al laboratorio y otro en la semana del laboratorio, que en conjunto sumarán 5 puntos. A ello se añaden 5 puntos correspondientes al informe previo, 5 puntos al desarrollo de la guía y al informe final, y 5 puntos de evaluación continua, distribuidos en 3 puntos para el proyecto (1.5 por desempeño individual y 1.5 por trabajo grupal) y 2 puntos por el trabajo en laboratorio. Es importante mencionar que este plan de acción está conectado a lograr el mejor resultado en el ciclo, por ende, cada actividad y evaluación ha sido diseñada para reforzar progresivamente los conocimientos y asegurar la aplicación práctica de lo aprendido.


> **IMPORTANTE** : Los avances en la implementación del proyecto deben registrarse de manera sistemática y organizada en un repositorio de GitHub (privado), el cual deberá ser compartido con el respectivo coach (con el rol collaborator y permiso triage dentro de sus proyectos). Este procedimiento permite un seguimiento transparente y detallado del progreso del grupo, facilita la retroalimentación constante y oportuna, y fomenta un trabajo colaborativo, estructurado y eficiente. Para garantizar una correcta coordinación, en la Sección 7 (Asesorías) se encuentran los nombres de usuario de los coaches, lo que permitirá al grupo compartir el repositorio de manera adecuada y asegurar que el acceso y la supervisión se realicen sin contratiempos. De esta forma, se fortalece la trazabilidad de los avances, se promueve la responsabilidad compartida y se asegura que cada etapa de la implementación se documente y revise conforme a los estándares académicos del proyecto.


---

<!-- Página 9 del PDF original -->

| Sem | Fecha | Actividades |
| --- | --- | --- |
| 1 | 18 Ago / 23 Ago | - Repaso Linux, Bash, Python - Revisión del diplomado en Cloud Computing & otra bibliografía. |
| 2 | 25 Ago / 30 Ago | - Repaso de Linux Networking y Linux Process Management - Lab 1: Bash & Python scripting + Linux Process Management - Primera exposición y discusión del proyecto y sus alcances. |
| 3 | 01 Sep / 06 Sep | - Revisión del diplomado en Cloud Computing & otra bibliografía - Revisión de tesis de Ruben Cordova y Antonio Merino - Lecturas adicionales provistas por “coach” y los miembros. - Redacción de requerimientos del proyecto |
| 4 | 08 Sep / 13 Sep | - Repaso de Tecnologías de Virtualización - Lab 2: Aprovisionamiento de un slice de VMs en un solo host. Presentar, como parte del reporte final del lab 2: 1. concepto de operación y/o casos de uso 2. descripción de entidades y roles en su solución 3. bosquejo de arquitectura (módulos e interacciones entre ellos). |
| 5 | 15 Sep / 20 Sep | - Repaso de Tecnologías de Virtualización (cont.) Presentar: 1. Desarrollo del borrador de arquitectura de solución: módulos y sus funciones. |
| 6 | 22 Sep / 27 Sep | - Repaso de Tecnologías de Virtualización (cont.) - Lab 3: Avances de la arquitectura proyecto + aprovisionamiento de Slices en múltiples hosts LINUX (parte 1) - FEEDBACK DEL PROFESOR Presentar 1. El documento y PPT con desarrollo de arquitectura debe subirse a PAIDEIA 1 día antes del Lab 3. |
| 7 | 29 Sep / 04 Oct | 1. Repaso de Tecnologías de Virtualización (cont.) 2. FEEDBACK DEL PROFESOR (en clase, grupo G7) Presentar: 3. Primera versión de código para despliegue de slices(lineal y anillo) en múltiples hosts LINUX (sin APIS, sólo funciones). |
| 8 | 06 Oct / 11 Oct | 1. Repaso del problema de “VM Placement” 2. Lab 4: aprovisionamiento de un slice de VMs en múltiples hosts LINUX (parte 2) Presentar: 3. El documento con HLD (R2 - Soporte para LINUX CLUSTER) debe subirse a paideia 1 día antes del Lab 4 (parte de nota del lab) 4. Exposición en el laboratorio del documento presentado. |


---

<!-- Página 10 del PDF original -->

| Sem | Fecha | Actividades |
| --- | --- | --- |
| 9 | 13 Oct / 18 Oct | - 1RA PRESENTACIÓN PROYECTO: - ARQUITECTURA GENERAL DEL PROYECTO - DISEÑO HIGH LEVEL DE LOS MÓDULOS R1, R1B y R1C, R2, y R5. - LA IMPLEMENTACIÓN DEL MÓDULO R2(Soporte de Linux Cluster). El módulo R2 deberá interactuar con el driver(SDK) que hayan definido como parte de sus módulos y para probar el funcionamiento deberán desplegar la siguiente topología (EX1-Topology), además de las pre-definidas (lineal y anillo). |
| 10 | 20 Oct / 25 Oct | - Repaso del problema de “VM Placement” (cont.) Presentar: 1. Desarrollo del High level software design de los módulos R3 y R4. |
| 11 | 27 Oct / 01 Nov | - Repaso de OpenStack - Lab 5: Análisis y despliegue de OpenStack, creación de topología usando CLI. Presentar 1. Implementación completa del User Interface (R1B). |
| 12 | 03 Nov / 08 Nov | - Repaso de OpenStack (cont.) - Revisión de tesis de Gabriel Gamero. - Definición con coaches del plan de pruebas. - Implementación completa de los requerimientos R1C y R5. - Unit testing: la aplicación imprime el output de todos los comandos que enviaría al resto de módulos pendientes de implementación |
| 13 | 10 Nov / 15 Nov | - Repaso de Contenedores - Lab 6: Despliegue de topología usando APIs de OpenStack / Plan de pruebas de todos los módulos - FEEDBACK DEL PROFESOR . o Experiencia de Lab: presentación de la implementación, el plan de pruebas y los resultados de las pruebas realizadas hasta el momento. Presentar: 1. Un(1) día antes del Lab 6 deben subir el plan de pruebas. |
| 14 | 17 Nov / 22 Nov | - Repaso de Contenedores (cont.) - Completar la implementación de los módulos R3 (despliegue de VMs en OpenStack) y R4 (algoritmo de VM Placement). |
| 15 | 24 Nov / 29 Novl | - El mercado de Cloud Computing - Lab 7: Diseño, Implementación y UNIT testing del mecanismo de VM Placement |
| 16 | 01 Dic / 06 Dic | - PRESENTACIÓN FINAL |


---

<!-- Página 11 del PDF original -->

## 6. ENTREGABLES


| Entrega | Documento requerido |
| --- | --- |
| Primera Entrega | 1. Arquitectura de la solución (documento PDF, requerimiento R1) incluyendo APIs y/o IPC (arquitectura del resto de requerimientos). Debe indicar cómo la arquitectura permite satisfacer sus requerimientos. |
| Primera Entrega | 2. High level software design (documento PDF) de los requerimientos R1B, R1C, R2, y R5(incluido R0 primera parte). |
| Primera Entrega | 3. Copia de presentación (powerpoint, PDF, etc.) |
| Primera Entrega | 4. Código actual, incluyendo especialmente el código relacionado al requerimiento R2 |
| Primera Entrega | 5. Durante el examen parcial: Demo del despliegue de slide predefinida (req. R2). |
| Entrega Final | 6. High level software design (documento PDF) de todos los módulos. Presentar en un mismo documento con la arquitectura (actualizada de ser necesario) |
| Entrega Final | 7. Plan de pruebas y reporte de plan de pruebas. |
| Entrega Final | 8. Copia de presentación (powerpoint, PDF, etc.) |
| Entrega Final | 9. Código de la versión final de su prototipo. |
| Entrega Final | 10. Durante examen final: Demostración de funciones a pedido de los jurados. |


---

<!-- Página 12 del PDF original -->

## 7. ASESORÍAS


| Horario | Grupo | Coach | Usuario GIT | Reunión semanal | Miembros |
| --- | --- | --- | --- | --- | --- |
| H0991 | G1 | Branko Zambrano | jbzambrano | Martes 8:00 PM | Carlos Gómez - 20070429 Samantha Sanchez* - 20172234 Christian Gonzales - 20182758 Andrés Lujan - 20191450 |
| H0991 | G2 | Ronny Pastor | RonnyPastor | Miércoles 8:00 PM / Viernes 8:00 PM | Luis Araujo - 20201862 Sergio Ordaya - 20202137 Kiara Ccala - 20206303 Miguel Alvizuri - 20212472 Gonzalo Alvarez - 20216352 |
| H0991 | G3 | Anthony García | anthonygarciam | Martes 9:00 PM / Miércoles 9:00 PM | Oscar Agreda - 20193315 Jose Morillos (L) - 20193733 Yosthim Enciso - 20201497 Alejandro Hancco - 20213801 |
| H0992 | G4 | Branko Zambrano | jbzambrano | Miércoles 8:00 PM | Alexander Abrisqueta - 20191641 Adrian Lopez - 20192733 Jesús Alvarado* - 20211688 Nilo Cori - 20213745 |
| H0992 | G5 | Fernando Guzman | fernandoguzmann | Jueves 2:00PM | Pedro Bustamente - 20206156 David Escobedo - 20210850 Santiago Yong - 20210751 Jean Piere Ipurre* - 20213733 |
| H0992 | G6 | Diana Sologuren | dianasologurenr | Miércoles 3:00 PM / Viernes 3:00 PM | Adrián Tipo - 20206466 Roberto Tafur - 20210535 Eduardo Garay - 20212591 José Calderón - 20216256 |
| H0992 | G7 | Juan Manuel Becerra | jmanu24 | Jueves 5:00 PM | Piero Fernandez - 20180524 Christopher Terrones - 20182048 Fabricio Estrada (L) - 20210795 Jostin Pino - 20213830 Brandon Tacuri - 20215433 |


(*) Se presume que es el líder, pues fue quien mandó el correo. Caso contrario, contactar al profesor.


---

<!-- Página 13 del PDF original -->

## 8. ROL DE PRESENTACIONES [RETROALIMENTACIÓN DEL PROFESOR]


| Presentación | Fecha | Grupos |
| --- | --- | --- |
| Concepto de Operación | Martes 02 Sep, 5:00PM (Clase sem 3) | G3, G6, G7 |
| Casos de Uso | Martes 09 Sep, 5:00PM (Clase sem 4) | G1, G4 |
| Bosquejo de arquitectura | Martes 16 Sep, 5:00PM (Clase sem 5) | G2, G5 |
| 1ra presentación (Arquitectura, etc.) | Martes 23 Sep, 5:00PM (Clase Sem 6) | G1, G4 |
| 1ra presentación (Arquitectura, etc.) | Martes 23 Sep, 8:00PM (Lab 3 H0991) | G2, G3 |
| 1ra presentación (Arquitectura, etc.) | Jueves 25 Sep, 5:00PM (Lab 3 H0992) | G5, G6 |
| 1ra presentación (Arquitectura, etc.) | Martes 30 Sep, 5:00PM (Clase sem 7) | G7 |
| Algoritmo de VM Placement & estrategia de monitoreo de recursos | Martes 28 Oct, 4:00PM (Clase sem 11) | Por definir |
| Configuración de OpenStack cluster (R3) | Martes 04 Nov, 4:00PM (Clase sem 12) | Por definir |
| 2da presentación (Plan de pruebas, etc.) | Martes 11 Nov, 5:00PM (Clase sem 13) | G3, G7 |
| 2da presentación (Plan de pruebas, etc.) | Martes 11 Nov, 8:00PM (Lab 6 H0991) | G1 y G2 |
| 2da presentación (Plan de pruebas, etc.) | Jueves 13 Nov, 5:00PM (Lab 6 H0992) | G5 y G6 |
| 2da presentación (Plan de pruebas, etc.) | Martes 18 Nov, 5:00PM (Clase sem 14) | G4 |


---

<!-- Página 14 del PDF original -->

## 9. CALIFICACIÓN DEL CURSO


La nota final del curso se calculará con la siguiente fórmula:


**Fórmula de calificación:** `Nf = 0.4Pb + 0.3Ex1 + 0.3Ex2`

- **Pb:** Promedio de los 7 laboratorios.
- **Ex1:** Nota asignada a la primera entrega del proyecto.
- **Ex2:** Nota asignada a la segunda (y final) entrega del proyecto.


A continuación se muestra una tabla con la distribución de puntajes


| Concepto | R0 | R1 | R1B | R1C | R2 | R3 | R4 | R5 | Total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Arq / Doc | 8 | 40 | 6 | 6 | 6 | 12 | 18 | 10 | 106 |
| Imp | 14 | N/A | 12 | 12 | 12 | 18 | 12 | 14 | 94 |
|  | 22 | 40 | 18 | 18 | 18 | 30 | 30 | 24 | 200 |


**Nota de EX1:** corresponde a los requerimientos R0, R1, R1B y R1C, R5 ( más el componente de arquitectura y documentación para R0), más la componente de arquitectura / implementación del módulo R2. Total 100 pts. Rúbrica de calificación: Ver sección 10. Script de validación: scriptEx1


**Nota de EX2:** corresponde al componente de implementación de los requerimientos R1B,R1C; además de R0(documentación) y finalmente R5 más el componente de diseño/arquitectura de los requerimientos R3 y R4. Total 100 pts. Rúbrica de calificación: Ver sección 11 Script de validación: scriptEx2


En ambas presentaciones, basta obtener 20*(número de integrantes) de los 100 puntos para ser asignado el puntaje máximo.


---

<!-- Páginas 15 y 16 del PDF original: transcripción detallada -->

## 10. TEMPLATE DE EVALUACIÓN — EX1

> **Fuente oficial:** `TEL141-Proyecto_del_curso-2025-2-V1(6).pdf`, secciones 10 y 11, páginas 15–18. El documento fuente dice 2025-2; el usuario ha confirmado que el mismo enunciado se utiliza en su curso 2026-2. Se conserva esta distinción y no se alteran los criterios.
>
> **Metodología:** transcripción desde las tablas incrustadas como imágenes en el PDF. Los identificadores EX1-... / EX2-... y los cálculos de puntos equivalentes se añadieron para trazabilidad y **no** forman parte de la rúbrica original. Los campos de evidencia están vacíos por defecto.


**EX1: 100 puntos** repartidos en 88 puntos de arquitectura/diseño y 12 puntos de implementación de R2. Los ítems especiales de rendimiento adicionales (al final de la página 16) se muestran aparte; no se suman automáticamente al total de 100.

## Resumen de puntajes

| Bloque | Tipo | Puntaje máximo | Fuente |
|---|---|---:|---|
| R0 | Arquitectura / Diseño | 8,00 | p. 15 |
| R1 | Arquitectura / Diseño | 40,00 | p. 15 |
| R1B | Arquitectura / Diseño | 6,00 | p. 15 |
| R1C | Arquitectura / Diseño | 18,00 | p. 15 |
| R2 | Arquitectura / Diseño | 6,00 | p. 16 |
| R5 | Arquitectura / Diseño | 10,00 | p. 16 |
| R2 | Implementación | 12,00 | p. 16 |
| **Total** | | **100,00** | |

## R0 — presentación y documentación — 8,00 puntos

*Página 15 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Puntos | ¿Cumplió? | Evidencia / ubicación |
|---|---|---:|---|---|
| `EX1-R0-D-01` | Claridad y buena organización de la exposición | 1,50 | N/A — evaluación del jurado | Pendiente |
| `EX1-R0-D-02` | Manejo de medios | 1,00 | N/A — evaluación del jurado | Pendiente |
| `EX1-R0-D-03` | Porcentaje de cobertura de requerimientos | 2,00 | N/A — evaluación del jurado | Pendiente |
| `EX1-R0-D-04` | Cohesión y trabajo en equipo (sinergia) | 0,50 | N/A — evaluación del jurado | Pendiente |
| `EX1-R0-D-05` | Orden y redacción en la documentación | 1,50 | N/A — evaluación del jurado | Pendiente |
| `EX1-R0-D-06` | Especificación de APIs | 1,50 | N/A — evaluación del jurado | Pendiente |
| **Subtotal R0-D** | | **8,00** | | |


## R1 — arquitectura genérica — 40,00 puntos

*Página 15 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Puntos | ¿Cumplió? | Evidencia / ubicación |
|---|---|---:|---|---|
| `EX1-R1-D-01` | Separación adecuada de plataformas (AWS, OpenStack, Linux Cluster, etc.) | 5,00 | Pendiente de verificar | Pendiente |
| `EX1-R1-D-02` | Modularidad (General) | 2,00 | Pendiente de verificar | Pendiente |
| `EX1-R1-D-03` | Modularidad - permite agregar/remover hardware fácilmente y sin detener la operatividad del sistema. | 3,00 | Pendiente de verificar | Pendiente |
| `EX1-R1-D-04` | Modularidad - Permite actualizar módulos independientemente y sin detener la operatividad del sistema (p.ej., DevOps) | 4,00 | Pendiente de verificar | Pendiente |
| `EX1-R1-D-05` | Modularidad - Enfoque de Seguridad (minimizar la exposición de cada módulo, y minimizar el impacto de un módulo/servicio comprometido) | 4,00 | Pendiente de verificar | Pendiente |
| `EX1-R1-D-06` | Escalabilidad - permite dimensionar cada módulo de manera independiente en respuesta a altas cargas (número de pedidos concurrentes) | 2,00 | Pendiente de verificar | Pendiente |
| `EX1-R1-D-07` | Escalabilidad - módulos pueden estar desplegados en máquinas distintas en casos de alta carga: capacidad para la comunicación en red de los módulos. | 2,00 | Pendiente de verificar | Pendiente |
| `EX1-R1-D-08` | Capacidad para almacenar de forma persistente la información de slices | 3,00 | Pendiente de verificar | Pendiente |
| `EX1-R1-D-09` | Capacidad para retomar la edición de una slice en un momento posterior | 3,00 | Pendiente de verificar | Pendiente |
| `EX1-R1-D-10` | Performance: Capacidad para permitir concurrencia/paralelismo al editar slices | 3,00 | Pendiente de verificar | Pendiente |
| `EX1-R1-D-11` | Performance: Capacidad para permitir concurrencia/paralelismo al desplegar slices | 4,00 | Pendiente de verificar | Pendiente |
| `EX1-R1-D-12` | Soporta la creación de logs | 5,00 | Pendiente de verificar | Pendiente |
| **Subtotal R1-D** | | **40,00** | | |


## R1B — interfaz de usuario, diseño — 6,00 puntos

*Página 15 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Puntos | ¿Cumplió? | Evidencia / ubicación |
|---|---|---:|---|---|
| `EX1-R1B-D-01` | Capacidad para soportar concurrencia de usuarios | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R1B-D-02` | Capacidad para editar, listar, y eliminar slices | 0,50 | Pendiente de verificar | Pendiente |
| `EX1-R1B-D-03` | Capacidad para configurar slices con topologías predefinidas (num nodos, num cores, MEM, almacenamiento, etc.) | 0,50 | Pendiente de verificar | Pendiente |
| `EX1-R1B-D-04` | Capacidad para componer y editar slices arbitrarias con el apoyo de topologías predefinidas | 2,00 | Pendiente de verificar | Pendiente |
| `EX1-R1B-D-05` | Capacidad de exportar plantillas con la configuración de un slice y capacidad de importar estas plantillas para sobre la base de ella crear una nueva slice. | 0,50 | Pendiente de verificar | Pendiente |
| `EX1-R1B-D-06` | Capacidad para visualizar el consumo de recursos | 0,50 | Pendiente de verificar | Pendiente |
| `EX1-R1B-D-07` | Capacidad para importar imágenes | 0,50 | Pendiente de verificar | Pendiente |
| `EX1-R1B-D-08` | Capacidad para proveer tokens de acceso a la consola virtual de las VMs | 0,50 | Pendiente de verificar | Pendiente |
| **Subtotal R1B-D** | | **6,00** | | |


## R1C — Slice Manager, diseño — 18,00 puntos

*Página 15 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Puntos | ¿Cumplió? | Evidencia / ubicación |
|---|---|---:|---|---|
| `EX1-R1C-D-01` | Flujo de trabajo completo (produce un slice que cumple todos los requerimientos) y en el orden correcto | 4,00 | Pendiente de verificar | Pendiente |
| `EX1-R1C-D-02` | Paralelismo/rapidez en el despliegue de slices | 2,00 | Pendiente de verificar | Pendiente |
| `EX1-R1C-D-03` | No tiene "race condition" u "overcommitting" de recursos. | 2,00 | Pendiente de verificar | Pendiente |
| `EX1-R1C-D-04` | Capacidad para monitorear los recursos asignados | 4,00 | Pendiente de verificar | Pendiente |
| `EX1-R1C-D-05` | Capacidad para validar la consistencia de los recursos asignados | 3,00 | Pendiente de verificar | Pendiente |
| `EX1-R1C-D-06` | Capacidad para validar que los requests vengan de un módulo autorizado y/o hayan sido hechos por un usuario autenticado y que tenga autorización para realizar la acción | 3,00 | Pendiente de verificar | Pendiente |
| **Subtotal R1C-D** | | **18,00** | | |


## R2 — soporte Linux, diseño — 6,00 puntos

*Página 16 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Puntos | ¿Cumplió? | Evidencia / ubicación |
|---|---|---:|---|---|
| `EX1-R2-D-01` | Selección de las tecnologías adecuadas para implementar el cluster | 1,50 | Pendiente de verificar | Pendiente |
| `EX1-R2-D-02` | Robustez de diseño / Error handling de las API del cluster | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-D-03` | Seguridad - minimiza la exposición de información/recursos del cluster a terceros. | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-D-04` | Permite agregar/remover nodos (workers) con la mínima disrupción/necesidad de cambios. | 0,50 | Pendiente de verificar | Pendiente |
| `EX1-R2-D-05` | Capacidad para monitoreo de recursos utilizados | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-D-06` | Permite el acceso a las VMs por consola virtual | 0,50 | Pendiente de verificar | Pendiente |
| `EX1-R2-D-07` | Capacidad para realizar el troubleshooting de cada slice por separado | 0,50 | Pendiente de verificar | Pendiente |
| **Subtotal R2-D** | | **6,00** | | |


## R5 — networking y seguridad, diseño — 10,00 puntos

*Página 16 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Puntos | ¿Cumplió? | Evidencia / ubicación |
|---|---|---:|---|---|
| `EX1-R5-D-01` | Capacidad para proveer salida a redes externas | 3,00 | Pendiente de verificar | Pendiente |
| `EX1-R5-D-02` | Capacidad para permitir el acceso desde el exterior (equivalente a una IP pública) a las VMs que lo requieran (selectivamente, brindando seguridad a las VMs frente a accesos no autorizados) | 3,00 | Pendiente de verificar | Pendiente |
| `EX1-R5-D-03` | Capacidad para utilizar VLANs en vez de túneles | 2,00 | Pendiente de verificar | Pendiente |
| `EX1-R5-D-04` | Capacidad para reconfigurar el switch de la infraestructura | 2,00 | Pendiente de verificar | Pendiente |
| **Subtotal R5-D** | | **10,00** | | |


## R2 — soporte Linux, implementación — 12,00 puntos

*Página 16 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Puntos | ¿Cumplió? | Evidencia / ubicación |
|---|---|---:|---|---|
| `EX1-R2-I-01` | Pudo desplegar las VMs en los servidores seleccionados, usando tecnologías de linux | 1,50 | Pendiente de verificar | Pendiente |
| `EX1-R2-I-02` | Pudo desplegar los enlaces entre VMs alojadas en diferentes servidores | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-I-03` | Implementa completamente la API diseñada | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-I-04` | Lidia con errores/reintentos | 0,50 | Pendiente de verificar | Pendiente |
| `EX1-R2-I-05` | Implementa el envío/manejo de imágenes para las VMs | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-I-06` | Implementa el borrado de las VMs y demás recursos (p.ej., interfaces TUN/TAP, OVSes, etc.) | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-I-07` | Implementa un mecanismo de acceso a las VMs vía consola virtual, proveyendo los tokens necesarios. | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-I-08` | Implementa la salida internet a las VMs que lo requieran | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-I-09` | Implementa el acceso desde internet (vía IP públicas) a las VMs que lo requieran | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-I-10` | Uso eficiente del espacio en disco usando el formato QCOW | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-I-11` | Escalabilidad: Soporta pedidos concurrentes | 1,00 | Pendiente de verificar | Pendiente |
| `EX1-R2-I-12` | Realiza borrado inteligente, es decir, elimina imágenes de VMs que no están siendo usadas (en los servidores). | 1,00 | Pendiente de verificar | Pendiente |
| **Subtotal R2-I** | | **12,00** | | |


## Características adicionales de Linux Cluster (página 16)

**Estos ítems están separados del bloque ordinario R2 de 12 puntos.** El PDF presenta una fila sin puntaje y otra con `3` puntos; se reproducen sin asumir que cambien el total oficial de EX1.

| ID agregado | Característica adicional | Puntaje visible en fuente |
|---|---|---|
| `EX1-R2-EXTRA-01` | Maneja un cache de imágenes que balancea el espacio en disco versus la velocidad para desplegar VMs | No indicado |
| `EX1-R2-EXTRA-02` | Uso e implementación de QinQ para no tener la limitante de 2^12 enlaces aprox. | 3,00 |

## Imágenes originales de EX1

![EX1, tabla de arquitectura y diseño, página 15](TEL141_Proyecto_Cloud_assets/rubrica_EX1_pagina_15.png)

![EX1, continuación de diseño e implementación de Linux, página 16](TEL141_Proyecto_Cloud_assets/rubrica_EX1_pagina_16.png)

---
**Nota de fidelidad:** se conservó el criterio «No tiene race condition u overcommitting» tal como aparece en EX1, aunque otras partes del proyecto admitan sobreasignación controlada. Esa diferencia se debe analizar, no corregir silenciosamente.


---

<!-- Páginas 17 y 18 del PDF original: transcripción detallada -->

## 11. TEMPLATE DE EVALUACIÓN — EX2

> **Fuente oficial:** `TEL141-Proyecto_del_curso-2025-2-V1(6).pdf`, secciones 10 y 11, páginas 15–18. El documento fuente dice 2025-2; el usuario ha confirmado que el mismo enunciado se utiliza en su curso 2026-2. Se conserva esta distinción y no se alteran los criterios.
>
> **Metodología:** transcripción desde las tablas incrustadas como imágenes en el PDF. Los identificadores EX1-... / EX2-... y los cálculos de puntos equivalentes se añadieron para trazabilidad y **no** forman parte de la rúbrica original. Los campos de evidencia están vacíos por defecto.


**EX2: 100 puntos.** En esta plantilla la columna **«Peso»** expresa porcentajes dentro de cada bloque; **no son puntos directos**. La columna «Puntos equivalentes» es una cuenta auxiliar: `puntaje del bloque × peso / 100`.

## Distribución de puntos EX2

| Bloque | Puntaje máximo | Página fuente |
|---|---:|---|
| R0 — presentación, documentación y diseño | 14,00 | 17 |
| R3 — diseño del despliegue OpenStack | 12,00 | 17 |
| R4 — diseño de VM Placement | 18,00 | 17 |
| R1B — implementación de interfaz y ciclo de vida | 12,00 | 18 |
| R3 — implementación OpenStack | 18,00 | 18 |
| R4 — implementación de VM Placement | 12,00 | 18 |
| R5 — implementación de networking y seguridad | 14,00 | 18 |
| **Total** | **100,00** | |

> **Advertencia documental:** la sección 9 del enunciado menciona R1C en la composición de EX2, mientras que la plantilla detallada de EX2 (págs. 17–18) no tiene una fila/bloque R1C independiente. No se ha añadido ni reasignado puntaje a R1C en esta transcripción. Debe confirmarse con el docente si existe una versión actualizada de la rúbrica.

## R0 — presentación, documentación y diseño — 14,00 puntos

*Página 17 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Peso dentro del bloque (%) | Puntos equivalentes | ¿Cumplió? | Evidencia |
|---|---|---:|---:|---|---|
| `EX2-R0-D-01` | Claridad de exposición y respuesta a preguntas | 35,00 | 4,90 | N/A — evaluación del jurado | Pendiente |
| `EX2-R0-D-02` | High Level Software Design claramente documentado | 35,00 | 4,90 | N/A — evaluación del jurado | Pendiente |
| `EX2-R0-D-03` | Reporte de pruebas: completo y bien documentado | 30,00 | 4,20 | N/A — evaluación del jurado | Pendiente |
| **Subtotal R0-D** | | **100,00** | **14,00** | | |


## R3 — diseño del despliegue OpenStack — 12,00 puntos

*Página 17 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Peso dentro del bloque (%) | Puntos equivalentes | ¿Cumplió? | Evidencia |
|---|---|---:|---:|---|---|
| `EX2-R3-D-01` | Consideración en diseño y fundamentación de los mínimos servicios requeridos (Keystone, Horizon, Nova, Neutron & ML2 Plugin, Glance) | 20,00 | 2,40 | Pendiente de verificar | Pendiente |
| `EX2-R3-D-02` | Uso eficiente (p.ej., paralelo, manejo de errores, auth de módulos, uso de caché) de APIs de OpenStack en el despliegue de VMs sobre OpenStack | 25,00 | 3,00 | Pendiente de verificar | Pendiente |
| `EX2-R3-D-03` | Permite orquestar VM usando OpenStack (Topologías personalizadas y predefinidas) | 25,00 | 3,00 | Pendiente de verificar | Pendiente |
| `EX2-R3-D-04` | Diseño permite crear topologías capa 2. | 20,00 | 2,40 | Pendiente de verificar | Pendiente |
| `EX2-R3-D-05` | Permite visualizar los proyectos desplegados por usuario (p.ej., en Horizon) | 10,00 | 1,20 | Pendiente de verificar | Pendiente |
| **Subtotal R3-D** | | **100,00** | **12,00** | | |


## R4 — diseño de VM Placement — 18,00 puntos

*Página 17 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Peso dentro del bloque (%) | Puntos equivalentes | ¿Cumplió? | Evidencia |
|---|---|---:|---:|---|---|
| `EX2-R4-D-01` | Estrategia de monitoreo de recursos es consistente con el algoritmo a desarrollar y con el evitar superar el máximo nivel de congestión permitido. | 15,00 | 2,70 | Pendiente de verificar | Pendiente |
| `EX2-R4-D-02` | Algoritmo de aprovisionamiento de VMs tiene función objetivo bien definida y sustentada. | 20,00 | 3,60 | Pendiente de verificar | Pendiente |
| `EX2-R4-D-03` | Algoritmo considera uso eficiente (utilización) de recursos para aquellas cargas dinámicas que no consumen (en todo momento) el 100% de recursos y pueden soportar que sus recursos (p.ej., cores físicos) sean compartidos. | 15,00 | 2,70 | Pendiente de verificar | Pendiente |
| `EX2-R4-D-04` | Algoritmo considera no solo la utilización actual, sino el estimado de la congestión durante el ciclo de vida del slice. Tanto el impacto de un número grande de asignaciones de VMs con baja utilización (pero que podrían variar/aumentar en el tiempo), como el impacto de asignaciones recientes cuyo uso aún no se ve reflejado en las mediciones (p.ej., aún no bootea la VM). | 15,00 | 2,70 | Pendiente de verificar | Pendiente |
| `EX2-R4-D-05` | Algoritmo de aprovisionamiento de VMs considera slices como un todo, y no VMs individuales. | 15,00 | 2,70 | Pendiente de verificar | Pendiente |
| `EX2-R4-D-06` | Algoritmo considera/limita el tiempo de ejecución para instancias (osea, slices) grandes | 10,00 | 1,80 | Pendiente de verificar | Pendiente |
| `EX2-R4-D-07` | Considera la zona de disponibilidad pedida al colocar las VMs. | 10,00 | 1,80 | Pendiente de verificar | Pendiente |
| **Subtotal R4-D** | | **100,00** | **18,00** | | |


## R1B — implementación de interfaz y ciclo de vida — 12,00 puntos

*Página 18 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Peso dentro del bloque (%) | Puntos equivalentes | ¿Cumplió? | Evidencia |
|---|---|---:|---:|---|---|
| `EX2-R1B-I-01` | Ser independiente de la capa de infraestructura (cluster de servidores Linux, OpenStack, AWS, etc.). | 10,00 | 1,20 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-02` | Implementación soporta concurrencia de usuarios | 10,00 | 1,20 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-03` | Permite seleccionar slices con topologías predefinidas: lineal, malla, árbol, anillo, y bus. | 10,00 | 1,20 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-04` | Permite editar slices (aún no desplegadas) combinando topologías predefinidas | 10,00 | 1,20 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-05` | Permite editar slices (aún no desplegadas) agregando nodos y enlaces. | 10,00 | 1,20 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-06` | Permite grabar slices (aún no desplegadas) para posterior edición | 5,00 | 0,60 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-07` | Permite exportar topologías | 5,00 | 0,60 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-08` | Permite importar topologías | 5,00 | 0,60 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-09` | Permite crear nuevos slices sobre la base de editar topologías importadas | 5,00 | 0,60 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-10` | Permite especificar la configuración (capacidad) de cada máquina virtual (VM) creada. | 5,00 | 0,60 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-11` | Lista la información necesaria de los slices que le pertenecen al usuario. | 5,00 | 0,60 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-12` | Permite visualizar el consumo de recursos del sistema | 5,00 | 0,60 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-13` | Permite borrar o editar slices previamente instanciados | 5,00 | 0,60 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-14` | Permite importar imágenes de VMs en forma independiente de la plataforma | 5,00 | 0,60 | Pendiente de verificar | Pendiente |
| `EX2-R1B-I-15` | Provee los tokens/credenciales necesarias para que el dueño del slice pueda acceder a la consola virtual de cada VM. | 5,00 | 0,60 | Pendiente de verificar | Pendiente |
| **Subtotal R1B-I** | | **100,00** | **12,00** | | |


## R3 — implementación OpenStack — 18,00 puntos

*Página 18 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Peso dentro del bloque (%) | Puntos equivalentes | ¿Cumplió? | Evidencia |
|---|---|---:|---:|---|---|
| `EX2-R3-I-01` | Implementó OpenStack con al menos los mínimos servicios requeridos (Keystone, Horizon, Nova, Neutron & ML2 plugin, Glance) | 20,00 | 3,60 | Pendiente de verificar | Pendiente |
| `EX2-R3-I-02` | Orquesta Topologías (predefinidas y personalizadas) usando OpenStack | 30,00 | 5,40 | Pendiente de verificar | Pendiente |
| `EX2-R3-I-03` | Orquesta slices/topologías en capa 2 | 20,00 | 3,60 | Pendiente de verificar | Pendiente |
| `EX2-R3-I-04` | Uso eficiente (p.ej., paralelo) de APIs de OpenStack en el despliegue de VMs sobre OpenStack | 10,00 | 1,80 | Pendiente de verificar | Pendiente |
| `EX2-R3-I-05` | Borrado slices | 10,00 | 1,80 | Pendiente de verificar | Pendiente |
| `EX2-R3-I-06` | Permite visualizar máquinas virtuales desplegadas en Horizon | 10,00 | 1,80 | Pendiente de verificar | Pendiente |
| **Subtotal R3-I** | | **100,00** | **18,00** | | |


## R4 — implementación de VM Placement — 12,00 puntos

*Página 18 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Peso dentro del bloque (%) | Puntos equivalentes | ¿Cumplió? | Evidencia |
|---|---|---:|---:|---|---|
| `EX2-R4-I-01` | Lista recursos(servidores) disponibles en ambas plataformas (Linux Cluster y OpenStack) | 20,00 | 2,40 | Pendiente de verificar | Pendiente |
| `EX2-R4-I-02` | Entrega una asignación de VMs a servidores de acuerdo al algoritmo diseñado en caso haya capacidad. | 50,00 | 6,00 | Pendiente de verificar | Pendiente |
| `EX2-R4-I-03` | Rechaza la asignación de VMs cuando no hay recursos disponibles, indicando la razón de la falla (logs o consola) | 20,00 | 2,40 | Pendiente de verificar | Pendiente |
| `EX2-R4-I-04` | Las VMs son asignadas a servidores en la zonas de disponibilidad elegida por el usuario. | 10,00 | 1,20 | Pendiente de verificar | Pendiente |
| **Subtotal R4-I** | | **100,00** | **12,00** | | |


## R5 — implementación de networking y seguridad — 14,00 puntos

*Página 18 del PDF.*

| ID agregado | Criterio de evaluación (transcripción) | Peso dentro del bloque (%) | Puntos equivalentes | ¿Cumplió? | Evidencia |
|---|---|---:|---:|---|---|
| `EX2-R5-I-01` | Usa VLANs para segmentar los enlaces/subredes minimizando el overhead (p.ej., no usa túneles en el Linux cluster ni redes "self-service" en OpenStack) | 15,00 | 2,10 | Pendiente de verificar | Pendiente |
| `EX2-R5-I-02` | Implementa las reglas de seguridad requeridas en los slices en el Linux cluster | 15,00 | 2,10 | Pendiente de verificar | Pendiente |
| `EX2-R5-I-03` | Implementa las reglas de seguridad requeridas en los slices en Openstack | 10,00 | 1,40 | Pendiente de verificar | Pendiente |
| `EX2-R5-I-04` | Provee de salida a internet a la máquinas que lo requieran (Linux Cluster y Openstack) | 15,00 | 2,10 | Pendiente de verificar | Pendiente |
| `EX2-R5-I-05` | Provee acceso desde internet (p.ej., SSH) a máquinas virtuales que lo requieran (Linux Cluster y Openstack) | 20,00 | 2,80 | Pendiente de verificar | Pendiente |
| `EX2-R5-I-06` | Configuran dinámicamente el switch físico para limitar los broadcasts de cada enlace virtual a los servidores que realmente los necesiten | 25,00 | 3,50 | Pendiente de verificar | Pendiente |
| **Subtotal R5-I** | | **100,00** | **14,00** | | |


## Imágenes originales de EX2

![EX2, presentación y diseño, página 17](TEL141_Proyecto_Cloud_assets/rubrica_EX2_pagina_17.png)

![EX2, implementación, página 18](TEL141_Proyecto_Cloud_assets/rubrica_EX2_pagina_18.png)

---

**Nota:** los textos de esta rúbrica se presentan como criterios de evaluación, no como afirmaciones de que el código G5 ya los cumple.
