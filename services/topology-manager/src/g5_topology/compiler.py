"""Traducción de una topología a la especificación que valida y ejecuta el platform-manager.

Direccionamiento determinista: el segmento k (en orden) recibe 10.60.k.0/24 y el nodo i (orden global,
desde 1) usa la IP .(10+i) en cada segmento al que pertenece. Así un nodo conserva el mismo último octeto
en todas sus redes, lo que facilita las prácticas.
"""
from .model import Topology

PROVIDERS = ("openstack",)  # Linux: pendiente de su configuración de fase 2.


class CompileError(ValueError):
    pass


def compile_spec(topology: Topology, provider: str, name: str | None = None):
    if provider not in PROVIDERS:
        raise CompileError(f"Proveedor {provider} aún no disponible para topologías editables")
    problems = topology.check_catalog()
    isolated = [n.id for n in topology.nodes if not any(n.id in s.members for s in topology.segments)]
    if isolated:
        problems.append("Nodos sin ninguna conexión: " + ", ".join(isolated))
    if not topology.segments:
        problems.append("La topología necesita al menos un enlace o bus")
    if len(topology.segments) > 250:
        problems.append("Demasiados segmentos para el direccionamiento 10.60.k.0/24")
    if problems:
        raise CompileError("; ".join(problems))
    index = {n.id: i + 1 for i, n in enumerate(topology.nodes)}
    networks, nics = [], {n.id: [] for n in topology.nodes}
    for k, s in enumerate(topology.segments, start=1):
        networks.append({"name": s.id, "cidr": f"10.60.{k}.0/24", "dhcp": True})
        for m in s.members:
            nics[m].append({"network": s.id, "ip": f"10.60.{k}.{10 + index[m]}"})
    vms = [{"name": n.id, "image": n.image, "vcpus": n.vcpus, "memory_mb": n.memory_mb, "disk_gb": n.disk_gb,
            "nics": nics[n.id]} for n in topology.nodes]
    return {"name": name or topology.name, "provider": provider, "networks": networks, "vms": vms}
