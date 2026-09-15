# Arranque auditor externo — V2.39.2 (Cierre de flaky + tercera pasada) (2026-09-14)

Copia en chat nuevo (auditor):

---

Eres auditor externo de Bolsa V1 **candidato V2.39.2**. Auditas **desde GitHub**, sin acceso al
entorno local.

- **Delta:** `v2.39-beta` (`e94f2632`) → tag **`v2.39.2-beta`** (anotado) → peeled al
  commit de sellado de `main`; el **código** auditado es `9444b364` (certificado GREEN).
- **`main`:** incluye, por encima del código, el commit de documentación de auditoría; el
  tag re-sellado apunta a ese commit final (el auditor lo resuelve con
  `git rev-list -n 1 v2.39.2-beta`).
- **Package:** `1.64.2-beta` · **CHANGELOG:** `[1.64.2-beta]`.
- **Alembic head:** `039_research_trials_regime` — esta fase **no añade migración**.
- **Flags:** sin cambios. `AUTO_ORCHESTRATOR_ADAPTIVE_REGIME` sigue **OFF** por defecto.
- **Tamaño del delta:** **17 commits**, **52 ficheros**, `+3384 / −249`.

**Regla:** NINGÚN estado ambiguo → NO COMPRAR. No inventes PASS. Compara **línea por línea**
`v2.39-beta` → `v2.39.2-beta` y registra P0/P1/P2/P3 con evidencia `archivo:línea`.

**Punto de entrada único:** [`audit-pack-v2.39.2-cierre-flaky-2026-09-13.md`](./audit-pack-v2.39.2-cierre-flaky-2026-09-13.md)
(16 secciones: diagnóstico, causa raíz medida, fix, regresión y verificación por hallazgo).

---

## Resumen del delta (qué cambió y por qué)

La auditoría interna cerró **nueve** hallazgos en esta fase. Los cinco primeros son el cierre de
**flaky** que resultaron ser dos bugs reales de producción; los cuatro últimos salieron al correr
la **batería exacta del CI**.

| #   | Sev | Hallazgo                                                                                                                         | Naturaleza       |
| --- | --- | -------------------------------------------------------------------------------------------------------------------------------- | ---------------- |
| 1   | P1  | El `executed_at` del ledger se derivaba del **reloj de pared** (no ordena bajo concurrencia)                                     | Producción       |
| 2   | P1  | `ApplyCustodyFees` calculaba `balance_after` con el cash **PRE-lock**                                                            | Producción       |
| 3   | P1  | La gramática de Discovery emitía planes **inoperables** (Donchian inalcanzable + par trigger/exit roto + doble EMA incompatible) | Producción       |
| 4   | P1  | Una lista **con instrumentos** no se podía borrar (FK sin CASCADE → 500)                                                         | Producción       |
| 5   | P2  | `pool_size=64` agotaba `max_connections` del PG local                                                                            | Config de test   |
| 6   | P2  | `test_two_workers_claim_disjoint_unknown_batch` **refutaba** lo que decía certificar                                             | Test deshonesto  |
| 7   | P2  | `lifecycle_outbox` **envenenaba suites** entre sí (`claim_batch` global)                                                         | Hermeticidad     |
| 8   | P3  | El bucle antirrecompra del A9 agotaba el presupuesto **siempre** (~518 s)                                                        | Test ineficiente |
| 9   | P3  | El job de CI de A14 **toleraba skips silenciosos** (certificación fantasma)                                                      | Gate de CI       |

---

## Foco 1 — Orden real del ledger bajo concurrencia (P1 #1, #2)

**Lee (fuentes reales, no solo docs):**

- `packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/ledger_repository.py`
  (`next_executed_at`)
- `packages/py/application/src/bolsa_application/accounts/trade.py`
- `packages/py/application/src/bolsa_application/accounts/custody.py`
- `packages/py/application/src/bolsa_application/accounts/cash.py`
- `packages/py/infrastructure/tests/chaos/test_load_concurrency_flow.py`

**Foco:**

1. ¿`next_executed_at` se lee **con el lock de la cartera ya tomado**, de modo que la lectura del
   último instante y la escritura del asiento sean atómicas frente al resto de escritores?
2. ¿El instante se deriva del **estado persistido** (`max(now, último + 1 µs)`) y por tanto es
   estrictamente creciente **con el orden de aplicación**, o queda algún camino que use el reloj?
3. ¿Está conectado en **las cuatro** rutas de escritura (trade, custodia, depósito, retiro)?
4. ¿El `balance_after` de custodia sale del cash **POST-lock** en **ambas** ramas (PENDING y
   periodo actual)?
5. ¿El paso de 1 µs hace **irrelevante** el desempate por `id` (que es un UUID v4 aleatorio)?
6. **Verifica por mutación:** revertir el uso del secuenciador a
   `_parse_executed_at(result.transaction.executed_at)` ¿hace **fallar** el test nuevo?

**Deuda anotada (no fix):** los **chaos tests no entran en CI** (requieren PG; se validan
localmente). El fix del ledger está cubierto por un test que **la CI no ejecuta**, aunque **sí**
por la suite de aplicación y por la regresión pura del secuenciador. Verifica si esa deuda es
aceptable o debe cerrarse.

---

## Foco 2 — La gramática de Discovery no debe emitir planes sin evidencia (P1 #3)

**Lee:**

- `packages/py/application/src/bolsa_application/discovery_grammar.py`
  (`grammar_variants_for_plan`, `_AXIAL_TRIGGER_EXIT_PAIRS`, `_plan_is_coherent`,
  `_donchian_break`, `_donchian_upper`, `_mutually_unreachable_trigger_exit`,
  `_conjunctive_ema_starvation`)
- `packages/py/application/tests/test_discovery_grammar.py`
- `apps/api-python/tests/test_a14_grammar_discovery_pg.py`

**Foco:**

1. ¿El trigger y el trend filter Donchian usan la **banda media**? ¿Queda algún camino con
   `close > upper`, que es **matemáticamente imposible** (el canal incluye la barra actual)?
2. ¿El eje de permutación permuta el exit homónimo **junto con** su trigger
   (`_AXIAL_TRIGGER_EXIT_PAIRS`), de modo que un cruce alcista no quede emparejado con un cruce
   bajista de las **mismas** EMAs (inalcanzable)?
3. ¿Los dos vetos de inanición son **deterministas** y **fail-closed** (retiran el plan de la
   enumeración en vez de emitirlo sin evidencia posible)?
4. **Reproduce el conteo:** con el presupuesto por defecto, ¿obtienes **1684 planes y 0
   degenerados** en la serie de integración (≥2 columnas operables por plan)?
5. ¿El `PBO CSCV` de una candidata gramatical **ya no** devuelve `None` por falta de matriz, de
   modo que `robustness`/`walk_forward` dejan de quedar `NOT_EVALUATED` en silencio?
6. **Invariante de conteo:** el `1784` histórico **ya no aplica**. Lo exigible es que **ninguna
   candidata emitida quede sin evidencia posible** y que el **techo del `GrammarBudget`** siga
   vigente. ¿Estás de acuerdo con ese encuadre o ves riesgo de explosión?

---

## Foco 3 — Integridad referencial y hermeticidad de tests (P1 #4, P2 #6, #7)

**Lee:**

- `packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/list_repository.py`
  (`delete`) y `apps/api-python/tests/test_lists.py`
- `packages/py/application/src/bolsa_application/lifecycle_outbox.py` (`claim_batch`)
- `apps/api-python/tests/test_lifecycle_outbox_worker_pg.py` (`_purge_residual_outbox`)
- `apps/api-python/tests/test_financial_integrity_pg.py` (teardown en `finally`)
- `apps/api-python/tests/test_live_order_recovery_concurrency_pg.py`

**Foco:**

1. ¿El borrado de listas vacía los `instrument_list_items` **antes** que la lista, en la **misma
   transacción**? ¿Alguna otra ruta borra listas sin pasar por el repositorio?
2. ¿`test_delete_list_with_items_does_not_violate_fk` **falla** si se revierte el fix (es decir,
   el test realmente cubre la regresión)?
3. ¿`claim_batch` filtra por posición? Si **no**, ¿es correcto que la purga de
   `_purge_residual_outbox` sea **global** (`status IN ('pending','processing')`) y no toque
   `applied`/`dead`?
4. ¿La purga introduce **carreras** con otros tests de outbox en paralelo? ¿O el aislamiento por
   fichero basta?
5. ¿`test_two_workers_claim_disjoint_unknown_batch` certifica ahora la propiedad **real**
   (mientras el lease está vivo, otro worker no reclama la misma fila)?

---

## Foco 4 — CI como certificación real, no fantasma (P3 #9 + cobertura)

**Lee:** `.github/workflows/python-ci.yml` (jobs `quality`, `lifecycle-pg`, `paper-forward-pg`,
`grammar-discovery-pg`) y `.github/workflows/release-tag-ci.yml`.

**Foco:**

1. El job `grammar-discovery-pg` declara `A14_GRAMMAR_PG_REQUIRED=1` pero el test **no lo leía**.
   El step nuevo «Fail on skipped A14 PG» inspecciona el log y falla si hay `SKIPPED`. ¿Cubre
   **todos** los modos de skip, o queda algún camino (colección vacía, `pytest.exit`, error de
   import) que pase sin que el job se ponga rojo?
2. ¿Algún **otro** job con `*_PG_REQUIRED` tiene el mismo agujero (declara el gate pero el test
   no lo lee)?
3. ¿Los jobs PG obtienen `DATABASE_URL` del `env` del workflow y **no** dependen de un `.env`
   que no existe en CI?
4. **Reproduce la verificación local** (sección 14 del audit-pack): `ruff`, `mypy`, la batería
   exacta del job `quality`, y `apps/api-python/tests` + `packages/py/infrastructure/tests`
   **dos veces seguidas** (el fallo era no determinista por contaminación entre suites).

---

## No pedir

LIVE · bump · unificar ledger/mesa · re-diseñar ADR · cerrar los chaos en CI sin PG · features
fuera del alcance. La regla de fail-closed y los gates CPCV/PBO/DSR/WFE/OOS **no se relajan**.

---

## Respuesta esperada

**(Pendiente — no inventar PASS).** Informe con `[severidad]` y veredicto **por cada foco**, con
evidencia `archivo:línea` y el delta real `v2.39-beta` → `v2.39.2-beta`. Marca explícitamente lo
que **no** puedas verificar desde GitHub y requiera entorno local.

---
