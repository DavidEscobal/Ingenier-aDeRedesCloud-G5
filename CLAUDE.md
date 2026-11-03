
# PUCP Private Cloud Orchestrator — Grupo 5

## Contexto del proyecto
Proyecto de Ingeniería de Redes Cloud de la PUCP,
semestre 2026-2.

Objetivo: Diseñar e implementar un orquestador
de slices sobre Linux Cluster y OpenStack.

## Documentación oficial
- requerimientos_md/TEL141_Proyecto_PUCP_Private_Cloud_Orchestrator.md
- requerimientos_md/Cambios_Fase1_Fase2_Requerimientos_EX2.md

## Arquitectura
- Arquitectura_md/G5_Documentacion_Ex1_Fase2_DETALLADA_Claude.md

## Guías de laboratorio
- Laboratorio_md/GUIA_LAB5_TEL141_2026-2.md
- Laboratorio_md/GUIA_LAB6_TEL141_2026-2.md

## Reglas para Claude Code
1. Consultar los requisitos oficiales pertinentes.
2. Respetar la arquitectura diseñada por G5.
3. Distinguir código implementado de diseño pendiente.
4. No inventar implementaciones ni pruebas exitosas.
5. No modificar código existente sin analizarlo.
6. Priorizar reutilización y modularidad.
7. No ejecutar cambios remotos sin autorización.
8. Nunca exponer credenciales ni tokens.
9. Reportar contradicciones entre documentos.

## Objetivo actual
Ver ESTADO_PROYECTO.md (sección «Próxima sesión»).
F0 y F1 terminadas; siguiente: F2 (Topology Manager,
borradores, edición y roles — R1B), en la rama `fase2`.

## Cómo trabajar en este repo
- Tests: `PYTHONPATH=tools/winshim python -m unittest discover -s tests`
  (en Linux, sin PYTHONPATH). Commit por paso, tests en verde.
- Fechas: usar la guía LAB6 2026-2, no el cronograma 2025-2 del enunciado.
- App server: `ssh g5-app`; gateway: `ssh g5-gw`. Avisar y pedir
  autorización antes de crear recursos o cambiar configuración remota.
- Nunca leer ni imprimir `~/.g5/openstack.env` ni tokens.
