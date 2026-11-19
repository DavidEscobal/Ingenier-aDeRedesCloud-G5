"""Simulador del VM Placement (scripts/simular_placement.py): los 4 casos de ejemplo dan la decisión esperada."""
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("simular_placement", ROOT / "scripts" / "simular_placement.py")
sim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sim)
EJ = ROOT / "ejemplos" / "placement"


def correr(nombre):
    caso = sim.leer(EJ / nombre)
    respuestas, elegida = sim.simular(caso)
    return caso, respuestas, elegida


class SimuladorPlacement(unittest.TestCase):
    def test_caso1_linux_evita_el_servidor_sin_ram(self):
        _, r, elegida = correr("caso1_linux_recursos.json")
        self.assertEqual(elegida, "linux")
        self.assertEqual(r["linux"]["status"], "PLAN_FOUND")
        self.assertNotIn("server1", r["linux"]["plan"].values())

    def test_caso2_openstack_respeta_la_zona(self):
        _, r, _ = correr("caso2_openstack_zona.json")
        os_ = r["openstack"]
        self.assertEqual(os_["status"], "PLAN_FOUND")
        self.assertTrue(set(os_["plan"].values()) <= {"worker1", "worker2"})
        self.assertEqual({d["host"] for d in os_["discarded_hosts"]}, {"worker3", "worker4"})

    def test_caso3_rechaza_por_disco(self):
        _, r, elegida = correr("caso3_sin_recursos.json")
        self.assertIsNone(elegida)
        self.assertEqual(r["openstack"]["status"], "HEURISTIC_NO_PLAN")
        self.assertEqual(sim.motivo_legible(r["openstack"]["reason"]),
                         "disco insuficiente: se piden 28,0 GB y quedan 27,0 GB libres")

    def test_caso4_auto_elige_la_plataforma_que_no_abre_servidores(self):
        _, r, elegida = correr("caso4_modo_automatico.json")
        self.assertEqual((r["linux"]["hosts_opened"], r["openstack"]["hosts_opened"]), (1, 0))
        self.assertEqual(elegida, "openstack")

    def test_salida_en_texto_muestra_la_orden_para_openstack(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(sim.main([str(EJ / "caso2_openstack_zona.json")]), 0)
        self.assertIn('availability_zone = "zona-a:worker', out.getvalue())

    def test_entrada_invalida_se_explica(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "malo.json"
            p.write_text(json.dumps({"plataforma": "auto", "servidores": [], "vms": []}), encoding="utf-8")
            with self.assertRaises(sim.EntradaInvalida):
                sim.leer(p)


if __name__ == "__main__":
    unittest.main()
