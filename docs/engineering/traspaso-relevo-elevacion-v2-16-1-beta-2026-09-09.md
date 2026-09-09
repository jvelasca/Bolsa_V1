# RELEVO — Elevación `v2.16.1-beta` (cierre de frentes residuales de la auditoría) — 2026-09-09

> **Base:** `main` en `021671a6` (v2.16-beta GREEN real en `39b16f4a` con iso 43 — los "3 fallos"
> del relevo de elevación fueron residuo entre pasos lifecycle-pg, no bug).
> **Este commit:** cierre de los frentes residuales detectados por la auditoría sobre `v2.16-beta` +
> decisión owner de aceptar la deuda P3 del núcleo C2 como riesgo medido. Núcleo financiero
> congelado **intacto**. Alembic head **`023_ohlcv_bars_unique_reconcile`** (sin migración).

## 1. Alcance

Tras las correcciones de sesión (P1-02/03 account default, Auditorías 2 y 3), el owner decidió
**cerrar el ciclo** antes de auditoría externa:

1. **Código de fix** (working tree, sin commitear hasta ahora) — owner-scoping de cuenta por
   defecto + las dos correcciones de la auditoría de esta sesión. Ver CHANGELOG `1.46.1-beta`.
2. **Nuevo documento** `docs/engineering/deuda-p3-nucleo-aceptada-c2-2026-09-09.md` con la
   **decisión owner** (registrada) de aceptar como riesgo medido los P3 del núcleo congelado
   (C2-07 columnas muertas, C2-09 AsyncMock, C2-10 float-eps, C2-11 FSM dormidas,
   C2-03 head hardcodeado, C2-04 provenance cache): **sin tocar** FSM/reconcilers/DR congelados.
3. **Bump** root `1.46.0-beta → 1.46.1-beta` + CHANGELOG.

## 2. Verificación del ciclo (previo al commit)

- ruff CI-parity (`uv run ruff check packages/py/application apps/api-python --config pyproject.toml`) → 0.
- mypy `src` de execution_event / order_live_drift_incident → Success.
- Unit trigger driver + execution = 18; regresión incidentes/execution = 60 passed.
- e2 PG real en scratch dedicated (`bolsa_c1_scratch`, head 023) = 5/5 (incl. merge `fill_unseen`).
- Documento P3 redactado con fidelidad ruta:línea de las fuentes C2.

## 3. Estado tras este commit (local, sin push)

`v2.16.1-beta` confluye hacia `1.46.1-beta`. **Queda como paso del owner en GitHub:** push a
`origin/main` y creación del tag v2.16.1-beta para correr el Release-tag CI (certify, dr-verify,
iso real-PG, playwright) y considerarlo GREEN final antes de auditoría externa.

FIN DEL RELEVO — Elevación `v2.16.1-beta` preparada localmente (código + doc P3 + bump + CHANGELOG);
commit en rama `main` local sin push; tag y CI real quedan a decisión del owner.
