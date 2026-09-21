# Traspaso — post `v2.47-beta` (AUTO-6.x hardening + V2.47 trazabilidad + AUTO-7 slice 1) — 2026-09-21

**Para el siguiente chat/agente.** Lee esto **antes** de tocar nada. Si hay contradicción con el plan de la
fase ([`plan-v2-47-auto-6-hardening-y-trazabilidad-2026-09-21.md`](./plan-v2-47-auto-6-hardening-y-trazabilidad-2026-09-21.md)),
manda el [audit-pack](./audit-pack-v2.47-auto-6-hardening-y-trazabilidad-2026-09-21.md).

---

## 1. Estado en una frase

**`1.72.0-beta` (`v2.47-beta`) queda sellado con un solo tag para dos trabajos que el plan repartía en dos
releases**: el **hardening de AUTO-6** (parada dura durable, exactly-once bajo muerte en cualquier costura,
multi-proceso real, economía **direccional** en vez de largo-only) y la **trazabilidad de `V2.47`**
(`cycle_id` determinista con columna indexada —migración **`044_auto_cycle_trace`**— e identidad formal de
señales) más el **slice 1 de `AUTO-7`** (auto-evaluación **pura y read-only**) y la **primera superficie UI**
del valor esperado y del móvil. La desviación (un sello en vez de dos) está **declarada** en el §7.1 del plan:
la migración `044` hace imposible un sello `V2.46.x` "sin migración" una vez que ambos trabajos conviven.

- **Tag anterior:** `v2.46-beta` (fase `a14b71d7`, tag → `5eb654b9`).
- **Migración:** `043_exit_identity_and_kill_state` → **`044_auto_cycle_trace`** (solo `ADD COLUMN`
  nullable + índice; **sin backfill**).
- **Freeze que sigue vigente:** `v2_43_governor_evidence.py` **byte a byte** igual, tabla del gobernador y
  umbrales **intactos**, `AUTO_ENGINE_SIM_V2_GOVERNOR=0` byte-idéntico a `v2.43.1`, y **sin SHORT**.

---

## 2. Qué cierra esta fase y con qué se mide

| Cierre                                            | La medida que lo sostiene                                                                                  |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| **La economía dejó de ser largo-only**            | `test_expected_value.py` (7 nuevos) + M8/M9/M10/**M18** (18/18 muerden)                                    |
| **`SELL` no entra por la puerta de atrás**        | `entry_direction()` devuelve `None` ⇒ `EV_DIRECTION_UNSUPPORTED`; M9 lo mide                               |
| **La parada dura sobrevive a un reinicio** (P0)   | `test_auto_v46_hardkill_recovery.py` (5) + `…_pg.py` (2) + **M17**                                         |
| **La liberación tiene emisor real**               | `POST /api/v1/risk/kill-switch/durable-release`, `reconciliationId` obligatorio, `not_engaged` idempotente |
| **Exactly-once bajo muerte en cualquier costura** | `test_auto_v46_crash_injection_matrix.py` (6) + `…_pg.py` (2), invariante tras reinicio                    |
| **Concurrencia entre PROCESOS**                   | `test_auto_v46_multiprocess_pg.py` (N workers reales; invariante **en BD**)                                |
| **El ciclo financiero tiene identidad**           | `test_auto_v47_cycle_trace.py` (11) + migración `044` + **M11/M12**                                        |
| **La colisión de señales ya no es silenciosa**    | `test_auto_v47_signal_identity.py` (9) + **M16**                                                           |
| **Existe auto-evaluación por estrategia**         | `test_auto_self_evaluation.py` (16) + feed (13) + API (2) + **M13/M14/M15**                                |
| **El valor esperado se ve (y solo si se midió)**  | `test_auto_v47_expected_value_journal.py` (5) + shared/web + `contract:check` OK                           |
| **Primer slice móvil**                            | 6 componentes + 7 ficheros de test nuevos de UI (`data-cabin-width` medible)                               |

**Verificación agregada del árbol final** (comandos exactos en el §11 del pack):

- `ruff` limpio · `mypy` **491** ficheros 0 issues · `lint-imports` **4 kept / 0 broken** ·
  gobernador **exit 0** con `git diff` **vacío**.
- Bloques offline con los targets **extraídos del YAML**: `quality` **2178** y tag **2189**
  (base `2091`/`2102` ⇒ **+87 en AMBOS**, 0 skipped).
- Suites PG nuevas con sus gates: **5 passed, 0 skipped**.
- Frontend: `shared` **786 passed + 1 todo**; `web` typecheck OK, lint **0 errores** (23 warnings legacy),
  **1290 passed**, build OK; `contract:check` **OK**.
- **Mutaciones: 18/18 muerden**, restauración byte a byte y huella `git status` **intacta**.

---

## 3. Lo que queda ABIERTO (con dueño declarado, no con un cero)

1. **El broker SIM sigue liquidando todas las tranchas en el mismo tick.** La ventana de muerte _mid-fill_ se
   cubre **por inyección** (§3 del pack), no moviendo el broker. Moverlo es **decisión de producto**.
2. **`BROKER_DESYNC` sigue sin productor.** Existe en el vocabulario de motivos y **ningún** camino de
   producción lo emite. No se fabricó un engagement para "cubrirlo".
3. **`allow_distinct_strategies` está en OFF** (`AUTO_ENGINE_SIM_V2_ALLOW_DISTINCT_STRATEGIES` sin definir). La
   política está implementada y probada, pero encenderla cambia la forma de competir dos estrategias sobre el
   mismo instrumento: **decisión del owner**.
4. **`cycle_id` sin backfill.** Una posición anterior a `2.47` traza con `NULL`: es **información**, no fallo.
5. **`AUTO-7` sin UI y sin calibrar nada** (read-only por diseño). Sus métricas **no** alimentan pesos,
   umbrales ni sizing: si alguien las conecta, es una fase nueva con su propio pack.
6. **La UI móvil es un slice**: 6 componentes. El resto de la superficie sigue sin adaptar.
7. **23 warnings de lint** en `web` (deuda legacy, no introducida aquí).
8. **`test_decision_journal_studies.py` era invisible para CI** (10 tests). Ya está registrado; conviene
   **auditar la lista** de `packages/py/application/tests` en los dos jobs para ver si hay más ficheros que
   nunca corrieron (el delta simétrico `+87/+87` es la herramienta).

---

## 4. Trampas MEDIDAS que te van a morder (léelas dos veces)

1. **La lista de tests de `packages/py/application/tests` es explícita, fichero a fichero**, en `quality`
   (`.github/workflows/python-ci.yml`) y en el job `python` del tag. **Un fichero nuevo ahí no corre si no lo
   registras** — y no falla: simplemente no existe. **Comprobación obligatoria: que el delta de los dos
   bloques sea EXACTAMENTE el mismo.** En esta fase se vio claro: `quality` +77 con el tag en +39 (38 tests
   volando) y, después, **+87/+87**.
2. **Nada de comentarios dentro de un `run: >`.** Es el hazard reincidente de `v2.40.2` y volvió a pasar en
   esta fase al registrar los ficheros nuevos: los `#` se convierten en "rutas inexistentes" para el runner
   offline (que lo detectó de inmediato). Los comentarios van **fuera** del bloque.
3. **La sonda de mutaciones y el bytecode `.pyc`.** Un `.pyc` se da por vigente con el mtime del fuente
   **truncado a segundos** y el **tamaño**: las mutaciones de esta matriz son del **mismo tamaño**
   (`e - t` ↔ `t - e`, `if x:` ↔ `if False:`), así que mutar y restaurar dentro del mismo segundo podía
   medir **el mutante con el árbol restaurado**. La sonda ya borra el `.pyc` de cada módulo mutado y corre con
   `PYTHONDONTWRITEBYTECODE=1`. **No lo quites.**
4. **Un test autorreferencial no prueba nada.** El test de coste corto que ya existía recalculaba el neto con
   el propio `cost_currency`: mutar la dirección del coste **no lo mordía** (M18 nacía verde). Al escribir un
   test, pregúntate: _¿si invierto la línea que quiero proteger, este test se cae?_ Compruébalo **mutando**,
   no razonando.
5. **`@bolsa/shared` hay que construirlo antes de `typecheck` de `web`.** Si no, `web` falla por tipos que sí
   existen en el fuente.
6. **El contrato API se verifica con `pnpm --filter @bolsa/web contract:check`.** Si tocas `accounts.py` o
   cualquier schema, regenera `openapi.json` y `schema.d.ts` (`dump_openapi.py` + `contract:gen`) o el job
   cae.
7. **Los pasos PG llevan guard anti-skip.** Que un test PG no falle **no** certifica: debe **no skipear**
   (`-rs` + grep de `skipped`). Los gates son `AUTO_*_PG_REQUIRED=1`.
8. **La medida se hace por JUnit XML** con `scripts/verify/offline_ci_run_yaml.py`, que **extrae los targets
   del YAML**: no inventes la lista de tests a mano para "verificar CI"; corre el runner que usa la de verdad.

---

## 5. Freeze (congelado)

- `AUTO_ENGINE_SIM_V2=0` ⇒ comportamiento `v2.39.x`.
- `AUTO_ENGINE_SIM_V2_GOVERNOR=0` ⇒ byte-idéntico a `v2.43.1` **sin parada dura**.
- `apps/api-python/scripts/v2_43_governor_evidence.py` **byte a byte** igual (su `"bump"` sigue en
  `1.68.0-beta`).
- Tabla del gobernador y umbrales: **no se tocan**.
- **Sin SHORT**: `entry_direction` devuelve `None` para `SELL`.
- **Sin backfill** de `cycle_id`.
- La migración `044` es **aditiva y nullable**: no reescribe ninguna fila.

---

## 6. Checklist de arranque del siguiente chat

```bash
git log --oneline -3 && git status --porcelain          # árbol limpio, tag v2.47-beta presente
uv run python apps/api-python/scripts/v2_43_governor_evidence.py; echo "exit=$?"   # 0 y sin diff
uv run alembic -c packages/py/infrastructure/alembic.ini heads                     # 044_auto_cycle_trace
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py            # 18/18, exit 0
gh run list --workflow "Release tag CI" --limit 3                                  # CI real del tag
```

Después: lee el §3 de este traspaso (**lo abierto**) y el §7 del plan (**desviaciones declaradas**) **antes**
de proponer nada.

---

## 7. Siguiente fase (según el roadmap)

- **`AUTO-8` — Adaptive AUTO** (`V2.48+` / `1.73.0-beta`): lo que sigue en el roadmap.
- **UI de `AUTO-7`** (fase propia, con datos ya disponibles en el endpoint y **sin** tocar pesos).
- **Deudas vivas** que pueden reclamar su sitio: el broker SIM por tick, un productor declarado para
  `BROKER_DESYNC`, encender `allow_distinct_strategies` (decisión del owner), completar el móvil y auditar la
  lista de tests de `application` (punto 8 del §3).
