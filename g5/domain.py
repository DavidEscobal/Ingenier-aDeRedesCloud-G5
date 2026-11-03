"""Conceptos del slice comunes a todos los proveedores.

Una solicitud de slice declara redes, VMs y publicaciones. El campo opcional `provider`
elige el driver que la valida y la materializa; si falta, se usa Linux (compatibilidad EX1).
Cada driver añade al plan sus propios campos (p. ej. S-VLAN y VNC en Linux).
"""
from .model import require

DEFAULT_PROVIDER = 'linux'
PROVIDERS = ('linux', 'openstack')


def provider_of(spec_or_plan):
    provider = spec_or_plan.get('provider', DEFAULT_PROVIDER) if isinstance(spec_or_plan, dict) else None
    require(provider in PROVIDERS, 'Proveedor no soportado: %s' % provider)
    return provider
