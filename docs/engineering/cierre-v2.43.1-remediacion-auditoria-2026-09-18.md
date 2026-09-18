# Cierre V2.43.1 — Remediación de la auditoría externa de `v2.43-beta` (5 hallazgos) (2026-09-18)

**Versión:** `1.68.1-beta` (bump `1.68.0-beta` → `1.68.1-beta`) · **Sin migración** (el head de Alembic
sigue en `042_portfolio_reservations`) · **Tag de certificación:** `v2.43.1-beta` (ver §10).

**Alcance:** los hallazgos reportados sobre `v2.43-beta` en el hilo de la auditoría externa
([issue #62](https://github.com/jvelasca/Bolsa_V1/issues/62)) y los que salieron al leer **la cola que la
propia auditoría dejó declarada como pendiente** (`position_ledger.py` y el resto de
`portfolio_reservation.py`, más allá de `build_portfolio_risk_state`). **No** es un slice: no hay cambio de
arquitectura, no hay comportamiento nuevo de producto y **no se toca el gobernador**.

**Lo que NO se toca, declarado por adelantado:** los tres ejes (`MarketRegime` × `RiskRegime` ×
`OperationalState`), la tabla de decisión, el gate de ENTRADAS, sus umbrales y su evidencia
(`v2_43_governor_evidence.py` **no cambia ni un byte**: ver §8.2). El slice 1 se audita sobre la ref que ya
está sellada (`v2.43-beta`), y este parche **no lo mueve**.

---

## 0. Resumen: los cinco hallazgos

| ID     | Hallazgo                                                                                                                                                                                                          | Naturaleza               | Dónde                                                             | Estado  |
| ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------ | ----------------------------------------------------------------- | ------- |
| **R1** | El comentario de `release()` afirmaba que `reserved_cash` se puede sumar **sin filtrar por estado**, mientras la propiedad filtra por `.live()`                                                                   | Contradicción doc↔código | `portfolio_reservation.py:687-695`                                | CERRADO |
| **R2** | `gross_risk` **nunca** era `None`: el riesgo de posiciones **no medido** se sumaba como `0` y se publicaba un total **por debajo del real**                                                                       | **Seguridad financiera** | `portfolio_reservation.py:988-1028`, `auto_v2_entry.py:1220-1244` | CERRADO |
| **R3** | Un `side` no interpretable (`"hold"`, `"BUY"`) entraba al fold y caía en su `else`: **se doblaba como VENTA** (posible sobreventa declarada en el journal y **P&L irreal en memoria y en `equityIfClosed`**)      | **Seguridad financiera** | `position_ledger.py:95-107`                                       | CERRADO |
| **R4** | Una posición **PLANA** publicaba `averageEntry: 0.0` (residuo del redondeo a 4 decimales) o una entrada histórica rancia                                                                                          | Contabilidad de posición | `position_ledger.py:264-275`                                      | CERRADO |
| **R5** | `ReservationEvent` no validaba nada: un `kind` desconocido se aplicaba como **liberación** y un alta **sin reserva** se perdía; `replay()` podía reconstruir un libro con **menos** capital comprometido del real | **Seguridad financiera** | `portfolio_reservation.py:95-96`, `570-598`                       | CERRADO |

**Por qué R2/R3/R5 son de seguridad financiera y no cosmética.** Los tres tienen la misma forma: _un dato
que el sistema no puede interpretar se degrada hacia el lado permisivo_. R2 convierte "no sé cuánto riesgo
hay" en "hay 0" en el cálculo más importante del módulo (`gross_risk`); R3 convierte "no sé qué lado es"
en "es una venta" (del lado que **reduce** la posición y **fabrica** P&L); R5 convierte "no sé qué pasó con
esta reserva" en "el capital no estaba comprometido". En los tres, el sistema resultante es más permisivo
que la realidad y **no lo declara**.

---

## 1. R1 — El comentario de `release()` contradecía a la propiedad

**Reportado:** dos lectores distintos de `reserved_cash` (la propiedad y un `sum()` sobre `all()` sin
filtrar) daban el mismo número _hoy_, y el comentario invitaba a que un camino futuro se ahorrase el
filtro.

**Código (`portfolio_reservation.py:687-695`, tras el fix):**

```python
# Las dimensiones reservadas significan "comprometido AHORA": una liberación
# parcial las escala a lo que queda vivo y una total las deja a 0. Lo que se
# reservó originalmente queda en el evento de alta (historia inmutable), no en el
# estado del libro. Invariante de este camino: una reserva NO viva tiene sus
# dimensiones a 0 (``factor=0.0``). OJO: ese invariante lo cumple ``release``, no
# la propiedad: ``reserved_cash``/``reserved_risk`` filtran ADEMÁS por ``.live()``
# como cinturón de seguridad, porque cualquier camino de liberación futuro debe
# seguir escalando a 0 para que sumar ``all()`` sin filtrar no doble-cuente. El
# contrato lo garantiza la propiedad; no te "ahorres" el filtro por este comentario.
```

**El fix es de contrato, no de código de producción**: la propiedad **no se toca**. Lo que cambia es que el
comentario ya no promete lo que el código no promete, y el invariante queda **mordido por un test** que
recorre las **cuatro** vías de liberación (total, parcial, por fill, rollback) y afirma
`Σ all() == Σ live()` en cada una — de modo que el "camino futuro" que el comentario temía pone la suite en
rojo en vez de pasar desapercibido.

**Test que lo muerde:** `test_reserved_cash_matches_sum_all_vs_live_filtered`
(`packages/py/analytics/tests/test_portfolio_reservation_ledger.py:284`).

---

## 2. R2 — `gross_risk` nunca era `None` (el riesgo no medido se leía como 0)

**Reportado (auditoría externa):** en `build_portfolio_risk_state()`, el riesgo de las posiciones sin medir
puede tratarse silenciosamente como cero.

**Código antes** (`HEAD` = `v2.43-beta`):

```python
gross: float | None = None
if position_total is not None or reserved_risk is not None:
    gross = _round4((position_total or 0.0) + (reserved_risk or 0.0))
```

**Por qué era un bug y no una decisión.** `reserved_risk` es una **propiedad** que devuelve `float` (0.0 sin
libro), así que **nunca es `None`**: la condición era **siempre verdadera** y la rama "no se puede medir"
**nunca se tomaba**. Y con la guarda derribada, el `(position_total or 0.0)` hace el resto: es el patrón que
convierte "no lo sé" en "es cero" — medido, es el mismo patrón del bug de `total_samples` que ya se cerró en
`discovery_evidence.py`. La
consecuencia: `position_risk_total=None` (hay posiciones abiertas sin `risk_amount`) publicaba
`gross_risk = reserved_risk`, un **suelo** que un consumidor lee como total, justo en el caso que el sistema
declara no poder medir.

**Código después (`portfolio_reservation.py:1022-1028`):**

```python
gross: float | None = None
if position_total is not None:
    # Solo se publica un total cuando el riesgo de las posiciones está MEDIDO: un
    # ``position_total=None`` (hay posiciones sin ``risk_amount``) no puede sumarse
    # como 0 ni siquiera para publicar "solo lo reservado" — sería un suelo leído
    # como total. ``reserved_risk`` nunca es ``None`` (es 0 medido sin libro), así que
    # no decide si el cálculo es posible: solo forma parte del cálculo.
    gross = _round4(position_total + reserved_risk)
```

`net_risk` hereda el `None` (se calcula desde `gross`).

**Y el otro extremo del mismo eje, en el camino del tick (`auto_v2_entry.py:1220-1244`).** Hay un caso en
que `risk_used=None` **no** significa "no medido" sino "cartera vacía" (el snapshot deja `risk_used` a
`None` cuando no hay posiciones). Publicar `None` ahí habría degradado el `measurement` de un cero
**medido**, así que la traducción es explícita y **solo** se aplica cuando no hay posiciones sin medir:

```python
risk_used = getattr(snapshot, "risk_used", None)
if risk_used is None and unmeasured == 0:
    risk_used = 0.0
```

**Tests que lo muerden** (tres, uno de ellos en el camino real del tick):
`test_gross_risk_is_none_when_position_risk_is_unmeasured` y
`test_gross_risk_is_a_number_when_position_risk_is_measured_at_zero`
(`test_portfolio_reservation_ledger.py:582,604`) y
`test_tick_risk_state_is_unknown_when_a_position_risk_is_unmeasured`
(`packages/py/application/tests/test_portfolio_reservation.py`).

---

## 3. R3 — Un lado no interpretable se doblaba como VENTA

**Lo que pasaba.** `AppliedFillFact` validaba `execution_id`, pero **no** `side`. El fold de
`position_ledger.py` decide con un `if fact.is_buy: ... else: <venta>`: cualquier `side` que no fuese
exactamente `"buy"` caía al `else` y se trataba como **venta**. Medido con el código sellado, un
`side="hold"` produce una **reducción de posición con `realized_pnl` calculado contra un coste ajeno**,
publicado en `LedgerPosition` y usado por el worker para `equityIfClosed`/`_v2_last_exit_label`; la fila
ILEGIBLE **sí** quedaba declarada en `violations` (`oversell_without_position`), pero el fold ya había
fabricado un `realized_pnl` a partir de ella. Dirección del error: hoy **no** re-aplica fills al libro
físico (medido: no lo hace), pero el P&L de ese instrumento queda irreal durante el resto del tick.

**Código después (`position_ledger.py:98-107`):**

```python
if self.side not in (SIDE_BUY, SIDE_SELL):
    # Un lado que no es compra NI venta NO se puede doblar: el fold lo trataría
    # como una venta (reduciría la posición y realizaría P&L contra un coste que
    # no le corresponde). La fila no interpretable se declara al LEER
    # (``coerce_applied_fill_fact`` ⇒ rechazada ⇒ measurement), nunca se
    # representa como un hecho con un lado inventado.
    raise ValueError(
        f"AppliedFillFact exige side {SIDE_BUY!r}/{SIDE_SELL!r}: {self.side!r}"
    )
```

Con el tipo validado, el `else` del fold es **una venta por construcción** (queda dicho en el comentario
del fold, para que nadie añada ahí una rama que dependa de un lado no interpretable).

**Test que lo muerde:** `test_an_uninterpretable_side_cannot_be_represented_as_a_fact`
(`test_position_ledger.py:204`), que además de exigir el `ValueError` prueba que un `side` válido **sí** se
representa.

---

## 4. R4 — Una posición PLANA publicaba `averageEntry: 0.0`

**Código antes** (`HEAD`):

```python
remaining = max(0.0, quantity - realized_qty)
avg_entry = None
if quantity > _QTY_EPS and remaining > _QTY_EPS:
    avg_entry = round4(max(0.0, cost_basis) / remaining)
elif quantity > _QTY_EPS:
    avg_entry = round4(cost_basis / quantity) if cost_basis > 0 else None
```

**El bug está en el `elif`.** Para una posición **plana** (`remaining == 0`) publicaba
`cost_basis / quantity`: si el redondeo a 4 decimales dejaba un residuo positivo en `cost_basis`, eso daba
`0.0` y el JSON del libro afirmaba "la entrada era 0,0"; si el residuo era exactamente 0 daba `None`. Es
decir: **el mismo hecho (posición cerrada) tenía dos representaciones según un residuo de coma flotante**, y
un consumidor que marque contra `average_entry` marcaría contra **cero**.

**Código después (`position_ledger.py:264-275`):** una posición plana no tiene entrada —
`average_entry = None`, llegue por donde llegue (cierre limpio, cierre con residuo o sobreventa). La
historia de lo comprado vive en `fills`, no en un campo de la posición viva.

**Tests que lo muerden:** `test_flat_position_never_publishes_a_zero_or_stale_average_entry`
(`test_position_ledger.py:101`, cubre los tres caminos) y `test_full_exit_flattens_and_is_not_published_as_open`
(que ya existía y ahora afirma `average_entry is None` **y** `cost_basis is None`).

---

## 5. R5 — `replay()` podía infradeclarar capital

**Lo que pasaba.** `ReservationEvent` es la unidad de `replay()`: reconstruye el libro aplicando eventos. No
validaba **nada**:

- un `kind` desconocido (p. ej. `"reserv"`, o `None`) se aplicaba por la rama de **liberación**, es decir
  **relajaba** el libro;
- un evento de **alta** sin su `reservation` se aplicaba como un no-op **silencioso**.

En los dos casos el libro reconstruido declaraba **menos capital comprometido del real**: la dirección
peligrosa (el sistema creería tener presupuesto libre que ya está prometido). Un evento que no se puede
aplicar **no se puede representar**.

**Código después (`portfolio_reservation.py:95-96, 591-598`):**

```python
RESERVATION_EVENT_RESERVE: ReservationEventKind = "reserve"
RESERVATION_EVENT_RELEASE: ReservationEventKind = "release"

    def __post_init__(self) -> None:
        if self.kind not in _RESERVATION_EVENT_KINDS:
            raise ValueError(
                f"ReservationEvent exige kind {RESERVATION_EVENT_RESERVE!r}/"
                f"{RESERVATION_EVENT_RELEASE!r}: {self.kind!r}"
            )
        if self.kind == RESERVATION_EVENT_RESERVE and self.reservation is None:
            raise ValueError("ReservationEvent de alta exige la reserva completa")
```

Las constantes canónicas se exportan en `__all__` y se usan en `reserve()`, en `release()` y en `replay()`,
de modo que el productor de eventos no puede escribir un `kind` que el reproductor no sepa aplicar.

**Test que lo muerde:** `test_a_non_replayable_event_cannot_be_represented`
(`test_portfolio_reservation_ledger.py:346`): prueba que los no representables **no se pueden construir** y
que las formas válidas (alta con reserva; liberación sin reserva) **sí**.

---

## 6. Matriz de mutaciones medida

Cinco mutaciones, aplicadas **una a una** sobre el árbol final, medidas y revertidas (verificando el
contenido exacto tras cada reversión: los 5 suites afectados vuelven a **144 passed**). Ninguna fila es
opinión.

| #      | Mutación (revertir el fix)                                                                                                    | Código que restaura                               | Rojos | Tests que se ponen rojos                                                                                                                                   |
| ------ | ----------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- | ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **M1** | `gross_risk` vuelve al `if ... or reserved_risk is not None:` con `(position_total or 0.0) + (reserved_risk or 0.0)`          | el de `HEAD`                                      | **2** | `test_gross_risk_is_none_when_position_risk_is_unmeasured` (puro) + `test_tick_risk_state_is_unknown_when_a_position_risk_is_unmeasured` (camino del tick) |
| **M2** | `AppliedFillFact` deja de validar `side`                                                                                      | el de `HEAD`                                      | **1** | `test_an_uninterpretable_side_cannot_be_represented_as_a_fact`                                                                                             |
| **M3** | Vuelve la rama del residuo en el fold (`elif quantity > _QTY_EPS: round4(cost_basis / quantity) if cost_basis > 0 else None`) | el de `HEAD` (líneas 252-253)                     | **1** | `test_flat_position_never_publishes_a_zero_or_stale_average_entry`                                                                                         |
| **M4** | `ReservationEvent.__post_init__` deja de validar `kind` y la reserva del alta                                                 | el de `HEAD` (método inexistente)                 | **1** | `test_a_non_replayable_event_cannot_be_represented`                                                                                                        |
| **M5** | `release()` deja las dimensiones intactas en una liberación **total** (`factor = 1.0 if fully_released`)                      | simula el "camino futuro" que el comentario temía | **2** | `test_reserved_cash_matches_sum_all_vs_live_filtered` + `test_release_by_fill_full_closes_the_reservation_and_frees_the_budget`                            |

**Total: 5 mutaciones / 6 rojos / 0 verdes.** Nota de método honesta: la **primera** versión de M3 que probé
dividía por `quantity` en **todos** los casos y daba **4 rojos** — pero **no era el código pre-fix**, así que
la descarté y re-medí con la línea **exacta** de `HEAD` (`git show HEAD:...position_ledger.py`), que da
**1 rojo**. Una mutación más fuerte que el bug no mide el sensor del bug, mide otra cosa.

---

## 7. Verificación local medida (árbol final, mutaciones revertidas)

Comandos **exactos** de la casa, con los targets extraídos del YAML donde corresponde:

| Comprobación                                | Comando                                                                                                             | Resultado                                          |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| Estático (invocación de CI)                 | `uv run ruff check packages/py apps/api-python --config pyproject.toml`                                             | **All checks passed!**                             |
| Tipos                                       | `uv run mypy packages/py/domain/src … apps/api-python/src --follow-imports=silent`                                  | **487 ficheros, 0 issues**                         |
| Fronteras                                   | `uv run lint-imports --config packages/py/.importlinter`                                                            | **4 kept / 0 broken**                              |
| Suites afectadas                            | `uv run pytest` (position_ledger, reservation_ledger, portfolio_reservation, governor_gate, auto_v2_entry)          | **144 passed**                                     |
| Evidencia del gobernador (self-check)       | `uv run python apps/api-python/scripts/v2_43_governor_evidence.py --out governor.json`                              | **exit 0** (la tabla sigue gobernando: no se tocó) |
| Bloque `quality` de CI (extraído del YAML)  | `uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores`     | **1983 → 1991 passed (+8)**, 0 failed / 0 skipped  |
| Bloque `python` del tag (extraído del YAML) | `uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores` | **1994 → 2002 passed (+8)**, 0 failed / 0 skipped  |

**El delta `+8/+8` es la comprobación de cobertura.** Los ocho tests nuevos son
los 4 de `test_portfolio_reservation_ledger.py` (invariante de R1, los dos de `gross_risk`, el evento no
reproducible), los 3 de `test_position_ledger.py` (lado, plana con los tres caminos, posición abierta) y 1 de
`test_portfolio_reservation.py` (tick). Suben **exactamente 8** en los **dos** bloques de CI ⇒ **todos**
entran por las listas existentes (`packages/py/analytics/tests` va por pase de directorio en `quality`, y
`test_portfolio_reservation.py` va explícito) y ninguno queda fuera de la red — la deuda que `v2.42.2` tuvo
que cerrar a mano para `test_auto_daily_journal.py`.

---

## 8. Cambio observable declarado, y lo que NO es fix

### 8.1 Cambio observable (uno, y es el hallazgo R2)

`V2TickPlan.risk_state` es un read-model **en memoria**: no se serializa (no hay `to_dict` en la dataclass
del plan) y **no entra en el payload del journal**, que publica las tres dimensiones
(`marketRegime`/`riskRegime`/`operationalState`) y los motivos. Por tanto:

- **el journal del camino V2 no cambia** y la **byte-identidad con `AUTO_ENGINE_SIM_V2_GOVERNOR=0` sigue
  intacta** (los tests de byte-identidad del slice 1 pasan);
- lo único que cambia en `risk_state` es que `gross_risk` pasa de un **suelo** a `None` cuando hay
  posiciones abiertas **sin `risk_amount`**. Eso **es** la corrección de R2, no una regresión: el valor
  anterior era el bug.

### 8.2 Lo que NO es fix (declarado antes de que se reporte)

- **No se toca `v2_43_governor_evidence.py`.** Su campo `"bump": "1.68.0-beta"` **se queda como está**: el
  gobernador no cambia, el artefacto que la auditoría de `v2.43-beta` tiene delante **no se mueve**, y
  cambiar la etiqueta de versión de un JSON citado por el pack auditado solo añadiría ruido al diff. La
  versión del **paquete** sí sube (`1.68.1-beta`).
- **No se corrige** que `HALTED` no tenga productor propio, que `REGIME_EXIT`/`RISK_EXIT` no sean eventos
  del FSM, ni los umbrales sin calibrar: son **slice 2** de `AUTO-3` y ya están declarados en el §9 del
  pack de `v2.43`. Este parche no los toca ni los desmiente.
- **No se mide PG real** en la máquina del autor (motivo ya declarado en fases anteriores: el `connect` del
  DSN se cuelga). **No hace falta**: este parche **no toca ningún fichero PG** ni añade migración, así que
  la certificación de durabilidad de `auto-v2-durable-pg` cubre lo mismo que ya cubría en `v2.42.2`/`v2.43`.
- **R1 no cambia código de producción**: es un comentario y un test de invariante. Si alguien esperaba un
  cambio en `reserved_cash`, no lo hay y no debe haberlo.
- `PositionLedger` sigue siendo **read-model sin tabla propia**, y el `limit` de `list_applied` sigue siendo
  un suelo (deuda declarada de `v2.40.5`, no de este parche).

---

## 9. Cómo verificarlo (para el auditor)

```bash
# las 5 suites que muerden los hallazgos (herméticas, <1 s)
uv run pytest packages/py/analytics/tests/test_position_ledger.py \
              packages/py/analytics/tests/test_portfolio_reservation_ledger.py \
              packages/py/application/tests/test_portfolio_reservation.py \
              packages/py/application/tests/test_auto_v3_governor_gate.py \
              packages/py/application/tests/test_auto_v2_entry.py -q

# la matriz de mutaciones, una a una (cada una debe poner en rojo lo que dice la tabla del §6)
# M1: portfolio_reservation.py -> gross = _round4((position_total or 0.0) + (reserved_risk or 0.0))
# M5: portfolio_reservation.py -> factor = 1.0 if fully_released else remaining / total

# y que el gobernador NO se movió (byte-identidad con el flag OFF + tabla que sigue gobernando)
uv run python apps/api-python/scripts/v2_43_governor_evidence.py --out governor.json; echo "exit=$?"
```

El diff completo del parche es pequeño y legible a propósito: **8 ficheros, `+375/−12`** (3 de código, 4 de
tests, 1 de versión) más la documentación. No hay nada que "auditar de fondo" fuera de esas líneas.

---

## 10. Sello

**Commit de la remediación:** `<pendiente: se fija en el commit de sellado>` · **Tag anotado:**
`v2.43.1-beta` (apunta al **commit de sellado** docs-only, siguiendo la convención que estrenó `v2.43-beta`).

**CI real medida** (la certificación del sello; este documento **no** afirma un run que aún no existe):

| Ref                                | Workflow       | Resultado     | Run           |
| ---------------------------------- | -------------- | ------------- | ------------- |
| `main` @ commit de fase            | Python CI      | `<pendiente>` | `<pendiente>` |
| `v2.43.1-beta` @ commit de sellado | Python CI      | `<pendiente>` | `<pendiente>` |
| `v2.43.1-beta` @ commit de sellado | Release tag CI | `<pendiente>` | `<pendiente>` |

**Sobre la ref auditada.** `v2.43-beta` **no se mueve** (sigue siendo el slice 1 tal cual se selló, y su
auditoría en curso sigue siendo válida); esta remediación es una ref **nueva** y aditiva. Un hallazgo del
auditor sobre _este_ parche se reporta igual que los anteriores: `P0/P1/P2 · afirmación atacada · ruta:línea
· comando exacto · salida observada · ¿el §8 de este documento ya lo declara?`.
