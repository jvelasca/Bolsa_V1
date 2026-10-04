# Evidencia `v2.88.44-beta` — `AUTO · DÍA-D-3c`: **de dónde nace la pérdida** (mecanismo de salida × coste aplicado × calidad de entrada), sin tocar motor

**Objeto:** el **siguiente chat, un auditor externo, o un Cursor distinto**. No es el historial (`PROJECT_STATE.md`).

**Producto:** `V2.88.44-beta` · **Package:** `2.11.44-beta` · **AsOf:** 2026-10-04 · **Nature:** `INVESTIGACION` · **Fase:** `V2.96 DIA-D AUTO LOSS ORIGIN` · **Δ motor = 0**.

**Schemas:** `dia-d-loss-origin-v1` (`KIND = "DIA_D_AUTO_LOSS_ORIGIN"`) y `dia-d-multi-cycle-ledger-v2` (aditivo sobre `-v1`). **Alembic:** head `048_journal_entry_dedupe_key` — **SIN migración** (leer no escribe esquema). **Contrato HTTP:** sin cambios (todo es Python puro; no viaja por OpenAPI).

**Padres:** [`v2.88.43`](../v2.88.43/README.md) (bootstrap de ciclos: banda TOTAL venue × sampling) → [`v2.88.42`](../v2.88.42/README.md) (de punto a banda: venue) → [`v2.88.41`](../v2.88.41/README.md) (atribución multirregimen).

**Packages de evidencia (no versionados, `.gitignore`):**

- `operability_runs/dia-d-auto-band/draw-00…draw-11/multi-cycles.json` — `12` ledgers `dia-d-multi-cycle-ledger-v2` (con detalle de fricción y motivo de cierre).
- `operability_runs/dia-d-auto/multi-band-detail-2021_2026.json` — el plegado `v2_94` con `--cycle-detail` (banda del venue + `crossCheck`), reconstruido desde la BD local.
- `operability_runs/dia-d-auto/loss-origin-2021_2026.json` — el artefacto `dia-d-loss-origin-v1`.

---

## 0. Qué añade este sello (y qué NO)

`v2.88.41` dijo **cuánto** se pierde (`expectancyR = -0.0094`) por año/régimen. `v2.88.42`/`v2.88.43` dijeron **cuánto puede moverse** ese punto (venue × sampling). Este sello responde a la pregunta que faltaba, la del auditor: **de dónde nace la pérdida**. Tres ejes, medidos sobre el MISMO replay hermético por sorteo, sin tocar el motor:

| Eje | Pregunta | Unidad | Fuente (ya existente) |
| --- | --- | --- | --- |
| **1. Mecanismo de salida** | ¿por qué se cierra cada ciclo y cuánto aporta cada motivo? | `R` por `day_exit_reason` | `worker.journal_pairs()` (`position_close.reason`) |
| **2. Coste aplicado** | ¿cuánto `R` bruto se come la fricción (`applied_cost`) y cuánto queda neto? | `R` / divisa | `applied_cost_from_fills(reference_mid)` |
| **3. Calidad de entrada** | ¿cómo de adversa es la excursión D1 inmediata y cuánto slippage hay señal→ejecución? | `R` y `bps` | barras D1 del corpus PIT |

**NO** es una nueva estrategia ni un ajuste: es **medición/atribución**. Un ledger sin fricción capturada produce costes `UNKNOWN` (declarado), nunca `0`.

---

## 1. Afirmaciones falsables (cada una con su forma de romperse)

| # | Afirmación | Cómo se rompe (falsación) | Evidencia |
| --- | --- | --- | --- |
| **1** | **La banda del venue no se mueve:** `v2_94` reconstruye la banda `v2.88.43` **byte a byte** (`bands` + `validity` + `coverage`), sin más cambio que `meta.bump`. | Que la reconstrucción difiera del sello del venue. | Diff de `global`/`byYear`/`byRegime`/`byOperationalRegime`/`byYearByRegime`/`coverage` contra el sello `v2.88.43` ⇒ **idénticos**; única diferencia: `meta.bump` y la codificación del `note` heredado. |
| **2** | **Autochequeo `k=0`:** el sorteo 0 (producción) reproduce el sello `v2.88.41` (`expectancyR=-0.0094`, `93` ciclos, `REFUTED`, `STRONG`) y `crossCheck.evidenceDrift=False`. | Que el sorteo 0 mida otra cosa. | `crossCheck={available:true, evidenceDrift:false, driftedKeys:[]}`. |
| **3** | **El porcentaje dominante es el stop, pero su expectancy bruta es ~0:** `STOP_EJECUTADO` = `93.4 %` de los ciclos (`1003/1074`) con `expectancyR` bruta `-0.0034` (prácticamente nula); el motor no pierde en el movimiento del stop, pierde en su **fricción**. | Un bucket dominante con expectancy bruta claramente negativa (entonces la pérdida nacería en el precio). | `byExitMechanism[STOP_EJECUTADO]`: `cycles=1003`, `realizedRGross.expectancyR.mean=-0.0034` vs `realizedRNet.expectancyR.mean=-0.0598`. |
| **4** | **El grueso del `R` bruto negativo vive en `THESIS_EXIT`:** `38` ciclos (`3.5 %`) con `expectancyR` bruta `-0.7087` y `hitRate` `8.3 %`. | Que los `THESIS_EXIT` tengan expectancy bruta cercana a 0. | `byExitMechanism[THESIS_EXIT]`: `realizedRGross.total.mean=-2.3462`, `expectancyR.mean=-0.7087`, `hitRate.mean=0.0833`. |
| **5** | **La fricción más que dobla la pérdida bruta global:** bruto `-2.9462 R` vs neto `-8.0580 R` (suelo), con `frictionRTotal` `4.0994 R` y `frictionCostTotal` `3 117.52` de divisa por sorteo. | Que una reconstrucción «sin coste» reproduzca el bruto casi igual al neto. | `costImpact`: `realizedRGrossTotal.mean=-2.9462`, `realizedRNetTotal.mean=-8.0580`, `frictionRTotal.mean=4.0994`, `frictionCostTotal.mean=3117.5229`, `netIsLowerBound=true`. |
| **6** | **La entrada es inmediatamente adversa:** MAE D1 media `-0.7115 R` sobre una ventana de `3` barras; `55.87 %` de los ciclos excursionan por debajo de `-0.5 R` y `27.84 %` por debajo de `-1.0 R`. | Que la excursión temprana sea ~0 o positiva. | `entryQuality.adverseExcursion`: `meanR=-0.7115`, `medianR=-0.5784`, `shareBelowHalfR=0.5587`, `shareBelowOneR=0.2784`, `windowDays=3`, `measured=1074`. |
| **7** | **El slippage señal→ejecución es siempre positivo (nunca favorable):** media `10.38 bps`, `shareAboveZero=1.0`. | Que algún ciclo tenga slippage `<= 0` (o que el campo sea `0` fabricado). | `entryQuality.entrySlippageBps`: `mean=10.3846`, `median=10.5148`, `shareAboveZero=1.0`. |
| **8** | **Regla del hueco intacta:** un ciclo sin cierre medido es `SIN_MECANISMO`; con fricción no `COMPLETE` el neto es `None` + `netRealizedRGap`, **jamás** el bruto disfrazado de neto. | Un `netRealizedR` no nulo con `frictionMeasurement != COMPLETE`. | `SIN_MECANISMO` (5 ciclos) ⇒ `realizedRNet.total = None`, `cyclesUnmeasured = 5`; `test_friction_partial_yields_none_net_never_gross`. |
| **9** | **Determinismo:** dos corridas de `v2_96` sobre el mismo `--out-dir` ⇒ JSON **byte a byte idéntico**. | Que dos corridas difieran. | `sha256 118DBF65DC8A0E2E573FE35B09D94138D6295DCFB260B8D418C1070467F063AA`, `11 089 B` (reproducido). |
| **10** | **`Δ motor = 0`:** ningún fichero de motor cambia de comportamiento; la captura de detalle es una costura inerte con default `False`. | Que el árbol del motor cambie o que la costura altere el replay con `capture_cycle_detail=False`. | `git status` vacío sobre los ficheros de motor (el runner `v2_87` sólo gana la costura inerte, default `False`); **A/B antiguo vs nuevo byte a byte idéntico** (`C208B2DE…`); el sha del artefacto congelado de `replay-repro` queda como gate de CI por tag. |

---

## 2. Medición real (`PostgreSQL`, `K = 12` sorteos del venue, años `2022-2025`)

**Cobertura:** `1074` ciclos totales · `1058` con fricción `COMPLETE` (`16` `PARTIAL`, `0` `UNKNOWN`) · `detailCaptured = true` · `12` sorteos.

### 2.1 Mecanismo de salida (`byExitMechanism`)

| Mecanismo | Ciclos | Sorteos con celda | R bruto total (media) | Expectancy bruta | R neto total (media) | Expectancy neta | HitRate | Fricción |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `STOP_EJECUTADO` | `1003` (93.4 %) | `12/12` | `-0.7186` | `-0.0034` | `-5.3355` | `-0.0598` | `0.4925` | `993` COMPLETE / `10` PARTIAL |
| `THESIS_EXIT` | `38` (3.5 %) | `11/12` | `-2.3462` | `-0.7087` | `-2.5012` | `-0.7525` | `0.0833` | `38` COMPLETE |
| `TIME_EXIT` | `28` (2.6 %) | `12/12` | `-0.3157` | `-0.0897` | `-0.4297` | `-0.1337` | `0.3690` | `27` COMPLETE / `1` PARTIAL |
| `SIN_MECANISMO` | `5` (0.5 %) | `5/12` | `+0.5730` | `+0.5730` | `None` (suelo) | `None` | `0.8000` | `0` COMPLETE / `5` PARTIAL |

**Lectura honesta:**

- El **stop domina en frecuencia** (`93.4 %`) pero su **expectancy bruta es ~0** (`-0.0034 R`): el stop no es «un sangrado por movimiento», es el punto donde el ciclo medio deja de ganar dinero y empieza a pagar fricción (su expectancy **neta** cae a `-0.0598 R`, un factor `~18×` sobre el bruto del bucket).
- El **grueso del `R` bruto negativo lo aportan los `THESIS_EXIT`** (`-0.7087 R/ciclo`, `hitRate` `8.3 %`): pocos ciclos, pero carísimos — es la **cola** donde nace la pérdida bruta.
- `TIME_EXIT` añade una pérdida pequeña y muy dispersa (`-0.0897 R/ciclo`).
- `SIN_MECANISMO` son `5` ciclos con cierre **no medido** en un subconjunto de sorteos: se declaran, **no** se les inventa mecanismo ni neto.
- **Aviso de suma:** la suma de brutos por mecanismo (`-2.8075`) **no** coincide con el bruto global (`-2.9462`, dif. `-0.1387`, `~4.7 %`) porque cada bucket se pliega sólo sobre los sorteos en que aparece (`drawsWithCell`) y las medias por sorteo se componen distinto. Se declara; no se cuadra a mano.

### 2.2 Coste aplicado (`costImpact`)

| Métrica | Media (sobre `12` sorteos) | min | max |
| --- | --- | --- | --- |
| `realizedRGrossTotal` | `-2.9462` | `-16.8590` | `+10.8568` |
| `realizedRNetTotal` (**suelo**) | `-8.0580` | `-23.7367` | `+6.3491` |
| `frictionRTotal` | `4.0994` | `3.3097` | `4.7815` |
| `frictionRMean` (por ciclo) | `0.0458` | `0.0432` | `0.0483` |
| `frictionCostTotal` (divisa) | `3 117.5229` | `2 395.9216` | `3 461.5970` |

**Reglas duras:** `netIsLowerBound = true` (`16` ciclos sin fricción `COMPLETE` ⇒ el neto es un **suelo**, `netUnmeasuredCycles = 16`). La fricción se mide contra el **mid de referencia del simulador** (`applied_cost`), no contra un precio de mercado: es el coste que **este venue** aplicó, no el de un broker real.

### 2.3 Calidad de entrada (`entryQuality`)

| Métrica | Valor |
| --- | --- |
| Ventana MAE (`entryAdverseWindowDays`) | `3` barras D1 |
| MAE temprana media / mediana | `-0.7115 R` / `-0.5784 R` |
| Cuota `< -0.5 R` | `55.87 %` |
| Cuota `< -1.0 R` | `27.84 %` |
| Slippage señal→ejecución (media / mediana) | `10.38 bps` / `10.51 bps` |
| Cuota slippage `> 0` | `100 %` |

**Lectura:** más de la mitad de los ciclos se pone en contra `> 0.5 R` **antes** de tener opción a trabajar; y la ejecución **siempre** paga algo (`10.4 bps` de media). Combinado con §2.2 (fricción), el diagnóstico es que la pérdida nace **en la entrada y en el coste**, no en un stop que dispare demasiado pronto.

### 2.4 Veredicto de la fase

Cada uno de los tres ejes tiene respuesta con `n` suficiente (`1074` ciclos) y **`fragility` explícita** (los cuatro buckets se marcan `fragile`: `few_cycles_per_draw` y/o `net_partial`), de modo que ninguna celda con `n` pequeño se cita como evidencia fuerte. **`CONFIRMED` NO se emite:** sigue reservado a evidencia PAPER.

---

## 3. Verificación (gates)

| Gate | Resultado |
| --- | --- |
| `pytest` DÍA-D (app `test_dia_d_*.py` + `test_dia_d_bump_guard.py`) | **120 passed** (`v2.88.43 = 110`; **+10**) |
| `pytest` `test_dia_d_loss_origin.py` | **9 passed** (taxonomía, precedencia, ledger v2, `PARTIAL→None`, `None != 0`, plegado, determinismo) |
| `ruff check` | limpio |
| `lint-imports` (`import-linter`) | **4 kept / 0 broken** |
| `mypy` | limpio |
| `contract:check` | OK (sin cambios de DTO) |
| `pnpm window:test` | **25/25** |
| `test_dia_d_bump_guard.py` | OK (incluye `v2_96`; `meta.bump` alineado a `2.11.44-beta`) |
| Determinar. `v2_96` | byte a byte idéntico (`sha256 118DBF65…`, `11 089 B`) |
| **Costura inerte (A/B)** | `v2_87` antiguo (`02607b2e`) vs nuevo (`50240f97`) con el MISMO entorno/fixture: artefacto **byte a byte idéntico** (`sha256 C208B2DE…`, `3 453 282 B`) ⇒ `capture_cycle_detail=False` no cambia la salida. |
| `Δ motor = 0` | `git status` vacío sobre los ficheros de motor; costura `v2_87` inerte con default `False` (probado A/B) |

---

## 4. Límites declarados (NO se cierran aquí)

- **Mecanismo = motivo decisorio** (`day_exit_reason`), no la trayectoria: un cierre por stop con `MAE` previa puede ser «stop» por etiqueta. No se reinterpreta.
- **`frictionR` es aproximada**: `friction / (|entry − stop| × qty)`; si falta stop o qty ⇒ hueco, no `0`.
- **MAE en D1 (entre días)**: el día de entrada puede incluir excursión previa al fill; no es intradía.
- **`Σ` por mecanismo ≠ global** (§2.1): se declara, no se cuadra.
- **Replay/OOS ≠ PAPER**: no sustituye la ventana PAPER real (`P3-2`/`P3-3` **ABIERTAS**).
- **Ciclos no IID** (block/regime bootstrap) sigue **P3**; aquí sólo se declara.
- **`n >= 5`** sigue heurístico; la evolución a `sample_quality` es posterior.
- **`CONFIRMED`** reservado a evidencia PAPER.

---

## 5. Cómo se reproduce

```bash
# 1) Regenerar los 12 sorteos con detalle de fricción + motivo de cierre (reutiliza los draws existentes)
uv run --no-sync python apps/api-python/scripts/v2_94_dia_d_multi_band.py \
  --reuse --cycles --cycle-detail \
  --out-dir operability_runs/dia-d-auto-band

# 2) Plegar los 12 ledgers al artefacto de origen de pérdida
uv run --no-sync python apps/api-python/scripts/v2_96_dia_d_loss_origin.py \
  --out-dir operability_runs/dia-d-auto-band \
  --out operability_runs/dia-d-auto/loss-origin-2021_2026.json

# 3) Dos corridas deben dar el mismo sha256 (determinismo)
```

---

## 6. Sello

- **Añadidos:** [`dia_d_exit_mechanism.py`](../../../../packages/py/application/src/bolsa_application/dia_d_exit_mechanism.py), [`dia_d_loss_origin.py`](../../../../packages/py/application/src/bolsa_application/dia_d_loss_origin.py), [`v2_96_dia_d_loss_origin.py`](../../../../apps/api-python/scripts/v2_96_dia_d_loss_origin.py), [`test_dia_d_loss_origin.py`](../../../../packages/py/application/tests/test_dia_d_loss_origin.py), `docs/engineering/evidence/v2.88.44/README.md`.
- **Modificados:** `dia_d_longitudinal.py` (`early_excursion_for_cycle`), `dia_d_multi_sampling.py` (ledger `-v2`), `v2_87` (costura `capture_cycle_detail`), `v2_91`/`v2_93`/`v2_94` (`--cycle-detail`/`--entry-window-days`), `v2_89`/`v2_90`/`v2_92`/`v2_95` (`meta.bump`), `test_dia_d_bump_guard.py`, `test_dia_d_multi_sampling.py`, `package.json`, `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`.
- **`Δ motor = 0`:** ningún fichero de motor tocado.
- **Commits locales:** funcional **`50240f97`**; re-anclaje del freeze del runner **`7a1efac4`** (`apps` `429229c9…` · `packages` `1bfb752c…`); docs **`c1646d3a`**.
- **Tag:** `v2.88.44-beta` → objeto **`ffd88e67`**, commit **`c1646d3a`** (tip `main`).
- **`Release tag CI` run [`37191651360`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37191651360) VERDE:** `11 jobs success` + `playwright` integrado `skipped` por diseño; `certify` `success`; `python` `4479 passed / 45 skipped` (**+10** sobre `v2.88.43`); `replay-repro` `REPRODUCIDO` `1E3ADAC2…` (`3 340 728 B` LF / sello `3 445 622 B` CRLF) ⇒ el artefacto congelado no se movió, confirmando en el CI real la inercia de la costura. `main`: [`Frontend`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37191649993) · [`Python`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37191650010) · [`Fase 2`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37191649991) · [`Optimize`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37191649995) · [`Gitleaks`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37191650016) VERDE.
