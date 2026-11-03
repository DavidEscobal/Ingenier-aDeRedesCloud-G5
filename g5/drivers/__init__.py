"""Registro de drivers por proveedor."""
from ..domain import provider_of
from .linux import LinuxDriver, validate_spec as validate_linux

VALIDATORS = {'linux': validate_linux}


def default_drivers(config, backend=None):
    return {'linux': LinuxDriver(config, backend)}


def validate(spec, config):
    return VALIDATORS[provider_of(spec)](spec, config)
