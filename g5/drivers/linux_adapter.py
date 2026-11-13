"""Adaptador de una especificación neutral (la que compila el topology-manager) al driver Linux.

El editor de topologías no conoce detalles del clúster Linux; aquí se completan:
- C-VLAN por red (100 + k, única dentro del slice; la S-VLAN del slice la reserva el driver).
- Worker por VM: reparto rotativo PROVISIONAL entre los workers habilitados, hasta que el grupo
  decida la heurística de placement (D-07). Se reemplazará por el módulo de placement.
- Imagen: nombre del catálogo -> SHA-256 de la copia local (la materializa `resolve_image`).
- SO invitado: por ahora solo CirrOS (configuración por consola serie). Ubuntu necesita usuario,
  hash de contraseña y llaves SSH que el editor todavía no pide.
- Sin DHCP: las IPs que asigna el compilador se fijan dentro del invitado.
"""
import copy
from ..model import Fault


def needs_adapter(spec):
    return (isinstance(spec, dict) and spec.get('provider') == 'linux' and isinstance(spec.get('vms'), list)
            and any(isinstance(v, dict) and 'worker' not in v for v in spec['vms']))


def adapt(spec, workers, resolve_image):
    """`workers`: nombres de workers habilitados (orden estable). `resolve_image(nombre) -> sha256`."""
    spec = copy.deepcopy(spec)
    if not workers:
        raise Fault('No hay workers Linux habilitados', 409)
    networks = spec.get('networks') or []
    if len(networks) > 64:
        raise Fault('Linux admite hasta 64 redes por slice')
    for k, net in enumerate(networks):
        if not isinstance(net, dict):
            raise Fault('Red inválida')
        net['cvid'] = 100 + k
        net['dhcp'] = False
    images = {}
    for i, vm in enumerate(spec['vms']):
        if not isinstance(vm, dict) or not isinstance(vm.get('image'), str):
            raise Fault('VM sin imagen')
        name = vm['image']
        if 'cirros' not in name:
            raise Fault('Linux de fase 2: por ahora solo imágenes CirrOS (%s)' % name, 409)
        if name not in images:
            images[name] = resolve_image(name)
        vm['image'] = images[name]
        vm['worker'] = workers[i % len(workers)]
        vm['guest'] = {'os': 'cirros'}
        vm.setdefault('internet', False)
        for j, nic in enumerate(vm.get('nics') or []):
            if isinstance(nic, dict):
                nic.setdefault('name', 'eth%d' % j)
    spec.setdefault('publications', [])
    return spec
