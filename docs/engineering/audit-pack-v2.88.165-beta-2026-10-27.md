# Audit pack — `v2.88.165-beta` (auditable desde GitHub)

> **AsOf:** 2026-10-27 · **Repo:** [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) (**público**) · **Tag:** `v2.88.165-beta`
> **Propósito:** reunir en un solo sitio **todo lo necesario para auditar esta versión desde GitHub sin credenciales**: identidad inmutable, cómo obtenerla, qué **certifica**, qué **NO**, y cómo **falsarlo**.
> **Naturaleza:** sello de **cierre** de la auditoría de detección compras/ventas. **`Δ motor = 0`** salvo el journal de `S-5` (declara, no opera) · **`Δ decisión = 0`** · **contrato HTTP aditivo** (`venue` nullable + `venueMeasurement`) · **SIN migración nueva** · Tag **unsigned** (anotado, sin firma GPG).

---

## 0. TL;DR — auditar en dos comandos

```bash
git clone --branch v2.88.165-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git
```

O, más estricto (fija el **commit** exacto, no el tag):

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1 && git checkout 00f321bb6e05332b677e7c880ba23442af9486cf
```

---

## 1. Identidad inmutable del sello

| Elemento | Valor |
| --- | --- |
| **Tag (anotado)** | `v2.88.165-beta` |
| **Objeto de tag** | se cita en el **commit POST-TAG** (el tag debe contener este pack, así que su objeto no puede citarse aquí); `git cat-file -p v2.88.165-beta` lo imprime |
| **Commit apuntado** | `00f321bb6e05332b677e7c880ba23442af9486cf` (**re-anclaje del pin** PAPER) |
| **Commit del sello** | `803613db` (código + pruebas + docs + bump + contrato) |
| **Corrección del E2E** | `fb18d729` (`gp-e2e-v290` lee el veredicto del gate; ver §5.6) |
| **Base (tag anterior)** | `v2.88.164-beta` → `133625155f3dc9bbf29795e72344d6813641eb65` |
| **Versión monorepo** | `2.11.165-beta` ([`package.json`](../../package.json)) |
| **Alembic head** | `058_estudio_daily_proposals` (**sin migración nueva**) |
| **Firma** | **unsigned** (anotado, sin GPG) |
| **Alcance del sello** | **5 commits**, **42 ficheros**, +1 271/−62 |

> **Nota:** el tag apunta al commit de **re-anclaje** `00f321bb`, posterior a `803613db` (`068b3fae`) y a la corrección `fb18d729`, porque el bump mueve `apps` (los `meta.bump` viven en `apps/api-python/scripts`) y `packages` (el `venue` nullable de `@bolsa/shared`), y el `window:freeze` del job `shared` es **fail-closed**. Los dos tree hashes del pin (`apps 927c2298…`, `packages 41e0afa8…`) son los del árbol del sello.
>
> **Nota de publicación:** el tag se creó primero sobre `068b3fae`; su CI salió **rojo** en `playwright (mock E2E)` porque `gp-e2e-v290` afirmaba el literal `INCONCLUSIVE` que `O-4` retira. Se corrigió la prueba (`fb18d729`), se re-ancló el pin y el tag/release se **movieron** al árbol corregido el mismo día, antes de citar ningún resultado verde.

---

## 2. Cómo obtener la versión

| Forma | Comando / enlace |
| --- | --- |
| Clonar el tag (recomendado) | `git clone --branch v2.88.165-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git` |
| Fijar el commit SHA | `git checkout 00f321bb` |
| Ver el árbol en la web | [tree/v2.88.165-beta](https://github.com/jvelasca/Bolsa_V1/tree/v2.88.165-beta) |
| Ver el commit del sello | [commit/803613db](https://github.com/jvelasca/Bolsa_V1/commit/803613db) |

---

## 3. Evidencia — qué leer, en orden

| # | Documento | Qué responde |
| --- | --- | --- |
| 1 | [`evidence/v2.88.165/README.md`](https://github.com/jvelasca/Bolsa_V1/blob/v2.88.165-beta/docs/engineering/evidence/v2.88.165/README.md) | Los cinco frentes, la tabla de gates y la falsabilidad |
| 2 | [`CHANGELOG.md` §`2.11.165-beta`](https://github.com/jvelasca/Bolsa_V1/blob/v2.88.165-beta/CHANGELOG.md) | Nota de release: alcance, deltas, verificación y límites |
| 3 | [`PROJECT_STATE.md` AsOf `V2.88.165-beta`](https://github.com/jvelasca/Bolsa_V1/blob/v2.88.165-beta/docs/engineering/PROJECT_STATE.md) | Estado vivo y qué queda abierto |
| 4 | [`auditoria-deteccion-compras-ventas-entorno-diario-2026-10-26.md`](https://github.com/jvelasca/Bolsa_V1/blob/v2.88.165-beta/docs/engineering/auditoria-deteccion-compras-ventas-entorno-diario-2026-10-26.md) | Los 21 hallazgos; **§9.12** con los cinco cierres y la matriz de trazabilidad a **21/21** |
| 5 | [`verificacion-auditoria-deteccion-compras-ventas-2026-10-26.md`](https://github.com/jvelasca/Bolsa_V1/blob/v2.88.165-beta/docs/engineering/verificacion-auditoria-deteccion-compras-ventas-2026-10-26.md) | Verificación independiente del bloque |

---

## 4. CI público (citable)

**`Release tag CI` del tag:** se cita en el **commit POST-TAG**, sobre `00f321bb6e05332b677e7c880ba23442af9486cf`.

> **Estado al publicar este pack:** el run del tag definitivo acaba de encolarse. Su resultado se cita en el **commit POST-TAG** que actualiza este documento y el cuerpo del Release, igual que en los sellos `.163` y `.164`. Mientras no esté citado, **la afirmación «CI verde» NO está certificada para `.165`**: lo que sí está medido es la verificación local de §8 y el intento previo descrito en §1.
>
> **Intento previo (rojo, retirado):** el tag se creó primero sobre `068b3fae`; el run [**40516676602**](https://github.com/jvelasca/Bolsa_V1/actions/runs/40516676602) dio **12 de 13 jobs verdes** —`shared` (`freeze OK (068b3fae)`), `python`, `frontend`, `lifecycle-pg`, `replay-repro` (`REPRODUCIDO`), `a7-gate`, `decision-spine`, `security`, `dr-verify` y los tres `playwright` integrados— y **rojo** en `playwright (mock E2E)`: `gp-e2e-v290` afirmaba el literal `INCONCLUSIVE` que `O-4` retira. No se citó como verde; se corrigió la prueba y se movió el tag.

| Job | Qué gatea | Referencia del sello anterior (`.164`) |
| --- | --- | --- |
| `shared (build/typecheck/test)` | `freeze` del pin + `window:test` + `@bolsa/shared` | `freeze OK (13362515)` + **50 passed** + **99 ficheros** |
| `frontend (typecheck/lint/test/build + contract:check)` | contrato sincronizado + `vitest` | `Contract check (no gen)` + **317 ficheros** |
| `python (ruff/imports/mypy/pytest offline)` | calidad + suite hermética | **`5567 passed, 62 skipped`**; `mypy` **573** |
| `lifecycle-pg` | Alembic + auth + bancos PG | **176** + **45** + **3** + **7** + **23** + … |
| `playwright (live AUTO daily chain)` / `mock E2E` / `integrated AUTO S5` / `integrated axe` | rutas y a11y | **2** / **139** / **8** / **32** passed |
| `replay-repro` | el artefacto congelado se regenera byte a byte | **`REPRODUCIDO`** (`E9B7376B…F5625`) ⇒ `Δ decisión = 0` |
| `a7-gate` / `decision-spine` / `security` / `dr-verify` | invariantes | **7** / **621** / gitleaks / dr |
| `certify (aggregate + artifact)` | agrega y certifica | `success` |
| `playwright (integrated E2E, opt-in)` | **no** es gate | `skipped` por diseño |

---

## 5. Qué **certifica** esta versión

Cierra los **cinco** criterios que el sello `.164` dejó como *criterio escrito sin prueba ejecutada*, de modo que la auditoría de detección pasa de **16/21** a **21/21** criterios con prueba ejecutada.

1. **S-4 — `THESIS_INVALIDATION` es alcanzable cuando el plan declara su nivel.** Con `invalidationPrice > stop` (mark `96`, nivel `96.5`, stop `95`) el motivo decisorio es `THESIS_INVALIDATION` y `reasons == ("THESIS_INVALIDATION",)` **sin** `STRUCTURAL_STOP`; el control con mark `94` sigue dando el stop, así que la precedencia **no** se rompe. La brecha que queda es de **producto**: ningún productor de entrada emite hoy ese nivel.
2. **S-5 — la posición que AUTO no gestiona deja de ser un `None` silencioso.** `POSITION_UNMANAGED` + `_v2_declare_unmanaged_position`: una fila por barra y símbolo con `held`, precio del tick, `reason: "no_position_state"`, `management: "none"` y `attention: "high"`. No abre ni vende; el tick siguiente lo vuelve a declarar.
3. **O-3 — ningún hueco se pinta como `0` ni como `"paper"`.** DÍA-D formatea con `formatDiaDValue()` y `closed === null` degrada a `insufficient`; `lastSignalPrice` ausente se rotula; el `venue` del monitor viaja `None` con `venueMeasurement = "UNKNOWN"` cuando el snapshot no lo declara (el DTO pierde el default).
4. **O-4 — el veredicto de la ventana es DATO, no texto.** `window-verdict.ts` agrega sólo lo declarado por el gate por valor: un veredicto ⇒ ese; varios ⇒ «SIN VEREDICTO ÚNICO» con recuento; ninguno medido ⇒ **NO MEDIDO**. La UI deja de escribir `INCONCLUSIVE`.
5. **T-3 — la cadencia queda fijada por prueba.** N ticks de 60 s sobre la barra cerrada ⇒ **una** decisión fresca (`bar_tick`) y un **único** `logical_order_id` en los trozos de fill, sin segunda ejecución.
6. **El E2E deja de afirmar la constante que `O-4` retira.** `gp-e2e-v290` compara contra el veredicto del gate en el DTO (`data-verdict="MIXED"` con el mock) y exige que la vista **no** emita `CONFIRMED` ni `INCONCLUSIVE`; la prueba que afirmaba `INCONCLUSIVE` se retiró porque era la que hacía verde una mentira.

**Trazabilidad:** implementados los **21** criterios (`B-1`…`B-6`, `O-1`…`O-6`, `S-1`…`S-6`, `T-1`…`T-3`). **Ningún hallazgo llega a E3.**

---

## 6. Límites / huecos **declarados** (lo que NO certifica)

1. **AUTO sigue OFF**; la operativa es **100 % PAPER virtual**, sin LIVE ni XTB real.
2. **La ventana PAPER sigue `INCONCLUSIVE`** (`episodios 0/2`, `ciclos 0/32`). La UI ahora **lee** ese veredicto —o declara `NO MEDIDO`— pero este sello **no lo mueve**, y un CI verde **no** la certifica.
3. **Evidencia E1** (hermética), con **E2** parcial donde ya lo era (`S-6`, `T-1`, `T-3`); **ningún** hallazgo llega a **E3**. No hay operación real medida.
4. **`S-4` no crea el productor.** La rama es alcanzable por contrato; que ningún plan de entrada declare un nivel distinto del stop es deuda de **producto**.
5. **`T-3` fija el contrato, no la cadencia en producción**: procesos vivos, latencia del primer tick y cobertura de la cola son observación operativa.
6. **No demuestra rentabilidad.** Los cambios declaran consecuencias y leen datos; no validan señales ni P&L.
7. **Contrato HTTP**: el único cambio es `AutoMonitorHeaderDto.venue` → `string | null` (sin default) + `venueMeasurement` (default `UNKNOWN`). `openapi.json`/`schema.d.ts` regenerados; el resto de esquemas no cambia.

---

## 7. Falsabilidad — cómo un auditor **rompe** cada afirmación

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | El tag apunta a `00f321bb` y desciende de `v2.88.164-beta` (`13362515`). | `git cat-file -p v2.88.165-beta` o `git rev-parse` da otro commit o linaje. |
| 2 | `2.11.165-beta` es la versión del árbol y los **13** `meta.bump` coinciden. | `package.json` muestra otra versión o `test_dia_d_bump_guard` falla. |
| 3 | Sin migración: head `058_estudio_daily_proposals`. | `alembic heads` da otro head. |
| 4 | El `contract:check` está verde y el cambio es aditivo. | `pnpm contract:check` falla, o el diff de `schema.d.ts` no se limita a `venue`/`venueMeasurement`. |
| 5 | El freeze del tag es OK. | `node scripts/window-pin.mjs --check` da `TREE_MOVED`. |
| 6 | La tesis dispara antes que el stop cuando el plan declara el nivel. | `test_thesis_exit_reachable_with_declared_invalidation_price` falla si `primary_reason` deja de ser `THESIS_INVALIDATION`, si `STRUCTURAL_STOP` viaja como motivo, o si el control (mark `94`) deja de dar el stop. |
| 7 | La posición no gestionada se declara una vez por barra. | `test_unadopted_position_is_declared_in_journal` falla si no hay fila `position_unmanaged`, si falta el símbolo/`held`, o si el tick siguiente repite el hecho. |
| 8 | Un dato ausente no se pinta como `0`/`"paper"`. | las pruebas de `dia-d-auto-panel`, `signal-alerts-section` y `auto-monitor-header` fallan si reaparece `0`, `0.00` o `paper`. |
| 9 | El veredicto de la ventana es dato. | `test_window_verdict_is_read_from_gate` cambia el veredicto del mock (`INCONCLUSIVE` → `READY`) y falla si la pintura no cambia; `window-verdict.test.ts` falla si `UNKNOWN` se rellena con un veredicto. |
| 10 | La cadencia está fijada. | `test_auto_loop_decides_once_per_closed_bar_and_settles_intrabar` falla si hay más de una decisión fresca por barra o si los trozos de fill no comparten `logical_order_id`. |
| 11 | El CI del tag es verde. | El run citado tiene algún job obligatorio en `failure` o `certify` rojo. El intento rojo de §4 queda documentado, no borrado. |
| 12 | El E2E mide el veredicto real. | `gp-e2e-v290` pasa si se le devuelve a la vista el literal `INCONCLUSIVE`: la prueba deja de comprobar `data-verdict`. |

---

## 8. Reproducir la verificación (local, opcional)

```bash
# Bump y contrato
uv run pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
pnpm contract:check

# Los cinco criterios
uv run pytest packages/py/analytics/tests/test_exit_plan.py \
  apps/api-python/tests/test_auto_v2_audit_regressions.py \
  apps/api-python/tests/test_auto_v2_bar_short_circuit.py -q
pnpm --filter @bolsa/web exec vitest run window-verdict estudio-daily-ops-panel \
  auto-monitor-header signal-alerts-section dia-d-auto-panel

# Suites completas
uv run pytest packages/py/domain/tests packages/py/market/tests \
  packages/py/application/tests packages/py/analytics/tests apps/api-python/tests -q
pnpm --filter @bolsa/web test
pnpm --filter @bolsa/shared test

# Gates de ventana
pnpm window:test
node scripts/window-pin.mjs --check

# E2E de la operativa diaria por valor (mock)
cd apps/web && E2E_RUN=1 pnpm e2e -- v290
```

**Resultados de referencia medidos en este árbol:** `pytest` completo **5930 passed** (11:04) · suites tocadas **65 passed** · `web` **2383 passed / 319 ficheros** · `shared` **855 passed / 99 ficheros** (+1 todo) · `typecheck` **OK** · `lint` **0 errores** (23 avisos preexistentes) · `ruff` limpio · `mypy` **573 ficheros** · `window:test` **50 passed** · guardián de bump **2 passed** · `e2e` v290 **5 passed**.
