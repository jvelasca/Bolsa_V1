# Auditoría de aislamiento de ejecución XTB (código) — 2026-10-14

> **Tipo:** auditoría **estática** de aislamiento (SIM/AUTO vs dinero real de XTB) sobre el **árbol actual**.
> **Objeto:** las barreras que impiden que una ruta **AUTO/SIM** alcance dinero real con los *defaults*, y sus residuos.
> **Veredicto:** **AISLADO EN CÓDIGO, sin hallazgos `P1`.** Los residuos quedan **declarados**: `G1` (`P2`) **CERRADO** el **2026-10-14** (ver §4); `G2`…`G6` (`P3`) **abiertos**.
> **Fecha:** 2026-10-14.

---

## 1. Alcance y método

Se inspeccionan las **barreras de aislamiento** que separan la vía **AUTO/SIM** (sandbox sin HTTP, dry-run) de la vía **real** (bridge XTB). Se ancla cada barrera en su `file:line` y en el **test/invariante** que la fija. Se declaran, además, los huecos y lo que **no** es verificable dentro del repo.

**Fuera de alcance (declarado):** el **bridge XTB** es una **frontera de confianza externa** (proceso/fuera del repo); esta auditoría **no** verifica su implementación, solo las condiciones con las que el repo lo invoca.

---

## 2. Barreras (veredicto `AISLADO`)

| # | Barrera | `file:line` | Test / invariante que la fija |
|---|---------|-------------|-------------------------------|
| B1 | **Doble env fail-closed** `LIVE_EXECUTION_UNLOCKED` + `LIVE_EXECUTION_AUTHORIZED` (ambas por entorno humano; cualquier otro valor ⇒ off) | [`live_execution_runtime.py:25-51`](../../packages/py/application/src/bolsa_application/live_execution_runtime.py) | [`test_a8_m0_auto_live_invariant.py`](../../packages/py/application/tests/test_a8_m0_auto_live_invariant.py) |
| B2 | **Sandbox sin HTTP**: `XtbBrokerAdapter.submit` no abre la vía real sin B1; sin ella ⇒ `not_wired` (`live_virtual_sandbox`), sin orden | [`broker_adapter.py:212-265`](../../packages/py/application/src/bolsa_application/broker_adapter.py) | [`test_broker_adapter.py`](../../packages/py/application/tests/test_broker_adapter.py) · [`test_confirm_broker_adapter.py`](../../packages/py/application/tests/test_confirm_broker_adapter.py) |
| B3 | **`broker_venue` default `paper`** (live = bridge XTB, opt-in explícito) | [`config.py:170-171`](../../packages/py/infrastructure/src/bolsa_infrastructure/config.py) | [`test_broker_venue_per_account.py`](../../packages/py/application/tests/test_broker_venue_per_account.py) · [`test_config.py`](../../packages/py/infrastructure/tests/test_config.py) |
| B4 | **Permiso POSITIVO SIM-only sellado** (`SimOnlyScope` intransferible; `require_sim_only_scope` exige `source`; el punto de movimiento de dinero lo **exige** para construirse; solo cubre `{paper, simulated}`) | [`simulated_finance.py:152-210`](../../packages/py/application/src/bolsa_application/simulated_finance.py) | [`test_a8_m0_sim_only_permission.py`](../../packages/py/application/tests/test_a8_m0_sim_only_permission.py) · [`test_simulated_finance.py`](../../packages/py/application/tests/test_simulated_finance.py) |
| B5 | **Dry-run que nunca envía** (`live_auto`: `status="live_dry_run_pass"`, `broker="none"`, «sin orden real») | [`execution_router.py:1201`](../../packages/py/application/src/bolsa_application/execution_router.py), [`execution_router.py:1420-1421`](../../packages/py/application/src/bolsa_application/execution_router.py) | [`test_execution_router.py`](../../packages/py/application/tests/test_execution_router.py) |
| B6 | **Kill switch** global (env OR memoria OR Redis) que veta el submit | [`risk_runtime.py:98-109`](../../packages/py/application/src/bolsa_application/risk_runtime.py) | [`test_execution_router.py`](../../packages/py/application/tests/test_execution_router.py) · [`test_or5_broker_execution_scenarios.py`](../../packages/py/application/tests/test_or5_broker_execution_scenarios.py) |
| B7 | **Invariante AST** (censo AUTO por convención + spine por ROL, allowlist invertida sobre `bolsa_application/**` y barrido de `apps/*/src`) | [`test_a8_m0_auto_live_invariant.py`](../../packages/py/application/tests/test_a8_m0_auto_live_invariant.py) | El propio test |

**Conclusión:** ninguna ruta **AUTO/SIM** alcanza dinero real con los *defaults*: B1 y B2 exigen **ambas** env humanas; B3 mantiene el venue en `paper`; B4 sella la vía de movimiento de dinero al scope SIM; B5 deja el dry-run sin broker; B6 permite el veto global; B7 fija el censo estructural.

---

## 3. Huecos declarados (abiertos)

> **Actualización 2026-10-14:** `G1` (`P2`) queda **CERRADO** (ver §4). Los huecos `G2`…`G6` (`P3`) siguen **abiertos**.

| Id | Sev. | Hueco | Evidencia |
|----|------|-------|-----------|
| **G2** | `P3` | El alcance del invariante AST está **acotado** a `bolsa_application` + `apps/*/src`; otros paquetes no se censan. | `test_a8_m0_auto_live_invariant.py` |
| **G3** | `P3` | El invariante **no ve dispatch dinámico** (`getattr`/`importlib`): una referencia construida por nombre en runtime no la detecta el AST. | `test_a8_m0_auto_live_invariant.py` |
| **G4** | `P3` | El **recovery worker nace ON** (`_worker_enabled` default `"1"`) y es **read-only**; el **apply financiero** va OFF por defecto (`LIVE_ORDER_RECOVERY_FINANCIAL_APPLY_ENABLED` fail-closed). | [`live_order_recovery_worker.py:74-76`](../../apps/api-python/src/bolsa_api/background/live_order_recovery_worker.py) |
| **G5** | `P3` | `POST /api/risk/broker-venue` y `/kill-switch` **no abren dinero por sí solos** (configuran venue/veto); la **auth** no se verificó en esta firma. | rutas de `risk` (`apps/api-python/src/bolsa_api/api/v1/routes/`) |
| **G6** | `P3` | Sin fugas de credenciales en el repo: el **bridge XTB** es frontera de confianza **FUERA** del repo. | — |

---

## 4. G1 CERRADO — los dos tests de broker corren en el job **por commit** (2026-10-14)

**Fecha de cierre:** 2026-10-14. **Sev.:** `P2` (era el único `P2`; **cerrado**).

**Qué era.** [`test_broker_adapter.py`](../../packages/py/application/tests/test_broker_adapter.py) y [`test_broker_venue_per_account.py`](../../packages/py/application/tests/test_broker_venue_per_account.py) **no** corrían en el job **por commit**: [`python-ci.yml`](../../.github/workflows/python-ci.yml) los dejaba en `--ignore` (L445-446) y el job offline de [`release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml) también (L834-835). Solo corrían en el **sello**, en el lote dedicado `W-G2/2` de **34** ficheros con PG real ([`release-tag-ci.yml:1060-1061`](../../.github/workflows/release-tag-ci.yml)).

**Verificación de hermeticidad (offline-safe).** Ambos ficheros se leyeron completos: usan dobles/fakes y `monkeypatch`; **no** tocan `get_settings`/`DATABASE_URL`/`create_engine`/`session`/`psycopg` ni repositorios que conecten. Se **ejecutaron con la BD inalcanzable** (imitando el job offline: `DATABASE_URL`/`DB_HOST`/`DB_PORT` a host/puerto inexistentes) y **pasaron**:

```
$ $env:DATABASE_URL="postgresql://nouser:nopass@127.0.0.1:1/nodb"
$ uv run --no-sync python -m pytest packages/py/application/tests/test_broker_adapter.py packages/py/application/tests/test_broker_venue_per_account.py -q
.............................                                            [100%]
29 passed in 1.47s
```

**Cableado exacto (CI).**

- [`python-ci.yml`](../../.github/workflows/python-ci.yml): se **quitan** las dos líneas `--ignore=packages/py/application/tests/test_broker_adapter.py` y `--ignore=packages/py/application/tests/test_broker_venue_per_account.py` del `run` del job **por commit** (eran L445-446). El pase de **directorio** `packages/py/application/tests` (L318) ya los recoge.
- [`release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml): se **quitan** las mismas dos líneas del `--ignore` del job **offline** del tag (eran L834-835) y se **quitan** los dos ficheros del lote explícito `W-G2/2` (eran L1060-1061). El nombre del paso y el comentario del lote bajan de **34** a **32** ficheros, dejando **declarado** el motivo del movimiento (herméticos ⇒ pase por commit de `python-ci.yml` en `v2.88.127`).

**Evidencia (censo y guardas, tras el cableado).**

```
$ uv run --no-sync python scripts/ci/test_selection.py --report
# universo            : 620
# ejecutado por el CI : 620
# NO ejecutado        : 0
#   declarado         : 0
#   SIN DECLARAR      : 0
# entradas obsoletas  : 0

$ uv run --no-sync python -m pytest apps/api-python/tests/test_ci_test_selection_census.py -q
5 passed

$ uv run --no-sync python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
1 passed

$ uv run --no-sync python -m pytest packages/py/application/tests/test_broker_adapter.py packages/py/application/tests/test_broker_venue_per_account.py -q   # entorno de aplicación (BD normal)
29 passed
```

**Estado.** Con `NO ejecutado = 0`, `SIN DECLARAR = 0` y `entradas obsoletas = 0`, **`G1` queda cerrado**; la guarda de censo sigue verde **sin** regenerar la línea base (`--write-baseline` **no** fue necesario). `G2`…`G6` (`P3`) siguen **abiertos**.

---

## 5. Residuales NO verificables (declarados)

- **Bridge externo XTB.** Su implementación vive **fuera** del repo (frontera de confianza); el repo solo garantiza las **condiciones de invocación** (B1–B7).
- **`XTB_BRIDGE_FILL_ORDERS` fuera del repo.** El contrato de esa orden se documenta, pero no se ejecuta/preuba aquí.
- **Dispatch dinámico** (`getattr`/`importlib`). Ningún análisis AST lo cubre (ver `G3`); se declara como límite del invariante, no como ausencia de barrera.

---

## 6. Falsabilidad

- Si con los *defaults* (`broker_venue="paper"`, sin las dos env LIVE) alguna ruta AUTO/SIM produce un `submit` real, el veredicto `AISLADO` se **rompe**.
- Si `SimOnlyScope` se construye sin `require_sim_only_scope` (forja) y el punto de movimiento de dinero se levanta, B4 se **rompe**.
- Si el dry-run `live_auto` emite una orden real al broker, B5 se **rompe**.
- **`G1`** (2026-10-14): **CERRADO** — los dos tests de broker ([`test_broker_adapter.py`](../../packages/py/application/tests/test_broker_adapter.py), [`test_broker_venue_per_account.py`](../../packages/py/application/tests/test_broker_venue_per_account.py)) ya entran en el job **por commit** de [`python-ci.yml`](../../.github/workflows/python-ci.yml), verificados herméticos (sin PG). Dejaría de estar cerrado si volvieran a caer en `--ignore` por commit o si dejasen de correr fuera del sello.
