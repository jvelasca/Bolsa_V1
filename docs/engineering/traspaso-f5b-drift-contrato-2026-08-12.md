# Traspaso — F5b drift contrato: regen del contract para desbloquear el gate (2026-08-12)

> **Padre único:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) §5
> (fase F5b-drift, deuda registrada en el cierre de [plan-p2.8-as-unknown-as-2026-08-12.md](./plan-p2.8-as-unknown-as-2026-08-12.md) §6/§8).
> **Rama de ejecución:** `stage/f5b-drift-contrato-2026-08-12` (desde base `01cb72a` = tip P2.8 en
> `stage/f1-integridad-financiera-2026-08-11`).
> **Regla del hilo:** NO tocar código fuera del alcance (solo el regen del contrato). Batería por paso.
> **Estado:** **COMPLETADO 2026-08-12** (commit `9c3f643`). `contract:check` vuelve a **verde**. Working tree limpio.

---

## 1. Deuda registrada (contexto)

Desde el merge de F5b (`DepositCashDto.amount`/`WithdrawCashDto.amount → gt=0` añade `exclusiveMinimum: 0.0`
al dump real de FastAPI), el `apps/web/api/openapi.json` commitado estaba **desfasado**: no se regeneró tras el
merge de F5b, ni P2.1 ni P2.8 lo hicieron. Consecuencia: `contract:check` estaba **ROJO en cualquier rama**, con
o sin dichas fases.

Fue registrado como deuda en el cierre de P2.8 (§6/§8) con decisión `cd_exclude` para esa fase (fuera de su
alcance) y con la nota de que debía resolverse en la **fase de fidelidad**: `contract:gen` + commit del regen.

## 2. Alcance de esta fase

**D5 cero features, cambio mínimo de contrato:**

- Regenerar `apps/web/api/openapi.json` contra el FastAPI vivo (offline, vía `uv`) y commitear el regen.
- El `schema.d.ts` (openapi-typescript) **no cambia** (`exclusiveMinimum` no produce diferencia de tipos TS).
- Desbloquear `contract:check` en la rama base viva y en todas las posteriores.

**NO forma parte de esta fase:** P2.6 duplicación TS↔Py, F5a §6 fidelidad campo-a-campo / `openapi-fetch`,
P1.9 API thin, P1.3 auth full. Permanecen como deuda en §6.

## 3. Implementación

| #     | Fichero                                     | Qué                                                                                                                                                                                              |
| ----- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **A** | `apps/web/api/openapi.json` (modificado)    | Regen vía `dump_openapi.py` (offline, `uv`, `PYTHONIOENCODING=utf-8`). Diff = **exactamente 2 inserciones**: `"exclusiveMinimum": 0.0` en `DepositCashDto.amount` y en `WithdrawCashDto.amount`. |
| **B** | `apps/web/src/api/schema.d.ts` (sin cambio) | openapi-typescript produce tipos idénticos (sin diff). Verificado.                                                                                                                               |

Comando ejecutado: `node scripts/sync-contract.mjs` (equivale a `contract:gen`) en `apps/web`, con
`$env:PYTHONIOENCODING="utf-8"` (nota operativa Windows). `contract:check` se re-ejecutó en frío → verde,
prueba de que el contrato commitado es **reproducible byte-a-byte**.

## 4. Batería (aplicada)

- `contract:check` (frío, tras commit): **VERDE** ✓ (exit 0) — antes de la fase estaba ROJO (exit 1).
- `pnpm --filter @bolsa/web typecheck` → **✓** (0).
- `pnpm --filter @bolsa/web lint` → **0 errores** (2 warnings pre-existentes en `backtests-page.tsx`,
  anotados en P2.1/P2.8, no tocados).
- `pnpm --filter @bolsa/web test` → **714 passed (141 f)** — sin regresiones.
- `schema.d.ts` sin diff → typecheck sin cambios de contrato TS.

## 5. Registro

| Fecha      | Acción                                                                                                                                                                                    |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-08-12 | Rama `stage/f5b-drift-contrato-2026-08-12` desde `01cb72a` (tip P2.8). Confirmado `contract:check` ROJO (baseline, exit 1) y drift exacto (2 `exclusiveMinimum` ausentes).                |
| 2026-08-12 | `contract:gen` → diff mínimo de 2 inserciones (`exclusiveMinimum: 0.0` en Deposit/Withdraw). `schema.d.ts` sin cambio.                                                                    |
| 2026-08-12 | Batería verde: contract:check ✓ · typecheck ✓ · lint 0 errores ✓ · test **714✓ (141 f)** ✓.                                                                                               |
| 2026-08-12 | Commit `9c3f643` ("chore(contract, F5b): regenerar openapi.json con exclusiveMinimum en Deposit/Withdraw"), 1 fichero +2. Tree limpio. `contract:check` verde post-commit (reproducible). |

## 6. Deuda / fuera de alcance (sin resolver aquí)

- **P2.6 residue**: duplicación TS↔Py restante (`ai-indicator-series` ↔ `technical_rating`/`data_quality`;
  `execution-policies`/`position-policies`/`tracker-definitions`/`tax-report` ↔ py) → requiere acuerdo de
  fuente de verdad. Consolidar los tipos web-only re-declarados en `packages/shared` (grafos
  `RecommendationV1`/`CoreRVerdict`) ahí.
- **F5a §6**: fidelidad campo-a-campo DTOs manuales vs contrato (igualdad estricta de tipos, `number`↔`integer`,
  `?`↔`null`, `manifest`) + adoptar `openapi-fetch` como cliente completo.
- **Deuda previa**: P1.9 API thin (hilo propio), P1.3 auth full (D4), mypy por fases.

## 7. Cierre — resultado alcanzado y texto de traspaso

F5b-drift **COMPLETADO** con el cambio mínimo pactado:

- `openapi.json` regenerado y commitado; `contract:check` **vuelve a verde** en la base viva y en ramas
  posteriores (se desbloquea el gate que estaba rojo desde el merge de F5b).
- `schema.d.ts` sin cambio → cero impacto de tipos en el FE.
- Batería completa verde. Commit `9c3f643`. Working tree limpio.

### Texto de traspaso (pegable en el próximo chat)

> CONTEXTO INMEDIATO: F5b drift contrato (regen del OpenAPI) **COMPLETADO** en rama
> `stage/f5b-drift-contrato-2026-08-12` (desde base `01cb72a` = tip P2.8 en
> `stage/f1-integridad-financiera-2026-08-11`).
>
> - **`contract:check` desbloqueado**: el drift heredado de F5b (`DepositCashDto.amount`/`WithdrawCashDto.amount
→ gt=0`, faltaba `exclusiveMinimum: 0.0` en `openapi.json`) estaba rojo en cualquier rama desde el merge
>   de F5b (P2.1/P2.8 no lo regeneraron). Regen vía `contract:gen` + commit.
> - **Diff mínimo**: exactamente **2 inserciones** (`"exclusiveMinimum": 0.0` en Deposit y Withdraw).
>   `schema.d.ts` **no cambia** (cero impacto de tipos FE).
> - **Commit**: `9c3f643` ("chore(contract, F5b): regenerar openapi.json con exclusiveMinimum...").
> - **Batería**: contract:check **VERDE** ✓ (antes ROJO) · web typecheck✓ · lint **0 errores** (2 warnings
>   pre-existentes en `backtests-page.tsx`, no tocados) · test **714✓ (141 f)**.
> - **Working tree limpio.** Rama base viva: `stage/f1-integridad-financiera-2026-08-11` (a `9c3f643`).

> DEUDA REGISTRADA → fases posteriores (sin resolver):
>
> - **P2.6 residue**: duplicación TS↔Py restante (ai-indicator-series ↔ technical_rating/data_quality;
>   execution-policies/position-policies/tracker-definitions/tax-report ↔ py) → requiere acuerdo de
>   fuente de verdad; consolidar tipos web-only re-declarados en `packages/shared`.
> - **F5a §6**: fidelidad campo-a-campo DTOs manuales vs contrato + `openapi-fetch` como cliente.
> - Deuda previa: P1.9 API thin (hilo propio), P1.3 auth full (D4), mypy por fases.
>
> Lee PRIMERO: `docs/engineering/traspaso-f5b-drift-contrato-2026-08-12.md` y sus fuentes
> (`plan-p2.8-as-unknown-as-2026-08-12.md` §6/§8, `eng-index` §5 F5b/F5c/P2.1/P2.8).
> NO toques código fuera del alcance de la fase que se declare.
