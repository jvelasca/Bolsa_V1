# Evidencia `v2.88.156-beta` — cierre de N-155 y H-145 mecánicos + atribución `planId`/`signalId`

> **Naturaleza:** sello **posterior y acotado** a `v2.88.155-beta`.
> **`Δ motor = 0`** · **`Δ decisión = 0`** · **sin migración** (head `057_top3_opportunity_identity`).
> Contrato HTTP **aditivo** (`signalId`/`planId`/`instrumentIdSource` dentro de `dict[str, Any]`;
> `openapi.json`/`schema.d.ts` regenerados, `contract:check` **OK**). `positionOpen` pasa a
> **tri-estado** (`bool | null`), que es lo único que cambia de forma no aditiva y es
> precisamente el objeto del hallazgo H-145-1.
>
> **Bump** `2.11.155-beta` → **`2.11.156-beta`** (+ `meta.bump` de los **13** CLIs) y tag
> anotado **`v2.88.156-beta`**. La evidencia publicada de `.153`, `.154` y `.155` **no se
> reescribe**. **AUTO sigue OFF** y la ventana PAPER sigue **`INCONCLUSIVE`**: un CI verde no
> certifica rentabilidad.

## 1. Qué publica este sello

Siete hallazgos (**N-155-1/2/3**, **H-145-1/2/4** y el *gap 2* de atribución). Ninguno toca
motor, umbrales, pesos A/B, `TOP_N`, régimen, sizing, entradas/salidas, orquestador ni replay
OOS: se corrigen **read-models, DTOs y observabilidad de errores**.

| # | Severidad | Hallazgo | Cierre |
| --- | --- | --- | --- |
| **N-155-1** | `P2` | `direction` se fabricaba (`"short" if side == "sell" else "long"`) y, sin entrada en la ventana, se caía a la reserva de SALIDA. | `_entry_reservation` devuelve `None` sin entrada; `direction`/`strategyVersion` viajan `None`; nota `entry_reservation_not_in_window`. |
| **N-155-2** | `P2` | La comparación TOP3 leía **una sola** foto (la última) y la aplicaba a todos los ciclos. | `snapshot_as_of` ancla la foto por ciclo (`bar <= SIGNAL`, fallback `RESERVATION`); `executedVsBest.anchor` declara la foto usada o el motivo del hueco. |
| **N-155-3** | `P3` | `str(...).strip()` publicaba `""` como identidad. | `_clean_identity_text` normaliza blancos a `None`. |
| **H-145-1** | `P2` | `except Exception: open_ids = set()` convertía «no medido» en «sin posición». | `positionOpen` tri-estado + nota `positions_unavailable`; el motor sigue recibiendo `False` (`Δ decisión = 0`). |
| **H-145-2** | `P3` | `except Exception: continue` silenciaba los chips caídos. | Notas `composite_chips_unavailable:<n>_ids` / `fundamentals_chips_unavailable:<n>_ids`; el batch continúa. |
| **H-145-4** | `P2` | `_ProgressPublisher.tick()` no tocaba `heartbeat_at` antes de la primera línea de progreso ⇒ otro worker podía reclamar el job. | `tick()` renueva el latido también sin progreso y conserva el `_offset`. |
| **Gap 2** | `P2` | El DTO del ciclo descartaba `signalId` y el id del plan. | `signalId`/`planId` se leen del hecho durable `auto_entry_decision` en el monitor, la cadena y el artefacto del parte diario. |

## 2. N-155-1 — la dirección deja de fabricarse

[`auto_operational_monitor.py:910`](../../../packages/py/application/src/bolsa_application/auto_operational_monitor.py)
(`_entry_reservation`):

- La SALIDA (`reservation_id = "exit:<orderId>"`, `side="sell"`) **nunca** gobierna el ciclo.
- Sin fila de entrada en la ventana se devuelve **`None`**: no hay fallback a
  `reservations[0]`.
- El paso `RESERVATION` queda `absent` con nota `entry_reservation_not_in_window` (distinta de
  `no_reservation_for_cycle`, que declara que no había ninguna reserva).

[`auto_operational_monitor.py:1045`](../../../packages/py/application/src/bolsa_application/auto_operational_monitor.py)
(`_build_cycle`):

```python
direction = "long" if side == "buy" else ("short" if side == "sell" else None)
```

`strategyVersion` se lee **solo** de la entrada. `instrumentId` se conserva desde la primera fila
de la ventana para no perder el agrupamiento por valor, pero se publica `instrumentIdSource`
(`entry_reservation` / `reservation_in_window` / `null`) para que el hueco no se disfrace.

El DTO HTTP ([`auto_operational_monitor.py:100`](../../../apps/api-python/src/bolsa_api/api/v1/routes/auto_operational_monitor.py))
pasa de `direction: str = "long"` a `direction: str | None = None`: el contrato dejaba de mentir
incluso antes de llegar a la UI.

**Capa extra de fabricación (no auditada) corregida.** En
[`auto-operational-monitor.ts:70`](../../../packages/shared/src/cognitive/auto-operational-monitor.ts)
el ternario `cycle.direction === "short" ? "Corto" : "Largo"` rotulaba `null` como «Largo». Ahora
`directionLabelFor(...)` devuelve `Largo` / `Corto` / «Sin dato todavía».

## 3. N-155-2 — la foto TOP3 se ancla al instante del ciclo

[`auto_chain_durable_reader.py:756`](../../../packages/py/application/src/bolsa_application/auto_chain_durable_reader.py)
(`read_top3_snapshots`) lee **todas** las fotos y parsea la barra del `run_id`
(`top3-<cuenta>-<barra ISO>`); una foto sin fecha legible va al final y **no** sirve de ancla.

[`auto_chain_durable_reader.py:823`](../../../packages/py/application/src/bolsa_application/auto_chain_durable_reader.py)
(`snapshot_as_of`) es puro y elige la foto más reciente con `bar <= at`; sin instante de
referencia devuelve `None` (no se puede afirmar contemporaneidad).

`read_estudio_chain_evidence` resuelve la foto **por ciclo** con
[`_cycle_anchor_instant`](../../../packages/py/application/src/bolsa_application/auto_chain_durable_reader.py)
(`SIGNAL`, fallback `RESERVATION`) y publica `bestScoredByCycle`:

```jsonc
{
  "bestScored": { "...": "fila rank 1 de la foto vigente" },
  "anchor": {
    "runId": "top3-acc-...",
    "bar": "2026-10-20T09:00:00Z",
    "entryAt": "2026-10-20T09:17:03Z",
    "measurement": "COMPLETE",
    "reason": null
  }
}
```

Sin foto anterior a la entrada: `bestScored=None`, `presetMatch=None`,
`measurement=UNKNOWN`, `reason="no_snapshot_at_or_before_entry"` (o
`cycle_entry_at_not_durable` si el ciclo no fecha su entrada). La foto global sigue publicándose
como `top3` para la cabecera del artefacto. Cada fila declara además su `runId`.

## 4. N-155-3 — `""` no es una identidad

`_clean_identity_text` normaliza `str(value).strip() or None` para `strategyPresetKey` y
`strategyVersion` en las filas de la foto. El lector anterior publicaba `""` y la UI no podía
distinguir «no declarado» de «declarado vacío».

## 5. H-145-1 — posiciones no medidas

[`estudio_daily_ops.py:392`](../../../packages/py/application/src/bolsa_application/estudio_daily_ops.py)
(`_build_hints`) devuelve, además de los hints, un mapa `positionOpen` tri-estado y las notas de
huecos. El parte publica `positionOpen: true | false | null` y, si la lectura falla,
`positions_unavailable`; `position_open` no se afirma desde una lectura caída.

**Invariante de decisión.** `OpinionHint.position_open` sigue siendo `bool` (`False` cuando no se
pudo medir): el motor de dictamen **no cambia** (`Δ decisión = 0`). El tri-estado del motor queda
**fuera de alcance** y declarado para `.157`.

## 6. H-145-2 — chips caídos declarados

Cada chunk que falla se contabiliza y se publica como
`composite_chips_unavailable:<n>_ids` / `fundamentals_chips_unavailable:<n>_ids`. El batch
continúa (los chips son hints, no la señal) y los indicadores afectados viajan `None`, nunca `0`.

## 7. H-145-4 — el latido no depende del primer progreso

[`auto_ops_dia_d.py:247`](../../../apps/api-python/src/bolsa_api/background/auto_ops_dia_d.py):

```python
last, offset = _read_last_progress(self._path, self._offset)
if last is None:
    # Arranque del proceso: el job está VIVO y el latido DEBE renovarse igual.
    async with self._session_factory() as session:
        await SqlAlchemyAutoOpsJobRepository(session).touch(self._job_id)
        await session.commit()
    return
```

Antes se retornaba sin `touch`: un arranque más largo que `stale_after_seconds` permitía que otro
worker reclamara el job y lo ejecutara por segunda vez.

## 8. Gap 2 — atribución señal → plan → ciclo

- `_cycle_signal_id` / `_cycle_plan_id`
  ([`auto_operational_monitor.py:236`](../../../packages/py/application/src/bolsa_application/auto_operational_monitor.py))
  leen `payload.signalId` y `payload.tradePlan.decisionId` del hecho durable
  `auto_entry_decision`. Se publican en la cabecera del ciclo y, **si la etapa ya tenía algún
  hecho**, como hecho aditivo de `SIGNAL`/`RISK` (nunca convierten `UNKNOWN` en `REACHED`).
- `_cycle_view` publica `signalId`/`planId`; `EstudioChainCycleV1` los declara en
  `@bolsa/shared`.
- El artefacto del parte diario (`estudio_audit` + `dia_d_auto_feedback`) **copia** la identidad
  si el ciclo de origen la declara y `None` si no; `EstudioAuditCycleDto` la expone para que el
  panel resuelva la atribución por contrato oficial (se elimina el cast
  `(cycle as { planId?... })` en [`estudio-daily-ops-panel.tsx:241`](../../../apps/web/src/features/auto-monitor/estudio-daily-ops-panel.tsx)).

> **Límite honesto:** hoy el replay DÍA-D (`RoundTrip.to_dict`) **no** sella `signalId`/`planId`,
> así que en producción el artefacto del parte diario seguirá publicando `None` y la ficha dirá
> «Histórico del valor; no atribuido a esta señal». El camino ya existe y es tipado; la
> **fuente** de esos ids en el replay pertenece al sello de replay real (abajo, fuera de alcance).

## 9. Verificación medida

| Comprobación | Resultado |
| --- | --- |
| `pytest test_auto_operational_monitor.py` | **71 passed** |
| `pytest test_auto_chain_durable_reader.py` | **23 passed** |
| `pytest test_estudio_daily_ops.py` | **7 passed** |
| `pytest test_estudio_audit.py test_dia_d_auto_feedback.py` | **47 passed** |
| `pytest test_auto_ops_dia_d.py` | **19 passed** |
| `pytest test_auto_identity_chain_battery_pg.py` (PostgreSQL real) | **3 passed in 4.44s** — incluye el anclaje con foto posterior |
| `vitest @bolsa/shared auto-operational-monitor` | **15 passed** |
| `pnpm --filter @bolsa/web test` | **313 ficheros / 2317 tests** |
| `pnpm typecheck` | **4/4 OK** |
| `pnpm lint` | **0 errores** (23 avisos preexistentes) |
| `uv run ruff check packages/py apps/api-python` | **All checks passed** |
| `uv run mypy packages/py/application/src apps/api-python/src` | **no issues / 407 ficheros** |
| `pnpm contract:check` | **OK** (`openapi.json` + `schema.d.ts` en sync) |
| Guardián de bump | **2 passed** |
| `npm run window:freeze` | **`freeze OK`** |
| `npm run window:test` | **50 passed** |

Pruebas nuevas por hallazgo:

- `test_entry_reservation_is_none_when_only_the_exit_is_in_the_window`,
  `test_closed_cycle_with_only_the_exit_declares_unknown_direction_and_version`,
  `test_cycle_without_any_reservation_does_not_assume_long`,
  `test_cycle_publishes_the_signal_to_plan_attribution_from_the_decision`,
  `test_cycle_without_the_decision_declares_attribution_as_none`.
- `test_snapshot_as_of_picks_the_photo_in_force_and_never_a_later_one`,
  `test_artifact_publishes_the_anchor_of_the_photo_used_for_each_cycle`,
  `test_artifact_without_a_photo_before_the_entry_declares_the_gap`,
  `test_blank_identity_in_the_photo_is_none_and_never_an_empty_string`,
  `test_read_top3_snapshot_returns_the_newest_photo_and_its_run_id`.
- `test_a_failed_positions_read_is_declared_unknown_not_closed`,
  `test_a_measured_positions_read_publishes_the_boolean`,
  `test_failed_chip_chunks_are_declared_instead_of_silenced`.
- `test_publisher_renews_the_heartbeat_before_the_first_progress_line`.
- `test_cycle_comparison_uses_the_photo_in_force_at_the_entry_pg` (PostgreSQL real).
- `trata la dirección como tri-estado: el hueco nunca se rotula «Largo»` (shared) y
  `atribuye el histórico por identidad cuando el ciclo publica planId/signalId` (UI).

## 10. Límites declarados (sin fabricar)

- **AUTO sigue OFF.** No se enciende la cadencia.
- La ventana PAPER sigue **`INCONCLUSIVE`** y **`CONFIRMED` no se emite**.
- Operativa **100 % SIM**; el bridge LIVE no se abre. **Rentabilidad no certificada.**
- **H-145-3** (job `OK` con errores por valor) y **H-145-5** (tope de intentos) **siguen
  abiertos**: requieren semántica operativa nueva y van a `.157`.
- **Gap 1** (identidad durable completa TOP3 ↔ parte diario ESTUDIO) **sigue abierto**: exige
  decidir la fuente de la identidad ganadora y añadir un puerto de lectura al servicio.
- **Replay DÍA-D real** con datos durables: fase de operación/evidencia, no de código. Por eso el
  artefacto del parte diario puede seguir declarando la atribución ausente.
- El tri-estado de `position_open` **en el motor de dictamen** queda para `.157` (aquí solo se
  declara el hueco del parte).
- Tag **anotado, unsigned**.

## 11. Freeze

El bump mueve `apps` —el `meta.bump` de los **13** CLIs vive en `apps/api-python/scripts`— y
`packages` (lector, monitor, parte diario y `@bolsa/shared`) ⇒ el pin PAPER se **re-ancla** al
árbol del sello para que el run de las 18:00 no aborte con `TREE_MOVED`; `npm run window:freeze` ⇒
**`freeze OK`** y `npm run window:test` **50 passed**.

## 12. Publicación

Se publica como `v2.88.156-beta` (anotado, unsigned) sobre el commit de **re-anclaje del pin**,
inmediatamente posterior al commit del sello, igual que en `.154`/`.155`: el gate
`window:freeze` del job `shared` es **fail-closed** y el tag no puede apuntar a un commit cuyo
pin no case con su árbol.

**Cita POST-TAG — pendiente de la corrida del tag.** Este documento **no** declara ningún run
verde: la cita se añade **después** de que `Release tag CI` termine sobre `v2.88.156-beta`.
Hasta entonces, el sello está **implementado y verificado en local**, no certificado por CI.
