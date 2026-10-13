# Evidencia `v2.88.125-beta` — pasos 3/4a/4b del veredicto: DÍA-D por valor/ciclo, certificador de la ventana PAPER y auditoría de olas UI 2..6

> **Bump:** `2.11.124-beta` → **`2.11.125-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87`, de los 9 CLIs `v2_89`…`v2_97` y del CLI nuevo `v2_98`; guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) verde).
>
> **Naturaleza:** incremento **mixto** — **funcional aditivo** (`paso 3`: read-model + `packages/shared`/`apps/web`) + **verificación/servicio** (`paso 4a`: certificador nuevo, dominio puro) + **auditoría + censo** (`paso 4b`: UI). **`Δ decisión = 0`** (sin umbrales/reparto/`TOP_N`/régimen/selección/protección/ejecución) · **`Δ motor de decisión = 0`** (se toca el **read-model** del monitor y el **dominio puro nuevo** del certificador, no el motor) · **SIN migración** (head `053_dia_d_cycle_verifications`) · **SIN cambio de contrato HTTP** (H1 reutiliza el campo `reason` ya existente; H4 vive en `packages/shared`). Tag **unsigned**.
>
> **Alcance del commit:** este commit **entrega la cadena `v2.88.123` → `v2.88.124` → `v2.88.125`** (los tres sellos tienen su propia evidencia: [`v2.88.123`](../v2.88.123/README.md), [`v2.88.124`](../v2.88.124/README.md)); `package.json` sella el final de la cadena (`2.11.125-beta`).

Cierra los **tres frentes restantes** del veredicto de auditoría: `paso 3` (cierre funcional DÍA-D), `paso 4a` (certificador de la ventana PAPER) y `paso 4b` (olas UI 2..6) — **declarando** lo que **no** queda cerrado.

---

## 1. `paso 3` — recorrido funcional de DÍA-D por valor y ciclo

### 1.1 H1 — corrección: `CYCLE_CLOSED` deja de afirmar `"flat"`

**Antes:** `packages/py/application/src/bolsa_application/auto_operational_monitor.py` publicaba `closed.get("reason", "flat")` y `cycles_from_fills` **nunca** emite `reason` ⇒ la etapa «Resultado» afirmaba un cierre por libro plano que **ninguna** evidencia sostenía.

**Ahora:**

```js
reason = closed.get("reason")
if reason is None:
    reason = exit_reason
```

`_cycle_closed_step(..., exit_reason=…)` recibe el `exitReason` del **hecho durable `SETTLEMENT` del MISMO ciclo** (`_get(settlement, "exitReason")`). Si no consta ninguno, el hecho viaja `value: null` con medición `UNKNOWN` (política `UNKNOWN ≠ 0` / «Sin dato todavía») — **nunca** un motivo de relleno. El campo `reason` ya existía ⇒ **sin cambio de forma del DTO** (no toca contrato).

Cubierto por 2 tests en [`test_auto_operational_monitor.py`](../../../../packages/py/application/tests/test_auto_operational_monitor.py) (motivo durable presente ⇒ lo publica; sin motivo durable ⇒ hueco, no `"flat"`).

### 1.2 H2/H7 — verificación (PG real, gate `AUTO_DIA_D_TRACE_PG_REQUIRED=1`)

[`test_auto_dia_d_trace_pg.py`](../../../../apps/api-python/tests/test_auto_dia_d_trace_pg.py) ampliado (mismo arnés de **proceso real** del Golden Day): añade (i) `SETTLEMENT.facts.exitReason == "time_exit"`, (ii) `decision.reasonCodes` no vacío, y (iii) un caso nuevo `..._per_value_and_cycle_pg` con **≥2 instrumentos** que exige `cycleId`/`settlementId` únicos y sin herencia, `SIGNAL.facts.instrumentId == cycle.instrumentId`, `exitReason == "time_exit"`, `reasonCodes` no vacío, **P&L cierre vs liquidación por ciclo** y suma de ciclos == libro aplicado.

### 1.3 H4 — la etapa `DECISION` consume `reasonCodes`

[`auto-operation-story.ts`](../../../../packages/shared/src/cognitive/auto-operation-story.ts) gana `buildDecisionStage`: si existe `cycle.decision` (hecho durable `auto_entry_decision`) la etapa `DECISION` se **enciende** y publica `reasonCodes` **MEDIDO**; sin `decision` ⇒ `NOT_MEASURED` (no se iguala a `SELECTION`/TOP-N); con `decision` sin `reasonCodes` ⇒ hecho presente con el motivo declarado `UNKNOWN`. Tests en `auto-operation-story.test.ts` y `auto-operation-story-panel.test.tsx`.

### 1.4 H3/H5/H6 — DECLARADOS (no implementados)

[`deuda-cierre-dia-d-h3-h5-h6-2026-10-13.md`](../../deuda-cierre-dia-d-h3-h5-h6-2026-10-13.md): **H3** la «señal de salida» no tiene etapa propia (`EXIT` `foldedInto: "SETTLEMENT"`); **H5** el monitor no admite consulta por instrumento (solo `cycleId`/`limit`); **H6** el CTA manual verifica el **#1 de Finalistas**, no la estrategia **ejecutada** del ciclo. Cada uno con `file:line` y **criterio de aceptación falsable**. Son contrato/UX con blast radius mayor; **no** son fugas de dato.

---

### 1.5 Endurecimiento de S1 (`test_auto_estudio_universe_coverage_pg.py`)

Al verificar el lote PG completo se observó que S1 era **sensible al estado preexistente** de la BD: usaba `add_to_estudio` (anexaba el lote al ESTUDIO existente), así que con un ESTUDIO/catálogo grande el universo a recorrer crecía y el bucle podía no alcanzar los valores sembrados dentro del presupuesto de sondeo (60 s) ⇒ **parpadeo real**. Se **fija ESTUDIO al lote sembrado** (`set_estudio`, no `add_to_estudio`): el universo certificado es **exactamente** lo sembrado (determinista, acotado, independiente del catálogo y de otras pruebas), y se restaura en el `finally`. No debilita la certificación (los valores sembrados siguen entrando por el MISMO camino) y elimina la dependencia de estado.

---

## 2. `paso 4a` — certificador de la ventana PAPER (`P3-2`/`P3-3`, ADR-046)

- **Función pura** [`certify_paper_window`](../../../../packages/py/application/src/bolsa_application/paper_window_certification.py) + CLI read-only [`v2_98_paper_window_certification.py`](../../../../apps/api-python/scripts/v2_98_paper_window_certification.py).
- **Umbrales de fuente única:** importa `MARKET_WINDOW_MIN_DAYS/_EPISODES/_CYCLES` de [`operability_window.py:88-90`](../../../../packages/py/application/src/bolsa_application/operability_window.py) y **delega** en `window_gate` — **no** re-declara ni duplica el cómputo. Eje declarado: `market_window` (días de **calendario** / regímenes **distintos** / ciclos **medibles**).
- **`None ≠ 0`:** `PaperWindowMaterial.measured` distingue «fuente leída» de «fuente no leída»; si `measured=False` los conteos son `None` y el veredicto es `INCONCLUSIVE` **aunque** `window_gate` devuelva ceros. Un `READY` exige `measured=True` **y** los tres criterios.
- **Gobierno de honestidad:** test PG [`test_paper_window_certification_pg.py`](../../../../apps/api-python/tests/test_paper_window_certification_pg.py) **cableado en el paso DEDICADO de `lifecycle-pg`** con gate `PAPER_WINDOW_CERT_PG_REQUIRED` (PG presente ⇒ corre; sin PG ⇒ skip, pero con el gate a `1` un skip es fallo duro; guard anti-skip por log). En CI **no** hay ventana real ⇒ ejercita la rama honesta `INCONCLUSIVE`. Verifica que el certificador **no fabrica**: si la ventana no se alcanza, declara `INCONCLUSIVE` y el test **pasa**. Cablearlo (en lugar de declararlo en la línea base) mantiene el **censo en 0**.
- **Lo que NO se cierra:** la ventana **real** ≥4 días de **calendario** (sale de `sim_fill_finance_context.created_at` = reloj de pared) **no** es automatizable en CI ⇒ queda como **OPERACIÓN** del propietario. El certificador **declara**, no sustituye.

---

## 3. `paso 4b` — auditoría de olas UI 2..6

[`auditoria-ui-olas-2-6-2026-10-13.md`](../../auditoria-ui-olas-2-6-2026-10-13.md): re-verificación **itemizada** contra el árbol actual (no contra el tag `v2.88.90`).

| Ola | Pantalla | Estado | Hallazgos abiertos |
|-----|----------|--------|--------------------|
| 1 | Confirmar · Hoy | **DONE** (sellada) | — |
| 2 | Cartera · Historial | **DONE** | — |
| 3 | Mercado | **DONE** | `O3-01` (P2, diseño) |
| 4 | Asesor | **DONE** | `O4-01`/`O4-02` (P2, diseño); `O4-03`/`O4-04` **cerrados** (mecánicos) |
| 5 | Chrome · palette | **DONE** | `O5-01` (P2, parcial tras W3) |
| 6 | Consola avanzada | **ABIERTA** | `O6-01`/`O6-02`/`O6-03` (P2: nivel 3 explícito) |

⇒ «olas 2..6 abiertas» queda **falsado para 2..5** y **acotado a la ola 6**.

- **Censo falsable ampliado:** +17 superficies nuevas por ola en [`barrido-global-first-level.test.tsx`](../../../../apps/web/src/features/barrido-global-first-level.test.tsx) (`WAVE_TOKEN_SURFACES` + `WAVE_DASH_SURFACES`), con las exclusiones **declaradas** (colisión de subcadena TS en `history-page`, gate por fichero en `operational-console-sections`).
- **Residuos cerrados:** `O4-03` (`—` del helper de nivel 3 → `ABSENT_DATA_TECHNICAL_DASH`) y `O4-04` («Ledger lab» → «Registro de laboratorio»), semántica idéntica.
- **Deuda preexistente declarada:** `heading-order` en 11 rutas L1; `axe` solo con mocks (Playwright integrado `opt-in`).

---

## 4. Verificación (local)

| Comprobación | Resultado |
|--------------|-----------|
| `ruff check` (todo lo tocado) | **All checks passed** |
| `mypy` (lista CI: `packages/py/*/src` + `apps/api-python/src`) | **Success: no issues found in 554 source files** |
| `import-linter` (`packages/py/.importlinter`) | **4 kept, 0 broken** |
| `pytest packages/py/application/tests` (suite completa) | **2727 passed** |
| Focal read-model + certificador + gate de ventana (no-PG) | **95 passed** |
| Paso PG DEDICADO de `lifecycle-pg` (5 ficheros, 5 gates ON, `-rs`) | **18 passed** (sin `skipped`) |
| `vitest` censo + primer nivel tocado | **328 passed** (`barrido-global-first-level` **320**) |
| `pnpm --filter @bolsa/web typecheck` / `lint` | **OK** / **0 errores** (23 warnings preexistentes) |
| `contract:check` | **OK** (sin cambio de contrato) |
| Censo de selección (`test_selection.py --missing`) | **0 sin declarar** |
| Guardián de bump (`test_dia_d_bump_guard`) | **1 passed** |
| `alembic heads` | `053_dia_d_cycle_verifications` (**sin migración**) |

---

## 5. Huecos declarados (NO cerrados; sin tocar el motor)

1. **H3** — la «señal de salida» sigue plegada en `SETTLEMENT` (no hay etapa `EXIT` propia).
2. **H5** — el monitor sigue **sin** consulta por instrumento.
3. **H6** — el CTA manual sigue verificando el **#1**, no la estrategia **ejecutada**.
4. **Ventana PAPER longitudinal (`P3-2`/`P3-3`)** — el certificador **existe**, pero la ventana real sigue **`NO MEDIDO`** (OPERACIÓN: ≥4 días de calendario / ≥2 episodios / ≥32 ciclos). **No** se emite `CONFIRMED` (reservado a decisión humana).
5. **Ola 6 (Consola avanzada)** — sigue abierta (nivel 3 explícito pendiente); `heading-order` (11 rutas L1) y `axe` (solo con mocks) siguen como deuda preexistente.
6. **P&L** — el DÍA-D certifica **identidad de fuentes y motivos**, no la **rentabilidad** ni la **magnitud** del resultado.
