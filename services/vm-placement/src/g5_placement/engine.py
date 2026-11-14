"""Núcleo BCDP v2 y BFD (referencia), tomados de vm-placement_md/bcdp2.py sin cambios de lógica.

Cambios respecto del original:
- `vectores` lee la instancia ya construida por el adaptador (`_cap`, `_uso`, `_dem`).
- Se quitó el bloque sin efecto de `reparar` (`if not occ[h] and not d["a"][h]: ... pass`).
- `deadline` (time.monotonic): si se supera, se lanza `Timeout` (R4-D-06).
- `bfd_hld` usa `cap[h][1] / 85` en lugar de `cpu_fisica`, como indica la guía.

Dimensiones: 0 vCPU nominal, 1 CPU real (centésimas), 2 RAM (MB), 3 disco (MB).
"""
import time

DIMS = 4
DIM_NAMES = ("vCPU", "CPU real", "RAM", "disco")


class Timeout(Exception):
    pass


def vectores(d):
    return [f[:] for f in d["_cap"]], [f[:] for f in d["_uso"]], [f[:] for f in d["_dem"]]


def _check(deadline):
    if deadline is not None and time.monotonic() > deadline:
        raise Timeout()


def _bcdp_nucleo(d, k=3, pesos="cap", refinar=False, reparar=False, eliminar=False, gamma=2.0, deadline=None):
    cap, uso, dem = vectores(d); N, M = d["N"], d["M"]
    base = [fila[:] for fila in uso]
    wcap = [1.0 / (sum(c[q] for c in cap) / M) if sum(c[q] for c in cap) > 0 else 0.0 for q in range(DIMS)]
    rest = set(range(N)); asg = {}; occ = list(d["a"])

    def pesos_actuales():
        if pesos == "cap": return wcap
        libre = [sum(cap[h][q] - uso[h][q] for h in range(M)) for q in range(DIMS)]
        pend = [sum(dem[i][q] for i in rest) for q in range(DIMS)]
        return [wcap[q] * (pend[q] / libre[q] if libre[q] > 0 else 1.0) ** 0.5 for q in range(DIMS)] if any(pend) else wcap

    def vol(i, w): return sum(w[q] * dem[i][q] for q in range(DIMS))

    def pesos_refinar():
        libre = [sum(cap[h][q] - uso[h][q] for h in range(M)) for q in range(DIMS)]
        pend = [sum(dem[i][q] for i in rest) for q in range(DIMS)]
        return [wcap[q] * ((pend[q] / libre[q]) if libre[q] > 0 else 1.0) ** gamma for q in range(DIMS)]

    def cabe(u, h, v): return all(u[h][q] + v[q] <= cap[h][q] for q in range(DIMS))

    def llenar(h, pendientes, u, w, wr=None):
        puestas = []
        while True:
            _check(deadline)
            libre = [cap[h][q] - u[h][q] for q in range(DIMS)]
            mejor = None
            for i in pendientes:
                v = dem[i]
                if any(v[q] > libre[q] for q in range(DIMS)): continue
                s = sum(w[q] * w[q] * v[q] * libre[q] for q in range(DIMS))
                if mejor is None or s > mejor[0] or (s == mejor[0] and i < mejor[1]): mejor = (s, i)
            if mejor is None: break
            i = mejor[1]; pendientes.discard(i); puestas.append(i)
            for q in range(DIMS): u[h][q] += dem[i][q]
        if refinar and puestas:
            w = wr if wr is not None else w
            mejora = True; rondas = 0
            while mejora and rondas < 20:
                _check(deadline)
                mejora = False; rondas += 1
                cand = sorted(pendientes, key=lambda i: (-vol(i, w), i))[:40]
                for p in list(puestas):
                    sin_p = [u[h][q] - dem[p][q] for q in range(DIMS)]
                    vp = vol(p, w); mejor = None
                    for x, a_ in enumerate(cand):
                        if any(sin_p[q] + dem[a_][q] > cap[h][q] for q in range(DIMS)): continue
                        va = vol(a_, w)
                        if va > vp + 1e-12 and (mejor is None or va > mejor[0]): mejor = (va, (a_,))
                        con_a = [sin_p[q] + dem[a_][q] for q in range(DIMS)]
                        for b_ in cand[x + 1:]:
                            if any(con_a[q] + dem[b_][q] > cap[h][q] for q in range(DIMS)): continue
                            vab = va + vol(b_, w)
                            if vab > vp + 1e-12 and (mejor is None or vab > mejor[0]): mejor = (vab, (a_, b_))
                    if mejor:
                        puestas.remove(p); pendientes.add(p)
                        for q in range(DIMS): u[h][q] -= dem[p][q]
                        for a_ in mejor[1]:
                            puestas.append(a_); pendientes.discard(a_)
                            for q in range(DIMS): u[h][q] += dem[a_][q]
                        mejora = True; break
                if mejora:
                    while True:
                        libre = [cap[h][q] - u[h][q] for q in range(DIMS)]
                        op = [i for i in pendientes if all(dem[i][q] <= libre[q] for q in range(DIMS))]
                        if not op: break
                        i = max(op, key=lambda i: (vol(i, w), -i)); pendientes.discard(i); puestas.append(i)
                        for q in range(DIMS): u[h][q] += dem[i][q]
        return puestas

    w = pesos_actuales()
    tam = lambda h: sum(wcap[q] * (cap[h][q] - uso[h][q]) for q in range(DIMS))
    for h in sorted((h for h in range(M) if occ[h]), key=lambda h: (-tam(h), h)):
        for i in llenar(h, rest, uso, w, pesos_refinar()): asg[i] = h
    while rest:
        libres = sorted((h for h in range(M) if not occ[h]), key=lambda h: (-tam(h), h))
        if not libres: break
        w = pesos_actuales(); wr = pesos_refinar(); mejor = None
        for c in libres[:max(1, k)]:
            u2 = [fila[:] for fila in uso]; r2 = set(rest)
            puestas = llenar(c, r2, u2, w, wr)
            v = sum(vol(i, wr) for i in puestas)
            if mejor is None or v > mejor[0]: mejor = (v, c)
        h = mejor[1]; puestas = llenar(h, rest, uso, w, wr)
        if not puestas: break
        occ[h] = 1
        for i in puestas: asg[i] = h

    if rest and reparar:
        for i in sorted(rest, key=lambda i: (-vol(i, wcap), i)):
            _check(deadline)
            hecho = False
            for h in range(M):
                if cabe(uso, h, dem[i]):
                    asg[i] = h; occ[h] = 1; hecho = True
                    for q in range(DIMS): uso[h][q] += dem[i][q]
                    break
            if hecho: rest.discard(i); continue
            for h in range(M):
                for j in [j for j in asg if asg[j] == h]:
                    if any(uso[h][q] - dem[j][q] + dem[i][q] > cap[h][q] for q in range(DIMS)): continue
                    dest = [g for g in range(M) if g != h and cabe(uso, g, dem[j])]
                    if not dest: continue
                    g = min(dest, key=lambda g: (0 if occ[g] else 1, sum(wcap[q] * (cap[g][q] - uso[g][q] - dem[j][q]) for q in range(DIMS)), g))
                    for q in range(DIMS):
                        uso[h][q] += dem[i][q] - dem[j][q]; uso[g][q] += dem[j][q]
                    asg[j] = g; asg[i] = h; occ[g] = 1; hecho = True; break
                if hecho: break
            if hecho: rest.discard(i)
            else: return None
    if rest: return None

    if eliminar:
        cambiado = True
        while cambiado:
            _check(deadline)
            cambiado = False
            nuevos = sorted({h for h in asg.values() if not d["a"][h]}, key=lambda h: (sum(wcap[q] * (uso[h][q] - base[h][q]) for q in range(DIMS)), h))
            for h in nuevos:
                u2 = [fila[:] for fila in uso]; mv = {}; ok = True
                for i in sorted((i for i in asg if asg[i] == h), key=lambda i: (-vol(i, wcap), i)):
                    dest = [g for g in range(M) if g != h and (d["a"][g] or g in asg.values()) and cabe(u2, g, dem[i])]
                    if not dest: ok = False; break
                    g = min(dest, key=lambda g: (sum(wcap[q] * (cap[g][q] - u2[g][q] - dem[i][q]) for q in range(DIMS)), g))
                    mv[i] = g
                    for q in range(DIMS): u2[g][q] += dem[i][q]
                if ok and mv:
                    for q in range(DIMS): u2[h][q] = base[h][q]
                    uso[:] = u2; asg.update(mv); cambiado = True; break
    return asg


CONFIGS = [dict(k=3, gamma=2.0), dict(k=3, gamma=0.0), dict(k=5, gamma=1.0), dict(k=1, gamma=4.0)]


def bcdp_v2(d, configs=CONFIGS, deadline=None):
    """Llenado refinado + reparación + eliminación; las configuraciones siguientes son solo respaldo."""
    for c in configs:
        asg = _bcdp_nucleo(d, refinar=True, reparar=True, eliminar=True, deadline=deadline, **c)
        if asg is not None: return asg
    return None


def bfd_hld(d, deadline=None):
    """BFD del HLD, solo como referencia de comparación."""
    cap, uso, dem = vectores(d); N, M = d["N"], d["M"]; occ = list(d["a"]); asg = {}
    for i in sorted(range(N), key=lambda i: (-dem[i][1], -dem[i][0], -dem[i][2], -dem[i][3], i)):
        _check(deadline)
        mejor = None
        for h in range(M):
            nuevo = [uso[h][k] + dem[i][k] for k in range(DIMS)]
            if any(nuevo[k] > cap[h][k] for k in range(DIMS)): continue
            clave = (0 if occ[h] else 1, 0.85 - nuevo[1] / (100 * cap[h][1] / 85), (cap[h][2] - nuevo[2]) / cap[h][2], (cap[h][3] - nuevo[3]) / cap[h][3], h)
            if mejor is None or clave < mejor[0]: mejor = (clave, h)
        if mejor is None: return None
        h = mejor[1]; asg[i] = h; occ[h] = 1
        for k in range(DIMS): uso[h][k] += dem[i][k]
    return asg


def validar(d, asg):
    """(ok, Z): todas las VMs asignadas y ningún host excedido en ninguna dimensión."""
    cap, uso, dem = vectores(d)
    if asg is None or sorted(asg) != list(range(d["N"])): return False, None
    usados = set()
    for i, h in asg.items():
        if not 0 <= h < d["M"]: return False, None
        usados.add(h)
        for k in range(DIMS): uso[h][k] += dem[i][k]
    ok = all(uso[h][k] <= cap[h][k] for h in range(d["M"]) for k in range(DIMS))
    return ok, sum(1 for h in usados if not d["a"][h])
