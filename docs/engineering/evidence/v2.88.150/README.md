# Evidencia `v2.88.150-beta` — gate direccional POR SÍMBOLO (ADR-047): el agregado deja de vetar la cartera entera

> **Bump:** `2.11.149-beta` → **`2.11.150-beta`** (`package.json` + `meta.bump` de los **13** CLIs;
> guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py)
> **2 passed**). Tag **unsigned**.
>
> **Cambio:** **`Δ decisión ≠ 0`** declarado y medido. El veto de entrada usa el régimen del
> **propio símbolo**; el agregado del universo se sigue calculando y se expone como **declaración**
> (`marketRegime`) y dial del gobernador. **`Δ contrato HTTP = 0`**
> (`openapi.json`/`schema.d.ts` **sin diff**; `contract:check` **OK**) · **SIN migración**
> (head `056_auto_ops_jobs`). ADR: [`047`](../../../adr/047-gate-direccional-por-simbolo.md).

## 1. Qué cambió (y qué no)

| Pieza | Cambio |
| --- | --- |
| [`auto_v2_entry.py`](../../../../packages/py/application/src/bolsa_application/auto_v2_entry.py) | `DiscoveryRegimeSource.by_symbol()`/`regime_for()`; `plan_v2_tick(regime_by_symbol=…)` resuelve `_entry_regime(símbolo)` para la barrera §3 y para la economía de candidatas. Guarda macro: `risk_off`/`crisis` ⇒ `RISK_OFF` **global**. |
| Journal | `regime` = agregado del tick · `entryRegime` = régimen del símbolo (**vocabulario operativo**) · `entryRegimeScope="per_symbol"`. Sin mapa no se inyectan claves: payload histórico byte-idéntico. |
| [`auto_simulation_worker.py`](../../../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py) | `_v2_regime_by_symbol()` lee `by_symbol()`; `regime_override`/fuente sin lectura ⇒ `None` (eje global histórico). |
| [`replay_oos.py`](../../../../packages/py/application/src/bolsa_application/replay_oos.py) | `entries_allowed_long = operable_symbols > 0` · `entries_allowed_long_global` conserva la lectura del agregado como **declaración**. |
| Preflight (`v2_76` + [`window-forward.mjs`](../../../../scripts/lib/window-forward.mjs)) | `entryGateScope`, `entriesAllowedLong`, `symbolsOperable`, `operableBySymbol`, `entriesAllowedLongGlobal`. |

**No** se toca: `classify_market_regime`, `_REGIME_CONSERVATIVE_PRIORITY`,
`regime_allows_entry_for` ni sus conjuntos bloqueados, `risk_scale`, gobernador, sizing, salidas,
`TOP_N`, umbrales, pesos A/B, contrato HTTP ni esquema.

## 2. Medida POST (misma máquina, read-only)

| Superficie | PRE (`.149`) | POST (`.150`) |
| --- | --- | --- |
| Preflight de hoy | `BEAR_TREND` ⇒ LONG vetadas | `BEAR_TREND` (declaración) + **`entriesAllowedLong: true`** · `per_symbol` · **8/20** operables |
| Censo del replay (fixture congelado) | `operableDays = 0` ⇒ paso 2 **saltado** | **1 226/1 285** días operables (95,4 %) · `maxOperableStreak 1 226` |
| Artefacto de replay (render CRLF) | `24066225…6D9F54F0` / 3 445 622 B | **`01429BCC…92B7476`** / **3 488 758 B** |
| Artefacto de replay (contenido LF) | `1E3ADAC2…929A37E7` / 3 340 728 B | **`E9B7376B…7F5625`** / **3 383 461 B** |

El cambio de `sha256` **es la prueba** de que la decisión cambió (ADR-047 §4.2). El par anterior
queda como **segmento PRE** (`.136`…`.149`): no se reescribe ningún README histórico.

## 3. Baseline de replay (regenerado y assertado)

Procedimiento medido en local (el mismo del job `replay-repro`):

```text
uv run --no-sync python apps/api-python/scripts/replay_oos_input_fixture.py seed \
  --fixture docs/engineering/evidence/v2.88.7/replay-input-fixture.ndjson
# → 20 instrumentos, 25 700 barras D1

WATCH="$(uv run --no-sync python apps/api-python/scripts/replay_oos_input_fixture.py watch \
  --fixture docs/engineering/evidence/v2.88.7/replay-input-fixture.ndjson)"
uv run --no-sync python apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py \
  --json --watch "$WATCH" --out <artefacto>
uv run --no-sync python apps/api-python/scripts/replay_oos_input_fixture.py \
  assert-artifact --file <artefacto>
```

- **Dos corridas idénticas** (hash de fichero igual) ⇒ runner determinista.
- `assert-artifact` ⇒ **`REPRODUCIDO (render del sello, byte a byte)`**.
- El artefacto **no** cambia al bumpear el paquete (el `bump` del replay sigue congelado en
  `2.11.0-beta`; verificado regenerando después del bump: hash idéntico).

## 4. Verificación medida

| Comando | Resultado |
| --- | --- |
| `uv run --no-sync pytest -q packages/py/application/tests apps/api-python/tests` | **4068 passed** |
| `pnpm window:test` | **50 passed** (48 + 2 de `parsePreflight`) |
| `pnpm lint:py` | **`All checks passed!`** |
| `pnpm imports:py` | **`4 kept, 0 broken`** |
| `pnpm types:py` | **`Success: no issues found in 566 source files`** |
| `pnpm contract:check` | **OK** |
| `python -m pytest test_dia_d_bump_guard` | **2 passed** |
| `pnpm window:freeze` | **OK** tras `window:pin --write` |

Casos falsables añadidos (`packages/py/application/tests/`):

- `test_plan_v2_tick_per_symbol_gate_does_not_veto_others` — un `trend_down` no veta a los demás;
  el agregado se declara y `entryRegime` publica la procedencia.
- `test_plan_v2_tick_per_symbol_gate_missing_symbol_is_unknown` — hueco de barras ⇒ `UNKNOWN`
  **sólo** de ese símbolo.
- `test_plan_v2_tick_macro_risk_off_vetoes_every_symbol` — `risk_off`/`crisis` sigue siendo veto
  **global**.
- `test_plan_v2_tick_without_symbol_map_keeps_historical_payload` — llamantes históricos intactos.
- `test_discovery_regime_source_exposes_regime_by_symbol` — `by_symbol`/`regime_for`.
- `test_census_files_the_day_when_one_symbol_trends_down` (actualizado) —
  `entries_allowed_long=True` + `entries_allowed_long_global=False` + `entryGateScope`.

## 5. Límites declarados (sin fabricar)

- La **ventana PAPER** no se re-mide: sus filas PRE siguen `NO_MEDIDO_REGIMEN` y **no** se
  re-clasifican. PRE y POST **no** son comparables en P&L (regla de decisión distinta).
- El replay prueba que el **gate se abre** (censo 0 → 1 226 días), **no** que haya P&L: exige señal,
  edge y ciclo. **No demuestra rentabilidad.**
- El **agregado sigue sin dimensionar** (no toca `risk_scale` ni el gobernador); si en el futuro
  debe modular tamaño, será otro ADR.
- El preflight local corrió con el watch del catálogo (**20**) porque la BD de desarrollo tiene ese
  universo activo; la comparación PRE/POST se hace sobre el **mismo** watch y la **misma** fuente.
- Operativa **100 % SIM** (`PAPER_D_EXECUTE` off) · tag **unsigned**.

## 6. Publicación

_(se completa POST-TAG con el run del `Release tag CI`, el `freeze OK` y el veredicto
`replay-repro` con el hash NUEVO)_
