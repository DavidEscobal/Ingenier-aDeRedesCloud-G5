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
IDENT = r"^[a-z][a-z0-9-]{0,31}$"
MAX_NODES = 16
MAX_SEGMENTS = 48
MAX_NICS = 8

# Tamaños = flavors existentes en Nova (el driver no crea flavors; D-11). Configurable por variable de entorno.
DEFAULT_SIZES = [
    {"id": "small", "label": "1 vCPU · 512 MB · 1 GB", "vcpus": 1, "memory_mb": 512, "disk_gb": 1},
    {"id": "standard", "label": "1 vCPU · 512 MB · 4 GB", "vcpus": 1, "memory_mb": 512, "disk_gb": 4},
]
DEFAULT_IMAGES = ["cirros"]


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
    position: Position | None = None


class Segment(Model):
    id: Ident = Field(pattern=IDENT)
    kind: Literal["link", "bus"]
    members: list[Ident] = Field(min_length=2, max_length=MAX_NODES)
    position: Position | None = None  # solo para dibujar el bus en el lienzo


class Topology(Model):
    schema_version: Literal[1] = 1
    name: Ident = Field(pattern=IDENT)
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
            if n.image not in images():
                problems.append(f"{n.id}: imagen {n.image} no disponible")
        return problems
