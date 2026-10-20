# Evidencia `v2.88.154-beta` — la cadena por valor se puede auditar de punta a punta

> **Naturaleza:** sello **posterior y acotado** a `v2.88.153-beta`. **`Δ motor = 0`** ·
> **`Δ decisión = 0`** · **`Δ contrato HTTP = 0`** · **sin migración nueva** (head
> `057_top3_opportunity_identity`).
>
> **Bump** `2.11.153-beta` → **`2.11.154-beta`** (+ `meta.bump` de los **13** CLIs) y tag
> anotado **`v2.88.154-beta`**. La evidencia publicada de `.153` **no se reescribe**.
>
> **AUTO sigue OFF** y la ventana PAPER sigue **`INCONCLUSIVE`**. Un CI verde no certifica
> rentabilidad.

## 1. Qué publica este sello

Tres frentes que quedaron en `main` **después** del tag `.153`, ahora bajo un solo sello:

| Bloque | Contenido |
| --- | --- |
| **A · P2 de `.153`** | La migración `057` **falla cerrado** si falta su tabla base (`assert_base_table_present`) y la identidad se mide en **tri-estado** (`COMPLETE`/`PARTIAL`/`UNKNOWN`). |
| **B · Batería POR VALOR** | Nuevo arnés PostgreSQL que recorre el camino productivo completo, con control negativo del tri-estado. |
| **C · Auditoría** | Cinco hallazgos (`H1`–`H5`) sobre esos commits, **todos** cerrados antes de sellar. Detalle: [`auditoria-sello-v2.88.154-2026-10-20.md`](../auditoria-sello-v2.88.154-2026-10-20.md). |

La cadena que el arnés demuestra:

```
top3_opportunities (rank 1, preset+versión)      ← identidad GANADORA
      ↓
auto_entry_decision (signalId, opportunityId, rank, preset, versión)
      ↓  decisionId == cycle_decision_id(cycleId)
TradePlan · PortfolioReservation(side='buy') · SimFillFinanceContext
      ↓
auto_cycle_settlement · CYCLE_CLOSED  (9 etapas durables)
      ↓
dia_d_cycle_verifications (identidad copiada del ciclo)
      ↓
pnl.reconciled  ==  libro aplicado  (quantum 0.000001)
```

Diseño, límites y cómo ejecutarlo: [`bateria-integrada-por-valor-2026-10-20.md`](../bateria-integrada-por-valor-2026-10-20.md).

## 2. El defecto de lectura que la batería destapó

`auto_operational_monitor._build_cycle` tomaba `reservations[0]`. Desde `V2.47` la **salida**
también declara `cycle_id` y el orden durable (`list_recent_with_cycle`, **DESC**) la pone
primero (`exit:<orderId>`, `side='sell'`, **sin** `strategy_version_id`) ⇒ un ciclo **cerrado**
se publicaba con `direction='short'` y `strategyVersion=None` pese a que ambos hechos existían
en la entrada.

Nueva `_entry_reservation(...)`: prefiere la **entrada** (`side='buy'`), conserva el orden
histórico si no la hay y **no** inventa nada. **Precondición declarada:** AUTO 2.0 es **largo
solamente**; si algún día se abriesen cortos, el discriminador correcto sería el prefijo
`exit:` del `reservation_id`.

**Radio de impacto (declarado en la auditoría):** la corrección **también** repara la
verificación DÍA-D de ciclos cerrados, porque `POST /api/auto/dia-d-verifications` deriva la
identidad por `resolve_dia_d_cycle_facts` → monitor. Antes, esa fila se persistía con
`strategy_version = NULL` (hueco silencioso; **no** había `409` espurio porque el contraste se
omite cuando el hecho durable es `None`). **No hay backfill**: las filas anteriores conservan
su hueco y se leen como desconocidas.

## 3. Verificación medida (local, antes del tag)

| Comprobación | Resultado |
| --- | --- |
| Batería PG (positivo + control negativo, gate ON) | **2 passed in 2.83 s** |
| Cadena ESTUDIO (proceso real, gate ON) | **1 passed in 9.11 s** |
| `test_auto_operational_monitor.py` (puros; +4 de la auditoría) | **67 passed** |
| `test_auto_chain_durable_reader.py` (tri-estado) | **17 passed** |
| Suite Python completa (`api-python` + `application` + `infrastructure`) | **4324 passed / 6 failed** — contienda con el stack dev vivo: **cinco** verdes en aislamiento (**25 passed**) y el sexto es el caos **conocido** `test_c3a` |
| `vitest src/features/auto-monitor` | **21 ficheros / 169 tests** |
| `pnpm typecheck` / `pnpm lint` | **4/4** · **0 errores** (23 avisos) |
| `pnpm lint:py` / `imports:py` / `types:py` | **`All checks passed!`** · **4/0** · **0 issues / 567** |
| `contract:check` | **OK** (sin diff) |
| Censo `test_selection.py --report` | **651/651 · 0 sin declarar · 0 obsoletas** |
| Guardián de bump | **2 passed** |

Sobre los seis rojos de la suite completa, sin adornos: el equipo tiene el **stack dev vivo**
(`queue_poll_worker` ×2 y `scheduler_worker` ×2, PIDs 18084/24364/46024/34540) drenando el
mismo outbox; se reintentaron los seis módulos en aislamiento y **cinco** pasan. El que
persiste —`test_c3a_crash_after_recovery_claim_then_second_is_exact_once`, «drained=0
resolved=0»— es el caos **ambiental declarado desde `.138`** (necesita acceso exclusivo a la
BD), no una regresión de este sello.

## 4. Auditoría del sello (`H1`–`H5`)

| # | Severidad | Hallazgo | Cierre |
| --- | --- | --- | --- |
| **H1** | `P3` | El docstring de `_drive_cycle` describía un cierre por `SELL` inyectada que **no ocurre** (el arnés cierra por `time_exit`). | Docstring corregido al mecanismo real. |
| **H2** | `P2` | `direction` **no tenía ninguna aserción** y es justo el campo que el defecto deformaba. | **4** tests puros de `_entry_reservation` (incluido salida-primero) + `direction == "long"` en positivo y control negativo. |
| **H3** | `P3` | La regla de entrada no declaraba su precondición (largo solamente). | Declarada en el helper y en el documento, con el discriminador futuro (`exit:`). |
| **H4** | `P2` | El radio de impacto estaba **subdeclarado** (también afectaba a la escritura DÍA-D). | Declarado; sin backfill; `Δ decisión = 0`. |
| **H5** | `P3` | La cita de freeze del `[Unreleased]` había quedado obsoleta. | Este sello escribe la cita medida. |

**Ningún `P1`** de motor, decisión, contrato ni esquema.

## 5. Límites declarados (sin fabricar)

- **AUTO sigue OFF**; no se enciende la cadencia. La batería demuestra **trazabilidad, no
  rentabilidad**.
- El parte diario ESTUDIO **no comparte identidad** (`estudio_auto` / `strategyVersion=1`) y
  `estudio_daily_ops` descarta `decisionId`: el enlace identidad-del-TOP3 → parte diario sigue
  sin existir.
- El `TradePlan` no publica `planId`/`signalId` en el DTO del ciclo: la atribución plan↔ciclo se
  demuestra por `decisionId`/`thesis_id`, no por el contrato de la UI.
- La verificación DÍA-D del arnés es una fila **derivada del ciclo**, no un replay real.
- `executedIsBestScoredAsset` compara `instrumentId` **sin canonizar símbolos**: se documenta
  como observación, no como contrato.
- Las fotos `top3_opportunities` anteriores a la `057` y las filas DÍA-D anteriores a esta
  corrección quedan con su hueco (`NULL`), **sin backfill**.
- Operativa **100 % SIM**; no se envían órdenes reales. Tag **anotado, unsigned**.

## 6. Freeze

El sello mueve `apps` —no solo `tests/`: el `meta.bump` de los 13 CLIs vive en
`apps/api-python/scripts`— y `packages` ⇒ el pin PAPER se **re-ancla** al árbol del sello
(`apps e162746a…` / `packages be243531…`) para que el run de las 18:00 no aborte con
`TREE_MOVED`; `pnpm window:freeze` ⇒ **`freeze OK`** y `pnpm window:test` **50 passed**.

## 7. Publicación

Se publica como `v2.88.154-beta` (anotado, unsigned) sobre el commit **`e3bcbe86`**.

**Cita POST-TAG — CI del sello VERDE.** `Release tag CI` [run **`39424571552`**](https://github.com/jvelasca/Bolsa_V1/actions/runs/39424571552) ⇒
**`conclusion: success`** (**13 jobs `success`**, `certify` incluido; **1 job `skipped`**
declarado: `playwright (integrated E2E, opt-in)`, que **no certifica**), `2026-10-20T12:44:04Z`
→ `12:58:58Z` (**14m54s**).

| Job | Resultado medido |
| --- | --- |
| `shared` | **`freeze OK (e3bcbe86)`** — el pin re-anclado no declara `TREE_MOVED`. |
| `replay-repro` | **`REPRODUCIDO`**: `sha256 E9B7376B…7F5625`, `3 383 461` bytes, `DIGEST` **igual en las dos corridas** ⇒ **`Δ decisión = 0` medido por el CI**. |
| `lifecycle-pg` | Paso `Pytest AUTO universe coverage + DÍA-D trace + daily watch ESTUDIO + PAPER window + ESTUDIO chain + identity battery (PG, fail if skipped)` ⇒ **21 passed in 35.88s** con `AUTO_IDENTITY_CHAIN_PG_REQUIRED=1` y guard anti-skip **verde** (log no vacío + **sin** `skipped`) — la batería de identidad corrió **en el CI del tag**; `multiprocess AUTO` **1 passed in 113.35s**. |
| `playwright (integrated AUTO S5)` | **8 passed, todos al primer intento (`retry 0`)**; `S5-04` en **5.64s**. |
| `python` · `frontend` (`contract:check`) · `playwright (mock E2E)` · `playwright (integrated axe)` · `a7-gate` · `dr-verify` · `decision-spine` · `security` · `certify` | **`success`**. |

El run **no certifica rentabilidad**: **AUTO sigue OFF**, la ventana PAPER sigue
**`INCONCLUSIVE`** y **`CONFIRMED` no se emite**. Tampoco se da por bueno ningún intento rojo:
no lo hubo.

**Entrada de auditoría en GitHub.** El sello se publica además como **GitHub Release**
[`v2.88.154-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.88.154-beta)
(**pre-release**, publicado `2026-10-20T15:29:20Z`), cuyo cuerpo es un **audit pack
autosuficiente** —identidad inmutable, jobs y artefactos del run, límites declarados y tabla de
**falsabilidad**— para auditar **sin credenciales**: basta clonar el tag o abrir la página del
release. El release cuelga del **tag** (`e3bcbe86`), no de esta cita: el commit de la cita es
`69e416c5`, **por delante** del tag, igual que este documento.
