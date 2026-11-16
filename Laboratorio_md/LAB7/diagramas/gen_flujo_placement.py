"""Genera el diagrama de flujo del módulo de VM Placement (LAB7, pregunta f) como SVG.

Uso: python Laboratorio_md/LAB7/diagramas/gen_flujo_placement.py  →  flujo_vm_placement.svg en la misma carpeta.
"""
from pathlib import Path
from xml.sax.saxutils import escape

W, H, CX = 1120, 2140, 430
FONT = "Segoe UI, Helvetica, Arial, sans-serif"
C = {  # componente: (relleno, borde)
    "slice": ("#DCEBFB", "#2F6FB0"),
    "mon": ("#DFF3E3", "#2E8B57"),
    "vp": ("#FFF1D6", "#C98A12"),
    "pm": ("#EDE3F7", "#7B4FB0"),
    "rej": ("#FBE3E3", "#C0392B"),
    "term": ("#2E4053", "#2E4053"),
    "io": ("#F4F6F7", "#566573"),
}
out = []


def text(cx, cy, lines, size=14, color="#1B2631", weight="normal"):
    lh = size * 1.25
    y0 = cy - (len(lines) - 1) * lh / 2
    for i, line in enumerate(lines):
        bold = line.startswith("**")
        line = line.strip("*")
        out.append('<text x="%.1f" y="%.1f" font-size="%d" fill="%s" font-weight="%s" text-anchor="middle" '
                   'dominant-baseline="middle">%s</text>' % (cx, y0 + i * lh, size, color,
                                                              "bold" if bold else weight, escape(line)))


def box(cx, cy, w, h, kind, lines, size=14):
    fill, stroke = C[kind]
    out.append('<rect x="%.1f" y="%.1f" width="%d" height="%d" rx="6" fill="%s" stroke="%s" stroke-width="2"/>'
               % (cx - w / 2, cy - h / 2, w, h, fill, stroke))
    text(cx, cy, lines, size)


def term(cx, cy, w, h, kind, lines):
    fill, stroke = C[kind]
    out.append('<rect x="%.1f" y="%.1f" width="%d" height="%d" rx="%d" fill="%s" stroke="%s" stroke-width="2"/>'
               % (cx - w / 2, cy - h / 2, w, h, h / 2, fill, stroke))
    text(cx, cy, lines, 14, "#FFFFFF" if kind == "term" else "#1B2631", "bold")


def io(cx, cy, w, h, lines):
    fill, stroke = C["io"]
    s = 18
    pts = [(cx - w / 2 + s, cy - h / 2), (cx + w / 2 + s, cy - h / 2), (cx + w / 2 - s, cy + h / 2),
           (cx - w / 2 - s, cy + h / 2)]
    out.append('<polygon points="%s" fill="%s" stroke="%s" stroke-width="2"/>'
               % (" ".join("%.1f,%.1f" % p for p in pts), fill, stroke))
    text(cx, cy, lines)


def diamond(cx, cy, w, h, kind, lines):
    stroke = C[kind][1]
    pts = [(cx, cy - h / 2), (cx + w / 2, cy), (cx, cy + h / 2), (cx - w / 2, cy)]
    out.append('<polygon points="%s" fill="#FFFFFF" stroke="%s" stroke-width="2"/>'
               % (" ".join("%.1f,%.1f" % p for p in pts), stroke))
    text(cx, cy, lines, 13)


def connector(cx, cy, label):
    out.append('<circle cx="%d" cy="%d" r="18" fill="#FFFFFF" stroke="#2E4053" stroke-width="2"/>' % (cx, cy))
    text(cx, cy, ["**" + label], 15)


def arrow(points, label=None, at=None, anchor="start", head=True):
    out.append('<polyline points="%s" fill="none" stroke="#34495E" stroke-width="1.8"%s/>'
               % (" ".join("%d,%d" % p for p in points), ' marker-end="url(#ah)"' if head else ""))
    if label:
        x, y = at
        out.append('<text x="%d" y="%d" font-size="13" font-weight="bold" fill="#34495E" text-anchor="%s">%s</text>'
                   % (x, y, anchor, escape(label)))


def note(x, y, w, h, lines):
    out.append('<rect x="%d" y="%d" width="%d" height="%d" rx="4" fill="#FEF9E7" stroke="#B7950B" '
               'stroke-width="1.5" stroke-dasharray="6 4"/>' % (x, y, w, h))
    lh = 13 * 1.3
    for i, line in enumerate(lines):
        bold = line.startswith("**")
        out.append('<text x="%d" y="%.1f" font-size="13" fill="#1B2631" font-weight="%s">%s</text>'
                   % (x + 12, y + 22 + i * lh, "bold" if bold else "normal", escape(line.strip("*"))))


# ---------------------------------------------------------------- título y leyenda
text(W / 2, 30, ["**Diagrama de flujo del módulo de VM Placement (orquestador G5)"], 20)
lx, ly = 700, 70
out.append('<rect x="%d" y="%d" width="370" height="225" rx="6" fill="#FFFFFF" stroke="#AAB7B8"/>' % (lx, ly))
out.append('<text x="%d" y="%d" font-size="14" font-weight="bold" fill="#1B2631">Leyenda</text>' % (lx + 14, ly + 24))
items = [("slice", "Slice Manager"), ("mon", "Monitoreo"), ("vp", "VM Placement"),
         ("pm", "Platform-manager (reserva y despliegue)"), ("rej", "Rechazo (se informa al usuario)")]
for i, (k, name) in enumerate(items):
    y = ly + 40 + i * 25
    out.append('<rect x="%d" y="%d" width="26" height="16" rx="3" fill="%s" stroke="%s" stroke-width="1.5"/>'
               % (lx + 14, y, C[k][0], C[k][1]))
    out.append('<text x="%d" y="%d" font-size="13" fill="#1B2631">%s</text>' % (lx + 50, y + 13, name))
y = ly + 40 + 5 * 25
out.append('<polygon points="%d,%d %d,%d %d,%d %d,%d" fill="#FFFFFF" stroke="#34495E" stroke-width="1.5"/>'
           % (lx + 27, y, lx + 40, y + 9, lx + 27, y + 18, lx + 14, y + 9))
out.append('<text x="%d" y="%d" font-size="13" fill="#1B2631">Decisión</text>' % (lx + 50, y + 14))
out.append('<circle cx="%d" cy="%d" r="9" fill="#FFFFFF" stroke="#2E4053" stroke-width="1.5"/>' % (lx + 200, y + 9))
out.append('<text x="%d" y="%d" font-size="13" fill="#1B2631">Conector</text>' % (lx + 216, y + 14))

# ---------------------------------------------------------------- flujo principal
term(CX, 80, 200, 44, "term", ["INICIO"])
arrow([(CX, 102), (CX, 128)])
io(CX, 160, 380, 60, ["Solicitud de slice: VMs (vCPU, RAM, disco),", "plataforma (Linux, OpenStack o automático) y zona"])
arrow([(CX, 190), (CX, 218)])
diamond(CX, 270, 300, 104, "slice", ["¿Todas las VMs ya tienen", "servidor asignado?"])
arrow([(CX - 150, 270), (168, 270)], "Sí", (CX - 175, 262), "end")
connector(150, 270, "A")
arrow([(CX, 322), (CX, 352)], "No", (CX + 8, 342))
box(CX, 380, 360, 54, "slice", ["Bloquear la plataforma", "(se planifica una solicitud a la vez)"])
arrow([(CX, 407), (CX, 437)])
box(CX, 470, 360, 64, "mon", ["Obtener el estado de los servidores", "(capacidad, uso, salud, zona) y los planes", "admitidos en los últimos 90 s"], 13)
arrow([(CX, 502), (CX, 532)])
box(CX, 565, 360, 64, "vp", ["Filtrar servidores candidatos:", "de la zona pedida, sanos y con datos", "de hace 15 s o menos"], 13)
arrow([(CX, 597), (CX, 625)])
diamond(CX, 675, 300, 100, "vp", ["¿Queda algún", "servidor candidato?"])
arrow([(CX, 725), (CX, 755)], "Sí", (CX + 8, 745))
box(CX, 782, 360, 54, "vp", ["Ubicar primero las VMs que el", "usuario fijó en un servidor"])
arrow([(CX, 809), (CX, 837)])
diamond(CX, 887, 300, 100, "vp", ["¿Las VMs fijadas", "caben en su servidor?"])
arrow([(CX, 937), (CX, 967)], "Sí", (CX + 8, 957))
box(CX, 1000, 380, 66, "vp", ["**Ejecutar BCDP v2 con el slice completo", "(llenar primero servidores ya en uso; abrir el", "menor número de servidores vacíos; límite 1 s)"], 13)
arrow([(CX, 1033), (CX, 1061)])
diamond(CX, 1111, 300, 100, "vp", ["¿Se encontró un plan", "dentro del tiempo?"])
arrow([(CX, 1161), (CX, 1191)], "Sí", (CX + 8, 1181))
box(CX, 1218, 360, 54, "vp", ["Revisar el plan con un verificador", "independiente (capacidades y asignaciones)"], 13)
arrow([(CX, 1245), (CX, 1273)])
diamond(CX, 1323, 300, 100, "vp", ["¿El plan es válido?"])
arrow([(CX, 1373), (CX, 1401)], "Sí", (CX + 8, 1393))
diamond(CX, 1451, 260, 100, "vp", ["¿Plataforma", "del slice?"])
arrow([(CX - 130, 1451), (250, 1451), (250, 1507)], "Linux", (CX - 140, 1443), "end")
arrow([(CX + 130, 1451), (610, 1451), (610, 1507)], "OpenStack", (CX + 140, 1443))
box(250, 1540, 240, 66, "vp", ["**Decisión para Linux", "worker = servidor del plan"], 13)
box(610, 1540, 260, 66, "vp", ["**Decisión para OpenStack", "availability_zone = «zona:host»"], 13)
arrow([(250, 1573), (250, 1600), (CX, 1600)], head=False)
arrow([(610, 1573), (610, 1600), (CX, 1600), (CX, 1628)])
connector(150, 1660, "A")
arrow([(168, 1660), (248, 1660)])
box(CX, 1660, 360, 64, "pm", ["Reservar los recursos de forma atómica", "(si otra solicitud ocupó el espacio,", "la reserva falla)"], 13)
arrow([(CX, 1692), (CX, 1720)])
diamond(CX, 1772, 300, 104, "slice", ["¿Reserva", "aceptada?"])
arrow([(CX - 150, 1772), (90, 1772), (90, 470), (248, 470)])
out.append('<text x="100" y="1796" font-size="13" font-weight="bold" fill="#34495E">No, por capacidad</text>')
out.append('<text x="100" y="1812" font-size="13" font-weight="bold" fill="#34495E">(intento &lt; 3): replanificar</text>')
arrow([(CX, 1824), (CX, 1854)], "Sí", (CX + 8, 1844))
box(CX, 1888, 380, 64, "pm", ["Registrar el plan (90 s) y desplegar las VMs", "con el driver de la plataforma"], 13)
arrow([(CX, 1920), (CX, 1950)])
term(CX, 1985, 420, 66, "term", ["FIN: slice desplegado,", "cada VM en el servidor indicado por el plan"])

# ---------------------------------------------------------------- rechazos
RX, BUS = 870, 1060
rejections = [
    (675, "No", ["**Rechazo", "no hay servidores candidatos", "en la zona pedida"]),
    (887, "No", ["**Rechazo", "la VM fijada no cabe", "(se indica el recurso: CPU, RAM o disco)"]),
    (1111, "No", ["**Rechazo", "sin plan o tiempo agotado", "(se indica el recurso más escaso)"]),
    (1323, "No", ["**Rechazo", "plan inválido (error interno);", "no se despliega nada"]),
    (1772, "No", ["**Rechazo", "la plataforma no aceptó la reserva", "(otro motivo o 3 intentos fallidos)"]),
]
for y, label, lines in rejections:
    arrow([(CX + 150, y), (RX - 120, y)], label, (CX + 160, y - 8))
    box(RX, y, 240, 70, "rej", lines, 13)
    arrow([(RX + 120, y), (BUS, y)], head=False)
arrow([(BUS, 675), (BUS, 2085), (RX + 150, 2085)])
term(RX, 2085, 300, 60, "rej", ["FIN: el usuario recibe el motivo", "(no queda ningún recurso creado)"])

# ---------------------------------------------------------------- nota del modo automático
note(690, 345, 400, 152, ["**Modo automático (plataforma «auto»)",
                          "Los pasos desde «Obtener el estado» hasta",
                          "«Revisar el plan» se hacen para Linux y para",
                          "OpenStack. Se elige el plan que abre menos",
                          "servidores vacíos (empate: Linux). Si la",
                          "plataforma elegida rechaza la solicitud, se",
                          "despliega en la otra."])
out.append('<line x1="612" y1="470" x2="688" y2="440" stroke="#B7950B" stroke-width="1.5" stroke-dasharray="6 4"/>')

svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" font-family="%s">\n'
       '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" '
       'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#34495E"/></marker></defs>\n'
       '<rect width="100%%" height="100%%" fill="#FFFFFF"/>\n%s\n</svg>\n') % (W, H, W, H, FONT, "\n".join(out))
Path(__file__).with_name("flujo_vm_placement.svg").write_text(svg, encoding="utf-8")
print("ok", len(out))
