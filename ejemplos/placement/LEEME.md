# Simulador de VM Placement

El simulador ejecuta **el mismo algoritmo de VM Placement que usa el orquestador** (BCDP v2) con datos escritos a
mano, por ejemplo los que proponga el jefe de práctica. No toca ningún clúster y solo necesita Python 3.

## Cómo ejecutarlo (cmd, desde la carpeta del repositorio)

```
python scripts\simular_placement.py ejemplos\placement\caso1_linux_recursos.json
python scripts\simular_placement.py ejemplos\placement\caso2_openstack_zona.json
python scripts\simular_placement.py ejemplos\placement\caso3_sin_recursos.json
python scripts\simular_placement.py ejemplos\placement\caso4_modo_automatico.json
```

Para ejecutar los cuatro seguidos: `python scripts\simular_placement.py ejemplos\placement\*.json`.

Para guardar el resultado en un archivo: `... > resultado.txt`.

## Qué muestra

- **Las VMs pedidas y los servidores de entrada:** lo que ya usa cada servidor y su límite.
- **Los servidores descartados y el motivo:** otra zona, caído o datos de monitoreo antiguos.
- **El plan:** a qué servidor va cada VM y la orden para la plataforma.
  - Linux: `worker = server2`.
  - OpenStack: `availability_zone = "zona:host"`.
- **El uso de cada servidor antes y después del plan.**
- **Si no hay plan:** el rechazo con el recurso que falta. El slice se rechaza completo.
- **En modo automático:** la comparación entre Linux y OpenStack y la plataforma elegida.

## Formato del archivo de entrada

```json
{
  "nombre": "Mi caso",
  "plataforma": "openstack",
  "zona": "zona-a",
  "servidores": [
    {"nombre": "worker1", "zona": "zona-a", "nucleos": 4, "ram_mb": 3935, "disco_gb": 9,
     "uso": {"vcpus": 1, "cpu_real": 0.3, "ram_mb": 1024, "disco_gb": 4}},
    {"nombre": "worker2", "zona": "zona-a", "nucleos": 4, "ram_mb": 3935, "disco_gb": 9, "sano": false}
  ],
  "vms": [
    {"nombre": "vm1", "vcpus": 1, "ram_mb": 1024, "disco_gb": 4},
    {"nombre": "vm2", "vcpus": 1, "ram_mb": 512, "disco_gb": 1, "cpu_prevista": 0.4, "servidor": "worker1"}
  ]
}
```

**Campos generales:**

| Campo | Obligatorio | Significado |
|---|---|---|
| `plataforma` | No (por defecto `openstack`) | `linux`, `openstack` o `auto`. En `auto`, `servidores` lleva dos listas: `{"linux": [...], "openstack": [...]}` |
| `zona` | No | Zona de disponibilidad pedida. Si se indica, solo se usan servidores de esa zona |

**Campos de cada servidor:**

| Campo | Obligatorio | Significado |
|---|---|---|
| `nombre` | Sí | Nombre del servidor |
| `nucleos` | Sí | Núcleos físicos |
| `ram_mb` o `ram_gb` | Sí | RAM total |
| `disco_gb` | Sí | Disco total |
| `zona` | No | Por defecto `nova` en OpenStack y `linux` en Linux |
| `uso` | No | Lo que ya está asignado: `vcpus`, `ram_mb` o `ram_gb`, `disco_gb` y `cpu_real` (núcleos realmente usados). Si falta `cpu_real`, se supone que las vCPU asignadas se usan al 100 % |
| `sano` | No | `false` = servidor caído o en mantenimiento |
| `datos_hace_s` | No | Antigüedad de los datos de monitoreo. Más de 15 s = se descarta |
| `vcpus_max` | No | Tope de vCPU del servidor |

**Campos de cada VM:**

| Campo | Obligatorio | Significado |
|---|---|---|
| `nombre` | Sí | Nombre de la VM |
| `vcpus` | Sí | vCPU pedidas |
| `ram_mb` o `ram_gb` | Sí | RAM pedida |
| `disco_gb` | Sí | Disco pedido |
| `cpu_prevista` | No | Núcleos que se espera que use. Si falta, se supone el 100 % de sus vCPU |
| `servidor` | No | Fija la VM en ese servidor (decisión del usuario) |

**Reglas del orquestador:**

- Hasta 2 vCPU por núcleo.
- La CPU real usada no puede pasar del 85 % de los núcleos.
- RAM y disco sin sobreasignar.
- Límite de 1 s para calcular el plan.

Se pueden cambiar con un bloque opcional
`"politica": {"cpu_ratio": 2.0, "cpu_limit": 0.85, "max_age_s": 15, "timeout_s": 1.0}`.
