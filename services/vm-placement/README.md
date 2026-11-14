# vm-placement (R4)

Servicio **sin estado**: recibe el inventario de hosts y las VMs de un slice y devuelve `{vm -> host}` con
**BCDP v2** (`vm-placement_md/bcdp2.py`, misma lógica) o el rechazo con su motivo.

- `POST /v1/placements` (token de servicio, `PLACEMENT_TOKEN_FILE`): estados `PLAN_FOUND`, `HEURISTIC_NO_PLAN`,
  `PLANNING_TIMEOUT` (límite por defecto 1 s) e `INVALID_OR_ERROR`. Todo plan pasa por el validador.
- Filtros previos: zona, salud y telemetría vencida (`age_s > 15`). Las VMs con `host` fijado se descuentan primero.
- Sin telemetría (`cpu_real_cent: null`) se usa la demanda completa de lo comprometido; sin perfil de VM,
  `100 × vcpus`.
- No reserva: el slice-manager pide el plan y el platform-manager lo reserva de forma atómica; si otro slice ganó la
  capacidad (409), el slice-manager vuelve a pedir un plan.
