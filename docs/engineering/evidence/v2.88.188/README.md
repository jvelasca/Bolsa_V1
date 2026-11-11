# Evidencia `v2.88.188-beta` — DECISIÓN se reorganiza y proyecta el análisis diario del valor; el stack deja de morir en silencio

> **Objeto:** tag anotado `v2.88.188-beta` sobre `main`.
> **Naturaleza:** sello **funcional** de UI + modelo compartido de lectura + operación del entorno de
> desarrollo. **`Δ motor = 0`** · **`Δ decisión = 0`** en reglas, umbrales, sizing y replay.
> **SIN migración** (`head` sigue `066_account_evidence_policy`) · **contrato HTTP sin cambio**
> (`openapi.json`/`schema.d.ts` fuera del diff; `contract:check` **OK**).

## 1. Qué publica este sello

Trabajo que hasta ahora vivía **solo en `main` sin tag**. Un clon obtenía el código, pero no un objeto
publicado que se pudiera contrastar contra un CI de tag.

| Delta | `.187` | `.188` |
| --- | --- | --- |
| `HEAD:apps` | `d4921f79…` | `5310f21d…` |
| `HEAD:packages` | `030d6c4d…` | `7c31fca3…` |
| Diff acumulado | — | **41 ficheros, +3.723/−441** |

- **Bump** `2.11.187-beta` → **`2.11.188-beta`** (+ **14** literales `meta.bump` de **13** scripts;
  `test_dia_d_bump_guard` **2 passed**; el literal congelado `2.11.0-beta` del replay de `v2_87` **no** se
  toca).
- **Pin PAPER re-anclado DESPUÉS del bump** (los `meta.bump` viven en `apps/`, que participa del freeze):
  `node scripts/window-pin.mjs --check` → `freeze OK` sobre el árbol del sello.

### 1.1 Producto

| Entrega | Fichero | Qué aporta |
| --- | --- | --- |
| DECISIÓN: 2 bloques fijos + 5 plegables | [`trading-operativa-panel.tsx`](../../../apps/web/src/features/trading/trading-operativa-panel.tsx) | Un asunto por bloque y una sola puerta de acción; mandato fusiona timeline y ficha; churn acotado al instrumento; atajos duplicados retirados; ids de sección por asunto con fallback de guardados viejos |
| DECISIÓN maximizable | [`trading-layout.tsx`](../../../apps/web/src/components/layout/trading-layout.tsx) · [`trading-layout-store.ts`](../../../apps/web/src/stores/trading-layout-store.ts) | Área completa con exclusión mutua; container queries por **ancho del panel**; < 768 px la vista maximizada es la única puerta |
| Análisis diario del valor | [`instrument-daily-analysis.ts`](../../../packages/shared/src/cognitive/instrument-daily-analysis.ts) | `InstrumentDailyAnalysisV1` como **proyección única**: tendencia, seguimiento con `indicatorSpecs` del TOP #1, entrada con niveles y salida con stop/objetivos/trailing; **`UNKNOWN` ≠ `0`** y huecos en `gaps` |
| Banda en MERCADO | [`operativa-analisis-diario.tsx`](../../../apps/web/src/features/trading/operativa-analisis-diario.tsx) | Banda colapsable sobre la tarjeta de decisión |
| AUTO fuera de la tarjeta | [`operativa-auto-panel.tsx`](../../../apps/web/src/features/trading/operativa-auto-panel.tsx) | Bloque propio, plegable |
| Entradas bloqueadas sin impedir cierres | [`operativa-cockpit-card.tsx`](../../../apps/web/src/features/trading/operativa-cockpit-card.tsx) | Aviso «Entradas bloqueadas · Confirm solo para cierres» **sin** desactivar Confirm |

### 1.2 Operación del entorno de desarrollo

| Entrega | Fichero | Qué aporta |
| --- | --- | --- |
| `api-exit` declarado | [`api-exit.mjs`](../../../scripts/lib/api-exit.mjs) | Motivo con **código, señal, pid, rol y uptime**; `api-exit:0` y `api-exit:signal:<SIG>` dejan de ser invisibles |
| Última causa conservada | [`run-dev.mjs`](../../../scripts/run-dev.mjs) | Handler de `close` (stdio drenado) que adjunta las últimas líneas del stderr; listener de `error` para fallos de spawn |
| Diagnóstico documentado | [`dev-logs.md`](../dev-logs.md) · [`DEV_STARTUP.md`](../../DEV_STARTUP.md) | Vocabulario de `reason` y receta de tres comandos |
| Guardián | [`api-exit.test.mjs`](../../../scripts/lib/api-exit.test.mjs) · `pnpm dev:test` | **9** casos, incluidos exit `0` y muerte por señal |

## 2. Qué NO certifica

| No certifica | Por qué |
| --- | --- |
| **Motor, reglas ni decisión** | No se tocó ningún umbral, peso, sizing, indicador ni replay. La banda **proyecta** artefactos existentes. |
| **Rentabilidad** | AUTO **OFF**, PAPER **`INCONCLUSIVE`**, sin órdenes reales. Ninguna cifra de este documento es evidencia operativa. |
| **El CI del tag** | Este README viaja **dentro** del tag; el run que certifica se cita **POST-TAG** y no se puede auto-certificar aquí. |
| **Los E2E live/integrated** | Exigen API + PostgreSQL + barras; un `skipped` **no** certifica. |
| **Suite completa de Python en local** | La certificación de `pytest` es la del job `python` del tag; aquí solo se midió ruff, imports y mypy. |

## 3. Cómo obtener el objeto

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git
cd Bolsa_V1
git fetch --tags
git checkout v2.88.188-beta
```

`main` puede haber avanzado después: el objeto certificado es el **tag**.

## 4. Verificación medida en local (sobre el árbol del sello)

| Comprobación | Resultado |
| --- | --- |
| `vitest` web | **377 ficheros / 2.800 tests**, 0 fallos |
| `pnpm typecheck` | **4/4** |
| `pnpm lint` | **0 errores** (23 avisos `exhaustive-deps` preexistentes) |
| `pnpm contract:check` | **OK** |
| `ruff check packages/py apps/api-python` | **All checks passed** |
| `lint-imports` | **4 kept, 0 broken** |
| `mypy` (scope CI) | **599 ficheros, no issues** |
| `pnpm window:test` | **86 passed** |
| `pnpm dev:test` | **9 passed** |
| `test_dia_d_bump_guard` | **2 passed** |
| `window:freeze` | **OK** tras el re-anclaje |

**Falsabilidad de `api-exit`:** con el stack listo se mató el proceso de la API
(`Stop-Process -Id <pid> -Force`). El cierre quedó declarado en consola, `logs/agent/events.log` y
`logs/agent/dev.json` con `role`, `pid`, `code`, `signal`, `uptimeMs` y `lastLines`; los puertos 8000 y 5173
quedaron libres y sin huérfanos. Es repetible con el mismo comando.

## 5. Límites declarados

- El **`Release tag CI`** del tag es el certificador del sello; las cifras de §4 son locales.
- El árbol `.187` **no se reabre**: este acto añade encima.
- La banda de análisis diario **no crea** evidencia operativa: su valor es de lectura y de honestidad
  (`UNKNOWN` no es `0`).
- Cualquier afirmación sobre rentabilidad queda **fuera**: AUTO OFF y PAPER `INCONCLUSIVE`.
