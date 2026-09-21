# Traspaso — post `v2.48-beta` (AUTO-8 Adaptive AUTO · slice 1) — 2026-09-21

**Para el siguiente chat/agente.** Lee esto **antes** de tocar nada. Si hay contradicción con el plan de la
fase ([`plan-v2-48-auto-8-adaptive-auto-2026-09-21.md`](./plan-v2-48-auto-8-adaptive-auto-2026-09-21.md)),
manda el [audit-pack](./audit-pack-v2.48-auto-8-adaptive-auto-2026-09-21.md).

> **AsOf:** 2026-09-21 · **Base:** `main` · HEAD **`cd5e3863`** (traspaso de `V2.47`) ·
> **tag vigente (a sellar):** `v2.48-beta` (se produce al integrar el árbol) ·
> **Versión de paquete:** `1.73.0-beta` · **Alembic head:** `044_auto_cycle_trace` (sin migración).
> **Árbol:** trabajo de `AUTO-8` slice 1 **sin commitear**; `governor.json` **untracked** (sin trackear por
> diseño: **no** lo añadas a un commit).
> **Fase que cierra:** `AUTO-8` — Adaptive AUTO · slice 1 (`V2.48`, `1.73.0-beta`, roadmap §10).

---

## 1. Estado en una frase

**`AUTO-8` slice 1 está implementado y verificado localmente**: una capa **pura y read-only**
(`auto_adaptive.py`) recomienda rotación (pausa de estrategias por salud de fills / régimen adverso) y
asignación (multiplicador `[0, 1]` que solo estrecha el riesgo por estrategia), y el motor determinista
`plan_v2_tick` la consume como **entradas** — pausando candidatas antes del ranking y estrechando el techo de
riesgo — sin tocar nunca los gates duros. Todo detrás de flag **OFF por defecto** con **byte-identidad**
(`adaptive_enabled`). **Sin migración**, **sin SHORT**, **sin backfill**.

- **Tag anterior:** `v2.47-beta` (fase AUTO-6.x hardening + V2.47 + AUTO-7 slice 1).
- **Freeze que sigue vigente:** `v2_43_governor_evidence.py` **byte a byte** igual (`"bump"` en `1.68.0-beta`),
  tabla del gobernador y umbrales **intactos**, `AUTO_ENGINE_SIM_V2_GOVERNOR=0` byte-idéntico a `v2.43.1`, **sin
  SHORT**, Alembic head `044_auto_cycle_trace`.

---

## 2. Qué cierra esta fase y con qué se mide

| Cierre                                                 | La medida que lo sostiene                                                                         |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| **Existe la recomendación Adaptive (pura, read-only)** | `auto_adaptive.py` + `test_auto_adaptive.py` (**17**) + M19/M20/M21                               |
| **Adaptive no decide: el motor sí**                    | `test_auto_adaptive_entry.py` (**5**) — los 3 gates del roadmap §10 + estrechamiento del risk cap |
| **Flag OFF ⇒ byte-idéntico a AUTO-7**                  | `test_flag_off_payload_is_byte_identical_to_v47` (gate 1)                                         |
| **Adaptive no salta los gates duros**                  | `test_adaptive_cannot_bypass_kill_switch` + `test_adaptive_cannot_bypass_unknown_regime` (gate 2) |
| **Rotación con régimen sintético**                     | `test_rotation_synthetic_regime_pauses_then_activates` (gate 3)                                   |
| **La asignación solo estrecha (`[0, 1]`)**             | `test_allocation_narrows_risk_cap` + `test_allocation_multipliers_are_monotonic_and_bounded`      |

**Verificación agregada del árbol final** (comandos exactos en el §7 del pack):

- `ruff` limpio · `mypy` **491** ficheros 0 issues · `lint-imports` **4 kept / 0 broken** ·
  gobernador **exit 0** con `git diff` **vacío**.
- Bloques offline con los targets **extraídos del YAML**: `quality` **2200** y tag **2211**
  (base `2178`/`2189` ⇒ **+22 en AMBOS**, 0 skipped).
- Suites nuevas: **22 passed** (17 puro + 5 aplicación).
- **Mutaciones: M19/M20/M21 muerden** (4/2/2 rojos), restauración byte a byte y huella `git status` **intacta**.

---

## 3. Lo que queda ABIERTO (con dueño declarado, no con un cero)

1. **El commit de fase y el tag `v2.48-beta` no se han producido.** El árbol de `AUTO-8` está **sin commitear**;
   al integrarlo se produce el commit de fase y el tag anotado, y se observa la **CI real** (Python CI + Release
   tag CI) con `gh` (patrón del repo).
2. **La recomendación Adaptive no se observa en UI.** Solo el detalle del journal la declara. La superficie
   (qué se pausó, por qué, y el multiplicador de riesgo) es una fase nueva.
3. **El flag `AUTO_ENGINE_SIM_V2_ADAPTIVE` sigue en OFF.** La política está implementada y probada, pero
   encenderla cambia qué estrategias compiten y cuánto riesgo se les asigna: **decisión del owner**.
4. **Sin productor de régimen nuevo**: `to_market_regime` mapea el `MarketRegime` del gobernador que el worker ya
   calcula. Un régimen no reconocido es `UNKNOWN` (no adverso), declarado.
5. **`governor.json` sigue untracked** (generado por `v2_43_governor_evidence.py --out`). No lo añadas a un
   commit.
6. **Deudas vivas de fases anteriores** (heredadas del traspaso de `V2.47`): broker SIM por tick, `BROKER_DESYNC`
   sin productor, `allow_distinct_strategies` en OFF (decisión del owner), móvil parcial, y auditar la lista de
   tests de `application`.

---

## 4. Trampas MEDIDAS que te van a morder (léelas dos veces)

1. **La lista de tests de `packages/py/application/tests` es explícita, fichero a fichero**, en `quality`
   (`.github/workflows/python-ci.yml`) y en el job `python` del tag. **Un fichero nuevo ahí no corre si no lo
   registras** — y no falla: simplemente no existe. **Comprobación obligatoria: que el delta de los dos bloques
   sea EXACTAMENTE el mismo.** Esta fase registró `test_auto_adaptive_entry.py` en ambos: `+22/+22`.
2. **Nada de comentarios dentro de un `run: >`.** Los `#` se convierten en "rutas inexistentes" para el runner
   offline. Los comentarios van **fuera** del bloque.
3. **La sonda de mutaciones y el bytecode `.pyc`.** La sonda borra el `.pyc` de cada módulo mutado y corre con
   `PYTHONDONTWRITEBYTECODE=1`. **No lo quites.**
4. **Un test autorreferencial no prueba nada.** Al escribir un test, pregúntate: _¿si invierto la línea que
   quiero proteger, este test se cae?_ Compruébalo **mutando** (M19/M20/M21 nacieron de esta disciplina).
5. **El teardown de `apps/api-python/tests` puede colgar sin PG.** El `connect` de `purge_all_residuals` no es
   instantáneo; la `FAST_FAIL_DSN` de la sonda no garantiza instantáneo en todas las máquinas (M7 flake, ver
   §6.1 del pack). Si una mutación reporta `<TIMEOUT 600s>`, **re-córrela aislada** antes de declarar regresión.
6. **La medida se hace por JUnit XML** con `scripts/verify/offline_ci_run_yaml.py`, que **extrae los targets del
   YAML**: no inventes la lista de tests a mano para "verificar CI".
7. **`adaptive` solo se publica cuando hay algo que declarar** (multiplicador `< 1`): no esperes una clave
   `adaptive` con el flag OFF ni con un multiplicador `1.0`.

---

## 5. Freeze (congelado)

- `AUTO_ENGINE_SIM_V2=0` ⇒ comportamiento `v2.39.x`.
- `AUTO_ENGINE_SIM_V2_GOVERNOR=0` ⇒ byte-idéntico a `v2.43.1` **sin parada dura**.
- `apps/api-python/scripts/v2_43_governor_evidence.py` **byte a byte** igual (su `"bump"` sigue en
  `1.68.0-beta`).
- Tabla del gobernador y umbrales: **no se tocan**.
- **Sin SHORT**: `entry_direction` devuelve `None` para `SELL`.
- **Sin migración ni backfill**: Alembic head `044_auto_cycle_trace`.
- `RiskAllocator.compute_allocation` y `portfolio_decision_engine.py` (vetos fail-closed): **no se tocan**.

---

## 6. Checklist de arranque del siguiente chat

```bash
git log --oneline -3 && git status --porcelain          # HEAD cd5e3863, árbol con trabajo de AUTO-8 sin commitear
uv run python apps/api-python/scripts/v2_43_governor_evidence.py; echo "exit=$?"   # 0 y sin diff
uv run alembic -c packages/py/infrastructure/alembic.ini heads                     # 044_auto_cycle_trace
uv run pytest packages/py/analytics/tests/test_auto_adaptive.py \
              packages/py/application/tests/test_auto_adaptive_entry.py -q         # 22 passed
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py            # 21 mutaciones, exit 0
```

Después: lee el §3 de este traspaso (**lo abierto**) y el §7 del plan (**desviaciones declaradas**) **antes** de
proponer nada.

---

## 7. Siguiente fase (según el roadmap)

- **Integrar y sellar `v2.48-beta`** (commit de fase + tag + CI real observada con `gh`).
- **UI de la recomendación Adaptive** (qué se pausó, por qué, multiplicador de riesgo): fase propia.
- **Más Adaptive** (siempre fuera del hard-risk path): el roadmap §12 lo deja explícito.
- **Deudas vivas** que pueden reclamar su sitio: broker SIM por tick, productor de `BROKER_DESYNC`, encender
  `allow_distinct_strategies` y `AUTO_ENGINE_SIM_V2_ADAPTIVE` (decisión del owner), completar el móvil y auditar
  la lista de tests de `application`.
