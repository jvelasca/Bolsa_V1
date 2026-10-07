# Evidencia `v2.88.85-beta` — `MANUAL · H1` + `AUTO · TOP3 (T1)`: **cierre manual por HTTP + contrato web del TOP3**

**Producto:** `V2.88.85-beta` · **Package:** `2.11.85-beta` · **AsOf:** 2026-10-07. **Sin migración nueva** (head `052_top3_opportunities`). **`Δ motor = 0`** (el fence relajado vive en el canal HTTP paper, no en el motor AUTO de decisión/ejecución). **Contrato HTTP regenerado** (los endpoints `/top3-opportunities` ya existían en FastAPI; `contract:check` verde). **Tag anotado `v2.88.85-beta`** (objeto `23076a9f` → commit `f626bfaa`).

**Padre de producto:** [`v2.88.84`](../v2.88.84/README.md). Auditoría que motivó el slice:
[`auditoria-manual-modo-demo-2026-10-07.md`](../../auditoria-manual-modo-demo-2026-10-07.md) (§H1) y
[`spec-auto-ui-definitiva-2026-10-07.md`](../../spec-auto-ui-definitiva-2026-10-07.md) (§T1–T4).

## Qué cambia

Cierra el dead-end H1 (P1) del canal MANUAL y abre el contrato web del TOP3 (T1), sin tocar el motor:

1. **H1 (P1) — cierre de posición abierta en MANUAL.** El fence de venta HTTP
   (`ExecuteGatedPortfolioTrade`) bloqueaba **toda** `side == 'sell'` con posición abierta
   (`ExitVetoedError("position_exit_requires_confirm")`). Quien abría en MANUAL quedaba **sin
   salida por HTTP**. Ahora `row_is_human_manual(row)` autoriza la venta directa **solo** cuando la
   fila declara origen manual: `birth_override_reason == "human_manual"`,
   `trade_plan_snapshot.origin == "HUMAN_MANUAL"` o `trade_plan_id` con prefijo `manual-`.
2. **Copy de recuperación (H3).** En MANUAL el desriesgo (`reduce`/`exit_hint`/`protect`) dirige a
   **Vender** (venta directa sobre el libro DEMO), en vez de encolar Confirm —que el modo MANUAL no
   permite— y presentarse como error genérico.
3. **T1 — contrato web del TOP3.** El contrato se regenera (`openapi.json` + `schema.d.ts`) y
   `apps/web/src/lib/api.ts` expone `getLatestTop3Opportunities()` y
   `getTop3OpportunitiesForRun(runId)`, tipados por `Top3OpportunitiesResponseDto`. **Sin** hook ni
   panel (eso es T2/T3, fuera de este slice).
4. **Limpieza semántica (P2).** El TOP3 describe **oportunidades rankeadas**, nunca una decisión de
   cartera: se corrigen el endpoint, el worker, el repositorio y la spec (que fija la regla dura).

## Invariantes de honestidad (no negociables)

- El fence **sigue vivo** para posiciones SEMI/AUTO: sin origen manual, una venta HTTP se veta y
  exige Confirm (`ExitPermission`). No hay bypass.
- La autorización de cierre manual se lee de la **fila real** de la posición (no de un flag del
  payload): no se puede pedir «cierre manual» por parámetro.
- T1 **no materializa** el TOP3 en UI: solo se expone el contrato tipado. Un panel que invente una
  acción a partir del TOP3 queda fuera del contrato.
- El TOP3 nombra oportunidades **rankeadas**; el orden no decide cartera, no veta y no emite orden.

## Verificación

- **Hermético (aplicación):** `packages/py/application/tests/test_execute_gated_portfolio_trade.py`
  - `test_gated_http_sell_fenced_when_position_open` — una posición **no** manual sigue vetada.
  - `test_gated_http_sell_allows_when_position_origin_human_manual` — una posición `HUMAN_MANUAL`
    cierra por HTTP.
  - `test_row_is_human_manual_signals` — las tres señales de origen manual.
- **Frontend (vitest):**
  - `apps/web/src/features/operations/propose-position-exit.test.ts` — copy de recuperación en
    MANUAL para `exit_hint`, `reduce` y `protect`.
  - `apps/web/src/features/trading/position-exit-drawer-actions.test.tsx` — en MANUAL **no** se
    encola Confirm y se muestra el copy.
- **Contrato:** `pnpm --filter @bolsa/web contract:gen` regenera `openapi.json`/`schema.d.ts`;
  `corepack pnpm contract:check` **verde** (0 drift).
- **Suite:** `ruff`, `mypy` y pytest (packages + API) verdes; typecheck/lint web verdes.
- **Sello DÍA-D:** `test_dia_d_bump_guard` verde — los CLI `v2_89`…`v2_97` (`meta.bump`) sellan
  `2.11.85-beta` junto al `package.json` (sin este paso, el bump dejaba el guardián rojo).

## Qué no cambia

Motor AUTO de decisión/ejecución (`Δ motor = 0`), ledger, posiciones, settlement y el scoring del
plan. El TOP3 persistido sigue siendo observabilidad. El tag `v2.88.84-beta` permanece.

## Cita POST-TAG

**Tag anotado `v2.88.85-beta`** (objeto `23076a9f` → commit `f626bfaa`, el tip del sello).
`Release tag CI` [`37653650379`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37653650379)
**VERDE** (`12` jobs = `11` `success` + `playwright` integrado `skipped`; `certify` `success`):

- `python` (ruff/imports/mypy/pytest offline): `4594 passed, 45 skipped`.
- `frontend` (typecheck/lint/test/build + `contract:check`): `1523 passed` (`258` ficheros).
- `lifecycle-pg` (Alembic + auth + golden restart): `success`.
- `playwright (mock E2E)`: `success`.
- `replay-repro`: **`REPRODUCIDO`** `sha256 1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7`
  (`bytes 3340728`; `Determinismo del runner` ⇒ 2ª corrida IDÉNTICA) ⇒ **`Δ motor = 0` confirmado por CI**.
- `decision-spine`, `dr-verify`, `shared`, `security` (gitleaks) y `a7-gate`: `success`.

El run apunta exactamente al árbol del sello (`head f626bfaa`), así que la certificación de CI
cubre lo que el auditor descarga del tag.
