# Traspaso / relevo — cierre de `v2.68-beta` (`AUTO-21`)

> **AsOf:** 2026-09-25 · **Versión:** `1.93.0-beta` · **Fase:** `P(R>0)`, correlación entre estrategias por
> cubo temporal y evidencia del régimen actual.
> **SIN migración.** **Freeze intacto.** Sello del reparto **`auto18-v1` congelado**.

## Qué se ha hecho

Fase estrictamente de **medición/evidencia**, sin producto nuevo y **sin mover el reparto**: las tres
lecturas se **publican** (artefacto + render + UI), nunca gatean.

1. **`P(R>0)` (probabilidad de outcome positivo).** El **mismo** bootstrap por episodios que ya encuadraba
   el intervalo publica ahora `probabilityPositive` = fracción de las medias bootstrap **estrictamente
   `> 0`**. Sin bootstrap (sin ciclos o menos de `min_episodes` rachas) la probabilidad es `None` y el
   hueco se declara (`no_cycles` / `insufficient_episodes`) — **nunca un `0`**. Sello del instrumento a
   **`bootstrap_episodes_v2`**.
2. **Calibración de la probabilidad.** Nueva pregunta `probability_positive_calibration`: compara la
   `P(R>0)` **declarada** sobre el IS contra la fracción positiva **realizada** del OOS, con error absoluto
   **medio** contra tolerancia declarada (`CALIBRATION_PROBABILITY_TOLERANCE_DEFAULT = 0.20`); sin celdas
   con ambos términos ⇒ `inconclusive`. `_aggregate` publica `probabilityPositiveOos` (por **ciclos**, no
   media de celdas). Sello a **`walk_forward_calibration_v3`**.
3. **Correlación entre estrategias (`auto_adaptive_correlation.py`, nuevo).** Alineación por **cubo
   temporal declarado** (`day` por defecto, `week`/`month`), Pearson sobre las **medias de R** de los cubos
   **compartidos** (`min_buckets = 4`). Sin solape ⇒ `None` + `no_shared_buckets`; pocos cubos ⇒
   `insufficient_buckets`; serie constante ⇒ `constant_series`. Filas sin instante ⇒ `undated_cycles`. Los
   pares se ordenan por nombre (**orden-invariante**). **No se conecta** al optimizador ni a la reserva.
4. **Evidencia del régimen actual (`auto_adaptive_regime_evidence.py`, nuevo).** Para el régimen actual
   (flag `--current-regime`, o el del ciclo **más reciente con régimen declarable**) publica, por
   estrategia, la celda `strategy × regime` (**reutilizando** el bootstrap de `AUTO-19A`, sin segunda
   aritmética) o el hueco declarado (`no_evidence_for_regime`, `measuredN = 0`). El carácter **adverso**
   sale de `ADAPTIVE_ADVERSE_REGIMES` (solo se publica).
5. **Render y UI.** El stub `AUTO-21 (fuera de alcance)` del `AUTO EVIDENCE REPORT` **desaparece**:
   `Current regime` / `Current evidence` y un bloque `correlation (bucket=...)` publican lo **medido** (o
   `NO MEDIDO`). Espejo TS en `auto-evidence-report.ts` (lee, no recalcula) + bloque de correlación en la
   sección. Las claves del artefacto son **aditivas y opcionales**: sin ellas el artefacto no cambia.
6. **Mutaciones.** **M182…M187** (una por invariante): sello sin subir (`M182`), probabilidad fabricada
   (`M183`), sello de calibración sin subir (`M184`), pregunta sin muestra mínima (`M185`), correlación sin
   cubos publicando `0.0` (`M186`) y régimen inventado (`M187`).

## Estado del sello

- **Tag:** `v2.68-beta` → commit del paquete de fase (ver `arranque-auditor`).
- **Base del diff:** `v2.67-beta`.
- **`v2.67-beta` permanece intacta** (tag inmutable).

## Compuertas (medidas)

| Compuerta | Resultado |
|---|---|
| `pnpm --filter @bolsa/web test` | **1327 passed** (232 ficheros) con `--testTimeout=30000` |
| `pnpm --filter @bolsa/web typecheck` | OK |
| `pnpm --filter @bolsa/web lint` | **0 errores** (23 warnings preexistentes) |
| `pnpm --filter @bolsa/web build` | OK |
| `pnpm --filter @bolsa/web contract:check` | OK |
| `uv run pytest packages/py/analytics -q` | **1238 passed** |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `uv run lint-imports --config packages/py/.importlinter` | **4 kept / 0 broken** |
| Mutaciones | **M182…M187** muerden; matriz completa **187/187** |

**Flake declarado (ajeno):** con el **timeout por defecto** (5 s), `backtests/core-r-scheduler.test.ts`
da `Test timed out in 5000ms` solo bajo la carga de la suite completa. El fichero está **sin tocar**, aislado
pasa siempre, junto a los tests de la fase pasa, y con `--testTimeout=30000` la suite queda **1327 passed**.

## Invariantes que NO se tocan

- PAPER = 100 % VIRTUAL; el reparto `auto18-v1`/`auto15-v1`; el freeze; **sin migración**
  (head `046_fill_reference_mid`).
- La UI **lee y presenta**: `null` ⇒ `NO MEDIDO`; veredicto ausente ⇒ `INCONCLUSIVE`; no-lista ⇒ `NO MEDIDO`.
- **La probabilidad y la correlación no son permisos**: viajan como evidencia y **no** mueven el sizing, el
  plan, la reserva ni la rotación.

## Pendiente / fuera de alcance

- **La corrida PAPER real**: paso operativo del propietario (bloqueo por **material**, no por código).
- Cualquier uso de la correlación o del régimen para **repartir**: esta fase solo los **mide y publica**.

## Cómo continuar

Ver [`arranque-agente-post-v2.68-auto-21-probabilidad-correlacion-regimen-2026-09-25.md`](./arranque-agente-post-v2.68-auto-21-probabilidad-correlacion-regimen-2026-09-25.md).
Para auditar, [`arranque-auditor-v2.68-auto-21-probabilidad-correlacion-regimen-2026-09-25.md`](./arranque-auditor-v2.68-auto-21-probabilidad-correlacion-regimen-2026-09-25.md).
