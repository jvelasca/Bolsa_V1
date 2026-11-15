# Diagnóstico del residuo sub-céntimo del P&L — cuantización por fill, no del ciclo

**Fecha:** 2026-11-15 · **Árbol en la fecha del diagnóstico:** `main` = `ca0dcfe9` + ADR-050 sin
commitear · **Publicado en:** `5de1042b` · **Versión de
trabajo:** `2.11.193-beta` · **Alembic head:** `068_strategy_verifications` (sin migración nueva) ·
**Naturaleza:** **diagnóstico**. No cambia código de producto, no relaja ninguna tolerancia, no toca
migraciones, no ejecuta ningún paso de sello. **Release no sellada.**

**Pregunta que cierra.** El único fallo de la suite Python sin causa raíz declarada afirmaba:

```
AssertionError: el P&L del ciclo debe cuadrar EXACTO con el libro aplicado:
   ciclo=-29.248900720000 libro=-29.248900
assert Decimal('-29.248901') == Decimal('-29.248900')
```

La diferencia es `7,2e-7`: menos de un quantum de `NUMERIC(18,6)`. La duda abierta era **qué
contrato se incumple**, y el dictamen de auditoría la formuló con precisión: si el contrato es
«igualdad exacta tras aplicar la precisión contable», el defecto está en la reconciliación; si
es «igualdad de los valores internos antes de cuantizar», está en la distribución de fills o en
la acumulación del ciclo.

**Respuesta.** Ninguna de las dos ubicaciones: el defecto está en **el punto donde se aplica el
quantum**. El libro redondea **por movimiento** (fill) y el ciclo suma exacto y solo se cuantiza
al publicar. La diferencia es exactamente la suma de esos redondeos individuales, y se mide aquí
fill a fill sobre el ciclo real.

---

## 1 · Lo que ya estaba medido y lo que faltaba

Medido antes de este expediente: falla determinista en aislamiento (2,20 s y 2,16 s), y pasó en
las corridas del 2026-11-14. No es contención de la BD.

Lo que faltaba era la **descomposición** del hueco. Declarar «menos de un quantum» es una
observación, no una causa: no distingue fuga de dinero de aritmética, y no dice dónde corregir.

---

## 2 · Reproducido y descompuesto (2026-11-15)

| Paso | Comando | Resultado |
| --- | --- | --- |
| Nodo rojo, sin tocarlo | `pytest apps/api-python/tests/test_auto_identity_chain_battery_pg.py::test_identity_chain_battery_complete_end_to_end_pg -q` | **1 failed** (2,15 s), mismo par |
| Nodo de diagnóstico nuevo | `pytest apps/api-python/tests/test_auto_identity_chain_pnl_residual_pg.py -q` | **1 passed** (~2,0 s) |
| Invariante puro | `pytest packages/py/application/tests/test_cycle_pnl_quantum.py -q` | **4 passed** (0,23 s) |

El nodo de diagnóstico conduce **el mismo ciclo productivo** que el nodo rojo (reutiliza
`_drive_cycle`/`_teardown` de la batería, mismo prefijo de instrumento determinista por día) y
descompone el hueco. Ciclo medido, `147.000000` de cantidad en cada lado, libro plano:

| Lado | Cantidad | Precio | `q·p` | `round6(q·p)` | Residuo con signo |
| --- | --- | --- | --- | --- | --- |
| buy | 100.000000 | 100.075500 | 10007.550000000000 | 10007.550000 | 0 |
| buy | 47.000000 | 100.118300 | 4705.560100000000 | 4705.560100 | 0 |
| sell | 73.500000 | 99.928100 | 7344.715350000000 | 7344.715350 | 0 |
| sell | 34.545000 | 99.875000 | 3450.181875000000 | 3450.181875 | 0 |
| sell | 17.140200 | 99.842800 | 1711.325560560000 | 1711.325561 | **+0.00000044** |
| sell | 21.814800 | 99.823900 | 2177.638413720000 | 2177.638414 | **+0.00000028** |

```
libro       = -29.248900
ciclo       = -29.248900720000   (settlement = -29.24890072)
libro − ciclo = +0.00000072  =  Σ residuos = 0.00000044 + 0.00000028
```

**El hueco son las dos ventas que no eran exactas a 6 decimales.** Las cuatro patas restantes
—incluidas las dos compras— tienen productos exactos al quantum y aportan cero. No hay ninguna
pérdida sin explicar.

---

## 3 · La identidad

Con el libro plano (toda la cantidad emparejada, que el nodo **exige** antes de afirmar nada)
el realizado del ciclo es algebraico y exacto:

```
ciclo = Σ ventas q·p − Σ compras q·p
libro = Σ ventas round6(q·p) − Σ compras round6(q·p)

libro − ciclo = Σ_i signo_i · ( round6(q_i·p_i) − q_i·p_i ),   signo = +1 venta / −1 compra
```

Los residuos son de cuantización **individual** y no se cancelan. Su cota es `n × 5e-7`, no un
quantum: por eso una tolerancia fija de «1 quantum sobre los totales» no es un criterio —el
nodo lo afirma explícitamente contra el número de fills.

**De dónde viene cada número.**

- Ciclo: FIFO de `cycles_from_fills` (`realized += (precio_salida − precio_entrada) × cantidad`)
  en [`auto_self_evaluation_feed.py`](../../packages/py/application/src/bolsa_application/auto_self_evaluation_feed.py).
  Sin cuantizar: precio y cantidad son 6 dp, el producto vive en 12. *(Estado diagnosticado; bajo
  ADR-051 el `pnl` publicado es el aplicado por fill y el FIFO exacto viaja como `pnlExact`.)*
- Libro: cada fill mueve `round6(q·p)` porque **todas** las columnas monetarias son
  `NUMERIC(18,6)` (`ledger_entries.amount`, `transactions.total`, `accounts.cash`). El arnés
  independiente lo replica así en
  [`applied_fill_equity.py`](../../apps/api-python/tests/applied_fill_equity.py) desde el
  incidente de equity de 2.57.
- El `SETTLEMENT` publica el mismo `pnl` del FIFO, sin cuantizar. *(Estado diagnosticado; bajo
  ADR-051 publica el aplicado y declara `pnlPolicy`.)*

---

## 4 · Qué NO es el defecto

1. **No es la distribución de fills.** El reparto decide *qué* residuos hay, no *si* hay hueco: lo
   que rompe la igualdad es que el quantum se aplique al movimiento y no al agregado.
2. **No es la acumulación del ciclo.** El FIFO sumaría exacto con cualquier orden; no pierde un
   dígito. El caso C del test puro lo fija con un ciclo cuyo P&L exacto es **cero** y cuyo libro,
   en cambio, no lo es.
3. **No es contención de la BD.** Reproduce en aislamiento, dos veces, con el mismo par.
4. **No es ADR-050.** Este árbol no toca `confirm/`, ni la ruta de revalidación de precio, ni la
   `067`; la `068` solo añade `strategy_verification_runs`.
5. **La fecha no es la causa, es la condición de visibilidad.** `_filling_instrument_id` elige el
   instrumento por día; de ahí sale el troceado y de ahí si algún producto tiene un séptimo
   decimal. Con precio y cantidad cuyo producto es exacto a 6 dp el hueco es 0 —el control
   negativo del test puro lo demuestra— y el nodo rojo pasaría sin haber cambiado nada. **La
   atribución del expediente anterior («es de fecha») describe cuándo aparece, no qué es.**

---

## 5 · Dos defectos colaterales que el arreglo deberá tocar

1. **La conciliación del producto da una garantía aparente.**
   [`pnl_reconciliation`](../../packages/py/application/src/bolsa_application/auto_chain_durable_reader.py)
   compara `CYCLE_CLOSED.pnl` contra `SETTLEMENT.pnl` — **dos derivados del mismo FIFO** — y
   cuantiza el total. Por eso `reconciled = True` mientras el libro discrepa: la aserción que
   falla no es la de ese gate. Un gate que solo se compara consigo mismo no mide nada.
   **No se ha cambiado**: el fix correcto exige decidir el contrato (§6), y el gate tendría que
   contrastar contra el libro aplicado o declarar la fuente independiente.
2. **El settlement publica dinero como `float`.**
   `build_cycle_settlement_entry` normaliza `pnl` con `_number()` → `float`
   ([`auto_operational_audit.py`](../../packages/py/application/src/bolsa_application/auto_operational_audit.py)),
   y el recuperador de hechos durables lo convierte antes a `float`
   ([`auto_simulation_worker.py`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py)).
   **No es la causa del hueco de `7,2e-7`** (ese viene del FIFO a 12 dp), pero es transporte de
   dinero en doble: un valor que necesita más de ~15-16 dígitos significativos deja de ser
   round-trip. El P&L de un ciclo cotiza en ese límite con carteras grandes.

---

## 6 · Contrato propuesto: **persistencia por fill**

Formulación para la decisión del propietario de la cadena de identidad y contabilidad:

> El dinero que se mueve es `round6(q × p)` **por fill**, porque es lo que el libro aplicado
> registra y lo que `cash` conserva. El resultado de un ciclo es, por tanto, la suma de los
> movimientos redondeados de sus fills. El FIFO exacto se conserva para **atribución** (qué
> compra casa con qué venta, `matched`), no como magnitud monetaria publicada.

Consecuencia declarada: dos cifras publicadas del mismo ciclo (una atribuible al emparejamiento y
otra al dinero) no pueden separarse más de lo que se separe un quantum por fill; el contrato elige
**una** y la otra se deriva de ella.

**Lo que este contrato NO autoriza:** tolerar la diferencia. La igualdad sigue siendo exacta, solo
cambia el lado en el que se aplica el quantum.

---

## 7 · Salidas posibles y decisión tomada

| Salida | Qué hace | Coste / impacto | Veredicto |
| --- | --- | --- | --- |
| **A1 — cuantizar el ciclo en origen** | El `pnl` del ciclo pasa a ser `Σ ± round6(q·p)` de sus fills; el FIFO se queda para atribución | Restaura la igualdad exacta con el libro y con el settlement. Mueve cifras publicadas en el 6.º decimal y cambia el `SETTLEMENT` ya sellado en runs antiguos (identidad nueva, no `UPDATE`) | **DECIDIDA E IMPLEMENTADA** |
| **A2 — publicar `pnlApplied` junto al exacto** | Se añade la magnitud cuantizada y la aserción compara contra ella | No rompe consumidores, pero publica dos números del mismo ciclo y obliga a declarar cuál manda en cada gate | Descartada: deja dos dueños y una tolerancia implícita |
| **B — tolerar `n × 5e-7`** | Relaja la igualdad | Convierte la aserción en ruido; deja de distinguir redondeo de fuga | **Prohibida sin autorización expresa del propietario de la cadena** |

**Decisión (2026-11-15, propietario de la cadena de identidad y contabilidad): A1 + reemisión
histórica con identidad nueva.** El contrato vive en
[ADR-051](../adr/051-dinero-del-ciclo-cuantizacion-por-fill.md) y su expediente en
[contrato-dinero-ciclo-2026-11-15.md](./contrato-dinero-ciclo-2026-11-15.md).

Lo implementado: `pnl` publicado = `Σ signo · round6(q·p)` con `ROUND_HALF_UP`; `pnlExact` = FIFO
exacto; `pnlPolicy` en el hecho de settlement y en la clave de deduplicación (versión solo cuando
se declara); lectores policy-aware; reemisión por `v2_103` (dry-run por defecto, `--apply` solo
`INSERT`). Sin migración, sin sello, sin tag, `AUTO` OFF. Δ medición ≠ 0 declarado; Δ motor = 0;
Δ decisión = 0.

Los dos defectos colaterales de §5 **no se absorben**: quedan declarados con su propio contrato
pendiente.

Ninguna de las tres salidas pertenece a ADR-050, que sigue intacto.

---

## 8 · Qué demuestra y qué no

- **Demuestra** el mecanismo (identidad exacta, medida sobre datos reales y sobre aritmética
  pura) y que el hueco no oculta dinero.
- **No demuestra** que el contrato deba ser A1: eso es una decisión de producto. Tampoco
  demuestra que el `float` del settlement cause un fallo hoy; sí que el tipo no es el del dinero.
- **No cambia** el nodo rojo: sigue rojo, con las mismas cifras. El propósito de los dos nodos
  nuevos es que el rojo deje de ser un número huérfano.

---

## 9 · Fronteras respetadas por el diagnóstico

*(La implementación posterior de A1 vive en [ADR-051](../adr/051-dinero-del-ciclo-cuantizacion-por-fill.md)
y en el [expediente del contrato](./contrato-dinero-ciclo-2026-11-15.md); lo de abajo describe lo
que este diagnóstico no tocó mientras medía.)*

1. No se modificó `auto_self_evaluation_feed.py`, `auto_chain_durable_reader.py` ni los
   productores de `SETTLEMENT`.
2. No se relajó la aserción del nodo rojo, ni `_MONEY`, ni ninguna tolerancia del producto.
3. No se tocaron `067`/`068`, la allowlist de drift, `opening_gate_seed` ni la banda de
   revalidación de precio.
4. No se ejecutaron `window:pin`, `window:freeze` ni se creó tag.
5. El recuento de la suite global sigue citándose como está (`6 failed, 5306 passed, 7 skipped`)
   y **sube en 1 nodo** por el diagnóstico nuevo; el nodo puro no toca la BD.

---

## 10 · Referencias

- [ADR-050](../adr/050-verificacion-periodica-estrategia.md)
- [Verificación de ADR-050: remedición, atribución de fallos y checklist de sello](./verificacion-adr-050-2026-11-14.md) §3.1 y §7
- Código citado:
  [`auto_self_evaluation_feed.py`](../../packages/py/application/src/bolsa_application/auto_self_evaluation_feed.py) ·
  [`auto_chain_durable_reader.py`](../../packages/py/application/src/bolsa_application/auto_chain_durable_reader.py) ·
  [`auto_operational_audit.py`](../../packages/py/application/src/bolsa_application/auto_operational_audit.py) ·
  [`applied_fill_equity.py`](../../apps/api-python/tests/applied_fill_equity.py)
- Nodos nuevos:
  [`test_cycle_pnl_quantum.py`](../../packages/py/application/tests/test_cycle_pnl_quantum.py) ·
  [`test_auto_identity_chain_pnl_residual_pg.py`](../../apps/api-python/tests/test_auto_identity_chain_pnl_residual_pg.py)
