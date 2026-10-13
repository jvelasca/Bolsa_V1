# Entrega a auditoría externa (MIA) — `v2.88.115-beta` · **Endurecimiento de la banda OOS** (`H2` identidad ambigua · `H3` sin reutilización de artefactos) · **atribución financiera honesta** (`P1`) · dominio puro de auditoría + orquestador **opt-in** · **`Δ motor ≠ 0`** · **`Δ decisión = 0`** · contrato **sin cambio** · **sin migración**

> **Fecha:** 2026-10-12 · **Producto:** `V2.88.115-beta` · **Package:** `2.11.115-beta` · **Alembic head:** `053_dia_d_cycle_verifications` (`uv run alembic heads` ⇒ sin `054`; **sin migración**).
> **Base:** `v2.88.114-beta` (tag anotado objeto `bcb19cd4` → commit `743bb8df`; `Release tag CI` [`38218516439`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38218516439) **VERDE**). HEAD del árbol al redactar el plan: `98a3ec9a`.
> **Unidad de esta auditoría:** cerrar, en **un solo sello**, los huecos de las dos auditorías previas sobre `v2.88.114-beta`: **`P1`** (AUDITORIA 2 — `estudio_audit` atribuía dinero de **otra** estrategia a un valor con identidad propia) y **`H2`**/**`H3`** (AUDITORIA 1 — el plegado de la banda elegía identidad «por orden de llegada» y podía reutilizar informes de sorteos previos).
> **Regla del hueco:** una afirmación que no se puede sostener se declara **abierta** con su remediación, **nunca** se silencia. Un dato ausente se rotula «Sin dato todavía»; **jamás** se rellena con `0` ni con verde. **Banda ≠ punto:** `pointCitable = False` mientras la banda cruce cero.
> **`Δ motor ≠ 0` correctivo/aditivo · `Δ decisión = 0`.** El diff toca `packages/py/**` y un CLI, pero **no** toca umbrales, reparto de capital, `TOP_N`, régimen, selección ni protección. `H2`/`P1` son **dominio puro**; `H3` vive en un **orquestador opt-in** (`--finance-band K`, **default `0` = OFF**) ⇒ el payload por defecto del CLI OOS queda **byte a byte** igual.
> **Contrato HTTP sin cambio:** el commit del sello no toca `openapi.json`, `schema.d.ts` ni `alembic/**` (verificado sobre `789677ca` con `git show --stat`).
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.115/README.md`](./evidence/v2.88.115/README.md) · **Plan:** [`plan-v2-88-115-endurecimiento-oos-finance-band-2026-10-12.md`](./plan-v2-88-115-endurecimiento-oos-finance-band-2026-10-12.md).
> **Cita POST-TAG:** tag anotado **`v2.88.115-beta`** (objeto `289653e7e76519872554737b485abe8b1ef1a8c1` → commit `789677caa75aa378ba15b7ca09ba6dfc1c2b0cb4`), publicado en `origin` (objeto + `^{}` resueltos). `Release tag CI` [`38276396567`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38276396567) **VERDE** (`10m43s`; **12 jobs `✓`** — `certify` incluido — + `playwright (integrated E2E, opt-in)` `skipped`, esperado). `replay-repro` **`✓`**: regenera el artefacto del sello desde el fixture **sin** mover el payload ⇒ el endurecimiento **opt-in** no tocó el sello congelado. `main` tras el sello: `Python CI` [`38276392511`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38276392511) · `Frontend CI` [`38276392469`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38276392469) · `Fase 2 scientific` [`38276392474`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38276392474) · `Optimize lab` [`38276392471`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38276392471) · `Gitleaks` [`38276392531`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38276392531) **VERDES**. Tag **unsigned** (declarado).

---

## 1. Qué se entrega (y qué NO)

**Se entrega**, en un único commit de sello (`789677ca`, 19 ficheros, +499/−35):

1. **`P1` Atribución financiera EXACTA.** `estudio_audit._pick_finance_group` deja de devolver el **único** grupo del símbolo cuando ese grupo declara **otra** `strategyPresetKey`. El fallback «grupo único» solo aplica si el valor **no** declara identidad, o si el único grupo tampoco la declara. Con identidad declarada y sin coincidencia ⇒ `None` + motivo explícito («los grupos del símbolo no declaran la identidad '…'»), mostrado como **«Sin dato todavía»** — **nunca** atribución cruzada marcada `measured`.
2. **`H2` Identidad AMBIGUA declarada.** `oos_finance_band._fold` acumula **todas** las claves `strategyPresetKey` distintas por cubo `(strategyVersion, symbol)`: una sola ⇒ identidad; **más de una** ⇒ `strategyPresetKey = None` + `strategyPresetKeyAmbiguous = True` + `strategyPresetKeys[]` con todas (ninguna «ganadora»); ninguna ⇒ hueco (`None`, no ambiguo). Determinista bajo permutación de sorteos. `SCHEMA_VERSION` `oos-finance-band-v1` → **`v2`**.
3. **`H3` Sin reutilización de artefactos.** `v2_87_replay_oos_durable_cycle._run_finance_band` (opt-in): **purga** restos previos al arrancar; por sorteo **borra y verifica la AUSENCIA** de sus salidas antes de lanzar; tras el subproceso exige reporte **FRESCO** (`mtime` posterior al lanzamiento) y **bien formado** (`groups[]` + `aggregate`), y valida los metadatos del payload (**cuenta**, **versión A**, **ventana**) antes de plegarlo.
4. **Pruebas puras** de las tres piezas (dominio + CLI), más el bump `2.11.115-beta` y la evidencia/plan/`PROJECT_STATE`.

**NO se entrega**, y se declara:

- **NO** se toca el **motor de decisión/ejecución**: umbrales, reparto, `TOP_N`, régimen, selección y protección intactos (`Δ decisión = 0`).
- **NO** hay migración: Alembic head sigue `053_dia_d_cycle_verifications`.
- **NO** cambia el **contrato HTTP** (ni `openapi.json` ni `schema.d.ts`).
- **NO** se resuelve **`H1`** (separación formal de la sensibilidad del simulador frente a la inferencia estadística en `pointCitable`) — **abierto**, sello propio.
- **NO** se regenera el artefacto de evidencia `finance-band-w32-k12.json`: sigue en esquema `v1`; regenerarlo en `v2` exige **PostgreSQL** con la entrada sembrada ⇒ **no reproducible sin PG**, y **no se finge**.

---

## 2. Cambios verificables (todo con gate)

| Pieza | Fichero(s) | Qué hace |
| --- | --- | --- |
| `P1` | `packages/py/application/src/bolsa_application/estudio_audit.py` | `_pick_finance_group` restringe el fallback «grupo único» a los casos **sin** identidad declarada; `build_estudio_audit_report` emite motivo específico cuando hay grupos del símbolo pero ninguno declara la clave del valor. |
| `H2` | `packages/py/application/src/bolsa_application/oos_finance_band.py` | `_PresetIdentity` + `_identity_from_keys`; `_fold` resuelve identidad/hueco/**ambigüedad**; `_render_cell` publica `strategyPresetKey`, `strategyPresetKeyAmbiguous`, `strategyPresetKeys`. `SCHEMA_VERSION` → `oos-finance-band-v2`. |
| `H3` | `apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py` | `_purge_draw_artifacts`, `_reset_draw_outputs`, `_read_fresh_draw_report`, `_validate_draw_payload` cableados en `_run_finance_band`. |
| Pruebas | `packages/py/application/tests/test_estudio_audit.py`, `.../test_oos_finance_band.py`, `apps/api-python/tests/test_replay_oos_cli_renderers.py` | `P1`: grupo único con otra clave **no** se atribuye; grupo sin clave **sí** se usa si el valor declara preset. `H2`: ambiguo/consistente/ausente/agregado + **invariancia por permutación**. `H3`: purga, reset+ausencia, **rechazo** de reporte reutilizado, **aceptación** de reporte nuevo, validación cuenta/versión/ventana. |
| Bump | `package.json` + `apps/api-python/scripts/v2_87`…`v2_97` | `2.11.115-beta` + `meta.bump` (guardián `test_dia_d_bump_guard.py`). |

---

## 3. Medición

- **Python (local):** `ruff check packages/py apps/api-python --config pyproject.toml` **All checks passed**; `mypy packages/py/application/src --follow-imports=silent` **263 source files, no issues**.
- **Batería de aplicación:** `pytest packages/py/application/tests -q` ⇒ **2691 passed** + **1 fallo AMBIENTAL declarado** (`ImportError: DLL load failed … _devicearray`; Windows Application Control bloqueó una DLL nativa de numpy/`numba` — **ajeno** al código tocado, no un fallo lógico).
- **Batería focalizada:** `pytest apps/api-python/tests/test_replay_oos_cli_renderers.py` ⇒ **15 passed**; `test_dia_d_bump_guard` + `test_ci_test_selection_census` + `test_oos_finance` + `test_oos_finance_band` + `test_estudio_audit` ⇒ **42 passed**; `test_auto_estudio_audit_route.py` ⇒ **6 passed**.
- **`Δ motor ≠ 0` sin mover el sello:** la autoridad es el job CI **`replay-repro`** del tag ⇒ **`✓`** (regenera el artefacto congelado desde el fixture **sin** moverlo). El endurecimiento vive en un flag **apagado por defecto** y escribe en fichero **aparte**.
- **No reproducible en CI:** la medición de la banda `K` con `K=12` que respalda `v2.88.114` exige PostgreSQL sembrado ⇒ **medición local**, no gate de CI; se declara como tal.

---

## 4. Hallazgos y estado tras esta entrega

| ID | Hallazgo | Estado |
| --- | --- | --- |
| `P1` (AUDITORIA 2) | atribución cruzada de dinero entre estrategias en `estudio_audit` | **✅ CERRADO** |
| `H2` (AUDITORIA 1) | identidad de estrategia «elegida por orden de llegada» en el plegado de la banda | **✅ CERRADO** |
| `H3` (AUDITORIA 1) | posible reutilización de informes de sorteos previos en `_run_finance_band` | **✅ CERRADO** |
| `H1` (AUDITORIA 1) | sensibilidad del simulador vs inferencia estadística (`pointCitable`) | **⏳ ABIERTO** (sello propio) |
| `R-ev` | regenerar `finance-band-w32-k12.json` con esquema `v2` | **✅ CERRADO** en `v2.88.119-beta` (`oos-finance-band-v4`; era `⏳ PENDIENTE` aquí; reproducible con PostgreSQL sembrado) |

- **Fallos ambientales declarados, no disimulados:** el `ImportError` de DLL de `numpy`/`numba` es de entorno (política de Control de Aplicaciones de Windows), no del diff.
- **Avisos de CI:** solo preexistentes y ajenos al diff (`react-hooks/exhaustive-deps` en el front de backtests, deprecación de Node 20 en `actions/*`, aviso de migración `ubuntu-latest`→26). **Ninguno** sobre `estudio_audit`/`oos_finance_band`/`v2_87`.

---

## 5. Gates

| Gate | Resultado (local) |
| --- | --- |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed** |
| `uv run mypy packages/py/application/src --follow-imports=silent` | **263 source files, no issues** |
| `uv run pytest packages/py/application/tests -q` | **2691 passed** (+ 1 fallo **ambiental** declarado) |
| `uv run pytest apps/api-python/tests/test_replay_oos_cli_renderers.py -q` | **15 passed** |
| `uv run pytest test_dia_d_bump_guard + guardas + oos_finance(_band) + estudio_audit -q` | **42 passed** |
| `uv run pytest apps/api-python/tests/test_auto_estudio_audit_route.py -q` | **6 passed** |
| `uv run alembic heads` (`packages/py/infrastructure`) | `053_dia_d_cycle_verifications (head)` — **sin migración** |
| `git show --stat 789677ca` | **sin** `openapi.json` / `schema.d.ts` / `alembic/**` ⇒ contrato sin cambio |
| `Release tag CI` (autoridad externa) | [`38276396567`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38276396567) **VERDE** (`replay-repro` **`✓`**) |

---

## 6. Sello

- **Producto:** `V2.88.115-beta`. **Package:** `2.11.115-beta`. **Sin migración** (head `053`). **Contrato sin cambio.** **`Δ motor ≠ 0` correctivo/aditivo · `Δ decisión = 0`.**
- **Añadidos:** `docs/engineering/evidence/v2.88.115/README.md`, `docs/engineering/plan-v2-88-115-endurecimiento-oos-finance-band-2026-10-12.md`, este documento.
- **Modificados:** `packages/py/application/src/bolsa_application/{estudio_audit.py,oos_finance_band.py}`; `apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py`; tests de aplicación y de CLI; `package.json` + `apps/api-python/scripts/v2_89`…`v2_97` (`meta.bump`); `docs/engineering/PROJECT_STATE.md`.
- **Tag anotado `v2.88.115-beta`** (objeto `289653e7` → commit `789677ca`): `Release tag CI` [`38276396567`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38276396567) **VERDE**; resto de workflows del tag y CI de rama **VERDES**. **Tag unsigned** (declarado). Cierre POST-TAG en `main`: commits `0066a07b` y `d52c7283` (`origin/main` == `HEAD` == `d52c7283`).

---

## 7. Guion de auditoría desde GitHub

1. **Evidencia.** Abrir [`docs/engineering/evidence/v2.88.115/README.md`](https://github.com/jvelasca/Bolsa_V1/blob/v2.88.115-beta/docs/engineering/evidence/v2.88.115/README.md).
2. **Entrega MIA.** Leer este documento.
3. **`Δ decisión = 0`.** Revisar `oos_finance_band.py` (`_fold`/`_identity_from_keys`) y `estudio_audit.py` (`_pick_finance_group`): **solo** componen/plegan lo ya calculado; no cambian selección, umbrales ni reparto.
4. **`P1` — que el hueco no se disfrace de dato.** `test_estudio_audit.py::test_single_group_with_other_preset_is_not_attributed` fija que un grupo único con otra clave **no** se atribuye; `::test_single_keyless_group_still_used_when_value_declares_preset` fija el fallback legítimo.
5. **`H2` — que la ambigüedad no elija «ganadora».** `test_oos_finance_band.py` fija ambiguo/consistente/ausente/agregado y la **invariancia por permutación**; el esquema publicado incluye `strategyPresetKeyAmbiguous` + `strategyPresetKeys[]`.
6. **`H3` — que no se reutilice un informe viejo.** `test_replay_oos_cli_renderers.py` fija purga, reset+ausencia, **rechazo** de fichero reutilizado y **aceptación** de fichero fresco, y la validación de cuenta/versión/ventana del payload.
7. **Reproducción local.**
   ```bash
   uv run ruff check packages/py apps/api-python --config pyproject.toml
   uv run mypy packages/py/application/src --follow-imports=silent
   uv run pytest packages/py/application/tests -q
   uv run pytest apps/api-python/tests/test_replay_oos_cli_renderers.py -q
   uv run pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
   (cd packages/py/infrastructure && uv run alembic heads)   # 053_dia_d_cycle_verifications (head)
   ```
8. **Qué falsaría el sello:** que `P1` vuelva a atribuir dinero de otra estrategia (o marque `measured`) · que `H2` publique **una** clave cuando los sorteos discrepan · que `H3` acepte un `draw-NN.finance.json` **no regenerado** · que `replay-repro` deje de reproducir el artefacto congelado · que aparezca una migración o un cambio de contrato no declarados.
