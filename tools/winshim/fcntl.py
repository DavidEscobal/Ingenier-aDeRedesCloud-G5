"""Stub SOLO para ejecutar la suite en Windows: flock es no-op (sin exclusión entre procesos).

No usar en el app server ni en los nodos: allí se usa el fcntl real de Linux.
"""
LOCK_EX = 2
LOCK_NB = 4
LOCK_UN = 8


def flock(fd, operation):
    return None
