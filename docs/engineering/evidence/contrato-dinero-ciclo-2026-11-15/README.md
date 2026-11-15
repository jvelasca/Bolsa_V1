# Evidencia — contrato del dinero del ciclo y reemisión de settlements (2026-11-15)

**Qué mide este expediente:** que el `pnl` publicado del ciclo es el DINERO del libro
(`applied_per_fill_v1`), que la reemisión histórica añade un hecho nuevo sin tocar el anterior, y
que los lectores eligen la política vigente sin declarar duplicados falsos.

**Entorno:** PostgreSQL local de desarrollo, `.env` del repo, `AUTO` OFF, bridge LIVE cerrado,
release **no sellada** (sin `window:pin`, sin `window:freeze`, sin tag). Ninguna cifra de este
documento proviene de una cuenta real de mercado: los ciclos del escenario controlado son
SIMULATED, producidos por el mismo motor del producto.

Artefactos crudos en este directorio: `dry-run.json`, `apply.json`, `reapply.json`
(operativa sobre la BD local) y `controlled-*.json` (escenario controlado).

---

## 1 · Línea base de la BD local (antes de tocar nada)

| Hecho | Valor |
| --- | --- |
| Hechos `auto_cycle_settlement` | **31** |
| De ellos, con `pnlPolicy` | **0** (todos históricos: `fifo_exact_v0` implícito) |
| Cuentas distintas con settlement | **31** (un hecho cada una) |
| Filas en `sim_fill_finance_context` | **816** |
| Filas con `cycle_id` sellado | **0** |
| Ejecuciones `APPLIED` | **1806** |

La última fila es la que manda para la reemisión: sin `cycle_id` no hay atribución de dinero y el
CLI **no inventa** ciclos vecinos por fecha. Es un límite del material local, no del contrato.

## 2 · Corrida operativa sobre la BD local (dry-run → apply → reapply)

Comando por cuenta (31 cuentas, `--json` para el artefacto):

```text
uv run --no-sync python apps/api-python/scripts/v2_103_reenvio_settlements_politica.py \
  --account-id <cuenta> [--apply] --json
```

| Corrida | Cuentas | Ciclos reconstruibles | `toReemit` | Insertados | Settlements antes → después |
| --- | --- | --- | --- | --- | --- |
| `dry-run.json` | 31 | **0** | 0 | — | 31 → 31 |
| `apply.json` | 31 | **0** | 0 | **0** | 31 → 31 |
| `reapply.json` | 31 | **0** | 0 | **0** | 31 → 31 |

**Lectura honesta:** la reemisión operativa es un **no-op** en esta BD porque **ningún** fill
declara `cycle_id`. No es un fallo del CLI: es el límite declarado —«un ciclo sin fills APLICADOS
reconstruibles se declara, no se inventa»— y así queda en el artefacto. El `apply` no muta nada
(31 hechos sin política antes y después) y reejecutar tampoco.

## 3 · Escenario controlado (el `apply` sí escribe, y solo INSERT)

Para medir el camino de escritura sobre PostgreSQL real sin dejar residuo, se creó **un** ciclo por
el camino productivo (mismo arnés del nodo de identidad: señal → reserva → orden → fill → cierre
`time_exit`), se sustituyó su settlement por el **histórico** (sin `pnlPolicy`, con el PnL exacto
del FIFO) y se ejecutó el CLI real. Al terminar, el escenario se retiró (cuenta e instrumento).

Ciclo medido: `applied_per_fill_v1` = `-43.178396`, `pnlExact` = `-43.178396000000`
(delta de residuo `0` en este ciclo: los precios ya caen en el quantum, de modo que lo que falta
es la **política**, no una diferencia de dinero).

| Paso | Resultado |
| --- | --- |
| `controlled-dry-run.json` | `solo_legacy = 1`, `toReemit = 1`, `previousPolicy = fifo_exact_v0`, `delta = 0.000000`, **sin escritura** (`applied = null`, `readOnly = true`) |
| `controlled-apply.json` | `inserted = 1`, `skipped = 0`, `afterCounts.vigente = 1`, `currentPolicyTotal = 1` |
| `controlled-reapply.json` | `inserted = 0`, `skipped = 1` — la clave policy-aware hace el reintento un no-op |
| Hechos tras el apply | **2**: el histórico intacto (`…:cyc-…`, sin política) y el nuevo (`…:cyc-…:applied_per_fill_v1`) |
| Motor del hecho nuevo | heredado del histórico (`auto-idch-…`); `auto-sim` es solo el respaldo declarado |
| Monitor (drill-down) | `SETTLEMENT = reached`, medición `COMPLETE`, `note = null`, resumen con `settlement_policy_superseded` y **sin** `duplicate_settlement_cycle` |
| Cadena (`pnl`) | `reconciled = true`, `policy = settlementPolicy = applied_per_fill_v1`, `superseded = true`, `cycleClosedPnl = settlementPnl = -43.178396`, `cycleExactPnl = -43.178396000000` |

El histórico aislado (antes del apply) también se midió en el nodo PG: `SETTLEMENT = PARTIAL` +
`settlement_policy_stale`, `pnl.reconciled = null` (hueco declarado, no `false`) y el lector de
recuperación **no** cuenta el ciclo como liquidado.

**Residuo del escenario:** comprobado tras el teardown — 31 settlements, 0 con política,
0 fills del prefijo sembrado, 0 entradas de journal del prefijo. La BD queda como estaba.

## 4 · Gates ejecutados (todo en verde)

| Comando | Resultado |
| --- | --- |
| `pytest packages/py/application` | **3447 passed, 5 skipped** (incluye los 2 tests nuevos del par reemitido) |
| Evidencia PAPER + restart + forward + snapshot + superación PG | **30 passed** |
| Batería de identidad + residuo + superación + v2.103 PG + estudio chain + hechos durables (con `AUTO_IDENTITY_CHAIN_PG_REQUIRED=1`) | **12 passed** |
| Nodos nuevos de reemisión y superación (puros + PG) | **18 passed** |
| `test_golden_day_v2_process_pg.py` + `test_auto_operational_monitor_pg.py` | **17 passed** |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed** |
| `pnpm contract:check` | **OK — `openapi.json` y `schema.d.ts` coinciden** |

Ninguno de estos gates se apoya en tolerancia: la igualdad dinero↔libro es exacta y el residuo se
mide contra `pnlExact`, no contra el número publicado.

## 5 · Límites de esta evidencia

1. **La reemisión operativa no tuvo candidatos** en esta BD (`cycle_id` nulo en 816/816 fills). La
   cifra nueva frente a la sellada **no existe** para esos 31 ciclos: no hay forma de reconstruirlos
   sin atribución durable, y no se inventa.
2. **El `apply` se midió en un escenario controlado** y en los nodos PG, no sobre historia real.
   El escenario se retiró; los artefactos son la medida.
3. **Un ciclo puede tener dos hechos.** Cualquier lector externo al producto que no distinga
   `pnlPolicy` verá un duplicado. Los lectores del producto (monitor, cadena, PAPER, recuperación)
   ya lo distinguen y así se certifica aquí.
4. **Δ medición ≠ 0 / Δ motor = 0 / Δ decisión = 0.** El 6.º decimal puede moverse; no se toca
   ningún umbral.
5. **Sin migración, sin sello, sin tag.** `AUTO` sigue OFF.

## 6 · Verificación independiente (tres subagentes, mismo día)

Tres lectores ajenos a la implementación reprodujeron la evidencia y auditaron el árbol. Su
resultado **no** se transcribe como «todo verde»: el tercero encontró un defecto real dentro del
alcance de la Fase 3 y se corrigió aquí.

1. **Dry-run independiente (31 cuentas).** Reprodujo las 31 corridas y comparó con `dry-run.json`:
   `readOnly = true` y `applied = null` en las 31, conteos agregados idénticos (todo cero),
   `before == after == 31 settlements` y `0` con `pnlPolicy`. Confirmó que el cero significa
   «nada reconstruible desde fills» (816/816 sin `cycle_id`), no «31 ya vigentes».
2. **Apply independiente + nodo PG.** Las 31 corridas `--apply` dieron `mode = apply`,
   `readOnly = false`, `inserted = 0`, `skipped = 0` y **cero mutación** verificada a nivel de tabla
   (`decision_journal_entries`: 48 912 filas antes y después, 31 settlements, misma distribución de
   política, mismos `max(created_at)` y mismas 816 filas de fills). El nodo PG de idempotencia pasó
   **2/2** con `AUTO_IDENTITY_CHAIN_PG_REQUIRED=1` (sin skip) y dejó la BD en la línea base.
3. **Auditoría de lectores (adversarial).** Confirmó policy-aware el monitor, `pnl_reconciliation`,
   la selección de PAPER, la recuperación de arranque y `v2_103`; **encontró** que
   `paper_evidence_reconciliation` seleccionaba por política pero **agregaba sin ella**:
   `settlements_total = len(settlement_rows)` contaba el hecho superado, de modo que un ciclo
   reemitido producía `2` cierres frente a `1` conciliado, una contradicción **falsa**
   `settlement_without_closed_cycle:unkeyed:1` y un gate de cierre (`reconciled == settlements`)
   inalcanzable. Corregido: el total cuenta **un cierre decisivo por ciclo** (el vigente manda) y
   los hechos superados no son evidencia; la nota `settlement_policy_superseded` ya no depende del
   orden de lectura. Dos tests nuevos fijan el par reemitido — uno en la conciliación (incluido el
   orden inverso) y uno extremo a extremo en el adaptador (los siete criterios siguen `met`).

Dictamen de cierre, alcance y fronteras de esa lectura adversarial:
[verificación adversarial de ADR-051](../../verificacion-adversarial-adr-051-2026-11-15.md).
