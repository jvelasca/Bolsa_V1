# Auditoría de aislamiento de ejecución XTB (código) — 2026-10-14

> **Tipo:** auditoría **estática** de aislamiento (SIM/AUTO vs dinero real de XTB) sobre el **árbol actual**.
> **Objeto:** las barreras que impiden que una ruta **AUTO/SIM** alcance dinero real con los *defaults*, y sus residuos.
> **Veredicto:** **AISLADO EN CÓDIGO, sin hallazgos `P1`.** Los residuos quedan **declarados**: `G1` (`P2`) **CERRADO** el **2026-10-14** (ver §4); `G2`/`G3`/`G5` (`P3`) **CERRADOS** el **2026-10-14** (ver §5 y §6), con el **residual de `G3`** declarado; `G4` y `G6` (`P3`) quedan **CONFIRMADOS/declarados** (verificados hoy, **readonly**, **no** cerrados: ver §7).
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

## 3. Huecos declarados — estado a 2026-10-14

> **Actualización 2026-10-14:** `G1` (`P2`) **CERRADO** en `v2.88.127` (ver §4); `G2`, `G3` y `G5` (`P3`) **CERRADOS** en `v2.88.128` (ver §5 y §6), con el **residual de `G3`** declarado; `G4` y `G6` (`P3`) quedan **CONFIRMADOS/declarados** (verificados hoy por lectura, **readonly**, **no** cerrados: ver §7). No queda ningún hueco `P2` abierto; ningún `P1`.

| Id | Sev. | Hueco | Estado (2026-10-14) | Detalle |
|----|------|-------|---------------------|---------|
| **G1** | `P2` | Los dos tests de aislamiento del broker no corrían en el job **por commit**. | **CERRADO** (`v2.88.127`) | §4 |
| **G2** | `P3` | El alcance del invariante AST estaba **acotado** a `bolsa_application` + `apps/*/src`; otros paquetes no se censaban. | **CERRADO** (`v2.88.128`) | §5 |
| **G3** | `P3` | El invariante **no veía dispatch dinámico** (`getattr`/`importlib`): una referencia construida por nombre en runtime no la detectaba el AST. | **CERRADO con residual** (`v2.88.128`) | §5 |
| **G4** | `P3` | El **recovery worker nace ON** (`_worker_enabled` default `"1"`) pero es **read-only**; el **apply financiero** va OFF por defecto (`LIVE_ORDER_RECOVERY_FINANCIAL_APPLY_ENABLED` fail-closed). | **CONFIRMADO/declarado** (readonly, **no** cerrado) | §7 |
| **G5** | `P3` | La **auth** de las rutas de control de riesgo (`broker-venue`/`kill-switch`) no se había verificado. | **CERRADO** (`v2.88.128`) | §6 |
| **G6** | `P3` | Sin fugas de credenciales en el repo; el **bridge XTB** es frontera de confianza **FUERA** del repo. | **CONFIRMADO/declarado** (readonly, **no** cerrado) | §7 |

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

**Estado.** Con `NO ejecutado = 0`, `SIN DECLARAR = 0` y `entradas obsoletas = 0`, **`G1` queda cerrado**; la guarda de censo sigue verde **sin** regenerar la línea base (`--write-baseline` **no** fue necesario). `G2`, `G3` y `G5` (`P3`) se **cierran** en `v2.88.128` (ver §5 y §6), con el **residual de `G3`** declarado; `G4`/`G6` quedan **confirmados/declarados** (readonly; ver §7).

---

## 5. G2 y G3 CERRADOS — el invariante AST cubre TODO el monorepo y detecta dispatch dinámico (2026-10-14)

**Fecha de cierre:** 2026-10-14 (sello `v2.88.128-beta`). **Sev.:** `P3`.

**Qué eran.** `G2`: el alcance del invariante AST estaba **acotado** a `bolsa_application/**` + `apps/*/src`, de modo que un módulo de otro paquete (`analytics`, `infrastructure`, `market`, `domain`, `ai`) podía **cablear** la vía real sin que el censo lo viera. `G3`: el detector era puramente **nominal** — una referencia construida por **nombre** en runtime (`getattr(obj, "resolve_broker_adapter")`, `importlib.import_module(...)`) no aparecía en el AST como símbolo de dinero, y quedaba como punto ciego.

**Cableado exacto** ([`test_a8_m0_auto_live_invariant.py`](../../packages/py/application/tests/test_a8_m0_auto_live_invariant.py)):

- **`G2` — barrido ampliado a todos los paquetes** (nuevo `test_no_other_package_references_live_money_path`, `:289-313`): se censa el `src` de `analytics`, `infrastructure`, `market`, `domain` y `ai` (raíces en `_OTHER_PACKAGE_ROOTS`, `:64-70`); para esos paquetes la **allowlist invertida es VACÍA** (la vía real solo puede vivir en `bolsa_application`). `assert root.is_dir()` por paquete y `assert discovered` evitan que el barrido se quede **vacío en silencio**.
- **`G3` — detector de dispatch dinámico** (`_dynamic_dispatch_symbols`, `:134-174`; nombres prohibidos en `_FORBIDDEN_DYNAMIC_NAMES`, `:59-61`): marca `getattr(obj, "<nombre prohibido>")`, `importlib.import_module(...)`, `__import__(...)`, `eval(...)`/`exec(...)` y **literales string IGUALES** a un nombre prohibido (`resolve_broker_adapter`, `XtbBrokerAdapter`, `IBrokerAdapter`, `broker_adapter`, `bolsa_application.broker_adapter`). `_reference_money` (`:204-211`) **une** el censo nominal con el dinámico ⇒ **todo** barrido (apps, otros paquetes y spine AUTO) aplica las dos señales.

**Evidencia (censo y guardas).**

```
$ uv run --no-sync python -m pytest packages/py/application/tests/test_a8_m0_auto_live_invariant.py apps/api-python/tests/test_risk_control_auth.py -q
49 passed        # 41 AST + 8 auth

$ uv run --no-sync python scripts/ci/test_selection.py --report
# universo            : 621
# ejecutado por el CI : 621
# NO ejecutado        : 0
#   declarado         : 0
#   SIN DECLARAR      : 0
# entradas obsoletas  : 0

$ uv run --no-sync python -m pytest apps/api-python/tests/test_ci_test_selection_census.py apps/api-python/tests/test_dia_d_bump_guard.py -q
6 passed

$ uv run --no-sync ruff check packages/py/application/tests/test_a8_m0_auto_live_invariant.py
All checks passed!
```

**El invariante ampliado NO halló referencias reales fuera de la allowlist.** El único tropiezo del barrido fue [`bolsa_analytics/cognitive/broker_adapter.py`](../../packages/py/analytics/src/bolsa_analytics/cognitive/broker_adapter.py): **menciona** `XtbBrokerAdapter` **solo en su docstring** (`:1-6`), no lo referencia (ni import, ni `.submit`, ni dispatch dinámico). Es un **recibo** de dominio (`BrokerAdapterReceipt`, ADR-034), no la vía real.

**`G3` residual (declarado).** El detector cierra las formas **literales**, pero los nombres **NO literales** siguen fuera del alcance del AST: `getattr(mod, var)` (nombre en variable), `importlib.import_module(build)` (nombre construido) y strings concatenados (`"resolve_" + "broker_adapter"`). No hay evidencia de su uso para alcanzar la vía real; se declara como **límite del invariante**, no como ausencia de barrera.

**Estado.** `G2` y `G3` quedan **CERRADOS** (con el **residual de `G3`** declarado).

---

## 6. G5 CERRADO — la auth de las rutas de control de riesgo se fija por test (2026-10-14)

**Fecha de cierre:** 2026-10-14 (sello `v2.88.128-beta`). **Sev.:** `P3`.

**Qué era.** `POST /api/risk/broker-venue` y `/api/risk/kill-switch` **no abren dinero por sí solos** (configuran venue/veto), pero la **auth** de estas rutas **no se había verificado** en la firma de la auditoría: no se sabía si exigían credencial.

**Cableado exacto.** El router vive en [`risk.py:49`](../../apps/api-python/src/bolsa_api/api/v1/routes/risk.py) (`APIRouter(prefix="/risk", tags=["risk"])`), con `POST /kill-switch` (`:119`), `POST /kill-switch/durable-release` (`:135`) y `POST /broker-venue` (`:207`). **Ninguna** de las tres vive en `PUBLIC_PREFIXES`, así que, con auth ON, el middleware corta **antes** de la ruta. Nuevo [`test_risk_control_auth.py`](../../apps/api-python/tests/test_risk_control_auth.py) (4 tests / **8 casos**) fija la propiedad de forma **falsable**:

- `test_risk_control_paths_are_not_public`: ninguna ruta bajo `/api/risk` está en `PUBLIC_PREFIXES` (guarda barata y explícita).
- `test_post_control_requires_jwt_when_auth_enabled` (3 rutas): con `APP_PASSWORD` puesto, **sin** token ⇒ **401** (el middleware corta antes del handler).
- `test_post_control_accepts_valid_jwt` (2 rutas): con JWT válido (Bearer) ⇒ **200** (el middleware deja pasar).
- `test_post_control_open_when_app_password_empty` (2 rutas): en dev **sin** `APP_PASSWORD` la auth está **OFF por diseño** (no es un agujero: `Settings` exige `APP_PASSWORD` en entorno productivo, **fail-closed**, [`config.py:243-256`](../../packages/py/infrastructure/src/bolsa_infrastructure/config.py)).

El test es **hermético/offline** a propósito: `REDIS_URL=""` deja el runtime best-effort de kill-switch/broker-venue en **no-op**, y la única lectura de BD del middleware (`SqlAlchemyUserRepository.get_by_id`) se sustituye por un doble. **No** se cambia el middleware ni se añade auth: solo se verifica y se fija.

**Evidencia.** Los **8** casos de auth pasan junto con los **41** del invariante AST (`49 passed`, ver §5) y el fichero entra en el censo (**621/621**, `0` sin declarar).

**Estado.** `G5` queda **CERRADO**: con `APP_PASSWORD` puesto, las tres rutas de control de riesgo exigen JWT (**401** sin credencial) porque **ninguna** vive en `PUBLIC_PREFIXES`.

---

## 7. G4 y G6 CONFIRMADOS/declarados (verificados hoy, readonly; NO cerrados) — 2026-10-14

> **Nota:** estos dos residuos se **confirman** hoy por **lectura de código** (readonly). **No** se cierran: `G4` describe una capacidad **deliberadamente** ON (contenida por diseño) y `G6` es una **frontera de confianza externa** al repo, no algo que un test del repo pueda cerrar.

- **`G4` — el recovery worker nace ON pero es read-only.** [`live_order_recovery_worker.py`](../../apps/api-python/src/bolsa_api/background/live_order_recovery_worker.py): `_worker_enabled()` nace **ON** (`LIVE_RECOVERY_WORKER_ENABLED` default `"1"`, `:74-76`), pero el worker es **read-only** por diseño (docstring `:17-19`: resolver **nunca** re-POSTea; `UNKNOWN` solo sale vía `query_broker` o queda `UNKNOWN`) y el **apply financiero** va **fail-closed OFF** por defecto (`LIVE_ORDER_RECOVERY_FINANCIAL_APPLY_ENABLED`, `financial_apply_enabled()`, `:86-93`; solo `1|true|yes|on` lo enciende). Confirmado por lectura; **no** es un hueco de dinero.
- **`G6` — sin fugas de credenciales en el repo; el bridge XTB es frontera externa.** Confirmado por lectura: [`.gitignore`](../../.gitignore) excluye `.env`; [`logging_redact.py`](../../apps/api-python/src/bolsa_api/logging_redact.py) redacta `authorization`/`api-key`/`password` y las credenciales concretas de la app (`app_password`/`app_auth_secret`/`db_password`/`xtb_user|pass|token`); [`config.py:292-321`](../../packages/py/infrastructure/src/bolsa_infrastructure/config.py) redacta `repr(Settings)` y el DSN; y el **bridge XTB** es frontera de confianza **FUERA** del repo (§1, fuera de alcance).

**Estado.** `G4` y `G6` permanecen **CONFIRMADOS/declarados** (readonly), **no** cerrados.

---

## 8. Residuales NO verificables (declarados)

- **Bridge externo XTB.** Su implementación vive **fuera** del repo (frontera de confianza); el repo solo garantiza las **condiciones de invocación** (B1–B7).
- **`XTB_BRIDGE_FILL_ORDERS` fuera del repo.** El contrato de esa orden se documenta, pero no se ejecuta/preuba aquí.
- **Dispatch dinámico NO literal.** El invariante ya cubre las formas **literales** (fijado en `G3`, §5); el **residual** —nombres construidos en variable o string concatenado (`getattr(mod, var)`, `importlib.import_module(build)`)— sigue fuera del alcance del AST y se declara como límite del invariante, no como ausencia de barrera.

---

## 9. Falsabilidad

- Si con los *defaults* (`broker_venue="paper"`, sin las dos env LIVE) alguna ruta AUTO/SIM produce un `submit` real, el veredicto `AISLADO` se **rompe**.
- Si `SimOnlyScope` se construye sin `require_sim_only_scope` (forja) y el punto de movimiento de dinero se levanta, B4 se **rompe**.
- Si el dry-run `live_auto` emite una orden real al broker, B5 se **rompe**.
- **Cierres (2026-10-14).** `G1` (`P2`, `v2.88.127`) y `G2`/`G3`/`G5` (`P3`, `v2.88.128`) están **CERRADOS**; `G4`/`G6` permanecen **CONFIRMADOS/declarados** (readonly), **no** cerrados. `G1`: los dos tests de broker ([`test_broker_adapter.py`](../../packages/py/application/tests/test_broker_adapter.py), [`test_broker_venue_per_account.py`](../../packages/py/application/tests/test_broker_venue_per_account.py)) entran en el job **por commit** de [`python-ci.yml`](../../.github/workflows/python-ci.yml) (verificados herméticos, sin PG); se **rompería** si volvieran a caer en `--ignore` por commit. `G2`: el invariante AST barre también `packages/py/{analytics,infrastructure,market,domain,ai}/src` (allowlist invertida vacía); se **rompería** si un módulo de otro paquete cableara la vía real sin que el test fallara. `G3`: detecta `getattr`/`importlib.import_module`/`__import__`/`eval`/`exec` y strings iguales a los nombres prohibidos; se **rompería** si una referencia nominal (import/attr/`.submit`) dejara de detectarse; su **residual** (nombres **NO literales**) sigue **declarado**, no cerrado. `G5`: las tres rutas de control de riesgo exigen JWT con auth ON (**401** sin credencial) y **ninguna** vive en `PUBLIC_PREFIXES`; se **rompería** si alguna entrara en `PUBLIC_PREFIXES` o si el test dejara de correr en CI.
