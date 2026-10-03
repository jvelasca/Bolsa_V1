# Entrega a auditoría externa MIA — `v2.88.41-beta` (DÍA-D · **atribución MULTIRREGIMEN 2021-2026**: año × régimen × resultado × excursión, 2026-10-03)

> **Objeto auditado:** tag anotado **`v2.88.41-beta`** → tag object **`7686bbf9`** → commit **`04397e12`**,
> versión **`2.11.41-beta`**, base del diff **`v2.88.40-beta`** → **`8c971c00`**, Alembic head
> **`048_journal_entry_dedupe_key`** (**sin migración**).
>
> **Identidad ESTABLE del producto:** el objeto se identifica por sus **árboles** `apps` `b0cd0174…` /
> `packages` `35a37d56…`, y el runner de la ventana los tiene **pineados** (`WINDOW_CONFIG.commit` =
> `85b00235`, el commit funcional). Cita el `tip` que veas en el clon, pero valida el objeto por esos
> dos hashes y por el `freeze OK` del dry-run.
> **Remote:** `https://github.com/jvelasca/Bolsa_V1` — **PÚBLICO** (el auditor clona sin credenciales).
> **Clase:** **capacidad del instrumento** de investigación sobre el motor AUTO, **advisory y read-only**.
> Convierte el diagnóstico de **un** año (`2022`, monorégimen `high_vol`) en una **base multirregimen**:
> **`Δ decisión motor = 0`**.
> **Punto de entrada del auditor:** **este documento** (no hay `arranque-auditor` separado: la entrega es
> autocontenida, igual que en `v2.88.40`).
> **Evidencia cruda:** [`evidence/v2.88.41/`](./evidence/v2.88.41/README.md) ·
> **plan ejecutado:** [`plan-v2-88-41-dia-d-multirregimen-2026-10-03.md`](./plan-v2-88-41-dia-d-multirregimen-2026-10-03.md) ·
> padre [`evidence/v2.88.40/`](./evidence/v2.88.40/README.md) (corrección semántica de la atribución).

---

## 0. Qué es y qué NO es esta entrega

**Es** la **extensión multirregimen** de la capa de **atribución** del `DÍA-D AUTO`: corre el MISMO
harness hermético **una pasada por año (2021-2026)**, con **universo `PIT` anclado al fin de cada año**,
y agrega el resultado por **año × régimen (agregado trial y operativo) × resultado (WINNERS/LOSERS) ×
excursión (MAE/MFE/captura/reversión)**. Responde, **de forma descriptiva y sin conclusión causal**, la
pregunta del dictamen: *¿el `-0.5011 R/ciclo` de `2022` es fenómeno de régimen, de selección de entradas,
de gestión de riesgo o de salida?*

**`Δ decisión motor = 0`.** Ningún fichero de motor aparece en el diff (`auto_simulation_worker.py`,
`auto_v2_entry.py`, `sim_durable_store.py`, `market_operability.py`, `replay_oos.py`,
`v2_87_replay_oos_durable_cycle.py`): el motor se **conduce** con stores en memoria desde el mismo
harness hermético de `v2_86`/`v2_87`/`v2_89`. No cambia ninguna decisión de inversión, ningún umbral
(`TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B), ninguna allocation ni ninguna migración. El artefacto congelado
de `replay-repro` es **idéntico** al sello `v2.88.40` (`1E3ADAC2…`).

**NO es** una capacidad nueva de motor, ni un cambio de umbrales, ni la ventana PAPER real. Sigue siendo
un instrumento **REPLAY/OOS** de **una sola estrategia** (`v283-window-a`); `P3-2`/`P3-3` siguen
**ABIERTAS**.

> **Trampa nº 1 — un año hueco NO es un `0`.** `2021` se **midió** (ventana efectiva `2021-09-15 →
> 2022-01-28`) y no aportó ningún ciclo medible ⇒ se declara en `coverage.yearsEmpty` y **no** aparece
> como fila en `byYear`. `2026` **no** se midió (`reason=sin_universo_pit`) y se declara en
> `coverage.yearsNotMeasured`. Ninguno de los dos se rellena con `0`.
>
> **Trampa nº 2 — la etiqueta de régimen SOLA no separa ganancia de pérdida.** `high_vol` agrega
> `-0.1492 R` sobre `80` ciclos, pero la matriz lo **descompone** en `2022 -0.5011` (53),
> `2023 +0.9151` (10), `2024 +1.7590` (4) y `2025 -0.1200` (13). Leer «`high_vol` = malo» es repetir el
> error que la matriz deshace.
>
> **Trampa nº 3 — el global `REFUTED` es por un margen MÍNIMO y por UN año.** Con `2022` incluido el
> global queda `-0.0094 R/ciclo` (prácticamente plano); `2023` (`+0.9151`), `2024` (`+1.5490`) y `2025`
> (`+0.1883`) son **positivos**. Además la concentración es `concentrated`: quitar **un** ciclo (el peor,
> `-12.02 R`) **voltea el signo** (`+0.0199`). No es «el motor pierde siempre».
>
> **Trampa nº 4 — `ALL ≠ LOSERS`** (heredada de `v2.88.40`). La fracción global de MAE `< -1R`
> (`51/93 = 54.84 %`) es de **TODOS** los ciclos. La pregunta se responde con `WINNERS`/`LOSERS`: en
> `high_vol`, `LOSERS` `93.33 %` frente a `WINNERS` `8.57 %`.
>
> **Trampa nº 5 — la matriz `byYearByRegime` sólo emite celdas MEDIDAS.** Una celda sin ciclos **no
> existe** en el JSON (nunca un `0`). Si un cruce no está en la tabla, es porque no se midió ese año en
> ese régimen.

---

## 1. El objeto y cómo obtenerlo

> **Dónde vive qué.** El **producto** auditado está **dentro del tag**; esta **entrega** (y el plan)
> viaja **POST-TAG en `main`**, porque el tag es inmutable y se selló antes de escribirse su cita. Clona
> `main` para **leer**, y `checkout` del tag para **verificar**. La cita del CI del tag (patrón `OBS-3`)
> vive en `main`, en el commit `6b6d5160`.

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1
# (A) leer la entrega        -> rama main (default tras el clon)
# (B) verificar el producto  -> el tag
git checkout v2.88.41-beta
git log --oneline -1                       # 04397e12 (re-anclaje del freeze; producto en 85b00235)
```

| Verdad | Valor |
| --- | --- |
| Tag anotado | `v2.88.41-beta` (tag object `7686bbf9`) → `04397e12` (producto funcional `85b00235`) |
| Versión (`package.json`) | `2.11.41-beta` (base `2.11.40-beta`) |
| Base del diff | `v2.88.40-beta` → `8c971c00` |
| Alembic head | `048_journal_entry_dedupe_key` — **SIN migración** |
| Delta tag-a-tag total | **17 ficheros, `+1751 / −22`** (incluye docs del post-tag de `v2.88.40` y `scripts/`) |
| Delta `packages/`+`apps/` | **8 ficheros, `+1159 / −4`** |
| `Δ motor` | **ningún** fichero de motor en el diff (verificado, §2) |
| `SCHEMA_VERSION` | (nuevo) **`dia-d-multi-v1`** · `KIND = DIA_D_AUTO_MULTI_ATTRIBUTION` |
| CI del tag | `Release tag CI` run **`37135395352`** — **VERDE** (11 jobs `success` + `playwright` integrado `skipped` por diseño; `certify` `success`; `python` `4446 passed / 45 skipped` = **+10**; `replay-repro` `REPRODUCIDO` `1E3ADAC2…`) |

**Composición del delta `packages/`+`apps/` (8 ficheros):**

| Fichero | Δ | Rol |
| --- | --- | --- |
| `packages/py/application/src/bolsa_application/dia_d_multi.py` | `+372` | dominio puro: agregación año × régimen × población × excursión (`dia-d-multi-v1`) |
| `packages/py/application/tests/test_dia_d_multi.py` | `+289` | 10 tests puros que muerden (cobertura, matriz, poblaciones, cota, determinismo) |
| `apps/api-python/scripts/v2_93_dia_d_multi.py` | `+493` | CLI del harness (1 pasada por año, PIT por año, fail-closed/fallback declarado) |
| `apps/api-python/tests/test_dia_d_bump_guard.py` | `+1` | guardián extendido a `v2_93` |
| `apps/api-python/scripts/v2_89_dia_d_auto_replay.py` | `+1/−1` | sólo `meta.bump` |
| `apps/api-python/scripts/v2_90_dia_d_feedback.py` | `+1/−1` | sólo `meta.bump` |
| `apps/api-python/scripts/v2_91_dia_d_longitudinal.py` | `+1/−1` | sólo `meta.bump` |
| `apps/api-python/scripts/v2_92_dia_d_attribution.py` | `+1/−1` | sólo `meta.bump` |

**Cómo recalcularlo en el clon (sin creerme nada):**

```bash
git diff --stat    v2.88.40-beta v2.88.41-beta                     # 17 ficheros, +1751/-22
git diff --numstat v2.88.40-beta v2.88.41-beta -- packages apps   # 8 ficheros, +1159/-4
git diff --name-only v2.88.40-beta v2.88.41-beta \
  -- "*auto_simulation_worker*" "*auto_v2_entry*" "*sim_durable_store*" \
     "*market_operability*" "*replay_oos*"                        # VACÍO = Δ motor 0
git diff --name-only v2.88.40-beta v2.88.41-beta -- "*alembic*" "*versions*"   # VACÍO = sin migración
git rev-parse "v2.88.41-beta^{}:apps" "v2.88.41-beta^{}:packages" # b0cd0174... / 35a37d56...
```

---

## 2. Firma de estado verificada **antes** de auditar

Corrida **por el auditor en su clon**, no heredada:

| Comprobación | Esperado |
| --- | --- |
| `git cat-file -t v2.88.41-beta` | `tag` (anotado) |
| `git rev-list -n 1 v2.88.41-beta` | `04397e12` |
| Árbol limpio en el checkout del tag | sí |
| Migración | **ninguna** (head `048_journal_entry_dedupe_key`) |
| Umbrales `TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B | intactos |
| Ficheros de motor en el diff | **ausentes** |
| Freeze del runner (`git rev-parse "HEAD:apps" "HEAD:packages"` en el commit funcional `85b00235`) | `b0cd017438c2a745cffa876f45211c021ba3309f` / `35a37d565b6d211306f6cb1aef87d6c8e12536aa` (el par del sello `v2.88.40-beta` era `22ca3e78…` / `f169415e…`; el pin se **re-ancló**) |
| Dry-run del runner | `freeze OK` |
| CI del tag | **11 `success`** + `playwright (integrated E2E, opt-in)` `skipped` por diseño; `certify` `success` (`Release tag CI` run `37135395352`) |

### 2.1 Cobertura y ventanas (medición real, PostgreSQL)

| Año | Medido | Ventana efectiva | Ciclos | `truncationReason` | `windowFallback` |
| --- | --- | --- | --- | --- | --- |
| 2021 | sí (**`yearsEmpty`**) | `2021-09-15 → 2022-01-28` | **0** | `null` | `null` |
| 2022 | sí | `2021-09-15 → 2023-01-27` | **53** | `null` | `null` |
| 2023 | sí | `2022-08-26 → 2024-01-29` | **10** | `null` | `null` |
| 2024 | sí | `2023-08-24 → 2025-01-29` | **8** | `null` | `null` |
| 2025 | sí | `2024-08-22 → 2026-01-29` | **22** | `null` | `null` |
| 2026 | **no** | — | — | — | razón `sin_universo_pit` |

Membresías elegibles por ancla (fail-closed): `2021=74`, `2022=74`, `2023=74`, `2024=75`, `2025=75`,
**`2026=0`** (el ancla `2026-12-31` excede la última barra durable ⇒ `eligible_at = 0`).

### 2.2 Resumen global

| Bloque | Valor |
| --- | --- |
| Veredicto | **`REFUTED`** (`negative_expectancy`) · `evidenceQuality=`**`STRONG`** |
| Muestra | **`93`** ciclos · `wins=45` / `losses=48` |
| Expectativa | `expectancyR=`**`-0.0094`** · `hitRate=0.4839` · `realizedRTotal=-0.8752` |
| Payoff | `avgWinR=+1.4123` · `avgLossR=-1.3423` · `payoffRatio=1.0522` · `identityGap=7.46e-17` |
| Concentración | **`concentrated`** · `expectancyWithoutWorstR=+0.0199` · `signFlipsWithoutWorst=true` · peor `5`=`-12.0241` · mejor `5`=`+15.9728` |

### 2.3 Por AÑO (resultado × excursión)

| Año | Ciclos | `expectancyR` | `hitRate` | `meanMaeR` | Captura media | `reversed` | `WINNERS` `< -1R` | `LOSERS` `< -1R` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 | 53 | **-0.5011** | 0.3396 | -1.3880 | 0.1429 | 7 | `2/18` (11.11 %) | `33/35` (94.29 %) |
| 2023 | 10 | +0.9151 | 0.7000 | -0.9817 | 0.3441 | 2 | `1/7` (14.29 %) | `2/3` (66.67 %) |
| 2024 | 8 | +1.5490 | 0.8750 | -0.4329 | 0.3619 | 0 | `0/7` (0.00 %) | `1/1` (100.00 %) |
| 2025 | 22 | +0.1883 | 0.5909 | -1.2039 | 0.2172 | 2 | `3/13` (23.08 %) | `9/9` (100.00 %) |

### 2.4 Por RÉGIMEN (agregado trial) y OPERATIVO

| Régimen (trial) | Operativo | Ciclos | `expectancyR` | `hitRate` | `meanMaeR` | `WINNERS` `< -1R` | `LOSERS` `< -1R` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `high_vol` | `HIGH_VOLATILITY` | **80** | **-0.1492** | 0.4375 | -1.2683 | `3/35` (8.57 %) | `42/45` (93.33 %) |
| `trend_down` | `BEAR_TREND` | 8 | +0.4576 | 0.6250 | -1.2547 | `2/5` (40.00 %) | `3/3` (100.00 %) |
| `range` | `SIDEWAYS` | 5 | +1.4795 | 1.0000 | -0.3648 | `1/5` (20.00 %) | `0/0` (n/d) |

### 2.5 Matriz AÑO × RÉGIMEN (sólo celdas medidas)

| Año | Régimen | Ciclos | `expectancyR` | `hitRate` | `meanMaeR` | `meanMfeR` | Captura media |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 | `high_vol` | 53 | -0.5011 | 0.3396 | -1.3880 | 1.2408 | 0.1429 |
| 2023 | `high_vol` | 10 | +0.9151 | 0.7000 | -0.9817 | 2.6828 | 0.3441 |
| 2024 | `high_vol` | 4 | +1.7590 | 1.0000 | -0.2879 | 3.9670 | 0.3808 |
| 2024 | `trend_down` | 4 | +1.3390 | 0.7500 | -0.5778 | 3.2547 | 0.3431 |
| 2025 | `high_vol` | 13 | -0.1200 | 0.4615 | -1.3028 | 1.8074 | 0.1880 |
| 2025 | `range` | 5 | +1.4795 | 1.0000 | -0.3648 | 3.4673 | 0.4212 |
| 2025 | `trend_down` | 4 | -0.4239 | 0.5000 | -1.9315 | 1.4689 | 0.0575 |

### 2.6 Severidad de MAE (población global `ALL`) y captura

`MAE` · `cycles=93` · `meanMaeR=-1.2186` · `minMaeR=-4.1436` · `< -1R` **51** (`54.84 %`) · `< -1.25R`
**41** (`44.09 %`) · `< -1.5R` **35** (`37.63 %`).
`captureRatio` · media `0.2022`, mediana `0.0`, máx `0.6237`, `aboveOneCount=0`; `reversedCount=11`;
`captureStudy.measuredCycles=91`, `notMeasuredCycles=2`; `leftOnTableR` medio `1.15 R`.

**Verificación local re-ejecutada en el momento del sello** (todos verdes): `pytest` DÍA-D **122 passed**
(`v2.88.40` = `112`; **+10** de `test_dia_d_multi.py`) · `ruff` All checks passed · `lint-imports`
**4 kept / 0 broken** · `mypy` **526 files** · `contract:check` OK · `tsc -b --noEmit` limpio · vitest
`auto-monitor` **4 ficheros / 14 tests** · `pnpm window:test` **25/25** · smoke `v2_93 --years 2022
--universe pit` (reproduce `-0.5011` / `53` / `33/35`) · determinismo dos corridas `2021-2026`
**idéntico** (`sha256 6ec29bfd…`, `90 473 B`).

---

## 3. Trampas declaradas: lo que el auditor **NO** debe concluir

1. **Un año hueco no es un `0`.** `2021` (medido vacío → `yearsEmpty`) y `2026` (no medido →
   `sin_universo_pit`) se **declaran**; ninguno se rellena, y un cubo sin ciclos no aparece en `byYear`.
2. **`high_vol` no es uniformemente negativo.** Agrega `-0.1492` sobre `80` ciclos, pero la matriz lo
   parte en años **positivos** (`2023`, `2024`) y **negativos** (`2022`, `2025`). La etiqueta sola no
   separa ganancia de pérdida.
3. **El global `REFUTED` es frágil.** `-0.0094 R/ciclo` con `2022` incluido; concentración
   `concentrated` (quitar **un** ciclo voltea el signo a `+0.0199`). No es un edge positivo sostenido,
   ni tampoco «el motor pierde siempre».
4. **`ALL ≠ LOSERS`.** El `54.84 %` de MAE `< -1R` es de **todos** los ciclos; la señal está en
   `LOSERS` (`93.33 %` en `high_vol`) y, sobre todo, en `WINNERS` (`8.57 %`).
5. **La matriz sólo emite celdas medidas.** Un cruce año × régimen ausente es un cruce **no medido**,
   no un `0`.
6. **`captureRatio > 1` es posible y no es bug** (cierre por encima del MFE D1, ruido intrabar); se
   declara en `aboveOneCount` (aquí `0`), no se recorta.
7. **La regla del hueco no se relaja.** Sin muestra, medias y fracciones son `None`/`NOT_MEASURED`
   (**nunca** `0`); un cubo sin ciclos medibles no aparece.
8. **La atribución es DESCRIPTIVA, no causal.** Descompone la muestra medida; no explica el mercado ni
   el futuro, ni decide H1-H4 (entrada/riesgo/gestión/salida).
9. **Las muestras por año son pequeñas.** `2023`/`2024`/`2025` tienen `10`/`8`/`22` ciclos: la lectura
   por celda es **indicativa**, no concluyente.
10. **El artefacto del barrido es gitignored.** Vive en `operability_runs/dia-d-auto/*.json`; un tercero
    lo **regenera** (§5), no lo hereda.
11. **Este sello mueve el árbol** `apps`/`packages`, así que el runner de la ventana se **re-ancló** a
    los hashes del commit funcional `85b00235` (`b0cd0174…` / `35a37d56…`); dry-run `freeze OK`.
12. **La entrega y la cita del CI son POST-TAG (en `main`, commit `6b6d5160`).** El sello es `04397e12`
    (producto `85b00235`); el pin del freeze es `85b00235`; el **CI del tag** es la run `37135395352`
    (**VERDE**).

---

## 4. Alcance sugerido: lo que queremos consensuar con el auditor

**P1.** **Cobertura declarada.** ¿`yearsMeasured ∪ yearsNotMeasured = yearsRequested`? ¿Cada año no
medido lleva `reason`, y **ningún** año se rellena con `0`? ¿`2026` fail-closed por ancla PIT futura es
la lectura correcta?

**P2.** **Consistencia de la matriz.** Para cada año, ¿`Σ cycles` de sus celdas `byYearByRegime` ==
`byYear[año].cycles`? ¿Puede quedar una celda huérfana o un año descolgado?

**P3.** **Separación por población.** ¿`LOSERS` y `WINNERS` de un régimen tienen `meanMaeR` divergentes?
¿Algún consumidor (CLI, docs, prompt) sigue etiquetando `ALL` como «perdedores»?

**P4.** **Excursión acotada.** ¿Todo `captureRatio` está en `[0, +inf)`? ¿`aboveOneCount` se declara
siempre? ¿`reversedCount` es estable entre corridas?

**P5.** **Determinismo.** ¿Mismo estado ⇒ payload **byte a byte** idéntico (sin reloj, ULID ni orden no
determinista)? ¿Dos corridas de `2021-2026` dan el mismo `sha256` (`6ec29bfd…`)?

**P6.** **Regla del hueco.** ¿En **ningún** camino un `None`/`NOT_MEASURED` se degrada a `0` (cubos
vacíos, medias de población vacía, `minMaeR`)?

**P7.** **`Δ motor = 0`.** ¿Los únicos cambios fuera de la capa de atribución son `meta.bump` y docs? ¿El
artefacto congelado de `replay-repro` sigue byte a byte (`1E3ADAC2…`)?

**P8.** **Freeze.** ¿`git rev-parse "HEAD:apps" "HEAD:packages"` en el commit funcional devuelve
**exactamente** `b0cd0174…`/`35a37d56…`, y el runner **aborta** (`TREE_MOVED`, fail-closed) si el árbol
se mueve?

**P9.** **¿Cambia alguna conclusión de 2022?** (Esperado: **no** el veredicto de `2022`
(`-0.5011`, `53` ciclos); **sí** la lectura del **global**, que pasa de monorégimen a multirregimen
`REFUTED` casi plano.) ¿Hay algún número del sello anterior que desaparezca sin justificación?

**P10.** **Orden del siguiente trabajo.** Candidatos: (a) **cruce H1-H4** (entrada/riesgo/gestión/salida)
con la ventana PAPER real `P3-2`/`P3-3`; (b) ampliar años/regímenes del barrido multirregimen;
(c) métricas ampliadas de concentración (HHI, shares `top1/top5/bottom`). ¿Cuál es **prerrequisito** de
cuál antes de tocar el motor AUTO?

---

## 5. Deuda viva que el auditor debe encontrar declarada (no oculta)

- **`P3-2`/`P3-3` (ventana PAPER real) — ABIERTAS.** La atribución es REPLAY/OOS; **no** sustituye la
  ventana PAPER real.
- **`2026` parcial y no medido.** A `2026-10-03` es año parcial; el ancla PIT `2026-12-31` excede la
  última barra durable (fail-closed) ⇒ `0` miembros elegibles.
- **`2021` medido vacío.** Corrió sin ciclos medibles; se declara `yearsEmpty`.
- **Muestras por año pequeñas** (`10`/`8`/`22` en `2023`/`2024`/`2025`): lectura por celda indicativa.
- **Sector aproximado.** Es el del catálogo **actual**, no point-in-time.
- **MAE/MFE entre días (D1).** El día de entrada puede incluir excursión previa al fill.
- **`CONFIRMED` reservado** a evidencia PAPER: aquí el veredicto es `REFUTED`.
- **Concentración limitada.** `classification` sólo resume el efecto del peor ciclo; las métricas
  ampliadas (HHI, shares) siguen pendientes.
- **Compuertas `G1`–`G7`:** `G6` ✅ y `G7` ✅; **`G1`–`G4` siguen ❌**
  ([`criterio-salida-beta-2026-10-01.md`](./criterio-salida-beta-2026-10-01.md) §3).
- **Artefactos locales gitignored:** los `sha256` de `operability_runs/dia-d-auto/*.json` se citan en la
  evidencia; un tercero los **regenera** (comando en `evidence/v2.88.41/README.md` §5), no los hereda.

---

## 6. Entregable esperado del auditor

`docs/engineering/auditoria-v2-88-41-dia-d-multirregimen-2026-XX-XX.md`, con veredicto **por pieza**
(cobertura · consistencia de la matriz · poblaciones · cota de excursión · determinismo · regla del
hueco · Δ motor · freeze) y respuesta a la **pregunta de fondo**: **¿el `-0.5011 R/ciclo` de `2022` es
fenómeno de régimen, de selección de entradas, de gestión de riesgo o de salida — descriptivamente y sin
conclusión causal?** Hallazgos **nuevos** separados de la deuda **ya declarada** (§5); lo que **no** se
pudo medir; y la **recomendación de siguiente trabajo** (P10).

---

## 7. Prompt listo para pegar (auditor MIA externo)

```text
Actúa como auditor externo independiente. Auditas un repositorio PÚBLICO de GitHub:
https://github.com/jvelasca/Bolsa_V1

OBJETO (sello): tag anotado v2.88.41-beta -> tag object 7686bbf9 -> commit 04397e12, version 2.11.41-beta,
base del diff v2.88.40-beta (8c971c00), Alembic head 048_journal_entry_dedupe_key (SIN migracion).
Clase: CAPACIDAD DEL INSTRUMENTO de investigacion sobre el motor AUTO (atribucion MULTIRREGIMEN 2021-2026
del DIA-D: ano x regimen x resultado x excursion). Advisory y read-only. NO es capacidad de motor y NO
toca el motor (delta motor = 0). NO cierra la ventana PAPER real. Nuevo SCHEMA_VERSION = dia-d-multi-v1.

PRIMERO lee, en este orden:
  1) docs/engineering/entrega-auditoria-externa-mia-v2.88.41-2026-10-03.md  (trampas §3 y preguntas §4)
  2) docs/engineering/evidence/v2.88.41/README.md   (afirmaciones falsables + limites §4)
  3) docs/engineering/plan-v2-88-41-dia-d-multirregimen-2026-10-03.md     (el plan ejecutado)

VERIFICA PRIMERO (firma de estado, en el clon):
  git cat-file -t v2.88.41-beta                                       (tag anotado)
  git rev-list -n 1 v2.88.41-beta                                     (04397e12)
  git diff --stat   v2.88.40-beta v2.88.41-beta                       (17 ficheros, +1751/-22)
  git diff --numstat v2.88.40-beta v2.88.41-beta -- packages apps     (8 ficheros, +1159/-4)
  git diff --name-only v2.88.40-beta v2.88.41-beta \
    -- "*auto_simulation_worker*" "*auto_v2_entry*" "*sim_durable_store*" \
       "*market_operability*" "*replay_oos*"                           (VACIO = delta motor 0)
  git diff --name-only v2.88.40-beta v2.88.41-beta -- "*alembic*" "*versions*"   (VACIO = sin migracion)
  git rev-parse "v2.88.41-beta^{}:apps" "v2.88.41-beta^{}:packages"   (b0cd0174... / 35a37d56...)

QUE QUEREMOS (respuestas concretas a los 10 puntos de §4 de la entrega):
  a) Cobertura: yearsMeasured union yearsNotMeasured = yearsRequested; cada ano no medido con reason;
     ningun ano rellenado con 0 (2021 medido vacio; 2026 fail-closed por ancla PIT futura).
  b) Consistencia: por ano, sum(cycles) de byYearByRegime == byYear[ano].cycles; sin celdas huerfanas.
  c) Poblaciones: LOSERS/WINNERS divergentes en meanMaeR; ningun consumidor rotula ALL como 'perdedores'.
  d) Excursion: todo captureRatio en [0,+inf); aboveOneCount declarado; reversedCount estable.
  e) Determinismo: mismo estado => payload byte a byte identico (sha256 6ec29bfd..., 90473 B).
  f) Regla del hueco: ningun None/NOT_MEASURED degradado a 0 (cubos vacios, medias, minMaeR).
  g) Delta motor = 0: unicos cambios fuera de la capa de atribucion = meta.bump y docs; replay-repro intacto.
  h) Freeze: HEAD:apps/HEAD:packages (commit funcional 85b00235) == b0cd0174.../35a37d56...; TREE_MOVED fail-closed.
  i) El multirregimen no cambia el veredicto de 2022 (-0.5011, 53 ciclos); si el global multirregimen.
  j) Orden del siguiente trabajo (cruce H1-H4 con PAPER P3-2/P3-3, mas anos/regimenes, concentracion ampliada).

REGLAS:
  - Trabaja sobre un clon fresco desde GitHub (repo publico, sin credenciales).
  - Cita fichero:linea. Distingue HALLAZGO NUEVO de DEUDA YA DECLARADA (la entrega §5 la lista).
  - NO leas un ano hueco como 0 ni como fallo: 2021 fue medido vacio; 2026 no se midio (sin_universo_pit).
  - NO leas 'high_vol' como 'malo': la matriz lo descompone en anos positivos (2023/2024) y negativos (2022/2025).
  - NO leas el global REFUTED como 'el motor pierde siempre': es -0.0094 (casi plano) y concentrado.
  - NO leas el 54.84% de ALL como 'perdedores que superaron el stop': mira WINNERS/LOSERS (Trampa n4).
  - El artefacto del barrido es gitignored: regeneralo con el comando de evidence/v2.88.41 §5.
  - El sello es 04397e12 (producto 85b00235); el pin del freeze es 85b00235; la entrega es POST-TAG (en main).
```
