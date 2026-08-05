# Handoff — Modelo único Estudio / supervisión (2026-08-06)

> Rama docs: `stage/estudio-membership-operativa-2026-08-04` (o la que lleve el commit de docs)  
> **Padre:** [estudio-supervision-model-2026-08-06.md](./estudio-supervision-model-2026-08-06.md) · [ADR-024](../adr/024-estudio-supervision-universe.md)

## Acordado (no implementado)

- Una sola lista **Estudio** (API) = universo supervisable.
- Deprecar concepto **Estudio personal**.
- Interruptor **Supervisión ON/OFF** arma Lista AUTO + CORE-R.
- Análisis automático; **SEMI** confirma operar / cambiar mandato.
- Gráfico **no** añade a Estudio.
- Quitar = unsubscribe (campaña/colas); no auto-cierra mandato.

## Hecho hoy

- ADR-024 Accepted (to-be).
- Diseño engineering + enlaces HELP / list-auto-ops / índice.
- Implementación de código: **mañana**.

## Arranque mañana

1. ADR-024 + diseño §4–5.
2. Persistencia lista API Estudio + migración store.
3. Luego: no auto-add · Supervisión ON · unsubscribe remove · tests.
