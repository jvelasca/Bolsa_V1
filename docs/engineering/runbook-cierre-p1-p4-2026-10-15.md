# Runbook de cierre `P1`-`P4` — operativa diaria de la ventana PAPER (2026-10-15)

> **Qué es:** la secuencia **manual y guiada** para operar la ventana PAPER de `AUTO` y cerrar los
> pendientes operativos `P1`-`P4` de la auditoría `v2.88.134-beta`, con los instrumentos del sello
> `v2.88.135-beta` (lane alineada al universo **ESTUDIO**, bundle de evidencia `v2_100` y helper de
> pin `window:pin`).
>
> **Qué NO es:** no es un pipeline de CI. **≥4 días de CALENDARIO operables** salen del **reloj de
> pared** y de un **mercado que permita LONG**: no se fabrica ni se fuerza el régimen. Si el mercado
> veta LONG, el día **no es medible** y se declara `NO_MEDIDO_REGIMEN` (no es un fallo).

**Base:** [`docs/engineering/evidence/v2.88.135/README.md`](./evidence/v2.88.135/README.md) ·
**Criterios falsables:** [`respuesta-auditoria-v2.88.133-beta-2026-10-15.md`](./respuesta-auditoria-v2.88.133-beta-2026-10-15.md) §6.

---

## 0. Preparación (una vez)

- **PostgreSQL** arriba y migrado (head `053_dia_d_cycle_verifications`).
- **API** arriba: `GET /api/health/ready` → `status: ready` (el scheduler de barras vive en el API).
- **Universe ESTUDIO sembrado** (~35 valores): si `resolve_daily_watch` devuelve `empty`/`unavailable`,
  el watch de la ventana queda vacío y el día **no se opera** (fail-closed). Siémbralo **antes** de empezar.
- **Flags de motor OFF** (SIM-only): `AUTO_ORCHESTRATOR_ENABLED` / `AUTO_SIMULATION_WORKER_ENABLED`
  no se activan para medir la ventana PAPER (la ventana usa el harness `v2_76`).
- **Defaults de aislamiento INTACTOS:** `BROKER_VENUE=paper` y **sin** `LIVE_EXECUTION_UNLOCKED` ni
  `LIVE_EXECUTION_AUTHORIZED` (los inyecta el runner; no los pongas a mano).

---

## 1. Secuencia diaria (UNA corrida por día de pared)

Todos los comandos, desde la raíz del repo:

### Paso 1 — Comprobar el freeze (fail-closed)

```bash
pnpm run window:freeze
```

- Debe imprimir **`freeze OK`** (`HEAD:apps`/`HEAD:packages` == pin).
- Si imprime **`TREE_MOVED`**: el árbol commiteado cambió. **No operes**: re-ancla con
  `pnpm run window:pin -- --note "<motivo>"` (solo si el avance del árbol es legítimo) y revisa el
  commit. Un `run-day` sobre un árbol movido **no** certifica.

### Paso 2 — Preflight (¿el mercado admite LONG hoy?)

```bash
pnpm run window:preflight
```

- `exit 0` y eje operable ⇒ **el día es medible**: sigue al paso 3.
- `exit 2` con veto (`BEAR_TREND`/`UNKNOWN`) ⇒ **LONG VETADAS**: el día se registra como
  **`NO_MEDIDO_REGIMEN`** y **no se opera** (el runner lo hace solo). **No se fuerza el régimen.**
  Repite en el siguiente día operable.
- Error duro (sin payload, PostgreSQL caído, watch ESTUDIO vacío) ⇒ **no** es veto: revísalo antes de
  continuar.

### Paso 3 — Correr el día (forward + journal + ventana + auditoría)

```bash
pnpm run window:run-day
```

El runner inyecta, **solo en el hijo**: `AUTO_ENGINE_SIM_REAL_PRICE=1`, `AUTO_OPERATIONAL_AUDIT=1`,
`BROKER_VENUE=paper`, y pasa `--watch-from-estudio` (universo **ESTUDIO** ∩ allowlist). Encadena
`v2_76` (forward) → `v2_77` (journal) → `v2_80` (ventana) → `v2_83` (auditoría) y sella
`operability_runs/window-runs/<DIA>/`.

### Paso 4 — Bundle de evidencia del día (`P1`-`P4`)

```bash
pnpm run window:evidence
```

Escribe `operability_runs/daily-evidence/<DIA>/evidence.{json,md}` con la matriz `P1`-`P4`
(certificador `v2_98` + cadena ESTUDIO `v2_99` + enlace DÍA-D + aislamiento). Regla `UNKNOWN ≠ 0`:
un hueco se declara `null` y **no** cierra el pendiente.

### Paso 5 — Estado de la ventana

```bash
pnpm run window:status
```

Lee el ledger: días medidos / vetados / declarados y el gate (`≥4 días`, `≥2 episodios`, `≥32 ciclos`)
**ligado al run** (un ledger `STALE` no certifica).

> **Nota:** si un `run-day` quedó a medias y el lock diario es huérfano, `pnpm run window:unlock`
> (nunca salta un PID vivo de este host).

---

## 2. Criterios de CIERRE (falsables, sin rebajar)

### `P1` — Ventana PAPER real (ADR-046)

Repite la secuencia en **≥4 fechas de calendario distintas y operables** y certifica:

```bash
uv run --no-sync python apps/api-python/scripts/v2_98_paper_window_certification.py \
  --account-id 1484e253d2d54645945a6b1d7 \
  --strategy-version v283-window-a --strategy-version v283-window-b \
  --json
```

**Cierra** con `verdict == READY`, `days ≥ 4`, `episodes ≥ 2`, `measurableCycles ≥ 32` y
`missingCriterionIds` **vacío**. Si el mercado veta LONG, sigue **`INCONCLUSIVE`** (hueco honesto).

### `P2` — Evidencia por valor de ESTUDIO

```bash
uv run --no-sync python apps/api-python/scripts/v2_99_auto_estudio_chain_evidence.py \
  --account-id 1484e253d2d54645945a6b1d7 --engine-id auto-sim --json
```

**Cierra** con valores medidos **`>0/35`** y cadenas que alcanzan `FILL`/`CYCLE_CLOSED` (9 etapas) con
`pnl.reconciled == true`.

### `P3` — Enlace DÍA-D ↔ ciclo

Tras el **primer ciclo AUTO real** con `strategyPresetKey` sellado:

1. En `/auto/operar`, pulsa **«Verificar D→hoy»**.
2. Lee el resultado:

```bash
# cycleId = el del ciclo AUTO que acaba de cerrar
GET /api/auto/dia-d-verifications?cycleId=<cycleId>
```

**Cierra** con una fila real en `dia_d_cycle_verifications` cuyo `cycleId` case con el ciclo AUTO y
`executedVsDiaD.matches != null` (True o False; nunca fabricado con una sola fuente).

### `P4` — Aislamiento fail-closed (MANTENER)

No requiere acción diaria; **evidencia** = suite de aislamiento verde **+** invariante de venue:

```sql
-- Debe devolver 0 con los defaults (venue=paper, envs LIVE ausentes).
SELECT count(*) FROM execution_events
WHERE account_id = '1484e253d2d54645945a6b1d7'
  AND lower(venue) IN ('live', 'broker_live', 'xtb', 'real', 'live_bridge');
```

`P4` es un invariante de **mantenimiento**: su verde **no** acredita la operación PAPER.

---

## 3. Registro y trazabilidad

- **Por día:** `operability_runs/window-runs/<DIA>/` (manifest + pasos) y
  `operability_runs/daily-evidence/<DIA>/` (matriz `P1`-`P4`).
- **Días no operables:** quedan como `NO_MEDIDO_REGIMEN` en el ledger (declarados, no cuentan como
  medidos).
- **No fabricar:** nunca rellenar `cycle_id`/`reserved_risk`, ni backdatear `created_at`, ni forzar
  `AUTO_ENGINE_SIM_V2_REGIME`, ni bajar umbrales para alcanzar un `READY`.

---

## 4. Re-anclaje del pin (solo cuando el árbol avance por un commit legítimo)

```bash
pnpm run window:freeze                                   # ¿freeze OK o TREE_MOVED?
pnpm run window:pin -- --note "sello v2.88.135"          # re-ancla commit/appsHash/packagesHash
pnpm run window:freeze                                   # debe volver a freeze OK
```

`window-pin.mjs` vive en `scripts/` (no participa del freeze), así que re-anclar **no** mueve a su vez
el árbol. El commit de re-anclaje es el **POST-TAG** (después del sello/tag), como en los sellos
previos.

---

## 5. Qué queda ABIERTO al terminar el runbook

- `P1`/`P2`/`P3` dependen de **días de mercado operables** (`P2`/`P3` dependen de `P1`).
- La **magnitud/rentabilidad** del P&L sigue **NO MEDIDA**.
- Con `BEAR_TREND`, el cierre puede tardar **semanas**: es **MERCADO**, no software.
