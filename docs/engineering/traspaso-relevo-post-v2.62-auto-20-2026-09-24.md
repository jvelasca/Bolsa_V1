# Traspaso / relevo — post `v2.62-beta` (`AUTO-20` · material PAPER real + cierre de O1/O2)

**Para el siguiente agente.** Lee esto antes de tocar nada. Fuente de verdad de la fase:
[plan](./plan-v2-62-auto-20-material-paper-real-2026-09-24.md) ·
[audit-pack](./audit-pack-v2-62-auto-20-material-paper-real-2026-09-24.md) ·
[arranque del auditor](./arranque-auditor-v2.62-auto-20-material-paper-real-2026-09-24.md).

## 1. Dónde estamos

* **`v2.62-beta` (`1.87.0-beta`)** sellada. Base de auditoría: `f55e6921` (cierre de `v2.61-beta`).
* `AUTO-20` cierra las **dos observaciones P3** de la auditoría de `v2.61-beta` y **pone el material
  PAPER real** al alcance del instrumento de calibración.
* El **reparto no se movió**: `auto18-v1` / `auto15-v1`; **sin migración**.

## 2. Qué se hizo (y por qué)

| Pieza | Qué cambia |
|---|---|
| **O1 cerrado** | Una versión cuyos ciclos **no tienen ningún R medible** ya no desaparece en silencio: sale `unmeasured_r:<version>`. Las filas sin versión salen como `unversioned_cycles`. |
| **O2 cerrado** | `walkForwardEfficiency` se calcula SOLO sobre pliegues **emparejados** (IS y OOS a la vez); se publican `foldCount`/`isFoldCount`/`oosFoldCount`/`pairedFoldCount`. |
| **Sello subido** | `CALIBRATION_METHOD`: `walk_forward_calibration_v1` → **`…_v2`** (la lectura cambió; el sello lo declara). |
| **Material con riesgo** | `adaptive_instrument_cycles` (público) expone el material CON riesgo por la MISMA costura que el informe (`_cycles_with_risk`). |
| **Exportador** | `apps/api-python/scripts/paper_cycles_export.py`: fills durables + reservas + régimen → JSON del instrumento. |

**Por qué O1 se cerró solo en la calibración**: el replay (`statistical_oos_v1`) es el **contrato
sellado** de `AUTO-19A` y no se toca. Si un futuro agente quiere cerrar O1 también en el replay,
tiene que **decidirlo explícitamente** (y subir `REPLAY_METHOD`), no colarlo.

## 3. Estado medido (compuertas)

* `ruff` limpio · `lint-imports` **4 kept / 0 broken** · `mypy` **499 ficheros, 0 errores**.
* Puros `packages/py/analytics` + `packages/py/application`: **3133 passed**.
* Mutaciones **M1–M168**: matriz completa, `0` sin fragmento, restauración byte a byte.
* Mutaciones nuevas **M165–M168** muerden (O1, O2 y material sin riesgo).

## 4. Huecos declarados (lo que ESTA fase NO cierra)

1. **El camino durable del exportador NO se ejercita end-to-end.** Está cableado sobre costuras ya
   selladas y pasa `ruff`/`mypy`/sonda de bloqueo, pero no hay fixture PG que siembre fills +
   reservas reales para él. **Es la deuda número uno de la fase.**
2. **El material real sigue sin medirse.** El fixture del instrumento es **sintético**: la
   calibración publicada mide el instrumento, no la estrategia. Ejecutar el exportador sobre una
   cuenta real es un paso **operativo del propietario**, no de código.
3. **`P(R > 0)`, correlación entre estrategias y current-regime gating** siguen fuera de alcance.

## 5. Ficheros clave

* `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_calibration.py` — O1 (notas) y
  O2 (`_aggregate`), sello del método.
* `packages/py/application/src/bolsa_application/auto_self_evaluation_feed.py` — `adaptive_instrument_cycles`.
* `apps/api-python/scripts/paper_cycles_export.py` — exportador (I/O).
* `apps/api-python/scripts/v2_44_mutation_audit.py` — M165–M168.

## 6. Cómo re-verificar en frío

```powershell
uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml
uv run --no-sync lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent
uv run --no-sync pytest packages/py/analytics/tests packages/py/application/tests -q
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py M165 M166 M167 M168
```

## 7. Reglas de la casa que siguen vigentes

* **Lo que no se midió se declara** — nunca un veredicto ni un cero inventado.
* **Un solo productor por medida** — sin segundos caminos que puedan divergir en silencio.
* **Nada de evidencia mueve el reparto** — el sello `auto18-v1` no se toca sin fase propia.
