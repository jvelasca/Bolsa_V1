# Cierre de la ventana PAPER D1..D4 — veredicto honesto **`NO MEDIDO`**

> **AsOf:** 2026-09-28 · **Ventana:** `D1..D4` (D1 = 2026-09-28) · **Cuenta (fija):**
> `1484e253d2d54645945a6b1d7` · **Versión A (fija):** `v283-window-a` · **Venue:** `PAPER` (virtual)
> **Veredicto:** **`NO MEDIDO`** — **no** `READY` y **no** `INCONCLUSIVE` fabricado.
> **Decisión del propietario:** cerrar la ventana ahora, en vez de arrastrarla 4 días de calendario,
> porque el material **no puede** acumularse (ver §3) y el freeze no protegía nada.

## 1. Qué se ejecutó (todo read-only salvo el forward, que es un productor PAPER)

| Paso | Comando | Resultado |
|---|---|---|
| Preflight (no escribe nada) | `v2_76_forward_market_material.py --preflight-only --watch-size 20` | **exit 2** · `{'range': 8, 'trend_down': 9, 'trend_up': 3}` · agregado `trend_down` · eje **`BEAR_TREND`** · LONG **VETADAS** (`regime_invalid`) |
| Forward D1 (detached) | `--account-id 1484e253… --version-a v283-window-a --interval-seconds 60 --max-ticks 400 --stop-when-ready --level evidence --json --out operability_runs/forward-market-20260928.json` | PID `16508`, vivo entre `08:38:05` y `09:15` local; `ticks=10/20/30`, `prices=20/20`, **`cycles=0/0`**, `verdict=BLOCKED`; **parado por el operador** a las `09:15`; el `--out` **NO** se escribió (el runner sólo escribe al terminar ⇒ declarado) |
| Ventana | `v2_80_market_window.py --account-id 1484e253… --strategy-version v283-window-a --days 4` | **exit 2** · `# BLOQUEADO: no hay ningún día de operabilidad que leer en la ventana` |
| Compuerta de material | `paper_material_readiness.py --account-id 1484e253… --strategy-version v283-window-a --level evidence` | **exit 2** · `PRODUCER READY? NO` · `EVIDENCE READY? NO` · `durable fills 0` · `closed cycles 0` · `reservations 0` |
| Auditoría de ventana | `v2_83_window_audit.py` | **NO EJECUTABLE**: sin `--window` (el capturador salió `2` y no produjo serie) ⇒ se declara, no se fabrica |

## 2. Evidencia durable (consultada en PostgreSQL, read-only)

Para la cuenta `1484e253d2d54645945a6b1d7` en los últimos 5 días:

| Tabla | Filas |
|---|---|
| `sim_fill_finance_context` (fills) | **0** |
| `portfolio_reservations` | **0** |
| `decision_journal_entries` | **0** |

El resto de la tabla sí tiene material (1931 fills, 374 reservas, 271 órdenes de salida), pero de **otras**
cuentas: la cuenta de la ventana nunca operó.

## 3. Por qué la ventana **no puede** acumular (causa medida, no supuesta)

1. **El eje veta.** Con `BEAR_TREND` el motor veta toda entrada LONG (`regime_invalid`): sin propuestas
   aprobadas no hay fills, ni reservas, ni ciclos, ni R. `cycles=0/0` no es un fallo, es un **veto legítimo
   de régimen**.
2. **El censo de vetos no es durable.** Las decisiones de entrada (`auto_entry_decision`, con
   `reasonCodes = regime_invalid`) viven en memoria del proceso (`worker._v2_journal`) y sólo se serializan
   en el `--out` del runner. Si el proceso muere —o si se para— ese censo **se pierde**.
3. **La ventana se construye sólo con material durable.** `v2_80_market_window.py:210`:
   `days = sorted(set(fills_by_day) | set(cycles_by_day) | set(journal_by_day))`. El `--forward` **no crea
   días**: sólo **enriquece** los que ya existen (`evidence=evidence_by_day.get(day)`, línea 232).

⇒ **Sin fills/cierres/journal no hay filas; sin filas, correr D2, D3 y D4 no cambia nada.** El `NO MEDIDO`
es la lectura correcta, no una rendición.

## 4. Veredicto y deuda

- **`NO MEDIDO`.** No se baja `min cycles` / `min R` / `folds` / `min_episodes`, no se cambia `TOP_N` ni
  los umbrales, no se cambia el gobernador, el watch ni el allocation, y **no** se fuerzan entradas.
- **`P3-2` / `P3-3` siguen ABIERTAS**: exigen una ventana PAPER ≥4 días **real** con material; esta corrida
  no la produce. **Ninguna deuda se cierra por documentación.**

## 5. Nota operativa encontrada al cerrar (para el próximo intento)

- **Docker Desktop estaba parado** al inicio de la fase: PostgreSQL inalcanzable ⇒ `psycopg.errors.ConnectionTimeout`.
  Eso mató al D1 anterior (PID `34492`). **Docker debe permanecer arriba durante toda la ventana.**
- El forward debe lanzarse **desacoplado** (`Start-Process -PassThru`); lanzado desde una shell del agente
  no sobrevive.
- Antes de invertir días: comprobar que la cuenta tiene **material durable** (`fills`/`reservations`/
  `decision_journal_entries`). Si son `0`, la ventana saldrá vacía por construcción.

## 6. Ficheros

- [Relevo post-`v2.85`](./traspaso-relevo-post-v2-85-auto-material-13-obs10-comportamiento-2026-09-28.md) ·
  [arranque del agente](./arranque-agente-v2-85-auto-material-13-obs10-comportamiento-2026-09-28.md)
- [Runbook de la ventana](./runbook-ventana-forward-v2.78-2026-09-27.md) ·
  [protocolo de auditoría de comportamiento](./protocolo-auditoria-comportamiento-auto-2026-09-28.md)
