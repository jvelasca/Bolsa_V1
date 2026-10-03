# Entrega a auditoría externa MIA — `v2.88.42-beta` (DÍA-D · **DE PUNTO A BANDA**: incertidumbre del SORTEO del venue en la atribución multirregimen, 2026-10-03)

> **Objeto auditado (sello LOCAL):** commit funcional **`4533b034`**, versión **`2.11.42-beta`**,
> base del diff **`v2.88.41-beta`** → **`04397e12`**, Alembic head **`048_journal_entry_dedupe_key`**
> (**sin migración**). **El tag anotado y el `Release tag CI` están PENDIENTES** (se citan POST-TAG);
> este documento es el handover de un sello local.
>
> **Identidad ESTABLE del producto:** el objeto se identifica por sus **árboles** `apps` `18d885fa…` /
> `packages` `8fbd4e6c…`, y el runner de la ventana los tiene **pineados** (`WINDOW_CONFIG.commit` =
> `4533b034`, el commit funcional). Cita el `tip` que veas en el clon, pero valida el objeto por esos
> dos hashes y por el `freeze OK` del dry-run.
> **Remote:** `https://github.com/jvelasca/Bolsa_V1` — **PÚBLICO** (el auditor clona sin credenciales).
> **Clase:** **capacidad del instrumento** de investigación sobre el motor AUTO, **advisory y read-only**.
> Convierte el **punto** por año/régimen de `v2.88.41` en una **banda del sorteo del venue**:
> **`Δ decisión motor = 0`**.
> **Punto de entrada del auditor:** **este documento** (autocontenido).
> **Evidencia cruda:** [`evidence/v2.88.42/`](./evidence/v2.88.42/README.md) ·
> padre: [`evidence/v2.88.41/`](./evidence/v2.88.41/README.md) (atribución multirregimen, punto) ·
> técnica de seed: `v2_88_16_3_oos_seed_robustness.py` (`W3.3`).

---

## 0. Qué es y qué NO es esta entrega

**Es** la **cuantificación de la incertidumbre del sorteo del venue** sobre la capa de **atribución**
del `DÍA-D AUTO`: corre el MISMO harness multirregimen **`K = 12` veces**, cada sorteo con el **ancla
temporal del seed del fill** desplazada (`fill_seed(bar_tick_now + k, symbol)`), **restaura el árbol
byte a byte** tras cada sorteo, y pliega los `12` artefactos en `min`/`median`/`max`/`mean`/`stdev` por
cubo + `validity` (`crossesZeroR`/`pointCitable`). Responde, **de forma descriptiva**, la pregunta del
dictamen: *¿el `-0.0094 R/ciclo` de `v2.88.41` —y cada punto por año/régimen— es citable, o es un dado
del sorteo del venue?*

**`Δ decisión motor = 0`.** Ningún fichero de motor aparece en el diff (`auto_simulation_worker.py`,
`auto_v2_entry.py`, `sim_durable_store.py`, `market_operability.py`, `replay_oos.py`,
`v2_87_replay_oos_durable_cycle.py`). El `seed` **se inyecta y se restaura byte a byte** por sorteo
(verificado: `git status` del worker vacío). No cambia ninguna decisión de inversión, ningún umbral
(`TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B), ninguna allocation ni ninguna migración. El artefacto congelado
de `replay-repro` es **idéntico** al sello anterior (`1E3ADAC2…`).

**NO es** una capacidad nueva de motor, ni un cambio de umbrales, ni la ventana PAPER real, ni un cambio
de estrategia. Sigue siendo **REPLAY/OOS** de **una sola estrategia** (`v283-window-a`); `P3-2`/`P3-3`
siguen **ABIERTAS**.

> **Trampa nº 1 — determinismo NO es validez.** El sorteo `k=0` reproduce el sello `v2.88.41` **byte a
> byte** (`93` ciclos, `-0.0094`, `REFUTED`, `STRONG`; `crossCheck.evidenceDrift=false`) **porque es el
> mismo dado**, no porque el resultado sea estable. Citar `-0.0094` como el resultado del sistema es el
> error que `W3.3` ya documentó.
>
> **Trampa nº 2 — el punto global NO es citable.** La banda de R total de los `12` sorteos es
> `[-16.859, +10.857]`, `se=2.501`, `IC95 ±4.902` ⇒ **cruza cero** y `pointCitable=False`. El veredicto
> alterna `REFUTED`×7 / `OOS_SUPPORTED`×3 / `MIXED`×2: el **signo** del edge global depende del sorteo.
>
> **Trampa nº 3 — `pointCitable=False` es el HALLAZGO, no un fallo.** Es prerequisito del `H1-H4`: sin
> suelo de ruido, comparar años es sobreinterpretar. La banda **no** mide el muestreo del ciclo (bootstrap,
> eje separado) ni el futuro.
>
> **Trampa nº 4 — hay celdas que SÍ son citables (a `K=12`).** `2022` (`-0.4363`, banda
> `[-0.6406, -0.1391]`), `2024` (`+1.2856`, `[+0.8425, +1.6662]`), `range` (`+1.1017`, `[+0.3748, +1.4795]`)
> y `high_vol` (`-0.1556`, `[-0.3278, -0.0149]`) **no** cruzan cero. `2023`, `2025` y `trend_down` **sí**
> cruzan cero ⇒ **no** citables.
>
> **Trampa nº 5 — `n` pequeño en un cubo lo hace frágil.** `drawsWithCell` es el `n` efectivo. La celda
> `2023 × trend_down` aparece en sólo `2/12` sorteos (`banda [-1.263, -1.139]`, pasa el criterio pero es
> **frágil**). Un `pointCitable=True` con `n=2` se lee con pinzas, y así se declara.
>
> **Trampa nº 6 — `K` es la resolución de la banda.** Con otro `K` la banda cambia; `K<2` **no** cita un
> punto (se declara `insufficient_draws`). El criterio es el MISMO de `W3.3`: no cruza cero **∧**
> `|mean| > 1.96·SE`.

---

## 1. El objeto y cómo obtenerlo

> **Dónde vive qué.** El **producto** auditado es el commit funcional **`4533b034`** (aún **sin tag**).
> Esta **entrega** viaja en el commit de **re-anclaje del freeze** (el que contiene este documento),
> porque el pin del runner vive en `scripts/` y se edita **después** de conocer los hashes del commit
> funcional. Al empujar, `main` tendrá: funcional `4533b034` → re-anclaje (esta entrega) → tag.

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1
git log --oneline -3                       # re-anclaje (entrega) → 4533b034 (producto funcional)
git show --stat 4533b034                   # el producto del sello
```

| Verdad | Valor |
| --- | --- |
| Commit funcional | **`4533b034`** (sello **local**; tag anotado **PENDIENTE**) |
| Versión (`package.json`) | `2.11.42-beta` (base `2.11.41-beta`) |
| Base del diff | `v2.88.41-beta` → `04397e12` |
| Alembic head | `048_journal_entry_dedupe_key` — **SIN migración** |
| Delta tag-a-tag total | **17 ficheros, `+1618 / −15`** (incluye docs POST-TAG del sello `v2.88.41`) |
| Delta `packages/`+`apps/` | **9 ficheros, `+1053 / −5`** |
| `Δ motor` | **ningún** fichero de motor en el diff (verificado, §2) |
| `SCHEMA_VERSION` | (nuevo) **`dia-d-multi-band-v1`** · `KIND = DIA_D_AUTO_MULTI_BAND` |
| CI del tag | **PENDIENTE** (sello local; se cita POST-TAG) |

**Composición del delta `packages/`+`apps/` (9 ficheros):**

| Fichero | Δ | Rol |
| --- | --- | --- |
| `packages/py/application/src/bolsa_application/dia_d_multi_uncertainty.py` | `+462` | dominio puro: pliega `K` artefactos `dia-d-multi-v1` en banda + `pointCitable` (`dia-d-multi-band-v1`) |
| `packages/py/application/tests/test_dia_d_multi_uncertainty.py` | `+183` | 9 tests puros que muerden (banda, huecos, citabilidad, determinismo) |
| `apps/api-python/scripts/v2_94_dia_d_multi_band.py` | `+402` | CLI: `K` re-sorteos (seed shift + restore byte a byte), `--draws/--reuse/--check-against` |
| `apps/api-python/tests/test_dia_d_bump_guard.py` | `+1` | guardián extendido a `v2_94` |
| `apps/api-python/scripts/v2_89…v2_93_…py` | `+1/−1` c/u | sólo `meta.bump` |

**Cómo recalcularlo en el clon (sin creerme nada):**

```bash
git diff --stat    04397e12 4533b034                                # 17 ficheros, +1618/-15
git diff --numstat 04397e12 4533b034 -- packages apps               # 9 ficheros, +1053/-5
git diff --name-only 04397e12 4533b034 \
  -- "*auto_simulation_worker*" "*auto_v2_entry*" "*sim_durable_store*" \
     "*market_operability*" "*replay_oos*"                           # VACÍO = Δ motor 0
git diff --name-only 04397e12 4533b034 -- "*alembic*" "*versions*"   # VACÍO = sin migración
git rev-parse "4533b034:apps" "4533b034:packages"                    # 18d885fa... / 8fbd4e6c...
```

---

## 2. Firma de estado verificada **antes** de auditar

| Comprobación | Esperado |
| --- | --- |
| `git show --stat 4533b034` | commit funcional del sello |
| Árbol limpio en el checkout | sí |
| Migración | **ninguna** (head `048_journal_entry_dedupe_key`) |
| Umbrales `TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B | intactos |
| Ficheros de motor en el diff | **ausentes** |
| Freeze del runner (`git rev-parse "4533b034:apps" "4533b034:packages"`) | `18d885faa7fc790ada9828efd0988399040eccc5` / `8fbd4e6c0871e86faa3114c1e6fcf8789110ac16` (el par del sello `v2.88.41-beta` era `b0cd0174…` / `35a37d56…`; el pin se **re-ancló**) |
| Dry-run del runner | `freeze OK` |
| CI del tag | **PENDIENTE** (sello local) |

### 2.1 Cobertura de la banda (`K = 12`, sobre 12 sorteos)

| Año | Medidos | Vacíos | No medidos | Motivo |
| --- | --- | --- | --- | --- |
| 2021 | 0/12 | **12/12** | 0/12 | medido sin ciclos en TODOS los sorteos |
| 2022-2025 | **12/12** | 0/12 | 0/12 | medido |
| 2026 | 0/12 | 0/12 | **12/12** | `sin_universo_pit` (ancla `2026-12-31` futura) |

### 2.2 Cubo GLOBAL (banda de `12` sorteos)

| Métrica | `min` | `median` | `max` | `mean` | `stdev` |
| --- | --- | --- | --- | --- | --- |
| `cycles` | 70 | 92.5 | 104 | 89.5 | 8.3516 |
| `expectancyR` | **-0.1813** | -0.0181 | **+0.1248** | **-0.0283** | 0.09675 |
| `realizedRTotal` | **-16.859** | -1.652 | **+10.857** | **-2.946** | 8.6637 |
| `hitRate` | 0.4086 | 0.4825 | 0.5402 | 0.4758 | 0.03706 |
| `meanMaeR` | -1.2925 | -1.1645 | -1.0632 | -1.1757 | 0.06303 |
| `captureMean` | 0.1661 | 0.2000 | 0.2146 | 0.1956 | 0.01566 |
| `reversedCount` | 4 | 8 | 11 | 8.0 | 2.2730 |

**`validity` GLOBAL:** `crossesZeroR=`**`True`** · `se=2.501` · `ci95HalfWidth=4.902` · `pointCitable=`**`False`**. Veredictos por sorteo: `REFUTED`×7 / `OOS_SUPPORTED`×3 / `MIXED`×2.

### 2.3 Por AÑO (banda de `realizedRTotal` y citabilidad)

| Año | `expectancyR` media | `expectancyR` banda | `realizedRTotal` banda | `drawsWithCell` | `pointCitable` |
| --- | --- | --- | --- | --- | --- |
| 2022 | **-0.4363** | `[-0.6406, -0.1391]` | `[-35.872, -7.927]` | 12 | **True** |
| 2023 | +0.3658 | `[-0.5040, +0.9151]` | `[-5.544, +11.983]` | 12 | False (cruza cero) |
| 2024 | **+1.2856** | `[+0.8425, +1.6662]` | `[+6.740, +12.392]` | 12 | **True** |
| 2025 | +0.2477 | `[-0.0107, +0.6120]` | `[-0.215, +10.404]` | 12 | False (cruza cero) |

### 2.4 Por RÉGIMEN (trial) y OPERATIVO

| Régimen (trial) | Operativo | `expectancyR` media | `realizedRTotal` banda | `pointCitable` |
| --- | --- | --- | --- | --- |
| `high_vol` | `HIGH_VOLATILITY` | **-0.1556** | `[-23.319, -1.114]` | **True** |
| `range` | `SIDEWAYS` | **+1.1017** | `[+1.124, +8.284]` | **True** |
| `trend_down` | `BEAR_TREND` | +0.5234 | `[-0.154, +7.556]` | False (cruza cero) |

### 2.5 Matriz AÑO × RÉGIMEN (banda y citabilidad)

| Año | Régimen | `drawsWithCell` | `expectancyR` media | `realizedRTotal` banda | `pointCitable` |
| --- | --- | --- | --- | --- | --- |
| 2022 | `high_vol` | 12 | -0.4363 | `[-35.872, -7.927]` | True |
| 2023 | `high_vol` | 12 | +0.3820 | `[-5.544, +11.983]` | False |
| 2023 | `trend_down` | **2** | -1.2010 | `[-1.263, -1.139]` | True (n=2, frágil) |
| 2024 | `high_vol` | 12 | +1.3920 | `[+2.033, +8.305]` | True |
| 2024 | `trend_down` | 12 | +1.2030 | `[+0.049, +5.356]` | True |
| 2025 | `high_vol` | 12 | -0.0390 | `[-5.632, +5.399]` | False |
| 2025 | `range` | 12 | +1.1020 | `[+1.124, +8.284]` | True |
| 2025 | `trend_down` | 12 | -0.1100 | `[-3.279, +2.724]` | False |

**Verificación local re-ejecutada en el momento del sello** (todos verdes): `pytest` DÍA-D **131 passed**
(`v2.88.41` = `122`; **+9** de `test_dia_d_multi_uncertainty.py`) · `ruff` All checks passed ·
`lint-imports` **4 kept / 0 broken** · `mypy` **527 files** · `contract:check` OK · `tsc -b --noEmit`
limpio · vitest `auto-monitor` **4 ficheros / 14 tests** · `pnpm window:test` **25/25** · corrida real
`v2_94 --draws 12 --check-against <sello>` (`crossCheck.evidenceDrift=False`; `pointCitable=False`
global) · determinismo `--reuse` ×2 **idéntico** (`sha256 4e87a3e6…`, `45 983 B`) · `git status` del
worker **vacío**.

---

## 3. Trampas declaradas: lo que el auditor **NO** debe concluir

1. **`pointCitable=False` global es el HALLAZGO.** `-0.0094 R/ciclo` no es citable: la banda de R
   `[-16.859, +10.857]` cruza cero (`se=2.501`, `IC95 ±4.902`).
2. **Determinismo ≠ validez.** `k=0` reproduce el sello byte a byte porque es el mismo dado; no es
   estabilidad.
3. **Hay celdas citables y celdas no.** `2022`/`2024`/`range`/`high_vol` no cruzan cero; `2023`/`2025`/
   `trend_down` **sí** cruzan cero (`pointCitable=False`).
4. **`drawsWithCell` es el `n` efectivo.** `2023 × trend_down` sólo aparece en `2/12`: `pointCitable=True`
   pero **frágil**.
5. **La banda mide el RUIDO DEL SORTEO DEL VENUE.** No es muestreo del ciclo (bootstrap, eje separado),
   ni futuro, ni PAPER.
6. **`K` es la resolución de la banda.** Con otro `K` cambia; `K<2` no cita (`insufficient_draws`).
7. **La regla del hueco no se relaja.** `meanMfeR` global es `None` (el artefacto multirregimen no lo
   publica a nivel global); sin muestra, `None`/`NOT_MEASURED`, **nunca** `0`.
8. **`2026` parcial/no medido y `2021` medido vacío** se heredan declarados de `v2.88.41`.
9. **REPLAY/OOS ≠ PAPER:** `CONFIRMED` sigue reservado; `P3-2`/`P3-3` **ABIERTAS**. La banda no cierra
   `H1-H4` (bloqueado por PAPER real).
10. **El artefacto de la banda y los `12` sorteos son gitignored** (`operability_runs/dia-d-auto*`); un
    tercero los **regenera** (§5), no los hereda.
11. **Este sello mueve el árbol** `apps`/`packages`, así que el runner se **re-ancló** a `4533b034`
    (`18d885fa…` / `8fbd4e6c…`); dry-run `freeze OK`.

---

## 4. Alcance sugerido: lo que queremos consensuar con el auditor

**P1.** **Autochequeo.** ¿El sorteo `k=0` (producción, sin parchear) reproduce el sello `v2.88.41`
(`93` ciclos, `-0.0094`, `hitRate=0.4839`, `REFUTED`, `STRONG`) con `evidenceDrift=False`?

**P2.** **Criterio de citabilidad.** ¿Es correcto el criterio de `W3.3` (banda de R **no** cruza cero **∧**
`|mean| > 1.96·SE`, `K>=2`)? ¿`K=12` es resolución suficiente, o el hallazgo exige declarar la banda
como tal sin más?

**P3.** **Determinismo vs validez.** ¿La reproducción byte a byte del sello (mismo dado) se está
distinguiendo correctamente de la **estabilidad** del resultado? ¿Algún consumidor sigue citando el
punto `-0.0094` sin banda?

**P4.** **Regla del hueco.** ¿En ningún camino un `None`/`NOT_MEASURED` se degrada a `0` (cubos vacíos,
`meanMfeR` global, media de población vacía)?

**P5.** **`n` efectivo.** ¿`drawsWithCell` y el `n` por métrica bastan para que el lector no sobreinterprete
un cubo con `n=2` (p. ej. `2023 × trend_down`)?

**P6.** **`Δ motor = 0`.** ¿Los únicos cambios fuera de la capa de atribución/banda son `meta.bump` y docs?
¿El artefacto congelado de `replay-repro` sigue byte a byte (`1E3ADAC2…`)?

**P7.** **Freeze.** ¿`git rev-parse "4533b034:apps" "4533b034:packages"` devuelve **exactamente**
`18d885fa…`/`8fbd4e6c…`, y el runner **aborta** (`TREE_MOVED`, fail-closed) si el árbol se mueve?

**P8.** **¿Cambia alguna conclusión de `v2.88.41`?** (Esperado: el veredicto de `2022` `-0.5011`/`53`
sigue siendo un punto del sorteo; el **global** pasa de «`-0.0094` casi plano» a «**no citable**», que es
la lectura correcta.)

**P9.** **Orden del siguiente trabajo.** Candidatos: (a) banda **bootstrap** del muestreo del ciclo (eje
separado del ruido del venue); (b) `H1-H4` con la ventana PAPER real `P3-2`/`P3-3`; (c) ampliar `K` /
años / regímenes. ¿Cuál es **prerrequisito** de cuál antes de tocar el motor AUTO?

---

## 5. Deuda viva que el auditor debe encontrar declarada (no oculta)

- **`P3-2`/`P3-3` (ventana PAPER real) — ABIERTAS.** La banda es REPLAY/OOS; **no** sustituye PAPER.
- **La banda mide el ruido del sorteo del venue**, no el muestreo del ciclo (bootstrap pendiente).
- **`K = 12` es la resolución.** Con otro `K` cambia; `K<2` no cita.
- **Cubos con `n` pequeño** (`drawsWithCell`) son frágiles.
- **`2026` parcial y no medido**; **`2021` medido vacío.**
- **MAE/MFE entre días (D1);** régimen = agregado trial por día; sector del catálogo **actual** (no PIT).
- **`CONFIRMED` reservado** a evidencia PAPER.
- **Compuertas `G1`–`G7`:** `G6` ✅ y `G7` ✅; **`G1`–`G4` siguen ❌**
  ([`criterio-salida-beta-2026-10-01.md`](./criterio-salida-beta-2026-10-01.md) §3).
- **Artefactos locales gitignored:** los `sha256` de `operability_runs/dia-d-auto*` se citan en la
  evidencia; un tercero los **regenera** (comando en `evidence/v2.88.42/README.md` §5), no los hereda.
- **Tag/CI del tag PENDIENTES:** sello local; la cita del `Release tag CI` se añade POST-TAG.

---

## 6. Entregable esperado del auditor

`docs/engineering/auditoria-v2-88-42-dia-d-banda-sorteo-venue-2026-XX-XX.md`, con veredicto **por pieza**
(autochequeo `k=0` · criterio de citabilidad · determinismo vs validez · regla del hueco · `n` efectivo ·
`Δ motor` · freeze) y respuesta a la **pregunta de fondo**: **¿el `-0.0094 R/ciclo` de `v2.88.41` (y cada
punto por año/régimen) es citable, o es un dado del sorteo del venue?** Hallazgos **nuevos** separados de
la deuda **ya declarada** (§5); lo que **no** se pudo medir; y la **recomendación de siguiente trabajo**.

---

## 7. Prompt listo para pegar (auditor MIA externo)

```text
Actúa como auditor externo independiente. Auditas un repositorio PÚBLICO de GitHub:
https://github.com/jvelasca/Bolsa_V1

OBJETO (sello LOCAL, SIN tag todavia): commit funcional 4533b034, version 2.11.42-beta, base del diff
v2.88.41-beta (04397e12), Alembic head 048_journal_entry_dedupe_key (SIN migracion).
Clase: CAPACIDAD DEL INSTRUMENTO de investigacion sobre el motor AUTO (BANDA DEL SORTEO DEL VENUE sobre
la atribucion multirregimen del DIA-D; K=12 re-sorteos del seed del fill, restauracion byte a byte).
Advisory y read-only. NO es capacidad de motor y NO toca el motor (delta motor = 0). NO cierra PAPER.
Nuevo SCHEMA_VERSION = dia-d-multi-band-v1.

PRIMERO lee, en este orden:
  1) docs/engineering/entrega-auditoria-externa-mia-v2.88.42-2026-10-03.md  (trampas §3 y preguntas §4)
  2) docs/engineering/evidence/v2.88.42/README.md   (afirmaciones falsables + limites §4)
  3) docs/engineering/evidence/v2.88.41/README.md   (el punto que esta banda mide)

VERIFICA PRIMERO (firma de estado, en el clon):
  git show --stat 4533b034                                            (commit funcional del sello)
  git diff --stat    04397e12 4533b034                                (17 ficheros, +1618/-15)
  git diff --numstat 04397e12 4533b034 -- packages apps               (9 ficheros, +1053/-5)
  git diff --name-only 04397e12 4533b034 \
    -- "*auto_simulation_worker*" "*auto_v2_entry*" "*sim_durable_store*" \
       "*market_operability*" "*replay_oos*"                           (VACIO = delta motor 0)
  git diff --name-only 04397e12 4533b034 -- "*alembic*" "*versions*"   (VACIO = sin migracion)
  git rev-parse "4533b034:apps" "4533b034:packages"                    (18d885fa... / 8fbd4e6c...)

QUE QUEREMOS (respuestas concretas a los 9 puntos de §4 de la entrega):
  a) Autochequeo k=0: reproduce el sello v2.88.41 (93 ciclos, -0.0094, REFUTED, STRONG) con drift=False.
  b) Criterio: no cruza cero Y |mean|>1.96*SE con K>=2; K=12 es resolucion suficiente o hay que declarar mas.
  c) Determinismo != validez: k=0 reproduce byte a byte PORQUE es el mismo dado, no por estabilidad.
  d) Regla del hueco: ningun None/NOT_MEASURED degradado a 0 (cubos vacios, meanMfeR global).
  e) n efectivo: drawsWithCell evita sobreinterpretar cubos con n=2 (p.ej. 2023 x trend_down).
  f) Delta motor = 0: unicos cambios fuera de la capa = meta.bump y docs; replay-repro intacto.
  g) Freeze: 4533b034:apps/4533b034:packages == 18d885fa.../8fbd4e6c...; TREE_MOVED fail-closed.
  h) El punto global -0.0094 NO es citable (banda [-16.859,+10.857], se=2.501, IC95 +-4.902); celdas
     citables 2022/2024/range/high_vol; no citables 2023/2025/trend_down.
  i) Orden del siguiente trabajo (bootstrap del ciclo, H1-H4 con PAPER P3-2/P3-3, mas K/anos/regimenes).

REGLAS:
  - Trabaja sobre un clon fresco desde GitHub (repo publico, sin credenciales).
  - Cita fichero:linea. Distingue HALLAZGO NUEVO de DEUDA YA DECLARADA (la entrega §5 la lista).
  - NO leas el determinismo (k=0 == sello) como validez: el sorteo del venue cambia el signo del global.
  - NO leas pointCitable=False como fallo: es el hallazgo (sin suelo de ruido, comparar anos es sobreinterpretar).
  - NO leas un puntoCitable=True con drawsWithCell=2 como solido: la banda es fragil y se declara.
  - NO leas un ano hueco como 0: 2021 medido vacio; 2026 no medido (sin_universo_pit).
  - El artefacto de la banda y los 12 sorteos son gitignored: regeneralo con el comando de evidence/v2.88.42 §5.
  - El sello es LOCAL (commit funcional 4533b034); tag y CI del tag PENDIENTES.
```
