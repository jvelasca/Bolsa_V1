# Verificación independiente del sello `v2.88.138-beta` + estado de la ventana PAPER (2026-10-16)

> **Qué es:** la verificación **independiente** del sello `v2.88.138-beta` (procedencia git/CI,
> cierre de los dos hallazgos de auditoría y deltas declarados) y el **estado medido** de la
> ventana PAPER (ADR-046), con los instrumentos que el operador usará para acumular evidencia.
>
> **Qué NO es:** no promociona la ventana, no declara AUTO validado y no demuestra rentabilidad.
> La ventana sigue **`INCONCLUSIVE`**: lo que falta es **OPERACIÓN** (días de mercado con LONG
> permitida), no software.

**Sello:** `v2.88.138-beta` · **commit de contenido** `bf606d69` · **commit del tag** `f79484d1` ·
**versión del paquete** `2.11.138-beta`.

---

## 0. Dictamen (una línea por hallazgo)

| # | Hallazgo | Veredicto | Evidencia |
| --- | --- | --- | --- |
| 1 | Procedencia del tag (apunta al commit del CI verde; anotado; unsigned; `main` sólo documental) | **CONFIRMADO** | §1 |
| 2 | Identidad de la sesión LAB **fail-closed** (tripartita exacta) | **CERRADO Y REPRODUCIDO** | §2 |
| 3 | Verificación durable: **lectura ≠ ausencia** (`unknown`/«No disponible») | **CERRADO Y REPRODUCIDO** | §2 |
| 4 | `Δ motor = 0` · `Δ decisión = 0` · `Δ contrato HTTP = 0` · sin migración · umbrales ADR-046 `4/2/32` intactos | **CONFIRMADO** | §3 |
| 5 | Cobertura del guardián de bump (`v2_87` fuera) | **HALLAZGO NUEVO — CORREGIDO** (test-only) | §4 |
| 6 | `pnpm contract:check` no ejecutable desde la raíz (la evidencia lo citaba así) | **HALLAZGO NUEVO — CORREGIDO** | §5 |
| 7 | Ventana PAPER certificada | **NO** — `INCONCLUSIVE` (0/4 · 0/2 · 0/32) | §6 |
| 8 | Bloqueador de entorno (cuenta de la ventana ausente) | **DETECTADO Y RESUELTO** (re-siembra con el id fijo) | §7.2 |

Los dos hallazgos de auditoría del incremento `9f0ae3ad` **quedan cerrados**, con una salvedad
formal (tag unsigned) y un **bloqueador de OPERACIÓN** para la ventana (§7).

---

## 1. Procedencia del sello (medido)

| Comprobación | Evidencia | Resultado |
| --- | --- | --- |
| Objeto del tag | `git cat-file -t v2.88.138-beta` | `tag` (**anotado**, objeto `ed03f876…`) |
| Commit del tag | `git rev-list -n 1 v2.88.138-beta` | `f79484d1` (padre `bf606d69`) |
| Firma | `git verify-tag v2.88.138-beta` | `error: no signature found` (**unsigned**) |
| CI del tag | `gh run view 38911216158` | `success`, `headSha f79484d1` |
| Jobs | — | **14 jobs = 13 `success` + 1 `skipped`**; `certify` está **entre** los 13 `success`; el único `skipped` es `playwright (integrated E2E, opt-in)` |
| `main` vs tag | `git diff --name-only v2.88.138-beta..HEAD` | `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/PROJECT_STATE.md`, `docs/engineering/evidence/v2.88.138/README.md` — **solo documentación** (sin `apps/`, sin `packages/`, sin `package.json`) |
| Freeze | `pnpm run window:freeze` | `freeze OK (60d02446)` · apps `4a36b7b1…` · packages `6d006d6c…` |

El tag porta el commit **cuyo pin casa con su propio árbol** (`f79484d1`): es el mecanismo
fail-closed del job `shared` (taggear el commit del sello daría `TREE_MOVED`). El pin vigente **ya
casa con `HEAD`**: no hace falta re-anclar antes de operar.

### 1.1 Salvedades declaradas (no invalidan el cierre)

- **Tag unsigned:** la firma criptográfica no acredita autoría; el CI sí pasó.
- **`_pendiente_` dentro del tag:** la evidencia **del tag** conserva 3 marcadores de publicación/CI;
  el commit **POST-TAG** `60d02446` los sustituye por los SHAs reales y el run verde. `main` queda
  correcto; sólo el snapshot histórico del tag no es autocontenido en esa sección.

---

## 2. Los dos hallazgos de auditoría (reproducidos)

Cerrados en `7200fd05` (Web) y re-verificados aquí de forma independiente.

1. **Identidad de la sesión LAB — fail-closed.** [`resolveLab()`](../../../apps/web/src/features/auto/auto-strategy-dia-d-explanation.ts)
   exige coincidencia **exacta** de `instrumentId` + `accountId` + `strategyPresetKey`; **no** existe
   respaldo por `definitionId`, y cualquier hueco ⇒ **no vinculada**. Los **5 casos de falsación**
   están asertados en [`auto-strategy-dia-d-explanation.test.ts`](../../../apps/web/src/features/auto/auto-strategy-dia-d-explanation.test.ts):
   mismo `presetKey` en **otro instrumento**, misma estrategia+instrumento en **otra cuenta**, ciclo
   **sin clave**, sesión **sin cuenta** y camino feliz.
2. **Lectura de la verificación — lectura ≠ ausencia.** [`resolveVerification()`](../../../apps/web/src/features/auto/auto-strategy-dia-d-explanation.ts)
   con `cycleId` enlazable y **fallo de lectura** declara `unknown` / «No disponible»
   ([`ABSENT_DATA_NOT_AVAILABLE`](../../../apps/web/src/components/absent-data.ts)); «Sin verificación»
   queda reservado a la lectura **satisfactoria sin fila**. Jamás se emite `CONFIRMED` ni se
   promocionan `READY`/`MATCH`/`OOS_SUPPORTED`.

**Medido:** `pnpm --filter @bolsa/web test` **2272/2272** · `pnpm --filter @bolsa/shared test`
**831 (+1 todo)** · `typecheck` limpio · `lint` **0 errores** (23 avisos preexistentes).

---

## 3. Deltas declarados (medidos, no asumidos)

| Delta | Comprobación | Resultado |
| --- | --- | --- |
| `Δ motor = 0` · `Δ decisión = 0` | `git diff --name-only bf606d69^ bf606d69 -- packages/py apps/api-python/src` | **vacío** |
| `Δ contrato HTTP = 0` | `pnpm contract:check` (§5) | `OK` |
| Sin migración | búsqueda de `openapi`/`schema`/`contract`/`*.d.ts` en el diff | **ninguno** |
| Umbrales ADR-046 | `git diff … -- operability_window.py` | **vacío**; valores `4 / 2 / 32` intactos |
| Suites Python focalizadas | `pytest` (bump guard + protocolo PAPER + ruta + certificador) | **23/23** |

**Matiz declarado.** El commit `bf606d69` es de **bump + documentación**; el entregable de
UI/read-model (`auto-strategy-dia-d-explanation.ts`, `auto-operation-story.ts`) vive en `3cb74501`.
«Solo `apps/web` + `packages/shared`» es cierto del **rango** del incremento, no de `bf606d69` solo.

---

## 4. Hallazgo NUEVO — cobertura del guardián de bump (`v2_87`)

**Medido.** El sello bumpeó **13** scripts (`git diff --name-only bf606d69^ bf606d69`), pero
[`test_dia_d_bump_guard`](../../../apps/api-python/tests/test_dia_d_bump_guard.py) sólo asertaba
**12**: **`v2_87` quedaba fuera**.

**Matiz decisivo.** `v2_87` emite **dos** artefactos con `bump`:

| literal | artefacto | destino | ¿sigue la versión del monorepo? |
| --- | --- | --- | --- |
| `2.11.138-beta` | banda OOS financiera (`_run_finance_band`) | `operability_runs/oos-finance-band/…` (gitignored) | sí (el sello lo bumpeó) |
| `2.11.0-beta` | **replay OOS durable** (censo + replay) | el `--out` que **`replay-repro` ASSERTA byte a byte** (`sha256 1E3ADAC2…`, 3 340 728 bytes) | **NO, CONGELADO a propósito** |

Bumpear el segundo literal cambiaría los bytes del artefacto y pondría **ROJO** `replay-repro` — por
eso el sello **no** lo tocó (el `sha256` quedó idéntico a `v2.88.136`/`v2.88.137`). El guardián usa
`re.search` (primer literal), así que cubrir `v2_87` sin declarar el congelado sería un **verde
engañoso**.

**Cobertura real (medida).** Scripts bajo `apps/api-python/scripts/` con clave `bump` = **19**;
fuera del guardián quedan **7**: 6 legacy pinneados a versiones viejas (`v2_42_2`, `v2_43`, `v2_74`,
`v2_75`, `v2_76`, `v2_86`, excluidos a propósito) **+ `v2_87`** (el único con hueco real).

**Remedio (test-only, `Δ motor = 0`).**
[`test_dia_d_bump_guard`](../../../apps/api-python/tests/test_dia_d_bump_guard.py) incorpora `v2_87`
al guardián y añade `test_v2_87_frozen_replay_bump_stays_pinned`, que **declara y ancla** el literal
congelado como tripwire falsable: medido `2 passed`; al «alinear» el literal con la versión del
paquete, el test **dispara**.

---

## 5. Hallazgo NUEVO — `contract:check` desde la raíz

La evidencia cita `pnpm contract:check`, pero el script vivía **sólo** en `apps/web/package.json`
(desde la raíz: `ERR_PNPM_RECURSIVE_EXEC_FIRST_FAIL`). El CI ya lo invoca bien
(`pnpm --filter @bolsa/web contract:check`). Se añade un **alias en la raíz** (`package.json`) que
delega en el filtro; medido `contract:check OK — openapi.json y schema.d.ts coinciden`. Cambio
**freeze-neutral** (raíz, fuera del pin de motor).

---

## 6. Instrumentos nuevos para operar la ventana

| Instrumento | Qué es | Deltas |
| --- | --- | --- |
| `pnpm run window:certify` ([`scripts/window-certify.mjs`](../../../scripts/window-certify.mjs)) | Certifica la ventana (ADR-046) leyendo cuenta y par A/B del **pin** (`WINDOW_CONFIG`), sin repetirlos a mano. Read-only; **no** sustituye la ventana real. | Freeze-neutral (`scripts/` no participa del freeze). `Δ motor = 0`. |

**Salida medida (2026-10-16, cuenta `1484e253d2d54645945a6b1d7`):**

```text
dias=0/4  episodios=0/2  ciclos=0/32  =>  INCONCLUSIVE
criterios faltantes: days, episodes, measurable_cycles
fills leidos 0  ·  ciclos 0  ·  entradas de journal 0
```

Es un **cero MEDIDO** (`measured: true`, la lectura **completó** sin material durable para la
cuenta). El certificado declara `readOnly: true` y `substitutesRealWindow: false`.

---

## 7. Operación diaria de la ventana

Base: [`runbook-cierre-p1-p4-2026-10-15.md`](./runbook-cierre-p1-p4-2026-10-15.md). **Un día de
pared por corrida**; `≥4` **fechas distintas**; `episodes` sale **sólo de ciclos cerrados**.

```bash
pnpm run window:freeze      # 1) fail-closed: debe imprimir "freeze OK"
pnpm run window:preflight   # 2) exit 0 => día medible; exit 2 CON payload => veto (NO se opera)
pnpm run window:run-day     # 3) forward -> journal -> ventana -> auditoría
pnpm run window:evidence    # 4) bundle P1-P4
pnpm run window:status      # 5) estado del ledger (gate ligado al run)
pnpm run window:certify     # 6) certificado (única medida del gate 4/2/32)
```

**Cadena validada sin abrir el motor** (`--dry-run run-day`): `freeze OK` y los 5 pasos del
pipeline (`v2_76` → `v2_77` → `v2_80` → `v2_83`) con los flags de operación inyectados **sólo en el
hijo** (`AUTO_ENGINE_SIM_REAL_PRICE=1`, `AUTO_OPERATIONAL_AUDIT=1`, `BROKER_VENUE=paper`).

**Cadencia automatizada.** `pnpm run window:task:install [--at HH:MM]` registra una tarea diaria de
Windows (`schtasks`) que ejecuta `pnpm window:run-day`. Es **segura por construcción**: `run-day`
evalúa el `freeze` **antes** del preflight y aborta `fail-closed` con `TREE_MOVED`; un veto de
régimen se registra `NO_MEDIDO_REGIMEN` y **no lanza el forward**.

### 7.1 Estado medido del ledger (2026-10-16)

| día | estado | régimen |
| --- | --- | --- |
| `20261014` | `NO_MEDIDO_REGIMEN` | `BEAR_TREND` |
| `20261015` | `NO_MEDIDO_REGIMEN` | `BEAR_TREND` |
| `20261016` | `NO_MEDIDO_REGIMEN` | `BEAR_TREND` |

`medidos=0 · veto=3` ⇒ gate **`NO_MEDIDO`**. El mercado veta LONG; **no se fuerza el régimen**.

### 7.2 BLOQUEADOR del entorno — detectado y **RESUELTO** (re-siembra)

**Antes (medido).** Sonda read-only (`investment_accounts` / `strategy_versions` /
`strategy_promotions`):

| Comprobación | Resultado |
| --- | --- |
| Alembic head | `055_dia_d_identity_nullable` **OK** |
| Cuenta `1484e253d2d54645945a6b1d7` | **AUSENTE** (`investment_accounts` total = 1 fila) |
| `v283-window-b` (fila + localizador `promoted` por cuenta) | presentes, pero **huérfanos** de la cuenta |
| Barras `1d` | `17 854` **OK** (universo ESTUDIO sembrado) |

Con la cuenta ausente, `run-day` **no puede medir**: es un **bloqueador**, no un veto.

**Remedio aplicado** ([runbook §0.1](./runbook-cierre-p1-p4-2026-10-15.md), mismo precedente de
`2026-10-02` / `v2.88.137`): re-sembrar la cuenta con el **MISMO id** forzado
(`create_simulated_account(initial_deposit=100000.0)`, forzando **solo** el id) y después
`ops_seed_window_pair.py --account-id 1484e253d2d54645945a6b1d7 --version-a v283-window-a
--version-b v283-window-b`.

**Después (verificado read-only).**

| Comprobación | Resultado |
| --- | --- |
| Cuenta de la ventana | `('1484e253d2d54645945a6b1d7', 'PAPER-VENTANA-a9c515', 'simulated', 'active')` |
| Cartera de inversión + asiento de depósito | **1 + 1** |
| `v283-window-b` | fila + localizador `promoted` + `EdgeReport` (1/1/1) |
| `EdgeReport` de A | **1** |
| `.env` | `PAPER_D_ACCOUNT_ID=1484e253d2d54645945a6b1d7` · `BROKER_VENUE=paper` **ya declarados** |
| Preflight de hoy | `exit 2` **con payload** ⇒ veto legítimo `BEAR_TREND` (**no** es fallo duro) |
| Ledger | `medidos=0 · veto=3 · duros=0` ⇒ gate `NO_MEDIDO` |

El entorno queda **listo para medir** en el próximo día de mercado con LONG permitida. **Causa de la
desaparición: NO MEDIDA** (la cuenta existía tras la re-siembra de `v2.88.137` a las `12:33` y faltaba
a las `16:2x`); conviene confirmar que ningún proceso recrea/limpia la BD entre sesiones, porque si lo
hace el bloqueador **reaparecerá**.

**Pendiente del OPERADOR para el primer día operable** (no afecta a los días vetados): reiniciar la
API **desde el árbol pineado** (el readiness es *schema-aware*; una API vieja contra la BD migrada
responde `503` y `run-day` abortaría con `API_NOT_READY`, que **no** es veto).
