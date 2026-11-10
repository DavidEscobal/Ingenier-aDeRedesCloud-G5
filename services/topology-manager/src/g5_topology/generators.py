"""Topologías predefinidas para N nodos y combinación de topologías.

Cada generador devuelve un `Topology` con posiciones para el lienzo. Semántica:
- lineal: cadena de enlaces punto a punto n1–n2–…–nN.
- anillo: lineal + enlace nN–n1.
- malla: malla completa, un enlace por cada par de nodos (N(N-1)/2).
- arbol: árbol binario por niveles (padre de i es (i-1)//2).
- bus: un único segmento L2 compartido por todos los nodos.
- estrella: un nodo central con un enlace a cada periférico.
"""
import math

from .model import Node, Position, Segment, Topology, sizes

GENERATORS = {
    "lineal": {"label": "Lineal", "min": 2, "max": 16},
    "anillo": {"label": "Anillo", "min": 3, "max": 16},
    "malla": {"label": "Malla (completa)", "min": 2, "max": 6},
    "arbol": {"label": "Árbol", "min": 2, "max": 15},
    "bus": {"label": "Bus", "min": 2, "max": 16},
    "estrella": {"label": "Estrella", "min": 3, "max": 9},
}


def _nodes(n, prefix, image, size, coords):
    s = next(x for x in sizes() if x["id"] == size)
    return [Node(id=f"{prefix}{i + 1}", image=image, vcpus=s["vcpus"], memory_mb=s["memory_mb"],
                 disk_gb=s["disk_gb"], position=Position(x=round(x), y=round(y)))
            for i, (x, y) in enumerate(coords)]


def _link(a, b):
    return Segment(id=f"{a}-{b}", kind="link", members=[a, b])


def generate(kind, n, name=None, prefix="n", image="cirros", size="small"):
    if kind not in GENERATORS:
        raise ValueError(f"Topología desconocida: {kind}")
    low, high = GENERATORS[kind]["min"], GENERATORS[kind]["max"]
    if not low <= n <= high:
        raise ValueError(f"{GENERATORS[kind]['label']}: entre {low} y {high} nodos")
    ids = [f"{prefix}{i + 1}" for i in range(n)]
    segments = []
    if kind in ("lineal", "anillo"):
        if kind == "lineal":
            coords = [(80 + i * 180, 200) for i in range(n)]
        else:
            r = 70 + 28 * n
            coords = [(r + 80 + r * math.cos(2 * math.pi * i / n - math.pi / 2),
                       r + 60 + r * math.sin(2 * math.pi * i / n - math.pi / 2)) for i in range(n)]
        segments = [_link(ids[i], ids[i + 1]) for i in range(n - 1)]
        if kind == "anillo":
            segments.append(_link(ids[-1], ids[0]))
    elif kind == "malla":
        r = 80 + 30 * n
        coords = [(r + 80 + r * math.cos(2 * math.pi * i / n - math.pi / 2),
                   r + 60 + r * math.sin(2 * math.pi * i / n - math.pi / 2)) for i in range(n)]
        segments = [_link(ids[i], ids[j]) for i in range(n) for j in range(i + 1, n)]
    elif kind == "arbol":
        coords = []
        for i in range(n):
            level = int(math.log2(i + 1))
            pos, width = i + 1 - 2 ** level, 2 ** level
            coords.append((80 + (pos + 0.5) * (900 / width), 60 + level * 150))
        segments = [_link(ids[(i - 1) // 2], ids[i]) for i in range(1, n)]
    elif kind == "bus":
        coords = [(80 + i * 160, 300) for i in range(n)]
        segments = [Segment(id=f"{prefix}bus", kind="bus", members=ids,
                            position=Position(x=80 + (n - 1) * 80, y=120))]
    else:  # estrella
        r = 220
        coords = [(r + 120, r + 80)] + [
            (r + 120 + r * math.cos(2 * math.pi * i / (n - 1)), r + 80 + r * math.sin(2 * math.pi * i / (n - 1)))
            for i in range(n - 1)]
        segments = [_link(ids[0], ids[i]) for i in range(1, n)]
    return Topology(name=name or f"{kind}-{n}", nodes=_nodes(n, prefix, image, size, coords), segments=segments)


def _free(base, wanted):
    if wanted not in base:
        return wanted
    i = 2
    while f"{wanted}-{i}" in base:
        i += 1
    return f"{wanted}-{i}"


def combine(base, add, connect=None, offset=None):
    """Agrega `add` a `base`: renombra lo que choque, desplaza posiciones y opcionalmente enlaza dos nodos."""
    used = {n.id for n in base.nodes} | {s.id for s in base.segments}
    rename = {}
    for n in add.nodes:
        rename[n.id] = _free(used, n.id)
        used.add(rename[n.id])
    max_x = max((n.position.x for n in base.nodes if n.position), default=0)
    dx = offset if offset is not None else max_x + 220
    nodes = list(base.nodes)
    for n in add.nodes:
        p = Position(x=n.position.x + dx, y=n.position.y) if n.position else None
        nodes.append(n.model_copy(update={"id": rename[n.id], "position": p}))
    segments = list(base.segments)
    for s in add.segments:
        members = [rename[m] for m in s.members]
        sid = _free(used, "-".join(members) if s.kind == "link" else s.id)
        used.add(sid)
        p = Position(x=s.position.x + dx, y=s.position.y) if s.position else None
        segments.append(Segment(id=sid, kind=s.kind, members=members, position=p))
    if connect:
        a, b = connect[0], rename.get(connect[1], connect[1])
        segments.append(Segment(id=_free(used, f"{a}-{b}"), kind="link", members=[a, b]))
    return Topology(name=base.name, description=base.description, nodes=nodes, segments=segments)
