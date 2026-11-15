# ADR-051 — El dinero del ciclo: cuantización por fill

**Estado:** **Accepted — implementado en el árbol, release NO sellada.** Fija la política
`applied_per_fill_v1` (el `pnl` publicado de un ciclo es la suma de sus movimientos ya
cuantizados), conserva el FIFO exacto como magnitud de **atribución** (`pnlExact`), versiona la
identidad del hecho de settlement (`pnlPolicy` en el payload y en la clave de deduplicación) y
re-emite los cierres históricos con identidad nueva, sin `UPDATE` y sin `DELETE`.
**`Δ motor = 0`** · **`Δ decisión = 0`** · **`activationAllowed = false`**.
**Fecha:** 2026-11-15
**Contexto:** [Diagnóstico del residuo sub-céntimo](../engineering/diagnostico-residuo-subcentimo-2026-11-15.md) ·
[expediente del contrato](../engineering/contrato-dinero-ciclo-2026-11-15.md) ·
[verificación de ADR-050](../engineering/verificacion-adr-050-2026-11-14.md).
**Depende de:** [ADR-008](./008-investment-accounts-and-ledger.md) (ledger y `NUMERIC(18,6)`) ·
[ADR-021](./021-dia-d-reconciliation.md) (reconciliación) ·
[ADR-029](./029-order-proposal-decision-journal.md) (journal append-only) ·
[ADR-041](./041-operational-coherence.md) (coherencia operativa).
**NO depende de, ni modifica:** [ADR-050](./050-verificacion-periodica-estrategia.md).

**Afecta a:**
[`auto_self_evaluation_feed.py`](../../packages/py/application/src/bolsa_application/auto_self_evaluation_feed.py) ·
[`cycle_pnl_policy.py`](../../packages/py/application/src/bolsa_application/cycle_pnl_policy.py) ·
[`auto_operational_audit.py`](../../packages/py/application/src/bolsa_application/auto_operational_audit.py) ·
[`auto_operational_monitor.py`](../../packages/py/application/src/bolsa_application/auto_operational_monitor.py) ·
[`auto_chain_durable_reader.py`](../../packages/py/application/src/bolsa_application/auto_chain_durable_reader.py) ·
[`paper_evidence_reconciliation.py`](../../packages/py/application/src/bolsa_application/paper_evidence_reconciliation.py) ·
[`auto_worker_state.py`](../../apps/api-python/src/bolsa_api/background/auto_worker_state.py) ·
[`auto_worker_runtime.py`](../../apps/api-python/src/bolsa_api/background/auto_worker_runtime.py) ·
[`v2_103_reenvio_settlements_politica.py`](../../apps/api-python/scripts/v2_103_reenvio_settlements_politica.py).

---

## 1. El problema

El libro aplicado mueve `round6(q × p)` **fill a fill**: todas sus columnas monetarias son
`NUMERIC(18, 6)` (`ledger_entries.amount`, `transactions.total`, `accounts.cash`). El FIFO del
ciclo sumaba `(salida − entrada) × cantidad` en aritmética exacta (precio y cantidad a 6 dp, el
producto vive en 12) y solo se cuantizaba **al publicar**. La diferencia medida sobre un ciclo
real fue de `7,2e-7`, y su identidad es exacta:

```
libro − ciclo = Σ_i signo_i · ( round6(q_i·p_i) − q_i·p_i ),   signo = +1 venta / −1 compra
```

No era una fuga, ni una acumulación, ni contención: era el **punto donde se aplicaba el
quantum**. La pregunta que quedaba abierta no era técnica sino de contrato: ¿cuál es la magnitud
monetaria publicada de un ciclo?

## 2. Decisión

> **El `pnl` publicado de un ciclo es el dinero que sus fills movieron:**
> `Σ signo_i · round6(q_i·p_i)` con `ROUND_HALF_UP`. **El FIFO exacto no se elimina**: se
> conserva como `pnlExact` para atribución (qué compra casó con qué venta), coste y R, y para
> seguir demostrando la identidad del residuo.

Política: `applied_per_fill_v1`. La histórica —FIFO exacto cuantizado al publicar— se nombra
`fifo_exact_v0` y es lo que se lee cuando un hecho **no declara** política.

### 2.1 Lo que la decisión NO autoriza

- **No autoriza tolerar la diferencia.** La igualdad con el libro sigue siendo **exacta**; solo
  cambia el lado en el que se aplica el quantum. Una tolerancia `n × 5e-7` queda prohibida sin
  autorización expresa del propietario de la cadena de identidad y contabilidad.
- **No autoriza dos números sin dueño.** `pnl` es el dinero; `pnlExact` es atribución. Cada gate
  declara cuál usa y por qué. `pnlExact` nunca se publica como si fuera caja.
- **No autoriza reescribir el pasado.** El hecho anterior no se actualiza ni se borra: queda
  **superado** por uno nuevo con identidad distinta.
- **No autoriza sellar.** `activationAllowed = false`, sin `window:pin`, sin `window:freeze`, sin
  tag, `AUTO` sigue OFF.

## 3. Identidad del hecho durable

El settlement publica `pnlPolicy` en el payload y la clave de deduplicación incorpora la
política **solo cuando se declara**:

```
auto_cycle_settlement:{account}:{engine}:{cycle}                    ← sin política (histórica)
auto_cycle_settlement:{account}:{engine}:{cycle}:{pnl_policy}       ← con política
```

Sin política la clave queda **byte-idéntica** a la histórica: los hechos anteriores y sus
reintentos siguen colapsando por `ON CONFLICT (dedupe_key) DO NOTHING`. Con política es una
identidad nueva, que es exactamente lo que permite que la reemisión **no sea descartada** por el
hecho que viene a superar.

Consecuencia declarada: un ciclo reemitido tiene **dos hechos** en el spine. Todo lector debe
distinguir políticas o declarará un duplicado que no existe (ver §5).

## 4. Re-emisión histórica

Los ciclos cerrados con fills `APPLIED` y `cycle_id` se reconstruyen con la **misma** función de
dominio (`cycles_from_fills`), nunca con un segundo FIFO. Se clasifican en `{vigente,
solo_legacy, sin_settlement}` y el reenvío:

1. `--dry-run` por defecto: publica la clasificación y la cifra nueva frente a la histórica.
2. `--apply` hace **solo `INSERT`** del hecho nuevo. Nunca `UPDATE`, nunca `DELETE`, nunca sello.
3. Reejecutar es un no-op por la clave versionada.

## 5. Lectura policy-aware (imprescindible, no cosmética)

| Lector | Regla |
| --- | --- |
| Monitor operativo | elige el settlement de la política **vigente**; dos políticas distintas no son `duplicate_settlement_cycle`; solo-legacy ⇒ `PARTIAL` + `settlement_policy_stale`; convivencia ⇒ nota `settlement_policy_superseded` |
| `pnl_reconciliation` | compara solo hechos de la misma política; un settlement histórico da `reconciled = null` + `settlement_policy_stale` (nunca `false` por un cambio de política) |
| Evidencia PAPER | la reemisión supera al histórico (no es duplicado) y **el hecho superado no cuenta como evidencia** (`settlementsTotal` cuenta un cierre decisivo por ciclo): un par histórico+vigente no infla el total ni produce `settlement_without_closed_cycle`; un histórico aislado declara el hueco y **no reconcilia** |
| Recuperación de arranque | solo cuenta como «ya liquidado» el settlement de la política vigente; así reemite el que solo tiene el histórico |

`pnl_reconciliation` **sigue siendo consistencia de publicación, no conciliación independiente**:
las dos cifras derivan de la misma autoridad. Ese defecto tiene su propio expediente y no se
absorbe aquí.

## 6. Consecuencias

- **Δ medición ≠ 0.** El `pnl` publicado de un ciclo puede moverse en el 6.º decimal y, en un
  ciclo marginal, **cambiar de signo**. Es Δ medición correcto bajo A1 y queda declarado.
- **Δ motor = 0.** No se toca ningún umbral, ni la lógica de entrada/salida, ni el reparto de
  fills. `cycles_from_fills` ya era la única autoridad de cierre.
- **Δ decisión = 0.** Nada de esto se lee para decidir; produce y publica hechos.
- **Sin migración.** `pnlPolicy` vive en el JSONB del payload. No hay cambio de esquema.
- **La conciliación no gana independencia.** Sigue midiendo que la publicación no divergió.

## 7. Alternativas consideradas

| Salida | Qué hace | Veredicto |
| --- | --- | --- |
| **A1 — cuantizar en origen** (esta) | `pnl` = `Σ ± round6(q·p)`; FIFO exacto como atribución | **Elegida** |
| **A2 — publicar `pnlApplied` junto al exacto** | dos números del mismo ciclo | Descartada: deja dos dueños y una tolerancia implícita |
| **B — tolerar `n × 5e-7`** | relaja la igualdad | **Prohibida** sin autorización: deja de distinguir redondeo de fuga |

## 8. Límites declarados

1. **Transporte `float` del settlement** (defecto colateral 2 del diagnóstico): el valor de 6
   decimales sobrevive el round-trip en el rango razonable, pero el tipo no es el del dinero. No
   se corrige aquí.
2. **Conciliación de la misma autoridad** (defecto colateral 1): no se convierte en gate
   independiente. No se corrige aquí.
3. **Un ciclo marginal puede cambiar de signo** por el quantum. Es correcto bajo A1.
4. **El árbol no queda sellado.** La release sigue abierta a decisión del propietario.

## 9. Verificación

- [Nodo puro del quantum](../../packages/py/application/tests/test_cycle_pnl_quantum.py): identidad
  exacta, control negativo, reparto y empate `HALF_UP`.
- [Nodo PG del residuo](../../apps/api-python/tests/test_auto_identity_chain_pnl_residual_pg.py):
  `libro − pnl` = **cero**; `libro − pnlExact` = **Σ residuos**.
- [Batería de identidad](../../apps/api-python/tests/test_auto_identity_chain_battery_pg.py) sin
  tocar: pasa por contrato, no por tolerancia.
- Evidencia de la re-emisión en
  [`docs/engineering/evidence/contrato-dinero-ciclo-2026-11-15/`](../engineering/evidence/contrato-dinero-ciclo-2026-11-15/README.md).
- [Verificación adversarial y dictamen de cierre](../engineering/verificacion-adversarial-adr-051-2026-11-15.md):
  **PASS técnico de A1, release NO sellada**. Incluye la corrección de agregación de PAPER (el hecho
  superado no cuenta como evidencia, en ambos órdenes de lectura) y la invalidación de la corrida
  obsoleta de las 10:52 UTC, cuyos cuatro fallos eran de un helper de pruebas sin `pnlPolicy`.
