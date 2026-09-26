# Arranque del agente — post `v2.71-beta` (`AUTO-19A`+`AUTO-19B`)

> **AsOf:** 2026-09-26 · **Tag vigente:** `v2.71-beta` (`1.96.0-beta`) · **Base:** `v2.70-beta`

## Contexto en una frase

`v2.71` es una **corrección del instrumento**: separa `P(ciclo>0)` (`cyclePositiveShare`) de
`P(edge>0)` (`edgePositiveProbability`), hace que la **calibración compare magnitudes homogéneas**
(`P(ciclo>0)` IS vs frecuencia positiva OOS) y cierra los **tres P3** de `AUTO-19A`/`AUTO-19B`
(cobertura no medida, nivel sin clampar, colisión de clave). **Sin estadística nueva, sin migración y
sin mover el reparto** (`auto18-v1` / `auto15-v1`).

## El invariante que instala

> **`P(R>0)` es la fracción de CICLOS positivos (lo medido) y `P(edge>0)` es la fracción de MEDIAS
> bootstrap positivas (el edge); la calibración solo compara magnitudes homogéneas, y lo que no se
> midió se declara — nunca se cuenta como evidencia negativa ni se publica con un nivel que no se usó.**

## Estado verificado

- `auto_adaptive_uncertainty.py`: `edge_positive_probability` + `cycle_positive_share`; sello
  `bootstrap_episodes_v3`.
- `auto_adaptive_replay.py`: `isCyclePositiveShare`, `dominantRegimeCoverage`, `cellsUnmeasured`,
  nivel clampeado.
- `auto_adaptive_calibration.py`: `walk_forward_calibration_v4`; `auto_adaptive_regime_evidence.py`:
  `current_regime_evidence_v2`; `auto_evidence_validation.py`: sellos `_v2`.
- Mutaciones **M193–M197** nuevas (`M182`–`M184`/`M187` actualizadas); matriz **197/197** (192 + 5 nuevas; el plan citaba `198` por un desliz aritmético).

## Deuda conocida y su estado

| Deuda | Estado |
|---|---|
| **H1** `P(R>0)` mezclaba dos funcionales | **cerrada** en `v2.71` |
| **H2** cobertura no medida contaba como no cubierta | **cerrada** en `v2.71` |
| **H3** nivel de intervalo publicado sin clampar | **cerrada** en `v2.71` |
| **H4** colisión de la clave `regimeCoverage` | **cerrada** en `v2.71` |
| **La corrida PAPER real** (material real) | **abierta** — paso operativo del propietario; RUN y harness listos |
| **P3-2** correlación por cubos (validación empírica) | **abierta** — requiere material real |
| **P3-3** `P(R>0)` vs tamaño muestral | **abierta** — no convertir en confidence/allocation |
| current-regime gating operativo · LIVE · allocation dinámica | **fuera de alcance** |

## Qué queda por hacer (elegir)

1. **Aportar material PAPER real** (el propietario) y correr el protocolo: **1 estrategia → ≥32
   ciclos medibles → `auto_evidence_run.py`**; luego **2ª estrategia** y `auto_evidence_validate.py`.
2. **Cerrar P3-2/P3-3** con el primer dataset real usando los diagnósticos del harness.
3. Usar la evidencia publicada para **decidir** algo (sizing, gating de régimen, restricción por
   correlación): decisión **de producto**, no tomada.

## Comandos de arranque

```bash
git fetch --tags
git log --oneline -5
pnpm --filter @bolsa/web test
uv run pytest packages/py/analytics packages/py/application -q
uv run pytest apps/api-python/tests/test_auto_v70_auto23_evidence_validation.py -q
uv run python apps/api-python/scripts/v2_44_mutation_audit.py M193 M194 M195 M196 M197
# Corrida de evidencia (fixture declarado; el material real es del propietario):
uv run --no-sync python apps/api-python/scripts/auto_evidence_run.py \
    --cycles packages/py/analytics/tests/fixtures/auto_calibration_cycles.json
# Validación (barrido + régimen + correlación):
uv run --no-sync python apps/api-python/scripts/auto_evidence_validate.py \
    --cycles packages/py/analytics/tests/fixtures/auto_calibration_cycles.json \
    --sizes 16,32,64 --buckets day,week
```

## Reglas de la casa a recordar

- Un nombre, un funcional: `P(R>0)` = **ciclos**; `P(edge>0)` = **medias**.
- Lo que no se midió se **declara** (`None` + `cellsUnmeasured`); nunca evidencia negativa ni un `0`.
- El nivel que se publica es el que se **usó** (clampeado).
- Un contrato que no puede fallar **no es un contrato**: cada invariante viaja con su mutación.
- La UI **lee y presenta**; nunca recalcula.
- No se toca el freeze ni el reparto (`auto18-v1`/`auto15-v1`). **Sin migración.**
- **`PAPER REAL` = datos reales con DINERO VIRTUAL**, nunca dinero real.
