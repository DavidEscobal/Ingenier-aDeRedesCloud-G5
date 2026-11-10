# MS-05 — Paso 5: slice real creado y borrado entrando por el gateway (microservicios completos)

- **Fecha:** 2026-11-10 · **Host:** app server · **Código:** `~/g5-app` = `fase2` `09f32f7` (+ script `435159c`)
- **Flujo:** usuario → **gateway** → **slice-manager** (identidad y `slice.create` en **IAM**) → **platform-manager**
  (token de servicio) → **os-tunnel** → OpenStack. Decisión D-12.
- **Ejecución:** `python3 scripts/smoke_gateway_slices.py --user admin123`, corrido por el usuario (contraseña y
  tokens nunca impresos). Plantilla `templates/os-lineal-1g.json` (3 VMs CirrOS, flavor `g5-1c-512m-1g`, 2 redes).
- **Tipo:** [REAL].

## Salida

```
OK   1. login por el gateway (token de 900s)
OK   2. curso TEL141 creado en IAM HTTP 201
OK   3. crear slice por el gateway HTTP 202
     slice_id=b5c3bd92892340e2b058fee189ea6c3f operación=520b91ad68a3444abb7a37dada186c7a
     t=  0.0s estado=QUEUED
     t=  5.1s estado=DEPLOYING
     t= 20.2s estado=READY
OK   4. el slice llega a READY READY
     evento 55 OS_CREATED: server vm1
     evento 56 OS_CREATED: server vm2
     evento 57 OS_PLACED: vm1@worker3, vm2@worker3, vm3@worker3
     evento 58 READY: Instancias ACTIVE en Nova: vm1@worker3, vm2@worker3, vm3@worker3
OK   5. aparece en la lista con dueño y curso dueño=admin123 curso=TEL141 estado=READY
OK   6. slice inexistente → 404
OK   7. borrar por el gateway HTTP 202
     t=  0.0s estado=DELETING
     t= 15.2s estado=DELETED
OK   8. el slice llega a DELETED DELETED

Resultado: 8/8 OK
```

## Verificación posterior (Claude, solo lectura)

| Comprobación | Resultado |
|---|---|
| Proyectos / servidores / redes `g5-*` en OpenStack | ninguno |
| VMs de laboratorio (`lab5`, `topo1_lab6`) | 5 ACTIVE, intactas |
| Registro del slice-manager | `b5c3bd92…` → dueño `admin123`, curso `TEL141`, proveedor `openstack` |

## Pruebas automáticas asociadas

`tests/app/test_slices.py` (5 casos, procesos reales de IAM, slice-manager y gateway con platform-manager
simulado): ciclo completo, solo el token de servicio llega al platform-manager, aislamiento entre profesores
(404), alumno y curso ajeno rechazados sin tocar el platform-manager, idempotencia por usuario, 422 explicado.
Suites: `tests/app` 19/19, núcleo 92/92.

## Límites

Probado con el rol admin. Profesor y alumno están cubiertos por las pruebas automáticas, no en el clúster.
El slice no se registra todavía como recurso IAM (asignación a alumnos, `professor_can_modify`, cuotas: pendientes).
