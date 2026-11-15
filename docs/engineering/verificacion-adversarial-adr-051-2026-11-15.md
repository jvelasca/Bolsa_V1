# Verificación adversarial de ADR-051 — dictamen de cierre del contrato A1

**Fecha:** 2026-11-15 · **Árbol en la fecha del dictamen:** `main` = `ca0dcfe9` + ADR-051 sin
commitear · **Publicado en:** `5de1042b` · **Versión de
trabajo:** `2.11.193-beta` (bump sin cambio, pendiente de sello) · **Alembic head:**
`068_strategy_verifications` · **Naturaleza:** verificación de cierre del contrato de **dinero**
(ADR-051), con corrección de un defecto real encontrado por lectura adversarial. **No** introduce
cambios adicionales de código de producto: la corrección descrita en §3 ya está implementada en el
árbol de trabajo y forma parte de la evidencia evaluada. **No** añade migración, **no** sella ni
etiqueta, **no** enciende `AUTO`.

**Dictamen.** **PASS técnico del alcance A1.** La semántica de contabilización y conciliación queda
corregida y verificada; **no** queda certificada una release. La distinción es deliberada: A1
define qué número es el dinero del ciclo y cómo se lee un hecho superado, y eso está cerrado; la
publicación y la activación siguen siendo decisiones del propietario y **no** se autorizan aquí.

**`Δ motor = 0`** · **`Δ decisión = 0`** · **`Δ medición ≠ 0`** (declarado, 6.º decimal) ·
**`activationAllowed = false`**.

---

## 1 · El contrato A1, correctamente delimitado

La separación resuelve la discrepancia del residuo sub-céntimo sin introducir tolerancias
arbitrarias:

| Magnitud | Qué es | Dónde vive |
| --- | --- | --- |
| `pnl` | resultado **contable**: suma de los movimientos ya cuantizados, `Σ signo · round6(q·p)` con `ROUND_HALF_UP` | número **publicado** del ciclo y del settlement |
| `pnlExact` | resultado **matemático** del FIFO, sin cuantización por movimiento | **atribución** (qué compra casó con qué venta), coste y R |

La igualdad con el libro aplicado sigue siendo **exacta** (`libro − pnl = 0`) y el hueco no
desaparece: cambia de sitio y se sigue midiendo (`libro − pnlExact = Σ signo · (round6(q·p) − q·p)`).
Una tolerancia `n × 5e-7` queda prohibida sin autorización expresa: dejaría de distinguir redondeo
de fuga. Ver [ADR-051 §2](../adr/051-dinero-del-ciclo-cuantizacion-por-fill.md).

## 2 · Las tres decisiones de compatibilidad

Son las que permiten que el contrato nuevo conviva con el spine histórico sin reescribirlo:

1. **La clave de deduplicación histórica permanece idéntica cuando no existe política.**
   `auto_cycle_settlement:{account}:{engine}:{cycle}` es byte-idéntica a la anterior, así que los
   hechos previos y sus reintentos siguen colapsando por `ON CONFLICT (dedupe_key) DO NOTHING`.
   El hecho histórico no gana ni pierde identidad por este cambio.
2. **La política nueva forma parte de la identidad del settlement cuando está declarada.**
   `auto_cycle_settlement:{account}:{engine}:{cycle}:{pnl_policy}` es una identidad **nueva**, y eso
   es exactamente lo que permite que la reemisión **no** sea descartada por el hecho que viene a
   superar. `pnlPolicy` viaja en el payload JSONB del hecho.
3. **Un settlement exclusivamente histórico produce `PARTIAL` y `reconciled = null`, no un falso
   resultado negativo.** Su PnL se midió con otra aritmética; tolerar la diferencia reabriría el
   hueco que el contrato cerró, y declarar `false` convertiría un cambio de política en una
   divergencia inexistente. Se declara el hueco (`settlement_policy_stale`) hasta que se reemita.

## 3 · Corrección adversarial de PAPER — el hallazgo principal

**Seleccionar por política no era suficiente.** La selección del settlement vigente era correcta,
pero la **agregación** seguía contando los hechos superados. Con un ciclo reemitido (histórico +
vigente) el resultado era:

- `settlementsTotal = 2` frente a **1** ciclo cerrado conciliado;
- una contradicción **falsa** `settlement_without_closed_cycle:unkeyed:1`;
- el gate de cierre `reconciled == settlements` **inalcanzable por construcción**;
- y una nota `settlement_policy_superseded` que dependía del **orden de lectura** del spine.

La contradicción entre dos cierres y una conciliación era real, no cosmética: el contrato de
lectura (§5 de ADR-051) decía una cosa y el agregado hacía otra.

**Corrección.**
[`paper_evidence_reconciliation.py`](../../packages/py/application/src/bolsa_application/paper_evidence_reconciliation.py):

```python
    #: Hechos que NO cuentan como evidencia porque un hecho de la política vigente los supera.
    #: Se excluyen del total: si se contaran, ``settlementsTotal`` valdría 2 por ciclo reemitido
    #: y la igualdad ``reconciled == settlements`` (gate de cierre) no podría cumplirse nunca.
    superseded_settlements = 0
    ...
    settlements_total = len(settlement_rows) - superseded_settlements
```

El contador se alimenta en **ambas** ramas de orden —el vigente llegó primero y el histórico
llegó primero— de modo que la nota `settlement_policy_superseded` ya no depende del orden en que
el lector entrega las filas. Un ciclo con dos cierres de la **misma** política sigue siendo un
duplicado declarado; lo que deja de contarse es el hecho **superado**.

**Lo que la corrección NO hace:** no cambia la selección del vigente, no relaja ninguna igualdad,
no convierte la conciliación en gate independiente y no borra ni actualiza el hecho histórico —
el spine sigue append-only.

**Cobertura añadida.** Dos nodos fijan el par reemitido, además de los ya existentes:

| Nodo | Qué fija |
| --- | --- |
| [`test_a_reemitted_settlement_supersedes_the_legacy_one_instead_of_duplicating_it`](../../packages/py/application/tests/test_paper_evidence_reconciliation.py) | histórico → vigente: `settlements_total == 1`, `superseded` declarado, sin `duplicate_settlement_cycle` y sin cierre sin ciclo |
| [`test_the_superseded_note_does_not_depend_on_the_reading_order`](../../packages/py/application/tests/test_paper_evidence_reconciliation.py) | **orden inverso** (vigente → histórico): veredicto idéntico |
| [`test_a_superseded_settlement_pair_still_satisfies_the_closure_criterion`](../../packages/py/application/tests/test_paper_evidence_adapter.py) | extremo a extremo: 32 ciclos reemitidos y los **siete criterios** siguen `met`, `contradictions` vacío |

Es especialmente relevante el tercero: prueba que el gate de cierre sigue siendo alcanzable **con**
reemisión, que era justo lo que el defecto impedía.

## 4 · Evidencia

Cifras tal como se comunicaron para este cierre:

| Área | Resultado |
| --- | --- |
| `packages/py/application` | **3447 passed, 5 skipped** |
| Identidad / residuo / superación / reemisión (PG) | **12 passed** |
| Nodos nuevos de reemisión y superación (puros + PG) | **18 passed** |
| Evidencia PAPER + restart + forward + snapshot | **30 passed** |
| Golden day + monitor (PG) | **17 passed** |
| `ruff check packages/py apps/api-python` | **All checks passed** |
| `pnpm contract:check` | **OK** — `openapi.json` y `schema.d.ts` coinciden |
| BD histórica | **816/816** fills sin `cycle_id` |

Ninguno de estos gates se apoya en tolerancia: la igualdad dinero ↔ libro es exacta y el residuo se
mide contra `pnlExact`.

Evidencia cruda y línea base de la reemisión:
[`docs/engineering/evidence/contrato-dinero-ciclo-2026-11-15/`](./evidence/contrato-dinero-ciclo-2026-11-15/README.md).

## 5 · El límite del material histórico

La base histórica **no permite reconstruir ciclos**: no tiene `cycle_id`. Es correcto que
[`v2_103_reenvio_settlements_politica.py`](../../apps/api-python/scripts/v2_103_reenvio_settlements_politica.py)
**no** intente inferirlos ni modifique registros históricos. Con 816/816 fills sin atribución
durable, la corrida operativa es un **no-op declarado** (31 settlements, 0 con política, 0 ciclos
reconstruibles), no un fallo del CLI.

La reemisión controlada aporta la evidencia que el material real no puede dar:

| Paso | Medición |
| --- | --- |
| `--dry-run` | `solo_legacy = 1`, `toReemit = 1`, `delta = 0.000000`, sin escritura (`applied = null`) |
| `--apply` | `inserted = 1`, `skipped = 0`; el histórico queda **intacto** junto al nuevo |
| Reejecución | `inserted = 0`, `skipped = 1` — la clave policy-aware hace el reintento un no-op |
| Cadena tras el apply | `reconciled = true`, política vigente, `superseded = true` |

Un insertado, cero en la segunda ejecución y conservación del hecho histórico: eso es la
idempotencia medida, no supuesta.

## 6 · La notificación de las 10:52 UTC es obsoleta y no se contabiliza

La corrida iniciada a las **10:52 UTC** **no** debe contabilizarse como resultado de la implementación
final. Sus **cuatro** fallos procedían de un **helper de pruebas que no declaraba `pnlPolicy`**, no
del contrato. La corrección del helper y la ejecución completa posterior satisfactoria **sustituyen**
ese resultado.

No se abre una regresión por aquella notificación, y la cifra **no se cita** como estado actual.
Mismo criterio que la corrección del recuento «9» del expediente de ADR-050: un recuento caducado se
corrige por escrito, no se maquilla.

## 7 · Fronteras que este cierre mantiene

1. **Sin migración.** `pnlPolicy` vive en el JSONB del payload; el head sigue siendo
   `068_strategy_verifications`, que pertenece a ADR-050.
2. **Sin sello, sin tag.** No se ejecutan `window:pin` ni `window:freeze`; la release sigue abierta.
3. **`AUTO` sigue OFF.** Nada de este cierre autoriza operar ni activa nada.
4. **`Δ motor = 0` y `Δ decisión = 0`.** No se toca ningún umbral, ni la lógica de entrada/salida,
   ni el reparto de fills. `Δ medición ≠ 0` en el 6.º decimal, declarado.
5. **Los dos defectos colaterales siguen fuera de alcance.** La conciliación continúa siendo
   consistencia de publicación (misma autoridad, no gate independiente) y el settlement sigue
   transportando dinero como `float`.
6. **La ampliación del contrato tipado sigue fuera de alcance.** `pnlPolicy` viaja en el JSONB y en
   los tipos compartidos de estudio, pero **no** se añade al DTO generado de
   `/api/auto/paper-evidence`: un consumidor externo al producto sigue sin campo tipado para
   distinguir políticas.

## 8 · Dictamen y recomendación

**PASS técnico de A1.** ADR-051 queda implementado y verificado según la evidencia anterior.

**Recomendación.** Conservar el cierre como PASS técnico de A1, **sin ampliar ahora el trabajo** y
**sin convertirlo en autorización de publicación o activación**. La política contable queda definida;
la rentabilidad de la estrategia es una cuestión **independiente**, que exige evidencia longitudinal
suficiente y no se deduce de este contrato.

## 9 · Referencias

- [ADR-051 — El dinero del ciclo: cuantización por fill](../adr/051-dinero-del-ciclo-cuantizacion-por-fill.md)
- [Expediente del contrato del dinero del ciclo](./contrato-dinero-ciclo-2026-11-15.md)
- [Evidencia cruda de la reemisión](./evidence/contrato-dinero-ciclo-2026-11-15/README.md)
- [Diagnóstico del residuo sub-céntimo](./diagnostico-residuo-subcentimo-2026-11-15.md)
- [Verificación de ADR-050](./verificacion-adr-050-2026-11-14.md) (§3.1: el residuo, antes del contrato)
- Código: [`cycle_pnl_policy.py`](../../packages/py/application/src/bolsa_application/cycle_pnl_policy.py) ·
  [`paper_evidence_reconciliation.py`](../../packages/py/application/src/bolsa_application/paper_evidence_reconciliation.py) ·
  [`auto_operational_monitor.py`](../../packages/py/application/src/bolsa_application/auto_operational_monitor.py) ·
  [`auto_self_evaluation_feed.py`](../../packages/py/application/src/bolsa_application/auto_self_evaluation_feed.py) ·
  [`auto_chain_durable_reader.py`](../../packages/py/application/src/bolsa_application/auto_chain_durable_reader.py) ·
  [`auto_worker_state.py`](../../apps/api-python/src/bolsa_api/background/auto_worker_state.py) ·
  [`v2_103_reenvio_settlements_politica.py`](../../apps/api-python/scripts/v2_103_reenvio_settlements_politica.py)
