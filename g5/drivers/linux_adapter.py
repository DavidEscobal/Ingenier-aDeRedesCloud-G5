"""Adaptador de una especificación neutral (la que compila el topology-manager) al driver Linux.

El editor de topologías no conoce detalles del clúster Linux; aquí se completan:
- C-VLAN por red (100 + k, única dentro del slice; la S-VLAN del slice la reserva el driver).
- Worker por VM: el elegido en el editor (`host`) o, si no hay, reparto rotativo PROVISIONAL entre los workers
  habilitados hasta que el grupo decida la heurística de placement (D-07).
- Imagen: nombre del catálogo -> SHA-256 de la copia local (la materializa `resolve_image`).
- SO invitado: por ahora solo CirrOS (configuración por consola serie). Ubuntu necesita usuario,
  hash de contraseña y llaves SSH que el editor todavía no pide.
- Sin DHCP: las IPs que asigna el compilador se fijan dentro del invitado.
- Internet: cada VM con `internet: true` recibe una red de acceso propia (10.200.i.0/27, NIC `inet0`, primera)
  hacia la puerta del slice (.1 en server4, NAT y firewall). Como en EX1, el acceso va separado de los enlaces
  del laboratorio para no unir VMs que el dibujo no une; la ruta por defecto sale solo por esa NIC.
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
    networks = spec.setdefault('networks', [])
    for i, vm in enumerate(spec['vms']):
        if isinstance(vm, dict) and vm.get('internet') is True:
            access = 'inet%d' % (i + 1)  # nombre corto: el de la VM puede tener hasta 32 caracteres
            networks.append({'name': access, 'cidr': '10.200.%d.0/27' % (i + 1)})
            vm['nics'] = [{'name': 'inet0', 'network': access, 'ip': '10.200.%d.10' % (i + 1)}] + list(vm.get('nics') or [])
    if len(networks) > 64:
        raise Fault('Linux admite hasta 64 redes por slice (incluidas las de acceso a Internet)')
    for k, net in enumerate(networks):
        if not isinstance(net, dict):
            raise Fault('Red inválida')
        net['cvid'] = 100 + k
        net['dhcp'] = False
    images, turn = {}, 0
    for i, vm in enumerate(spec['vms']):
        if not isinstance(vm, dict) or not isinstance(vm.get('image'), str):
            raise Fault('VM sin imagen')
        name = vm['image']
        if 'cirros' not in name:
            raise Fault('Linux de fase 2: por ahora solo imágenes CirrOS (%s)' % name, 409)
        if name not in images:
            images[name] = resolve_image(name)
        vm['image'] = images[name]
        host = vm.pop('host', None)
        if host is not None:  # servidor elegido a mano (paso 3 del Ex2)
            if host not in workers:
                raise Fault('%s no es un worker Linux habilitado (%s)' % (host, ', '.join(workers)), 409)
            vm['worker'] = host
        else:                 # reparto rotativo provisional entre las VMs sin servidor fijo
            vm['worker'] = workers[turn % len(workers)]
            turn += 1
        vm['guest'] = {'os': 'cirros'}
        vm.setdefault('internet', False)
        for j, nic in enumerate(vm.get('nics') or []):
            if isinstance(nic, dict):
                nic.setdefault('name', 'eth%d' % j)
    spec.setdefault('publications', [])
    return spec
