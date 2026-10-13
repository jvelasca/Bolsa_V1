# Evidencia `v2.88.121-beta` — remediación de la re-auditoría `v2.88.118 → v2.88.120` (H1–H5)

> **Sello:** `v2.88.121-beta` (base `v2.88.120-beta`).
> **Bump:** `2.11.120-beta` → **`2.11.121-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87` y de los 9 CLIs `v2_89`…`v2_97`; guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) verde).
> **Naturaleza:** sello **corrector aditivo** · **`Δ motor ≠ 0`** **acotado al dominio puro de banda/informe + UI** (`dia_d_multi_uncertainty`, `estudio_audit`, `estudio-audit-*`, `auto-operacion-page`) · **`Δ decisión = 0`** (no toca umbrales, reparto, `TOP_N`, régimen ni protección) · **SIN migración** (head `053_dia_d_cycle_verifications`) · **contrato HTTP ampliado** (campos `linkedCycles`/`unlinkedCycles`/`duplicateCycles` aditivos en `EstudioAuditSignalDto`).
> **Cierra:** **`1`** fallo de corrección (**H1**) + **`3`** huecos de trazabilidad (**H2–H4**) + **`1`** errata cosmética (**H5**) de la re-auditoría independiente [`auditoria-externa-v2.88.118-120-2026-10-13.md`](../../auditoria-externa-v2.88.118-120-2026-10-13.md).
> **Fecha:** 2026-10-13.

---

## 1. Qué cambia (corrección + trazabilidad)

| Pieza | Fichero | Contenido |
| --- | --- | --- |
| **H1 · muestra efectiva** | [`dia_d_multi_uncertainty.py`](../../../../packages/py/application/src/bolsa_application/dia_d_multi_uncertainty.py) | `band_validity` mide la **muestra efectiva** (`effective_draws = int(stats["n"]) if stats is not None else 0`) y la guarda de **máxima precedencia** pasa a `if no_effective_sample:` (`effective_draws < MIN_DRAWS_FOR_BAND = 2`) ⇒ `status = "NOT_MEASURED"`, `reason = "no_effective_sample"` (`STATISTICAL_CONFIDENCE_NO_SAMPLE_REASON`), `missing = list(gaps)`, `established = False` — **aunque** `independent_sample` declare procedencia completa. La banda financiera [`oos_finance_band.py`](../../../../packages/py/application/src/bolsa_application/oos_finance_band.py) delega en la MISMA `band_validity` ⇒ hereda el fix (las dos bandas **no pueden divergir**). |
| **H2 · recuentos que cuadran** | [`estudio_audit.py`](../../../../packages/py/application/src/bolsa_application/estudio_audit.py) | `_cycles_for_symbol` devuelve `(rows, unlinked, duplicates)`; `_signal_for_symbol` recibe `linked_cycles`/`unlinked_cycles`/`duplicate_cycles` y los expone como `linkedCycles`/`unlinkedCycles`/`duplicateCycles`. Invariantes: `linkedCycles == len(cycles[])` y `linkedCycles + unlinkedCycles + duplicateCycles == cycles`. Los huecos se declaran en `unmeasured` (`señal: N ciclo(s) sin cycleId …` / `… con cycleId repetido …`). |
| **H3 · orden natural + dedup** | [`estudio_audit.py`](../../../../packages/py/application/src/bolsa_application/estudio_audit.py) | `_natural_sort_key` ordena por tramos numéricos (`cyc-2` < `cyc-10`, no lexicográfico); se ordena por `(cycleId natural, firma de la fila)` **antes** de deduplicar por `cycleId` ⇒ dos ciclos con la MISMA clave no eligen «ganadora» por permutación. |
| **H3 · key React estable** | [`estudio-audit-panel.tsx`](../../../../apps/web/src/features/auto-monitor/estudio-audit-panel.tsx) | `key={`${cycle.cycleId}#${index}`}` en la lista de ciclos (evita claves repetidas) y el recuento usa `describeSignal(value.signal, cycles.length)`. |
| **H4 · UI fuera de ventana** | [`auto-operacion-page.tsx`](../../../../apps/web/src/features/auto/auto-operacion-page.tsx) | El hueco distingue **cargando** (`data-testid="auto-operacion-loading"`) de **no-encontrado/fuera de ventana** (`data-testid="auto-operacion-sheet-hole"`, declara el `cycleId` pedido y la ventana actual). |
| **H4 · UI · helper** | [`estudio-audit-view.ts`](../../../../apps/web/src/features/auto-monitor/estudio-audit-view.ts) | `describeSignal(signal, listedCycles)` puro: `N de M ciclos enlazables · K medidos [· U sin enlazar] [· D repetidos]`; compatibilidad con artefacto antiguo sin `linkedCycles` (cae al nº listado). |
| **DTO read-only** | [`auto_estudio_audit.py`](../../../../apps/api-python/src/bolsa_api/api/v1/routes/auto_estudio_audit.py) | `EstudioAuditSignalDto` gana `linkedCycles`, `unlinkedCycles`, `duplicateCycles` (`= 0` por defecto, aditivos). |
| **Contrato FE/BE** | [`schema.d.ts`](../../../../apps/web/src/api/schema.d.ts) · [`openapi.json`](../../../../apps/web/api/openapi.json) | Regenerados con `contract:gen` (diff **acotado** a `EstudioAuditSignalDto`). |
| **H5 · errata** | [`evidence/v2.88.119/README.md`](../v2.88.119/README.md) | Corregido: `115`→`v2`, `116`→`v3`, `117`→`v4`; `118` endureció **sin** subir esquema (antes atribuía `v1→v4` a los sellos 115–118). |

---

## 2. Hallazgo H1 — el medio-estado `MEASURED` con `n = 1`

**Antes (`v2.88.118`):** la guarda `no_effective_sample` sólo cubría `stats is None`. Con **1 sorteo**
(`stats` no-`None` pero `< MIN_DRAWS_FOR_BAND = 2`) + `independent_sample` + procedencia completa, la
banda emitía `status = "MEASURED"` / `established = False`: exactamente el medio-estado que el sello
`v2.88.118` decía haber eliminado. El doc afirmaba que `no_effective_sample` cubría «menos de
`MIN_DRAWS_FOR_BAND` sorteos»; el código sólo cubría «cero sorteos».

**Ahora:** la muestra es **efectiva** (no basta con que `stats` exista). Cualquier banda con
`effective_draws < MIN_DRAWS_FOR_BAND` declara `NOT_MEASURED` / `no_effective_sample` /
`established = False`, **por delante** de `venue_seeded`, `provenance_missing` y `provenance_incomplete`
(motivo más específico). `MIN_DRAWS_FOR_BAND` es una sola constante compartida por los dos módulos de
banda.

**Pruebas de corrección:**

- `packages/py/application/tests/test_oos_finance_band.py::test_h1_1_single_draw_blocks_measured_even_with_provenance`
- `packages/py/application/tests/test_dia_d_multi_uncertainty.py::test_h1_1_single_draw_does_not_establish_statistical_confidence`

---

## 3. Huecos de trazabilidad H2–H4

**H2 (conteo).** `signal.cycles`/`measuredCycles` podían **superar** `len(cycles[])` (contaban ciclos no
enlazables que la lista excluía). Ahora `signal` declara el desglose y se sostiene el invariante
`linkedCycles == len(cycles[])`.

**H3 (orden/dedup).** `rows.sort(key=lambda row: row["cycleId"])` era **lexicográfico** (`cyc-10` < `cyc-2`)
y **no deduplicaba** ⇒ orden no cronológico y claves React repetidas. Ahora orden **natural** + dedup
determinista por `cycleId` (desempate por firma; invariante bajo permutación).

**H4 (cobertura).** No había test del caso mixto enlazado/no-enlazado ni de navegación real del deep-link,
y el hueco no distinguía «cargando» de «fuera de ventana». Añadidos:

- `packages/py/application/tests/test_estudio_audit.py::test_signal_counts_linked_and_unlinked_and_matches_listing`
- `packages/py/application/tests/test_estudio_audit.py::test_duplicate_cycle_id_is_deduplicated_and_declared`
- `packages/py/application/tests/test_estudio_audit.py::test_cycles_are_sorted_naturally_not_lexicographically`
- `apps/web/src/features/auto/auto-pages.test.tsx` — «un ciclo fuera de la ventana se distingue del id ausente y declara el id pedido» + estado de carga
- `apps/web/src/features/auto/auto-nav.test.ts` — `autoOperacionHref`
- `apps/web/src/features/auto-monitor/estudio-audit-{view,panel}.test.*` — recuento y ciclos del panel

---

## 4. Delta de contrato (aditivo)

- `EstudioAuditSignalDto` gana `linkedCycles`, `unlinkedCycles`, `duplicateCycles` (opcionales en el
  esquema OpenAPI; siempre presentes en el payload del endpoint).
- **No** se añade ninguna ruta; los dos `GET /auto/estudio-audit[/{window}]` mantienen su forma y su modo
  `PRECOMPUTED_ARTIFACT`.

---

## 5. Verificación (local)

| Compuerta | Resultado |
| --- | --- |
| `ruff check packages/py apps/api-python --config pyproject.toml` | ✅ `All checks passed!` |
| `mypy` (lista exacta de CI: `domain`/`market`/`infrastructure`/`application`/`api-python`, `--follow-imports=silent`) | ✅ `Success: no issues found in 552 source files` |
| `lint-imports --config packages/py/.importlinter` | ✅ **4 kept, 0 broken** |
| `pytest packages/py/application/tests -q` | ✅ **2715 passed** (177.52 s) — **+5** sobre los `2710` del sello anterior |
| `pytest apps/api-python/tests -q` | ✅ **1003 passed**, **1 failed** — ver «fallo ambiental declarado» abajo |
| `pnpm --filter @bolsa/web test` | ✅ **2097 passed** (297 ficheros) — **+3** sobre los `2094` del sello anterior |
| `pnpm --filter @bolsa/web typecheck` | ✅ sin errores |
| `pnpm --filter @bolsa/web lint` | ✅ **0 errores** (23 warnings **preexistentes**, ajenos al diff) |
| `pnpm --filter @bolsa/web contract:check` | ✅ `openapi.json` y `schema.d.ts` coinciden con el commit |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py -q` | ✅ **1 passed** |
| `alembic heads` | `053_dia_d_cycle_verifications (head)` — **sin migración** |

**Fallo ambiental declarado (no disimulado):**
`apps/api-python/tests/chaos/live_a7/test_c3_crash_injection_recovery_worker.py::test_c3b_crash_after_resolve_put_no_double_on_relaunch`
falla **bajo la suite completa** por **concurrencia/timing real-PG** (`AssertionError: primer resolve no reclamó la fila: 'drained=0 resolved=0'`)
y **pasa en aislamiento** (re-ejecutado: `1 passed in 2.86s`); es **ajeno** al diff (banda/informe/UI). En
`v2.88.120` el par que fallaba era `test_lists.py::{test_lists_crud_flow,test_delete_list_with_items_does_not_violate_fk}`
(también ambiental) — este run **no** los reprodujo ⇒ el conjunto de fallos es **dependiente del entorno**,
no del sello. Total de tests idéntico entre sellos (1004).

---

## 6. Límites declarados

- **`Δ motor ≠ 0` acotado, `Δ decisión = 0`.** El cambio de motor vive en el **dominio puro** de banda
  (`dia_d_multi_uncertainty`) y de informe (`estudio_audit`) y en la UI; no toca motor de decisión ni
  ejecución. No cambia umbrales, reparto, `TOP_N`, régimen ni protección.
- **Cambio de forma de artefacto: NINGUNO.** `SCHEMA_VERSION` **no** sube (`dia-d-multi-band-v3`,
  `oos-finance-band-v4`): solo se endurece una rama semántica (**H1**) y se amplía el DTO de señal (**H2**).
  El endurecimiento de H1 puede degradar `statisticalConfidence` de artefactos con pocos sorteos — **es el
  objetivo** (antes declaraban un `MEASURED` falso); no re-mide ningún artefacto sellado. **Ningún artefacto
  sellado cambia:** la guarda vive en la rama `design == "independent_sample"`, y la banda publicada de
  `v2.88.119` (`finance-band-w32-k12.json`) es `design = "venue_draw"` (ya `statisticalConfidence =
  NOT_MEASURED` por diseño) ⇒ su `sha256(LF)` (`21d7159e…`) **se mantiene**.
- **No** se rellena el «porqué» (`C2`), **no** se emite `CONFIRMED` (reservado a la ventana PAPER,
  **`P3-2`/`P3-3` abiertos**, ADR-046), **no** se automatiza la lane diaria ESTUDIO.
- **Tag `unsigned`:** el tag anotado **no** está firmado.

---

## 7. Cita POST-TAG

**Tag `v2.88.121-beta` empujado** (anotado, **unsigned**; objeto `82dd7038` → commit de sello `0bb06f97`).
`origin/main` == `HEAD` == `0bb06f97`. `Release tag CI`
[**38383921714**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38383921714) — **verde en 11m40s**
(`createdAt` 2026-10-13T10:31:17Z → `updatedAt` 10:42:57Z), **12/12 jobs `success` + `certify`**
(`playwright (integrated E2E, opt-in)` = `skipped` por diseño). Lo decisivo: **`replay-repro (regenera el
artefacto del sello desde el fixture)`** cerró en **success** (`5m20s`) ⇒ el artefacto congelado **SE
REPRODUCE**, coherente con **`Δ decisión = 0`**; y `lifecycle-pg` cerró con **sin migración** (head
`053_dia_d_cycle_verifications`).

| Job | Conclusión | Duración |
| --- | --- | --- |
| `security` (gitleaks) | ✅ success | 11s |
| `shared` (build/typecheck/test) | ✅ success | 34s |
| `a7-gate` (chaos real-PG) | ✅ success | 53s |
| `lifecycle-pg` (Alembic + auth + golden restart) | ✅ success | 5m35s |
| `frontend` (typecheck/lint/test/build + contract:check) | ✅ success | 2m15s |
| `python` (ruff/imports/mypy/pytest offline) | ✅ success | 3m11s |
| `dr-verify` (battery DB_DR / TCP CI) | ✅ success | 50s |
| `playwright` (mock E2E) | ✅ success | 11m27s |
| `playwright` (integrated AUTO S5) | ✅ success | 3m19s |
| **`replay-repro`** (regenera el artefacto del sello) | ✅ **success** | 5m20s |
| `decision-spine` | ✅ success | 26s |
| `certify` (aggregate + artifact) | ✅ success | 4s |
| `playwright` (integrated E2E, opt-in) | ⏭️ skipped (diseño) | — |

**Nota (fallo local ≠ CI):** el único fallo que salió localmente
(`chaos/live_a7/test_c3_crash_injection_recovery_worker.py::test_c3b…`) **no** se reproduce en CI: el job
`a7-gate (A7 C3 chaos live_a7 · dedicated real-PG)` cerró **success** ⇒ confirma que era **timing local**,
no un defecto del sello.

CI de **rama** (`main`, `0bb06f97`): `Python CI`
[38383918195](https://github.com/jvelasca/Bolsa_V1/actions/runs/38383918195) · `Frontend CI`
[38383918212](https://github.com/jvelasca/Bolsa_V1/actions/runs/38383918212) · `Fase 2 scientific`
[38383918103](https://github.com/jvelasca/Bolsa_V1/actions/runs/38383918103) · `Optimize lab`
[38383918200](https://github.com/jvelasca/Bolsa_V1/actions/runs/38383918200) · `Gitleaks`
[38383918119](https://github.com/jvelasca/Bolsa_V1/actions/runs/38383918119) — **todos `success`**.
CI de **tag**: `Python CI` ([38383921707](https://github.com/jvelasca/Bolsa_V1/actions/runs/38383921707)) ·
`Frontend CI` ([38383921560](https://github.com/jvelasca/Bolsa_V1/actions/runs/38383921560)) ·
`Fase 2 scientific` ([38383921610](https://github.com/jvelasca/Bolsa_V1/actions/runs/38383921610)) ·
`Optimize lab` ([38383921534](https://github.com/jvelasca/Bolsa_V1/actions/runs/38383921534)) — `success`.
Tag anotado **sin firmar** (`unsigned`). **Sello CERRADO.**
