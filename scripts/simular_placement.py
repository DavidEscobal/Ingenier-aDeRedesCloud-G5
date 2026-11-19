"""Simulador del módulo de VM Placement (R4) con datos dados a mano (p. ej., el input de los JPs).

Ejecuta el MISMO algoritmo que usa el orquestador (BCDP v2 del microservicio vm-placement), sin tocar ningún
clúster, y muestra el resultado en tablas: a qué servidor va cada VM, servidores descartados, uso antes y después,
la orden para la plataforma (Linux: worker; OpenStack: availability_zone "zona:host") o el motivo del rechazo.

Uso (desde la raíz del repositorio, en cmd o bash):
    python scripts/simular_placement.py ejemplos/placement/caso1_linux_recursos.json
    python scripts/simular_placement.py ejemplos/placement/*.json          (varios casos seguidos)
    python scripts/simular_placement.py --json caso.json                   (respuesta cruda del módulo)

Formato de entrada: ver ejemplos/placement/LEEME.md.
"""
import argparse
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "vm-placement" / "src"))
from g5_placement.planner import PLAN_FOUND, host_vectors, plan, vm_vector  # noqa: E402

# Los mismos valores por defecto que el servicio vm-placement del orquestador.
POLITICA = {"cpu_ratio": 2.0, "cpu_limit": 0.85, "max_age_s": 15, "timeout_s": 1.0}
ZONA_POR_DEFECTO = {"linux": "linux", "openstack": "nova"}
PLATAFORMAS = ("linux", "openstack")       # orden de desempate del modo automático (igual que el orquestador)


class EntradaInvalida(ValueError):
    pass


def _num(d, *claves, defecto=None, factor=1):
    """Primer valor presente entre varias claves; `factor` convierte unidades (p. ej., GB → MB)."""
    for i, k in enumerate(claves):
        if d.get(k) is not None:
            v = d[k]
            if not isinstance(v, (int, float)) or v < 0:
                raise EntradaInvalida("«%s» debe ser un número ≥ 0 (en %s)" % (k, d.get("nombre", "?")))
            return v * (factor[i] if isinstance(factor, tuple) else factor)
    if defecto is None:
        raise EntradaInvalida("falta «%s» en %s" % (claves[0], d.get("nombre", "?")))
    return defecto


def servidor(s, plataforma):
    """Servidor del archivo de entrada → host normalizado (el formato que entrega el módulo de monitoreo)."""
    if not s.get("nombre"):
        raise EntradaInvalida("cada servidor necesita «nombre»")
    uso = s.get("uso") or {}
    uso.setdefault("nombre", s["nombre"])
    vcpus_usadas = int(_num(uso, "vcpus", defecto=0))
    cpu_real = uso.get("cpu_real")
    h = {
        "id": s["nombre"], "provider": plataforma,
        "zone": s.get("zona") or ZONA_POR_DEFECTO[plataforma],
        "cpu_cores": int(_num(s, "nucleos")),
        "vcpus_max": s.get("vcpus_max"),
        "ram_mb": int(_num(s, "ram_mb", "ram_gb", factor=(1, 1024))),
        "disk_mb": int(_num(s, "disco_gb", factor=1024)),
        "vcpus_used": vcpus_usadas,
        "cpu_real_cent": None if cpu_real is None else int(round(_num(uso, "cpu_real") * 100)),
        "ram_used_mb": int(_num(uso, "ram_mb", "ram_gb", defecto=0, factor=(1, 1024))),
        "disk_used_mb": int(_num(uso, "disco_gb", defecto=0, factor=1024)),
        "occupied": bool(s.get("vms_actuales", vcpus_usadas) > 0),
        "healthy": bool(s.get("sano", True)),
        "age_s": float(s.get("datos_hace_s", 3)),
    }
    return h


def vm(v):
    if not v.get("nombre"):
        raise EntradaInvalida("cada VM necesita «nombre»")
    out = {"id": v["nombre"], "vcpus": int(_num(v, "vcpus")),
           "ram_mb": int(_num(v, "ram_mb", "ram_gb", factor=(1, 1024))),
           "disk_mb": int(_num(v, "disco_gb", factor=1024))}
    if v.get("cpu_prevista") is not None:
        out["cpu_cent"] = int(round(_num(v, "cpu_prevista") * 100))
    if v.get("servidor"):
        out["host"] = v["servidor"]
    return out


def leer(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    plataforma = data.get("plataforma", "openstack")
    if plataforma not in ("linux", "openstack", "auto"):
        raise EntradaInvalida("«plataforma» debe ser linux, openstack o auto")
    servs = data.get("servidores")
    if plataforma == "auto":
        if not isinstance(servs, dict) or not all(p in servs for p in PLATAFORMAS):
            raise EntradaInvalida("en modo auto, «servidores» debe tener las listas «linux» y «openstack»")
        hosts = {p: [servidor(s, p) for s in servs[p]] for p in PLATAFORMAS}
    else:
        if isinstance(servs, dict):
            servs = servs.get(plataforma)
        if not isinstance(servs, list) or not servs:
            raise EntradaInvalida("«servidores» debe ser una lista no vacía")
        hosts = {plataforma: [servidor(s, plataforma) for s in servs]}
    vms = [vm(v) for v in data.get("vms") or []]
    if not vms:
        raise EntradaInvalida("«vms» debe ser una lista no vacía")
    nombres = [v["id"] for v in vms]
    if len(set(nombres)) != len(nombres):
        raise EntradaInvalida("hay VMs con el mismo nombre")
    politica = dict(POLITICA, **(data.get("politica") or {}))
    return {"nombre": data.get("nombre") or Path(path).stem, "descripcion": data.get("descripcion"),
            "plataforma": plataforma, "zona": data.get("zona"), "hosts": hosts, "vms": vms, "politica": politica}


def simular(caso):
    """Devuelve {plataforma: respuesta del módulo} y la plataforma elegida (o None si ninguna tiene plan)."""
    respuestas = {p: plan({"zone": caso["zona"], "hosts": hs, "vms": caso["vms"], "policy": caso["politica"]})
                  for p, hs in caso["hosts"].items()}
    con_plan = [(r["hosts_opened"], len(r["hosts_used"]), PLATAFORMAS.index(p), p)
                for p, r in respuestas.items() if r["status"] == PLAN_FOUND]
    elegida = min(con_plan)[3] if con_plan else None
    return respuestas, elegida


# ------------------------------------------------------------------------------------------------- salida en texto
def tabla(cabecera, filas):
    filas = [[str(c) for c in f] for f in filas]
    anchos = [max(len(str(h)), *(len(f[i]) for f in filas)) if filas else len(str(h)) for i, h in enumerate(cabecera)]
    linea = "+" + "+".join("-" * (a + 2) for a in anchos) + "+"
    out = [linea, "| " + " | ".join(str(h).ljust(a) for h, a in zip(cabecera, anchos)) + " |", linea]
    out += ["| " + " | ".join(c.ljust(a) for c, a in zip(f, anchos)) + " |" for f in filas]
    out.append(linea)
    return "\n".join(out)


def gb(mb):
    return ("%.1f" % (mb / 1024)).replace(".", ",")


def cpu(cent):
    return ("%.2f" % (cent / 100)).replace(".", ",")


def pct(a, b):
    return "%d %%" % round(100 * a / b) if b else "-"


def motivo_legible(texto):
    """Pasa los números del motivo a unidades legibles (el módulo usa MB y centésimas de núcleo)."""
    conv = {"RAM": lambda x: "%s GB" % gb(x), "disco": lambda x: "%s GB" % gb(x),
            "CPU real": lambda x: "%s núcleos" % cpu(x), "vCPU": lambda x: "%d vCPU" % x}

    def rep(m):
        f = conv[m.group(1)]
        return "%s insuficiente: se piden %s y quedan %s libres" % (m.group(1), f(int(m.group(2))), f(int(m.group(3))))
    return re.sub(r"(CPU real|vCPU|RAM|disco) insuficiente: se piden (\d+) y quedan (\d+) libres", rep, texto)


def mostrar_entrada(caso, hosts, p):
    pol = caso["politica"]
    filas = []
    for h in hosts:
        cap, uso = host_vectors(h, pol)
        estado = "sano" if h["healthy"] else "CAÍDO"
        if h["age_s"] > pol["max_age_s"]:
            estado += ", datos de hace %d s" % h["age_s"]
        filas.append([h["id"], h["zone"], h["cpu_cores"], "%d/%d" % (uso[0], cap[0]), "%s/%s" % (cpu(uso[1]), cpu(cap[1])),
                      "%s/%s" % (gb(uso[2]), gb(cap[2])), "%s/%s" % (gb(uso[3]), gb(cap[3])),
                      "sí" if h["occupied"] else "no", estado])
    print("\nServidores %s (entrada):" % p.upper())
    print(tabla(["Servidor", "Zona", "Núcleos", "vCPU usadas/máx", "CPU real/límite", "RAM GB", "Disco GB",
                 "En uso", "Estado"], filas))


def mostrar_resultado(caso, p, r, hosts):
    pol = caso["politica"]
    if r["discarded_hosts"]:
        print("\nServidores descartados antes de calcular:")
        print(tabla(["Servidor", "Motivo"], [[d["host"], d["reason"]] for d in r["discarded_hosts"]]))
    if r["status"] != PLAN_FOUND:
        print("\nRESULTADO (%s): RECHAZO [%s]" % (p.upper(), r["status"]))
        print("Motivo: %s" % motivo_legible(r["reason"]))
        print("No se crea ninguna VM: el slice se rechaza completo.")
        return
    print("\nRESULTADO (%s): PLAN ENCONTRADO en %s ms (algoritmo %s)" % (p.upper(), ("%.1f" % r["elapsed_ms"]).replace(".", ",") if r["elapsed_ms"] >= 0.1 else "< 0,1", r["algorithm"]))
    fijadas = {v["id"] for v in caso["vms"] if v.get("host")}
    zona_de = {h["id"]: h["zone"] for h in hosts}
    filas = []
    for v in caso["vms"]:
        destino = r["plan"][v["id"]]
        orden = ("worker = %s" % destino if p == "linux"
                 else 'availability_zone = "%s:%s"' % (zona_de[destino], destino))
        filas.append([v["id"], destino, "fijada por el usuario" if v["id"] in fijadas else "decidida por el módulo", orden])
    print(tabla(["VM", "Servidor", "Origen", "Orden para la plataforma"], filas))

    print("\nUso de los servidores antes -> después del plan:")
    filas = []
    for h in hosts:
        if h["id"] not in r["hosts_used"]:
            continue
        cap, uso = host_vectors(h, pol)
        suma = [0, 0, 0, 0]
        for v in caso["vms"]:
            if r["plan"][v["id"]] == h["id"]:
                suma = [a + b for a, b in zip(suma, vm_vector(v))]
        des = [a + b for a, b in zip(uso, suma)]
        filas.append([h["id"], "%d -> %d de %d" % (uso[0], des[0], cap[0]),
                      "%s -> %s de %s (%s)" % (cpu(uso[1]), cpu(des[1]), cpu(cap[1]), pct(des[1], cap[1])),
                      "%s -> %s de %s (%s)" % (gb(uso[2]), gb(des[2]), gb(cap[2]), pct(des[2], cap[2])),
                      "%s -> %s de %s (%s)" % (gb(uso[3]), gb(des[3]), gb(cap[3]), pct(des[3], cap[3])),
                      "sí" if not h["occupied"] else "no"])
    print(tabla(["Servidor", "vCPU", "CPU real (núcleos, % del límite)", "RAM (GB)", "Disco (GB)", "Servidor nuevo"], filas))
    print("Servidores vacíos que se empezaron a usar: %d  |  Servidores usados: %d"
          % (r["hosts_opened"], len(r["hosts_used"])))


def mostrar(caso, respuestas, elegida):
    print("=" * 100)
    print("SIMULACIÓN DE VM PLACEMENT: %s" % caso["nombre"])
    if caso["descripcion"]:
        print(caso["descripcion"])
    pol = caso["politica"]
    print("Plataforma pedida: %s  |  Zona pedida: %s" % (caso["plataforma"], caso["zona"] or "(ninguna)"))
    print("Reglas: hasta %s vCPU por núcleo; CPU real <= %d %% de los núcleos; datos de monitoreo <= %d s; "
          "límite de cálculo %s s" % (str(pol["cpu_ratio"]).replace(".", ","), round(pol["cpu_limit"] * 100),
                                      pol["max_age_s"], str(pol["timeout_s"]).replace(".", ",")))
    print("\nVMs pedidas:")
    print(tabla(["VM", "vCPU", "CPU prevista (núcleos)", "RAM (GB)", "Disco (GB)", "Fijada en"],
                [[v["id"], v["vcpus"], cpu(v["cpu_cent"]) if "cpu_cent" in v else "%d (sin dato: se supone todo)" % v["vcpus"],
                  gb(v["ram_mb"]), gb(v["disk_mb"]), v.get("host", "-")] for v in caso["vms"]]))
    for p, r in respuestas.items():
        mostrar_entrada(caso, caso["hosts"][p], p)
        mostrar_resultado(caso, p, r, caso["hosts"][p])
    if caso["plataforma"] == "auto":
        print("\nMODO AUTOMÁTICO: comparación de plataformas")
        print(tabla(["Plataforma", "Resultado", "Servidores vacíos que ocupa", "Servidores usados"],
                    [[p, "plan" if r["status"] == PLAN_FOUND else "rechazo", r["hosts_opened"] if r["status"] == PLAN_FOUND else "-",
                      len(r["hosts_used"]) if r["status"] == PLAN_FOUND else "-"] for p, r in respuestas.items()]))
        if elegida:
            print("PLATAFORMA ELEGIDA: %s (regla: menos servidores vacíos ocupados; luego menos servidores usados; "
                  "empate: Linux)" % elegida.upper())
        else:
            print("PLATAFORMA ELEGIDA: ninguna. El slice se rechaza con el motivo de cada plataforma.")
    print()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Simula el módulo de VM Placement con un archivo de entrada JSON.")
    ap.add_argument("archivos", nargs="+", help="archivo(s) JSON de entrada (acepta comodines, p. ej. ejemplos/placement/*.json)")
    ap.add_argument("--json", action="store_true", help="imprime la respuesta cruda del módulo en JSON")
    args = ap.parse_args(argv)
    try:   # en consola Python ya escribe en Unicode; redirigido a archivo o tubería, se usa UTF-8
        if not sys.stdout.isatty():
            sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    rutas = [r for a in args.archivos for r in (sorted(glob.glob(a)) or [a])]
    codigo = 0
    for ruta in rutas:
        try:
            caso = leer(ruta)
        except (OSError, json.JSONDecodeError, EntradaInvalida) as e:
            print("ERROR en %s: %s" % (ruta, e), file=sys.stderr)
            codigo = 2
            continue
        respuestas, elegida = simular(caso)
        if args.json:
            print(json.dumps({"caso": caso["nombre"], "elegida": elegida, "respuestas": respuestas},
                             ensure_ascii=False, indent=2))
        else:
            mostrar(caso, respuestas, elegida)
    return codigo


if __name__ == "__main__":
    sys.exit(main())
