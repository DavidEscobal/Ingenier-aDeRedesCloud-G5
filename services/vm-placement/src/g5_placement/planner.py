"""Del inventario normalizado a un plan: filtros (zona, salud, telemetría), VMs fijadas, BCDP v2 y validador.

Unidades: RAM y disco en MB; CPU real en centésimas de CPU (150 = 1,5 CPU).
"""
import time

from .engine import DIM_NAMES, DIMS, Timeout, bcdp_v2, validar

PLAN_FOUND = "PLAN_FOUND"
NO_PLAN = "HEURISTIC_NO_PLAN"
TIMEOUT = "PLANNING_TIMEOUT"
INVALID = "INVALID_OR_ERROR"


def host_vectors(h, policy):
    """Capacidad y uso de un host en las 4 dimensiones."""
    cap = [int(policy["cpu_ratio"] * h["cpu_cores"]), int(policy["cpu_limit"] * 100 * h["cpu_cores"]),
           int(h["ram_mb"]), int(h["disk_mb"])]
    real = h.get("cpu_real_cent")
    if real is None:                       # dato ausente no equivale a cero: demanda completa de lo comprometido
        real = 100 * h.get("vcpus_used", 0)
    uso = [int(h.get("vcpus_used", 0)), int(real), int(h.get("ram_used_mb", 0)), int(h.get("disk_used_mb", 0))]
    return cap, uso


def vm_vector(v):
    return [int(v["vcpus"]), int(v["cpu_cent"] if v.get("cpu_cent") is not None else 100 * v["vcpus"]),
            int(v["ram_mb"]), int(v["disk_mb"])]


def eligible(hosts, zone, policy):
    """Hosts candidatos y los descartados con su motivo."""
    ok, out = [], []
    for h in hosts:
        if zone and h.get("zone") != zone:
            out.append({"host": h["id"], "reason": "fuera de la zona %s" % zone})
        elif not h.get("healthy", True):
            out.append({"host": h["id"], "reason": "host no saludable o en mantenimiento"})
        elif h.get("age_s") is not None and h["age_s"] > policy["max_age_s"]:
            out.append({"host": h["id"], "reason": "telemetría vencida (%.0f s)" % h["age_s"]})
        else:
            ok.append(h)
    return ok, out


def shortage(caps, usos, dems, ids):
    """Explica por qué no hay plan: recurso total insuficiente o una VM que no cabe en ningún host."""
    msgs = []
    for q in range(DIMS):
        free = sum(max(0, c[q] - u[q]) for c, u in zip(caps, usos))
        need = sum(d[q] for d in dems)
        if need > free:
            msgs.append("%s insuficiente: se piden %d y quedan %d libres" % (DIM_NAMES[q], need, free))
    if not msgs:
        for d in dems:
            if not any(all(u[q] + d[q] <= c[q] for q in range(DIMS)) for c, u in zip(caps, usos)):
                msgs.append("una VM (%s) no cabe entera en ningún servidor" %
                            ", ".join("%s=%d" % (DIM_NAMES[q], d[q]) for q in range(DIMS)))
                break
    if not msgs:
        def ratio(q):
            free = sum(max(0, c[q] - u[q]) for c, u in zip(caps, usos))
            return sum(d[q] for d in dems) / free if free else float("inf")
        q = max(range(DIMS), key=ratio)
        per_host = ", ".join("%s %d" % (i, max(0, c[q] - u[q])) for i, c, u in zip(ids, caps, usos))
        msgs.append("no hay reparto válido: la capacidad libre está repartida entre servidores; recurso más "
                    "ajustado: %s (se piden %d; libre por servidor: %s)" % (DIM_NAMES[q], sum(d[q] for d in dems), per_host))
    return "; ".join(msgs)


def plan(request):
    """request: {zone, hosts[], vms[], policy{}} -> respuesta (dict)."""
    t0 = time.monotonic()
    policy = request["policy"]
    deadline = t0 + policy["timeout_s"]
    result = {"algorithm": "BCDP v2", "plan": {}, "hosts_opened": 0, "hosts_used": [],
              "discarded_hosts": [], "reason": None}

    def done(status, reason=None):
        result.update(status=status, reason=reason, elapsed_ms=round((time.monotonic() - t0) * 1000, 1))
        return result

    hosts, discarded = eligible(request["hosts"], request.get("zone"), policy)
    result["discarded_hosts"] = discarded
    if not hosts:
        return done(NO_PLAN, "no hay servidores candidatos" + (" en la zona %s" % request["zone"] if request.get("zone") else ""))
    index = {h["id"]: n for n, h in enumerate(hosts)}
    caps, usos = zip(*(host_vectors(h, policy) for h in hosts))
    caps, usos = [list(c) for c in caps], [list(u) for u in usos]
    occupied = [1 if h.get("occupied") else 0 for h in hosts]
    base_occupied = list(occupied)

    # VMs fijadas por el usuario: se descuentan primero y su host cuenta como ocupado.
    fixed, free_vms = {}, []
    for v in request["vms"]:
        if v.get("host"):
            if v["host"] not in index:
                return done(NO_PLAN, "la VM %s está fijada en %s, que no es candidato" % (v["id"], v["host"]))
            h = index[v["host"]]; dv = vm_vector(v)
            if any(usos[h][q] + dv[q] > caps[h][q] for q in range(DIMS)):
                falta = [DIM_NAMES[q] for q in range(DIMS) if usos[h][q] + dv[q] > caps[h][q]]
                return done(NO_PLAN, "la VM %s fijada en %s no cabe (%s)" % (v["id"], v["host"], ", ".join(falta)))
            for q in range(DIMS): usos[h][q] += dv[q]
            occupied[h] = 1; fixed[v["id"]] = v["host"]
        else:
            free_vms.append(v)

    dems = [vm_vector(v) for v in free_vms]
    d = {"N": len(dems), "M": len(hosts), "a": occupied, "_cap": caps, "_uso": usos, "_dem": dems}
    try:
        asg = bcdp_v2(d, deadline=deadline) if dems else {}
    except Timeout:
        return done(TIMEOUT, "se superó el límite de %.1f s" % policy["timeout_s"])
    if asg is None:
        return done(NO_PLAN, shortage(caps, usos, dems, [h["id"] for h in hosts]))
    ok, _ = validar(d, asg)
    if not ok:
        return done(INVALID, "el validador rechazó el plan")
    result["plan"] = dict(fixed, **{free_vms[i]["id"]: hosts[h]["id"] for i, h in asg.items()})
    used = sorted(set(result["plan"].values()))
    result["hosts_used"] = used
    result["hosts_opened"] = sum(1 for hid in used if not base_occupied[index[hid]])
    return done(PLAN_FOUND)
