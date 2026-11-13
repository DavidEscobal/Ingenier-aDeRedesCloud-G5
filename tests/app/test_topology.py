"""Paso 6: Topology Manager (generadores, combinación, compilación, borradores) y su paso por el gateway.

La compilación se verifica contra el validador REAL del driver OpenStack del núcleo (g5), para que lo que
produzca el editor nunca sea rechazado por el platform-manager.
"""
import os
import secrets
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from iam_support import initialize
from test_bootstrap import ROOT, request, service

sys.path.insert(0, str(ROOT))
if os.name == "nt":
    sys.path.insert(0, str(ROOT / "tools" / "winshim"))
from g5.drivers.openstack.driver import validate_spec  # noqa: E402
from g5_topology.compiler import CompileError, compile_spec  # noqa: E402
from g5_topology.generators import GENERATORS, combine, generate  # noqa: E402
from g5_topology.model import Topology  # noqa: E402
from pydantic import ValidationError  # noqa: E402

CORE_CONFIG = {"openstack": {}}
EXPECTED_SEGMENTS = {
    "lineal": lambda n: n - 1, "anillo": lambda n: n, "malla": lambda n: n * (n - 1) // 2,
    "arbol": lambda n: n - 1, "bus": lambda n: 1, "estrella": lambda n: n - 1,
}


class GeneratorTests(unittest.TestCase):
    def test_every_generator_compiles_to_a_spec_the_engine_accepts(self):
        for kind, limits in GENERATORS.items():
            for n in sorted({limits["min"], (limits["min"] + limits["max"]) // 2, limits["max"]}):
                with self.subTest(kind=kind, n=n):
                    topo = generate(kind, n)
                    self.assertEqual(len(topo.nodes), n)
                    self.assertEqual(len(topo.segments), EXPECTED_SEGMENTS[kind](n))
                    spec = compile_spec(topo, "openstack")
                    validate_spec(spec, CORE_CONFIG)  # lanza Fault si el motor lo rechazaría

    def test_semantics_bus_is_one_shared_segment_and_lineal_is_point_to_point(self):
        bus, lineal = generate("bus", 4), generate("lineal", 4)
        self.assertEqual([(s.kind, len(s.members)) for s in bus.segments], [("bus", 4)])
        self.assertTrue(all(s.kind == "link" and len(s.members) == 2 for s in lineal.segments))
        ring = generate("anillo", 4)
        self.assertEqual(ring.segments[-1].members, ["n4", "n1"])
        tree = generate("arbol", 7)
        self.assertEqual([s.members for s in tree.segments[:2]], [["n1", "n2"], ["n1", "n3"]])

    def test_addressing_is_deterministic_and_keeps_last_octet_per_node(self):
        spec = compile_spec(generate("lineal", 3), "openstack")
        self.assertEqual([n["cidr"] for n in spec["networks"]], ["192.168.1.0/24", "192.168.2.0/24"])
        self.assertFalse(any(n["cidr"].startswith("10.60.") for n in spec["networks"]), "10.60/16 es del acceso externo (D-16)")
        vm2 = next(v for v in spec["vms"] if v["name"] == "n2")
        self.assertEqual([nic["ip"] for nic in vm2["nics"]], ["192.168.1.12", "192.168.2.12"])

    def test_limits_and_invalid_documents_are_explained(self):
        with self.assertRaisesRegex(ValueError, "entre 2 y 6"):
            generate("malla", 7)
        with self.assertRaisesRegex(ValueError, "desconocida"):
            generate("hexagono", 3)
        base = generate("lineal", 2).model_dump()
        dup = dict(base, segments=base["segments"] * 2)
        with self.assertRaises(ValidationError):
            Topology.model_validate(dup)
        ghost = dict(base, segments=[{"id": "x", "kind": "link", "members": ["n1", "nada"]}])
        with self.assertRaisesRegex(ValidationError, "inexistentes"):
            Topology.model_validate(ghost)
        lonely = dict(base, segments=[])
        with self.assertRaisesRegex(CompileError, "sin ninguna conexión"):
            compile_spec(Topology.model_validate(lonely), "openstack")
        big = dict(base, nodes=[dict(base["nodes"][0], vcpus=8), base["nodes"][1]])
        with self.assertRaisesRegex(CompileError, "no disponible"):
            compile_spec(Topology.model_validate(big), "openstack")
        linux = compile_spec(generate("lineal", 2), "linux")  # neutral: el platform-manager completa Linux
        self.assertEqual(linux["provider"], "linux")
        self.assertTrue(all("worker" not in v for v in linux["vms"]))
        with self.assertRaisesRegex(CompileError, "aún no disponible"):
            compile_spec(generate("lineal", 2), "vmware")
        exam = generate("anillo", 4)
        exam.name = "Ex2_G5_test"                       # nombre del examen: mayúsculas y "_"
        self.assertEqual(compile_spec(Topology.model_validate(exam.model_dump()), "openstack", "Ex2_G5_test_2")["name"],
                         "Ex2_G5_test_2")
        for bad in ("2abc", "con espacio", "x" * 65, "a;rm", "ñandú"):
            with self.assertRaises(ValidationError):
                Topology.model_validate(dict(exam.model_dump(), name=bad))
        pinned = generate("lineal", 3)
        pinned.nodes[0].host = "server2"
        self.assertEqual(compile_spec(pinned, "linux")["vms"][0]["host"], "server2")
        self.assertNotIn("host", compile_spec(pinned, "linux")["vms"][1])
        with self.assertRaisesRegex(CompileError, "no son de openstack"):
            compile_spec(pinned, "openstack")
        l2 = generate("lineal", 3)
        l2.segments[0].addressed = False                 # enlace sin IP (VM switch del Ex2, paso 15b)
        spec = compile_spec(l2, "openstack")
        self.assertNotIn("cidr", spec["networks"][0])
        self.assertTrue(all("ip" not in nic for vm in spec["vms"] for nic in vm["nics"] if nic["network"] == l2.segments[0].id))
        self.assertIn("cidr", spec["networks"][1])
        online = generate("lineal", 2)
        online.nodes[0].internet = True
        self.assertTrue(compile_spec(online, "linux")["vms"][0]["internet"])
        self.assertNotIn("internet", compile_spec(online, "linux")["vms"][1])
        with self.assertRaisesRegex(CompileError, "solo en Linux"):
            compile_spec(online, "openstack")

    def test_combining_renames_collisions_and_links_both_parts(self):
        merged = combine(generate("anillo", 3), generate("estrella", 4), connect=("n1", "n1"))
        ids = [n.id for n in merged.nodes]
        self.assertEqual(len(ids), 7)
        self.assertEqual(len(set(ids)), 7, "sin nombres repetidos")
        self.assertEqual(merged.segments[-1].members, ["n1", "n1-2"], "enlace entre ambas partes")
        validate_spec(compile_spec(merged, "openstack"), CORE_CONFIG)


class TopologyServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = ExitStack()
        cls.addClassCleanup(cls.stack.close)
        directory = Path(cls.stack.enter_context(tempfile.TemporaryDirectory()))
        settings, password, _ = initialize(directory)
        cls.stack.enter_context(patch.dict(os.environ, settings))
        cls.iam, _ = cls.stack.enter_context(service("g5_iam.main", **settings))
        cls.tm, _ = cls.stack.enter_context(service("g5_topology.main", IAM_URL=cls.iam,
                                                    TOPOLOGY_DB_PATH=str(directory / "drafts.db")))
        cls.gw, _ = cls.stack.enter_context(service("g5_gateway.main", IAM_URL=cls.iam, TOPOLOGY_MANAGER_URL=cls.tm))
        cls.admin = cls.login("admin", password)
        cls.prof = cls.user("profa", "professor")
        cls.other = cls.user("profb", "professor")

    @classmethod
    def login(cls, username, password):
        status, data = request(cls.iam + "/v1/auth/login", "POST", body={"username": username, "password": password})
        assert status == 200, (status, data)
        return data["access_token"]

    @classmethod
    def user(cls, username, role):
        password = secrets.token_urlsafe(18)
        status, _ = request(cls.iam + "/v1/iam/users", "POST", cls.admin,
                            {"username": username, "password": password, "display_name": username, "role": role})
        assert status == 201
        return cls.login(username, password)

    def test_generate_combine_and_compile_through_gateway(self):
        status, catalog = request(self.gw + "/v1/topologies/catalog", token=self.prof)
        self.assertEqual(status, 200)
        self.assertEqual({g["id"] for g in catalog["generators"]}, set(GENERATORS))
        status, ring = request(self.gw + "/v1/topologies/generate", "POST", self.prof, {"kind": "anillo", "n": 4})
        self.assertEqual((status, len(ring["segments"])), (200, 4))
        status, tree = request(self.gw + "/v1/topologies/generate", "POST", self.prof, {"kind": "arbol", "n": 3, "prefix": "t"})
        status, merged = request(self.gw + "/v1/topologies/combine", "POST", self.prof,
                                 {"base": ring, "add": tree, "connect": ["n1", "t1"]})
        self.assertEqual((status, len(merged["nodes"])), (200, 7))
        status, spec = request(self.gw + "/v1/topologies/compile", "POST", self.prof,
                               {"topology": merged, "provider": "openstack", "name": "combinada"})
        self.assertEqual(status, 200)
        validate_spec(spec, CORE_CONFIG)

    def test_errors_are_readable_and_auth_is_required(self):
        status, body = request(self.gw + "/v1/topologies/generate", "POST", self.prof, {"kind": "malla", "n": 9})
        self.assertEqual(status, 422)
        self.assertIn("entre 2 y 6", body["detail"])
        bad = {"topology": {"name": "x", "nodes": [{"id": "a", "image": "cirros", "vcpus": 1, "memory_mb": 512, "disk_gb": 1}],
                            "segments": [{"id": "s", "kind": "link", "members": ["a", "b"]}]}}
        status, body = request(self.gw + "/v1/topologies/validate", "POST", self.prof, bad)
        self.assertEqual(status, 422)
        self.assertIn("inexistentes", body["detail"])
        self.assertEqual(request(self.gw + "/v1/topologies/catalog")[0], 401)
        self.assertEqual(request(self.gw + "/v1/drafts", token="falso")[0], 401)

    def test_drafts_are_private_versioned_and_round_trip_as_export(self):
        _, lineal = request(self.gw + "/v1/topologies/generate", "POST", self.prof, {"kind": "lineal", "n": 3, "name": "mi-lineal"})
        status, draft = request(self.gw + "/v1/drafts", "POST", self.prof, {"topology": lineal})
        self.assertEqual((status, draft["version"], draft["name"]), (201, 1, "mi-lineal"))
        did = draft["id"]
        # Exportar = el documento guardado; importarlo de nuevo produce un borrador idéntico.
        status, exported = request(self.gw + "/v1/drafts/" + did, token=self.prof)
        status, imported = request(self.gw + "/v1/drafts", "POST", self.prof, {"topology": exported["topology"]})
        self.assertEqual(imported["topology"], exported["topology"])
        # Edición con control de versión: la segunda escritura con la versión vieja da 409.
        edited = dict(exported["topology"], description="con un nodo más")
        status, v2 = request(self.gw + "/v1/drafts/" + did, "PUT", self.prof, {"topology": edited, "version": 1})
        self.assertEqual((status, v2["version"]), (200, 2))
        status, body = request(self.gw + "/v1/drafts/" + did, "PUT", self.prof, {"topology": edited, "version": 1})
        self.assertEqual(status, 409)
        self.assertIn("versión más nueva", body["detail"])
        # Privados: otro profesor no los ve ni los toca.
        self.assertNotIn(did, [d["id"] for d in request(self.gw + "/v1/drafts", token=self.other)[1]])
        self.assertEqual(request(self.gw + "/v1/drafts/" + did, token=self.other)[0], 404)
        self.assertEqual(request(self.gw + "/v1/drafts/" + did, "DELETE", self.other)[0], 404)
        self.assertEqual(request(self.gw + "/v1/drafts/" + did, "DELETE", self.prof), (200, {"status": "deleted"}))
        self.assertEqual(request(self.gw + "/v1/drafts/" + did, token=self.prof)[0], 404)


if __name__ == "__main__":
    unittest.main()
