# MS-02 — Platform-manager en Docker alcanza OpenStack mediante `os-tunnel`

- **Fecha:** 2026-11-10 · **Host:** app server (`10.20.11.248`) · **Código:** `~/g5-app` = `fase2` `760668c`
- **Despliegue:** `docker compose -f deploy/compose.yaml --profile platform up -d`
- **Configuración:** `deploy/platform-config/` (700/600, fuera de Git), copiada de `~/g5-orchestrator/config`
  y `~/.g5` sin leer ni imprimir secretos; `endpoint_map` → `http://os-tunnel:<puerto>`.
- **Tipo:** [REAL], solo lectura: no se creó ningún recurso en OpenStack. Sin tokens en este registro
  (el token de la API se pasó por stdin).

## 1. Servicios

| Servicio | Estado | Puertos |
|---|---|---|
| gateway | healthy | `127.0.0.1:8000` |
| iam | healthy | interno |
| slice-manager | healthy | interno |
| **os-tunnel** | healthy (los 5 reenvíos abiertos) | ninguno publicado |
| **platform-manager** | healthy | interno |

Log de `os-tunnel`: `ubuntu@10.20.11.245 -> 192.168.202.1 puertos: 5000 8774 9696 9292 6080`.
El servicio `g5-tunnels` del host no se modificó.

## 2. Pruebas desde dentro del contenedor `platform-manager`

| # | Prueba | Resultado |
|---|---|---|
| 1 | `GET /v1/capabilities` con token | 200; proveedores `linux` y `openstack` |
| 2 | `GET /v1/capabilities` sin token | 401 |
| 3 | `GET /v1/slices` | 200; 0 slices (base nueva en el volumen `platform-data`) |
| 4 | Keystone vía `os-tunnel` | 5 proyectos; ningún `g5-*` |
| 5 | Nova vía `os-tunnel` | 5 servidores (de `lab5` y `topo1_lab6`, no del orquestador) |
| 6 | Neutron vía `os-tunnel` | 5 redes |
| 7 | Glance vía `os-tunnel` | imagen `cirros` |

## Conclusión y límites

El núcleo de ejecución corre como microservicio y llega a las cuatro APIs de OpenStack sin depender de los
túneles del host. **No cubre** todavía: crear un slice desde el contenedor (requiere autorización para crear
recursos), la llamada slice-manager → platform-manager (paso 5) ni el driver Linux (falta `cluster.json` de fase 2).
