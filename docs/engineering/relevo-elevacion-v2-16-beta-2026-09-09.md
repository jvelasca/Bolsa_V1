# RELEVO — v2.16-beta elevado a `main` (V2.15.4 account-less + V2.15.5 DR industrial) — 2026-09-09

> **Padre (hechos del delta):** relevo de bloque [`traspaso-relevo-v2-15-5-dr-industrial-2026-09-09.md`](./traspaso-relevo-v2-15-5-dr-industrial-2026-09-09.md) (V2.15.5 DR industrial) sobre `16d84031` = V2.15.4 → rama `main`, además del relato de la faena V2.15.4 (aislamiento account-less).
> **Este fichero:** **relevo de cierre de la ELEVACIÓN** de `v2.16-beta`. **NO es una nueva implementación** — junta dos entregas ya implementadas y verificadas localmente (V2.15.4 + V2.15.5) que estaban SIN tag/push sobre el último `v2.15.3-beta`. Núcleo financiero congelado **intacto**.
> **Alcance de la elevación:** bump de paquete + CHANGELOG + doc off-site 3er medio. Sin cambio de código de núcleo ni migración (Alembic head se mantiene `023_ohlcv_bars_unique_reconcile`).

## 1. Motivación (decisión owner, sub-bloque)

El relevo V2.15.5 (§8) dejó el arranque natural V2.16 = _elevar/taggear (run real) + materializar el 3er medio off-site_. El owner optó por: **un solo bump/serie menor** que engloba las dos entregas locales y **una guía MVP declarativa** para el 3er medio (sin credenciales), sin bloquear la certificación.

## 2. Qué se elevó (código previo ya en `main`), ahora auditable desde GitHub

| Pieza                                                      | Commit                                                                                                                     |
| ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Base                                                       | `main` en `5ef9016b` (tag `v2.15.3-beta`)                                                                                  |
| V2.15.4 (aislamiento account-less P1 C2-06)                | `16d84031` (ya en `main` local, no elevado)                                                                                |
| V2.15.5 (DR industrial; snapshot/digest/OHLCV/C2-01/3-2-1) | `302a3220` (ya en `main` local, no elevado)                                                                                |
| Commit elevación (bump)                                    | `14afd886` (bump `1.46.0-beta` + CHANGELOG + guía off-site)                                                                |
| Commit fix del gate CI                                     | `5a1bb206` (higiene `account-isolation`, ver §5)                                                                           |
| Tag                                                        | [`v2.16-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.16-beta) → `5a1bb206` (re-tag tras fix del primer run) |
| Previo                                                     | `v2.15.3-beta` → `5ef9016b`                                                                                                |
| Alembic head                                               | `023_ohlcv_bars_unique_reconcile` (sin migración nueva)                                                                    |

## 3. Cambios del commit de elevación (`14afd886`)

- `package.json` root: version `1.46.0-beta`.
- `CHANGELOG.md`: entrada `## [1.46.0-beta] — 2026-09-09` (V2.15.4 + V2.15.5 + verificación real).
- `docs/engineering/guia-off-site-3er-medio-2026-09-09.md` (**nuevo**): guía MVP del 3er medio off-site — topología 3-2-1 honesta (medio 3 = sync Rclone de `<DB_BACKUP_MIRROR_DIR>/db-backups`), set-up declarativo (`rclone config` + `schtasks` de sync + `rclone check`), sin credenciales; deuda residual declarada.
- `apps/api-python/tests/test_account_isolation.py` (**fix `5a1bb206`**): ver §5.

## 4. Verificación

- **Estática previa al push:** working tree limpio; `node --check`/aislamiento ya cubiertos en los commits elevados (43 passed real-PG en V2.15.5; la iso 2-owners V2.15.4 verde).
- **Gate industrial del tag:** job `dr-verify` (battery DR/SQL) + aggregate `certify` (needs: security, shared, spine, frontend, python, playwright-mock, lifecycle-pg, dr-verify) del **Release-tag CI**. **Dos runs no-GREEN** (ver §5); el fix higiénico lleva el gate de isol de **10 → 40 passed**, pero quedan **3 fallos REALES de scope de V2.15.4** (ver §6) por reproducción local puntual.
- Nota: Docker Desktop local no estaba levantado al elevar; la batería DR local con volumen real que reportó V2.15.5 es la cubierta en el propio relato de esa faena. El CI del tag corre la DR por TCP sobre PG `postgres:16-alpine` del runner.

### Resultado concreto de los runs del tag

- **Run 1** (`34321014783`, sobre commit de elevación `14afd886`): no-GREEN → `lifecycle-pg` paso `account-isolation gate` 33/43 con **401** (cascada de cache auth-ON, ver §5). Todo lo demás (incl. `dr-verify`) green.
- **Run 2** (`34322567613`, re-tag en `5a1bb206` con fix de higiene): no-GREEN → el MISMO paso pasa **40/43**; quedan **3 fallos reales de scope** (ver §6). `dr-verify` green.
- **Estado del tag:** `v2.16-beta` apunta al commit del fix (`5a1bb206`), **no-GREEN a día de hoy**. PARA CERTIFICAR el tag hace falta resolver los 3 fallos de scope de V2.15.4 (reproducción con PG local) y re-lanzar.

## 5. Incidencia del primer run no-GREEN + fix de higiene COMITTEADO (`5a1bb206`)

- Fix **pusheado a `origin/main`** y re-tag realizado (ver §2/§4).
- **Causa raíz:** los tests auth-ON de `test_account_isolation.py` cae el `assert user "app"` (sin seeding de CI) **antes** del `get_settings.cache_clear()` final → `Settings` cacheado (`@lru_cache`) con auth ON contamina al proceso pytest → 401 en cascada.
- **Fix (test/hygiene, sin tocar núcleo):** `finally` incondicional de `get_settings.cache_clear()` + helper idempotente `_ensure_app_user(factory)` (seeds `app`, login `app`, password `s3cret`). `ruff` PASSA. Prueba del efecto: el gate pasa de 10 → 40 en el run 2.

## 6. Pendiente — 3 fallos REALES de scope de V2.15.4 (requieren PG local para dirimir)

En el run 2, `dr-verify` green y todo lo demás en verde salvo 3 tests **con lógica de scoping real** (ya no 401 de infra). Reproducen en real-PG del job y necesitan PG local para decidir si son **bug de V2.15.4** (sub-scope en list_decision_sessions/refresh-observed) o **datos residuales del job**:

1. `test_accountless_decision_sessions_scoped_to_principal_default_account` — session de cuenta default no aparece (`session_a in ids` → vacío).
2. `test_accountless_scoped_by_principal_default_not_a_when_b_principal` — idem.
3. `test_refresh_observed_accountless_does_not_read_foreign_or_orphan_memory` — refresh-observed account-less devuelve `200` donde 404.

**Acción owner (elegida):** no relanzar más tag-CI a ciegas; dejar bump/tag/fix pusheados y reproducir con Docker/PG local apuntando el mismo paso (`uv run pytest apps/api-python/tests/test_account_isolation.py -q --tb=long`) para reparar el núcleo V2.15.4 si aplica, y re-elevar/GREENear `v2.16-beta` tras ello.

## 7. Deuda / clarificaciones heredadas (no bloquean)

1. **3er medio off-site** sin automatizar del todo: la guía MVP no crea credenciales ni remoto; ejecutarlo requiere `rclone config` del owner + apuntar `DB_BACKUP_MIRROR_DIR` a un mount sincronizado + el `schtasks`/job de sync (documentado con plantillas `rclone sync`/`rclone check`).
2. **Retención off-site** sin estado propio: la poda remota (`retentionPrune`) solo actúa en local; el 3er medio crece con el espejo.
3. `release-tag-ci.yml` **sin cambios** en V2.15.5 ni en este bloque; los fixes fueron de test/hygiene, no de estructural del workflow.

FIN DEL RELEVO (de bloque de elevación) — V2.16-beta elevado y taggeado en **`v2.16-beta` → `5a1bb206`** (bump `1.46.0-beta`), pusheado y auditable desde GitHub. **ESTADO: TAG NO-GREEN pendiente de resolver** — dos runs del Release-tag CI no-GREEN: cascada 401 (arreglada vía fix de higiene `5a1bb206`) + **3 fallos reales de scope de V2.15.4** (lista en §6). `dr-verify` (DR industrial) GREEN en ambos. Acción del owner: reproducir §6 con PG local y, al corregirse, re-lanzar el tag para GREEN final.
