# os-tunnel: túneles SSH app server -> gateway -> APIs OpenStack, dentro de la red Docker `control`.
# Sustituye, para los contenedores, a los túneles del host (g5-tunnels), que escuchan solo en 127.0.0.1.
FROM alpine:3.20
RUN apk add --no-cache openssh-client
# UID/GID del dueño de la clave montada (600) en el host; OpenSSH exige entrada en /etc/passwd.
ARG APP_UID=1000
ARG APP_GID=1000
RUN addgroup -g ${APP_GID} tunnel && adduser -D -u ${APP_UID} -G tunnel tunnel
COPY --chmod=0755 entrypoint.sh /usr/local/bin/os-tunnel
USER tunnel
ENTRYPOINT ["/usr/local/bin/os-tunnel"]
