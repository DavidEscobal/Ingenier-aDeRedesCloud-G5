# LAB6 2026-2 — Informe previo, Actividad 1 (2 pts): guía de ejecución para el grupo

Fuente: `Laboratorio_md/GUIA_LAB6_TEL141_2026-2.md` §5. Entrega del informe previo: **jueves 5 de noviembre**.
Las respuestas deben salir de **ejecuciones reales**; esta guía solo indica qué ejecutar y qué anotar.

## Antes de empezar

- Entrar al headnode: `ssh ubuntu@10.20.11.245 -p 5821` y cargar credenciales: `. ~/env-scripts/cloud-admin-openrc`
  (si la carpeta está en `/root`, usar `sudo -i` primero).
- **No** recrear `cloud_admin` ni cambiar su contraseña: el orquestador G5 la usa.
- **Tokens:** en las capturas, tapar el valor de `X-Auth-Token` / `X-Subject-Token` y la contraseña.
- Guardar cada salida: `comando 2>&1 | tee ~/lab6_pasoN.txt`.

## Paso 1 — CLI normal vs `--debug`

```bash
openstack server list 2>&1 | tee ~/lab6_paso1_normal.txt
openstack --debug server list 2>&1 | tee ~/lab6_paso1_debug.txt
grep -E "^REQ: curl|RESP: \[" ~/lab6_paso1_debug.txt
```

Anotar: qué información extra aparece (REQ/RESP, cabeceras, cuerpos JSON, catálogo); **contar** las líneas `REQ:`
(llamadas HTTP); el **orden** de servicios (Keystone `:5000` primero, luego Nova `:8774`) y por qué (token +
catálogo de endpoints antes de llamar a Nova).

## Paso 2 — Token de Keystone

```bash
openstack --debug token issue 2>&1 | tee ~/lab6_paso2.txt
grep -E "REQ: curl|X-Auth-Token|/v3/auth/tokens" ~/lab6_paso2.txt
```

Anotar: la cabecera en la que viaja el token en las llamadas siguientes (`X-Auth-Token`) y el endpoint usado
(`POST http://controller:5000/v3/auth/tokens`, el token vuelve en `X-Subject-Token`).

## Paso 3 — Neutron: debug vs documentación

```bash
openstack --debug network list 2>&1 | tee ~/lab6_paso3.txt
grep -E "REQ: curl.*9696" ~/lab6_paso3.txt
openstack network list --name link_1
```

Anotar: la URL completa del request (`http://controller:9696/v2.0/networks`); los parámetros opcionales de
`GET /v2.0/networks` según https://docs.openstack.org/api-ref/network/v2 (p. ej. `name`, `id`, `project_id`,
`shared`, `router:external`, `status`, `fields`, `sort_key`, `limit`); y el filtro por nombre (`--name`).

## Paso 3.5 — Misma llamada con `curl`

```bash
TOKEN=$(openstack token issue -f value -c id)
curl -s -X GET http://192.168.202.1:9696/v2.0/networks -H "X-Auth-Token: $TOKEN" | python3 -m json.tool | tee ~/lab6_paso35.txt
unset TOKEN
```

Anotar: si coincide con `openstack network list` (mismos recursos; el CLI muestra solo algunas columnas en tabla,
la API devuelve el JSON completo con todos los campos).

## Paso 4 — Error HTTP de Nova

```bash
openstack --debug server show 00000000-0000-0000-0000-000000000000 2>&1 | tee ~/lab6_paso4.txt
grep -E "RESP: \[|itemNotFound" ~/lab6_paso4.txt
```

Anotar: el código (esperado **404 Not Found**), su significado según la API de Nova y en qué línea del debug
aparece el cuerpo del error (`RESP BODY: {"itemNotFound": ...}`).

## Paso 5 — Explicación (máx. 7 líneas)

Redactar con lo observado: el CLI obtiene un token de Keystone, lee el catálogo, construye peticiones REST con
`X-Auth-Token` al servicio correspondiente, recibe JSON y lo formatea en tabla; no ejecuta nada localmente.

> Referencia propia: el driver OpenStack del orquestador (`g5/drivers/openstack/session.py`) hace exactamente
> esa secuencia; sirve para la pregunta de la evaluación personal sobre el uso de tokens.
