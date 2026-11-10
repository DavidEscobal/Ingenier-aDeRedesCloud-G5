# MS-06 — Roles académicos contra el clúster real: profesor crea, otro profesor y alumno aislados

- **Fecha:** 2026-11-10 · **Host:** app server · **Código:** `fase2` `25cdc94` (`scripts/smoke_gateway_roles.py`)
- **Flujo:** todo por el **gateway** → slice-manager (IAM decide identidad y permisos) → platform-manager → OpenStack.
- **Ejecución:** `python3 scripts/smoke_gateway_roles.py --admin admin123`, corrido por el usuario. El script asegura en
  IAM `prof1`, `prof2` (profesores) y `alumno1` (alumno) matriculados en `TEL141`, con contraseñas aleatorias que no
  se imprimen ni se guardan. Plantilla `templates/os-lineal-1g.json` (3 VMs CirrOS).
- **Tipo:** [REAL]. Cierra el límite declarado en MS-05 (solo rol admin).

## Salida

```
OK   1. usuarios prof1, prof2 (profesor) y alumno1 (alumno) listos en TEL141
OK   2. alumno1 NO puede crear slices HTTP 403 not_authorized
OK   3. prof1 NO puede crear en un curso ajeno HTTP 403
OK   4. prof1 crea un slice en TEL141 HTTP 202
     slice_id=6ed86684c89347719e33e9c7c6e5dc49
     t=  0.0s estado=DEPLOYING
     t= 20.3s estado=READY
OK   5. el slice de prof1 llega a READY READY
OK   6. prof2 NO lo ve en su lista (0 slices propios)
OK   7. prof2 NO puede consultarlo HTTP 404
OK   8. prof2 NO puede borrarlo HTTP 404
OK   9. alumno1 NO puede consultarlo (aún no está asignado) HTTP 404
OK   10. el admin SÍ lo ve, con dueño prof1 dueño=prof1 estado=READY
OK   11. prof1 sigue viéndolo READY (el intento de prof2 no lo afectó) READY
OK   12. prof1 borra su slice HTTP 202
     t=  0.0s estado=DELETING
     t= 15.2s estado=DELETED
OK   13. el slice llega a DELETED DELETED

Resultado: 13/13 OK
```

## Verificación posterior (Claude, solo lectura)

| Comprobación | Resultado |
|---|---|
| Proyectos / servidores / redes `g5-*` en OpenStack | ninguno |
| VMs de laboratorio | 5 ACTIVE, intactas |
| Registro del slice-manager | `6ed86684…` → dueño `prof1`, curso `TEL141` (y el de MS-05, dueño `admin123`) |
| Usuarios IAM | `admin123` (admin), `prof1`, `prof2` (professor), `alumno1` (student), activos |
| Matrículas TEL141 | `alumno1`, `prof1`, `prof2` |

## Qué demuestra

- **Autorización por rol y curso (IAM):** el alumno y el curso ajeno se rechazan (403) antes de tocar la infraestructura.
- **Aislamiento entre usuarios:** un profesor no ve, no consulta y no borra el slice de otro (404, sin revelar existencia),
  y su intento no altera el slice.
- **Alcance del admin:** ve todos los slices con su dueño.
- **Ciclo real** de un profesor: READY en ~20 s y borrado limpio en ~15 s.

## Límites

- El alumno todavía no puede ver slices asignados: falta registrar el slice como recurso en IAM y asignarlo (D-12, pendiente).
- `professor_can_modify` y las cuotas del curso aún no se aplican.
