# Arranque del AUDITOR — `v2.64-beta` (`AUTO-20C` · Primera calibración PAPER (virtual) + perímetro + invariante)

Eres el auditor **independiente** de esta fase. Audítala **contra el tag `v2.64-beta`**, no contra el
resumen del autor. Contexto: [plan](./plan-v2-64-auto-20c-paper-virtual-2026-09-25.md) ·
[audit-pack](./audit-pack-v2-64-auto-20c-paper-virtual-2026-09-25.md) ·
[invariante](./invariante-paper-virtual-2026-09-25.md) ·
[origen (auditoría de `v2.63.1`)](./traspaso-relevo-post-v2.63-auto-20b-export-e2e-2026-09-25.md).

## 1. Qué se afirma (y qué NO)

**Se afirma:** el manifest de material declara su **perímetro** (versiones observadas frente a las pedidas,
fills excluidos por no tener versión o tener otra) **sin cambiar el universo medido**; la cadena produce un
**artefacto reproducible** (`AUTO20C_REAL_PAPER_REPORT.json`) y un **render** legible sin alterar stdout; y
toda la cadena declara el invariante **PAPER = dinero VIRTUAL** (venue `paper` o el exportador se bloquea).

**NO se afirma:** que la estrategia tenga edge; ni que el walk-forward con los umbrales por defecto haya
corrido sobre material real (exige ≥32 ciclos medidos por estrategia: es paso **operativo**); ni que la
huella sea una prueba criptográfica de procedencia; ni que `Current regime`/`Current evidence` estén
cubiertos (son `AUTO-21`, declarado como fuera de alcance).

## 2. Cómo empezar

```powershell
git checkout v2.64-beta
uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml
uv run --no-sync lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent
uv run --no-sync pytest packages/py/analytics/tests packages/py/application/tests -q
$env:AUTO20B_EXPORT_PG_REQUIRED="1"; uv run --no-sync pytest apps/api-python/tests/test_auto_v63_auto20b_export_e2e_pg.py apps/api-python/tests/test_auto_v64_auto20c_artifact.py apps/api-python/tests/test_auto_v63_auto20b_export_completeness.py -q -rs
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py M175 M176 M177 M178
```

## 3. Los puntos donde atacaría

1. **¿El perímetro cambia el universo?** El manifest debe **cuantificar** los fills sin versión / de otra
   versión SIN incluirlos: la huella y los conteos de ciclos deben ser los mismos que sin el agregado. Si
   `fillsExcludedNoVersion` entrara al material, la huella cambiaría y sería un fallo.
2. **¿Sin agregado del store el perímetro miente?** Debe quedar `None` ("no medido"), nunca `0` —un `0`
   diría "no hay excluidos", que es una afirmación que no se hizo.
3. **¿El render inventa veredictos?** Una pregunta ausente o un `walkForwardEfficiency=None` deben imprimir
   `INCONCLUSIVE`. Un `SUPPORTED`/`NOT_SUPPORTED` que el informe no emitió es **bloqueante**.
4. **¿El artefacto reinterpreta la medición?** `artifact["report"]` debe ser **idéntico** a
   `CalibrationReport.as_dict()`. Cualquier diferencia es un segundo productor encubierto.
5. **¿`--out`/`--render` cambian stdout?** Deben ser **aditivos**: la salida por stdout sin flags y con
   flags debe ser **byte-idéntica**. Si difiere, la compatibilidad declarada es falsa.
6. **¿La venue bloquea de verdad?** Con `BROKER_VENUE=live` el exportador debe salir **2** sin imprimir
   JSON. Si sellara un artefacto `paper_real` con material de otro carril, sería una mentira de procedencia.
7. **¿El sello del reparto se movió?** `ADAPTIVE_POLICY_VERSION` (`auto18-v1`) y `DATA_GATE_POLICY_VERSION`
   (`auto15-v1`) intactos; `governor.json` byte a byte; **sin migración** (head en `046_fill_reference_mid`).
8. **¿Se colaron cambios no declarados?** `auto_adaptive.py`, `auto_adaptive_data_gate.py`,
   `auto_simulation_worker.py`, `auto_adaptive_journal.py` y `auto_adaptive_replay.py`
   (`statistical_oos_v1`) **no** deben haber cambiado. El agregado del store debe ser **aditivo**: el worker
   no lo llama.

## 4. Trampas declaradas (no son fallos, están escritas)

* **El fixture del E2E es sintético**: mide la cadena de material, no el edge.
* **El walk-forward real no se ejecuta**: exige ≥32 ciclos medidos por estrategia; es paso operativo (§6 del
  traspaso).
* **`Current regime`/`Current evidence` salen como `AUTO-21 (fuera de alcance)`**: es una **declaración** del
  hueco, no un número inventado.
* **El perímetro es metadata, no material**: que el manifest mencione `fillsExcluded*` no lo mete en la
  huella ni en el informe de calibración.
* **`materialOrigin` es obligatorio**: si un test o caller no lo declara, falla por diseño; no hay valor por
  defecto que pueda mislabelar un fixture como material real.

## 5. Qué entregar

Un veredicto con lo **verificado** (comando y salida), los **hallazgos** con severidad y lo que la fase
**no** cubre. Si un punto del §3 no lo pudiste romper, dilo — eso también es resultado.
