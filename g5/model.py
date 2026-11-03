"""Validación del contrato; no se aceptan órdenes shell del cliente."""
import hashlib
import json
import re
import math
from decimal import Decimal, ROUND_CEILING


class Fault(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def require(ok, message, status=400):
    if not ok:
        raise Fault(message, status)


def integer(value, lo, hi, name):
    require(type(value) is int and lo <= value <= hi, '%s: entero %s..%s' % (name, lo, hi))
    return value


def disk_bytes(value, unit='GiB'):
    require(type(value) in (int, float) and math.isfinite(value) and 1 <= value <= 2048,
            'disk_gb: número finito entre 1 y 2048 (admite 2.2)')
    require(unit in ('GB', 'GiB'), 'disk_unit debe ser GB o GiB')
    factor = 1024**3 if unit == 'GiB' else 1000**3
    return int((Decimal(str(value)) * factor / 512).to_integral_value(rounding=ROUND_CEILING)) * 512


def slug(value):
    require(isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9-]{0,31}', value), 'Identificador inválido')
    return value


def digest(value):
    require(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value), 'Se requiere SHA256 hexadecimal')
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def fields(obj, allowed, required=()):
    require(isinstance(obj, dict), 'Se esperaba un objeto JSON')
    require(not set(obj) - set(allowed), 'Campos desconocidos: ' + ', '.join(sorted(set(obj) - set(allowed))))
    require(set(required) <= set(obj), 'Campos obligatorios: ' + ', '.join(required))


def validate(spec, config):
    """Valida una solicitud de slice con el driver de su proveedor (Linux por defecto)."""
    from .drivers import validate as validate_with_driver
    return validate_with_driver(spec, config)
