# MS-10 — Asignación de un slice real: el profesor asigna, el alumno lo ve y abre la consola

- **Fecha:** 2026-11-10 · **Host:** app server · **Código:** `fase2` `83db479` (D-14) + `52613ef` (script de contraseñas)
- **Ejecución:** el usuario fijó contraseñas propias para `prof1` y `alumno1` con `scripts/set_user_passwords.py`
  (no impresas) y operó la web como cada uno. Verificación de Claude: bases de slice-manager, IAM (auditoría),
  platform-manager y OpenStack, solo lectura.
- **Tipo:** [REAL].

## Secuencia (hora del app server, auditoría de IAM)

| Hora | Actor | Acción | Resultado |
|---|---|---|---|
| 19:53:52 | `service:slice-manager` | `resource.register_slice` `7ea4fdb7…` (slice `os-lineal-profesor` de prof1 + vm1–vm3) | allowed |
| 19:55:10–53 | prof1 | `course.students TEL141` (lista de alumnos para asignar) | allowed |
| 19:55:56 | prof1 | `assignment.set` slice + vm1 + vm2 + vm3 → alumno1 | allowed (4) |
| 19:55:34 | alumno1 | `resources.list_metadata` (Mis slices) | allowed |
| 19:56:10 | alumno1 | `slice.read` sobre el slice asignado | allowed |
| 19:56:13 | alumno1 | `vm.console` sobre `…-vm1` | allowed |
| 19:56:46 | prof1 | `slice.delete` (política del curso) | allowed |

Motor: `os-lineal-profesor` → READY → DELETED; eventos `CONSOLE` de vm1. Registro del slice-manager: dueño `prof1`,
curso `TEL141`, `iam_registered = 1`. OpenStack después: 0 proyectos `g5-*`; 5 VMs de laboratorio ACTIVE.

## Qué demuestra

- Un slice creado por un profesor queda registrado en IAM (slice + VMs) mediante la identidad de servicio.
- El profesor elige al alumno entre los matriculados y le asigna el slice y sus VMs.
- El alumno ve el slice asignado y abre la consola de su VM; IAM autoriza cada acceso (`slice.read`, `vm.console`).
- El borrado del profesor pasa por la política del curso (`slice.delete`).

## Pendientes observados

- No se ejecutó en real el paso **Quitar** (la revocación está cubierta por `tests/app/test_slices.py`).
- Al borrar un slice, su recurso y asignaciones siguen en IAM (inofensivo: el slice está DELETED y la web lo
  oculta); conviene retirarlos al confirmar el borrado.
