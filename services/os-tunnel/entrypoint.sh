#!/bin/sh
# Abre en 0.0.0.0 del contenedor los mismos puertos de servicio de OpenStack (5000, 8774, ...),
# reenviados por SSH a través del gateway hacia el controller. Sin secretos en la imagen:
# la clave y known_hosts se montan en ~/.ssh (solo lectura).
set -eu
: "${OS_TUNNEL_GATEWAY:?usuario@host del gateway}"
: "${OS_TUNNEL_CONTROLLER:?IP del controller OpenStack}"
: "${OS_TUNNEL_PORTS:=5000 8774 9696 9292 6080}"
: "${OS_TUNNEL_KEY:=$HOME/.ssh/id_ed25519_g5_gw}"

forwards=""
for port in $OS_TUNNEL_PORTS; do
  forwards="$forwards -L 0.0.0.0:${port}:${OS_TUNNEL_CONTROLLER}:${port}"
done

echo "os-tunnel: ${OS_TUNNEL_GATEWAY} -> ${OS_TUNNEL_CONTROLLER} puertos: ${OS_TUNNEL_PORTS}"
# Si un reenvío falla o se pierde la conexión, ssh termina y Docker reinicia el contenedor.
# shellcheck disable=SC2086
exec ssh -N -T -o BatchMode=yes -o ExitOnForwardFailure=yes -o GatewayPorts=yes \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
  -o StrictHostKeyChecking=yes -o IdentitiesOnly=yes -i "$OS_TUNNEL_KEY" \
  $forwards "$OS_TUNNEL_GATEWAY"
