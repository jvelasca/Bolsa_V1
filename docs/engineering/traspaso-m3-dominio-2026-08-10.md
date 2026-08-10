# Traspaso M3 — Capa de dominio (`py/domain` + `application`) · 2026-08-10

> **Este documento es el punto de entrada para el chat/hilo que ejecute M3.**
> Resumen ejecutivo del **estado verificado** del repo tras cerrar M2 (2026-08-10, tarde), preparado
> para poder continuar en un **hilo nuevo** sin perder contexto. No se re-descubre nada: cada hecho
> de abajo está confirmado en el repo/CI.

## 0. Qué es M3 (fuente: `docs/engineering/general-audit-plan-2026-08-10.md` §5)

Fila de la tabla de módulos:

> **M3 — Capa de dominio** (`py/domain` + `application`) | Coherencia de negocio, docstrings, código muerto | Riesgo Medio | Prioridad ★★★

Orden sugerido del plan 08-10:
1. **M0** (docs) — cerrado
2. **M1 + M2** (reproducibilidad/versiones) — **M1 cerrado** (`67f8b46`), **M2 cerrado** (este traspaso)
3. **M3 / M4 / M6** (backend por capas) — el corazón de la lógica de negocio → **M3 es el siguiente**
4. **M5** (frontend por features) — lo más grande, dividido
5. **M7** (dev-stack residual F3.7)

## 1. Protocolo sagrado (leer y respetar — mismo que M1/M2)

1. **Tolerancia cero a fallos.** No asumir: verificar siempre en el repo/CI.
2. **Preservación funcional absoluta.** Un cambio solo si es necesario y probado.
3. **Alcance atómico.** Un módulo por hilo; no tocar nada ajeno a M3.
4. **Flujo en 3 fases:** FASE 1 (diagnóstico, sin cambios) → FASE 2 (plan atómico + aprobación del
   usuario) → FASE 3 (ejecución + batería + commit + push + registro). Sin aprobación explícita
   **no se toca código ni se commitea.**
5. **Docs como fuente de verdad.** Anclar decisiones a ficheros reales.
6. «No romper NADA»: batería completa de tests antes y después.

## 2. Estado del repo al crear este traspaso (2026-08-10, tras M2)

- Rama activa: `stage/estudio-membership-operativa-2026-08-04`.
- HEAD: `0469fa2` (cierre docs M2). **Working tree limpio**, sincronizado con `origin/<rama>`.

### Commits de M2 (4, pusheados, CI verde)

| Commit | Contenido |
| ------ | --------- |
| `20ecad0` | `@types/react 19.2.18` + `@types/react-dom 19.2.4` (rangos `^19.2.18`/`^19.2.4`) + `pnpm-lock.yaml` |
| `ae79c62` | Fix CI pre-existente: paso `Build shared` (construir `dist/` de `@bolsa/shared`) en `frontend-ci.yml` |
| `57d81cd` | Fix 2º defecto CI: declarar `@types/node@22.20.0` en web (`TS2580 process`) |
| `0469fa2` | Registro docs M2 (§7.2 plan + traspaso + índice CERRADO) |

**Frontend CI verde** en `57d81cd` (Build shared + Typecheck + Lint + Test + Build). Python ruta usa
`python-ci.yml` de `apps/api-python`/`packages/py`.

## 3. Hechos de diagnóstico confirmados (relevantes para backend)

Del plan 08-10 y del cierre M1/M2:

- **Python:** todo `hatchling`, `requires-python >=3.12`, un gestor (uv). Señales razonables de
  desactualización (`vectorbt`, `arq`, `fastapi`, `ruff`) documentadas en §7.1 del plan de
  continuación; `vectorbt` **conservado/fijado** (`==1.1.0`, mantenimiento parado). `uv.lock`
  commiteado en M1 → backend reproducible.
- **Deuda `mypy`:** 454 errores **pre-existentes** (continue-on-error en CI), pendiente como frente
  aparte (NO es alcance M3 salvo que el hilo decida abordarla como sub-hito).
- **`B007` de ruff pendiente:** `packages/py/infrastructure/tests/test_daily_ops_digest_pdf.py:54`
  (variable de bucle `day` sin usar), no auto-fix (`--unsafe-fixes` o renombrar a `_day`). Mini-cierre
  de higiene M0 pendiente, **alternativo/independiente** a M3.
- **M3 concreto (plan §5):** Capa de dominio = `py/domain` + `application`:
  - **Coherencia de negocio** (reglas de dominio consistentes entre paquetes).
  - **Docstrings** (cobertura/calidad).
  - **Código muerto** (detectar y retirar).

## 4. Frentes a resolver (para el chat M3 — heredados, no consensuados)

Esto **no** es un plan consensuado, es el diagnóstico heredado + elaborado. El chat M3 debe, en FASE 1
(diagnóstico, **sin cambios**):

1. **Mapear `packages/py/domain` + `packages/py/application`**: paquetes, módulos, dependencias
   entre ellos y hacia fuera (qué usa cada capa). Confirmar el inventario real (no asumir).
2. **Auditar coherencia de negocio**: detectar reglas/constantes duplicadas o contradictorias entre
   `domain` y `application` (p.ej. umbrales, códigos de estado, lógica de decisión en sitio que debería
   estar en dominio).
3. **Auditar docstrings**: paquetes públicos con docstrings ausentes o desactualizados vs documentación
   de arquitectura (`docs/ARCHITECTURE.md`, `docs/PROJECT_PREMISES.md`).
4. **Detectar código muerto**: símbolos no usados / exports sin consumidores (con la batería y
   `ruff`/`mypy` como apoyo, sin romper).
5. **No tocar infraestructura ni modelo de datos** (eso es M4); no tocar web por features (M5).
6. **Batería backend del módulo** (plan §5): `ruff` + `mypy` + `pytest`. Referencia del cierre M1:
   `pytest` **434 passed**, `ruff` solo `B007` pendiente, `mypy` deuda pre-existente.

## 5. Documentos fuente de verdad / índices

- `docs/engineering/engineering-index-2026-08-03.md`
- `docs/engineering/general-audit-plan-2026-08-10.md` (§4 hallazgos, §5 módulos, §7 registros M0)
- `docs/engineering/dev-continuation-plan-2026-08-09.md` (§7.1 cierre M1, §7.2 cierre M2)
- `docs/engineering/traspaso-m2-versiones-frontend-2026-08-10.md` (precedente más reciente del patrón)
- `docs/engineering/traspaso-m1-reproducibilidad-backend-2026-08-10.md` (precedente backend)
- `docs/ARCHITECTURE.md` · `docs/PROJECT_PREMISES.md` · `docs/adr/*` · `packages/py/*/pyproject.toml`

> Al cierre de M3 (FASE 3), actualizar `dev-continuation-plan-2026-08-09.md` con una sección 7.x
> nueva y añadir este fichero al índice engineering (bajo Product/Ops, junto a los traspasos).
