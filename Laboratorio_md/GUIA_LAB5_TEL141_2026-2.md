# Guía del Laboratorio 5 — TEL141 Ingeniería de Redes Cloud

**PUCP — Facultad de Ciencias e Ingeniería · Semestre 2026-2**

- **Tema:** Instalación de OpenStack + uso de CLI.
- **Laboratorio:** N.° 5.
- **Profesor:** Rubén Córdova.
- **Jefe de laboratorio responsable:** Fernando Guzmán.
- **Fuente:** `GUIA_LAB-5_TEL141_2026-2(3).pdf` (47 páginas).

> **Nota de conversión:** se conserva el contenido de la guía, incluidos comandos,
> secuencias de configuración, preguntas, criterios y errores tipográficos de origen.
> Los prompts de terminal (`root@HeadNode:~#`, `root@WorkerX:~#`, `C:\>`)
> se omiten en los bloques de código para facilitar su lectura y copia; no implica que
> los comandos hayan sido ejecutados ni verificados. Los saltos de línea pueden reflejar
> la paginación del PDF. Las imágenes originales están en `GUIA_LAB5_assets/`.

## Índice

1. [Indicaciones y objetivos](#indicaciones-y-objetivos)
2. [Escenario global y conexiones SSH](#escenario-global-y-conexiones-ssh)
3. [Experiencia de laboratorio: instalación de OpenStack](#experiencia-de-laboratorio-instalación-de-openstack)
4. [Reporte final: topología P2P](#reporte-final-topología-p2p)
5. [Criterios de evaluación](#criterios-de-evaluación)
6. [Notas de fidelidad y posibles inconsistencias del original](#notas-de-fidelidad-y-posibles-inconsistencias-del-original)

---

## Indicaciones y objetivos

**Indicaciones generales (página 1):**

- Durante el laboratorio se puede usar el material provisto por los docentes y blogs de internet.
- Seguir atentamente las indicaciones de los jefes de práctica.
- Cualquier tipo de plagio será reportado a facultad.
- Es responsabilidad del alumno completar las actividades dentro de los plazos establecidos en la guía; de lo contrario, habrá penalidad individual o grupal.

**Objetivos:**

- Comprender la arquitectura de OpenStack e instalar OpenStack.
- Comprender y utilizar la CLI de OpenStack para crear redes y máquinas virtuales.

| N.º | Actividad | Tiempo estimado | Puntaje |
|---:|---|---|---:|
| 1 | Experiencia de Laboratorio | 2 horas | 5 ptos |
| 2 | Desempeño en el laboratorio | 2 horas | 2 ptos |
| 3 | Reporte Final | 2 horas | 6 ptos |
| 4 | Evaluación Continua del Proyecto | 2 horas | 2 ptos |
| 5 | Cuestionarios de clase | — | 5 ptos |

---

## Escenario global y conexiones SSH

<!-- Fuente: página 2 -->

La sección de Ingeniería de las Telecomunicaciones cuenta con una nube privada que ejecuta VNRT (Virtual Network Research Testbed), desarrollada por miembros del GIRA. VNRT permite crear y asignar slices de cómputo: máquinas virtuales interconectadas en capa 2 que emulan redes reales. Después del examen parcial, cada grupo dispone de una topología para la fase 2.

![Topología del slice de Cloud Computing, fase 2](GUIA_LAB5_assets/topologia_fase2.png)

*Figura original de la página 2: clúster Linux, clúster OpenStack, gateway, app, MGMT 1 (192.168.201.0/24), MGMT 2 (192.168.202.0/24), OVS1 y OVS2.*

<!-- Fuente: página 3 -->

Las VMs `app` y `gateway` tienen direcciones IP accesibles desde la red de la PUCP. Para conectarse con el resto de VMs se utiliza el gateway y su correspondiente puerto.

| Clúster | Dispositivo | Puerto SSH vía gateway |
|---|---|---:|
| Linux | server1 | 5811 |
| Linux | server2 | 5812 |
| Linux | server3 | 5813 |
| Linux | server4 | 5814 |
| Linux | ovs1 | 5815 |
| OpenStack | headnode | 5821 |
| OpenStack | worker1 | 5822 |
| OpenStack | worker2 | 5823 |
| OpenStack | worker3 | 5824 |
| OpenStack | ovs2 | 5825 |

**Ejemplo de acceso al HeadNode:**

```bash
ssh ubuntu@IP_Gateway -p 5821
```

> **Fidelidad de tabla:** el PDF original titula las dos columnas «PUERTO» y «DISPOSITIVO», aunque los valores aparecen en el orden dispositivo/puerto. Aquí se normalizan los encabezados, sin modificar los datos.

---

## Experiencia de laboratorio: instalación de OpenStack

<!-- Fuente: página 4 del PDF original -->

### Experiencia de laboratorio — indicaciones

Indicaciones generales:

- Puntaje total: 5 pts
- El desarrollo de la Experiencia de Laboratorio es GRUPAL.
- Las actividades de la “Experiencia de Laboratorio” deben ser desarrolladas sobre su copia del archivo TEL141_Lab5_EL_Template.docx, el cual se encuentra en sección “Laboratorio 5: Instalación de Openstack + uso de CLI / API” de PAIDEIA, en la actividad “EXPERIENCIA DE LABORATORIO [H099X]” según el horario que le corresponda. Debe cambiar el nombre del archivo a TEL141_Lab5_EL_GXXX.pdf, donde XXX es número de grupo PUCP. Al terminar, deberá subir este archivo en versión PDF.
- A lo largo de la guía encontrará las etiquetas Head Node, Worker Nodes y Local Host, esto lo ayudará a saber en qué nodo de su slice deberá ejecutar cada comando.
- La Experiencia de Laboratorio será entregada (en PAIDEIA) al finalizar la sesión síncrona del laboratorio de cada horario. No se podrán subir los informes después de dicha hora ni se recibirán por ningún otro medio.
- Es responsabilidad del alumno revisar y practicar los conceptos previos necesarios para el correcto desarrollo del laboratorio.

### ACTIVIDAD N° 1: Configuraciones Generales

#### Head Node

Configure el fichero /etc/hosts para resolver nombres

```bash
echo -e '192.168.202.1\tcontroller' >> /etc/hosts
echo -e '192.168.202.2\tcompute1' >> /etc/hosts
echo -e '192.168.202.3\tcompute2' >> /etc/hosts
echo -e '192.168.202.4\tcompute3' >> /etc/hosts
```

Agregue el dns de Google al fichero /etc/resolv.conf

```bash
echo 'nameserver 8.8.8.8' >> /etc/resolv.conf
```

<!-- Fuente: página 5 del PDF original -->

Actualizar repositorios

```bash
apt-get update
```

#### Worker Nodes

Configure el fichero /etc/hosts para resolver nombres

```bash
echo -e '192.168.202.1\tcontroller' >> /etc/hosts
echo -e '192.168.202.2\tcompute1' >> /etc/hosts
echo -e '192.168.202.3\tcompute2' >> /etc/hosts
echo -e '192.168.202.4\tcompute3' >> /etc/hosts
```

Agregue el dns de Google al fichero /etc/resolv.conf

```bash
echo 'nameserver 8.8.8.8' >> /etc/resolv.conf
```

Actualizar repositorios

```bash
apt-get update
```

### ACTIVIDAD N° 2: Generación de service passwords

#### Head Node

Cree y edite el archivo /root/service_passwords para establecer las contraseñas necesarias para la configuración de OpenStack

```bash
echo 'export ADMIN_PASS='$(openssl rand -hex 16) \
> ~/service_passwords
echo 'export CINDER_DBPASS='$(openssl rand -hex 16) \
>> ~/service_passwords
echo 'export CINDER_PASS='$(openssl rand -hex 16) \
>> ~/service_passwords
echo 'export DASH_DBPASS='$(openssl rand -hex 16) \
>> ~/service_passwords
echo 'export DEMO_PASS='$(openssl rand -hex 16) \
>> ~/service_passwords
```

<!-- Fuente: página 6 del PDF original -->

```bash
echo 'export GLANCE_DBPASS='$(openssl rand -hex 16) \
>> ~/service_passwords
echo 'export GLANCE_PASS='$(openssl rand -hex 16) \
>> ~/service_passwords
echo 'export KEYSTONE_DBPASS='$(openssl rand -hex 16) \
>> ~/service_passwords
echo 'export METADATA_SECRET='$(openssl rand -hex 16) \
>> ~/service_passwords
echo 'export NEUTRON_DBPASS='$(openssl rand -hex 16) \
>> ~/service_passwords
```

```bash
echo 'export NEUTRON_PASS='$(openssl rand -hex 16) \
>> ~/service_passwords
echo 'export NOVA_DBPASS='$(openssl rand -hex 16) \
>> ~/service_passwords
echo 'export NOVA_PASS='$(openssl rand -hex 16) \
>> ~/service_passwords
echo 'export PLACEMENT_PASS='$(openssl rand -hex 16) \
>> ~/service_passwords
echo 'export PLACEMENT_DBPASS='$(openssl rand -hex 16) \
>> ~/service_passwords
echo 'export RABBIT_PASS='$(openssl rand -hex 16) \
>> ~/service_passwords
```

Copie el archivo al directorio home del usuario ubuntu de los compute nodes

```bash
scp ~/service_passwords ubuntu@compute1:/home/ubuntu
scp ~/service_passwords ubuntu@compute2:/home/ubuntu
scp ~/service_passwords ubuntu@compute3:/home/ubuntu
```

#### Worker Nodes

Mueva el fichero de contraseñas ubicado en el directorio home del usuario ubuntu al home de root

```bash
mv /home/ubuntu/service_passwords ~
```

<!-- Fuente: página 7 del PDF original -->

### ACTIVIDAD N° 3: Chrony - Network Time Protocol

#### Head Node

Configure la zona horaria

```bash
timedatectl set-timezone America/Lima
```

Instale los paquetes

```bash
apt install chrony -y
```

Edite el archivo /etc/chrony/chrony.conf y agregue las direcciones precisas de los servidores NTP

```bash
sed -i '/^pool /s/^/# /' /etc/chrony/chrony.conf
echo 'server 0.south-america.pool.ntp.org iburst' \
>> /etc/chrony/chrony.conf
echo 'server 1.south-america.pool.ntp.org iburst' \
>> /etc/chrony/chrony.conf
echo 'server 2.south-america.pool.ntp.org iburst' \
>> /etc/chrony/chrony.conf
echo 'server 3.south-america.pool.ntp.org iburst' \
>> /etc/chrony/chrony.conf
```

Para permitir que otros nodos se conecten al chrony daemon del nodo controller, agregue una descripción de la red de management (192.168.202.0/24) al fichero chrony.conf mencionado anteriormente

```bash
echo 'allow 192.168.202.0/24' >> /etc/chrony/chrony.conf
```

Reinicie el servicio NTP

```bash
service chrony restart
```

<!-- Fuente: página 8 del PDF original -->

Verifique la sincronización NTP

```bash
chronyc sources
```

#### Worker Nodes

Configure la zona horaria

```bash
timedatectl set-timezone America/Lima
```

Instale los paquetes

```bash
apt install chrony -y
```

Configure el archivo /etc/chrony/chrony.conf para hacer referencia al controller node (head node)

```bash
sed -i '/^pool /s/^/# /' /etc/chrony/chrony.conf
echo 'server controller iburst' >> /etc/chrony/chrony.conf
```

Reinicie el servicio NTP

```bash
service chrony restart
```

Verifique la sincronización NTP

```bash
chronyc sources
```

#### Output esperado

<!-- Fuente: página 9 del PDF original -->

![Ejemplo de verificación de Chrony](GUIA_LAB5_assets/ejemplo_chrony.png)

*Captura original de `chronyc sources` (página 9).*

### ACTIVIDAD N° 4: Herramientas y Paquetes para Ubuntu 20.04

#### Head Node

Agregue el dns de Google al fichero /etc/resolv.conf

```bash
echo 'nameserver 8.8.8.8' >> /etc/resolv.conf
```

Instale el command-line client para OpenStack de python3

```bash
apt install python3-openstackclient -y
```

Instale crudini

```bash
apt-get install crudini -y
```

Habilite los paquetes de OpenStack Victoria para Ubuntu 20.04 LTS

```bash
add-apt-repository cloud-archive:victoria -y
```

#### Worker Nodes

Agregue el dns de Google al fichero /etc/resolv.conf

```bash
echo 'nameserver 8.8.8.8' >> /etc/resolv.conf
```

Instale crudini

```bash
apt-get install crudini -y
```

Habilite los paquetes de OpenStack Victoria para Ubuntu 20.04 LTS

<!-- Fuente: página 10 del PDF original -->

```bash
add-apt-repository cloud-archive:victoria -y
```

### ACTIVIDAD N° 5: MariaDB - Base de Datos SQL

#### Head Node

Instale los paquetes

```bash
apt install mariadb-server python3-pymysql -y
```

Cree y edite el fichero /etc/mysql/mariadb.conf.d/99-openstack.cnf: cree una sección [mysqld] y establezca la clave bind-address para la dirección IP de management del controller node (head node) para permitir el acceso de otros nodos a través de la red de administración. Configure claves adicionales para habilitar opciones útiles y el juego de caracteres UTF-8

```bash
echo '[mysqld]' > /etc/mysql/mariadb.conf.d/99-openstack.cnf
echo 'bind-address = 192.168.202.1' \
>> /etc/mysql/mariadb.conf.d/99-openstack.cnf
echo 'default-storage-engine = innodb' \
>> /etc/mysql/mariadb.conf.d/99-openstack.cnf
echo 'innodb_file_per_table = on' \
>> /etc/mysql/mariadb.conf.d/99-openstack.cnf
echo 'max_connections = 4096' \
>> /etc/mysql/mariadb.conf.d/99-openstack.cnf
echo 'collation-server = utf8_general_ci' \
>> /etc/mysql/mariadb.conf.d/99-openstack.cnf
echo 'character-set-server = utf8' \
>> /etc/mysql/mariadb.conf.d/99-openstack.cnf
```

Reinicie el servicio de base de datos

```bash
service mysql restart
```

Asegure el servicio de base de datos ejecutando ‘mysql_secure_installation’, en particular, elija la contraseña root para la cuenta root de la base de datos y ‘Y’ para cualquier consulta de tipo ‘[Y/n]’

<!-- Fuente: página 11 del PDF original -->

```bash
mysql_secure_installation
```

### ACTIVIDAD N° 6: RABBITMQ - Cola de Mensajes

#### Head Node

Instale el paquete

```bash
apt install rabbitmq-server -y
```

Cargue el fichero service_passwords

```bash
. /root/service_passwords
```

Agregue el usuario openstack

```bash
rabbitmqctl add_user openstack $RABBIT_PASS
```

Permitir acceso de configuración, escritura y lectura al usuario openstack

```bash
rabbitmqctl set_permissions openstack ".*" ".*" ".*"
```

### ACTIVIDAD N° 7: Memcached - Almacenamiento en caché

#### Head Node

Instale los paquetes

```bash
apt install memcached python3-memcache
```

Edite el archivo /etc/memcached.conf y configure el servicio para utilizar la dirección IP de management del controller node (head node). Esto es para permitir el acceso de otros nodos a través de la red de administración

```bash
sed -i 's/127.0.0.1/192.168.202.1/g' /etc/memcached.conf
```

<!-- Fuente: página 12 del PDF original -->

Reinicie el servicio Memcached

```bash
service memcached restart
```

### ACTIVIDAD N° 8: Etcd - Almacenamiento de datos clave-valor

#### Head Node

Instale el paquete etcd

```bash
apt install etcd -y
```

Edite el archivo /etc/default/etcd y establezca los valores de ETCD_INITIAL_CLUSTER, ETCD_INITIAL_ADVERTISE_PEER_URLS, ETCD_ADVERTISE_CLIENT_URLS, ETCD_LISTEN_CLIENT_URLS en la dirección IP de management del controller node (head node) para permitir el acceso de otros nodos a través de la red de administración

```bash
echo 'ETCD_NAME="controller"' >> /etc/default/etcd
echo 'ETCD_DATA_DIR="/var/lib/etcd"' >> /etc/default/etcd
echo 'ETCD_INITIAL_CLUSTER_STATE="new"' >> /etc/default/etcd
echo 'ETCD_INITIAL_CLUSTER_TOKEN="etcd-cluster-01"' \
>> /etc/default/etcd
echo 'ETCD_INITIAL_CLUSTER="controller=http://192.168.202.1:2380"' \
>> /etc/default/etcd
echo 'ETCD_INITIAL_ADVERTISE_PEER_URLS="http://192.168.202.1:2380"' \
>> /etc/default/etcd
echo 'ETCD_ADVERTISE_CLIENT_URLS="http://192.168.202.1:2379"' \
>> /etc/default/etcd
echo 'ETCD_LISTEN_PEER_URLS="http://0.0.0.0:2380"' \
>> /etc/default/etcd
echo 'ETCD_LISTEN_CLIENT_URLS="http://192.168.202.1:2379"' \
>> /etc/default/etcd
```

Habilite y reinicie el servicio etcd

```bash
systemctl enable etcd
systemctl restart etcd
```

<!-- Fuente: página 13 del PDF original -->

### ACTIVIDAD N° 9: Keystone - Identidad

#### Head Node

Cargue el fichero service_passwords

```bash
. /root/service_passwords
```

Crear la base de datos 'keystone'

```bash
mysql -e "CREATE DATABASE keystone;"
```

Configurar acceso a la base de datos 'keystone'

```bash
mysql -e "GRANT ALL PRIVILEGES ON keystone.* TO \
'keystone'@'localhost' IDENTIFIED BY '$KEYSTONE_DBPASS';"
mysql -e "GRANT ALL PRIVILEGES ON keystone.* TO 'keystone'@'%' \
IDENTIFIED BY '$KEYSTONE_DBPASS';"
```

Instale los paquetes

```bash
apt install keystone -y
```

Edite el fichero /etc/keystone/keystone.conf: En la sección [database] configure el acceso a la base de datos

```bash
crudini --set /etc/keystone/keystone.conf database connection \
mysql+pymysql://keystone:$KEYSTONE_DBPASS@controller/keystone
```

En la sección [token], configure el proveedor de token 'fernet'

```bash
crudini --set /etc/keystone/keystone.conf token provider fernet
```

<!-- Fuente: página 14 del PDF original -->

Complete la base de datos de Keystone

```bash
su -s /bin/sh -c "keystone-manage db_sync" keystone
```

Inicialice los repositorios de claves de Fernet

```bash
keystone-manage fernet_setup --keystone-user keystone \
--keystone-group keystone
keystone-manage credential_setup --keystone-user keystone \
--keystone-group keystone
```

Arranque Keystone

```bash
keystone-manage bootstrap --bootstrap-password $ADMIN_PASS \
--bootstrap-admin-url http://controller:5000/v3/ \
--bootstrap-internal-url http://controller:5000/v3/ \
--bootstrap-public-url http://controller:5000/v3/ \
--bootstrap-region-id RegionOne
```

Edite el fichero /etc/apache2/apache2.conf y configure la opción ServerName para hacer referencia al controller node (head node)

```bash
echo 'ServerName controller' >> /etc/apache2/apache2.conf
```

Reinicie el servicio Apache

```bash
systemctl restart apache2
```

Cree el directorio /root/env-scripts/

```bash
mkdir ~/env-scripts
```

En la carpeta que acaba de crear, cree y edite el fichero admin-openrc con las variables de entorno necesarias para administrar OpenStack

<!-- Fuente: página 15 del PDF original -->

```bash
echo 'export OS_USERNAME=admin' > ~/env-scripts/admin-openrc
echo "export OS_PASSWORD=$ADMIN_PASS" \
>> ~/env-scripts/admin-openrc
echo 'export OS_PROJECT_NAME=admin' >> ~/env-scripts/admin-openrc
echo 'export OS_USER_DOMAIN_NAME=Default' \
>> ~/env-scripts/admin-openrc
echo 'export OS_PROJECT_DOMAIN_NAME=Default' \
>> ~/env-scripts/admin-openrc
echo 'export OS_AUTH_URL=http://controller:5000/v3' \
>> ~/env-scripts/admin-openrc
echo 'export OS_IDENTITY_API_VERSION=3' \
>> ~/env-scripts/admin-openrc
echo 'export OS_IMAGE_API_VERSION=2' >> ~/env-scripts/admin-openrc
```

#### Verificar operación

Cargue el fichero con las credenciales de admin para el cliente de OpenStack

```bash
. ~/env-scripts/admin-openrc
```

Liste los usuarios creados

```bash
openstack user list
```

> **Indicación de evidencia:** Complete el Paso 1 - Actividad 1 del TEL141_LAB5_EL_Template.

Liste los proyectos creados

```bash
openstack project list
```

> **Indicación de evidencia:** Complete el Paso 2 - Actividad 1 del TEL141_LAB5_EL_Template.

Liste los dominios creados

```bash
openstack domain list
```

> **Indicación de evidencia:** Complete el Paso 3 - Actividad 1 del TEL141_LAB5_EL_Template.

<!-- Fuente: página 16 del PDF original -->

### ACTIVIDAD N° 10: Glance - Imágen

#### Head Node

Cargue el fichero service_passwords

```bash
. /root/service_passwords
```

Crear la base de datos 'glance'

```bash
mysql -e "CREATE DATABASE glance;"
```

Configurar acceso a la base de datos 'glance'

```bash
mysql -e "GRANT ALL PRIVILEGES ON glance.* TO \
'glance'@'localhost' IDENTIFIED BY '$GLANCE_DBPASS';"
mysql -e "GRANT ALL PRIVILEGES ON glance.* TO \
'glance'@'%' IDENTIFIED BY '$GLANCE_DBPASS';"
```

Cargue el fichero con las credenciales de admin para el cliente de OpenStack

```bash
. ~/env-scripts/admin-openrc
```

Cree el usuario 'glance'

```bash
openstack user create --domain default \
--password $GLANCE_PASS glance
```

Cree el proyecto 'service'

```bash
openstack project create --domain default \
--description "Service Project" service
```

Agregue el rol 'admin' al usuario 'glance' en el proyecto 'service'

```bash
openstack role add --project service --user glance admin
```

<!-- Fuente: página 17 del PDF original -->

Crear el servicio de imágenes 'glance'

```bash
openstack service create --name glance \
--description "OpenStack Image" image
```

Crear los endpoints de la API del servicio de imágenes

```bash
openstack endpoint create --region RegionOne \
image public http://controller:9292
openstack endpoint create --region RegionOne \
image internal http://controller:9292
openstack endpoint create --region RegionOne \
image admin http://controller:9292
```

Instale los paquetes

```bash
apt install glance -y
```

Edite el fichero /etc/glance/glance-api.conf: En la sección [database] configurar el acceso a la base de datos

```bash
crudini --set /etc/glance/glance-api.conf database connection \
mysql+pymysql://glance:$GLANCE_DBPASS@controller/glance
```

En las secciones [keystone_authtoken] y [paste_deploy], configure el acceso al servicio de identidad

```bash
crudini --set /etc/glance/glance-api.conf keystone_authtoken \
www_authenticate_uri http://controller:5000
crudini --set /etc/glance/glance-api.conf keystone_authtoken \
auth_url http://controller:5000
crudini --set /etc/glance/glance-api.conf keystone_authtoken \
memcached_servers controller:11211
crudini --set /etc/glance/glance-api.conf keystone_authtoken \
auth_type password
crudini --set /etc/glance/glance-api.conf keystone_authtoken \
project_domain_name Default
crudini --set /etc/glance/glance-api.conf keystone_authtoken \
user_domain_name Default
```

<!-- Fuente: página 18 del PDF original -->

```bash
crudini --set /etc/glance/glance-api.conf keystone_authtoken \
project_name service
crudini --set /etc/glance/glance-api.conf keystone_authtoken \
username glance
crudini --set /etc/glance/glance-api.conf keystone_authtoken \
password $GLANCE_PASS
crudini --set /etc/glance/glance-api.conf paste_deploy flavor \
keystone
```

En la sección [glance_store], configure el local file system store y la ubicación de los archivos de imagen

```bash
crudini --set /etc/glance/glance-api.conf glance_store stores \
file,http
crudini --set /etc/glance/glance-api.conf glance_store \
default_store file
crudini --set /etc/glance/glance-api.conf glance_store \
filesystem_store_datadir /var/lib/glance/images/
```

Complete la base de datos del servicio de glance

```bash
su -s /bin/sh -c "glance-manage db_sync" glance
```

Reinicie los servicios de imagen

```bash
service glance-api restart
```

#### Verificar operación

Descargue cirros

```bash
wget \
http://download.cirros-cloud.net/0.4.0/cirros-0.4.0-x86_64-disk.img
```

<!-- Fuente: página 19 del PDF original -->

Cargue la imagen al servicio de imágenes utilizando el formato de disco QCOW2 , el formato de contenedor simple y la visibilidad pública para que todos los proyectos puedan acceder a ella

```bash
glance image-create --name "cirros" \
--file ~/cirros-0.4.0-x86_64-disk.img \
--disk-format qcow2 --container-format bare \
--visibility=public
```

Liste las imágenes

```bash
openstack image list
```

> **Indicación de evidencia:** Complete el Paso 1 - Actividad 2 del TEL141_LAB5_EL_Template.

### ACTIVIDAD N° 11: Placement - Colocación

#### Head Node

Cargue el fichero service_passwords

```bash
. /root/service_passwords
```

Crear la base de datos 'placement'

```bash
mysql -e "CREATE DATABASE placement;"
```

Configurar acceso a la base de datos 'placement'

```bash
mysql -e "GRANT ALL PRIVILEGES ON placement.* TO \
'placement'@'localhost' IDENTIFIED BY '$PLACEMENT_DBPASS';"
mysql -e "GRANT ALL PRIVILEGES ON placement.* TO \
'placement'@'%' IDENTIFIED BY '$PLACEMENT_DBPASS';"
```

Cargue el fichero con las credenciales de admin para el cliente de OpenStack

```bash
. ~/env-scripts/admin-openrc
```

<!-- Fuente: página 20 del PDF original -->

Cree el usuario 'placement'

```bash
openstack user create --domain default \
--password $PLACEMENT_PASS placement
```

Agregue el rol 'admin' al usuario 'placement' en el proyecto 'service'

```bash
openstack role add --project service --user placement admin
```

Crear el servicio de colocación 'placement'

```bash
openstack service create --name placement \
--description "Placement API" placement
```

Crear los endpoints de la API del servicio de colocación

```bash
openstack endpoint create --region RegionOne \
placement public http://controller:8778
openstack endpoint create --region RegionOne \
placement internal http://controller:8778
```

```bash
openstack endpoint create --region RegionOne \
placement admin http://controller:8778
```

Instale los paquetes

```bash
apt install placement-api -y
```

Edite el fichero /etc/placement/placement.conf: En la sección [placement_database] configurar el acceso a la base de datos

```bash
crudini --set /etc/placement/placement.conf placement_database \
connection mysql+pymysql://placement:$PLACEMENT_DBPASS@controller/placement
```

<!-- Fuente: página 21 del PDF original -->

En las secciones [api] y [keystone_authtoken], configure el acceso al servicio de identidad

```bash
crudini --set /etc/placement/placement.conf api auth_strategy \
keystone
crudini --set /etc/placement/placement.conf keystone_authtoken \
auth_url http://controller:5000/v3
crudini --set /etc/placement/placement.conf keystone_authtoken \
memcached_servers controller:11211
crudini --set /etc/placement/placement.conf keystone_authtoken \
auth_type password
```

```bash
crudini --set /etc/placement/placement.conf keystone_authtoken \
project_domain_name Default
crudini --set /etc/placement/placement.conf keystone_authtoken \
user_domain_name Default
crudini --set /etc/placement/placement.conf keystone_authtoken \
project_name service
crudini --set /etc/placement/placement.conf keystone_authtoken \
username placement
crudini --set /etc/placement/placement.conf keystone_authtoken \
password $PLACEMENT_PASS
```

Complete la base de datos del servicio de placement

```bash
su -s /bin/sh -c "placement-manage db sync" placement
```

Vuelva a cargar el servidor web para agregar los nuevos ajustes de configuración para placement

```bash
service apache2 restart
```

#### Verificar operación

Muestre el estado de placement

```bash
placement-status upgrade check
```

<!-- Fuente: página 22 del PDF original -->

**PREGUNTA 5: PLACEMENT STATUS**

[INSERTE EL OUTPUT DEL COMANDO ANTERIOR]

Instale pip3

```bash
apt install python3-pip -y
```

Instale el pugin osc-placement

```bash
pip3 install osc-placement
```

Liste las clases de recursos disponibles

```bash
openstack --os-placement-api-version 1.2 resource class list \
--sort-column name
```

> **Indicación de evidencia:** Complete el Paso 1 - Actividad 3 del TEL141_LAB5_EL_Template.

Liste los traits disponibles

```bash
openstack --os-placement-api-version 1.6 trait list \
--sort-column name
```

> **Indicación de evidencia:** Complete el Paso 2 - Actividad 3 del TEL141_LAB5_EL_Template.

### ACTIVIDAD N° 12: Nova - Cómputo

#### Head Node

Cargue el fichero service_passwords

```bash
. /root/service_passwords
```

<!-- Fuente: página 23 del PDF original -->

Crear las bases de datos 'nova_api', 'nova' y 'nova_cell0'

```bash
mysql -e "CREATE DATABASE nova_api;"
mysql -e "CREATE DATABASE nova;"
mysql -e "CREATE DATABASE nova_cell0;"
```

Configurar acceso a las bases de datos creadas

```bash
mysql -e "GRANT ALL PRIVILEGES ON nova_api.* TO \
'nova'@'localhost' IDENTIFIED BY '$NOVA_DBPASS';"
mysql -e "GRANT ALL PRIVILEGES ON nova_api.* TO \
'nova'@'%' IDENTIFIED BY '$NOVA_DBPASS';"
mysql -e "GRANT ALL PRIVILEGES ON nova.* TO \
'nova'@'localhost' IDENTIFIED BY '$NOVA_DBPASS';"
mysql -e "GRANT ALL PRIVILEGES ON nova.* TO \
'nova'@'%' IDENTIFIED BY '$NOVA_DBPASS';"
mysql -e "GRANT ALL PRIVILEGES ON nova_cell0.* TO \
'nova'@'localhost' IDENTIFIED BY '$NOVA_DBPASS';"
mysql -e "GRANT ALL PRIVILEGES ON nova_cell0.* TO \
'nova'@'%' IDENTIFIED BY '$NOVA_DBPASS';"
```

Cargue el fichero con las credenciales de admin para el cliente de OpenStack

```bash
. ~/env-scripts/admin-openrc
```

Cree el usuario 'nova'

```bash
openstack user create --domain default --password $NOVA_PASS nova
```

Agregue el rol 'admin' al usuario 'nova' en el proyecto 'service'

```bash
openstack role add --project service --user nova admin
```

Crear el servicio de computo 'nova'

```bash
openstack service create --name nova \
--description "OpenStack Compute" compute
```

<!-- Fuente: página 24 del PDF original -->

Crear los endpoints de la API del servicio de computo

```bash
openstack endpoint create --region RegionOne \
compute public http://controller:8774/v2.1
openstack endpoint create --region RegionOne \
compute internal http://controller:8774/v2.1
openstack endpoint create --region RegionOne \
compute admin http://controller:8774/v2.1
```

Instale los paquetes

```bash
apt install nova-api nova-conductor nova-novncproxy \
nova-scheduler -y
```

Edite el fichero /etc/nova/nova.conf: En las secciones [api_database]y [database], configure el acceso a la base de datos

```bash
crudini --set /etc/nova/nova.conf api_database connection \
mysql+pymysql://nova:$NOVA_DBPASS@controller/nova_api
crudini --set /etc/nova/nova.conf database connection \
mysql+pymysql://nova:$NOVA_DBPASS@controller/nova
```

En la sección [DEFAULT], configure el acceso a la cola de mensajes RabbitMQ

```bash
crudini --set /etc/nova/nova.conf DEFAULT \
transport_url rabbit://openstack:$RABBIT_PASS@controller:5672/
```

En las secciones [api] y [keystone_authtoken], configure el acceso al servicio de identidad

```bash
crudini --set /etc/nova/nova.conf \
api auth_strategy keystone
crudini --set /etc/nova/nova.conf \
keystone_authtoken www_authenticate_uri http://controller:5000/
crudini --set /etc/nova/nova.conf \
keystone_authtoken auth_url http://controller:5000/
crudini --set /etc/nova/nova.conf \
keystone_authtoken memcached_servers controller:11211
crudini --set /etc/nova/nova.conf \
keystone_authtoken auth_type password
```

<!-- Fuente: página 25 del PDF original -->

```bash
crudini --set /etc/nova/nova.conf \
keystone_authtoken project_domain_name Default
crudini --set /etc/nova/nova.conf \
keystone_authtoken user_domain_name Default
crudini --set /etc/nova/nova.conf \
keystone_authtoken project_name service
crudini --set /etc/nova/nova.conf \
keystone_authtoken username nova
crudini --set /etc/nova/nova.conf \
keystone_authtoken password $NOVA_PASS
```

En la sección [DEFAULT], configure la opción my_ip para usar la dirección IP de la interfaz de management del controller node (head node)

```bash
iface=ens3
mgmt_ip=$(ip addr show ${iface} | grep \
"inet " | awk '{print $2}' | cut -d "/" -f 1)
crudini --set /etc/nova/nova.conf DEFAULT \
my_ip ${mgmt_ip}
```

En este punto se debería configurar la sección [neutron], pero se dejará para más adelante (cuando configure el servicio Neutron en el controller node (head node)).

En la sección [vnc], configure el proxy VNC para usar la dirección IP de management del controller node (head node)

```bash
crudini --set /etc/nova/nova.conf vnc \
enabled true
crudini --set /etc/nova/nova.conf vnc \
server_listen \$my_ip
crudini --set /etc/nova/nova.conf vnc \
server_proxyclient_address \$my_ip
```

En la sección [glance], configure la ubicación de la API del servicio de imágenes

```bash
crudini --set /etc/nova/nova.conf glance \
api_servers http://controller:9292
```

<!-- Fuente: página 26 del PDF original -->

En la sección [oslo_concurrency], configure la ruta de bloqueo

```bash
crudini --set /etc/nova/nova.conf oslo_concurrency \
lock_path /var/lib/nova/tmp
```

Debido a un error de packing, elimine la opción log_dir de la sección [DEFAULT]

```bash
sed -i '/^log_dir = \/var\/log\/nova/s/^/# /' /etc/nova/nova.conf
```

En la sección [placement] configurar el acceso al servicio Placement

```bash
crudini --set /etc/nova/nova.conf placement \
region_name RegionOne
crudini --set /etc/nova/nova.conf placement \
project_domain_name Default
crudini --set /etc/nova/nova.conf placement \
project_name service
crudini --set /etc/nova/nova.conf placement \
auth_type password
```

```bash
crudini --set /etc/nova/nova.conf placement \
user_domain_name Default
crudini --set /etc/nova/nova.conf placement \
auth_url http://controller:5000/v3
crudini --set /etc/nova/nova.conf placement \
username placement
crudini --set /etc/nova/nova.conf placement \
password $PLACEMENT_PASS
```

Complete la base de datos nova-api

```bash
su -s /bin/sh -c "nova-manage api_db sync" nova
```

Registre la base de datos cell0

```bash
su -s /bin/sh -c "nova-manage cell_v2 map_cell0" nova
```

<!-- Fuente: página 27 del PDF original -->

Crea la celda cell1

```bash
su -s /bin/sh -c "nova-manage cell_v2 create_cell \
--name=cell1 --verbose" nova
```

Complete la base de datos nova

```bash
su -s /bin/sh -c "nova-manage db sync" nova
```

Verifique que nova cell0 y cell1 estén registrados correctamente

```bash
su -s /bin/sh -c "nova-manage cell_v2 list_cells" nova
```

Reinicie los servicios de Cómputo

```bash
service nova-api restart
service nova-scheduler restart
service nova-conductor restart
service nova-novncproxy restart
```

#### Worker Nodes

Instale los paquetes

```bash
apt install nova-compute -y
```

Cargue el fichero service_passwords

```bash
. /root/service_passwords
```

Edite el fichero /etc/nova/nova.conf: En la sección [DEFAULT], configure el acceso a la cola de mensajes RabbitMQ

```bash
crudini --set /etc/nova/nova.conf DEFAULT \
transport_url rabbit://openstack:$RABBIT_PASS@controller
```

<!-- Fuente: página 28 del PDF original -->

En las secciones [api] y [keystone_authtoken], configure el acceso al servicio de identidad

```bash
crudini --set /etc/nova/nova.conf \
api auth_strategy keystone
crudini --set /etc/nova/nova.conf \
keystone_authtoken www_authenticate_uri http://controller:5000/
crudini --set /etc/nova/nova.conf \
keystone_authtoken auth_url http://controller:5000/
crudini --set /etc/nova/nova.conf \
keystone_authtoken memcached_servers controller:11211
crudini --set /etc/nova/nova.conf \
keystone_authtoken auth_type password
crudini --set /etc/nova/nova.conf \
keystone_authtoken project_domain_name Default
crudini --set /etc/nova/nova.conf \
keystone_authtoken user_domain_name Default
crudini --set /etc/nova/nova.conf \
keystone_authtoken project_name service
crudini --set /etc/nova/nova.conf \
keystone_authtoken username nova
crudini --set /etc/nova/nova.conf \
keystone_authtoken password $NOVA_PASS
```

En la sección [DEFAULT], configure la opción my_ip para usar la dirección IP de la interfaz de management del compute node según corresponda

```bash
iface=ens3
mgmt_ip=$(ip addr show ${iface} | grep \
"inet " | awk '{print $2}' | cut -d "/" -f 1)
crudini --set /etc/nova/nova.conf DEFAULT my_ip ${mgmt_ip}
```

En este punto se debería configurar la sección [neutron], pero se dejará para más adelante (cuando configure el servicio Neutron en el compute node).

En la sección [vnc], configure el proxy VNC para usar la dirección IP de management del controller node (head node)

```bash
crudini --set /etc/nova/nova.conf vnc enabled true
crudini --set /etc/nova/nova.conf vnc server_listen 0.0.0.0
crudini --set /etc/nova/nova.conf vnc \
server_proxyclient_address \$my_ip
```

<!-- Fuente: página 29 del PDF original -->

```bash
crudini --set /etc/nova/nova.conf vnc \
novncproxy_base_url http://controller:6080/vnc_auto.html
```

En la sección [glance], configure la ubicación de la API del servicio de imágenes

```bash
crudini --set /etc/nova/nova.conf glance \
api_servers http://controller:9292
```

En la sección [oslo_concurrency], configure la ruta de bloqueo

```bash
crudini --set /etc/nova/nova.conf oslo_concurrency \
lock_path /var/lib/nova/tmp
```

En la sección [placement] configurar el acceso al servicio Placement

```bash
crudini --set /etc/nova/nova.conf placement region_name RegionOne
crudini --set /etc/nova/nova.conf placement \
project_domain_name Default
crudini --set /etc/nova/nova.conf placement project_name service
crudini --set /etc/nova/nova.conf placement auth_type password
crudini --set /etc/nova/nova.conf placement \
user_domain_name Default
crudini --set /etc/nova/nova.conf placement \
auth_url http://controller:5000/v3
crudini --set /etc/nova/nova.conf placement username placement
crudini --set /etc/nova/nova.conf placement \
password $PLACEMENT_PASS
```

Reinicie el servicio Cómputo

```bash
service nova-compute restart
```

#### Head Node

Confirme que hay hosts informáticos en la base de datos

```bash
openstack compute service list --service nova-compute
```

<!-- Fuente: página 30 del PDF original -->

Encuentre los nodos de cómputo

```bash
su -s /bin/sh -c "nova-manage cell_v2 \
discover_hosts --verbose" nova
```

#### Verificar operación

Liste los componentes del servicio para verificar el inicio y registro exitosos de cada proceso

```bash
openstack compute service list
```

> **Indicación de evidencia:** Complete el Paso 1 - Actividad 4 del TEL141_LAB5_EL_Template.

### ACTIVIDAD N° 13: Neutron - Redes

#### Head Node

Cargue el fichero service_passwords

```bash
. /root/service_passwords
```

Crear la base de datos 'neutron'

```bash
mysql -e "CREATE DATABASE neutron;"
```

Configurar acceso a la base de datos 'neutron'

```bash
mysql -e "GRANT ALL PRIVILEGES ON neutron.* TO \
'neutron'@'localhost' IDENTIFIED BY '$NEUTRON_DBPASS';"
mysql -e "GRANT ALL PRIVILEGES ON neutron.* TO \
'neutron'@'%' IDENTIFIED BY '$NEUTRON_DBPASS';"
```

Cargue el fichero con las credenciales de admin para el cliente de OpenStack

```bash
. ~/env-scripts/admin-openrc
```

<!-- Fuente: página 31 del PDF original -->

Cree el usuario 'neutron'

```bash
openstack user create --domain default \
--password $NEUTRON_PASS neutron
```

Agregue el rol 'admin' al usuario 'neutron' en el proyecto 'service'

```bash
openstack role add --project service --user neutron admin
```

Crear el servicio de red 'neutron'

```bash
openstack service create --name neutron \
--description "OpenStack Networking" network
```

Crear los endpoints de la API del servicio de red

```bash
openstack endpoint create --region RegionOne \
network public http://controller:9696
openstack endpoint create --region RegionOne \
network internal http://controller:9696
openstack endpoint create --region RegionOne \
network admin http://controller:9696
```

Instalar los componentes

```bash
apt install neutron-server neutron-plugin-ml2 \
neutron-l3-agent neutron-dhcp-agent neutron-metadata-agent \
neutron-openvswitch-agent -y
```

Edite el fichero /etc/neutron/neutron.conf

```bash
crudini --set /etc/neutron/neutron.conf database \
connection mysql+pymysql://neutron:$NEUTRON_DBPASS@controller/neutron
```

```bash
crudini --set /etc/neutron/neutron.conf DEFAULT \
transport_url rabbit://openstack:$RABBIT_PASS@controller
crudini --set /etc/neutron/neutron.conf DEFAULT \
core_plugin ml2
```

<!-- Fuente: página 32 del PDF original -->

```bash
crudini --set /etc/neutron/neutron.conf DEFAULT \
service_plugins router
crudini --set /etc/neutron/neutron.conf DEFAULT \
allow_overlapping_ips true
crudini --set /etc/neutron/neutron.conf DEFAULT \
auth_strategy keystone
crudini --set /etc/neutron/neutron.conf keystone_authtoken \
www_authenticate_uri http://controller:5000
crudini --set /etc/neutron/neutron.conf keystone_authtoken \
auth_url http://controller:5000
crudini --set /etc/neutron/neutron.conf keystone_authtoken \
memcached_servers controller:11211
crudini --set /etc/neutron/neutron.conf keystone_authtoken \
auth_type password
crudini --set /etc/neutron/neutron.conf keystone_authtoken \
project_domain_name default
crudini --set /etc/neutron/neutron.conf keystone_authtoken \
user_domain_name default
crudini --set /etc/neutron/neutron.conf keystone_authtoken \
project_name service
crudini --set /etc/neutron/neutron.conf keystone_authtoken \
username neutron
crudini --set /etc/neutron/neutron.conf keystone_authtoken \
password $NEUTRON_PASS
crudini --set /etc/neutron/neutron.conf DEFAULT \
notify_nova_on_port_status_changes true
crudini --set /etc/neutron/neutron.conf DEFAULT \
notify_nova_on_port_data_changes true
crudini --set /etc/neutron/neutron.conf nova \
auth_url http://controller:5000
crudini --set /etc/neutron/neutron.conf nova \
auth_type password
crudini --set /etc/neutron/neutron.conf nova \
project_domain_name default
crudini --set /etc/neutron/neutron.conf nova \
user_domain_name default
crudini --set /etc/neutron/neutron.conf nova \
region_name RegionOne
crudini --set /etc/neutron/neutron.conf nova \
project_name service
crudini --set /etc/neutron/neutron.conf nova \
username nova
```

<!-- Fuente: página 33 del PDF original -->

```bash
crudini --set /etc/neutron/neutron.conf nova \
password $NOVA_PASS
crudini --set /etc/neutron/neutron.conf oslo_concurrency \
lock_path /var/lib/neutron/tmp
```

Edite el fichero /etc/neutron/plugins/ml2/ml2_conf.ini

```bash
crudini --set /etc/neutron/plugins/ml2/ml2_conf.ini \
ml2 type_drivers flat,vlan
crudini --set /etc/neutron/plugins/ml2/ml2_conf.ini \
ml2 mechanism_drivers openvswitch
crudini --set /etc/neutron/plugins/ml2/ml2_conf.ini \
ml2 tenant_network_types vlan
crudini --set /etc/neutron/plugins/ml2/ml2_conf.ini \
ml2_type_flat flat_networks physnet0
crudini --set /etc/neutron/plugins/ml2/ml2_conf.ini \
ml2_type_vlan network_vlan_ranges physnet1:11:900
crudini --set /etc/neutron/plugins/ml2/ml2_conf.ini \
ml2 extension_drivers port_security
crudini --set /etc/neutron/plugins/ml2/ml2_conf.ini \
securitygroup enable_ipset true
```

Configure el ML2 openvswitch mechanism driver

```bash
ovs-vsctl add-br br-provider
ovs-vsctl add-br br-vlan
ovs-vsctl add-port br-vlan ens4
crudini --set /etc/neutron/plugins/ml2/openvswitch_agent.ini \
ovs bridge_mappings physnet0:br-provider,physnet1:br-vlan
```

Habilite security groups

```bash
crudini --set /etc/neutron/plugins/ml2/openvswitch_agent.ini \
securitygroup enable_security_group true
```

Configure el firewall driver

```bash
crudini --set /etc/neutron/plugins/ml2/openvswitch_agent.ini \
securitygroup firewall_driver openvswitch
```

<!-- Fuente: página 34 del PDF original -->

Configure el Layer-3 Agent

```bash
crudini --set /etc/neutron/l3_agent.ini DEFAULT \
interface_driver openvswitch
```

Configure el DHCP Agent

```bash
crudini --set /etc/neutron/dhcp_agent.ini DEFAULT \
interface_driver openvswitch
crudini --set /etc/neutron/dhcp_agent.ini DEFAULT \
dhcp_driver neutron.agent.linux.dhcp.Dnsmasq
crudini --set /etc/neutron/dhcp_agent.ini DEFAULT \
enable_isolated_metadata true
```

Configure el Metadata Agent

```bash
crudini --set /etc/neutron/metadata_agent.ini DEFAULT \
nova_metadata_host controller
crudini --set /etc/neutron/metadata_agent.ini DEFAULT \
metadata_proxy_shared_secret $METADATA_SECRET
```

Edite el fichero /etc/nova/nova.conf

```bash
crudini --set /etc/nova/nova.conf neutron \
auth_url http://controller:5000
crudini --set /etc/nova/nova.conf neutron \
auth_type password
crudini --set /etc/nova/nova.conf neutron \
project_domain_name default
crudini --set /etc/nova/nova.conf neutron \
user_domain_name default
crudini --set /etc/nova/nova.conf neutron \
region_name RegionOne
crudini --set /etc/nova/nova.conf neutron \
project_name service
crudini --set /etc/nova/nova.conf neutron \
username neutron
crudini --set /etc/nova/nova.conf neutron \
password $NEUTRON_PASS
```

<!-- Fuente: página 35 del PDF original -->

```bash
crudini --set /etc/nova/nova.conf neutron \
service_metadata_proxy true
crudini --set /etc/nova/nova.conf neutron \
metadata_proxy_shared_secret $METADATA_SECRET
```

Complete la base de datos neutron

```bash
su -s /bin/sh -c "neutron-db-manage --config-file \
/etc/neutron/neutron.conf --config-file /etc/neutron/plugins/ml2/ml2_conf.ini \
upgrade head" neutron
```

Reinicie la api de nova

```bash
service nova-api restart
```

Reinicie los servicios de networking

```bash
service neutron-server restart
service neutron-dhcp-agent restart
service neutron-metadata-agent restart
service neutron-l3-agent restart
service neutron-openvswitch-agent restart
```

Valide el servicio de neutron

```bash
openstack network agent list
```

Cree una red provider

```bash
openstack network create  --share --external \
--provider-physical-network physnet0 \
--provider-network-type flat external
openstack subnet create --network external \
--allocation-pool start=172.20.15.2,end=172.20.15.254 \
--dns-nameserver 8.8.8.8 --gateway 172.20.15.1 \
--subnet-range 172.20.15.0/24 external_subnet
```

<!-- Fuente: página 36 del PDF original -->

#### Worker Nodes

Cargue el fichero service_passwords

```bash
. /root/service_passwords
```

Agregue el dns de Google al fichero /etc/resolv.conf

```bash
echo 'nameserver 8.8.8.8' >> /etc/resolv.conf
```

Instale los paquetes de neutron

```bash
apt install neutron-openvswitch-agent -y
```

Edite el fichero /etc/neutron/neutron.conf

```bash
crudini --set /etc/neutron/neutron.conf DEFAULT \
transport_url rabbit://openstack:$RABBIT_PASS@controller
crudini --set /etc/neutron/neutron.conf DEFAULT \
auth_strategy keystone
crudini --set /etc/neutron/neutron.conf keystone_authtoken \
www_authenticate_uri http://controller:5000
crudini --set /etc/neutron/neutron.conf keystone_authtoken \
auth_url http://controller:5000
crudini --set /etc/neutron/neutron.conf keystone_authtoken \
memcached_servers controller:11211
crudini --set /etc/neutron/neutron.conf keystone_authtoken \
auth_type password
crudini --set /etc/neutron/neutron.conf keystone_authtoken \
project_domain_name default
crudini --set /etc/neutron/neutron.conf keystone_authtoken \
user_domain_name default
crudini --set /etc/neutron/neutron.conf keystone_authtoken \
project_name service
crudini --set /etc/neutron/neutron.conf keystone_authtoken \
username neutron
crudini --set /etc/neutron/neutron.conf keystone_authtoken \
password $NEUTRON_PASS
crudini --set /etc/neutron/neutron.conf oslo_concurrency \
lock_path /var/lib/neutron/tmp
```

<!-- Fuente: página 37 del PDF original -->

Configure el ML2 openvswitch mechanism driver

```bash
ovs-vsctl add-br br-vlan
ovs-vsctl add-port br-vlan ens4
crudini --set /etc/neutron/plugins/ml2/openvswitch_agent.ini \
ovs bridge_mappings physnet1:br-vlan
```

Habilite security groups

```bash
crudini --set /etc/neutron/plugins/ml2/openvswitch_agent.ini \
securitygroup enable_security_group true
```

Configure el firewall driver

```bash
crudini --set /etc/neutron/plugins/ml2/openvswitch_agent.ini \
securitygroup firewall_driver openvswitch
```

Configure el servicio de computo para usar neutron

```bash
crudini --set /etc/nova/nova.conf neutron auth_url \
http://controller:5000
crudini --set /etc/nova/nova.conf neutron auth_type password
crudini --set /etc/nova/nova.conf neutron project_domain_name \
default
crudini --set /etc/nova/nova.conf neutron user_domain_name default
crudini --set /etc/nova/nova.conf neutron region_name RegionOne
crudini --set /etc/nova/nova.conf neutron project_name service
crudini --set /etc/nova/nova.conf neutron username neutron
crudini --set /etc/nova/nova.conf neutron password $NEUTRON_PASS
```

Reinicie los servicios

```bash
service nova-compute restart
service neutron-openvswitch-agent restart
```

<!-- Fuente: página 38 del PDF original -->

#### Head Node

Liste los agentes de networking

```bash
openstack network agent list
```

> **Indicación de evidencia:** Complete el Paso 1 - Actividad 5 del TEL141_LAB5_EL_Template.

### ACTIVIDAD N° 14: Horizon - Dashboard

#### Head Node

Agregue el dns de Google al fichero /etc/resolv.conf

```bash
echo 'nameserver 8.8.8.8' >> /etc/resolv.conf
```

Instale los paquetes

```bash
apt install openstack-dashboard -y
```

Edite el fichero /etc/openstack-dashboard/local_settings.py: Configure el dashboard para usar los servicios de OpenStack en el controller node (head node)

```bash
sed -i 's/^OPENSTACK_HOST = "127\.0\.0\.1"/\
OPENSTACK_HOST = "controller"/' \
/etc/openstack-dashboard/local_settings.py
```

Configure el servicio memcached

```bash
echo "SESSION_ENGINE = 'django.contrib.sessions.backends.cache'" \
>> /etc/openstack-dashboard/local_settings.py
sed -i 's/127.0.0.1:11211/controller:11211/g' \
/etc/openstack-dashboard/local_settings.py
```

<!-- Fuente: página 39 del PDF original -->

Habilite la API de identidad versión 3

```bash
sed -i 's|http://%s/identity/v3|http://%s:5000/v3|' \
/etc/openstack-dashboard/local_settings.py
```

Habilite el soporte multidominios

```bash
echo "OPENSTACK_KEYSTONE_MULTIDOMAIN_SUPPORT = True" >> \
/etc/openstack-dashboard/local_settings.py
```

Configurar versiones de API

```bash
echo 'OPENSTACK_API_VERSIONS = {"identity": 3, "image": 2, \
"volume": 3,}' >> /etc/openstack-dashboard/local_settings.py
```

Configure Default como dominio predeterminado para los usuarios que cree a través del dashboard

```bash
echo 'OPENSTACK_KEYSTONE_DEFAULT_DOMAIN = "Default"' >> \
/etc/openstack-dashboard/local_settings.py
```

Configure member como rol predeterminado para los usuarios que cree a través del panel:

```bash
echo 'OPENSTACK_KEYSTONE_DEFAULT_ROLE = "member"' >> \
/etc/openstack-dashboard/local_settings.py
```

Configure la zona horaria

```bash
sed -i 's/TIME_ZONE = "UTC"/TIME_ZONE = "America\/Lima"/' \
/etc/openstack-dashboard/local_settings.py
```

Vuelva a cargar la configuración del servidor web

```bash
systemctl reload apache2.service
```

<!-- Fuente: página 40 del PDF original -->

#### Local Host

Ejecute un túnel ssh para acceder al puerto 80 del Head Node apuntando al puerto 50080 del Local Host

```bash
ssh -NL 50080:127.0.0.1:80 ubuntu@10.20.12.X -p 5821
```

Desde su local host, abra un navegador web y acceda al dashboard usando el siguiente enlace: http://localhost:50080/horizon

> **Indicación de evidencia:** Complete el Paso 1 - Actividad 6 del TEL141_LAB5_EL_Template.

---

## Reporte final: topología P2P

<!-- Fuente: páginas 41 a 46 -->

### Indicaciones generales del reporte final

- Puntaje total: **6 puntos**.
- Entrega **grupal** sobre `TEL141_Lab5_RF_Template.docx`, publicado en PAIDEIA.
- Guardar el reporte en PDF con el nombre `TEL141_LAB5_RF_GXXX.pdf`.
- Entregar mediante PAIDEIA **como máximo dos días después** de finalizar la sesión síncrona.
- La guía no acepta entregas posteriores al plazo ni por otro medio.

### Actividad previa — túneles SSH (Local Host)

| Puerto Local Host | Puerto Head Node | Servicio contextual |
|---:|---:|---|
| 55000 | 5000 | Keystone |
| 58774 | 8774 | Nova |
| 56080 | 6080 | Consola noVNC |
| 50080 | 80 | Dashboard Horizon |

**Comandos de la guía:**

```bash
ssh -NL 55000:127.0.0.1:5000 ubuntu@10.20.12.X -p 5821
ssh -NL 58774:127.0.0.1:8774 ubuntu@10.20.12.X -p 5821
ssh -NL 56080:127.0.0.1:6080 ubuntu@10.20.12.X -p 5821
ssh -NL 50080:127.0.0.1:80 ubuntu@10.20.12.X -p 5821
```

### Preparación de OpenStack: dominio y usuario Cloud (Head Node)

<!-- Fuente: página 42 del PDF original -->

```bash
ssh -NL 58774:127.0.0.1:8774 ubuntu@10.20.12.X -p 5821
```

```bash
ssh -NL 56080:127.0.0.1:6080 ubuntu@10.20.12.X -p 5821
```

```bash
ssh -NL 50080:127.0.0.1:80 ubuntu@10.20.12.X -p 5821
```

#### Head Node

Cargue el fichero con las credenciales de admin para el cliente de OpenStack

```bash
. ~/env-scripts/admin-openrc
```

Cree el flavor 512MBRAM_1VCPUs_4GBRoot

```bash
openstack flavor create --ram 512 --disk 4 --vcpus 1 \
512MBRAM_1VCPUs_4GBRoot
```

Cree un nuevo dominio, llámelo cloud

```bash
openstack domain create Cloud --description "Domain for TEL141"
```

En adelante, todas las acciones de OpenStack se ejecutarán sobre el dominio cloud.

Cree un nuevo proyecto, llámelo cloud_admin

```bash
openstack project create --domain Cloud --description "Admin \
project for Cloud domain" cloud_admin
```

<!-- Fuente: página 43 del PDF original -->

Genere un password para el usuario de OpenStack que está por crear.

```bash
CLOUD_ADMIN_PASS=$(openssl rand -hex 16)
```

Cree el usuario cloud_admin en OpenStack

```bash
openstack user create --domain cloud --project cloud_admin \
--password $CLOUD_ADMIN_PASS cloud_admin
```

Agregue el rol admin al usuario cloud_admin sobre el proyecto cloud_admin y el dominio Cloud

```bash
openstack role add admin --user cloud_admin --domain Cloud
openstack role add admin --user cloud_admin --project cloud_admin
```

Cree el fichero cloud-admin-openrc en el directorio ~/env-scripts/ con las variables de entorno

necesarias para administrar OpenStack con el usuario cloud_admin

```bash
echo 'export OS_USERNAME=cloud_admin' > \
~/env-scripts/cloud-admin-openrc
echo "export OS_PASSWORD=$CLOUD_ADMIN_PASS" \
>> ~/env-scripts/cloud-admin-openrc
echo 'export OS_PROJECT_NAME=cloud_admin' >> \
~/env-scripts/cloud-admin-openrc
echo 'export OS_USER_DOMAIN_NAME=Cloud' \
>> ~/env-scripts/cloud-admin-openrc
```

```bash
echo 'export OS_PROJECT_DOMAIN_NAME=Cloud' \
>> ~/env-scripts/cloud-admin-openrc
echo 'export OS_AUTH_URL=http://controller:5000/v3' \
>> ~/env-scripts/cloud-admin-openrc
echo 'export OS_IDENTITY_API_VERSION=3' \
>> ~/env-scripts/cloud-admin-openrc
echo 'export OS_IMAGE_API_VERSION=2' >> \
~/env-scripts/cloud-admin-openrc
```

### Actividad 1: topología P2P de dos nodos (5 puntos)

<!-- Fuente: página 44 -->

El objetivo indicado es crear mediante la CLI de OpenStack una red punto a punto que conecte dos instancias virtuales.

![Topología P2P de dos nodos](GUIA_LAB5_assets/topologia_p2p_dos_vms.png)

*Figura de la página 44. Las instancias aparecen con IPs 192.168.18.1/24 y 192.168.18.2/24.*

<!-- Fuente: página 44 del PDF original -->

**PASO 1:** Cree un nuevo proyecto con el nombre lab5 (en el dominio Cloud)

```bash
openstack project create lab5 --domain Cloud
```

**PASO 1.1:** Usando el output del Paso 1, defina la variable de entorno project_id con el ID del proyecto lab5.

```bash
project_id=<lab5_project_id>
```

**PASO 2:** Agregue el rol admin al usuario cloud_admin sobre el proyecto lab_5 que creó en el paso anterior.

```bash
openstack role add admin --project $project_id \
--user cloud_admin --user-domain Cloud
```

**PASO 3:** Cree una red con el nombre link_1. La red se debe crear sobre el proyecto lab_5. Además la red debe tener el port-security desactivado.

<!-- Fuente: página 45 del PDF original -->

```bash
openstack network create link_1 --project $project_id \
--disable-port-security
```

**PASO 3.1:** Usando el output del Paso 3, defina la variable de entorno network_id con el ID de la red link_1.

```bash
network_id=<link1_network_id>
```

**PASO 4:** Cree una subred con el nombre subnet_link_1. La subred se debe crear sobre el proyecto lab_5 (utilice el ID del proyecto). Además la subred debe pertenecer a la red link_1 (utilice el ID de la red), usar IPv4, usar un rango de subred en formato CIDR (como sugerencia, use el rango 10.0.39.96/28 ), tener desactivado el DHCP y no debe usar gateway.

```bash
openstack subnet create subnet_link_1 --project $project_id \
--network $network_id --subnet-range 10.0.39.96/28 --no-dhcp --gateway none
```

**PASO 5:** Cree un puerto con el nombre port_1_link_1. El puerto debe crearse sobre el proyecto lab_5 (utilice el ID del proyecto). Además el puerto debe pertenecer a la red link_1 (utilice el ID de la red) y tener desactivado el port-security.

```bash
openstack port create port_1_link_1 --project $project_id \
--network $network_id --disable-port-security
```

**PASO 6:** Cree un puerto con el nombre port_2_link_1. El puerto debe crearse sobre el proyecto lab_5 (utilice el ID del proyecto). Además el puerto debe pertenecer a la red link_1 (utilice el ID de la red) y tener desactivado el port-security.

```bash
openstack port create port_2_link_1 --project $project_id \
--network $network_id --disable-port-security
```

<!-- Fuente: página 46 del PDF original -->

**PASO 7:** Utilice los documentos adjuntados en su actividad de laboratorio para crear una instancia con el nombre “instance_1”, imagen cirros y flavor 512MBRAM_1VCPUs_4GBRoot. Asimismo, la instancia debe tener attacheado el puerto port_1_link_1.

Sugerencia: complete el archivo .env y luego utilice el archivo main.py (según convenga). Trate de no modificar los otros archivos.

**PASO 8:** De igual manera al paso anterior, cree una instancia con el nombre “instance 2”, imagen cirros y flavor 512MBRAM_1VCPUs_4GBRoot. En este caso, la instancia debe tener attacheado el puerto port_1_link_2.

**PASO 9:**

Verifique que la creación de las instancias haya sido exitosa

```bash
openstack server list --project lab5
```

**PASO 10:** Obtenga la url de la consola de cada una de las instancias

```bash
openstack console url show <instance_1_id>
openstack console url show <instance_2_id>
```

**PASO 11:** Usando las urls del paso anterior, acceda a las consolas de las instancias (apuntando a Local Host puerto 56080) y configure sus interfaces de red

```bash
# ip add add 192.168.18.X dev eth0
# ip link set dev eth0 up
```

**PASO 12:** Pruebe la conexión entre ambas instancias mediante un ping.

> **Indicación de evidencia:** Complete el Paso 1 de la Actividad 1 del TEL141_LAB5_EL_Template.

**PASO 13:** Ingrese a Horizon y ubique la topología de red del proyecto lab5.

> **Indicación de evidencia:** Complete el Paso 2 y Paso 3 de la Actividad 1 del TEL141_LAB5_EL_Template.

---

## Criterios de evaluación

<!-- Fuente: página 47 -->

La página final de la guía incluye la rúbrica de evaluación.

| Producto | Criterio | Descripción del criterio (según la guía) |
|---|---|---|
| Experiencia de Laboratorio (5 ptos) | Ejecución y resolución | Ejecuta grupalmente las actividades enfocadas en instalar los servicios de OpenStack. |
| Experiencia de Laboratorio (5 ptos) | Ejecución y resolución | Resuelve colaborativamente obstáculos con metodologías de diagnóstico de ingeniería. |
| Experiencia de Laboratorio (5 ptos) | Implementación | Despliega e implementa servicios de nube privada que permiten orquestar máquinas virtuales. |
| Experiencia de Laboratorio (5 ptos) | Análisis y resolución de problemas | Identifica y resuelve colaborativamente incidencias durante el despliegue de servicios de nube privada. |
| Desempeño en el Laboratorio (2 ptos) | Comprensión del proceso | Sustenta el proceso y evidencia comprensión de los componentes y del diseño modular distribuido. |
| Reporte Final (6 ptos) | Ejecución y resolución | Despliega y configura una topología P2P de dos VMs con la CLI de OpenStack. |
| Reporte Final (6 ptos) | Ejecución y resolución | Verifica la conectividad de capa 2 del modelo OSI en una red overlay, comprobando transporte e aislamiento entre servidores físicos. |
| Evaluación Continua del Proyecto (2 ptos) | Presentación | Presenta y justifica el avance del diseño e implementación de VM Placement. |
| Cuestionarios de clase (5 ptos) | Comprensión de teoría | Demuestra comprensión de los fundamentos teóricos utilizados en la experiencia. |

![Rúbrica de evaluación del Laboratorio 5](GUIA_LAB5_assets/rubrica_evaluacion_lab5.png)

---

## Notas de fidelidad y posibles inconsistencias del original

1. La guía utiliza Ubuntu 20.04 y OpenStack Victoria. Los comandos se transcribieron como documentación del laboratorio, **no como una actualización tecnológica**.
2. En la actividad P2P, el **paso 6** crea el puerto `port_2_link_1`, pero el **paso 8** menciona `port_1_link_2` para la segunda instancia. Se conserva el texto original: esa referencia debe comprobarse al ejecutar el laboratorio.
3. En el **paso 11** aparece el comando `ip add add 192.168.18.X dev eth0`, tal como figura en el PDF. No se ha corregido silenciosamente.
4. El documento usa el nombre `lab5` y en algunas instrucciones lo llama `lab_5`; se conserva la escritura de cada paso.
5. La guía de instalación emplea `tenant_network_types vlan` en Neutron ML2 y en la rúbrica final se utiliza la expresión «red overlay»; no se reinterpreta esa terminología.
6. La documentación contiene operaciones de configuración del sistema, credenciales y servicios. Antes de ejecutar en la infraestructura compartida, revisar los comandos, los permisos y la configuración real; este documento **no acredita ejecución ni resultados**.
7. El PDF original tiene 47 páginas y los dibujos y capturas originales se suministran como imágenes en `GUIA_LAB5_assets/`. El logotipo repetido de PUCP no se duplica en cada página para evitar ruido.

**Fin de la conversión.**
