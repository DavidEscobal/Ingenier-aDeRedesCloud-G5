# EX1 — Demo de soporte Linux Cluster R2


## 1. Cambios y alcance de la implementación

- Tres workers, con la asignación round robin exacta del examen. El gateway pasa a server4 para liberar server3 como Worker3.
- Plantillas EX1, lineal y anillo. Cada enlace representa un dominio L2 separado; el anillo gráfico no convierte a las VMs en bridges o routers.
- Dos imágenes: Ubuntu y CirrOS. Los sabores admiten disco fraccionario de 2.2, sin redondearlo a 3.
- Ubuntu recibe usuario, clave pública, contraseña para la consola y todas las NICs mediante NoCloud/cloud-init. CirrOS recibe direcciones y nombres de NIC por su consola serie.
- Solo VM1 y VM3 tienen red de acceso, ruta por defecto, salida a Internet y publicación SSH.
- La herramienta presenta VM, worker, PID, nombre de QEMU, ruta QCOW2, MAC y NIC. Las operaciones, solicitudes y evidencias quedan guardadas.
- El borrado retira discos, semillas de cloud-init, TAP, bridges y reglas propios. También elimina automáticamente las bases del slice que ya no estén referenciadas en cada worker. Las bases compartidas se conservan.
- Preparación SSH autónoma y un único procedimiento de presentación, sin dependencias de scripts antiguos.

La implementación corresponde al **Driver Linux/R2**, con cliente de API, validación de planes, reservas y ejecutor para demostrarlo. En la arquitectura completa, Infrastructure Manager consumiría este contrato. Aquí `g5.demo` y `g5.cli` actúan como clientes del driver. Usan su API HTTP, no ejecutan directamente la creación de VMs. No se implementan los servicios completos de UI, Keycloak, RabbitMQ, MySQL, MongoDB, AWS u OpenStack. SQLite aporta la persistencia transaccional y la cola local de operaciones del driver.

## 2. Infraestructura física y topología solicitada

Son dos niveles distintos: los servidores y OFS alojan y transportan los recursos; la topología EX1 es el slice de seis VMs que se crea encima.

### 2.1 Infraestructura VNRT

| Equipo | Gestión interna inicial | Puerto de entrada VNRT indicado en PDF | Función en esta entrega |
|---|---|---:|---|
| server1 / Worker1 | 10.0.10.1 | 5801 | VM1 y VM4; QEMU/KVM, discos, TAP y OVS |
| server2 / Worker2 | 10.0.10.2 | 5802 | VM2 y VM5; QEMU/KVM, discos, TAP y OVS |
| server3 / Worker3 | 10.0.10.3 | 5803 | VM3 y VM6; QEMU/KVM, discos, TAP y OVS |
| server4 / headnode | 10.0.10.4 | 5804 | API 8085, estado, catálogo, ejecutores, noVNC 6080 y gateway por slice |
| OFS | 10.0.10.5 | 5805 | Transporte QinQ, bridge `OFS` |

El inventario inicial supone `ens3` para gestión y `ens4` para datos en server1–4; OFS usa `ens4`–`ens8`. Antes de desplegar, se comprueba que server4 dispone de una interfaz de datos conectada a OFS y configura los nombres reales. El gateway necesita ese enlace; la conexión de gestión por sí sola no lo sustituye. `doctor` verifica interfaces, direcciones, binarios y KVM; la conectividad física completa se confirma con la aceptación real.

Las IP internas son valores iniciales del paquete recibido. Si la VPN de examen entrega otros valores, se actualiza `config/cluster.json`. Los puertos 5801–5805 son entradas a los hosts; no son puertos asignados automáticamente a las VMs.

### 2.2 Slice y flavours

| VM | Sistema | vCPU | RAM | Disco solicitado | Worker | Acceso externo |
|---|---|---:|---:|---:|---|---|
| VM1 / `vm1` | Ubuntu | 1 | 512 MiB | 2.2 | server1 | Internet y SSH |
| VM2 / `vm2` | CirrOS | 1 | 512 MiB | 1 | server2 | Sin publicación ni ruta por defecto |
| VM3 / `vm3` | Ubuntu | 1 | 512 MiB | 2.2 | server3 | Internet y SSH |
| VM4 / `vm4` | Ubuntu | 1 | 512 MiB | 2.2 | server1 | Sin publicación ni ruta por defecto |
| VM5 / `vm5` | Ubuntu | 1 | 512 MiB | 2.2 | server2 | Sin publicación ni ruta por defecto |
| VM6 / `vm6` | CirrOS | 1 | 512 MiB | 1 | server3 | Sin publicación ni ruta por defecto |

El proyecto rotula RAM 0.5 GB y disco 2.2/1 GB. El inventario adopta la convención binaria habitual de QEMU: 512 MiB y `disk_unit: "GiB"`. Así, 2.2 corresponde a **2 362 232 320 bytes**, alineados al sector de 512 bytes; 1 corresponde a 1 073 741 824 bytes. Si la evaluación requiere GB decimales, fija `disk_unit: "GB"` antes de crear slices: 2.2 será 2 200 000 000 bytes. La unidad elegida aparece en `/v1/capabilities`; no se cambia silenciosamente el flavor. El tamaño virtual de la base debe caber en el disco solicitado.

La demanda es 6 vCPU y 3072 MiB. Cada worker necesita 2 vCPU y 1024 MiB para las VMs, además de margen para el host. Los discos suman 4.4 en server1, 3.2 en server2 y 3.2 en server3, más las bases y el margen de almacenamiento. Las capacidades reservables iniciales son 2 vCPU, 2048 MiB y 12 unidades de disco por worker: **son configuración, no mediciones**.

### 2.3 Enlaces 

| Red | Extremos e IP | NICs en los invitados | C-VLAN |
|---|---|---|---:|
| `link12`, 192.168.12.0/27 | VM1 .10 — VM2 .11 | `to-vm2` — `to-vm1` | 112 |
| `link23`, 192.168.23.0/27 | VM2 .10 — VM3 .11 | `to-vm3` — `to-vm2` | 123 |
| `link14`, 192.168.14.0/27 | VM1 .10 — VM4 .11 | `to-vm4` — `to-vm1` | 114 |
| `link34`, 192.168.34.0/27 | VM3 .10 — VM4 .11 | `to-vm4` — `to-vm3` | 134 |
| `link45`, 192.168.45.0/27 | VM4 .10 — VM5 .11 | `to-vm5` — `to-vm4` | 145 |
| `link56`, 192.168.56.0/27 | VM5 .10 — VM6 .11 | `to-vm6` — `to-vm5` | 156 |
| `access1`, 192.168.101.0/27 | VM1 .10 — gateway .1 | `access0` | 301 |
| `access3`, 192.168.103.0/27 | VM3 .10 — gateway .1 | `access0` | 303 |

Las NICs experimentales no tienen ruta por defecto. No se habilita forwarding en ninguna VM. Las redes de acceso están separadas para no añadir un enlace L2 VM1–VM3 que no aparece en el dibujo. El gateway tiene una interfaz de diagnóstico `.1` en cada segmento; su firewall bloquea tránsito entre segmentos. En EX1 el direccionamiento es estático y DHCP está desactivado; el driver conserva soporte DHCP para otras solicitudes.

Los TAP son access de su C-VLAN. Un bridge por slice transporta esas C-VLAN y un puerto `dot1q-tunnel` añade la S-VLAN, asignada de forma exclusiva al slice. OFS transporta la etiqueta externa 802.1ad y la interna 802.1Q. Otro slice puede reutilizar C-VLAN y direcciones con una S-VLAN diferente. La combinación de ambas etiquetas evita consumir una VLAN global por cada enlace; este driver limita cada slice a 64 redes y utiliza el rango S-VLAN configurado, no promete capacidad ilimitada.

## 3. Archivos

| Ruta | Uso |
|---|---|
| `README.md` | Preparación, demo, evaluación, operación y límites |
| `config/cluster.example.json` | Inventario inicial, capacidades, gateway y transporte |
| `templates/ex1.json` | Grafo y sabores del examen, con alias de imagen |
| `templates/lineal.json`, `templates/anillo.json` | Topologías predefinidas de seis nodos |
| `g5/api.py` | API autenticada y carga de imágenes |
| `g5/cli.py` | Cliente HTTP y consulta de operaciones |
| `g5/demo.py` | Resuelve plantillas, despliega vía API y guarda evidencias |
| `g5/model.py` | Validación de recursos, NIC, publicaciones y credenciales del invitado |
| `g5/store.py` | SQLite: reservas, slices, cola, eventos e idempotencia |
| `g5/engine.py` | Dependencias, paralelismo, reintentos y compensaciones |
| `g5/backend.py` | Transporte SSH y doble explícito de pruebas |
| `g5/agent.py` | Acciones remotas sobre QEMU, QCOW2, OVS, invitados y gateway |
| `g5/console.py` | Token noVNC, túnel VNC y expiración |
| `g5/manage.py` | Configuración, instalación, inventario, preflight y servicios |
| `api/openapi.json` | Contrato OpenAPI 3.0.3 de endpoints del driver |
| `scripts/setup_ssh.py` | Clave y acceso administrativo a los cinco equipos |
| `scripts/prepare_ubuntu_image.sh` | Preparación opcional de una nueva base Ubuntu |
| `scripts/validate_ex1.py` | Validación real de PID, discos, seis enlaces, broadcasts, Internet, SSH, QinQ y VNC |
| `scripts/validate_concurrency.py` | Dos slices simultáneos y conservación de una base compartida |
| `tests/test_cluster.py`, `tests/test_ex1.py` | 60 pruebas locales |
| `tests/fixtures/two-vms.json` | Fixture pequeño para las pruebas de lógica del driver |

Se crean durante el uso: `config/cluster.json`, credenciales `config/*.token`, `generated/`, `state/` y `evidencias/`. No vienen precargados. Las plantillas de `templates/` **no se envían directamente a la API**: contienen alias `ubuntu`/`cirros`; `demo build` los reemplaza por SHA256 y añade credenciales y orígenes autorizados.

## 4. Preparación previa en server4

### 4.1 Extraer, instalar dependencias e inicializar

Copia el ZIP a server4 y ejecuta:

```bash
unzip Ingenier-aDeRedesCloud-G5-main.zip
cd Ingenier-aDeRedesCloud-G5-main
sudo apt-get update
sudo apt-get install -y python3 qemu-utils openssh-client openssl novnc python3-websockify sqlite3
python3 -m g5.manage init
nano config/cluster.json
```

`init` crea tokens aleatorios de administrador y usuario con permisos 0600. No sobreescribe credenciales existentes. La API debe ejecutarse como `ubuntu`, sin sudo.

Revisa estos valores antes de continuar:

- `workers` y `gateway`: hosts, roles, nombres que coincidan con `hostname -s`, capacidades y dirección externa ya asignada.
- `common.management_interface`, `common.data_ports`, `common.bridge`: gestión `ens3`, datos `ens4` y bridge `br-int` inicialmente. `switch` sobreescribe bridge y puertos con `OFS` y `ens4`–`ens8`.
- Conectividad de datos de server4 a OFS. No asignes la interfaz de gestión como puerto de datos.
- `ssh_key`: `~/.ssh/id_ed25519_ex1`; usuarios SSH `ubuntu`, puerto interno 22, salvo ajuste individual.
- `svid_range`: 1000–3999, reservado para este driver. `transit_pool`: 172.30.0.0/16, sin superposición con redes reales.
- `guest_mtu`: 1450, con transporte MTU 1500. `max_image_gb`: 4 GiB por archivo cargado; no es el tamaño virtual del disco.
- `cache_max_gb`: 8 GiB por worker; márgenes RAM 256 MiB y disco 2 GiB. Amplía si la medición real lo exige, sin ocultar sobreasignación.
- `gc_on_delete: true`: retira bases sin referencias al borrar. `false` conserva caché para despliegues posteriores y exige GC explícito para demostrar el paso 11.
- `probe_user`/`probe_password`: credenciales de la imagen CirrOS. Las iniciales son `cirros`/`gocubsgo`; cámbialas si tu imagen usa otras.

Se requiere Python 3.6 o posterior, QEMU/KVM en los tres workers y OVS con QinQ (2.8 o posterior). Las órdenes de disco usan soporte de `--force-share`. No se descargan ni incorporan automáticamente imágenes de sistemas operativos.

### 4.2 Establecer SSH e instalar agentes

```bash
python3 scripts/setup_ssh.py
python3 -m g5.manage install-agents
python3 -m g5.manage doctor
python3 -m g5.manage bootstrap
```

Verifica las huellas SSH antes de aceptarlas. El script pide las credenciales administrativas necesarias y comprueba `sudo -n true`. Si tu cuenta no dispone de sudo no interactivo para la preparación, debes habilitarlo por el mecanismo administrativo del entorno. El acceso a server4 también se prepara: el backend invoca su agente local por SSH a 10.0.10.4.

La instalación crea `g5qemu`, copia el agente como root e instala un wrapper sudo sin argumentos. Los workers reciben `genisoimage` para NoCloud, además de QEMU/OVS. El gateway recibe OVS, iptables y dnsmasq. OFS no actualiza su OVS. Se puede usar `install-agents --skip-packages` si todo está instalado.

`doctor` no configura la red. `bootstrap` habilita el transporte QinQ, añade los puertos declarados y activa forwarding IPv4 en el gateway. No vacía el firewall ni borra bridges ajenos. Aborta ante controlador externo, IP en un puerto de datos, interfaz de gestión mezclada o modo access incompatible. Antes de usar el mismo transporte, retira mediante su mecanismo original cualquier carga anterior y conserva lo que necesites; este paquete no borra indiscriminadamente recursos ajenos.

### 4.3 Arrancar API y consola

```bash
python3 -m g5.manage units
sudo install -m 0644 generated/g5-cluster-api.service /etc/systemd/system/
sudo install -m 0644 generated/g5-cluster-console.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now g5-cluster-api g5-cluster-console
systemctl --no-pager status g5-cluster-api g5-cluster-console
python3 -m g5.cli nodes
```

La API escucha en 127.0.0.1:8085 y noVNC en 127.0.0.1:6080. Se accede remotamente mediante túnel SSH. Si se configura escucha API fuera de loopback, el servidor exige certificado y clave TLS. No abras directamente los VNC de los workers: escuchan solo en loopback y el driver controla su acceso con tokens.

## 5. Preparar e importar las dos imágenes

Los workers deben empezar sin discos de VMs. Las bases originales y el catálogo se mantienen en **server4**. El despliegue transfiere únicamente las imágenes necesarias: Ubuntu a los tres workers; CirrOS a server2 y server3.

Ubuntu debe ser una base QCOW2 autónoma x86_64 compatible con BIOS/QEMU y cloud-init/NoCloud, con tamaño virtual de hasta 2.2 en la unidad elegida. Debe contener `cloud-init`, `openssh-server`, `netplan.io`, `tcpdump` y **`arping` de Thomas Habets**. `iputils-arping` no proporciona la opción `-B` de la guía. VM4/VM5 no tienen Internet: instala esas herramientas en la base antes de desplegar.

Si necesitas preparar una copia nueva y tienes acceso a los repositorios del sistema invitado:

```bash
sudo apt-get install -y libguestfs-tools
bash scripts/prepare_ubuntu_image.sh /ruta/ubuntu-original.qcow2 /ruta/ubuntu-ex1.qcow2
```

El script deja intacto el origen, aplana la copia e instala las herramientas; limpia identidad cloud-init y claves SSH del invitado. No aumenta ni reduce el tamaño virtual. Si la imagen Ubuntu requiere más de 2.2, utiliza una base pequeña adecuada y comprueba espacio de su sistema de archivos. **No ejecutes un shrink del disco para forzar el flavor.** El builder rechaza una base que no cabe. Este script requiere una imagen Ubuntu ya arrancable; no construye una distribución desde cero.

CirrOS necesita consola serie funcional, las credenciales configuradas y herramientas `ip`, `sudo`, `base64` y `ping`. Su tamaño virtual debe caber en 1 unidad. Prueba ambas bases antes de la exposición.

```bash
mkdir -p generated
qemu-img info /ruta/ubuntu-ex1.qcow2
qemu-img info /ruta/cirros.qcow2
python3 -m g5.cli import-image /ruta/ubuntu-ex1.qcow2 > generated/ubuntu-image.json
python3 -m g5.cli import-image /ruta/cirros.qcow2 > generated/cirros-image.json
python3 -m g5.cli images
```

Sustituye las dos rutas por las reales. La importación valida SHA256, QCOW2, integridad, tamaño máximo y ausencia de backing/data files externos. El `virtual-size` debe cumplir el flavor aunque el archivo comprimido ocupe menos.

### 5.1 Claves del invitado y orígenes de acceso

Incluye la clave pública de server4 para el validador y la pública de tu notebook para el paso 9. En PowerShell, si no tienes una clave para los invitados:

```powershell
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\id_ed25519_ex1_guest"
Get-Content "$env:USERPROFILE\.ssh\id_ed25519_ex1_guest.pub"
```

Copia **solo la pública** a `generated/notebook.pub` en server4. No copies la clave privada del headnode a la notebook. Si usas únicamente el validador interno, basta la pública de server4; para la evaluación externa añade también la pública de la notebook.

Determina el origen que recibe realmente server4 desde tu VPN/notebook. `allowed_sources` debe contener esa IP/CIDR, o el origen después del NAT institucional. Puedes observarlo con `sudo tcpdump -nn -i ens3 tcp port 22001` mientras intentas conectar. Luego, en server4:

```bash
read -r -p 'CIDR de origen autorizado de la notebook/VPN (ej. IP/32): ' EX1_CLIENT_CIDR
python3 -m g5.demo build \
  --ubuntu-image generated/ubuntu-image.json \
  --cirros-image generated/cirros-image.json \
  --ssh-key ~/.ssh/id_ed25519_ex1.pub \
  --ssh-key generated/notebook.pub \
  --allowed-source "$EX1_CLIENT_CIDR"
```

Puedes repetir `--allowed-source` para otro origen concreto. Se añade automáticamente 10.0.10.4/32 para el validador local. Se generan `generated/ex1.json`, `lineal.json`, `anillo.json` y `guest-credentials.json`. Este último contiene el usuario `ex1`, la contraseña aleatoria de login VNC y su hash; se guarda con permisos 0600 y se reutiliza al regenerar las plantillas. **SSH en Ubuntu usa claves; la contraseña es para la consola.** No muestres ese archivo ni las URLs con tokens al publicar evidencias.

## 6. Ensayo de preparación y concurrencia

Pruebas locales, sin tocar infraestructura:

```bash
python3 -m unittest discover -s tests -v
```

Ensayo real opcional, antes del EX1 y sin otros slices activos:

```bash
python3 scripts/validate_concurrency.py \
  --image generated/cirros-image.json \
  --run evidencias/concurrencia-01
```

Crea dos slices de dos VMs, uno por solicitud concurrente, con las mismas C-VLAN y direcciones, pero distinta S-VLAN. Comprueba idempotencia y que borrar uno no detenga el otro ni elimine la base compartida. Después elimina sus slices. Esta prueba verifica concurrencia y referencias de imágenes; la conectividad EX1 se comprueba por separado. Si hay un timeout, conserva `requests.json` y los archivos de operación para recuperar la solicitud; no cambies de clave de idempotencia sin comprobar si ya fue aceptada.

## 7. Guion de presentación siguiendo los 11 pasos del PDF

La evaluación de implementación asigna 12 puntos en su tabla. El extracto de cronograma menciona la primera presentación el **12 de octubre** y pide mostrar EX1 además de lineal/anillo. Este README no asigna puntajes individuales que el PDF no indica. El orden siguiente reproduce la guía de validación; captura evidencias reales de cada paso.

### Paso 1. VPN y acceso

En tu notebook, conecta la VPN de examen `TEL141_G5.ovpn` con las credenciales entregadas para esa sección. Los datos de una sesión anterior no sustituyen los del examen.

En otra terminal PowerShell abre el túnel noVNC. Si tienes ruta directa a la gestión:

```powershell
ssh -N -L 6080:127.0.0.1:6080 -L 8085:127.0.0.1:8085 ubuntu@10.0.10.4
```

Si accedes mediante el gateway de VNRT, usa su dirección vigente y el puerto 5804:

```powershell
$Ex1VnrtHost = Read-Host 'IP o nombre del gateway VNRT entregado para el examen'
ssh -p 5804 -N -L 6080:127.0.0.1:6080 -L 8085:127.0.0.1:8085 "ubuntu@$Ex1VnrtHost"
```

Mantén el túnel abierto. Son alternativas según tu conectividad; no ejecutes ambos sobre los mismos puertos locales.

### Paso 2. Mostrar workers vacíos

Desde server4:

```bash
python3 -m g5.demo preflight --empty --output evidencias/preflight-inicial.json
```

Debe terminar sin error. El inventario busca todos los procesos QEMU del host y los discos/manifiestos/bases del directorio administrado. **No afirma haber explorado todos los directorios del disco.** Para la comprobación visual por SSH, abre cada worker y ejecuta también:

```bash
hostname
ps -eo pid,args | grep '[q]emu-system' || true
sudo find /var/lib/g5-cluster /var/lib/libvirt/images /home /tmp /opt \
  -type f \( -iname '*.qcow2' -o -iname '*.qcow' -o -iname '*.img' -o -iname '*.raw' -o -iname '*.vmdk' -o -iname '*.vdi' -o -iname '*.iso' \) \
  -print 2>/dev/null
```

Una ruta que no exista no es un disco pendiente; interpreta la salida. Si hay imágenes de VMs en otros directorios usados por tu grupo, revísalos también. No borres datos desconocidos para aparentar un worker vacío. La base del catálogo en server4 puede permanecer: el paso se refiere a los workers.

### Paso 3. Desplegar el slice asignado

```bash
python3 -m g5.demo deploy --file generated/ex1.json --run evidencias/ex1-01
```

La carpeta registra el cuerpo y la clave antes de enviar la petición. Repetir exactamente el comando permite recuperar la misma solicitud si hubo timeout. Para otra demostración usa otra carpeta, por ejemplo `ex1-02`, después de borrar la anterior.

Se despliegan VM1/VM4 en server1, VM2/VM5 en server2 y VM3/VM6 en server3. Se reserva toda la capacidad antes de crear recursos, se prepara QinQ, se transfieren bases, se crea la red, luego se arrancan VMs. Los workers trabajan en paralelo; las dos VMs de cada worker se atienden secuencialmente. `READY` verifica QEMU y red del host, no garantiza que Ubuntu haya terminado cloud-init.

### Pasos 4 y 5. Mostrar IDs, PIDs y comprobar por SSH

```bash
python3 -m g5.demo status --run evidencias/ex1-01
cat evidencias/ex1-01/interfaces.tsv
```

La tabla muestra `vm`, worker, PID real, ejecución y disco. Se guardan `processes.json`, `diagnostics.json`, `slice.json`, `events.json` e `interfaces.tsv`. El identificador QEMU tiene forma `g5-<slice_id>-vmN`.

En el worker indicado por la tabla, sustituye el PID con el observado:

```bash
ps -p PID_OBSERVADO -o pid,etime,args
```

No uses números de PID de un ejemplo o una ejecución anterior. Deben coincidir PID, nombre QEMU y VM del plan.

### Paso 6. Manejo de errores y reintentos

```bash
python3 - <<'PY'
import json
from pathlib import Path
for event in reversed(json.loads(Path('evidencias/ex1-01/events.json').read_text())):
    print(event['event'], event['detail'])
PY
```

Hay hasta tres intentos remotos, con espera incremental; también se registran los reintentos de transferencia de imágenes. Las acciones usan identificadores estables y detectan recursos existentes. Un fallo definitivo al crear activa compensación; si la limpieza no se confirma, se mantienen reservas y el estado es `ERROR_CLEANUP`.

Si el despliegue no falló, no inventes eventos `RETRY`. Explica el mecanismo y muestra las pruebas de fallo inyectado de `tests/`; esas pruebas son simuladas. Si ocurre un error real, actualiza `demo status`, muestra el evento y su recuperación. No desconectes gestión ni borres binarios para provocar fallos durante la exposición.

### Paso 7. VNC y aislamiento de broadcasts

Obtén accesos a las cuatro Ubuntu:

```bash
python3 -m g5.demo consoles --run evidencias/ex1-01
```

En la notebook abre las URLs de VM1, VM3, VM4 y VM5. Son consolas VNC a través de noVNC y del túnel a server4. El token dura 600 segundos; si expira, vuelve a emitirlo. Otro token para la misma VM revoca el anterior, por lo que conserva una sesión por VM durante la prueba.

Inicia sesión con `ex1` y la contraseña de `generated/guest-credentials.json`. En las cuatro Ubuntu revisa:

```bash
cloud-init status --wait
ip -br addr
```

Las NICs deben coincidir con la tabla de enlaces. Si no aparecen esos nombres/IP, corrige la inicialización de la imagen antes de medir aislamiento.

En **VM1, VM3 y VM5**, deja una terminal escuchando:

```bash
sudo tcpdump -en -i to-vm4
```

En **VM4**, ejecuta por separado:

```bash
sudo arping -B -c3 -I to-vm1
sudo arping -B -c3 -I to-vm3
sudo arping -B -c3 -I to-vm5
```

| Orden emitida en VM4 | Receptor de los tres broadcasts entre las VMs observadas | VMs que no deben recibir esos broadcasts |
|---|---|---|
| `to-vm1` | VM1 | VM3 y VM5 |
| `to-vm3` | VM3 | VM1 y VM5 |
| `to-vm5` | VM5 | VM1 y VM3 |

Distingue las solicitudes de VM4 del ARP de fondo por su MAC emisora. El validador automático filtra esa MAC y exige tres tramas en el receptor correcto y cero en los otros dos. No exige que alguien responda a la IP broadcast: la evidencia relevante es la recepción Ethernet de las solicitudes.

### Paso 8. Internet en VM1 y VM3

Desde VNC, en cada una:

```bash
ip -4 route
ping -c 3 8.8.8.8
```

VM1 debe usar `192.168.101.1` y VM3 `192.168.103.1` por `access0`. VM2/VM4/VM5/VM6 no reciben ruta por defecto. La salida pasa por el namespace del slice, el gateway y el NAT de la infraestructura.

### Paso 9. SSH desde la notebook a VM1 y VM3

Se publican:

| VM | Publicación en server4 | Destino |
|---|---|---|
| VM1 | 10.0.10.4:22001/TCP | 192.168.101.10:22 |
| VM3 | 10.0.10.4:22003/TCP | 192.168.103.10:22 |

Con ruta VPN hacia la gestión, en PowerShell:

```powershell
ssh -i "$env:USERPROFILE\.ssh\id_ed25519_ex1_guest" -p 22001 ex1@10.0.10.4
ssh -i "$env:USERPROFILE\.ssh\id_ed25519_ex1_guest" -p 22003 ex1@10.0.10.4
```

Ejecuta `hostname` en cada sesión para demostrar que llegaste a vm1 y vm3. Comprueba las huellas de las VMs al primer acceso.

**10.0.10.4 es privada.** La figura admite red de acceso pública o privada. Esta solución demuestra publicación selectiva por DNAT desde una red externa al slice. Si la notebook solo alcanza el gateway superior de VNRT, ese gateway debe enrutar o publicar los puertos hacia server4; abrir 5804 para SSH del host no publica 22001/22003. Configura con el administrador los destinos y orígenes permitidos antes del examen. El paquete no asigna una IP pública real ni administra ese NAT superior.

Como acceso operativo alternativo puede usarse un túnel SSH a server4, pero al presentarlo aclara que demuestra SSH tunelizado, no una publicación directa a Internet. El validador prueba DNAT desde el headnode; **esa prueba no acredita acceso desde la notebook**.

### Paso 10. QCOW2 y ahorro de espacio

Toma la ruta real de `processes.json` y, en su worker:

```bash
sudo qemu-img info --force-share /var/lib/g5-cluster/vms/SLICE_ID-vm1/disk.qcow2
sudo qemu-img info --force-share --backing-chain /var/lib/g5-cluster/vms/SLICE_ID-vm1/disk.qcow2
sudo du -h /var/lib/g5-cluster/vms/SLICE_ID-vm1/disk.qcow2
```

Sustituye `SLICE_ID` y la VM por los reales. `--force-share` permite inspeccionar el disco abierto por QEMU; no escribe sobre él. Muestra `file format: qcow2`, `virtual size`, `disk size` y `backing file`. El overlay almacena diferencias y crece según uso; no ocupa de inicio todo su tamaño virtual. VM1 y VM4 comparten la misma base local Ubuntu en server1.

### Paso 11. Borrado inteligente

Cierra las consolas y ejecuta:

```bash
python3 -m g5.demo cleanup --run evidencias/ex1-01
python3 -m g5.demo preflight --empty --output evidencias/preflight-final.json
```

Muestra `cleanup.json` y repite la inspección por SSH del paso 2. Deben desaparecer procesos, overlays, semillas, TAP, bridges propios y bases sin referencias. El bridge físico `br-int`/`OFS`, la configuración de agentes, la base de datos de auditoría y los registros de protección contra trabajos tardíos permanecen: son infraestructura del servicio, no VMs del slice.

El catálogo del headnode se conserva para una próxima solicitud. Si otra VM o un overlay huérfano depende de una base en un worker, el GC la conserva. Ese comportamiento es borrado inteligente; eliminarla rompería el otro disco.

Para retirar una caché no utilizada que quedó de una prueba anterior:

```bash
python3 -m g5.cli cache-gc server1 --all-unused
python3 -m g5.cli cache-gc server2 --all-unused
python3 -m g5.cli cache-gc server3 --all-unused
```

Nunca reemplaces este procedimiento por `pkill qemu`, borrado global de OVS o `rm -rf` de los directorios de estado.

## 8. Validador real y topologías predefinidas

### 8.1 Validación automática del EX1

Después del despliegue y antes del borrado:

```bash
python3 scripts/validate_ex1.py \
  --run evidencias/ex1-01 \
  --guest-key ~/.ssh/id_ed25519_ex1
```

Ejecuta desde server4, donde reside el namespace del gateway, con permiso para `sudo -n ip netns exec`. Comprueba backend real, ubicación, PID por SSH, tamaños y backing QCOW2, inicialización Ubuntu, MAC/IP, ping en los seis enlaces, las tres rondas de broadcast, Internet en VM1/VM3, ausencia de salida en VM4/VM5, publicaciones SSH desde el headnode, doble etiqueta en OFS y VNC con tokens válidos, inválidos y expirados.

Usa la clave pública ya instalada por `demo build`. Las primeras huellas SSH de las VMs se guardan en un archivo propio de esa ejecución. No cambia las huellas SSH de los workers. Las capturas se guardan en `evidencias/ex1-01/validation-.../`. El validador no crea ni borra el slice. Si aborta, deja el slice para diagnóstico.

El resultado exitoso es `AUTOMATED_PASS_MANUAL_PENDING`, porque siguen requiriéndose la VPN, las sesiones VNC/SSH desde la notebook y el borrado final. No presenta un `PASS` global del examen. Las pruebas automáticas de VNC emiten tokens nuevos y los dejan expirar; después emite otra vez `demo consoles` para la presentación manual.

### 8.2 Lineal y anillo

Se usan las mismas seis VMs, sabores y asignación round robin. Lineal conecta 1–2–3–4–5–6; anillo añade 6–1. Cada enlace mantiene su segmento L2. Solo VM1/VM3 conservan red de acceso.

Con las cuotas iniciales y los puertos publicados compartidos, ejecuta las tres demos **secuencialmente**:

```bash
python3 -m g5.demo deploy --file generated/lineal.json --run evidencias/lineal-01
python3 -m g5.demo status --run evidencias/lineal-01
python3 -m g5.demo consoles --run evidencias/lineal-01
# Mostrar conexiones del grafo usando interfaces.tsv y ping al vecino.
python3 -m g5.demo cleanup --run evidencias/lineal-01

python3 -m g5.demo deploy --file generated/anillo.json --run evidencias/anillo-01
python3 -m g5.demo status --run evidencias/anillo-01
python3 -m g5.demo consoles --run evidencias/anillo-01
# Mostrar también el enlace VM6-VM1 que cierra el anillo.
python3 -m g5.demo cleanup --run evidencias/anillo-01
```

`validate_ex1.py` comprueba intencionalmente el grafo EX1, por lo que rechaza lineal/anillo. En estas topologías usa `interfaces.tsv` para identificar la NIC y la IP del vecino; no reutilices las direcciones de un enlace inexistente.

## 9. Correspondencia con los criterios de implementación R2

| Criterio de la tabla | Implementación | Evidencia que se presenta |
|---|---|---|
| VMs en servidores seleccionados | Plan inmutable y QEMU/KVM; tres workers | Tabla VM–worker–PID; pasos 3–5 |
| Enlaces entre distintos servidores | TAP, C-VLAN y transporte S-VLAN por OFS | Ping por enlace y capturas del paso 7 |
| API diseñada implementada | REST autenticada; cliente CLI/demo | `api/openapi.json`, operaciones y diagnósticos |
| Errores y reintentos | Idempotencia, tres intentos, eventos, compensación | Paso 6; pruebas de fallos claramente identificadas como locales |
| Envío y manejo de imágenes | SHA256, validación, transferencia y caché por worker | Catálogo y rutas de bases; importación previa/despliegue |
| Borrado de VMs y recursos | Retirada de recursos por ID/propiedad | Paso 11 y comparación de inventarios |
| Consola virtual y tokens | noVNC, túnel, expiración y revocación | Paso 7; prueba RFB y expiración |
| Internet selectivo | Ruta por access0, firewall, namespace y NAT | Paso 8 |
| Acceso desde una red externa | DNAT por VM y lista de orígenes | Paso 9; depende de ruta/NAT superior para acceso desde Internet |
| QCOW eficiente | Base inmutable y overlays diferenciales | Paso 10 |
| Pedidos concurrentes | Cola durable, ejecutores, reservas transaccionales | `validate_concurrency.py`; pruebas de no sobreasignación |
| Borrado inteligente de imágenes | GC automático con referencias de manifiestos/overlays | Bases desaparecen tras paso 11; ensayo de base compartida |
| Caché frente a espacio/velocidad | Reutilización por SHA y GC LRU bajo presupuesto | Base única por worker; conservación mientras siga referenciada |
| QinQ | `dot1q-tunnel`, etiqueta 802.1ad, C-VLAN por enlace | Captura en OFS con S-VLAN y C-VLAN |

La rúbrica, el PDF y el cronograma son guías de lo que hay que demostrar; esta tabla no certifica aprobación ni afirma que una prueba física ya se ejecutó.

## 10. API, operación y recuperación

El contrato completo está en `api/openapi.json`. Operaciones principales:

| Método y ruta | Función |
|---|---|
| `GET /v1/capabilities` | Capacidades, backend real/simulado y unidad de disco |
| `GET /v1/nodes`, `PATCH /v1/nodes/{node}` | Salud, consumo/reservas y habilitación de admisión |
| `GET /v1/images`, `PUT /v1/images/{sha256}`, `DELETE /v1/images/{sha256}` | Catálogo e importación/borrado protegido |
| `POST /v1/nodes/{node}/cache/gc` | Limpieza local de bases sin referencias |
| `POST /v1/slices`, `GET /v1/slices` | Crear mediante cola y listar |
| `GET /v1/slices/{id}`, `DELETE /v1/slices/{id}` | Plan/estado y borrado |
| `POST /v1/slices/{id}/stop`, `/start`, `/reconcile` | Detener, reanudar o reparar recursos |
| `GET /v1/operations/{id}` | Consultar finalización; 202 no significa desplegado |
| `GET /v1/slices/{id}/events`, `/diagnostics` | Auditoría y estado real por slice |
| `POST /v1/slices/{id}/vms/{vm}/console` | Emitir token VNC |
| `POST /v1/slices/{id}/vms/{vm}/probe` | Sondeo serie de CirrOS; Ubuntu se verifica por SSH/VNC |

Las peticiones requieren Bearer token. Las mutaciones de ciclo de vida necesitan `Idempotency-Key`. Reutiliza la misma clave y el mismo cuerpo ante respuesta incierta. Un cuerpo distinto con la misma clave se rechaza. Solo una operación de ciclo de vida puede estar activa sobre el mismo slice. Los usuarios leen sus slices; el administrador/servicio tiene permisos globales. Los tokens de API se guardan hasheados en la configuración, y los de consola en SQLite; no constituyen el modelo completo de roles académicos de la arquitectura.

Consultas y acciones puntuales:

```bash
python3 -m g5.cli list
python3 -m g5.cli get ID_DEL_SLICE
python3 -m g5.cli diagnostics ID_DEL_SLICE
python3 -m g5.cli events ID_DEL_SLICE
python3 -m g5.cli stop ID_DEL_SLICE
python3 -m g5.cli wait ID_OPERACION_DEVUELTA
python3 -m g5.cli start ID_DEL_SLICE
python3 -m g5.cli wait ID_OPERACION_DEVUELTA
```

Sustituye los IDs; espera cada operación antes de la siguiente. `stop` conserva discos/redes/reservas y puede forzar la detención tras esperar el apagado ACPI. Guarda antes el trabajo del invitado. `reconcile` reaplica recursos de un slice existente con reservas; no compensa destruyendo sus discos si falla.

| Incidencia | Acción |
|---|---|
| `Preflight` falla | Corrige host, interfaz, bridge, KVM, binario o capacidad que indica; no omitas el control |
| Base Ubuntu mayor que el flavor | Consigue/prepara una imagen apropiada; no reduzcas el disco por fuerza |
| `READY` pero Ubuntu no permite login | Espera cloud-init y revisa por VNC; comprueba NoCloud, versión de imagen y credenciales |
| Timeout al crear | Repite `demo deploy` con la misma carpeta; conserva `deployment.json` |
| Fallo definitivo al crear | Revisa `events.json`; `FAILED_CLEANED` significa recursos retirados, `ERROR_CLEANUP` requiere limpieza pendiente |
| Error durante borrado | Corrige la causa y repite `demo cleanup`; se conserva la reserva hasta confirmar limpieza |
| API reiniciada | Las operaciones RUNNING vuelven a pendientes y se ejecutan de forma idempotente; se revocan tokens VNC |
| Broadcast aparece donde no corresponde | Revisa NIC/MAC, C-VLAN de TAP, bridge y forwarding del invitado; no aceptes solo pings como prueba de aislamiento |
| SSH externo falla | Verifica puerto, origen observado, ruta/NAT superior, clave pública y ruta de retorno del invitado |
| Base persiste tras borrar | Consulta manifiestos/overlays: puede seguir referenciada; no la borres manualmente |

Logs y diagnóstico de infraestructura:

```bash
journalctl -u g5-cluster-api -u g5-cluster-console --no-pager -n 100
python3 -m g5.manage doctor
python3 -m g5.manage inventory --nodes server1,server2,server3
```

Los agentes conservan manifiestos y discos en `/var/lib/g5-cluster`. Los recursos propios llevan prefijo `g5` e identificadores de propiedad. La limpieza no actúa sobre QEMU/OVS desconocidos. Para validar manualmente QinQ en un puerto OFS que lleve tráfico del enlace probado:

```bash
sudo tcpdump -en -i ens4 'ether proto 0x88a8'
```

Genera tráfico entre workers mientras capturas. Deben observarse las dos etiquetas; el valor externo está en el plan y el interno en `interfaces.tsv`. Revisa el puerto físico y el efecto de offloads si la captura no ve etiquetas; no declares éxito a partir de la configuración sin observación.

### 10.1 Incorporación o retiro de workers

Añade un worker al inventario con nombre, host, capacidades y puerto de datos hacia OFS; prepara SSH, instala el agente, ejecuta doctor/bootstrap para ese nodo y actualiza el inventario del API. La plantilla EX1 mantiene su asignación fija; otras solicitudes pueden elegir el nuevo worker. El driver admite destinos explícitos, no implementa aquí el servicio completo de Placement.

Para impedir nuevas asignaciones:

```bash
python3 -m g5.cli drain server1
# Después de terminar o borrar sus slices, puede retirarse del inventario.
python3 -m g5.cli drain server1 --enable
```

No retires del inventario un worker con reservas: el driver lo rechaza. Esta versión usa un único proceso API con ejecutores internos; no ofrece actualización sin interrupción ni alta disponibilidad distribuida. Un reinicio breve de la API no borra los QEMU existentes, pero el gateway está en server4: una caída de ese host afecta Internet y consola hasta su recuperación. Replica/persistencia compartida, cola externa y elección de líder serían ampliaciones de arquitectura, no capacidades desplegadas en esta demo.

## 11. Referencias técnicas

Además de los tres adjuntos del proyecto usados para esta revisión, se consultó documentación primaria para la inicialización, discos y transporte:

- QEMU, utilidad qemu-img: https://www.qemu.org/docs/master/tools/qemu-img.html
- cloud-init, NoCloud: https://docs.cloud-init.io/en/26.1/reference/datasources/nocloud.html
- cloud-init, red versión 2: https://docs.cloud-init.io/en/latest/reference/network-config-format-v2.html
- cloud-init, usuarios y grupos: https://docs.cloud-init.io/en/latest/reference/yaml_examples/user_groups.html
- Open vSwitch, puertos QinQ: https://www.openvswitch.org/support/dist-docs/ovs-vswitchd.conf.db.5.html
- Thomas Habets, arping y opción -B: https://github.com/ThomasHabets/arping

Consulta: 7 de octubre de 2026. Usa las versiones disponibles en VNRT y verifica la compatibilidad antes de la presentación.
