# Entrega a auditoría externa MIA — `v2.88.40-beta` (DÍA-D · **corrección semántica de la atribución** A39-01/02/03: captura de MFE acotada, severidad de MAE por población, cross-check tolerante, 2026-10-03)

> **Objeto auditado:** tag anotado **`v2.88.40-beta`** → tag object **`d113c3e7`** → commit **`8c971c00`**,
> versión **`2.11.40-beta`**, base del diff **`v2.88.39-beta`** → **`0648cd40`**, Alembic head
> **`048_journal_entry_dedupe_key`** (**sin migración**).
>
> **Identidad ESTABLE del producto:** el objeto se identifica por sus **árboles** `apps` `22ca3e78…` /
> `packages` `f169415e…`, y el runner de la ventana los tiene **pineados** (`WINDOW_CONFIG.commit` =
> `bd3c9cd9`, el commit funcional). Cita el `tip` que veas en el clon, pero valida el objeto por esos
> dos hashes y por el `freeze OK` del dry-run.
> **Remote:** `https://github.com/jvelasca/Bolsa_V1` — **PÚBLICO** (el auditor clona sin credenciales).
> **Clase:** **corrección del instrumento** de investigación sobre el motor AUTO, **advisory y read-only**.
> No añade capacidad: cierra tres hallazgos semánticos de la auditoría de `v2.88.39-beta`.
> **Evidencia cruda:** [`evidence/v2.88.40/`](./evidence/v2.88.40/README.md) ·
> padre [`evidence/v2.88.39/`](./evidence/v2.88.39/README.md) (el sello auditado, donde nacieron A39-01/02/03).

---

## 0. Qué es y qué NO es esta entrega

**Es** la corrección **quirúrgica** de la capa de **atribución** del OOS 2022 que introdujo `v2.88.39`,
sobre la MISMA muestra medida. Cierra los tres hallazgos que la auditoría de `v2.88.39` marcó como
bloqueantes de uso, y re-cita el cuarto (**A39-04**, la cita del CI del tag) ya VERDE:

| Hallazgo | Qué se corrige |
| --- | --- |
| **A39-01 🔴** | `capture_study` medía `realized / mfe` **sin acotar**: ratios **negativos** y explosión con `MFE → 0+` (evidencia del sello anterior: `meanCapture=-12.12`, `medianCapture=-1.26`). Ahora `capturedR = max(realizedR, 0)` y el ratio vive en `[0, +inf)`; un `captureRatio > 1` se **declara** (`aboveOneCount`), no se recorta. |
| **A39-02 🔴** | `mae_severity` afirmaba medir "perdedores" pero contaba **cualquier** ciclo con MAE bajo el umbral (no conocía `realizedR`). Ahora publica **poblaciones** `ALL` / `WINNERS` / `LOSERS`, uniendo el MAE con su ciclo por `cycle_key`. |
| **A39-03 🟠** | El cross-check comparaba floats por **igualdad exacta** (`!=`). Ahora `expectancyR`/`hitRate` usan `math.isclose` (`rel_tol=abs_tol=1e-12`); el resto sigue exacto. |
| **A39-04 🟠** | La **cita del CI del tag** (patrón `OBS-3`: el `Release tag CI` sólo corre al empujar el tag, así que su resultado no puede vivir dentro del mismo tag) queda **evidenciada VERDE** en `main` para `v2.88.40-beta`: `Release tag CI` run [`37132550660`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37132550660) — `11 jobs success` + `playwright` integrado `skipped` por diseño; `certify` `success`; `python` `4436 passed / 45 skipped`; `replay-repro` `REPRODUCIDO` `1E3ADAC2…`. Se **re-cita** aquí sin re-sellar. |

**`SCHEMA_VERSION` de la atribución sube a `dia-d-attribution-v2`** (cambia la forma de `capture` y
`maeSeverity`).

**`Δ decisión motor = 0`.** Ningún fichero de motor aparece en el diff: el motor se **conduce** con
stores en memoria desde el mismo harness hermético de `v2_86`/`v2_87`. No cambia ninguna decisión de
inversión, ningún umbral (`TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B) ni ninguna migración. La muestra OOS
2022 es **idéntica** a la sellada por `v2.88.39` (`crossCheck.evidenceDrift=false`, 5/5 claves).

**NO es** una capacidad nueva, ni un cambio de motor, ni una prueba multirrégimen, ni la ventana PAPER
real. `2022` sigue siendo **monorégimen** (`high_vol`) y **una sola estrategia** (`v283-window-a`).
`P3-2`/`P3-3` siguen **ABIERTAS**.

> **Trampa nº 1 — la corrección cambia la FORMA del artefacto.** `capture` y `maeSeverity` **rompen
> compatibilidad** con `dia-d-attribution-v1`. Un auditor que compare contra un artefacto del sello
> anterior verá claves distintas (`meanCapture` → `captureRatio`; `breaches` → `populations`). El
> artefacto vive en `operability_runs/dia-d-auto/*.json`, que es **gitignored**: un tercero lo
> **regenera** (§5), no lo hereda.
>
> **Trampa nº 2 — el `66 %` NO es "perdedores que superaron el stop".** Ese `66 %` es la fracción de
> **TODOS** los ciclos con MAE `< -1R` (`ALL`: `35/53`). La pregunta de investigación se responde con
> `LOSERS` (`33/35 = 94.29 %`) y, sobre todo, con `WINNERS` (`2/18 = 11.11 %`): **dos ganadores
> atravesaron `-1R`** (mínimo de ganador `-1.1316R`). Este es **exactamente** el sesgo que A39-02
> corregía; leer `ALL` como "perdedores" es repetir el error.
>
> **Trampa nº 3 — `captureRatio > 1` es posible y NO es un bug.** El MFE se mide con barras D1
> (máximo del rango); el cierre puede superar ese extremo por ruido **intrabar**. Se **declara** en
> `captureRatio.aboveOneCount` (en 2022: `0`), no se recorta silenciosamente.
>
> **Trampa nº 4 — un MAE medible sin `realizedR` sólo entra en `ALL`.** Si `realizedR` no es legible,
> el ciclo no se clasifica ni ganador ni perdedor: entra en `ALL` y queda fuera de `WINNERS`/`LOSERS`
> (se declara el remanente, no se adivina).
>
> **Trampa nº 5 — `leftOnTableR` usa `max(R,0)`.** Un perdedor con MFE positivo deja **todo** el MFE
> en la mesa (su `capturedR` es `0`). El premio dejado en la mesa **no** es un coste neto, es una
> métrica de excursión.

---

## 1. El objeto y cómo obtenerlo

> **Dónde vive qué.** El **producto** auditado está **dentro del tag**; esta **entrega** viaja
> **POST-TAG en `main`**, porque el tag es inmutable y se selló antes de escribirse su cita. Clona
> `main` para **leer**, y `checkout` del tag para **verificar**.

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1
# (A) leer la entrega        -> rama main (default tras el clon)
# (B) verificar el producto  -> el tag
git checkout v2.88.40-beta
git log --oneline -1                       # 8c971c00 (sello v2.88.40)
```

| Verdad | Valor |
| --- | --- |
| Tag anotado | `v2.88.40-beta` (tag object `d113c3e7`) → `8c971c00` |
| Versión (`package.json`) | `2.11.40-beta` (base `2.11.39-beta`) |
| Base del diff | `v2.88.39-beta` → `0648cd40` |
| Alembic head | `048_journal_entry_dedupe_key` — **SIN migración** |
| Delta tag-a-tag total | **14 ficheros, `+497 / −85`** (incluye docs y `scripts/`) |
| Delta `packages/`+`apps/` | **6 ficheros, `+246 / −68`** |
| `Δ motor` | **ningún** fichero de motor en el diff (verificado, §2) |
| `SCHEMA_VERSION` | `dia-d-attribution-v1` → **`dia-d-attribution-v2`** |
| CI del tag | `Release tag CI` run **`37132550660`** — **VERDE** (11 jobs `success` + `playwright` integrado `skipped` por diseño; `certify` `success`; `python` `4436 passed / 45 skipped`; `replay-repro` `REPRODUCIDO` `1E3ADAC2…` / `3 340 728 B`) |

**Composición del delta `packages/`+`apps/` (6 ficheros):**

| Fichero | Δ | Rol |
| --- | --- | --- |
| `packages/py/application/src/bolsa_application/dia_d_attribution.py` | `+85/−30` | dominio puro: `capture_study` + `mae_severity` por población + `_population_breaches` + `SCHEMA_VERSION` v2 + límites |
| `packages/py/application/tests/test_dia_d_attribution.py` | `+108/−26` | tests reescritos + 4 nuevos que muerden |
| `apps/api-python/scripts/v2_92_dia_d_attribution.py` | `+50/−9` | cross-check `isclose` + `_print_text` + `meta.bump` |
| `apps/api-python/scripts/v2_89_dia_d_auto_replay.py` | `+1/−1` | sólo `meta.bump` |
| `apps/api-python/scripts/v2_90_dia_d_feedback.py` | `+1/−1` | sólo `meta.bump` |
| `apps/api-python/scripts/v2_91_dia_d_longitudinal.py` | `+1/−1` | sólo `meta.bump` |

**Cómo recalcularlo en el clon (sin creerme nada):**

```bash
git diff --stat   v2.88.39-beta v2.88.40-beta                     # 14 ficheros, +497/-85
git diff --numstat v2.88.39-beta v2.88.40-beta -- packages apps   # 6 ficheros, +246/-68
git diff --name-only v2.88.39-beta v2.88.40-beta \
  -- "*auto_simulation_worker*" "*auto_v2_entry*" "*sim_durable_store*" \
     "*market_operability*" "*replay_oos*"                        # VACÍO = Δ motor 0
git diff --name-only v2.88.39-beta v2.88.40-beta -- "*alembic*" "*versions*"   # VACÍO = sin migración
git rev-parse "v2.88.40-beta^{}:apps" "v2.88.40-beta^{}:packages" # 22ca3e78... / f169415e...
```

---

## 2. Firma de estado verificada **antes** de auditar

Corrida **por el auditor en su clon**, no heredada:

| Comprobación | Esperado |
| --- | --- |
| `git cat-file -t v2.88.40-beta` | `tag` (anotado) |
| `git rev-list -n 1 v2.88.40-beta` | `8c971c00` |
| Árbol limpio en el checkout del tag | sí |
| Migración | **ninguna** (head `048_journal_entry_dedupe_key`) |
| Umbrales `TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B | intactos |
| Ficheros de motor en el diff | **ausentes** |
| Freeze del runner (`git rev-parse "HEAD:apps" "HEAD:packages"` en el commit funcional `bd3c9cd9`) | `22ca3e78ec4e18f69a11a9fd047dfb9db9f3f43f` / `f169415e7c46c38ed15c53d0030a86480d49132b` (el par del sello `v2.88.39-beta` era `2fd946c4…` / `fdcae617…`; el pin se **re-ancló**) |
| Dry-run del runner | `freeze OK` |
| CI del tag | **11 `success`** + `playwright (integrated E2E, opt-in)` `skipped` por diseño; `certify` `success` (`Release tag CI` run `37132550660`) |

**Resultado medido (misma muestra OOS 2022, `REFUTED`, `evidenceDrift=false`):**

| Bloque | `v2.88.39` (auditado) | `v2.88.40` (corregido) |
| --- | --- | --- |
| `capture.ratio` media / mediana / máx | `-12.12` / `-1.26` / n/d | **`+0.1429` / `0.0` / `0.6237`**, `aboveOneCount=0` |
| `capture.capturedR` media | (no existía) | **`+0.4141`** |
| `capture.leftOnTableR` media / mediana | `+1.741` / `+1.689` | **`+0.8758` / `0.9882`** |
| MAE `< -1R` | `35/53 = 66 %` (rotulado "perdedores") | **ALL `35/53 = 66.04 %`** · **WINNERS `2/18 = 11.11 %`** · **LOSERS `33/35 = 94.29 %`** |
| `summary` | `expectancyR=-0.5011`, `hitRate=0.3396`, `53` ciclos | **idéntico** |

**Verificación local re-ejecutada en el momento del sello** (todos verdes): `pytest` DÍA-D **112 passed** ·
`ruff` All checks passed · `lint-imports` **4 kept / 0 broken** · `mypy` **525 files** · `contract:check`
OK · `tsc -b --noEmit` limpio · vitest `auto-monitor` **4 ficheros / 14 tests** · `pnpm window:test`
**25/25** · smoke `v2_92 --year 2022 --universe pit` con `evidenceDrift=false`.

---

## 3. Trampas declaradas: lo que el auditor **NO** debe concluir

1. **`ALL ≠ LOSERS`.** El `66 %` de ciclos con MAE `< -1R` **no** es "perdedores que superaron el
   stop": es la fracción de **todos**. Léelo junto a `WINNERS`/`LOSERS`.
2. **`captureRatio > 1` es legítimo** (cierre por encima del MFE D1, ruido intrabar). Se declara en
   `aboveOneCount`; no es un error de cálculo ni se recorta.
3. **`leftOnTableR` no es pérdida neta.** Es el MFE favorable que quedó sin capturar; un perdedor con
   MFE positivo deja todo su MFE "en la mesa".
4. **El cambio rompe compatibilidad (`v1 → v2`).** No es una extensión aditiva: `capture` y
   `maeSeverity` cambian de forma. Comparar con artefactos del sello anterior es inválido.
5. **El cross-check tolera residuo de coma flotante, pero no afloja la auditoría.** `verdict`,
   `evidenceQuality` y `measuredCycles` siguen por igualdad **exacta**; sólo `expectancyR`/`hitRate`
   usan `1e-12`.
6. **La regla del hueco no se relaja.** Sin muestra, medias y fracciones son `None`/`NOT_MEASURED`
   (**nunca** `0`); un cubo sin ciclos medibles no aparece.
7. **La atribución es DESCRIPTIVA, no causal.** `2022` es monorégimen y una sola estrategia; la señal
   está en el payoff y en la excursión, no en los cubos de régimen/estrategia.
8. **El artefacto del barrido es gitignored.** Vive en `operability_runs/dia-d-auto/*.json`; un tercero
   lo **regenera** (§5), no lo hereda.
9. **Este sello mueve el árbol** `apps`/`packages`, así que el runner de la ventana se **re-ancló** a
   los hashes del commit funcional `bd3c9cd9` (`22ca3e78…` / `f169415e…`); dry-run `freeze OK`.
10. **Los documentos de auditoría y esta entrega son POST-TAG (en `main`).** El sello es `8c971c00`; el
    pin del freeze es `bd3c9cd9`; el **CI del tag** es la run `37132550660` (**VERDE**).

---

## 4. Alcance sugerido: lo que queremos consensuar con el auditor

**P1.** ¿`capture_study` es **semánticamente limpia**? ¿Existe **algún** camino con `MFE > 0` y
`realizedR < 0` que produzca `captureRatio < 0` o un valor no finito? ¿El ratio está acotado por abajo
en `0` **siempre**?

**P2.** ¿La partición `WINNERS`/`LOSERS` es **coherente** con `payoff_decomposition` (`> 0` vs `<= 0`)?
¿Un ciclo con `realizedR` ilegible puede colarse en `WINNERS`/`LOSERS`, o queda sólo en `ALL`?

**P3.** ¿La severidad por población **no** se puede confundir con "perdedores"? ¿Algún consumidor (CLI,
docs, prompt) sigue etiquetando `ALL` como "perdedores"?

**P4.** Cross-check: ¿`_numbers_close` evita un falso `DRIFT` por residuo (`-0.5011` vs
`-0.5011000000000001`) **sin** dejar de detectar un drift material (`1e-6`)? ¿Un valor no numérico
(`None`/texto) hace algo distinto de la igualdad exacta?

**P5.** Determinismo: ¿mismo estado ⇒ payload **byte a byte** idéntico (sin reloj, ULID ni orden no
determinista)? ¿`aboveOneCount`/`reversedCount` son estables?

**P6.** Regla del hueco: ¿en **ningún** camino un `None`/`NOT_MEASURED` se degrada a `0` (medias de
población vacía, `minMaeR`, `share` sin muestra)?

**P7.** `Δ motor = 0`: ¿los únicos cambios fuera de la capa de atribución son `meta.bump` y docs? ¿El
artefacto congelado de `replay-repro` sigue byte a byte?

**P8.** Freeze: ¿`git rev-parse "HEAD:apps" "HEAD:packages"` en el commit funcional devuelve
**exactamente** `22ca3e78…`/`f169415e…`, y el runner **aborta** (`TREE_MOVED`, fail-closed) si el
árbol se mueve?

**P9.** La corrección, ¿**cambia alguna conclusión** de 2022? (Esperado: **no** el veredicto
`REFUTED` ni la expectativa; **sí** la lectura de la excursión.) ¿Hay algún número que el sello
anterior presentara y que ahora desaparezca sin justificación?

**P10.** **Orden del siguiente trabajo.** Candidatos: (a) `DÍA-D-3b` multirrégimen / 2022-2026;
(b) métricas ampliadas de concentración (HHI, shares `top1/top5/bottom`); (c) ventana PAPER real
(`P3-2`/`P3-3`). ¿Cuál es **prerrequisito** de cuál antes de tocar el motor AUTO?

---

## 5. Deuda viva que el auditor debe encontrar declarada (no oculta)

- **`P3-2`/`P3-3` (ventana PAPER real) — ABIERTAS.** La atribución es REPLAY/OOS; **no** sustituye la
  ventana PAPER real.
- **Concentración limitada.** `classification = broad` sólo significa que **retirar el peor ciclo no
  cambia el signo**; no es una prueba de no-concentración. Las métricas ampliadas (HHI, shares) siguen
  pendientes (fuera de alcance de este sello).
- **Monorégimen.** `2022` colapsa `byRegime` a `high_vol` y `byStrategy` a `v283-window-a`.
- **Sector aproximado.** Es el del catálogo **actual**, no point-in-time; `Financial Services`
  (`n=2`) no concluye.
- **MAE/MFE entre días (D1).** El día de entrada puede incluir excursión previa al fill.
- **`CONFIRMED` reservado** a evidencia PAPER: aquí el veredicto es `REFUTED`.
- **Compuertas `G1`–`G7`:** `G6` ✅ y `G7` ✅; **`G1`–`G4` siguen ❌**
  ([`criterio-salida-beta-2026-10-01.md`](./criterio-salida-beta-2026-10-01.md) §3).
- **Artefactos locales gitignored:** los `sha256` de `operability_runs/dia-d-auto/*.json` se citan en la
  evidencia; un tercero los **regenera** (comando en `evidence/v2.88.40/README.md` §5), no los hereda.

---

## 6. Entregable esperado del auditor

`docs/engineering/auditoria-v2-88-40-dia-d-atribucion-correccion-2026-XX-XX.md`, con veredicto **por
pieza** (semántica de captura · severidad por población · cross-check · determinismo · regla del hueco ·
Δ motor · freeze) y respuesta a la **pregunta de fondo**: **¿las métricas corregidas miden lo que dicen
medir, sin coaccionar huecos a `0` y sin reintroducir el sesgo de "perdedores"?** Hallazgos **nuevos**
separados de la deuda **ya declarada** (§5); lo que **no** se pudo medir; y la **recomendación de
siguiente trabajo** (P10).

---

## 7. Prompt listo para pegar (auditor MIA externo)

```text
Actúa como auditor externo independiente. Auditas un repositorio PÚBLICO de GitHub:
https://github.com/jvelasca/Bolsa_V1

OBJETO (sello): tag anotado v2.88.40-beta -> tag object d113c3e7 -> commit 8c971c00, version 2.11.40-beta,
base del diff v2.88.39-beta (0648cd40), Alembic head 048_journal_entry_dedupe_key (SIN migracion).
Clase: CORRECCION DEL INSTRUMENTO de investigacion sobre el motor AUTO (capa de atribucion del OOS 2022).
Cierra A39-01/A39-02/A39-03 de la auditoria de v2.88.39. Advisory y read-only. NO es capacidad nueva y NO
toca el motor (delta motor = 0). NO cierra la ventana PAPER real. SCHEMA_VERSION sube a dia-d-attribution-v2.

PRIMERO lee, en este orden:
  1) docs/engineering/entrega-auditoria-externa-mia-v2.88.40-2026-10-03.md  (trampas §3 y preguntas §4)
  2) docs/engineering/evidence/v2.88.40/README.md   (afirmaciones falsables + limites §4)
  3) docs/engineering/evidence/v2.88.39/README.md   (el sello auditado, donde nacieron A39-01/02/03)

VERIFICA PRIMERO (firma de estado, en el clon):
  git cat-file -t v2.88.40-beta                                       (tag anotado)
  git rev-list -n 1 v2.88.40-beta                                     (8c971c00)
  git diff --stat   v2.88.39-beta v2.88.40-beta                       (14 ficheros, +497/-85)
  git diff --numstat v2.88.39-beta v2.88.40-beta -- packages apps     (6 ficheros, +246/-68)
  git diff --name-only v2.88.39-beta v2.88.40-beta \
    -- "*auto_simulation_worker*" "*auto_v2_entry*" "*sim_durable_store*" \
       "*market_operability*" "*replay_oos*"                           (VACIO = delta motor 0)
  git diff --name-only v2.88.39-beta v2.88.40-beta -- "*alembic*" "*versions*"   (VACIO = sin migracion)
  git rev-parse "v2.88.40-beta^{}:apps" "v2.88.40-beta^{}:packages"   (22ca3e78... / f169415e...)

QUE QUEREMOS (respuestas concretas a los 10 puntos de §4 de la entrega):
  a) capture_study: ningun camino con MFE>0 y realizedR<0 produce ratio negativo o no finito; cota [0,inf).
  b) Particion WINNERS/LOSERS coherente con payoff (>0 vs <=0); un realizedR ilegible solo entra en ALL.
  c) La severidad por poblacion no se puede leer como 'perdedores'; ningun consumidor rotula ALL asi.
  d) Cross-check: isclose evita falso DRIFT por residuo y sigue detectando drift material; no numerico => exacto.
  e) Determinismo: mismo estado => payload byte a byte identico (sin reloj/ULID/orden no determinista).
  f) Regla del hueco: ningun None/NOT_MEASURED degradado a 0 (medias de poblacion vacia, minMaeR, share).
  g) Delta motor = 0: unicos cambios fuera de la capa de atribucion = meta.bump y docs; replay-repro intacto.
  h) Freeze: HEAD:apps/HEAD:packages (commit funcional bd3c9cd9) == 22ca3e78.../f169415e...; TREE_MOVED fail-closed.
  i) La correccion no cambia el veredicto REFUTED ni la expectativa; si cambia la lectura de la excursion.
  j) Orden del siguiente trabajo (DIA-D-3b multirregimen, concentracion ampliada, o ventana PAPER real).

REGLAS:
  - Trabaja sobre un clon fresco desde GitHub (repo publico, sin credenciales).
  - Cita fichero:linea. Distingue HALLAZGO NUEVO de DEUDA YA DECLARADA (la entrega §5 la lista).
  - NO leas el 66% de ALL como 'perdedores que superaron el stop': mira WINNERS/LOSERS (Trampa n2).
  - NO leas captureRatio>1 como bug: es ruido D1 intrabar, declarado en aboveOneCount (Trampa n3).
  - NO leas 'NOT_MEASURED' como 0 ni como fallo: es la regla de la casa (un hueco nunca se coacciona a 0).
  - El artefacto del barrido es gitignored: regeneralo con el comando de evidence/v2.88.40 §5.
  - El sello es 8c971c00; el pin del freeze es bd3c9cd9; la entrega es POST-TAG (en main).
```
