"""Imprime un fragmento de cluster.json. No ejecuta SSH ni modifica el inventario o los switches."""
import argparse
import json
from pathlib import Path

MAP = Path(__file__).resolve().parents[1] / 'config' / 'fase2-links.json'


def plan(provider, first, per_host, segments, external=None, external_wire=None):
    inventory = json.loads(MAP.read_text(encoding='utf-8'))
    links = {row[0]: row[1:] for row in inventory['links']}
    prefix = inventory['mac_prefix'] + ':'
    linux = provider == 'linux'
    indices = range(2, 6) if linux else range(7, 10)
    switch, mgmt_link = ('ovs1', 21) if linux else ('ovs2', 22)
    lo, hi = segments
    last = first + len(indices) * per_host - 1
    if not (per_host > 0 and 1 <= first <= last < 4095 and 1 <= lo <= hi < 4095 and (hi < first or last < lo)):
        raise ValueError('Los rangos de transporte y segmento deben ser válidos y disjuntos')
    cfg = dict(name=switch, role='switch', bridge='g5-l2', host='192.168.%d.5' % (201 if linux else 202),
               management_mac=prefix + links[mgmt_link][1], segment_range=[lo, hi], circuits=[])
    fragment = {'require_central_fabric': True, 'central_fabric': {provider: cfg}}
    if not linux:
        cfg['physnet'] = 'physnet1'
    if external is not None:
        port, tag = external
        if linux or not (1 <= tag <= 4094) or lo <= tag <= hi or first <= tag <= last or not port:
            raise ValueError('Puerto o VLAN lógica de acceso externo inválidos')
        cfg.update(external_tag=tag, external_port=port)
    if external_wire is not None:
        if (external is None or not 1 <= external_wire <= 4094 or first <= external_wire <= last or
                lo <= external_wire <= hi or external_wire == external[1]):
            raise ValueError('El tránsito externo requiere un VID reservado y separado de los demás rangos')
        headnode, _, _, switch_mac = links[6]
        cfg['external_circuit'] = dict(host=headnode, uplink=prefix + switch_mac, vlan=external_wire, port=external[0])
    for n, link in enumerate(indices):
        host, host_mac, peer, switch_mac = links[link]
        if peer != switch:
            raise ValueError('El enlace VNRT no llega al switch del clúster')
        if linux:
            endpoint = {'data_mac': prefix + host_mac}
            if host == 'server4':
                fragment['gateway'] = endpoint
            else:
                fragment.setdefault('workers', {})[host] = endpoint
        for vlan in range(first + n * per_host, first + (n + 1) * per_host):
            cfg['circuits'].append(dict(host=host, uplink=prefix + switch_mac, vlan=vlan, port='g5c%d' % vlan))
    return fragment


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('provider', choices=('linux', 'openstack'))
    parser.add_argument('--first-wire', type=int, required=True, help='primer VID de transporte reservado al grupo')
    parser.add_argument('--per-host', type=int, required=True, help='circuitos de NIC por host')
    parser.add_argument('--segments', nargs=2, type=int, required=True, metavar=('MIN', 'MAX'))
    parser.add_argument('--external-port', help='puerto de acceso autorizado al dominio externo en g5-l2')
    parser.add_argument('--external-tag', type=int)
    parser.add_argument('--external-wire', type=int, help='VID de tránsito hacia el headnode por el enlace 6')
    args = parser.parse_args()
    if (args.external_port is None) != (args.external_tag is None):
        parser.error('external-port y external-tag se indican juntos')
    try:
        result = plan(args.provider, args.first_wire, args.per_host, args.segments,
                      (args.external_port, args.external_tag) if args.external_port else None, args.external_wire)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
