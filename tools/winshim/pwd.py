"""Stub SOLO para ejecutar la suite en Windows; devuelve un usuario ficticio con uid/gid 0."""
import collections

struct_passwd = collections.namedtuple('struct_passwd', 'pw_name pw_passwd pw_uid pw_gid pw_gecos pw_dir pw_shell')


def getpwnam(name):
    return struct_passwd(name, 'x', 0, 0, '', '/', '/bin/sh')
