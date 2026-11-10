# web (D-10)

Interfaz del orquestador: React 18 + Vite 5, compilada a estáticos y servida por `nginx-unprivileged`.
El navegador solo habla con este contenedor; nginx reenvía `/api/*` al gateway por la red interna
(mismo origen, sin CORS). Publica `127.0.0.1:8080` en el app server: se accede por túnel SSH.

## Parte 1 (implementada)

- **Login** contra IAM; sesión en `sessionStorage` (se borra al cerrar la pestaña; expira con el token, 15 min).
- **Menú por rol:** admin ve "Todos los slices"; profesor, "Mis slices" + "Nuevo slice"; alumno, "Mis slices"
  (vacío hasta que exista la asignación de slices en IAM).
- **Mis slices:** lista con proveedor, curso, dueño (admin), estado; se refresca sola mientras algo cambia;
  borrar con confirmación.
- **Detalle:** estado en vivo e historial de eventos de la operación.
- **Nuevo slice:** curso (de IAM), plantilla (catálogo provisional `src/templates/`, copia de
  `templates/os-lineal-1g.json`), nombre, vista previa de VMs y redes. Linux deshabilitado hasta su config de fase 2.

## Parte 2 (implementada): Topologías y editor

- **Topologías:** borradores propios con versión; exportar (descarga `<nombre>.topology.json`), importar JSON
  (validado por el Topology Manager antes de guardarse) y borrar.
- **Editor (React Flow `@xyflow/react`):** predefinidas lineal, anillo, malla, árbol, bus y estrella con N VMs;
  *Reemplazar* o *Combinar con lo actual*; agregar VMs y buses; conectar arrastrando; renombrar; tamaño (solo
  flavors existentes) e imagen; eliminar; guardar con control de versión (409 si otra pestaña guardó antes).
- **Desplegar como slice:** compila la topología en el Topology Manager y la crea por el Slice Manager.

## Ver la web

```bash
ssh -N -L 8080:127.0.0.1:8080 g5-app
```

Luego abrir http://127.0.0.1:8080 en el navegador de tu PC.

## Desarrollo (requiere Node 20)

```bash
npm ci && G5_GATEWAY=http://127.0.0.1:8000 npm run dev
```

## Pendiente

Consola por VM (ruta en el gateway), edición de slices ya desplegados, cursos/usuarios, imágenes y consumo (parte 3).
