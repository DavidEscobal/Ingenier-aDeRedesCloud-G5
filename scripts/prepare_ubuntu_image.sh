#!/usr/bin/env bash
# Crea una base autónoma nueva y preinstala herramientas ANTES de la exposición.
set -euo pipefail
if [[ $# -ne 2 ]]; then
  echo "Uso: bash scripts/prepare_ubuntu_image.sh ENTRADA.qcow2 SALIDA.qcow2" >&2
  exit 2
fi
source_image=$(realpath -- "$1")
target_image=$(realpath -m -- "$2")
[[ -f "$source_image" && ! -e "$target_image" ]] || { echo 'Origen inexistente o salida ya existe' >&2; exit 1; }
for binary in qemu-img virt-customize; do command -v "$binary" >/dev/null; done
qemu-img check -f qcow2 "$source_image"
qemu-img convert -f qcow2 -O qcow2 "$source_image" "$target_image"
# No cambia el tamaño virtual: la base debe caber en 2.2 GiB (o GB si así se configura).
virt-customize -a "$target_image" \
  --install cloud-init,openssh-server,arping,tcpdump,netplan.io \
  --run-command 'cloud-init clean --logs' \
  --run-command 'rm -f /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg /etc/netplan/50-cloud-init.yaml; rm -f /etc/ssh/ssh_host_*; truncate -s 0 /etc/machine-id' \
  --run-command 'printf "%s\n" "datasource_list: [ NoCloud ]" > /etc/cloud/cloud.cfg.d/90-ex1-datasource.cfg' \
  --run-command 'set -eu; command -v tcpdump; arping -h 2>&1 | grep -q -- "-B"; systemctl enable ssh' \
  --run-command 'apt-get clean'
qemu-img check -f qcow2 "$target_image"
qemu-img info "$target_image"
echo 'Base preparada. Importe esta salida y pruebe el arranque antes del examen.'
