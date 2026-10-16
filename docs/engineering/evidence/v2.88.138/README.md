# Evidencia `v2.88.138-beta` — explicación `P3→P4` de la estrategia seleccionada (UI 8.x) + cierre de los dos hallazgos de auditoría del incremento `9f0ae3ad`

> **Bump:** `2.11.137-beta` → **`2.11.138-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87`, de los 9 CLIs `v2_89`…`v2_97`, del certificador `v2_98`, del CLI `v2_99` y de `v2_100` — **13 scripts** en [`apps/api-python/scripts`](../../../../apps/api-python/scripts/); guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) **1 passed**).
>
> **Naturaleza:** incremento **de UI/read-model PURO + documentación** — **no** toca el motor de decisión, ni umbrales, ni contrato HTTP, y **no** hay migración. · **`Δ motor = 0`** · **`Δ decisión = 0`** · **`Δ contrato HTTP = 0`** (`contract:check` **OK**; solo `apps/web` + `packages/shared`) · **SIN migración** (head `055_dia_d_identity_nullable`, de la remediación AUDITORIA2). Tag **unsigned**.
>
> **Base:** `v2.88.137-beta`.
>
> **Alcance del modelo de cuentas:** **single-user/single-account**. No cambia con este sello.

---

## 0. Qué cierra (y qué NO)

| Pieza | Estado | Qué aporta |
| --- | --- | --- |
| **Explicación `P3→P4`** | **ENTREGADO** | Bloque «Por qué se sostiene (evidencia medida)»: une la estrategia **EJECUTADA** del ciclo (P3) con la evidencia medida del **VALOR** (P4), la verificación durable **por ciclo** y la sesión LAB, en **una** superficie. |
| **Hallazgo AUDITORIA2 — identidad LAB** | **CERRADO** | La sesión LAB sólo se atribuye a la operación con identidad **tripartita EXACTA** (`instrumentId` + `accountId` + `strategyPresetKey`); cualquier hueco ⇒ **fail-closed** («no vinculada»). |
| **Hallazgo AUDITORIA2 — lectura de la verificación** | **CERRADO** | Un **fallo de lectura** de las verificaciones durables se declara `unknown`/«No disponible», nunca `not-verified`/«Sin verificación» (`UNKNOWN != 0`). |

**NO cierra** (se declara): la **ventana PAPER real** (ADR-046) sigue **`0/4 días`, `0/2 regímenes`, `0/32 ciclos` ⇒ `INCONCLUSIVE`** — lo que falta es **OPERACIÓN**, no software. La **magnitud/rentabilidad** del P&L sigue **NO MEDIDA**. Este sello **no demuestra rentabilidad**.

---

## 1. Explicación `P3→P4` de la estrategia seleccionada

**Problema.** El usuario veía la estrategia **seleccionada** (P3) y, por separado, evidencia DÍA-D/OOS (P4), sin una lectura que dijera **por qué se sostiene** y con la honestidad de **a quién** pertenece cada dato.

**Cambio.** NUEVO read-model **puro** [`auto-strategy-dia-d-explanation.ts`](../../../../apps/web/src/features/auto/auto-strategy-dia-d-explanation.ts) (`buildAutoStrategyDiaDExplanation`), reutilizado por la tarjeta P3 y el panel de historia:

- **P3 (estrategia):** la EJECUTADA del ciclo se resuelve en el TOP del valor por `presetKey` **EXACTO** (no se cae al `#1`), con sus indicadores y las razones del coach.
- **P4 (DÍA-D):** se reutiliza el agregado **probado** [`buildDiaDEvidenceAggregate`](../../../../apps/web/src/features/auto-monitor/dia-d-evidence-aggregate.ts) (cuatro capas: ventana · reconciliación · OOS · PAPER) **sin promoción**; más los contadores y suelos de muestra y la fila **EXACTA** del ciclo (`cycleEvidence`).
- **Etapa `EXPLANATION` (`@bolsa/shared`):** [`auto-operation-story.ts`](../../../../packages/shared/src/cognitive/auto-operation-story.ts) publica la **clave EXACTA** del ciclo en la fila `EXPLANATION` (conocimiento cross-ciclo, grupo propio, fuera de la historia de la operación).

**Invariantes falsables (declaradas en la superficie).**

1. **La evidencia DÍA-D es del VALOR, no de la estrategia.** El artefacto agrega el veredicto por `symbol`; **no** existe identidad de estrategia por valor. Rótulo [`AUTO_STRATEGY_EXPLANATION_SCOPE_VALUE_LABEL`](../../../../apps/web/src/features/auto/auto-strategy-dia-d-explanation.ts) «Del valor (no de la estrategia)». Lo único **exacto** es la fila del `cycleId` enlazado («Del ciclo (exacta)»).
2. **Sin promoción de capas.** `READY`, `MATCH` y `OOS_SUPPORTED` **no** confirman; `CONFIRMED` **no se emite**.
3. **`UNKNOWN != 0`.** Un contador ausente es `null`, jamás `0`; un hueco se declara con el rótulo de `absent-data`.
4. **Fail-closed y lectura ≠ ausencia.** Sin símbolo resuelto o sin artefacto, la vista declara el hueco; un fallo de lectura se declara «No disponible» y `loading` deja el hueco en `null` (**transitorio**, no ausencia).

---

## 2. Hallazgo de auditoría — identidad de la sesión LAB (fail-closed)

**Antes.** `resolveLab()` recibía el `instrumentId` pero **no lo comparaba**, **descartaba** el `accountId`, caía a `executedStrategyDefinitionId` como si fuera la clave de estrategia y casaba **cualquier** sesión si la clave esperada era `null`. Consecuencia: una sesión LAB de **otro instrumento** (o de **otra cuenta**) podía mostrarse como de esta operación.

**Ahora** ([`resolveLab()`](../../../../apps/web/src/features/auto/auto-strategy-dia-d-explanation.ts#L277)). La sesión se da por **vinculada** sólo con **identidad tripartita EXACTA** y **sin huecos**:

| espacio de claves | esperado | sesión |
| --- | --- | --- |
| instrumento | `strategy.instrumentId` (UUID) | `session.instrumentId` |
| cuenta | `accountId` (Activa, UUID) | `session.accountId` |
| estrategia | `cycle.strategyPresetKey` (clave exacta) | `session.strategyPresetKey` |

Son **tres** espacios **distintos**: no se sustituye uno por otro (jamás se usa el `definitionId` como clave) y un hueco **nunca** se rellena. Si cualquiera falta o no coincide ⇒ `active = false` con el rótulo [`AUTO_STRATEGY_EXPLANATION_LAB_UNLINKED_LABEL`](../../../../apps/web/src/features/auto/auto-strategy-dia-d-explanation.ts) = «Sesión LAB abierta de otra operación (no vinculada)». La cuenta **Activa** entra desde [`auto-operation-story-panel.tsx`](../../../../apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx) (`accountId` de `useAutoOperationalMonitor()`).

---

## 3. Hallazgo de auditoría — fallo de lectura de la verificación (lectura ≠ ausencia)

**Antes.** Un **error de lectura** de las verificaciones durables se mapeaba a `not-verified` ⇒ la UI mostraba «Sin verificación», un **falso negativo** (afirmaba ausencia donde sólo había un fallo de lectura).

**Ahora** ([`resolveVerification()`](../../../../apps/web/src/features/auto/auto-strategy-dia-d-explanation.ts#L235)). Con un `cycleId` que enlazar y **sin** fila, un `verificationsError` se declara estado `unknown` con el rótulo «No disponible» (constante [`ABSENT_DATA_NOT_AVAILABLE`](../../../../apps/web/src/components/absent-data.ts)) — **nunca** «Sin verificación». La **ausencia real** sólo se declara con la lectura **correcta** y sin fila; sin `cycleId`, el hueco es real (no hay nada que enlazar). Regla `UNKNOWN != 0`.

---

## 4. Verificación

- **Web:** `pnpm --filter @bolsa/web test` — unitarias del read-model y del panel (casos añadidos: camino feliz con identidad completa; misma clave en **distinto instrumento**; misma estrategia e instrumento en **distinta cuenta**; ciclo **sin** clave declarada; **fallo de lectura** de la verificación ⇒ `unknown`/«No disponible»). `typecheck` **OK** · `eslint` **0 errores**.
- **Shared:** `pnpm --filter @bolsa/shared test` (etapa `EXPLANATION` con la clave exacta del ciclo).
- **Contrato:** `pnpm contract:check` **OK** (sin cambio: `apps/web` + `packages/shared` puros).
- **E2E (mock):** `gp-e2e-s5` verde (3/3) tras calentar Vite (no toca el escenario integrado).
- **Guardián de bump:** `test_dia_d_bump_guard` **1 passed** (`2.11.138-beta`).
- **Deltas:** `git diff --name-only -- packages/py apps/api-python/src` **vacío** ⇒ **`Δ motor = 0`** · **`Δ decisión = 0`**; sin `contract:gen` ⇒ **`Δ contrato HTTP = 0`**; sin migración.

---

## 5. Límites declarados (sin fabricar)

- La **ventana PAPER real** (ADR-046) sigue **`INCONCLUSIVE`** (`0/4 días`, `0/2 regímenes`, `0/32 ciclos`): falta **OPERACIÓN**.
- La **magnitud/rentabilidad** del P&L sigue **NO MEDIDA**.
- La evidencia DÍA-D por valor **no** aporta identidad de estrategia (solo el `cycleId` la da exacta). Añadirla exigiría campos de estrategia en `values[]` ⇒ **cambio de contrato HTTP** (fuera de alcance).
- Tag **unsigned**. Este sello **no demuestra rentabilidad**.

### 5.1 Ventana PAPER — estado medido al cerrar el sello (2026-10-16)

Ledger local (`operability_runs/window-runs/ledger.jsonl`, artefacto **no** versionado):

| día | estado | régimen |
| --- | --- | --- |
| `20261014` | `NO_MEDIDO_REGIMEN` | `BEAR_TREND` |
| `20261015` | `NO_MEDIDO_REGIMEN` | `BEAR_TREND` |
| `20261016` | `NO_MEDIDO_REGIMEN` | `BEAR_TREND` |

`medidos=0 · veto=3 · declarados=0 · duros=0` ⇒ gate **`NO_MEDIDO`**: la ventana sigue
**`0/4 días`, `0/2 episodios`, `0/32 ciclos` ⇒ `INCONCLUSIVE`**. No es un fallo: el mercado veta LONG
(23 `trend_down` / 7 `range` / 5 `trend_up` sobre los 35 valores del ESTUDIO el `2026-10-16`) y el
eje operativo es el **más conservador** del watch. **No** se fuerza el régimen ni se toca ADR-046. El
día `20261016` ya estaba **registrado** a las `08:37` (preflight read-only ⇒ `BEAR_TREND`, LONG
vetadas): `run-day` es **idempotente** por día, así que no hay nada nuevo que medir sin `--force`.

---

## 6. Cierre POST-TAG — tag `v2.88.138-beta` y su CI de etiqueta

El tag (**anotado, unsigned**) se publica sobre el commit cuyo **pin PAPER casa con su árbol** — no
sobre el commit del sello —. Motivo (fail-closed): el gate `pnpm window:freeze` del job `shared`
compara los **dos tree hashes** del pin con `HEAD:apps`/`HEAD:packages`; en el commit del sello el pin
aún cita el árbol **previo** ⇒ taggearlo deja su propio CI en `TREE_MOVED` (runbook P1-P4 §4).

| paso | commit | contenido |
| --- | --- | --- |
| sello (contenido) | _pendiente_ | bump `2.11.138-beta` + `meta.bump` (13 CLIs) + CHANGELOG + `CURRENT_SYSTEM`/`PROJECT_STATE` + evidencia |
| re-anclaje del pin | _pendiente_ | `pnpm run window:pin -- --note "sello v2.88.138"` ⇒ `apps`/`packages` del árbol del sello, `freeze OK` (`scripts/` no participa del freeze) |

**`Release tag CI` — run [`_pendiente_`]:** _pendiente de publicar el tag y observar el CI._
