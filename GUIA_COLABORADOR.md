# Guía para colaborar sin romper lo que funciona

> **Léela completa antes de tocar nada.** El orquestador está desplegado y probado en el clúster real
> (evidencias `docs/evidencias/F2/MS-01` a `MS-11`). Esta guía existe para que tu trabajo sume sin poner en riesgo eso.
> Punto de restauración del estado actual: etiqueta **`ex2-base-2026-11-10`**.

## 1. El flujo de trabajo (resumen)

```
fase2 (la rama "buena")  ──clonas──▶  fase2-<tu-nombre>  (trabajas, commits, push cuando quieras)
        ▲                                        │
        └──── Pull Request revisado + tests en verde ┘   ← única forma de entrar a fase2
```

1. **Clona y crea tu rama** desde `fase2`:
   ```bash
   git clone https://github.com/DavidEscobal/Ingenier-aDeRedesCloud-G5.git
   cd Ingenier-aDeRedesCloud-G5
   git switch fase2
   git switch -c fase2-<tu-nombre>
   ```
2. **Trabaja en tu rama.** Haz commits pequeños y sube tu rama seguido (`git push -u origin fase2-<tu-nombre>`):
   es tu respaldo y no afecta a nadie.
3. **Antes de proponer tus cambios**, ejecuta `bash scripts/verificar.sh` y deja todo en verde.
4. **Abre un Pull Request** de `fase2-<tu-nombre>` hacia `fase2`. GitHub corre los tests automáticamente
   (workflow `tests`). Cesar revisa el cambio y decide si entra.
5. **Nunca hagas push directo a `fase2`**, ni `git push --force` sobre ella.

Si `fase2` avanzó mientras trabajabas: `git fetch origin && git merge origin/fase2` en tu rama, y vuelve a verificar.

## 2. Lee primero

1. [CLAUDE.md](CLAUDE.md): reglas del proyecto (también las sigue tu asistente de IA).
2. [ESTADO_PROYECTO.md](ESTADO_PROYECTO.md): estado real, decisiones **D-01 a D-15** y el **«Punto de reanudación»**
   con lo que sigue. No contradigas una decisión sin discutirla con el grupo; si cambia, regístrala ahí.
3. La arquitectura: 9 microservicios en Docker Compose (`deploy/compose.yaml`); cada `services/*/README.md` explica el suyo.

## 3. Lo que NUNCA debes hacer

| ❌ Prohibido | Por qué |
|---|---|
| Subir tokens, contraseñas, `keys.json`, `cluster.json`, `openstack.env`, claves SSH, `*.db`, imágenes de disco | **El repositorio es público.** Los secretos viven solo en el app server (`~/g5-app/deploy/platform-config/`) |
| `docker compose down -v` en el app server | **`-v` borra los volúmenes**: usuarios de IAM, slices, borradores y catálogo de imágenes. Para detener basta `down` |
| Borrar o regenerar `~/g5-app/deploy/platform-config/` | Contiene las identidades de servicio que conectan los microservicios entre sí |
| Tocar `g5-tunnels` del app server, o iptables / `authorized_keys` del gateway | Corta el acceso a OpenStack |
| Borrar los proyectos `lab5` / `topo1_lab6`, recrear `cloud_admin`, borrar el flavor `g5-1c-512m-1g` o la imagen `cirros-062` | No son tuyos o los usa la demo |
| Desplegar en el app server (`~/g5-app`) código que no esté en `fase2`, o sin avisar | Los servicios y puertos son compartidos; alguien puede estar en una demo |
| Ejecutar otra vez `g5_iam.cli init` | IAM ya está inicializado |
| Imprimir o pegar tokens en chats, issues o commits | Mismo motivo: repositorio público |

## 4. Preparar tu entorno (una vez)

Requisitos: **Python 3.12** y Git. (Node 20 solo si vas a tocar la web; también puede compilarse con Docker.)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      Linux/Mac: source .venv/bin/activate
for s in gateway iam-service slice-manager topology-manager image-catalog; do pip install -r services/$s/requirements.lock; done
```

## 5. Antes de cada Pull Request: `bash scripts/verificar.sh`

Hace cuatro comprobaciones y debe terminar en **TODO OK**:

1. Tests del núcleo (`tests/`): motor, drivers, contenedores.
2. Tests de los microservicios (`tests/app/`): IAM, gateway, slice-, topology- e image-catalog con procesos reales.
3. Contratos OpenAPI al día: si cambiaste una API, regenera y commitea `contracts/http/*.json`
   (`python scripts/export_app_contracts.py`).
4. Que tus cambios no contengan secretos ni archivos sensibles.

Reglas de calidad:
- **Todo cambio con su test.** Si arreglas algo, agrega el test que lo habría detectado.
- **No borres ni debilites tests existentes** para que pase tu cambio; si un test cambia, explica por qué en el PR.
- **No inventes resultados:** una prueba en el clúster real se documenta como `docs/evidencias/F2/MS-xx_*.md`
  con lo que realmente se vio.

## 6. Si necesitas el clúster o el app server

- **Avisa a Cesar antes** de crear slices, reconstruir contenedores o cambiar configuración remota.
- Capacidad limitada: caben **~6 VMs** de 1 GB en total. **Borra tus slices al terminar.**
- Usuarios de prueba (`prof1`, `alumno1`): pide las contraseñas a Cesar **por privado**.
- Para probar cambios usa los tests en tu PC; el servidor solo recibe código ya integrado en `fase2`.

## 7. Qué puedes avanzar sin chocar con nadie

- **Documentación (R0):** actualizar el HLD y el reporte de pruebas con MS-01 a MS-11.
- **Propuesta de heurística de placement (D-07)** para que el grupo decida (insumo: notebook 07 y la rúbrica R4).
- Coordina antes de tocar placement o R5 (seguridad y red), para no editar los mismos archivos a la vez.

## 8. Si algo sale mal

- Tu rama está rota: no pasa nada, `fase2` no se tocó. Vuelve a un commit anterior de tu rama o empieza otra desde `fase2`.
- Algo entró mal a `fase2`: avisa a Cesar; existe la etiqueta `ex2-base-2026-11-10` como punto de restauración.

## 9. Para el dueño del repositorio (David): proteger `fase2`

GitHub → **Settings → Branches → Add branch ruleset** (o *Branch protection rule*) para `fase2`:
- **Require a pull request before merging** (1 aprobación).
- **Require status checks to pass** → seleccionar `tests`.
- **Block force pushes** y no permitir borrado de la rama.

Con esto nadie puede subir directo a `fase2` por error: todo entra revisado y con los tests en verde.
