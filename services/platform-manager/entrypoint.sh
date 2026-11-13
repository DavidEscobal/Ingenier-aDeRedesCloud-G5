#!/bin/sh
# Dos procesos en el mismo espacio de red (los túneles VNC del driver Linux escuchan en 127.0.0.1):
#  1) consola noVNC/websockify de Linux en :6080 (solo red interna `control`; exige token de consola vigente),
#     con el python del sistema, que trae websockify (paquete python3-websockify);
#  2) la API del platform-manager (proceso principal).
set -eu
/usr/bin/python3 -m g5.console --state /app/state --host 0.0.0.0 --port 6080 --web /usr/share/novnc &
exec python -m g5.api "$@"
