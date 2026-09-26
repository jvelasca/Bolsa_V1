# Plan de fase — V2.75 / `AUTO-MATERIAL-3`: EVIDENCE READY (muestra acumulada por el productor)

> **AsOf:** 2026-09-26 · **Bump:** `1.99.0-beta` → **`2.00.0-beta`** · **Base:** `v2.74-beta`
> **Alembic head:** `046_fill_reference_mid` (**SIN migración**) · **Freeze intacto**
> (`auto_simulation_worker.py` no se toca) · **Reparto congelado** (`auto18-v1` / `auto15-v1`).
> **Naturaleza:** fase de **acumulación de muestra**, no de decisión. El instrumento no cambia.

## 1. Por qué esta fase

`v2.74` dejó el bloqueo del productor resuelto en **estructura**: el camino AUTO 2.0 acuña
`cycle_id`, reservas con denominador, salidas con `cycle_id`, ciclos cerrados y R medible — pero solo
UN ciclo, y `EVIDENCE_READY` exige `≥32` ciclos medibles por estrategia. La fase anterior lo declaró
explícitamente: «el bloqueante ya no es de CÓDIGO del productor, es de **MUESTRA**». `V2.75` ataca
esa muestra **sin tocar el umbral**.

## 2. Objetivo y criterio de salida

1. **Acumular `≥32` ciclos medibles por estrategia** sobre una **cuenta PAPER nueva**, conduciendo el
   camino REAL (`AutoSimRuntime` → `worker.real_turn`) con el decider determinista y `price_script`.
2. Pasar el gate `PAPER MATERIAL READINESS` de `PRODUCER_READY` a **`EVIDENCE_READY`** sin rebajar
   `min cycles` / `min R` / `folds` / `min_episodes`.
3. Correr **`AUTO-22`** (`auto_evidence_run.py`) sobre ese material ⇒ bundle inmutable de 3 niveles.
4. Correr **`AUTO-23`** (`auto_evidence_validate.py`) ⇒ barrido P(R>0) vs N, correlación por cubos y
   estabilidad por régimen.
5. **Declarar con honestidad** lo que la muestra NO permite cerrar (P3-2 / P3-3) y por qué.

## 3. Entregables

| Entregable | Ruta |
|---|---|
| Harness de acumulación | `apps/api-python/scripts/v2_75_paper_sample_accumulation.py` |
| Evidencia de la muestra | `docs/engineering/evidencia-sample-accumulation-v2.75-2026-09-26.txt` |
| Evidencia AUTO-22 | `docs/engineering/evidencia-auto22-run-v2.75-2026-09-26.txt` |
| Evidencia AUTO-23 | `docs/engineering/evidencia-auto23-validation-v2.75-2026-09-26.txt` |
| Audit-pack | `docs/engineering/audit-pack-v2-75-auto-material-3-evidence-ready-2026-09-26.md` |
| Arranque del auditor | `docs/engineering/arranque-auditor-v2-75-auto-material-3-evidence-ready-2026-09-26.md` |
| Arranque del agente siguiente | `docs/engineering/arranque-agente-v2-75-auto-material-3-evidence-ready-2026-09-26.md` |
| Relevo | `docs/engineering/traspaso-relevo-post-v2-75-auto-material-3-2026-09-26.md` |

## 4. El harness (qué hace y qué NO)

`v2_75_paper_sample_accumulation.py`:

- Siembra cuenta PAPER nueva + instrumento que **llena en ambos lados** (`buy` y `sell`) en la
  ventana de minutos del worker, + `EdgeReport` bajo la versión `v75-producer-orb-v1`.
- Encadena round-trips con **worker/engine NUEVO por round-trip** y **un DÍA distinto por round-trip**.
  Dos razones, ambas legítimas (no se desactiva ningún dedupe):
  - `_minute` (arranca en ~1 y avanza por turno) vuelve a la ventana donde el sondeo garantiza el
    fill; el `seed` del SIM es `minute * 100_003 + sum(ord(symbol)) % 9999` ⇒ fuera de esa ventana el
    fill es probabilístico (~13 % de fallo) y la entrada no se materializa.
  - La identidad de señal es por **barra diaria** (`sim_consumed_signals.bar_timestamp` = inicio del
    día): un día distinto por round-trip evita que el dedupe anti-repetición bloquee la entrada.
- Lee el material durable con **la MISMA pieza que el gate** (`build_paper_material_readiness`) y
  declara el veredicto. `exit 0` ⇔ `EVIDENCE_READY`; `exit 2` ⇔ no llega al mínimo.

**No hace** (reglas duras vigentes): no baja umbrales, no repara material, no rellena `cycle_id` ni
`reserved_risk`, no toca el histórico legacy, no reparte, no migra, no toca el freeze.

## 5. Resultado de la corrida (2026-09-26)

- **44** round-trips solicitados → **42** abiertos y cerrados → **42 ciclos medibles** ⇒
  `EVIDENCE_READY` (mínimo 32). Dos round-trips finales no cerraron (`failedAt: [42, 43]`).
- Gate CLI `--level evidence`: `exit 0`, sello `paper_material_readiness_v2`.
- Cuenta `40787fbdb2354f70a3aec5256`, instrumento `v75-sample-0000000038`, versión
  `v75-producer-orb-v1`.
- **AUTO-22**: bundle `evidence_runs/20260926T152807Z-70418d88/` (huella
  `sha256:70418d88…`), 42 ciclos, `P(R>0)=0.0000`, `Effective-N=1`, `Correlación = NO MEDIDO`.
- **AUTO-23**: `evidence_validations/20260926T152821Z-70418d88/`, barrido `{16,32,64}` (64
  `insufficient_measured_cycles`), correlación con **1 cubo activo** (⇒ sin pares), régimen
  `INCONCLUSIVE` (`episodes=1`).

## 6. Hallazgo central (declarado, no barrido)

**El gate de CANTIDAD se cruza; la DIVERSIDAD no.** El productor determinista cierra todos los
ciclos con R casi idéntico y **todos comparten bucket de calendario y episodio de régimen** (los
timestamps son de reloj real del mismo día; el régimen es `BULL_TREND` fijo). Consecuencia honesta:

- `P3-2` (correlación por cubos) y `P3-3` (`P(R>0)` vs N) **siguen ABIERTAS**: el instrumento queda
  ejercitado, pero exige **material PAPER REAL de mercado** repartido en `≥4` cubos y `≥2` episodios.
- El material de esta fase es **PAPER durable con precio guionizado**; `read_paper_material` lo
  etiqueta `paper_real` (material durable), lo que se **declara** para no confundirlo con una corrida
  sobre datos de mercado.

## 7. Invariantes que NO se mueven

- Umbrales (`min cycles` 32, `min R`, `folds` 3, `min_is` 8, `min_oos` 4, `min_episodes`): intactos.
- `ALLOCATION = none` (congelado): la evidencia **no reparte**.
- Sellos `auto18-v1` / `auto15-v1`: intactos. Migración: ninguna (head `046`).
- `evidence_runs/` y `evidence_validations/`: inmutables y **no versionados** (se reproducen).
