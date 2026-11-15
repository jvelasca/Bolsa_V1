# Expediente del contrato del dinero del ciclo — A1, re-emisión y límites

**Fecha:** 2026-11-15 · **Árbol:** `main` + ADR-050 sin commitear · **Versión de trabajo:**
`2.11.193-beta` · **Alembic head:** `068_strategy_verifications` (**sin migración nueva**) ·
**Naturaleza:** implementación del contrato **A1** decidido por el propietario de la cadena de
identidad y contabilidad sobre el [diagnóstico del residuo
sub-céntimo](./diagnostico-residuo-subcentimo-2026-11-15.md). **Release NO sellada.**

**ADR:** [ADR-051](../adr/051-dinero-del-ciclo-cuantizacion-por-fill.md).

---

## 1 · Qué se decidió y qué se ejecutó

| Decisión | Ejecución |
| --- | --- |
| **A1 — persistencia por fill** | `cycles_from_fills` publica `pnl = Σ signo · round6(q·p)` con `ROUND_HALF_UP` y conserva el FIFO exacto en `pnlExact` |
| **Política declarada** | constante `applied_per_fill_v1` en [`cycle_pnl_policy.py`](../../packages/py/application/src/bolsa_application/cycle_pnl_policy.py); la histórica se nombra `fifo_exact_v0` y es lo que se lee cuando el hecho no declara nada |
| **Reemisión con identidad nueva** | `pnlPolicy` en el payload del settlement y `:{policy}` en la clave de deduplicación; el hecho anterior **no** se toca |
| **Lectores policy-aware** | monitor, `pnl_reconciliation`, evidencia PAPER y lector de recuperación |
| **Alcance: solo el quantum** | los dos defectos colaterales del diagnóstico quedan **declarados y sin absorber** (§4) |
| **Sin migración, sin sello, sin tag** | `pnlPolicy` vive en JSONB; `AUTO` sigue OFF; ADR-050 intacto |

## 2 · La aritmética, con las cifras medidas

Ciclo real del nodo de identidad (libro plano, 147.000000 de cantidad por lado):

| Lado | Cantidad | Precio | `q·p` | `round6(q·p)` | Residuo con signo |
| --- | --- | --- | --- | --- | --- |
| buy | 100.000000 | 100.075500 | 10007.550000000000 | 10007.550000 | 0 |
| buy | 47.000000 | 100.118300 | 4705.560100000000 | 4705.560100 | 0 |
| sell | 73.500000 | 99.928100 | 7344.715350000000 | 7344.715350 | 0 |
| sell | 34.545000 | 99.875000 | 3450.181875000000 | 3450.181875 | 0 |
| sell | 17.140200 | 99.842800 | 1711.325560560000 | 1711.325561 | **+0.00000044** |
| sell | 21.814800 | 99.823900 | 2177.638413720000 | 2177.638414 | **+0.00000028** |

```
exacto (pnlExact) = -29.248900720000
libro             = -29.248900
Σ residuos        = +0.00000072

antes:  libro − pnl  = +0.00000072   (el nodo rojo exigía cero y no podía darlo)
ahora:  libro − pnl  =  0            (el publicado es el del libro)
        libro − exacto = Σ residuos  (el hueco sigue siendo exactamente medible)
```

**El hueco no desaparece: cambia de sitio.** Pasa de estar entre el libro y el número publicado a
estar entre el número publicado y la magnitud de atribución, donde se puede demostrar que es
cuantización y no fuga.

## 3 · Cambios por capa

### 3.1 Dominio puro

- `pnl` = dinero aplicado (`ROUND_HALF_UP` **por movimiento emparejado**), `pnlExact` = FIFO
  exacto, `pnlPolicy` = política declarada. Las filas sin `cycle_id` (legacy, sin identidad de
  dinero) aplican el quantum **por emparejamiento** y lo declaran en el docstring.
- La cantidad que se cuantiza es la **emparejada**, no la del fill: una venta que el FIFO descarta
  por no tener contrapartida no fabrica dinero.
- Identidad algebraica resultante, con libro plano:
  `pnl = pnlExact + Σ signo · (round6(m·p) − m·p)`, donde `m` es la cantidad emparejada.

### 3.2 Hecho de settlement

- `build_cycle_settlement_entry(..., pnl_policy=...)` añade `pnlPolicy` **solo si se aporta**;
  sin política el payload es byte-idéntico al histórico.
- `durable_fact_dedupe_key(..., pnl_policy=...)` versiona la clave **solo** del settlement y
  **solo** cuando hay política. El guardián de 160 bytes y la identidad histórica no cambian.
- Los productores (`_v2_journal_cycle_settlement`, recuperación de arranque) pasan la política y
  `_v2_cycle_pnl` devuelve `Decimal` (el `float` del payload sigue: defecto 2 fuera de alcance).

### 3.3 Lectura

- **Monitor**: selecciona por política. Solo-legacy ⇒ `SETTLEMENT` `PARTIAL` +
  `settlement_policy_stale` (nunca `reached` limpio). Convivencia ⇒ se lee el vigente y se declara
  `settlement_policy_superseded`. Dos hechos de la MISMA política siguen siendo duplicado.
- **`pnl_reconciliation`**: publica `cycleExactPnl`, `policy`, `settlementPolicy`, `superseded` y
  `notes`; un settlement histórico da `reconciled = null`, no `false`.
- **Evidencia PAPER**: la reemisión supera al histórico (no es duplicado) y el hecho superado **no
  cuenta como evidencia** (`settlementsTotal` mide un cierre decisivo por ciclo), de modo que el par
  histórico+vigente no produce `settlement_without_closed_cycle` ni deja inalcanzable el gate
  `reconciled == settlements`; un histórico aislado declara `settlement_policy_stale` y **no
  reconcilia**.
- **Recuperación**: `build_durable_fact_cycle_reader` solo cuenta como liquidado el settlement de
  la política vigente, de modo que el arranque rellena el hueco de los ciclos legacy.
- **Corrección colateral mínima (declarada)**: el drill-down del monitor por `cycleId` publicaba el
  ciclo DOS veces cuando tenía cierre y fills (la reconstrucción del orden no lo marcaba como
  visto). Ahora `seen` se inicializa con el ciclo pedido: una sola fila, mismo contenido. Es un
  defecto de lectura, no de decisión.

## 4 · Frontera explícita de los dos defectos colaterales

No se absorben en este cambio. Cada uno queda con su contrato pendiente:

1. **`pnl_reconciliation` es consistencia de publicación, no conciliación independiente.** Las dos
   cifras (cierre y settlement) derivan de la misma autoridad. El gate ahora lo **dice** en su
   docstring y publica la política; sigue sin contrastar contra el libro aplicado. Un gate
   independiente exige decidir qué fuente manda y cómo se lee sin un segundo FIFO.
2. **El settlement transporta dinero como `float`.** `_number()` normaliza a `float` y el
   round-trip de 6 decimales sobrevive en el rango razonable, pero el tipo no es el del dinero. La
   corrección exige tocar el contrato del payload y a todos sus lectores; no es el quantum.

## 5 · Límites declarados

1. **Δ medición ≠ 0**: el `pnl` publicado puede moverse en el 6.º decimal y un ciclo marginal puede
   cambiar de signo. Es correcto bajo A1 y no se compensa.
2. **Δ motor = 0 / Δ decisión = 0**: no se toca ningún umbral ni la lógica de entrada/salida.
3. **Dos hechos por ciclo reemitido**: cualquier lector externo que no distinga política verá un
   duplicado. Los lectores del producto ya lo distinguen; la verificación independiente lo comprueba.
4. **Legacy sin `cycle_id`**: no tiene identidad de dinero; su quantum es por emparejamiento y así
   se declara. No se le atribuye una caja que no tiene.
5. **Sin migración, sin sello, sin tag.** `AUTO` OFF.
6. **La BD local no tiene historia reemisible**: 816/816 fills sin `cycle_id` y 31 settlements sin
   política. La corrida operativa es un no-op declarado; el `apply` se certifica en escenario
   controlado y en los nodos PG (§6 y la evidencia cruda).

## 6 · Verificación

| Gate | Qué afirma |
| --- | --- |
| `test_cycle_pnl_quantum.py` | identidad exacta, control negativo, reparto y empate `HALF_UP` vs `HALF_EVEN` |
| `test_auto_self_evaluation_feed.py` | forma de la fila y política declarada |
| `test_auto_operational_audit.py` | payload con/sin `pnlPolicy`, clave con/sin política |
| `test_auto_operational_monitor.py` · `test_auto_opportunity_identity.py` | selección por política, duplicado real vs superado, `stale` declarado |
| `test_paper_evidence_reconciliation.py` | superado no es duplicado; legacy aislado no reconcilia |
| `test_auto_chain_durable_reader.py` | `pnl_reconciliation` policy-aware |
| `test_auto_identity_chain_pnl_residual_pg.py` | `libro − pnl = 0`; `libro − pnlExact = Σ residuos` |
| `test_auto_identity_chain_battery_pg.py` | sin tocar: verde por contrato |
| `test_auto_settlement_policy_superseding_pg.py` | monitor elige la vigente, recuperación reemite el legacy, cadena declara `stale` |
| `test_v2_103_reenvio_settlements_politica.py` | clasificación pura, delta contra el histórico, dry-run por defecto |
| `test_v2_103_reenvio_settlements_politica_pg.py` | un hecho NUEVO por legacy, el anterior intacto, reejecutar no-op |

Recuentos de la corrida declarada: **3447 passed, 5 skipped** en `packages/py/application`; **12
passed** en la batería PG de identidad/residuo/superación/reemisión/estudio/hechos durables; **18
passed** en los nodos nuevos; **30 passed** en evidencia PAPER + restart + forward + snapshot
+ superación PG; **17 passed** en golden day + monitor PG; `ruff` y `contract:check` en verde.

La evidencia cruda de la reemisión vive en
[`evidence/contrato-dinero-ciclo-2026-11-15/README.md`](./evidence/contrato-dinero-ciclo-2026-11-15/README.md).

## 7 · Referencias

- [ADR-051 — El dinero del ciclo: cuantización por fill](../adr/051-dinero-del-ciclo-cuantizacion-por-fill.md)
- [Diagnóstico del residuo sub-céntimo](./diagnostico-residuo-subcentimo-2026-11-15.md) §7
- [Verificación de ADR-050](./verificacion-adr-050-2026-11-14.md) §3.1 y §7
- [`auto_self_evaluation_feed.py`](../../packages/py/application/src/bolsa_application/auto_self_evaluation_feed.py) ·
  [`cycle_pnl_policy.py`](../../packages/py/application/src/bolsa_application/cycle_pnl_policy.py) ·
  [`auto_operational_audit.py`](../../packages/py/application/src/bolsa_application/auto_operational_audit.py) ·
  [`auto_operational_monitor.py`](../../packages/py/application/src/bolsa_application/auto_operational_monitor.py) ·
  [`auto_chain_durable_reader.py`](../../packages/py/application/src/bolsa_application/auto_chain_durable_reader.py) ·
  [`paper_evidence_reconciliation.py`](../../packages/py/application/src/bolsa_application/paper_evidence_reconciliation.py)
