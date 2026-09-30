# Ventana PAPER — día `2026-09-30` **`NO MEDIDO`** por veto de régimen, y preparación del disparo de D1

> **AsOf:** 2026-09-30 · **Cuenta (fija):** `1484e253d2d54645945a6b1d7` · **Versión A (fija):** `v283-window-a` ·
> **Versión B (semilla):** `v283-window-b` · **Venue:** `PAPER` (virtual) · **Árbol de código:** `2.11.11-beta`
> (`HEAD` `89617818`; `apps` `d088d64d`, `packages` `b710934a`) · **Alembic head:** `046_fill_reference_mid`.
> **Veredicto del día:** **`NO MEDIDO`** — **no** se lanza un forward vacío, **no** se fuerza el régimen y
> **no** se fabrica una serie. Se prepara el entorno y se espera al primer día **operable** (`preflight exit 0`).

## 1. Preflight real de hoy (read-only, no escribe)

```text
uv run --no-sync python apps/api-python/scripts/v2_76_forward_market_material.py --preflight-only --watch-size 20
# exit 2
# régimen por símbolo          {'trend_down': 10, 'range': 6, 'trend_up': 4}
# agregado (más conservador)   trend_down
# eje operativo                BEAR_TREND
# entradas LONG                VETADAS (regime_invalid)
```

**Lectura honesta (runbook §1, literal).** El mercado de hoy **veta todas las entradas LONG** con el
agregado más conservador. Correr el forward hoy produciría `cycles=0` / `verdict=BLOCKED` — exactamente la
firma del D1 del `2026-09-28`. La regla dura es explícita: *«La ventana se corre cuando el mercado lo
permita… el veredicto correcto mientras no lo permita es `INCONCLUSIVE` / `NO MEDIDO`»* y *«si veta, DECLARA
y no fuerces»*. Un forward de `~6h40m` (`400 ticks × 60 s`) hoy añadiría un **día de calendario vacío**, no
progreso hacia el gate (`≥32 ciclos`).

## 2. Material durable (medido en PostgreSQL, read-only)

`paper_material_readiness.py --account-id 1484e253d2d54645945a6b1d7 --strategy-version v283-window-a --level evidence` → **exit 2**:

| Métrica | Valor |
|---|---|
| `durable fills` (cuenta, todas las versiones) | **0** |
| `closed cycles` | **0** |
| `reservations` | **0** |
| `measurable R (≥32/strategy)` | **0** |
| `PRODUCER READY?` / `EVIDENCE READY?` | **NO** / **NO** |
| `Allocation` | `FROZEN` |

`v2_80_market_window.py --days 4 --render …` → **exit 2** · `# BLOQUEADO: no hay ningún día de operabilidad
que leer en la ventana`. `v2_83_window_audit.py` → **no ejecutable** (el capturador no produjo serie): se
**declara**, no se fabrica.

**Por qué la ventana no acumula sin un día operable.** `v2_80_market_window.py` construye los días con
material **durable** (`fills | cycles | journal`); el `--forward` **no crea días**, sólo **enriquece** los que
ya existen. Sin fills/cierres/journal no hay filas ⇒ correr D1/D2/D3/D4 sobre días vetados **no cambia nada**
(causa ya medida en `ventana-paper-cierre-no-medido-2026-09-28.md` §3).

## 3. Entorno preparado (para que D1 corra sobre **un solo** árbol)

| Comprobación | Valor |
|---|---|
| API `:8000` `/api/health/ready` | `ready` · `package 2.11.11-beta` · `git_sha 89617818` · `schema 046_fill_reference_mid` |
| API **antes** de reiniciar | `package 2.11.9-beta` · `git_sha d7d89708` ⇒ corría **código previo** al sello |
| Acción | **API reiniciada** (`node scripts/dev-api-python.mjs`) para releer `.env` y servir el árbol sellado |
| PostgreSQL / Docker | `bolsa-postgres` **healthy** en `127.0.0.1:5432` (**debe permanecer arriba** toda la ventana) |
| `.env` | `PAPER_D_ACCOUNT_ID=1484e253d2d54645945a6b1d7`, `BROKER_VENUE=paper` |
| Freeze de código (`git rev-parse HEAD:apps HEAD:packages`) | `d088d64d…` · `b710934a…` (deben **no** moverse durante D1..D4) |

## 4. Protocolo de disparo de D1 (primer día con `preflight exit 0`)

**Disparador (sonda read-only, repetible a diario):**

```powershell
uv run --no-sync python apps/api-python/scripts/v2_76_forward_market_material.py --preflight-only --watch-size 20
# exit 0 ⇒ el universo admite LONG hoy  ⇒ LANZAR D1 (abajo)
# exit 2 ⇒ veta (BEAR_TREND/UNKNOWN)   ⇒ DECLARAR y no forzar
```

**D1 (sólo si `exit 0`), con la cuenta y versión fijas** — lanzar **desacoplado** para que sobreviva al
agente (`Start-Process -PassThru`), `$DIA = Get-Date -Format "yyyyMMdd"`:

```powershell
$env:BROKER_VENUE = "paper"
$ACCOUNT = "1484e253d2d54645945a6b1d7"; $VERSION_A = "v283-window-a"; $DIA = Get-Date -Format "yyyyMMdd"
uv run --no-sync python apps/api-python/scripts/v2_76_forward_market_material.py `
    --account-id "$ACCOUNT" --version-a "$VERSION_A" `
    --interval-seconds 60 --max-ticks 400 --stop-when-ready --level evidence `
    --json --out "operability_runs/forward-market-$DIA.json"
```

Al terminar el forward, encadenar `v2_77` → `v2_80` (`--days 4 --forward 'operability_runs/forward-market-*.json'`)
→ `v2_83`, con los comandos exactos del [runbook §3.1](./runbook-ventana-forward-v2.78-2026-09-27.md). Repetir
**cada día de mercado** con `$ACCOUNT` y `$VERSION_A` **constantes**.

## 5. Reglas duras vigentes (no negociables)

- **No** se lanza un forward en un día vetado para «no perder el día»: no produce ciclos y quema ~6h40m de reloj.
- **No** se fuerza `AUTO_ENGINE_SIM_V2_REGIME`, **no** se baja `min cycles`/`min R`/`folds`/`min_episodes`,
  **no** se backdatea `created_at`, **no** se toca el gobernador/`TOP_N`/umbrales/allocation/pesos A/B.
- `$ACCOUNT` y `$VERSION_A` **constantes** D1..D4; un cambio intermedio **invalida** la ventana.
- El **árbol de código** (`apps`/`packages`) **no** debe moverse durante D1..D4 (freeze). Docs sí.
- Veredicto honesto: **`INCONCLUSIVE` / `NO MEDIDO`** mientras no haya material. `P3-2`/`P3-3` **no** se
  cierran por documentación.

## 6. Ficheros

- [Runbook de la ventana](./runbook-ventana-forward-v2.78-2026-09-27.md) ·
  [arranque operativo A/B y cuenta fija](./arranque-ventana-paper-operativa-2026-09-27.md) ·
  [cierre `NO MEDIDO` previo (2026-09-28)](./ventana-paper-cierre-no-medido-2026-09-28.md) ·
  [viabilidad del AUTO por replay OOS `v2.86`](./replay-oos-viabilidad-auto-v2.86-2026-09-29.md) ·
  [evidencia del sello `v2.88.11`](./evidence/v2.88.11/README.md)
