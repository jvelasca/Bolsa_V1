# Arranque auditor — V2.42.2 / AUTO-2 slice 2c: cierre con evidencia (`1.67.2-beta`)

**Qué auditas:** el **cierre de `AUTO-2`**. Este slice no añade capacidades de gestión nuevas: convierte en
**evidencia medible** lo que 2b dejó en "tests que pasan" y en **estructural** la afirmación de que con el
motor V2 ON la política de protección antigua no se lee. Es un slice **corto y de superficie pequeña** (5
ficheros de código/test + 1 script + 1 runner de dev + docs), así que la auditoría rentable es la del
**§9 del pack**: intentar romper la atribución de motivos, el "cero legacy" y la verificación de rutas.

**Pack:** [`audit-pack-v2.42.2-auto-2-slice-2c-2026-09-18.md`](./audit-pack-v2.42.2-auto-2-slice-2c-2026-09-18.md)

**Qué auditar exactamente:** tag anotado **`v2.42.2-beta`** _(commit y runs en el §8.1 del pack, al sellar)_.
`main` puede ir por delante sólo con docs.

**Contexto que NO tienes que re-auditar:** E1/E2/E3 y H-1..H-7 (slice 2b) ya se auditaron en
[`audit-pack-v2.42.1-auto-2-slice-2b-2026-09-17.md`](./audit-pack-v2.42.1-auto-2-slice-2b-2026-09-17.md).
Aquí basta comprobar que 2c **no** los degradó (las baterías completas van en el §8.2 del pack).

---

## 1. Orden de lectura (20–30 min)

1. **§1 y §6 del pack**: qué **afirma** y qué **no** afirma la versión. Si una afirmación no se sostiene con
   lo que leas después, ese es el hallazgo.
2. `packages/py/application/src/bolsa_application/auto_reason_codes.py` (`day_exit_reason`,
   `DAY_EXIT_REASON_UNDECLARED`): el **dueño único** de la traducción motivo → etiqueta del día.
3. `packages/py/application/src/bolsa_application/auto_daily_journal.py`: `SimJournalRow.reason`,
   `AutoDailyReport.exit_reasons`/`atr_sources`, `build_auto_daily_report` y `_sorted_counts`.
4. `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py`: `_emit(reason=...)`,
   `_v2_last_exit_label` (dónde se puebla y dónde se vacía), `atr_source_counts()` y el **restructure** de
   `auto_turn` (el `else` legacy detrás de `not self._v2_enabled`).
5. `apps/api-python/tests/test_auto_v2_golden_day_evidence.py` (el día completo, el sensor que explota y la
   medición de ATR) y `packages/py/application/tests/test_auto_daily_journal.py` (los 5 puros nuevos).
6. `apps/api-python/scripts/v2_42_2_golden_day_evidence.py` (evidencia reproducible; **sale ≠ 0** si el
   criterio no se cumple) y `scripts/verify/offline_ci_run_yaml.py` (medición local de CI **del YAML**).

## 2. Afirmaciones verificables (con su medida)

| #   | Afirmación                                                                   | Cómo la rompes                                                                        |
| --- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| A1  | La suma de motivos del día es exactamente el número de cierres               | Busca un cierre que **no** pase por la fila `position_close` del día                  |
| A2  | El motivo es el **decisorio** (stop-out ≠ salida por tesis)                  | Fuerza un stop con la tesis "rozada" y mira qué cuenta el día                         |
| A3  | Un cierre sin motivo declarado se cuenta `undeclared`                        | Quita la `reason` de una fila de cierre y comprueba que no se le atribuye `time_exit` |
| A4  | Con V2 ON la política legacy **no se evalúa**                                | Quita el `if self._v2_enabled` del restructure: el sensor del día debe **explotar**   |
| A5  | La procedencia del ATR se **mide**, no se inventa                            | Pide el reporte sin `atr_sources` y comprueba que queda **vacío**                     |
| A6  | El día golden ejerce los **tres** desenlaces y cierra el libro               | Comprueba que los tres cierres son por precio/reloj **reales** y no por un atajo      |
| A7  | La lista de tests de CI del slice es **ejecutable** (sin rutas inexistentes) | Corre `scripts/verify/offline_ci_run_yaml.py` en los dos jobs y mira `exit`           |

## 3. Comandos listos

```bash
# estático (invocación EXACTA de CI)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
             packages/py/application/src apps/api-python/src \
             --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# suites del slice
uv run pytest packages/py/application/tests/test_auto_daily_journal.py \
              apps/api-python/tests/test_auto_v2_golden_day_evidence.py -q

# evidencia del día (JSON) y su self-check
uv run python apps/api-python/scripts/v2_42_2_golden_day_evidence.py --out /tmp/dia.json; echo "exit=$?"

# bloques offline de CI tal cual están en el YAML (+ verificación de rutas)
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores
```

**Matriz de mutación (7 mutaciones, 7 rojos)**: §4 del pack. El script que la orquesta no se versiona
(aplica/corre/**revierte verificando contenido exacto**); si quieres rehacerla, empieza por las tres que más
valor tienen: `day_exit_reason` mal mapeado, la fila de cierre sin motivo, y el `else` legacy sin el guard.

## 4. Preguntas abiertas que deberías intentar romper

1. **`_v2_last_exit_label` rancio**: se vacía al inicio de cada `auto_turn`; ¿basta eso? ¿Qué pasa si en el
   **mismo** turno la posición se gestiona (etiqueta puesta) y además el decider vende por su cuenta?
2. **Ventas parciales**: un cierre puede materializarse en dos ventas; ¿el día cuenta **una** salida o dos?
   ¿La etiqueta es la misma en las dos filas?
3. **`structural_stop` fuera del journal rico**: el test exige que el stop-out **no** aparezca como motivo de
   gestión. ¿Es una afirmación del diseño o un efecto colateral del camino que escogió el test?
4. **`undeclared` como cajón de sastre**: ¿podría esconder un motivo real perdido por el camino (un
   `primary_reason` que no llega al plan)? Si sí, ¿hay algún contador que lo delate?
5. **El atajo declarado de `BBB`**: el test escribe `invalidation_price` a mano (`replace`) porque hoy
   **ningún productor manda el nivel al `TradePlan`**. ¿Es aceptable como evidencia del día o debería el
   slice haber cableado el productor? (El pack lo declara; decide si es deuda o defecto).
6. **Coste oculto**: ¿el restructure cambió algún comportamiento del camino **legacy** (`V2=0`) más allá de
   lo declarado en el §5.4 del pack (SELL con `qty <= 0` que ya no emite `hold_no_op`)?

## 5. Qué NO es un hallazgo (declarado antes de que lo encuentres)

- Que el día evidencial sea **hermético** (sin PG ni feed de mercado): es una decisión de diseño declarada en
  el §1.2/§6 del pack. Lo que sí sería hallazgo es que el pack lo presentara como sesión real.
- Que la `ProtectionConfig` **se siga construyendo** en el constructor: el criterio de salida habla de
  **lecturas en el camino V2**, no de construcción (el camino `V2=0` debe conservar `v2.39.x`).
- Que el **veto de ATR esté OFF**: D3 pedía medir primero, y el flip es del owner.
- Que **PG real** no se haya medido en la máquina del autor: se declara y lo certifica CI.
- Que `REGIME_EXIT`/`RISK_EXIT` no existan como eventos del FSM: llegan con `AUTO-3` (gobernador).
