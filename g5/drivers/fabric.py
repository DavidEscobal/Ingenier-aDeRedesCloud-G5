"""Circuitos de acceso 802.1Q preaprovisionados entre hosts y el OVS central.

Cada NIC tiene su propia VLAN de transporte. Únicamente el bridge central une
los extremos de un segmento, incluso si dos NIC pertenecen al mismo compute.
"""
from ..model import require


def reserve(config, db, sid, plan, provider):
    fabrics = config.get('central_fabric', {})
    require(provider in fabrics or not config.get('require_central_fabric'),
            'Falta el inventario de circuitos para ' + provider, 503)
    if provider not in fabrics:
        return
    cfg = fabrics[provider]
    switch = cfg['name']
    slots = cfg['circuits']
    lo, hi = cfg['segment_range']
    expected = {'linux': 'ovs1', 'openstack': 'ovs2'}[provider]
    require(switch == expected and cfg.get('role') == 'switch' and
            1 <= lo <= hi < 4095 and slots, 'Inventario central incompleto para ' + expected, 503)
    wires = [s['vlan'] for s in slots]
    ports = [s['port'] for s in slots]
    require(len(set(wires)) == len(wires) and len(set(ports)) == len(ports) and
            all(s.get('host') and s.get('uplink') and s['port'] for s in slots) and
            all(type(v) is int and 1 <= v <= 4094 and not lo <= v <= hi for v in wires),
            'Circuitos o etiquetas de aislamiento inválidos', 503)
    external = cfg.get('external_tag')
    if external is not None:
        require(cfg.get('external_port') and type(external) is int and 1 <= external <= 4094 and
                not lo <= external <= hi and external not in wires, 'VLAN externa en conflicto', 503)
    if cfg.get('external_circuit'):
        static = cfg['external_circuit']
        wire = static['vlan']
        require(provider == 'openstack' and external is not None and static['port'] == cfg['external_port'] and
                static['port'] not in ports and type(wire) is int and 1 <= wire <= 4094 and wire not in wires
                and wire != external and not lo <= wire <= hi, 'Circuito permanente de Internet inválido', 503)
    if provider == 'linux':
        legacy_lo, legacy_hi = config['svid_range']
        require(all(not legacy_lo <= wire <= legacy_hi for wire in wires),
                'Las VLAN de transporte deben quedar fuera del pool QinQ', 503)
    used = {r[0] for r in db.execute('SELECT tag FROM fabric_leases WHERE switch=?', (switch,))}
    free = iter(t for t in range(lo, hi + 1) if t not in used)
    segments = {}
    for net in plan['networks']:
        tag = next(free, None)
        require(tag is not None, 'Sin VLAN lógica en ' + switch, 409)
        segments[net['name']] = tag
        db.execute('INSERT INTO fabric_leases VALUES(?,?,?)', (switch, tag, sid))
    attachments = []

    def allocate(host, segment):
        slot = next((s for s in slots if s['host'] == host and s['vlan'] not in used), None)
        require(slot is not None, 'Falta un circuito libre para ' + str(host), 409)
        wire = slot['vlan']
        used.add(wire)
        attachments.append(dict(host=host, port=slot['port'], vlan=wire, segment=segment))
        db.execute('INSERT INTO fabric_leases VALUES(?,?,?)', (switch, wire, sid))
        return wire

    for vm in plan['vms']:
        host = vm.get('worker') if provider == 'linux' else vm.get('host')
        require(host, 'La VM requiere un servidor resuelto por VM Placement', 409)
        for nic in vm['nics']:
            nic['wire_vlan'] = allocate(host, segments[nic['network']])
        if provider == 'openstack' and vm.get('internet'):
            require(external is not None, 'Falta VLAN externa validada', 503)
            vm['external_vlan'] = allocate(host, external)
    if provider == 'linux':
        for net in plan['networks']:
            if 'cidr' in net:
                net['gateway_vlan'] = allocate(config['gateway']['name'], segments[net['name']])
    else:
        require(cfg.get('physnet'), 'Falta el physnet verificado de los circuitos', 503)
        plan['fabric_physnet'] = cfg['physnet']
    plan['fabric'] = {'switch': switch, 'attachments': attachments}


def connect(backend, plan):
    fabric = plan['fabric']
    backend.call(fabric['switch'], 'circuit_connect', sid=plan['id'], attachments=fabric['attachments'])


def disconnect(backend, plan):
    if plan.get('fabric'):
        backend.call(plan['fabric']['switch'], 'circuit_disconnect', sid=plan['id'])
