# Audit-pack `AUTO-8.1` Adaptive correcto, explícito y reproducible — `1.74.0-beta` (2026-09-21)

**Punto de partida:** tag **`v2.48-beta`** (`1.73.0-beta`).
**Migración:** **NO** — Alembic head sigue en **`044_auto_cycle_trace`**.
**Bump:** `1.73.0-beta` → **`1.74.0-beta`**.
**Sonda de mutaciones:** [`apps/api-python/scripts/v2_44_mutation_audit.py`](../../apps/api-python/scripts/v2_44_mutation_audit.py)
(matriz extendida con **M19–M27**; ver §6).
**Sello:** tag anotado **`v2.49-beta`** (ver §12).

Este documento sigue la convención del repo: **lo que se midió, con el artefacto que lo produjo**. Donde algo no
se pudo medir, se declara **no medido** (no se rellena con un cero). El plan de la fase es
[`plan-v2-49-auto-8-1-adaptive-correcto-2026-09-21.md`](./plan-v2-49-auto-8-1-adaptive-correcto-2026-09-21.md)
y el relevo,
[`traspaso-relevo-post-v2-49-auto-8-1-adaptive-correcto-2026-09-21.md`](./traspaso-relevo-post-v2-49-auto-8-1-adaptive-correcto-2026-09-21.md).
Si el plan y este pack se contradicen, **manda el pack**.

---

## 0. Resumen: qué cierra esta pasada

| #   | Hallazgo / deuda (auditoría externa de `v2.48`)                                      | Estado    | Evidencia (medida)                                                                       |
| --- | ------------------------------------------------------------------------------------ | --------- | ---------------------------------------------------------------------------------------- |
| 1   | La asignación no exigía decisividad POR FILA (una muestra fina movía el reparto)     | CERRADO   | gate por fila + `test_allocation_non_decisive_positive_does_not_leak_into_reparto` (M23) |
| 2   | "Sin evidencia" no era política: era `1.0` por default o `0.0` por ausencia de clave | CERRADO   | `AdaptivePolicy.unknown_multiplier` + materialización por versión (M22)                  |
| 3   | El multiplicador `0.0` **quitaba** el techo de riesgo (cedía todo el `risk_budget`)  | CERRADO   | techo cero explícito en `compute_allocation` + 2 tests (ver §4)                          |
| 4   | Sin `policyVersion`, sin evidencia en el journal, sin goldens de reproducibilidad    | CERRADO   | `auto8-v2` + `evidence_for` + ON-neutral≡OFF + golden de orden (M24)                     |
| 5   | Rotación sin hysteresis ni cooldown (riesgo de parpadeo)                             | CERRADO   | zona muerta PF `1.0`→`1.10` / WR `0.35`→`0.45` + `min_pause_cycles` (M25/M26/M27)        |
| 6   | `strategy × regime` y `net expectancy_R` sin productor de datos                      | DECLARADO | forma `UNKNOWN`/`None` en `StrategyHealth`; política ignora `UNKNOWN` (§9)               |

---

## 1. La corrección de la asignación — `recommend_allocation`

`packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive.py`.

Antes (`v2.48`):

- `positive` se construía con `row.expectancy_currency is not None and > 0`, **sin** `row.decisive`;
- `decisive_positive = any(row.decisive and ...)` comprobaba la decisividad del **grupo**, no por fila;
- con al menos una decisoria positiva, `shares` solo contenía las claves de `positive`, y cualquier otra activa
  caía en `shares.get(..., 0.0)` ⇒ multiplicador `0.0` (riesgo cero) por una muestra no validada.

Ahora:

- solo las filas `decisive` con `expectancy_currency > 0` entran al numerador;
- **cada** versión activa tiene su entrada en el mapa: las que no reparten reciben
  `AdaptivePolicy.unknown_multiplier` (neutral `1.0` por defecto);
- `recommend_allocation` **nunca** emite `0.0`.

La semántica de "sin evidencia" es una **política declarada y configurable**, no el default de
`AllocationPlan.multiplier_for`.

---

## 2. El sello de política y la evidencia en el journal

- **`AdaptivePolicy(policy_version="auto8-v2")`** viaja en `AdaptivePlan.policy_version`, en `as_dict()`
  (`"policyVersion"`) y en el journal. Cambiar umbrales, la regla de asignación o el suelo de régimen **exige**
  subir la versión.
- **Evidencia por estrategia** (`AdaptivePlan.evidence_for`): `decisive`, `trades`, `expectancyCurrency`,
  `expectancyR`, `netExpectancyR`, `profitFactor`, `winRate`, `regime`. Se publica en el **estrechamiento**
  (`payload["adaptive"]["evidence"]`, solo cuando el multiplicador es `< 1.0`) y en la **pausa**
  (`payload["adaptiveEvidence"]`).
- Con el flag OFF, o con la recomendación neutral (multiplicador `1.0`), el payload del tick sigue siendo el
  histórico: la byte-identidad no se paga con trazabilidad, se compaginan (ver §5, golden ON-neutral≡OFF).

---

## 3. Hysteresis y cooldown

| Regla                 | PAUSA                      | REACTIVACIÓN                    |
| --------------------- | -------------------------- | ------------------------------- |
| Salud (profit factor) | `pf < 1.0` (decisoria)     | `pf >= 1.10` y expectancy `> 0` |
| Régimen adverso (WR)  | `wr < 0.35` (no decisoria) | `wr >= 0.45`                    |
| Cooldown              | `min_pause_cycles = 3`     | tras cumplir la ventana mínima  |

El estado previo entra como **dato** (`paused_cycles`), nunca como estado interno del módulo puro. Sin muestra
decisoria, una pausa de **salud** no puede sostenerse (no pudo originarse ahí): manda la regla de régimen. El
worker mantiene el contador en memoria (`_v2_adaptive_paused_cycles`), reiniciado con el proceso (límite §9).

---

## 4. La inversión `0.0 → sin techo` (cerrada)

`0.0` llegaba a `compute_allocation` como `max_risk_per_trade_pct = base * 0.0 = 0.0`. El guard `pct > 0` dejaba
`max_by_pct = None`, así que `risk_amount = risk_budget` (TODO el presupuesto de cartera) y **sin**
`CAP_RISK_PCT`. El env no puede producir `0.0` (`_env_float(...) or base`), de modo que la **única** ruta era el
multiplicador Adaptive: el "estrechamiento máximo" asignaba MÁS riesgo por operación que cualquier otro.

Ahora `pct == 0.0` es un techo **cero explícito** (`max_by_pct = 0.0`, `CAP_RISK_PCT`, `quantity = 0`,
`approved = False`). `None` conserva su único significado: "sin techo por porcentaje". El resto del sizing y
`portfolio_decision_engine.py` no se tocan.

---

## 5. Verificación local medida (árbol final)

| Comprobación                | Comando                                                                                                             | Resultado                                                        |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Estático (invocación de CI) | `uv run ruff check packages/py apps/api-python --config pyproject.toml`                                             | **All checks passed!**                                           |
| Tipos                       | `uv run mypy … --follow-imports=silent`                                                                             | **491 ficheros, 0 issues**                                       |
| Fronteras                   | `uv run lint-imports --config packages/py/.importlinter`                                                            | **4 kept / 0 broken** (610 ficheros, 3256 deps)                  |
| Suites Adaptive + sizing    | `uv run pytest …/test_auto_adaptive.py …/test_auto_adaptive_entry.py …/test_risk_allocator.py -q`                   | **51 passed** (29 + 9 + 13)                                      |
| Matriz de mutaciones        | `uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py`                                           | **6/6 nuevas (M22–M27) muerden** + M19–M21 verdes; árbol intacto |
| Bloque `quality` de CI      | `uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores`     | **2218 passed, 0 failed, 0 skipped**                             |
| Bloque `python` del tag     | `uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores` | **2229 passed, 0 failed, 0 skipped**                             |

### 5.1 Delta de cobertura

| Fichero                                                     | `v2.48` | `v2.49` | Delta   |
| ----------------------------------------------------------- | ------- | ------- | ------- |
| `packages/py/analytics/tests/test_auto_adaptive.py`         | 17      | 29      | **+12** |
| `packages/py/application/tests/test_auto_adaptive_entry.py` | 5       | 9       | **+4**  |
| `packages/py/analytics/tests/test_risk_allocator.py`        | 11      | 13      | **+2**  |

`test_auto_adaptive_entry.py` está **registrado a mano** en los dos jobs (`python-ci.yml` y
`release-tag-ci.yml`), así que el delta de los dos bloques debe ser **igual** (comprobación de cobertura).

Medido: `quality` pasa de **2200** (`v2.48`) a **2218**; el job `python` del tag, de **2211** a **2229**. El delta
es **exactamente +18 en los dos bloques** (`+12` analytics del pase de directorio, `+2` `test_risk_allocator.py`
del pase de directorio, `+4` del fichero registrado a mano), que es la comprobación de que ningún test nuevo se
quedó fuera de una de las dos listas.

---

## 6. Mutaciones (M19–M27) — MEDIDAS

**Sonda:** [`v2_44_mutation_audit.py`](../../apps/api-python/scripts/v2_44_mutation_audit.py). Patrón de la casa:
copia en memoria, restauración **sin** `git checkout --`, huella `git status --porcelain` antes/después.

| #   | Mutación aplicada (revertir el fix)                          | Rojos observados (medido) |
| --- | ------------------------------------------------------------ | ------------------------- |
| M19 | la estrategia probadamente negativa deja de pausarse         | **4**                     |
| M20 | la pausa en régimen adverso deja de aplicarse                | **2**                     |
| M21 | el multiplicador deja de acotarse a `[0, 1]`                 | **2**                     |
| M22 | el multiplicador de una versión sin evidencia cae a `0`      | **7**                     |
| M23 | una muestra no decisoria entra al reparto proporcional       | **1**                     |
| M24 | el plan deja de sellar `policyVersion`                       | **2**                     |
| M25 | el umbral de reactivación baja al de pausa (sin zona muerta) | **1**                     |
| M26 | sin decisividad la pausa de salud se declara vigente         | **1**                     |
| M27 | la pausa mínima (cooldown) deja de respetarse                | **1**                     |

**Balance: 6 de 6 mutaciones NUEVAS (M22–M27) muerden** y **M19–M21 siguen mordiendo** (M19–M21 se actualizaron a
los nuevos fragmentos del código); la línea base queda **verde**, cada mutación se **restaura byte a byte**
(`restaurado byte a byte: si`) y la huella `git status` de los ficheros mutados es **idéntica** antes y después
(`intacto: la sonda no altero el arbol`).

---

## 7. Cómo verificarlo (para el auditor)

```bash
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
         packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

uv run pytest packages/py/analytics/tests/test_auto_adaptive.py \
              packages/py/application/tests/test_auto_adaptive_entry.py \
              packages/py/analytics/tests/test_risk_allocator.py -q   # 51 passed

uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py   # M19-M27, exit 0

uv run alembic -c packages/py/infrastructure/alembic.ini heads        # => 044_auto_cycle_trace
```

---

## 8. Registro en CI

Sin ficheros de test nuevos: `test_auto_adaptive.py` y `test_risk_allocator.py` entran por el pase de directorio
`packages/py/analytics/tests`; `test_auto_adaptive_entry.py` ya estaba registrado a mano en ambos jobs. No hay
delta asimétrico que corregir.

---

## 9. Límites declarados (no silenciosos)

- **Salud solo de fills**: no hay migración ni backfill; lo no medido es `UNKNOWN` y una estrategia sin muestra
  **no** se rota.
- **La asignación solo estrecha** (`[0, 1]`): nunca ensancha el riesgo por operación por encima del techo del
  gobernador; `0.0` veta (techo cero explícito).
- **`net expectancy_R` no medido**: `StrategyHealth.net_expectancy_r` es siempre `None` hoy. `expectancy_currency`
  es **bruto** (`(sell − buy) × qty`, sin comisión ni slippage) y el `expectancy_r` de la self-evaluation es `None`
  porque ningún productor emite `r_multiple` por ciclo.
- **`strategy × regime` no medido**: `StrategyHealth.regime` es siempre `UNKNOWN` (los fills no llevan régimen).
  La rotación usa el régimen **del tick**; la política ignora `UNKNOWN` y no se inventa el cruce.
- **Cooldown en memoria**: `_v2_adaptive_paused_cycles` se reinicia con el proceso; tras un crash una pausa puede
  levantarse antes de su ventana mínima (sin tabla ni migración en esta fase).
- **Sin UI**: la recomendación, la política y la evidencia solo son observables vía el detalle del journal.
- **`governor.json` sin trackear** (generado por la evidencia del gobernador).

---

## 10. Freeze (congelado, no tocar sin motivo)

- **Comportamiento de `AUTO_ENGINE_SIM_V2=0`**: debe seguir siendo `v2.39.x`.
- **Comportamiento de `AUTO_ENGINE_SIM_V2_GOVERNOR=0`**: byte-idéntico a `v2.43.1` **sin parada dura**.
- **`v2_43_governor_evidence.py`**: **byte a byte igual** y su `"bump"` se queda en `1.68.0-beta`.
- **Tabla del gobernador y sus umbrales**: **no** se tocan.
- **`v2.48-beta` y anteriores no se mueven**: `v2.49-beta` es **nueva y aditiva**.
- **Sin SHORT**.
- **Sin migración ni backfill**: Alembic head sigue `044_auto_cycle_trace`.
- **`RiskAllocator.compute_allocation`**: solo cambia el borde `pct == 0.0`; el resto del sizing y
  `portfolio_decision_engine.py` **no** se tocan.

---

## 11. Gate de `AUTO-9` (lo que falta y por qué no se inventó)

`strategy × regime` y `net expectancy_R` **no tienen productor, pero sí tienen datos**: los tres insumos ya
viven en fuentes durables, atados por `cycle_id` (migración `044`). Lo que falta es el adaptador que los lea y
la agregación, no el esquema. **Corrección medida el 2026-09-22** (lo que aquí decía «probable migración `045`»
era una inferencia, y era falsa):

- **`risk_amount`** (el denominador de R): `portfolio_reservations.reserved_risk`, junto a `entry`, `stop`,
  `quantity`, `side` y `cost` (JSONB de `TradingCost`: comisión/spread/slippage/gap), indexado por `cycle_id`
  (`portfolio_reservations_cycle_id_idx`, migración `044`). El motor ya lo escribe con el `riskAmount` de la
  asignación (`auto_v2_entry._reserved_sizing`), y el store ya mapea `cycle_id`.
- **PnL realizado**: `sim_fill_finance_context` por `cycle_id` — exactamente lo que `cycles_from_fills` agrega.
- **Régimen de entrada**: `marketRegime` del payload del journal, que ya viaja con el `cycleId`.

Por tanto **AUTO-9 no exige migración de esquema**: el head sigue en `044`. Lo que sí hay que **medir** es el
coste de leer el régimen desde el JSONB del journal (no hay índice sobre `payload->>'cycleId'`); si sale caro, la
respuesta es un índice **aditivo**, no una tabla nueva. Y el coste disponible es el **estimado en la decisión**,
no el realizado, así que `netExpectancyR` tendrá que publicarse etiquetado como tal y `net_expectancy_r` seguirá
siendo un subconjunto declarado (`PARTIAL`), nunca un total silencioso. Se entrega la **forma**
(`UNKNOWN`/`None` declarados) y el plan de la fase en
[`plan-v2-50-auto-9-strategy-regime-y-net-expectancy-r-2026-09-22.md`](./plan-v2-50-auto-9-strategy-regime-y-net-expectancy-r-2026-09-22.md),
en vez de publicar un cruce o un neto fabricados.

---

## 12. Sello (HECHO y medido)

**Commit de fase:** `2f541fc7` — `feat(v2.49): AUTO-8.1 Adaptive correcto, explícito y reproducible
(1.74.0-beta)`, **14 ficheros**, `+1248/−91`. **Tag anotado:** `v2.49-beta` → objeto `3d0a139b` → commit
`2f541fc7`. `package.json` → **`1.74.0-beta`**; `CHANGELOG.md` con la entrada de la fase; docs
`plan`/`pack`/`traspaso` en `docs/engineering/`; freeze declarado en §10. El push a `main` fue
**fast-forward** (`fae8ec29..2f541fc7`, 1 delante / 0 detrás).

**CI real (observada con `gh` sobre el commit sellado, 2026-09-22).** Diez runs, **todos `success`**, cero rojos:

| Ref                | Workflow           | Run                                                                            |
| ------------------ | ------------------ | ------------------------------------------------------------------------------ |
| `v2.49-beta` (tag) | **Release tag CI** | [`35694148660`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35694148660) |
| `v2.49-beta` (tag) | Python CI          | [`35694148702`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35694148702) |
| `v2.49-beta` (tag) | Frontend CI        | [`35694148679`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35694148679) |
| `v2.49-beta` (tag) | Optimize lab       | [`35694148691`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35694148691) |
| `v2.49-beta` (tag) | Fase 2 scientific  | [`35694148758`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35694148758) |
| `main`             | Python CI          | [`35694063954`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35694063954) |
| `main`             | Frontend CI        | [`35694063893`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35694063893) |
| `main`             | Optimize lab       | [`35694063913`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35694063913) |
| `main`             | Fase 2 scientific  | [`35694063898`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35694063898) |
| `main`             | Gitleaks           | [`35694064028`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35694064028) |

---

## 13. Anécdota operativa MEDIDA: el push de 4 tags no disparó la CI del tag

Al empujar con `git push origin main --follow-tags`, `--follow-tags` arrastró **cuatro** tags locales
(`v1.35-beta`, `v1.57-beta`, `v1.58-beta` y el nuevo `v2.49-beta`). GitHub **no creó ningún evento de tag**:
salieron los cinco workflows del push a `main` y **ninguno** de los del tag (ni `Release tag CI`). No es un fallo
del repo ni del workflow: es una limitación documentada de GitHub.

> _Events will not be created for tags when more than three tags are pushed at once._
> — [Webhook events and payloads](https://docs.github.com/en/webhooks/webhook-events-and-payloads#push)
> (mismo comportamiento reportado en [actions/runner#3644](https://github.com/actions/runner/issues/3644))

**Mitigación aplicada y medida:** recrear el tag **solo** (`git push origin :refs/tags/v2.49-beta` y después
`git push origin v2.49-beta`) generó el evento y los cinco workflows del tag arrancaron, con `Release tag CI` en
**`success`**. **Lección para el próximo sello:** no usar `--follow-tags` en un repositorio con tags locales
antiguos; empujar el tag de la fase **de uno en uno**.
