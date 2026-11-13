# Platform Manager: núcleo de ejecución de fase2 (g5/) — API, cola de jobs, Engine y drivers.
# Contexto de build: la raíz del repositorio (ver deploy/compose.yaml y .dockerignore).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# openssh-client: LinuxDriver (agente por SSH) y túneles a OpenStack.
# qemu-utils: qemu-img valida las imágenes qcow2 que se materializan para Linux (sin backing file ni cifrado).
# novnc + python3-websockify: consola de las VMs Linux en el navegador (entrypoint.sh).
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssh-client qemu-utils novnc python3-websockify \
 && rm -rf /var/lib/apt/lists/*
# El UID debe coincidir con el dueño de la clave SSH montada (permisos 600) y
# tener entrada en /etc/passwd, que OpenSSH exige.
ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd --gid ${APP_GID} appuser \
 && useradd --uid ${APP_UID} --gid ${APP_GID} --create-home appuser \
 && mkdir -p /app/state /run/g5 && chown appuser:appuser /app/state
WORKDIR /app
COPY g5 ./g5
COPY api ./api
COPY templates ./templates
USER appuser
EXPOSE 8000
# Sin secretos en la imagen: cluster.json, keys.json, openstack.env y la clave SSH
# se montan en /run/g5 en tiempo de ejecución (solo lectura).
COPY --chmod=755 services/platform-manager/entrypoint.sh /usr/local/bin/g5-entrypoint
EXPOSE 6080
ENTRYPOINT ["/usr/local/bin/g5-entrypoint"]
CMD ["--config", "/run/g5/cluster.json", \
     "--keys", "/run/g5/keys.json", \
     "--openstack-env", "/run/g5/openstack.env", \
     "--state", "/app/state", \
     "--host", "0.0.0.0", "--port", "8000", "--internal-network"]
