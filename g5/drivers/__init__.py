"""Registro de drivers por proveedor."""
from ..domain import provider_of
from .linux import LinuxDriver, validate_spec as validate_linux
from .openstack.driver import OpenStackDriver, validate_spec as validate_openstack

VALIDATORS = {'linux': validate_linux, 'openstack': validate_openstack}


def default_drivers(config, backend=None):
    # La sesión OpenStack se abre recién al primer uso: sin sección `openstack` el driver no se usa.
    return {'linux': LinuxDriver(config, backend), 'openstack': OpenStackDriver(config)}


def validate(spec, config):
    return VALIDATORS[provider_of(spec)](spec, config)
