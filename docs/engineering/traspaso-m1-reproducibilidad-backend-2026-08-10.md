# Traspaso M1 — Reproducibilidad backend (`uv`) · 2026-08-10

> **Este documento es el punto de entrada para el chat/hilo que ejecute M1.**
>
> ✅ **ESTADO: RESUELTO (2026-08-10).** Ejecutado en FASE 3 y cerró con `uv.lock` commiteado +
> batería en verde (`pytest 434 passed`, ruff solo `B007` pendiente, mypy deuda pre-existente).
> Ver registro en [dev-continuation-plan-2026-08-09.md §7.1](./dev-continuation-plan-2026-08-09.md).
> Los apartados 2–4 abajo son el **diagnóstico heredado** (pre-ejecución); no re-descubrir.
>
> Resumen ejecutivo del contexto ya verificado en el hilo M0/shared. No se re-descubre nada:
> cada hecho de diagnóstico abajo está **confirmado en el repo** con fecha 2026-08-10.

## 0. Qué es M1 (fuente: `docs/engineering/general-audit-plan-2026-08-10.md` §5)

Fila de la tabla de módulos:

> **M1 — Reproducibilidad backend** | Commitear `uv.lock`; evaluar subir `fastapi`/`ruff`/`arq` con tests | Riesgo Bajo | Prioridad ★★★

Y pendiente registrado en `dev-continuation-plan-2026-08-09.md` §7.0:

> M1 — Reproducibilidad backend (siguiente módulo del plan 08-10): diagnosticar
> `uv.lock` + desactualizaciones de dependencias Python (`uv`) y documentar/commitar el
> estado reproducible.

## 1. Protocolo sagrado (leer y respetar — mismo que M0/shared)

1. **Tolerancia cero a fallos.** No asumir: verificar siempre en el repo/CI.
2. **Preservación funcional absoluta.** Un cambio solo se hace si es necesario y probado.
3. **Alcance atómico.** Un módulo por hilo; no tocar nada ajeno a M1.
4. **Flujo en 3 fases:** FASE 1 (diagnóstico, sin cambios) → FASE 2 (plan atómico + aprobación del
   usuario) → FASE 3 (ejecución + batería + commit + push + registro). Sin aprobación explícita
   del usuario **no se toca código ni se commitea.**
5. **Docs como fuente de verdad.** Anclar decisiones a ficheros reales.
6. «No romper NADA»: batería completa de tests antes y después.

## 2. Hechos de diagnóstico confirmados (FASE 1 ya avanzada)

### 2.1 No existe `uv.lock` en ningún nivel del workspace (CONFIRMADO)

- `Glob **/uv.lock` → **0 resultados**. Nivel raíz, `packages/py/*`, `apps/api-python`: nada.
- El `pyproject.toml` raíz usa `[tool.uv.workspace]` con `members` de los 8 paquetes/API
  (es decir, es un **workspace uv**, que en condiciones normales genera `uv.lock` en la raíz).
- **`.gitignore` NO excluye `uv.lock`** (sin matches de `uv.lock`/`lock` en el gitignore) →
  la ausencia no es intencional: simplemente **nunca se generó/commiteó el lockfile**.
- No hay `requirements*.txt` en el repo → el único manifiesto de deps Python son los
  `pyproject.toml`.
- **Implicación (núcleo de M1):** sin `uv.lock` las instalaciones del backend no son
  reproducibles en CI/entornos (a diferencia de `pnpm-lock.yaml`, que sí existe y cierra el
  frontend). Este es el `⚠️` del plan 08-10 §4.

### 2.2 Estructura del workspace uv (confirmada)

- `pyproject.toml` raíz: `[tool.uv.workspace]` members =
  `packages/py/domain`, `market`, `infrastructure`, `application`, `analytics`, `ai`, `apps/api-python`.
- Dev-deps raíz (`[tool.uv] dev-dependencies`): `pytest>=8.3`, `pytest-asyncio>=0.25`,
  `httpx>=0.28`, `mypy>=1.14`, `ruff>=0.9`, `import-linter>=2.1`.
- Mypy raíz: `python_version=3.12`, `strict=true`, plugins pydantic+sqlalchemy.
- Ruff raíz: línea 100, select `E,F,I,UP,B`, ignore `E501`; isort conocidas como first-party
  (`bolsa_ai`, `bolsa_api`, …).

### 2.3 Rangos de dependencias con señales razonables de desactualización (del plan 08-10 §4)

| Paquete | Dep | Rango actual |
| ------- | --- | ------------ |
| `apps/api-python` | `fastapi>=0.115` | señala `>=0.115` |
| `apps/api-python` | `ruff>=0.9` (dev) | señala `>=0.9` |
| `packages/py/infrastructure` | `arq>=0.26` | señala `>=0.26` |
| `packages/py/analytics` | `vectorbt>=0.26` | mantenimiento parado |
| `packages/py/analytics` | `optuna>=4.0`, `numpy>=2.0`, `pandas>=2.2` | ok |
| `packages/py/analytics` | `lightgbm>=4.0` (extra `ml`) | ok |
| raíz | `ruff>=0.9` | señala `>=0.9` |

> ⚠️ La evaluación de «subir» estas deps **debe hacerse con tests** (FASE 3), no ciegamente.
> `vectorbt` tiene mantenimiento parado (candidato a **no** tocar o documentar congela).

## 3. Batería de verificación base del módulo (toca backend)

Del plan 08-10 §5: `ruff` + `mypy` + `pytest` (y confirmar CI en GitHub). Ruta típica por paquete
con uv (workspace): `uv run ruff check`, `uv run mypy`, `uv run pytest` en cada paquete, o
`uv run --package <name> …`. Comprobar la convención exacta que usa el repo/CI antes de lanzar.

## 4. Frentes concretos a resolver (para el chat M1)

Esto **no** es un plan consensuado, es el diagnóstico heredado. El chat M1 debe:
1. **Generar y commitear `uv.lock`** (`uv lock` en la raíz del workspace) — decisión de riesgo
   bajo que cierra la reproducibilidad. Verificar que no infla package names ni rompe cascada.
2. **Evaluar** subir `fastapi`/`arq`/`ruff` con tests de regresión; decidir por hallazgo según
   el CI (no subir de forma masiva). `vectorbt`: conservar/documentar (mantenimiento parado).
3. Mantener **al alcance estricto M1** (solo backend/Python repro y versiones).

## 5. Estado del repo al crear este traspaso

- Rama activa: `stage/estudio-membership-operativa-2026-08-04`
- Último push al inicio de M1: `59eff77..003fefc` (incluye mini-módulo shared `8e4ee62` +
  registro docs `003fefc`). **Working tree limpio** al momento de crear este documento.
- No hay rama dedicada a M1 todavía: decidir si M1 va en la rama stage actual o en una rama
  nueva de módulo (preguntar al usuario en FASE 2 si procede).

## 6. Documentos fuente de verdad / índices

- `docs/engineering/engineering-index-2026-08-03.md`
- `docs/engineering/general-audit-plan-2026-08-10.md` (§4 hallazgos, §5 módulos, §7 seguimiento)
- `docs/engineering/dev-continuation-plan-2026-08-09.md` (§7.0 pendiente M1)
- `docs/ARCHITECTURE.md` · `docs/DEV_STARTUP.md` (arranque backend)
- `packages/py/README.md`

> Al cierre de M1 (FASE 3), actualizar `dev-continuation-plan-2026-08-09.md` con una sección
> 7.x nueva y añadir este fichero al índice engineering si se decide mantenerlo.
