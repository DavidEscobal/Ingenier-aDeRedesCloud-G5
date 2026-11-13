"""Traducción de una topología a la especificación que valida y ejecuta el platform-manager.

Direccionamiento determinista (D-16): el segmento k (en orden) recibe 192.168.k.0/24 y el nodo i (orden global,
desde 1) usa la IP .(10+i) en cada segmento al que pertenece. Así un nodo conserva el mismo último octeto
en todas sus redes, lo que facilita las prácticas. No se usa 10.60.0.0/16: el laboratorio lo reserva para el
acceso externo de los grupos (G5: 10.60.9.0/24 Linux, 10.60.10.0/24 OpenStack). k <= 200 deja fuera las redes
de gestión 192.168.201.0/24 y 192.168.202.0/24.
"""
from .model import Topology, hosts

MAX_SEGMENTS = 200
PROVIDERS = ("openstack", "linux")  # Linux: el platform-manager completa workers, C-VLAN e imagen.


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
    if len(topology.segments) > MAX_SEGMENTS:
        problems.append(f"Demasiados segmentos (máximo {MAX_SEGMENTS}, direccionamiento 192.168.k.0/24)")
    wrong = [f"{n.id}→{n.host}" for n in topology.nodes if n.host and n.host not in hosts().get(provider, [])]
    if wrong:
        problems.append(f"Servidores que no son de {provider}: " + ", ".join(wrong))
    if provider != "linux" and any(n.internet for n in topology.nodes):
        problems.append("Salida a Internet desde el editor: por ahora solo en Linux (OpenStack, pendiente de R5)")
    if problems:
        raise CompileError("; ".join(problems))
    index = {n.id: i + 1 for i, n in enumerate(topology.nodes)}
    networks, nics = [], {n.id: [] for n in topology.nodes}
    for k, s in enumerate(topology.segments, start=1):
        if not s.addressed:  # enlace L2 sin direccionamiento: interfaces conectadas pero sin IP
            networks.append({"name": s.id, "dhcp": False})
            for m in s.members:
                nics[m].append({"network": s.id})
            continue
        networks.append({"name": s.id, "cidr": f"192.168.{k}.0/24", "dhcp": True})
        for m in s.members:
            nics[m].append({"network": s.id, "ip": f"192.168.{k}.{10 + index[m]}"})
    vms = [{"name": n.id, "image": n.image, "vcpus": n.vcpus, "memory_mb": n.memory_mb, "disk_gb": n.disk_gb,
            "nics": nics[n.id], **({"internet": True} if n.internet else {}), **({"host": n.host} if n.host else {})}
           for n in topology.nodes]
    return {"name": name or topology.name, "provider": provider, "networks": networks, "vms": vms}
