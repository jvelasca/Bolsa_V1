# Arranque del agente siguiente — post `v2.79` (`AUTO-MATERIAL-7`: OPERABILITY CENSUS)

> **AsOf:** 2026-09-27 · **Versión:** `2.04.0-beta` · **Tag:** `v2.79-beta` ·
> **Base:** `v2.78-beta` (`2.03.0-beta`) · **Alembic head:** `046_fill_reference_mid` (**SIN migración**).
> **Freeze:** `auto_simulation_worker.py` **intacto** · **Reparto:** `auto18-v1` / `auto15-v1`
> (`ALLOCATION = none`).

## 1. Estado

- **`AUTO-MATERIAL-7` / `v2.79` CERRADA.** Cierra `H-1` (MEDIUM), `H-2` (LOW) y `H-3` (LOW) de la
  auditoría externa de `v2.78-beta`, y con ello el caso general de `P3-6`: el censo de operabilidad es
  de **decisiones de ENTRADA** y los motivos de **gestión de posición** se publican por su canal
  propio (`positionEventByCode`), nunca como vetos.
- **Sin migración** y **sin tocar** el motor, el gobernador, `TOP_N`, el reparto ni ningún workflow.
- `test_market_operability.py`: **37 → 48 passed**. Matriz de mutaciones: **213 → 219**, todas muerden
  y restauran byte a byte.

## 2. Lo que un agente nuevo debe poder verificar en 5 minutos

```bash
uv run --no-sync python -m pytest packages/py/application/tests/test_market_operability.py -q   # 48 passed
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py M214 M215 M216 M217 M218 M219
```

Los seis rótulos nuevos deben salir con `rojo en:` **no vacío** y `restaurado byte a byte: si`.

## 3. Deuda abierta (no se cierra aquí)

- **`P3-2` / `P3-3` — 🔴 ABIERTAS.** Requieren el primer dataset PAPER real con **diversidad de
  mercado** (≥4 cubos de calendario y ≥2 episodios de régimen). Es el **paso operativo del
  propietario** (ver el [runbook de la ventana](./runbook-ventana-forward-v2.78-2026-09-27.md)).
- **`P3-5` — 🟠 ABIERTA.** `reserved_risk` sobrecargado (libro vivo vs evidencia histórica).
- **`OBS-5` — 🟡 DECLARADA.** `classify_veto_reasons` descarta conteos `<= 0` ante un mapping crudo;
  el camino real está a salvo por el parser del journal.
- **Deuda de auditoría `v2.73-beta`** — 🟡 ABIERTA (de proceso; cubierta por el linaje de `v2.74`).

## 4. Candidatos para la próxima fase (requieren ratificación del propietario)

1. **`AUTO-MATERIAL-8` — Operability Census sobre el journal durable.** Hoy el censo se lee del JSON
   del runner; una variante que lo lea del **journal durable** (`decision_journal_entries`) daría el
   mismo censo para cualquier corrida, sin depender del runner. *(Cuidado: hoy el journal durable
   guarda el evento rico; habría que filtrar por evento igual que aquí.)*
2. **`AUTO-MATERIAL-9` — Cierre de `P3-2`/`P3-3`.** No es una fase de código: es **correr la ventana**
   (≥4 días) con el runbook y leer `auto_evidence_run.py`/`auto_evidence_validate.py`.
3. **UI de lo que el journal ya publica** (candidato arrastrado desde `AUTO-16`): renderizar
   `vetoByBucket` + `positionEventByCode` en la UI existente.
4. **`OBS-5`**: endurecer el contrato de `classify_veto_reasons` (declarar el `<= 0` en el docstring o
   tipar la entrada).

## 5. Reglas duras que siguen vigentes

- **No** bajar `min cycles` / `min R` / `folds` / `min_is` / `min_oos` / `min_episodes`.
- **No** forzar `AUTO_ENGINE_SIM_V2_REGIME`; **no** backdatear `created_at`; **no** sobrescribir
  `evidence_runs/` ni `evidence_validations/`.
- **Forward, no replay.** Veredicto honesto `INCONCLUSIVE` / `NO MEDIDO` si el material sigue
  degenerado.
- El `freeze` del worker: **no** se toca.

## 6. Evidencia de la fase (cruda, en `docs/engineering/`)

| Fichero | Qué acredita |
|---|---|
| [`audit-pack-v2-79-…`](./audit-pack-v2-79-auto-material-7-operability-census-2026-09-27.md) | matriz afirmación→código→test por hallazgo |
| [`auditoria-v2-78-…`](./auditoria-v2-78-auto-material-6-operability-accounting-2026-09-27.md) | el veredicto que origina la fase (`H-1`/`H-2`/`H-3`) |
| `evidencia-matriz-mutaciones-v2.79-219-2026-09-27.txt` | 219/219, byte a byte, árbol intacto |
| [`runbook-ventana-forward-v2.78-…`](./runbook-ventana-forward-v2.78-2026-09-27.md) | la operación de la ventana ≥4 días |
