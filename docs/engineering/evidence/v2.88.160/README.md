# Evidencia `v2.88.160-beta` — adopción sin geometría inventada, atribución versión→ciclo y TOP sin ceros

## 1. Qué publica este sello

Cierra los **cinco huecos A–E** del diagnóstico
[`diagnostico-adopcion-puntuacion-atribucion-2026-10-21.md`](../../diagnostico-adopcion-puntuacion-atribucion-2026-10-21.md).
**`Δ motor = 0`**, **`Δ decisión = 0`** salvo la selección sin medición, y **sin migración** (`head`
sigue `057_top3_opportunity_identity`).

## 2. Los cinco huecos

| Hueco | Síntoma medido (2026-10-21) | Cierre |
| --- | --- | --- |
| **C** | Los hechos de gestión de posición solo vivían en RAM | Buffer `_v2_position_journal_pending` + `_v2_flush_position_journal()` al cerrar turno, que sella cada hecho con `build_position_management_journal_entry` en `_operational_audit_sink` |
| **B** | Stop `12.9144` sobre mercado `10.42` ⇒ cuatro ventas cerraron la posición en `0,04 s` | `_adoption_cost_basis()` da precedencia al libro sobre el espejo; `_v2_adoption_stop()` exige ATR finito **y positivo**, `0 < stop < entry` y `stop < price·(1−0,002)`; si no, `_v2_declare_adoption_without_stop()` declara `RECONCILIATION_REQUIRED`/`PROTECTION_MISSING` con telemetría completa |
| **D** | Posición adoptada con `ver=None` / `cycle=None` | `_canonical_applied_facts()` / `_canonical_open_attribution()` leen el último BUY aplicado con `build_position_ledger`; `readopt_positions` restaura la versión **después** del bucle de la proyección (el libro manda sobre el espejo) y propaga `cycle_id` |
| **A** | 40 de 41 candidatas con `0.0` exacto ⇒ el `top_n=5` lo formaban 1 candidata real y 4 ceros por desempate alfabético | `OpportunityScore.measured_components`/`scored`, motivo `OPPORTUNITY_UNSCORED`, y `select_top_opportunities(..., require_measured=True)` **solo** en la decisión: la foto TOP3 cross-asset conserva el histórico |
| **E** | `3204115d` ×2 con 1933.3953 bajo dos motores vivos | `read_live_engines` en los dos stores + `_cost_basis_is_ambiguous`: se reconcilia la **cantidad**, se niega el **coste** medio de la cuenta y se declara |

## 3. Verificación medida (local, sobre este árbol)

| Comprobación | Resultado |
| --- | --- |
| Focalizado (A9.1 crash battery, ranker, worker integration, TOP3 PG, bump guard) | **76 passed** |
| Suite `packages/py` + `apps/api-python` | **5900 passed / 1 skipped** (`chaos/live_a7` deseleccionado) |
| `ruff` | **All checks passed!** |
| `mypy` | **no issues / 567 source files** |
| `window-pin --check` | **freeze OK** |

**Límite de la suite.** Los **7** tests de `chaos/live_a7` se deseleccionaron: son caos con workers
reales y esperas de 40 s que fallan de forma intermitente bajo carga (en una pasada `c3a`, en otra
`c3b`), sin relación con estos cambios. Su certificación es la del CI del tag (§7), que corre el job
`a7-gate` con PostgreSQL real dedicado.

## 4. Cierre del día `20261021` (medido, no interpretado)

| Dato | Valor |
| --- | --- |
| `status` / `reason` | **`MEDIDO`** / vacío |
| `steps.forward` | `exit 2 · declared true · hard false` |
| `sample.verdict` | **`BLOCKED`** |
| `sample.closedCycles` | **4** (`durableFills 20`, `turnTotals.closed 1`, 12 fills del día) |
| `sample.measurableCycles` | **0** |
| `blockers` | `no measurable risk` · `no exit orders` · `insufficient measurable cycles per strategy` |
| `window.header.undatedCycles` | **4** |
| Freeze del artefacto | `apps f37b6da0` / `packages b33bf1e0` (idéntico al pin entonces vigente) |

**El día no fue `HARD_ERROR`.** `exit 2` ⇒ `declared: true, hard: false` ⇒ `resolveDayStatus` nunca
cae en error duro. Es la clasificación correcta: posición viva, stop bajo mercado, horizonte abierto y
cero ciclos **medibles** — no demuestra ni una ejecución ni una rentabilidad.

**Corrección de una predicción propia.** El diagnóstico afirmaba que el día cerraría con **0 ciclos
cerrados**. Falso: cerró **4 round-trips**. Lo que sí se cumplió es lo que el gate mide: **0
medibles**. Se documenta como **Huecos F-1/F-2** (ciclos cerrados sin día atribuido y sin denominador
de riesgo enlazado), **fuera** de este sello.

## 5. Certificación y evidencia

| Comando | Resultado |
| --- | --- |
| `window:certify` | **`INCONCLUSIVE`** · días `4/4` · episodios `0/2` · ciclos `0/32` · faltan `episodes`, `measurable_cycles` |
| `window:evidence` | **P4 CERRADO**; P1, P2 y P3 **abiertos** |

`P4` es un invariante de **mantenimiento** (venue `paper`, envs LIVE ausentes, 0 trazas LIVE): su
cierre **no** acredita la operación PAPER.

## 6. Freeze

| Elemento | Valor |
| --- | --- |
| Commit del sello | `4a76d477` |
| Commit del pin | `f2caa2a0` |
| `apps` | `4be4a32f87b4f2c8feaace4d09842fbcf020bf5c` |
| `packages` | `0824c030a43bb057ef782dad22a1bc76614b10fa` |

El pin se **re-ancló** porque el bump mueve `apps` (el `meta.bump` de los 13 CLIs vive en
`apps/api-python/scripts`) y `packages` (el lector en `packages/py/application`). Tras el re-anclaje,
`window:freeze` ⇒ **`freeze OK`**.

## 7. Publicación

Tag **anotado y unsigned**, pre-release (es una `beta`). Trabajado y cerrado el **2026-10-22**;
publicado el mismo día junto con `.158` y `.159`, que quedaron sin publicar desde el 2026-10-21.

**Efecto sobre la ventana.** El re-anclaje invalida la procedencia de los días medidos con el pin
anterior: `2026-10-19..22` quedan **`STALE`** y no cuentan. La medición válida arranca en el primer
día de sesión que se corra **después** de este tag.

## 8. Límites declarados

- AUTO sigue **OFF**; la ventana sigue **`INCONCLUSIVE`** y `CONFIRMED` **no** se emite.
- Los 4 ciclos cerrados **no** son evidencia de rentabilidad: no tienen R reconstruible ni día
  atribuido.
- No se backfillea nada de lo ya corrido; ningún día se reinterpretó a posteriori.
- Los Huecos **F-1/F-2** están declarados y **no** se arreglan aquí.

## 9. CI del tag (post-publicación, medido)

Medido el **2026-10-22** sobre el `headSha` del tag, no sobre `main`:

| Workflow | Run | `headSha` | Conclusión |
| --- | --- | --- | --- |
| `Release tag CI` | [39815515285](https://github.com/jvelasca/Bolsa_V1/actions/runs/39815515285) | `2e0f1fa6` | **`success`** (13/13 jobs) |

Cita: https://github.com/jvelasca/Bolsa_V1/actions/runs/39815515285
