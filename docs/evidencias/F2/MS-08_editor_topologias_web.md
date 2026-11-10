# MS-08 — Editor de topologías (paso 6): predefinidas, combinación, enlace manual, versiones, export/import y despliegue

- **Fecha:** 2026-11-10 · **Host:** app server · **Código:** `fase2` `afeac3e` (topology-manager) + `e4012c3` (web parte 2)
- **Servicios:** 8 contenedores *healthy* (web, gateway, iam, slice-manager, topology-manager, platform-manager,
  os-tunnel). Ejecución por el usuario desde el navegador (sesión `admin123`); verificación por Claude leyendo las
  bases de cada servicio y OpenStack (solo lectura).
- **Tipo:** [REAL].

## Pasos realizados en la web y verificación

| # | Acción del usuario (web) | Verificación | Criterio R1B |
|---|---|---|---|
| 1 | Topologías → Nueva → **Anillo** 3 VMs (n1–n3) | borrador con 3 enlaces del anillo | Seleccionar topología predefinida |
| 2 | **Árbol** 3 VMs → *Combinar con lo actual* | nodos `a1–a3` añadidos sin colisión de nombres, 2 enlaces del árbol | Editar combinando predefinidas |
| 3 | **Guardar** | borrador `anillo-3` **v1**, 6 VMs, 5 enlaces | Grabar para posterior edición |
| 4 | **Desplegar como slice** (TEL141) | slice `anillo-3` READY: "Instancias ACTIVE en Nova: a1@worker3, a2@worker2, a3@worker1, n1@worker3, n2@worker3, n3@worker3" | Crear slice desde la topología editada |
| 5 | Reabrir el borrador, **conectar n1–a1** arrastrando, Guardar | borrador **v2**, 6 enlaces, contiene n1–a1 | Editar agregando enlaces |
| 6 | **Exportar JSON** e **Importar JSON** | segundo borrador `anillo-3` v1 (id `98c5810c…`) idéntico: 6 VMs, 6 enlaces, n1–a1 | Exportar / importar topologías |
| 7 | Borrar el slice desde la web | DELETED: "Eliminación confirmada en todos los destinos; reservas liberadas" | Borrar slices instanciados |

## Spec compilada del slice desplegado (paso 4, desde el motor)

```
redes: n1-n2 10.60.1.0/24 · n2-n3 10.60.2.0/24 · n3-n1 10.60.3.0/24 · a1-a2 10.60.4.0/24 · a1-a3 10.60.5.0/24
vms:   n1 .11/.11 · n2 .12/.12 · n3 .13/.13 · a1 .14/.14 · a2 .15 · a3 .16   (último octeto fijo por VM)
```

Nova repartió las 6 VMs en los tres computes (worker1, worker2, worker3) con el flavor `g5-1c-512m-1g`.

## Estado final

OpenStack: 0 proyectos, servidores y redes `g5-*`; 5 VMs de laboratorio ACTIVE, intactas.

## Observaciones

- El primer despliegue se hizo con la topología **v1** (anillo y árbol aún sin unir): el editor permite segmentos
  desconectados entre sí; el enlace n1–a1 se agregó después (v2). La v2 no se desplegó para no exceder la capacidad.
- Capacidad: 6 VMs de 1 GB llenaron el clúster (worker1 y worker2 tienen ~1 GB libre por las VMs de laboratorio).
