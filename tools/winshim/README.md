# winshim — solo desarrollo en Windows

`g5` usa `fcntl` y `pwd`, que solo existen en Linux. Estos stubs permiten correr la suite
de pruebas en Windows:

```bash
PYTHONPATH=tools/winshim python -m unittest discover -s tests
```

Limitaciones: `flock` no bloquea, así que las pruebas no validan la exclusión entre procesos
por archivo de bloqueo (las transacciones SQLite sí son reales). La validación oficial se hace
en Linux (app server), sin `PYTHONPATH`.
