# MS-11 — Importar una imagen desde la web y desplegar VMs con ella

- **Fecha:** 2026-11-10 · **Host:** app server · **Código:** `fase2` `83fa6b4` (D-15) + `b0d77ea` (detección de formato)
- **Camino:** navegador → web (nginx, sin búfer) → gateway → **image-catalog** (IAM `image.manage`) → platform-manager
  (token de servicio `image-catalog`) → **Glance**, todo en streaming; nada se escribe en el disco del app server.
- **Ejecución:** el usuario, como `admin123`, importó `cirros-0.6.2-x86_64-disk.img` (CirrOS oficial, descargado por él)
  con el nombre `cirros-062`, y luego desplegó desde el editor una topología lineal de 2 VMs con esa imagen.
- **Tipo:** [REAL]. Verificación de Claude: catálogo, Glance, motor y Nova, solo lectura.

## Verificaciones previas (sin credenciales de usuario)

| Prueba | Resultado |
|---|---|
| `GET /api/v1/images` · `POST /api/v1/images` sin token | 401 · 401 |
| image-catalog → platform-manager → Glance | 200: `cirros` (12.1 MB, pública) |

## Importación

| Fuente | Resultado |
|---|---|
| Log del image-catalog | `POST /v1/images?name=cirros-062&disk_format=qcow2` → **201 Created** (20:26:45) |
| Catálogo G5 | `cirros-062`, openstack, id Glance `fdae0322-d5ee-422e-9668-59388067cdca`, qcow2, 20.44 MB, SHA-256 `07e44a73e54c94d9…`, importada por `admin123` |
| Glance | `cirros-062` **active**, **public**, qcow2, 20.44 MB (junto a `cirros`) |

El formato se detectó como qcow2 por la cabecera del archivo aunque la extensión era `.img`.

## Uso en un slice

| Fuente | Resultado |
|---|---|
| Motor | slice `lineal-2` **READY**; imágenes del spec: `cirros-062` |
| Nova | `g5-252e62eb-n1` y `g5-252e62eb-n2` **ACTIVE** en worker3, arrancadas desde `cirros-062` |

## Conclusión

Una imagen importada por la interfaz queda disponible para todos los proyectos y se usa en el editor y en el
despliegue sin pasos manuales en OpenStack. Pendiente: materialización en el clúster Linux y borrado de imágenes.
