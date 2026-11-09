# Errata de alcance del diff de `v2.88.186-beta` (2026-11-08)

**Naturaleza:** errata documental. **No** re-etiqueta, **no** reescribe y **no** reabre el acto de
publicación `.186`. El objeto certificado sigue siendo el tag anotado
`v2.88.186-beta` (objeto `db919045…`) → commit `a5013f75`.

**Qué corrige:** la frase que describía el diff `v2.88.183-beta..v2.88.186-beta` como si no contuviera
cambios funcionales («**Nada de motor, decisión, contrato, UI ni migraciones**»). Esa frase es cierta
para el **delta propio del sello** (`.185 → .186`) y **falsa** para el **contenido acumulado desde la
última Release** (`.183 → .186`).

---

## 1. Los dos ámbitos, medidos

| Ámbito | Base | Commits | Ficheros | Líneas | Contenido |
| --- | --- | --- | --- | --- | --- |
| **A. Delta propio del sello** | `31c2d3cd` (árbol `.185`) | **30** | **28** | +2 634 / −26 | `package.json`, 14 `meta.bump`, `CHANGELOG`, `docs/`, pin (`scripts/`), fixtures de los golden V191/V195/V196, E2E live y `release-tag-ci.yml`, `final_package.py`, `window-preflight.ps1` |
| **B. Acumulado desde la última Release** | `2ffc037b` (`.183`) | **116** | **231** | +25 471 / −1 108 | Todo lo de A **más** la evolución funcional integrada en los árboles `.184` y `.185` |

Comandos que producen la tabla:

```bash
git rev-list --count 31c2d3cd..v2.88.186-beta^{}          # 30
git diff --shortstat  31c2d3cd v2.88.186-beta^{}          # 28 files, +2634/-26

git rev-list --count 'v2.88.183-beta^{}..v2.88.186-beta^{}'   # 116
git diff --shortstat  'v2.88.183-beta^{}' 'v2.88.186-beta^{}' # 231 files, +25471/-1108
```

## 2. Qué rompe exactamente la afirmación

Ámbito **A** (el sello) no toca producto: no hay módulos de motor ni migraciones en la comparación
`31c2d3cd..a5013f75`. La afirmación es defendible **solo** ahí.

Ámbito **B** sí contiene producto. Cambios de implementación desde `.183` hasta el tag:

| Fichero | Δ |
| --- | --- |
| `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` | 1 158 líneas |
| `apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py` | 89 líneas |
| `apps/api-python/src/bolsa_api/background/paper_auto_engine_worker.py` | 64 líneas |
| `apps/api-python/src/bolsa_api/background/window_day_watch_worker.py` | 173 líneas |
| `apps/api-python/src/bolsa_api/api/v1/routes/account_evidence_policy.py` | 105 líneas (nueva) |
| `apps/api-python/src/bolsa_api/api/v1/routes/auto_engine_intent.py` | 163 líneas (nueva) |
| `apps/api-python/src/bolsa_api/api/v1/routes/signals_evaluate.py`, `auto_operational_monitor.py`, `router.py`, `dependencies.py` | 42 líneas |
| `apps/api-python/src/bolsa_api/schemas/signals_evaluate.py` | 7 líneas |

Total en `apps/api-python/src/bolsa_api`: **15 ficheros, +1 564 / −261**.

Migraciones nuevas en el rango acumulado (`packages/py/infrastructure/alembic/versions/`):

- `063_auto_engine_lease.py`
- `064_strategy_account_scope.py`
- `065_auto_engine_intent.py`
- `066_account_evidence_policy.py`

Por tanto la cabecera de migración del sello (`head` = `066_account_evidence_policy`) es correcta
**como estado del árbol**, pero no es correcto inferir de ella que el rango `.183 → .186` no introdujo
migraciones: las introdujo, antes de `.186`.

## 3. Atribución correcta

- El acto `.186` **no** introduce esos cambios: los publica.
- La evolución funcional entró en los árboles `.184` y `.185`, que **nunca recibieron tag ni Release**.
- `v2.88.186-beta` es el primer objeto etiquetado que los contiene. Un auditor que compare `.186`
  contra `.183` **sí** ve cambios de motor; quien compare `.186` contra `.185` **no**.
- En consecuencia: `Δ motor = 0` debe leerse siempre como **«respecto a `.185`»**, nunca como
  «respecto a la última Release».

## 4. Sobre el expediente dentro del tag

El `docs/engineering/evidence/v2.88.186/README.md` **del tag** dejó la sección §5 (POST-TAG) con
`_pendiente de medición POST-TAG_` y el valor de pin `apps f50042c1…`, anterior al re-anclaje a
`d39a04a7…`. Es esperado: el tag no se reescribe para incorporar documentación posterior. `main` es
quien la completa. Consecuencia práctica para el auditor:

| Documento | Dónde leerlo |
| --- | --- |
| Evidencia del sello, §1-§4, §6-§7 | válido en el tag |
| Evidencia del sello, §5 POST-TAG | **solo** válido en `main` (`6919eb5f` y posteriores) |
| Esta errata | `main`; no existe en el tag |

## 5. Alcance de esta errata

- **No** cambia el dictamen de publicación: el tag sigue técnicamente validado.
- **No** convierte `.186` en funcionalmente idéntico a `.183`.
- **No** afirma que el CI GREEN demuestre rentabilidad: `paper_forward_results = 0`,
  `measurable_cycles 0/32`, `PAPER INCONCLUSIVE`.
- **No** modifica el pin ni el freeze: `apps d39a04a7…` / `packages 2de53cda…` del tag son idénticos
  al pin vigente.

## 6. Falsación

```bash
# el delta del sello no toca motor
git diff --name-only 31c2d3cd v2.88.186-beta^{} -- 'apps/api-python/src/**'

# el acumulado sí
git diff --stat 'v2.88.183-beta^{}' 'v2.88.186-beta^{}' -- apps/api-python/src/bolsa_api

# migraciones en el acumulado
git diff --name-only 'v2.88.183-beta^{}' 'v2.88.186-beta^{}' -- packages/py/infrastructure/alembic/versions

# los árboles del tag siguen siendo el pin
git rev-parse a5013f75:apps a5013f75:packages
```

Si alguno de estos comandos discrepa de la tabla, esta errata es falsa en ese punto y debe corregirse
con un acto nuevo, no reescribiendo el tag.
