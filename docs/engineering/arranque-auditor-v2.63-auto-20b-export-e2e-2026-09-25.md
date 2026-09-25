# Arranque del AUDITOR — `v2.63-beta` (`AUTO-20B` · Export E2E + oráculo same-material)

Eres el auditor **independiente** de esta fase. Audítala **contra el tag**, no contra el resumen del
autor. Contexto: [plan](./plan-v2-63-auto-20b-export-e2e-2026-09-25.md) ·
[audit-pack](./audit-pack-v2-63-auto-20b-export-e2e-2026-09-25.md) ·
[origen (auditoría de `v2.62`)](./auditoria-v2-62-auto-20-material-paper-real-2026-09-24.md).

## 1. Qué se afirma (y qué NO)

**Se afirma:** el camino durable del exportador está **ejercitado end-to-end contra PostgreSQL real**
(fills + reservas + régimen → JSON → calibración) con cardinalidad verificada contra un **oráculo
independiente**; la lectura de reservas ya **no puede truncarse en silencio** (`--limit` es tamaño de
página y sin completitud probada sale **2**); y el informe de calibración declara el **universo medido**
(`material` + huella) sin cambiar ninguna medición.

**NO se afirma:** que la estrategia tenga edge; ni que el walk-forward con los umbrales por defecto
haya corrido sobre material real (exige ≥32 ciclos medidos por estrategia: es paso **operativo**); ni
que la huella sea una prueba criptográfica de procedencia (es un sello de igualdad de universo).

## 2. Cómo empezar

```powershell
git checkout v2.63-beta
uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml
uv run --no-sync lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent
uv run --no-sync pytest packages/py/analytics/tests packages/py/application/tests -q
$env:AUTO20B_EXPORT_PG_REQUIRED="1"; uv run --no-sync pytest apps/api-python/tests/test_auto_v63_auto20b_export_e2e_pg.py -q -rs
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py M169 M170 M171 M172 M173 M174
```

## 3. Los siete puntos donde atacaría

1. **¿La completitud es real o solo "una página más"?** Un `--limit` pequeño con reservas de sobra
   debe recuperar **todas** y declarar `riskReadSaturated == false`. Fuerza una página que satura sin
   progreso (doble que ignora `offset`) y comprueba que el exportador sale **2** sin imprimir JSON.
2. **¿El oráculo es independiente o es el producto otra vez?** El fixture se construye **desde las
   especificaciones sembradas** (12/9/3, 8/8, 5/0, 1 sin versión, 2 regímenes), no desde el manifest.
   Si el conteo del manifest se "explica" con la salida del propio exportador, el oráculo no vale.
3. **¿El same-material cruza la frontera del JSON?** El informe durable (`build_auto_self_evaluation`)
   y el material del calibrador deben describir el **mismo** conjunto de `cycleId`, con el mismo
   `riskAmount`/`costApplied`/`regime`/`strategyVersion` — y el informe recalculado **desde el JSON
   exportado** debe salir **idéntico** al durable.
4. **¿La huella distingue universos y aguanta el `json.dumps`?** `Decimal("100.000000")`, `100` y la
   cadena `"100.000000"` deben dar el **mismo** sello; cambiar `strategyVersion`/`regime`/`riskAmount`
   debe cambiar el sello; un `cycleId` que **parece** un número (`"2.0"` vs `"2"`) **no** se normaliza.
5. **¿El bloque `material` es opcional de verdad?** Sin manifest, `as_dict()` **no** debe traer la
   clave: byte-idéntico al informe ya auditado, con `CALIBRATION_METHOD` intacto
   (`walk_forward_calibration_v2`). Con manifest, la medición (celdas, agregados, notas) no puede
   cambiar.
6. **¿El sello del reparto se movió?** `ADAPTIVE_POLICY_VERSION` (`auto18-v1`) y
   `DATA_GATE_POLICY_VERSION` (`auto15-v1`) intactos; `governor.json` byte a byte; **sin migración**
   (Alembic head sigue en `046_fill_reference_mid`).
7. **¿Se colaron cambios no declarados?** `auto_adaptive.py`, `auto_adaptive_data_gate.py`,
   `auto_simulation_worker.py`, `auto_adaptive_journal.py` y `auto_adaptive_replay.py`
   (`statistical_oos_v1`) **no** deben haber cambiado. El `offset` del store debe ser **aditivo**: el
   worker llama sin `offset` y su lectura debe ser byte-idéntica.

## 4. Trampas declaradas (no son fallos, están escritas)

* **El fixture del E2E es sintético**: mide la **cadena de material**, no el edge de una estrategia.
* **El walk-forward real no se ejecuta**: los umbrales por defecto exigen ≥32 ciclos medidos por
  estrategia. Es paso operativo del propietario, declarado en el plan (§8).
* **`material` es metadata de ENTRADA**: no mueve ninguna medición ni el sello del instrumento. Que el
  informe `v2` con y sin `material` difiera **solo** en esa clave es lo buscado.
* **Los puros del exportador viven en un fichero aparte** (`..._export_completeness.py`) para que el
  job offline los ejecute: el E2E `_pg.py` va en `--ignore` offline y se certifica en el job PG con
  gate fail-if-skipped. No lo leas como duplicación.

## 5. Qué entregar

Un veredicto con lo **verificado** (comando y salida), los **hallazgos** con severidad y lo que la fase
**no** cubre. Si un punto del §3 no lo pudiste romper, dilo — eso también es resultado.
