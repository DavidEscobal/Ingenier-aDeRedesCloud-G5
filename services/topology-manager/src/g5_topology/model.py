"""Documento de topología (schema_version 1), independiente del proveedor.

- `nodes`: VMs con su tamaño y posición en el lienzo.
- `segments`: dominios L2. `link` une exactamente 2 nodos (punto a punto); `bus` une 2..N nodos en un mismo
  segmento compartido. Así "lineal" (cadena de enlaces) y "bus" (un solo segmento) no se confunden.
"""
import os
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Ident = str
IDENT = r"^[a-z][a-z0-9-]{0,31}$"   # nodos y segmentos (nombres de interfaces y recursos)
NAME = r"^[A-Za-z][A-Za-z0-9_-]{0,63}$"  # nombre visible de la topología/slice (Ex2_G5_test)
IMAGE_RE = __import__("re").compile(r"[a-z0-9][a-z0-9._-]{0,62}")
MAX_NODES = 16
MAX_SEGMENTS = 48
MAX_NICS = 8

# Tamaños = flavors existentes en Nova (el driver no crea flavors; D-11). Configurable por variable de entorno.
# Opción A (2026-11-13): tamaños predefinidos; cada uno necesita su flavor público en Nova (los nuevos se crean
# con autorización, como g5-1c-512m-1g). Linux acepta cualquiera que quepa en el worker.
DEFAULT_SIZES = [
    {"id": "small", "label": "Pequeña · 1 vCPU · 512 MB · 1 GB", "vcpus": 1, "memory_mb": 512, "disk_gb": 1},
    {"id": "standard", "label": "Estándar · 1 vCPU · 512 MB · 4 GB", "vcpus": 1, "memory_mb": 512, "disk_gb": 4},
    {"id": "medium", "label": "Mediana · 1 vCPU · 1 GB · 2 GB", "vcpus": 1, "memory_mb": 1024, "disk_gb": 2},
    {"id": "large", "label": "Grande · 2 vCPU · 1 GB · 2 GB", "vcpus": 2, "memory_mb": 1024, "disk_gb": 2},
    {"id": "xlarge", "label": "Extra grande · 2 vCPU · 2 GB · 4 GB", "vcpus": 2, "memory_mb": 2048, "disk_gb": 4},
]
DEFAULT_IMAGES = ["cirros"]


# Servidores que se pueden elegir a mano por proveedor (el platform-manager vuelve a validar). Configurable.
DEFAULT_HOSTS = {"linux": ["server1", "server2", "server3"], "openstack": ["worker1", "worker2", "worker3"]}


def hosts():
    return json.loads(os.environ["TOPOLOGY_HOSTS"]) if os.getenv("TOPOLOGY_HOSTS") else DEFAULT_HOSTS


def sizes():
    return json.loads(os.environ["TOPOLOGY_SIZES"]) if os.getenv("TOPOLOGY_SIZES") else DEFAULT_SIZES


def images():
    return json.loads(os.environ["TOPOLOGY_IMAGES"]) if os.getenv("TOPOLOGY_IMAGES") else DEFAULT_IMAGES


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Position(Model):
    x: float = Field(ge=-100000, le=100000)
    y: float = Field(ge=-100000, le=100000)


class Node(Model):
    id: Ident = Field(pattern=IDENT)
    image: str = Field(min_length=1, max_length=64)
    vcpus: int = Field(ge=1, le=64)
    memory_mb: int = Field(ge=64, le=524288)
    disk_gb: int = Field(ge=1, le=2048)
    internet: bool = False  # salida a Internet por la puerta del slice (Linux; OpenStack pendiente de R5)
    host: str | None = Field(default=None, pattern=IDENT)  # servidor fijo (Ex2 paso 3); None = automático
    position: Position | None = None


class Segment(Model):
    id: Ident = Field(pattern=IDENT)
    kind: Literal["link", "bus"]
    members: list[Ident] = Field(min_length=2, max_length=MAX_NODES)
    addressed: bool = True  # False = enlace sin IP (p. ej. puertos de una VM que hará de switch, Ex2 paso 15b)
    position: Position | None = None  # solo para dibujar el bus en el lienzo


class Topology(Model):
    schema_version: Literal[1] = 1
    name: str = Field(pattern=NAME)
    description: str = Field(default="", max_length=300)
    nodes: list[Node] = Field(min_length=1, max_length=MAX_NODES)
    segments: list[Segment] = Field(default_factory=list, max_length=MAX_SEGMENTS)

    @model_validator(mode="after")
    def coherent(self):
        ids = [n.id for n in self.nodes]
        if len(set(ids)) != len(ids):
            raise ValueError("Nombres de nodo repetidos")
        seg_ids = [s.id for s in self.segments]
        if len(set(seg_ids)) != len(seg_ids):
            raise ValueError("Nombres de segmento repetidos")
        if set(ids) & set(seg_ids):
            raise ValueError("Un nodo y un segmento no pueden llamarse igual")
        known, pairs = set(ids), set()
        degree = {i: 0 for i in ids}
        for s in self.segments:
            if len(set(s.members)) != len(s.members):
                raise ValueError(f"Segmento {s.id}: miembro repetido")
            missing = [m for m in s.members if m not in known]
            if missing:
                raise ValueError(f"Segmento {s.id}: nodos inexistentes {missing}")
            if s.kind == "link":
                if len(s.members) != 2:
                    raise ValueError(f"Enlace {s.id}: debe unir exactamente 2 nodos")
                pair = frozenset(s.members)
                if pair in pairs:
                    raise ValueError(f"Enlace duplicado entre {' y '.join(sorted(pair))}")
                pairs.add(pair)
            for m in s.members:
                degree[m] += 1
        over = [n for n, d in degree.items() if d > MAX_NICS]
        if over:
            raise ValueError(f"Nodos con más de {MAX_NICS} interfaces: {over}")
        return self

    def check_catalog(self):
        """Tamaños e imágenes deben existir en el catálogo (flavors/imágenes reales)."""
        allowed = {(s["vcpus"], s["memory_mb"], s["disk_gb"]) for s in sizes()}
        problems = []
        for n in self.nodes:
            if (n.vcpus, n.memory_mb, n.disk_gb) not in allowed:
                problems.append(f"{n.id}: tamaño {n.vcpus} vCPU/{n.memory_mb} MB/{n.disk_gb} GB no disponible")
            # La existencia real de la imagen la verifica el platform-manager (preflight en Glance) al desplegar;
            # el catálogo de imágenes vive en el image-catalog (D-15).
            if not IMAGE_RE.fullmatch(n.image):
                problems.append(f"{n.id}: nombre de imagen inválido")
        return problems
