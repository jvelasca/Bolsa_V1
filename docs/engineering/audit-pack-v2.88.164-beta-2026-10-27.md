# Audit pack — `v2.88.164-beta` (auditable desde GitHub)

> **AsOf:** 2026-10-27 · **Repo:** [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) (**público**) · **Tag:** `v2.88.164-beta`
> **Propósito:** reunir en un solo sitio **todo lo necesario para auditar esta versión desde GitHub sin credenciales**: identidad inmutable, cómo obtenerla, qué **certifica**, qué **NO**, y cómo **falsarlo**.
> **Naturaleza:** sello de **remediación** de la auditoría de detección compras/ventas. **`Δ motor ≠ 0`** acotado a evaluación de señal y decisión de salida · **`Δ decisión ≠ 0`** en el camino ACTIVE y en posiciones con tesis invalidada · **contrato HTTP aditivo** · **SIN migración nueva** · Tag **unsigned** (anotado, sin firma GPG).

---

## 0. TL;DR — auditar en dos comandos

```bash
git clone --branch v2.88.164-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git
```

O, más estricto (fija el **commit** exacto, no el tag):

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1 && git checkout 133625155f3dc9bbf29795e72344d6813641eb65
```

---

## 1. Identidad inmutable del sello

| Elemento | Valor |
| --- | --- |
| **Tag (anotado)** | `v2.88.164-beta` |
| **Objeto de tag** | `8c4c4f34eeb3eed19bce1b15f206a3c9b2ef2d12` |
| **Commit apuntado** | `133625155f3dc9bbf29795e72344d6813641eb65` (**re-anclaje del pin** PAPER) |
| **Commit del sello** | `3e9ab2cc` (bump + CHANGELOG + evidencia + contrato) |
| **Commit documental POST-TAG** | `c2513098` (cita del run; posterior al tag) |
| **Base (tag anterior)** | `v2.88.163-beta` → `84f58d0f` |
| **Versión monorepo** | `2.11.164-beta` ([`package.json`](../../package.json)) |
| **Alembic head** | `058_estudio_daily_proposals` (**sin migración nueva**) |
| **Firma** | **unsigned** (anotado, sin GPG) |
| **Alcance** | **25 commits**, **52 ficheros**, +6 236/−164 |

> **Nota:** el tag apunta al commit de **re-anclaje** `13362515`, inmediatamente posterior al sello `3e9ab2cc`, porque el bump mueve `apps` (los `meta.bump` viven en `apps/api-python/scripts`) y el `window:freeze` del job `shared` es **fail-closed**. Los dos tree hashes del pin (`apps 381aa48…`, `packages 54a96c1…`) son los del árbol del sello.

---

## 2. Cómo obtener la versión

| Forma | Comando / enlace |
| --- | --- |
| Clonar el tag (recomendado) | `git clone --branch v2.88.164-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git` |
| Fijar el commit SHA | `git checkout 13362515` |
| Ver el árbol en la web | [tree/v2.88.164-beta](https://github.com/jvelasca/Bolsa_V1/tree/v2.88.164-beta) |
| Ver el commit del sello | [commit/3e9ab2cc](https://github.com/jvelasca/Bolsa_V1/commit/3e9ab2cc) |

---

## 3. Evidencia — qué leer, en orden

| # | Documento | Qué responde |
| --- | --- | --- |
| 1 | [`evidence/v2.88.164/README.md`](https://github.com/jvelasca/Bolsa_V1/blob/v2.88.164-beta/docs/engineering/evidence/v2.88.164/README.md) | Los doce frentes, la tabla de gates y el **cierre POST-TAG** |
| 2 | [`CHANGELOG.md` §`2.11.164-beta`](https://github.com/jvelasca/Bolsa_V1/blob/v2.88.164-beta/CHANGELOG.md) | Nota de release: alcance, deltas, verificación y límites |
| 3 | [`PROJECT_STATE.md` AsOf `V2.88.164-beta`](https://github.com/jvelasca/Bolsa_V1/blob/v2.88.164-beta/docs/engineering/PROJECT_STATE.md) | Estado vivo y qué queda abierto |
| 4 | [`auditoria-deteccion-compras-ventas-entorno-diario-2026-10-26.md`](https://github.com/jvelasca/Bolsa_V1/blob/v2.88.164-beta/docs/engineering/auditoria-deteccion-compras-ventas-entorno-diario-2026-10-26.md) | Los 21 hallazgos, §9.1–§9.11 con lo aplicado y la matriz de trazabilidad |
| 5 | [`verificacion-auditoria-deteccion-compras-ventas-2026-10-26.md`](https://github.com/jvelasca/Bolsa_V1/blob/v2.88.164-beta/docs/engineering/verificacion-auditoria-deteccion-compras-ventas-2026-10-26.md) | Verificación independiente y §12.8–§12.18 |

---

## 4. CI público (citable)

**`Release tag CI` del tag (VERDE):** [run **40508374102**](https://github.com/jvelasca/Bolsa_V1/actions/runs/40508374102) — `success` en **12m32s** (2026-10-27T13:00:52Z → 13:13:24Z), sobre `133625155f3dc9bbf29795e72344d6813641eb65`.

| Job | Conclusión | Evidencia medida |
| --- | --- | --- |
| `shared (build/typecheck/test)` | success | **`freeze OK (13362515)`** + `window:test` **50 passed** + **99 ficheros** |
| `frontend (typecheck/lint/test/build + contract:check)` | success | **`Contract check (no gen)`** y **317 ficheros** |
| `python (ruff/imports/mypy/pytest offline)` | success | **`5567 passed, 62 skipped`** (104 s); `mypy` **573**; `Contracts: 4 kept, 0 broken` |
| `lifecycle-pg (Alembic + auth + golden restart)` | success | W-G2/2 **176** · account isolation **45** · Golden Day **3** · AUTO ruta REAL **7** · universe/DÍA-D/watch/PAPER/chain/identity/attempt cap **23** (incluye `scan_queue_health_pg`) · crash **2** · concurrent **3** · hardkill **2** · crash matrix **2** · multiprocess **1** |
| `playwright (live AUTO daily chain)` | success | **`2 passed (36.7s)`**; `Start AUTO_OPS worker` y guard anti-skip verdes |
| `playwright (mock E2E)` | success | **139 passed (11.3m)** |
| `playwright (integrated AUTO S5)` | success | **8 passed (1.5m)** |
| `playwright (integrated axe)` | success | **32 passed (2.6m)** |
| `replay-repro (regenera el artefacto del sello desde el fixture)` | success | **`REPRODUCIDO`** `sha256 E9B7376B…F5625`, 2ª corrida **idéntica** ⇒ **`Δ decisión = 0`** |
| `a7-gate (A7 C3 chaos live_a7 · dedicated real-PG)` | success | **7 passed (15.6 s)** |
| `decision-spine` | success | **621 passed** |
| `security (gitleaks)` | success | — |
| `dr-verify (battery DB_DR / TCP CI)` | success | — |
| `certify (aggregate + artifact)` | success | agrega y **certifica** |
| `playwright (integrated E2E, opt-in)` | **skipped** (opt-in por diseño) | **no certifica** |

**Artefactos descargables** (pestaña *Artifacts* del run):

| Artefacto | Tamaño | Id |
| --- | --- | --- |
| `release-tag-ci-summary` | 436 B | `12737565111` |
| `replay-oos-durable-v2.88.7` | 277 164 B | `12735444485` |
| `playwright-live-auto-daily` | 5 756 B | `12735828026` |
| `playwright-integrated-auto-s5-timings` | 26 492 B | `12735309149` |

---

## 5. Qué **certifica** esta versión

Cierra **16 de los 21 criterios** falsables de la auditoría de detección compras/ventas. Los doce frentes:

1. **B-1/B-6 — warmup por preset medido sobre la serie.** `preset_evaluability` (profundidad `1` comparaciones, `2` cruces); umbrales de los **21** presets de `1` a **201**; el scan emite `warmup_insufficient: …` y el decisor declara el motivo en `memo`.
2. **B-3 — el estado `gated` sale del libro.** `assume_long` + `long_by_symbol` (callable): una posición abierta **antes** de la ventana puede salir; no se re-entra; libro ilegible ⇒ `HOLD`.
3. **P1-12b — «no evaluable» ≠ «sin señal».** `scan-silence.ts` clasifica `not_evaluable` / `insufficient_data` / `other` con el prefijo estable exportado en `@bolsa/shared` (**14** pruebas).
4. **O-6 — el journal declara con qué dato se decidió.** `featureSource` (`real` sólo si **todas** las barras son completas) y `signalWindowBars`; lo no medido se **omite**.
5. **S-1 — F5 resuelve por sugerencia, no por status** (`TRIGGERED`/`ARMED`): un `TIME_STOP` vencido es una salida en las dos capas.
6. **S-2 — una sola tabla de salidas protectoras**: `THESIS_INVALIDATION` vende bajo `CRITICAL`.
7. **S-3 — `EXIT_PENDING` sólo con orden emitida**; lo demás se declara `exit_not_emitted`.
8. **O-1/O-2 — el settle fallido se cuenta** (`settlement_failed`) **y el modo estructural se publica** (`structural`, `structuralOrders`).
9. **T-1/T-2 — la cola del scan se declara y el scan diario corre ya**: `scan_queue_stalled` con acción si `pending` ≥ 300 s, primer tick inmediato y dedupe durable por SQL.
10. **S-6 — el AUTO consulta F5 antes de una salida** y lo declara (`exemption = auto_sim_exit_precedence`, `blocksExit: false`).
11. **B-5 — la ACTIVE dice por qué no operó**: `hold_reason` tipificado + evento `auto_active_strategy_hold`, una vez por `(símbolo, motivo, barra)`.
12. **Contrato y CI**: `openapi.json`/`schema.d.ts` regenerados (`AutoOpsJobSlotDto`, 231 rutas / 495 esquemas) — el `contract:check` estaba **rojo** en el árbol de partida y aquí queda **verde en el CI**.

**Trazabilidad:** implementados `B-1`, `B-2`, `B-3`, `B-4`, `B-5`, `B-6`, `O-1`, `O-2`, `O-5`, `O-6`, `S-1`, `S-2`, `S-3`, `S-6`, `T-1`, `T-2`; con criterio y evidencia E0/E2 parcial `S-4`, `S-5`, `O-3`, `O-4`, `T-3`. **Ningún hallazgo llega a E3.**

---

## 6. Límites / huecos **declarados** (lo que NO certifica)

1. **AUTO sigue OFF**; la operativa es **100 % PAPER virtual**, sin LIVE ni XTB real.
2. **La ventana PAPER sigue `INCONCLUSIVE`** (`episodios 0/2`, `ciclos 0/32`). Este sello **no la mueve** y un CI verde **no** la certifica.
3. **Evidencia E1** (hermética) salvo `S-6` y `T-1`, con **E2** parcial por CI; **ningún** hallazgo llega a **E3**. No hay operación real medida.
4. **No demuestra rentabilidad.** Los cambios corrigen silencios y declaraciones; no validan señales ni P&L.
5. **`T-3` sigue abierto**: el bucle AUTO de 60 s sobre señal D1 se declara en el diseño y se prueba por fronteras de barra, no como cadencia sellada.
6. **`S-4`/`S-5`/`O-3`/`O-4`**: criterio escrito sin prueba ejecutada.
7. **El fallo local de concurrencia** (`test_multi_portfolio_ledger_sequence`, `ValueError: Cartera no encontrada`) se declara: pasa `1 passed` en aislamiento y falló por compartir base con la suite paralela.
8. **El artefacto congelado del replay no cambia** (`E9B7376B…F5625`): el sello no mueve la decisión del replay, y eso es lo que el CI mide, no una mejora de resultado.

---

## 7. Falsabilidad — cómo un auditor **rompe** cada afirmación

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | El tag apunta a `13362515` y desciende de `v2.88.163-beta` (`84f58d0f`). | `git rev-parse` / `git cat-file -p` del tag da otro commit o linaje. |
| 2 | `2.11.164-beta` es la versión del árbol y los **13** `meta.bump` coinciden. | `package.json` muestra otra versión o `test_dia_d_bump_guard` falla. |
| 3 | Sin migración: head `058_estudio_daily_proposals`. | `alembic heads` da otro head. |
| 4 | El `contract:check` está verde y es aditivo. | `pnpm contract:check` falla o el diff no se limita a `AutoOpsJobSlotDto`. |
| 5 | El freeze del tag es OK. | `node scripts/window-pin.mjs --check` da `TREE_MOVED`. |
| 6 | El warmup de los 21 presets está medido y no deducido. | `test_preset_evaluability.py` con una serie corta declara evaluable un preset, o el umbral de `golden_cross` deja de ser 201. |
| 7 | `gated` sale del libro. | `test_held_position_exits_without_an_entry_in_the_window` deja de emitir `SELL` con posición abierta. |
| 8 | `EXIT_PENDING` exige orden. | Un `hold` del manager deja `lifecycleState = EXIT_PENDING` (rompe `test_exit_pending_requires_emitted_order`). |
| 9 | La ACTIVE declara motivo. | `ACTIVE_STRATEGY=1` + `SIGNAL=0` produce `HOLD` sin `auto_active_strategy_hold` (rompe `test_auto_active_strategy_hold_b5.py`). |
| 10 | El CI del tag es verde. | El run citado tiene algún job obligatorio en `failure` o `certify` rojo. |
| 11 | `replay-repro` reproduce byte a byte. | El `sha256` del artefacto regenerado difiere de `E9B7376B…F5625`. |

---

## 8. Reproducir la verificación (local, opcional)

```bash
# Bump y contrato
uv run pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
pnpm contract:check

# Suites herméticas
uv run pytest packages/py/application/tests -q
uv run pytest apps/api-python/tests -q -m "not integration"
pnpm --filter @bolsa/web test
pnpm --filter @bolsa/shared test

# Gates de ventana
pnpm window:test
node scripts/window-pin.mjs --check
```

**Resultados de referencia medidos en este árbol:** `application` **2944 passed** · `analytics` + `infrastructure` **1547 passed** · `api-python` offline **1405 passed** · `web` **2371 passed / 317 ficheros** · `shared` **855 passed / 99 ficheros** · `typecheck` 4/4 · `lint` **0 errores** · `window:test` **50 passed** · guardián de bump **2 passed**.
