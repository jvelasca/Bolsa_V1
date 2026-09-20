# Audit-pack v2.43.2 — Hardening de contabilidad de posición + Exit Governance (AUTO-3 slice 2) (2026-09-19)

**Versión:** `1.68.2-beta` (bump `1.68.1-beta` → `1.68.2-beta`) · **Sin migración** (el head de Alembic
sigue en `042_portfolio_reservations`) · **Tag de certificación:** **PENDIENTE** (este documento se
publica **antes** del sello; §9 declara qué falta y no afirma CI de un tag que aún no existe).

**Alcance.** Dos fases en un solo parche:

- **Fase 1 — Hardening (v2.43.2):** seis hallazgos de contabilidad de posición detectados al leer
  `position_ledger.py` y el camino del snapshot de trabajo del tick, **dos de ellos P0**. No hay cambio de
  arquitectura ni comportamiento nuevo de producto.
- **Fase 2 — Exit Governance (AUTO-3 slice 2):** el gobernador deja de gobernar **solo las entradas** y
  pasa a gobernar también el **ciclo de vida** de la posición (`RISK_EXIT`/`REGIME_EXIT`/`KILL_SWITCH`),
  con productor real de `HALTED`, frescura por dimensión y reservas de salida vivas.

**Nota de numeración (importante para el auditor).** El plan de trabajo bautizó la fase 2 como «_Exit
Governance v2.44_». **La versión del paquete es `1.68.2-beta`, no `1.69.0-beta`**, porque el
[roadmap](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md) reserva `V2.44`/`1.69.0-beta` para **AUTO-4
Portfolio Optimizer** y el [relevo del slice 1](./traspaso-relevo-post-v2-43-auto-3-slice-1-2026-09-18.md)
declara Exit Governance como **AUTO-3 slice 2**. Este parche **es** el slice 2 de `AUTO-3` y **no** abre la
`V2.44` del roadmap. Si el auditor encuentra una referencia a «v2.44» en el código, es la **etiqueta del
plan**, no la versión de paquete.

**Lo que NO se toca, declarado por adelantado.** El **gobernador** no se toca: ni los tres ejes, ni la
tabla de decisión, ni el gate de ENTRADAS, ni sus umbrales. Su evidencia
(`apps/api-python/scripts/v2_43_governor_evidence.py`) queda **byte a byte igual que en `HEAD`** (verificado
con `git diff`) y sigue **exit 0** con la escalera de drawdown gobernando. Su campo `"bump": "1.68.0-beta"`
**se queda como está**, por el mismo motivo que se declaró en
[`v2.43.1`](./cierre-v2.43.1-remediacion-auditoria-2026-09-18.md) §8.2: cambiar la etiqueta de versión de
un JSON citado por packs anteriores solo añade ruido al diff, y este parche **no** mueve la tabla. Tampoco
se mueve **`v2.43-beta`** ni **`v2.43.1-beta`**: esta es una ref nueva y aditiva.

---

## 0. Resumen: los seis hallazgos del hardening

| ID     | Hallazgo                                                                                                                                                                                                                | Gravedad | Dónde                                                     | Estado  |
| ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | --------------------------------------------------------- | ------- |
| **H1** | `realized_qty` sumaba la cantidad **solicitada** de la venta, no la que **casó**: una venta rechazada o el exceso de un oversell avanzaba la cantidad cerrada y podía **reportar como plana una compra real posterior** | **P0**   | `position_ledger.py:280-292`                              | CERRADO |
| **H2** | El snapshot de trabajo **resucitaba R2**: `(risk_used or 0.0) + committed_risk` convertía "riesgo no medido" en un **total medido** y el motor dejaba de vetar                                                          | **P0**   | `auto_v2_entry.py:1173`, `auto_portfolio_snapshot.py:436` | CERRADO |
| **H3** | Un stop del **lado equivocado** se publicaba como riesgo **`0.0`** (medido) en vez de desconocido ⇒ "stop mal puesto" se leía como "posición sin riesgo"                                                                | P1       | `auto_v2_entry.py:607`                                    | CERRADO |
| **H4** | El **fold** no garantizaba la idempotencia por `execution_id`: dos hechos con la misma clave doblaban posición, riesgo, cash y P&L (aunque la PK la garantice en la escritura)                                          | P1       | `position_ledger.py:360-372`                              | CERRADO |
| **H5** | El libro **no tenía cuota de cuenta**: con `account_id=None` (todas las cuentas) el fold **fundía** dos posiciones del mismo instrumento en cuentas distintas en **una**                                                | P1       | `position_ledger.py:98,375`                               | CERRADO |
| **H6** | Un hecho **sin `applied_at`** se ordenaba como el **más antiguo** (`str(None or "")` precede a cualquier ISO) y torcía el coste medio                                                                                   | P2       | `position_ledger.py:320`                                  | CERRADO |

**Por qué H1 y H2 son P0 y no cosmética.** Los dos tienen la misma forma que los hallazgos R2/R3/R5 de
`v2.43.1`: _un dato que el sistema no puede interpretar se degrada hacia el lado permisivo, y no lo
declara_.

- **H1** hace que el sistema **vea menos posición de la que tiene**: `remaining_qty = quantity - realized_qty`
  y `realized_qty` avanzaba con una venta que **no casó**. Con la posición viva subestimada, la
  reconciliación puede concluir "ya estoy plano" sobre una posición real, y `equityIfClosed`/P&L heredan el
  error. Es exactamente la dirección peligrosa en la que el sistema cree tener **menos** riesgo del real.
- **H2** es el patrón `or 0.0` **reintroducido por el propio fix de R2**: `v2.43.1` cerró que `gross_risk`
  se publicara por debajo del real, y el snapshot de trabajo del tick volvía a fabricar el total con un
  `(None or 0.0)`. El **motor dejaba de vetar** por medición incompleta precisamente cuando había una
  posición que no declaraba su riesgo.

---

## 1. H1 — `realized_qty` se inflaba con lo que el venue movió, no con lo que casó

**Lo que pasaba (`HEAD`).**

```python
if sellable <= _QTY_EPS:
    violations.append(f"oversell_without_position:{fact.execution_id}")
    realized_qty += fact.quantity          # ← no había inventario y aun así "se cerraba"
    continue
matched = min(fact.quantity, sellable)
...
realized_qty += fact.quantity              # ← el EXCESO también avanzaba la cantidad cerrada
```

`realized_qty` es, por definición del módulo, la cantidad **cerrada** (`quantity_closed`), y
`cost_basis`/`realized_pnl` ya avanzaban solo por `matched`. La cantidad cerrada era el único de los tres
que avanzaba con la **petición**: **la misma línea mentía en dos direcciones** — sobreventa declarada en
`violations` a la vez que la cantidad cerrada crecía.

**Código después (`position_ledger.py:274-311`).**

```python
        # Venta aplicada: se cuenta SIEMPRE como venta ejecutada (es un hecho del venue),
        # pero solo realiza P&L / cierra cantidad en la parte que casa contra inventario.
        sold_qty += fact.quantity
        avg_entry = (cost_basis / quantity) if quantity > _QTY_EPS else None
        sellable = quantity - realized_qty
        if sellable <= _QTY_EPS:
            violations.append(f"oversell_without_position:{fact.execution_id}")
            continue
        matched = min(fact.quantity, sellable)
        ...
        realized_qty += matched
```

Y `LedgerPosition` gana **dos campos explícitos** para que la distinción deje de ser implícita:

- **`sold_qty`** — Σ ventas **ejecutadas** (el hecho del venue, siempre cuenta).
- **`unmatched_exit_qty = sold_qty - realized_qty`** — el exceso que **no tenía inventario** contra el que
  casar. `position_ledger.py:311`.

Ambos son **aditivos** y se exponen en `to_dict()`. Un consumidor anterior que solo lea `realized_qty`
sigue viendo la cantidad cerrada — que ahora **sí** es `min(Σ BUY, Σ SELL)`, no `Σ SELL`.

**Por qué se separó en vez de solo corregir el signo.** Si `realized_qty` dejaba de contar el exceso **sin**
publicarlo en ningún sitio, el hecho del venue (vendí 100 contra una posición de 73,5) desaparecía del
libro: la sobreventa quedaría declarada en `violations` pero el número que un humano mira para reconciliar
con el bróker no tendría dónde estar. La semántica acordada es **`realized_qty` = solo lo casado** y el
exceso en un campo propio.

**Tests que lo muerden** (`packages/py/analytics/tests/test_position_ledger.py`):

- `test_oversell_excess_never_inflates_realized_qty_nor_average_entry` — `realized_qty == 73.5`,
  `sold_qty == 100.0`, `unmatched_exit_qty == 26.5`.
- `test_orphan_oversell_never_swallows_a_later_legit_buy` — es el caso **mordido**: una venta huérfana
  seguida de una compra legítima tiene que dejar la compra **viva**. Con el código anterior, la venta
  huérfana avanzaba `realized_qty` y la compra posterior nacía "ya cerrada".
- `test_orphan_oversell_before_a_legit_buy_keeps_position_via_quantities` — el mismo invariante leído por
  el `quantities()` que alimenta la reconciliación (no por el campo crudo).

---

## 2. H2 — El snapshot de trabajo no puede fabricar riesgo medido

**Lo que pasaba (`HEAD`).**

```python
risk_used = snapshot.risk_used
if has_committed_risk:
    risk_used = round(((snapshot.risk_used or 0.0) + committed_risk) * 10000) / 10000
```

`snapshot.risk_used is None` **no** significa "cero": significa que **alguna posición abierta no declara su
`risk_amount`** (el hallazgo R2 de `v2.43.1`). El `or 0.0` convertía esa ausencia en un número y publicaba
un total **medido**. Además el rebuild de `build_auto_portfolio_snapshot` **no** recibía `risk_measurement`,
así que un `risk_used` explícito se leía como una **afirmación** del llamante (`_derive_measurement` lo
trata como medido) y el `UNKNOWN` de la base **se borraba**.

**Código después.**

```python
    # AUTO hardening (v2.43.2): solo se puede SUMAR el riesgo reservado cuando la base
    # está MEDIDA. Un ``snapshot.risk_used = None`` significa "alguna posición abierta no
    # declara su riesgo" ⇒ la cartera tiene ``gross_risk`` DESCONOCIDO. El antiguo
    # ``(None or 0.0) + committed_risk`` convertía esa ausencia en un total medido y el
    # motor dejaba de vetar por medición incompleta: es exactamente "riesgo no medido ≠
    # riesgo 0" (R2), reintroducido por el snapshot de trabajo. Se conserva la ausencia y
    # se reenvía la medición tal cual para que el rebuild no la re-derive a COMPLETE.
    if has_committed_risk and snapshot.risk_is_complete:
        risk_used = round(((snapshot.risk_used or 0.0) + committed_risk) * 10000) / 10000
```

```python
        risk_used=risk_used,
        risk_budget=snapshot.risk_budget,
        # La medición NO se re-deriva: un ``risk_used`` explícito se leería como una
        # AFIRMACIÓN completa en el rebuild y borraría el ``UNKNOWN`` de la base.
        risk_measurement=snapshot.risk_measurement,
```

Y en el lado del rebuild (`auto_portfolio_snapshot.py:430-449`), el suelo derivado de los `risk_amount`
**solo** se calcula si el llamante no ha declarado ya un agregado no medible:

```python
    asserted_measurement = coerce_measurement(risk_measurement)

    used = explicit_used
    # Deriva un SUELO de los ``risk_amount`` SOLO si el llamante no ha declarado ya que
    # el agregado NO es medible. Un ``risk_measurement`` explícito y no ``COMPLETE``
    # prohíbe fabricar un total: el número sería un suelo publicado bajo una etiqueta que
    # dice "no sé" (AUTO hardening v2.43.2 — no resucitar R2 desde el snapshot de trabajo).
    if used is None and declared and asserted_measurement in (None, MEASUREMENT_COMPLETE):
        used = _round4(sum(_non_negative(p.risk_amount) or 0.0 for p in declared))
    ...
    resolved_measurement = asserted_measurement or derived_measurement
```

**Nota de método declarada (importante para no leer el fix al revés).** El `risk_used=None` del snapshot
tiene un segundo significado legítimo: **cartera vacía**. `v2.43.1` lo tradujo explícitamente a `0.0`
**solo** cuando no hay posiciones sin medir. Este parche **no** deshace esa traducción: la conserva en
`_risk_state_for` y lo que prohíbe es **sumar riesgo reservado a una base no medible**. Las dos
afirmaciones conviven porque son casos distintos: "cero **medido**" (cartera vacía) y "**no medido**"
(hay posición sin riesgo declarado).

**Tests que lo muerden** (`packages/py/application/tests/test_auto_v2_entry.py`):

- `test_working_snapshot_never_fabricates_measured_risk` — posición sin `risk_amount` + reserva viva con
  riesgo ⇒ la foto de trabajo sigue con `risk_measurement != COMPLETE` y `risk_used is None` (nunca
  `committed_risk`).
- `test_working_snapshot_adds_committed_risk_when_base_is_measured` — el **control**: con la base medida,
  el riesgo reservado **sí** se suma (el fix no bloquea el caso bueno).

---

## 3. H3 — Stop del lado equivocado = riesgo no medido, no cero

**Lo que pasaba (`HEAD`).**

```python
risk_amount = max(0.0, (float(entry) - float(stop)) * float(qty))
```

Para un `long` con `stop >= entry`, la diferencia es negativa y el `max(0.0, …)` publicaba
**`risk_amount = 0.0`**: un riesgo **medido y cero**. El motor de decisión lee un riesgo medido como
"puedo dimensionar contra esto", así que **dejaba de vetar por medición incompleta** justo en el caso en
que la geometría de riesgo es ininteligible.

**Código después (`auto_v2_entry.py:599-615`).**

```python
            # La geometría la valida la MISMA casa que el resto del motor
            # (``stop_distance``): un long con ``stop >= entry`` NO tiene stop válido, así
            # que su riesgo es DESCONOCIDO (``None``), nunca un 0 declarado. Un 0 aquí
            # contaba como riesgo medido (``COMPLETE``) y el motor dejaba de vetar por
            # medición incompleta: "stop mal puesto" se leía como "posición sin riesgo".
            distance = stop_distance(
                entry=float(entry), stop=float(stop), direction="long"
            )
            if distance is not None:
                risk_amount = distance * float(qty)
```

La autoridad de la geometría pasa a ser `stop_distance()` de `portfolio_reservation.py`, que **ya** era la
casa única que valida stops en el resto del motor: el snapshot no reimplementa la regla.

**Tests que lo muerden:** `test_build_worker_snapshot_wrong_side_stop_is_unmeasured_risk` (el mordido:
`risk_amount is None`, **no** `0.0`, y la decisión veta con `risk_measurement_unknown`) y
`test_build_worker_snapshot_valid_stop_is_measured_risk` (el control).

---

## 4. H4 — Idempotencia de `execution_id` garantizada por el fold

**Lo que pasaba.** La idempotencia **durable** existe desde `AUTO-1`: `execution_events` tiene PK sobre la
clave financiera y `ON CONFLICT DO NOTHING`. Pero el fold era un `sorted()` + agrupación **sin deduplicar**:
si a `build_position_ledger` le llegaban dos hechos con el mismo `execution_id` (una lectura que los une,
un replay, un bug en el lector), el libro contaba el fill **dos veces** — posición, riesgo, cash y P&L. El
hueco no era "la tabla no protege" sino **"el fold no se defiende por sí mismo"**.

**Código después (`position_ledger.py:358-372`).**

```python
    # Idempotencia por identidad financiera: gana la PRIMERA aparición (ya ordenada) y las
    # repeticiones se declaran. ``execution_id`` es global (PK), no por instrumento.
    seen: set[str] = set()
    deduped: list[AppliedFillFact] = []
    duplicates: list[str] = []
    for fact in ordered:
        key = str(fact.execution_id or "").strip()
        if key in seen:
            duplicates.append(key)
            continue
        seen.add(key)
        deduped.append(fact)
```

Los repetidos **no se ignoran en silencio**: entran en `violations` como
`duplicate_execution_id:<id>`, suman a `facts_rejected` y **degradan la medición** (`unvalued`). El libro
que ha visto un duplicado **no** puede leerse como "la posición es exactamente esta".

**Test que lo muerde:** `test_duplicate_execution_id_cannot_double_the_position` — `BUY 100@10
execution_id=X` aplicado dos veces ⇒ `quantity == 100`, **nunca 200**, y el duplicado declarado.

---

## 5. H5 — El libro es por CUENTA

**Lo que pasaba.** `AppliedFillFact` no llevaba `account_id`, y `read_applied_fill_facts` leía los hechos
de **todas** las cuentas cuando no se le pasaba una. El fold agrupaba por **instrumento**, así que dos
posiciones del mismo símbolo en cuentas distintas se fundían en **una** cantidad — y esa cantidad fusionada
es exactamente la que alimenta `quantities()`, el mapa instrumento → cantidad viva con el que la
reconciliación decide. Una fusión así **no se detecta a sí misma**: el número es plausible.

**Código después.**

- `AppliedFillFact.account_id: str = ""` (`position_ledger.py:98`), poblado por
  `applied_fills.py:217` (`account_id=getattr(event, "account_id", None)`) y normalizado en
  `coerce_applied_fill_fact` (un hecho sin cuenta va al cajón `""`: se **agrupa**, nunca se suma a otra
  cuenta).
- El fold agrupa por `(account_id, instrument_id)` (`position_ledger.py:375`) y `LedgerPosition` publica
  `accountId`.
- **Colisión entre cuentas declarada:** si el mismo instrumento aparece en **más de una** cuenta, el mapa
  `quantities()` **no puede** representarlo sin fundirlo ⇒ se **degrada la medición** (cuenta como un
  `unvalued`) en vez de publicar una cantidad fusionada que la reconciliación tomaría por real.

**Por qué degradar y no rechazar.** Rechazar los hechos dejaría el libro vacío (peor: "no tengo
posiciones"), que es la dirección permisiva. Degradar la medición conserva la información y **veta** las
aperturas, que es lo que el sistema hace con cualquier dato que no puede interpretar.

**Tests que lo muerden:** el agrupamiento por cuenta y la colisión entre cuentas
(`packages/py/analytics/tests/test_position_ledger.py`).

---

## 6. H6 — Un hecho sin fecha no se ordena como el más antiguo

**Lo que pasaba.** La clave del fold era `(str(applied_at or ""), str(execution_id or ""))`. `str(None or
"")` es `""`, que precede a **cualquier** ISO real en orden lexicográfico: una fila legada sin fecha se
doblaba como "el hecho más antiguo", y como el coste medio se **acumula en orden** (`cost_basis` crece con
las compras y las ventas realizan contra el medio vigente), el orden determinaba el `average_entry` y el
P&L realizado. Un `""` colado al principio no es un detalle de ordenación: es **otro precio de entrada**.

**Código después (`position_ledger.py:320-336`).**

```python
def _fold_sort_key(fact: AppliedFillFact) -> tuple[int, str, str]:
    """Clave determinista del fold: ``(tiene_fecha, applied_at, execution_id)``.

    AUTO hardening (v2.43.2): un hecho SIN fecha no puede ordenarse como si fuera el
    PRIMERO. ``str(None or "") == ""`` precede a cualquier ISO real en orden lexicográfico,
    así que una fila legada sin fecha se doblaba como "la compra más antigua" y torcía el
    coste medio (que depende del orden de compras y ventas). Los hechos sin fecha se
    separan al FINAL de forma declarada (``1``) y el orden entre ellos sigue siendo
    determinista por ``execution_id``. AUTO-1b ya cerró la causa raíz (un ``datetime`` de
    PostgreSQL dejaba de perder su fecha al normalizarse); esto protege el residuo legado.
    """
    return (
        0 if fact.applied_at else 1,
        str(fact.applied_at or ""),
        str(fact.execution_id or ""),
    )
```

**Test que lo muerde:** `test_facts_without_date_are_folded_last_not_first`.

---

## 7. Fase 2 — Exit Governance (AUTO-3 slice 2)

### 7.1 Taxonomía de motivos: se extiende, no se duplica

`ExitReason` gana **`KILL_SWITCH`**, **`REGIME_EXIT`** y **`RISK_EXIT`** (`exit_plan.py:19-22`) y se
insertan en la `EXIT_REASON_PRECEDENCE` **que ya existía** (`exit_plan.py:44-56`), cuyo orden es **por
autoridad de deshacer riesgo**:

```text
KILL_SWITCH > REGIME_EXIT > RISK_EXIT > MANUAL > STRUCTURAL_STOP
             > THESIS_INVALIDATION > PORTFOLIO_RISK > TARGET_1 > TARGET_2 > TRAIL > TIME_STOP
```

Lo relevante **no** es que haya tres razones nuevas, sino que **`REGIME_EXIT` deja de ser un override
post-hoc fuera del `Literal`**: antes el manager forzaba la venta y **añadía** el string `"regime_exit"` a
mano al final de la lista (`exit_reasons.append(REGIME_EXIT)`), de modo que el motivo vivía fuera de la
taxonomía y no competía por precedencia con nadie. Ahora nace en el `ExitPlan` (`_collect_reasons` recibe
`kill_switch`/`regime_exit`/`risk_exit`, `exit_plan.py:168-174`), y el manager **deriva** la lista de la
decisión:

```python
    exit_reasons: list[str] = []
    if decision.primary_reason:
        exit_reasons.append(decision.primary_reason.lower())
    exit_reasons.extend(reason.lower() for reason in decision.secondary_reasons)
```

`PositionDecision` gana **`secondary_reasons`** (`position_decision.py:354`): un solo `primary_reason`
**decisorio** (el primero por precedencia) y los demás que también dispararon. `PositionManagerResult`
publica `primary_exit_reason`/`secondary_reasons` (`position_manager.py:120-133`). **El journal deja de
perder la atribución múltiple** sin inventar un segundo eje.

`suggestion_from_exit_policy` trata los tres motivos del gobernador como **venta TOTAL explícita** (no
negociable por tramos ni protegible con un stop), con una rama **explícita** en vez de dejar que caigan en
el fallback: si mañana se añade otro motivo, este contrato no cambia por accidente.

### 7.2 `portfolio_risk`/`manual` dejan de ser inalcanzables

`build_exit_plan_from_position` **ya** aceptaba `portfolio_risk` y `manual` desde `AUTO-2`, pero
**nadie los pasaba** desde el camino AUTO: `PORTFOLIO_RISK` y `MANUAL` eran valores **inalcanzables** de la
taxonomía. Ahora se propagan por `build_position_decision` y `manage_position_outcome` (parámetros
aditivos con default `False`).

### 7.3 El gobernador gobierna el ciclo de vida, no solo la entrada

`manage_position_outcome` recibe la lectura del gobernador **para esta posición** — `risk_regime`,
`drawdown_band`, `operational_state` — además del régimen de mercado (`position_manager.py:281-285`):

```python
    # Lectura del gobernador (fail-closed: lo no reconocido no es permisivo).
    halted = coerce_operational_state(operational_state) == "HALTED"
    band = coerce_drawdown_band(drawdown_band)
    risk_off = coerce_risk_regime(risk_regime) == "RISK_OFF" or band == "EXIT_ONLY"
    regime_exit = regime_is_exit_only(regime)
```

| Lectura del gobernador                       | Motivo decisorio | Efecto          |
| -------------------------------------------- | ---------------- | --------------- |
| `OperationalState == HALTED`                 | `KILL_SWITCH`    | venta **total** |
| régimen de mercado exit-only                 | `REGIME_EXIT`    | venta **total** |
| `RiskRegime == RISK_OFF` o banda `EXIT_ONLY` | `RISK_EXIT`      | venta **total** |

Tres cosas que el diseño garantiza y conviene declarar porque son donde un fix así se suele romper:

1. **Coercers canónicos, fail-closed.** `risk_regime`/`drawdown_band`/`operational_state` pasan por los
   `coerce_*` del gobernador: un valor **no reconocido** no es permisivo (`UNKNOWN`), no un bypass.
2. **`RISK_OFF` ⇒ `portfolio_risk=True` **y** `risk_exit=True`.** El contrato del roadmap dice
   `portfolio_risk` (exit total); `risk_exit` se añade para que el motivo **decisorio** sea `RISK_EXIT`
   (más alto en la precedencia) y `PORTFOLIO_RISK` viaje como **secundario**. Sin esa distinción el
   journal no podría distinguir "el gobernador liquidó" de "la política de cartera liquidó".
3. **Reafirmación defensiva (`position_manager.py:324-333`).** La decisión ya pide `full_exit`, pero
   además se **reafirma** la venta total:

```python
    # Reafirmación defensiva: un halt, un permiso exit-only o un ``RISK_OFF`` son SIEMPRE
    # venta TOTAL. La decisión ya pide ``full_exit``, pero así ningún camino (recon,
    # fracción de T2, ratchet de stop) puede dejar posición abierta contra el gobernador.
    if halted or regime_exit or risk_off:
        order_action = "sell"
        order_qty = marked.remaining_quantity
        stop_update = None
```

**`EXIT_ONLY`/`ENTRY_RESTRICTED` NO liquidan.** Es la distinción que más fácil se equivoca y queda
declarada en el docstring del worker: `EXIT_ONLY` veta **aperturas**; lo que **liquida** es
`RiskRegime == RISK_OFF` (⇒ `RISK_EXIT`) y `OperationalState == HALTED` (⇒ `KILL_SWITCH`). Un test lo
muerde explícitamente (`test_exit_only_operational_state_does_not_liquidate`).

**Motivos en el journal.** `RISK_EXIT`/`REGIME_EXIT`/`KILL_SWITCH` entran en
`_DAY_EXIT_REASON_BY_PRIMARY` (`auto_reason_codes.py:113-118`) para que la fila `position_close` del día
cuente la liquidación de riesgo sin reinterpretar nada, y en `_journal_exit_request` del worker para
**avanzar el FSM** (`EXIT_REQUESTED`): sin eso la posición quedaba `OPEN` mientras la orden de venta
viajaba y **un reinicio en mitad del exit no veía el estado de salida**.

### 7.4 `HardKillSwitch` latcheado por encima del gobernador

Módulo nuevo `packages/py/analytics/src/bolsa_analytics/cognitive/hard_kill_switch.py` (puro,
determinista: sin I/O, sin reloj — el `at` es opaco y lo aporta el llamante).

**El agujero que cierra.** `resolve_operational_state` acepta `halted` **desde el slice 1** y fuerza
`HALTED` con él, pero **`plan_v2_tick` no lo pasaba nunca** (default `False`): el kill switch era un
**parámetro muerto**. La tabla podía leer "halted" y nadie se lo decía.

Propiedades que el diseño garantiza (y que están mordidas por tests):

| Propiedad                | Contrato                                                                                                                                                                                                                  |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Tipificado**           | Solo los 8 motivos canónicos. Un motivo no canónico levanta `ValueError`: no se puede parar el sistema "de cualquier manera" y dejar el journal sin poder explicar por qué                                                |
| **Latcheado**            | Una vez activado **no se auto-libera**: que el tick siguiente "parezca" normal no lo desactiva. Reavisar no reinicia el latch (cuenta `reengagements` y conserva el motivo original)                                      |
| **Independiente**        | No depende del juicio del gobernador ni de sus umbrales: se aplica **antes** de la tabla y no se puede "compensar" con un eje benigno                                                                                     |
| **Liberación explícita** | `release(reconciliation_ok=True)`: sin reconciliación declarada, sigue latcheado                                                                                                                                          |
| **Entradas vs salidas**  | Bloquea entradas **siempre**; por defecto **permite** las salidas protectoras (`force_protective_exits=True`) — el invariante de oro de la casa: la reconciliación veta aperturas, **nunca** una salida que reduce riesgo |

Motivos: `DATA_CORRUPTION`, `BROKER_DESYNC`, `RECONCILIATION_FAILURE`, `DUPLICATE_EXECUTION`,
`RISK_BREACH`, `STALE_DATA`, `MANUAL_KILL`, `SYSTEM_ERROR`.

**En el motor (`auto_v2_entry.py:817-841`).**

```python
        # V2.44: la parada DURA es INDEPENDIENTE del flag del gobernador. Si ``halted``
        # está activo se evalúa la tabla aunque el gobernador esté OFF, porque un kill
        # switch no puede quedar desactivado por un flag de conveniencia.
        if cfg.governor_enabled or halted:
            governor = assess_from_measurements(
                ...
                halted=halted,
            )
```

El `or halted` es deliberado y tiene su test: **un kill switch no puede quedar desactivado por un flag de
conveniencia**. En el worker, `engage_kill_switch`/`release_kill_switch` son la API pública
(`auto_simulation_worker.py:1227-1237`).

### 7.5 Frescura por dimensión

Módulo nuevo `packages/py/analytics/src/bolsa_analytics/cognitive/data_freshness.py`. La frescura era un
único booleano ("los datos están frescos o no"), que mezcla **relojes distintos** y no distingue lo que
puede esperar de lo que no. Ahora son cuatro dimensiones con umbral declarado por dimensión:

| Dimensión     | Qué invalida                             | Umbral por defecto |
| ------------- | ---------------------------------------- | ------------------ |
| `market_data` | su vejez invalida **cualquier apertura** | 300 s              |
| `atr`         | degrada el dimensionamiento              | 3600 s             |
| `quote`       | el precio de referencia de ejecución     | 60 s               |
| `volume`      | la liquidez                              | 3600 s             |

Invariante de la casa, hecho explícito: **stale ⇒ NO ENTRY, pero las salidas protectoras siguen
permitidas**. Por eso el veredicto se publica como `blocks_new_entry` — un **veto de aperturas** — y
**nunca** como un halt, que congelaría también las salidas.

Dos decisiones de honestidad del dato que merecen declararse:

- **`unknown` bloquea igual que `stale`** para `market_data` (`blocks_new_entry` es `status != fresh`): no
  se abre contra un dato que **no se pudo fechar**. Y en el eje **booleano** del snapshot `unknown` se
  publica como **`stale`**: "no sé" jamás puede leerse como fresco.
- **Un instante no interpretable ⇒ `unknown`, nunca epoch 0.** `_epoch` devuelve `None` si no puede
  normalizar; devolver `0` habría fabricado un "muy viejo" ⇒ un **stale inventado**.

Las otras tres dimensiones **no** bloquean la apertura por sí solas: degradan el dimensionamiento, que ya
es fail-closed río abajo.

### 7.6 Reservas de SALIDA vivas (F9)

**El agujero.** `committed_positions()` **saltaba** las reservas `sell` ("una VENTA no compromete capital")
y la reconciliación del worker solo consumía fills `is_buy`. Para una entrada esto es correcto; para una
**salida con fill parcial** es un agujero: la cola de un `RISK_EXIT` era **invisible** en los dos sentidos.

1. La foto de trabajo **sobreestimaba** la exposición comprometida (la venta ya emitida no descontaba).
2. Al reiniciar nadie sabía que había una salida **en vuelo**: la gestión volvía a dimensionar contra la
   posición y **emitía otra vez la MISMA orden**.

**Código después.** `committed_positions()` **netea** por instrumento
(`portfolio_reservation.py:847-899`): `net_qty = Σ compras vivas − Σ ventas vivas`, **nunca negativo** (si
la venta cubre todo el compromiso de compra, no queda nada que proyectar); `market_value` y `risk_amount`
solo se publican si **todas** las partes son medibles (si no, `None`: la misma disciplina fail-closed del
resto del módulo). El worker:

- crea una reserva de salida **durable antes de emitir** (`_v2_reserve_exit`,
  `auto_simulation_worker.py:1887`) — no reserva capital ni riesgo nuevo (`0.0` declarados): su dimensión es
  la **cantidad viva**, que es lo que impide re-emitir;
- la libera con los fills de **venta**, casando por **lado**:
  `_v2_release_reservations_for_fill(side=SIDE_SELL)` (`auto_simulation_worker.py:3283`);
- la reconciliación de arranque casa **por (instrumento, lado)**, no solo por instrumento
  (`applied: dict[tuple[str, str], ...]`).

**Y sigue vigente el invariante de `v2.41`:** si la liberación no se puede **persistir**, la reserva se
**conserva**. Jamás se libera en memoria lo que no es durable.

### 7.7 Golden Day dinámico con crash

`apps/api-python/tests/test_auto_v44_exit_governance.py` (nuevo, 8 tests). El escenario obligatorio del
plan, **con reinicio dentro de cada fase**:

- `test_v2_risk_off_liquidates_open_position_with_risk_exit` — posición abierta + `RISK_OFF` ⇒ `RISK_EXIT`
  ⇒ orden de venta real.
- `test_v2_hard_kill_switch_vetoes_entry_with_governor_halted` — la parada dura veta la apertura (y la
  tabla se evalúa **con el gobernador por defecto**).
- `test_v2_halt_forces_protective_exit_not_congelation` — con la parada activa, la salida protectora
  **sigue viva**: el halt no congela el riesgo.
- `test_v2_stale_market_data_vetoes_entry_but_allows_protective_exit` y
  `test_v2_stale_data_blocks_new_entry` — frescura: veta aperturas, no salidas.
- `test_v2_exit_leaves_a_live_sell_reservation_released_by_fill` — la salida deja reserva viva y el fill
  la libera.
- `test_v2_golden_day_dynamic_entry_risk_exit_flat_with_restart` — el día completo:
  `ENTRY → RISK_EXIT → FLAT` con reinicio en cada fase y `position=0, reservation=0, pending=0`.
- `test_v2_restart_mid_risk_exit_releases_the_dead_sell_reservation_once` — **el caso de fuego**: `SELL
100` emitida, cae el proceso, y al reiniciar debe ser **imposible emitir `SELL 100` dos veces**; la
  reserva muerta se libera **una vez** (`RESERVATION_RELEASED_BY_RESTART`) y no queda viva para
  re-emitirse.

---

## 8. Cambios observables declarados

| Cambio                                                                                            | Naturaleza                                                                                                                                        |
| ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `LedgerPosition.sold_qty` / `unmatched_exit_qty` / `accountId` y `AppliedFillFact.accountId`      | **Aditivos**. `realized_qty` cambia de **valor** (ahora `min(ΣBUY, ΣSELL)`), que **es** el fix H1                                                 |
| `PositionDecision.secondaryReasons`, `PositionManagerResult.primaryExitReason`/`secondaryReasons` | **Aditivos** en `to_dict()`: el journal del camino V2 publica dos claves nuevas **solo** cuando hay gestión de posición con motivos               |
| `PositionManagerResult.exitReasons` puede traer **más de un** motivo                              | `REGIME_EXIT` ya no se **añadía** al final: ahora el orden es por **precedencia** y el motivo puede ser `RISK_EXIT` donde antes era `regime_exit` |
| `committed_positions()` descuenta las reservas `sell` vivas                                       | La exposición comprometida **baja** cuando hay una salida en vuelo (que es la corrección, no una regresión)                                       |
| `risk_amount = None` con stop del lado equivocado                                                 | De **`0.0` medido** a **desconocido**: el motor **veta** donde antes aprobaba con un riesgo inventado a la baja (es el fix H3)                    |

**Byte-identidad con el gobernador OFF.** `plan_v2_tick` evalúa la tabla si `cfg.governor_enabled or
halted`; con el flag OFF y **sin parada dura**, `halted` es `False` y el camino es el histórico. La
evidencia del gobernador (que corre su control con el flag OFF en cada tramo de la escalera) sale **exit 0**
midiendo exactamente el mismo journal.

---

## 9. Verificación local medida (árbol final)

Comandos **exactos** de la casa. Los dos bloques offline usan el runner versionado
(`scripts/verify/offline_ci_run_yaml.py`), que **extrae los targets del YAML**, verifica que cada ruta
existe y mide por **JUnit XML** (bajo `subprocess` en Windows el stdout de pytest llega truncado).

| Comprobación                         | Comando                                                                                                                                                                                                                                  | Resultado                                       |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| Estático (invocación de CI)          | `uv run ruff check packages/py apps/api-python --config pyproject.toml`                                                                                                                                                                  | **All checks passed!**                          |
| Tipos                                | `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent`                                                                       | **487 ficheros, 0 issues**                      |
| Fronteras                            | `uv run lint-imports --config packages/py/.importlinter`                                                                                                                                                                                 | **4 kept / 0 broken** (602 ficheros, 3192 deps) |
| Evidencia del gobernador             | `uv run python apps/api-python/scripts/v2_43_governor_evidence.py --out governor.json`                                                                                                                                                   | **exit 0** (la tabla sigue gobernando)          |
| Bloque `quality` de CI               | `uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores`                                                                                                                          | **2031 passed, 0 failed, 0 skipped**            |
| Bloque `python` del tag              | `uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores`                                                                                                                      | **2042 passed, 0 failed, 0 skipped**            |
| `packages/py/analytics` (completo)   | `uv run pytest packages/py/analytics -q`                                                                                                                                                                                                 | **862 passed**                                  |
| `packages/py/application` (completo) | `uv run pytest packages/py/application -q`                                                                                                                                                                                               | **1705 passed, 5 skipped**                      |
| v2.44 + módulos nuevos               | `uv run pytest apps/api-python/tests/test_auto_v44_exit_governance.py packages/py/analytics/tests/test_hard_kill_switch.py packages/py/analytics/tests/test_data_freshness.py packages/py/application/tests/test_position_manager.py -q` | **45 passed**                                   |

### 9.1 El delta `+40/+40` es la comprobación de cobertura

`quality` pasa de **1991** (medido en `v2.43.1`) a **2031**; el job `python` del tag, de **2002** a
**2042**. El delta es **exactamente 40** en **los dos** bloques, y el reparto de los 40 tests nuevos es:

| Fichero                                                  | Nuevos | Nota                           |
| -------------------------------------------------------- | ------ | ------------------------------ |
| `packages/py/analytics/tests/test_position_ledger.py`    | 5      | H1 (×3), H4, H6                |
| `packages/py/application/tests/test_auto_v2_entry.py`    | 4      | H2 (×2), H3 (×2)               |
| `packages/py/application/tests/test_position_manager.py` | 8      | gobernador → manager (×8)      |
| `packages/py/analytics/tests/test_hard_kill_switch.py`   | 7      | **fichero nuevo**              |
| `packages/py/analytics/tests/test_data_freshness.py`     | 8      | **fichero nuevo**              |
| `apps/api-python/tests/test_auto_v44_exit_governance.py` | 8      | **fichero nuevo** (Golden Day) |
| **Total**                                                | **40** |                                |

Que el delta sea **idéntico en los dos bloques** significa que los tres ficheros nuevos entran por las
**listas existentes** (`packages/py/analytics/tests` va por **pase de directorio** en `quality`;
`apps/api-python/tests` también en `quality` y **explícito** en el job `python` del tag) y **ninguno queda
fuera de la red** — la deuda que `v2.42.2` tuvo que cerrar a mano para `test_auto_daily_journal.py`.

---

## 10. Matriz de mutaciones MEDIDA

**Sonda:** [`apps/api-python/scripts/v2_43_2_mutation_audit.py`](../../apps/api-python/scripts/v2_43_2_mutation_audit.py)
(patrón de `v2_40_4_mutation_audit.py`: copia en memoria, restauración **sin** `git checkout --` y huella
`git status --porcelain` de los ficheros tocados verificada **antes/después** — la sonda devuelve `exit 0`
solo si el árbol queda intacto). Medida el **2026-09-20** sobre el árbol final de este parche, con
`uv run --no-sync python apps/api-python/scripts/v2_43_2_mutation_audit.py`.

**Método.** Cada mutación se aplica con `.replace(old, new, 1)`; antes de aplicarla la sonda comprueba que
el fragmento aparece **exactamente una vez** (si aparece más de una, **aborta** en vez de mutar la primera
y mentir). Las suites de `apps/api-python` se corren con un `DATABASE_URL` a un puerto local cerrado: el
teardown de `apps/api-python/tests/conftest.py` purga residuos contra Postgres y, sin PG, se colgaría; con
el DSN fast-fail falla al instante y la sonda devuelve **rojos con nombre**, no un `TIMEOUT` mudo. El
`timeout` de 600 s sigue ahí como red.

| #   | Mutación aplicada (revertir el fix)                                                   | Rojos observados (medido)                                                                                                                                                                                                                                                                                                |
| --- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| M1  | bloque del fold → versión de `HEAD` (sin `sold_qty`; `realized_qty += fact.quantity`) | **5**: `test_orphan_oversell_before_a_legit_buy_keeps_position_via_quantities`, `test_orphan_oversell_never_swallows_a_later_legit_buy`, `test_oversell_excess_never_inflates_realized_qty_nor_average_entry`, `test_oversell_is_a_declared_violation_not_an_invented_short`, `test_sell_without_any_buy_is_a_violation` |
| M2  | `if has_committed_risk:` sin `and snapshot.risk_is_complete`                          | **1**: `test_working_snapshot_never_fabricates_measured_risk`                                                                                                                                                                                                                                                            |
| M3  | `risk_measurement=None` en el rebuild                                                 | **1**: `test_working_snapshot_never_fabricates_measured_risk`                                                                                                                                                                                                                                                            |
| M4  | `risk_amount = max(0.0, (entry - stop) * qty)` (la línea de `HEAD`)                   | **1**: `test_build_worker_snapshot_wrong_side_stop_is_unmeasured_risk`                                                                                                                                                                                                                                                   |
| M5  | `if False:` en el dedupe por `execution_id`                                           | **1**: `test_duplicate_execution_id_cannot_double_the_position`                                                                                                                                                                                                                                                          |
| M6  | agrupar por `("", instrument_id)` en vez de `(account_id, instrument_id)`             | **NADA** — agujero declarado (§10.1)                                                                                                                                                                                                                                                                                     |
| M7  | `0,` como clave del fold (un hecho sin fecha se ordena primero)                       | **1**: `test_facts_without_date_are_folded_last_not_first`                                                                                                                                                                                                                                                               |
| M8  | quitar `or halted` del `if cfg.governor_enabled or halted:`                           | **1**: `test_v2_hard_kill_switch_vetoes_entry_with_governor_halted`                                                                                                                                                                                                                                                      |
| M9  | `halted=False` fijo en la llamada a `assess_from_measurements`                        | **1**: `test_v2_hard_kill_switch_vetoes_entry_with_governor_halted`                                                                                                                                                                                                                                                      |
| M10 | `if regime_exit:` (sin `halted` ni `risk_off`)                                        | **NADA** — mutación no observable (§10.1)                                                                                                                                                                                                                                                                                |
| M11 | `blocks_new_entry` → `return False`                                                   | **4**: `test_stale_market_data_blocks_new_entry`, `test_unknown_market_data_is_not_fresh`, `test_v2_stale_data_blocks_new_entry`, `test_v2_stale_market_data_vetoes_entry_but_allows_protective_exit`                                                                                                                    |
| M12 | saltar (`continue`) las reservas `sell` en `committed_positions`                      | **NADA** — agujero declarado (§10.1)                                                                                                                                                                                                                                                                                     |
| M13 | casar los fills por `(instrument_id, "buy")` en vez de `(instrument_id, side)`        | **NADA** — agujero declarado en el camino de arranque (§10.1)                                                                                                                                                                                                                                                            |

**Balance: 9 de 13 mutaciones muerden** (M1–M5, M7–M9, M11) y **4 nacen verdes** (M6, M10, M12, M13).
Ninguna de las 13 pone rojo a `T_KILL`: sus 7 tests son **unitarios puros** de `HardKillSwitch` (latch,
tipificación, liberación) y no pasan por código mutado; su contrato está medido por su propia suite, no por
esta matriz.

### 10.1 Las cuatro mutaciones verdes: por qué (medido, no supuesto)

Una mutación verde **no** se declara "agujero de cobertura" por defecto (la trampa ya medida en `v2.42.1`
M5/M10/M13 y `v2.43` M5/M6). Cada verde de arriba se investigó hasta su causa:

- **M6 — agujero de cobertura de H5 (real).** La mutación **sí rompe comportamiento** (fusiona en una las
  posiciones del mismo instrumento en cuentas distintas y desactiva la degradación por colisión), pero
  **ninguna suite la muerde**: `packages/py/analytics/tests/test_position_ledger.py` no construye **nunca**
  un libro con dos `account_id` para el mismo instrumento (0 apariciones de `account_id` en el fichero), así
  que el eje "cuenta" del libro no está ejercitado.
- **M10 — mutación NO observable (no es agujero de comportamiento).** `manage_position` ya pasa
  `risk_exit=risk_off`, `regime_exit=regime_exit` y `kill_switch=halted` a `build_position_decision`, así
  que la decisión **ya nace** con venta total en los tres casos. Quitar la reafirmación defensiva no cambia
  el resultado en **ningún** camino medido: es una línea "cinturón y tirantes" **redundante** con la
  decisión, sin sensor propio. No es el bug de vuelta.
- **M12 — agujero de cobertura del neteo de F9 (real).** El único test que usa `committed_positions()`,
  `test_committed_positions_projects_live_buys_only`, reserva la compra y la venta en **instrumentos
  distintos** (`AAA` / `BBB`), así que el contrato de F9 —**netear una venta viva contra la compra del
  MISMO instrumento**— no se afirma en ninguna parte. La mutación borra ese neteo y pasa inadvertida.
- **M13 — agujero de cobertura en el camino de arranque (real).** La mutación vive en
  `_v2_reconcile_reservations`, que **solo corre en el arranque** (`auto_simulation_worker.py:3445`). El
  único test de arranque con una reserva `sell` viva
  (`test_v2_restart_mid_risk_exit_releases_the_dead_sell_reservation_once`) la libera por la rama
  **"muerta"** (`status == RESERVATION_RELEASED_BY_RESTART`, `filled == 0`), así que el cambio de clave de
  agrupación no se observa. Es **exactamente** la trampa que el relevo avisaba para M13 ("dos sensores
  tapándose"). El camino "venta liberada por fill" **sí** está cubierto — pero por la **otra** ruta
  (release inline en `auto_turn`, `test_v2_exit_leaves_a_live_sell_reservation_released_by_fill`), no por
  la reconciliación de arranque.

**Consecuencia declarada:** este cierre **no cambia una línea de código de producción ni añade tests**
(regla de oro del relevo §0). Los tres agujeros reales (M6, M12, M13) quedan **declarados aquí** con su
mutación reproducible; añadir su sensor es una decisión del owner, no un "arreglo a escondidas" dentro del
sello.

**Aviso de método** (de las trampas ya medidas en el repo, §4 del relevo de `v2.43`): antes de "añadir
cobertura" a una mutación verde, comprobar que la mutación **rompe comportamiento** y no otro motivo; y
si un test sigue verde con la mutación, **no** es automáticamente un agujero de cobertura — hay que
descartar que el mutante sea más fuerte (o más débil) que el bug real.

### 10.2 Otros límites declarados (no silenciosos)

- **PG real NO medido** en la máquina del autor (motivo ya declarado en fases anteriores: el `connect` del
  DSN no responde ni rechaza, se cuelga). La fase 1 **no toca ningún fichero PG** ni añade migración, así
  que la certificación de durabilidad de `auto-v2-durable-pg` cubre lo mismo que en `v2.43.1`; la
  durabilidad de las **reservas de salida** (fase 2) se certifica en los jobs con PG real, que deben
  re-ejecutarse en CI. **Un skip mudo no certifica nada.**
- **`PositionLedger` sigue siendo read-model sin tabla propia** y el `limit` de `list_applied` sigue siendo
  un **suelo** (deuda declarada de `v2.40.5`, no de este parche).
- **La parada dura es en memoria** (`HardKillSwitch` es un dataclass del worker): **no** se persiste entre
  reinicios. Un reinicio **olvida** que había una parada activa. Es una decisión declarada, no un olvido —
  persistirla exige decidir **dónde** (JSONB o tabla) y es trabajo de la fase de Crash/Recovery.
- **`force_protective_exits` no está cableado a política**: existe el flag y su semántica, pero el camino
  del worker **no lo consulta** todavía para congelar salidas (el default `True` es lo que se ejecuta).
- **La frescura se puebla desde el tick SIM**: `_v2_data_timestamps` se alimenta con el reloj de las
  marcas del simulador; **no** hay todavía un productor real (feed) que declare la edad de `atr`/`volume`,
  así que esas dos dimensiones normalmente van **`unknown`** y **no** atan. Solo `market_data` es el eje
  activo hoy.
- **El emisor de `RECONCILED` sigue sin existir** en el camino del worker (deuda de `AUTO-2`), y por tanto
  la **liberación explícita** de la parada dura (`release_kill_switch`) **no tiene un productor automático**:
  se libera por API explícita. Es coherente con el diseño (liberar exige reconciliación), pero significa que
  hoy un halt **no se libera solo**.
- **Los umbrales del gobernador siguen declarados y no calibrados** (`min_liquidity_notional` en `0,0`,
  `restricted_edge_factor` en `2,0`): deuda de `AUTO-3` slice 1, intacta aquí.
- **El gobernador sigue con default OFF**: este parche **no** flipa ningún flag. Con OFF (y sin parada
  dura) el camino V2 es el histórico.

---

## 11. Cómo verificarlo (para el auditor)

```bash
# Estático, tipos y fronteras (invocaciones EXACTAS de CI)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
             packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# El gobernador NO se movió (byte-identidad + la tabla sigue gobernando)
git diff -- apps/api-python/scripts/v2_43_governor_evidence.py   # debe salir VACÍO
uv run python apps/api-python/scripts/v2_43_governor_evidence.py --out governor.json; echo "exit=$?"

# Los dos bloques offline de CI (targets e ignores EXTRAÍDOS del YAML, medida por JUnit XML)
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores

# Las suites que muerden los hallazgos (herméticas, <1 s)
uv run pytest packages/py/analytics/tests/test_position_ledger.py \
              packages/py/analytics/tests/test_hard_kill_switch.py \
              packages/py/analytics/tests/test_data_freshness.py \
              packages/py/analytics/tests/test_exit_plan.py \
              packages/py/application/tests/test_auto_v2_entry.py \
              packages/py/application/tests/test_position_manager.py -q

# El Golden Day dinámico con reinicio (el test de fuego)
uv run pytest apps/api-python/tests/test_auto_v44_exit_governance.py -q
```

**Formato de un hallazgo sobre este parche** (el mismo que el resto del repo):
`P0/P1/P2 · afirmación atacada · ruta:línea · comando exacto · salida observada · ¿el §10 de este
documento ya lo declara?`

---

## 12. Sello

**PENDIENTE.** Este documento se publica **antes** del sello y **no afirma** CI de un tag que aún no
existe. Lo que falta, explícitamente (orden de trabajo:
[`relevo-cierre-v2.43.2-matriz-mutaciones-y-sello-2026-09-20.md`](./relevo-cierre-v2.43.2-matriz-mutaciones-y-sello-2026-09-20.md)):

1. **La matriz de mutaciones del §10** (medida, una a una, con reversión verificada) — orden de trabajo en [`relevo-cierre-v2.43.2-matriz-mutaciones-y-sello-2026-09-20.md`](./relevo-cierre-v2.43.2-matriz-mutaciones-y-sello-2026-09-20.md).
2. **Commit de fase** y **tag anotado** (`v2.43.2-beta`, siguiendo la convención de `v2.43-beta` y
   `v2.43.1-beta`: el tag apunta al commit de **sellado** docs-only, para que la ref sellada no cite refs
   inexistentes).
3. **CI real medida** en `main` y en la ref del tag: `Python CI` (5/5, con `quality` y
   `auto-v2-durable-pg`) y `Release tag CI` (jobs requeridos + `certify`), y `Gitleaks`. Los jobs con
   **PG real** son donde se certifica la durabilidad de las reservas de salida del §7.6.
4. **Errata del diff** (ficheros y `+N/−M` reales), que se fija en el commit de fase.

---

## 13. Errata de esta pasada (método)

Se declara **antes** de que se reporte, porque es exactamente el tipo de error que el repo ya declaró dos
veces en su historia de CI:

**La primera verificación de `ruff` se hizo sin el flag `--config pyproject.toml`** y concluyó «2 avisos,
ambos preexistentes en `HEAD`» (verificado con `git show`). **Con la invocación de la casa** — la del
YAML, `uv run ruff check packages/py apps/api-python --config pyproject.toml` — el resultado era **7 avisos,
y los 7 eran de ficheros tocados por este parche**: el flag de config cambia la clasificación first-party
de `isort` y, por tanto, **qué bloques de imports considera desordenados**.

Se verificó la dirección del error con un **worktree limpio en `HEAD`**: la invocación de la casa sobre
`HEAD` da `All checks passed!`, luego los 7 eran introducidos por este trabajo y no preexistentes.
Corregido con `uv run ruff check packages/py apps/api-python --config pyproject.toml --fix` antes de
sellar, y re-verificado (`All checks passed!`).

**La lección, que va al relevo §4:** medir con la **invocación exacta del CI** (o, mejor, con el runner
que la **extrae del YAML**), nunca con una copia a mano — un parámetro de configuración ausente convierte
una medición en una medición de **otra cosa**. Es la misma familia de error que el runner versionado de
`v2.42.2` vino a cerrar.

---

## 14. Freeze (congelado, no tocar sin motivo)

- **Comportamiento de `AUTO_ENGINE_SIM_V2=0`**: debe seguir siendo `v2.39.x`.
- **Comportamiento de `AUTO_ENGINE_SIM_V2_GOVERNOR=0`**: byte-idéntico a `v2.43.1` **sin parada dura**.
  Cualquier cambio ahí es un hallazgo.
- **`v2_43_governor_evidence.py`**: byte a byte igual, y su `"bump"` **se queda** en `1.68.0-beta`.
- **`v0` del clasificador de régimen** (`discovery_market_regime`): inmutable, etiqueta a etiqueta.
- **La tabla del gobernador y sus umbrales** (`operational_governor.py`): **no se tocan** en este parche.
- **Sin migración**: Alembic head en `042_portfolio_reservations`.
- **Los gates PG** y los ficheros PG en el `--ignore` de los jobs offline: un skip mudo no certifica.
