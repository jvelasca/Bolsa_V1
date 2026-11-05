# Expediente de auditoría EXTERNA — DÍA-D monetario `2026-11-05`

> **Para quién es esto.** Para un auditor que **no ha participado** en el desarrollo y quiere
> intentar **refutar** las afirmaciones de este repositorio en vez de creerlas. El repositorio es
> **público** (`github.com/jvelasca/Bolsa_V1`), así que todo lo que se cita aquí es clonable.
>
> **Qué NO es.** No es un sello, no acredita rentabilidad y no sustituye la ventana PAPER real.
> Es el expediente con el que se publica **un resultado negativo** para que pueda ser atacado.

---

## 1. La afirmación central

> Con el motor AUTO tal como está en `2.11.183-beta`, la estrategia **no** supera la política de
> evidencia de rentabilidad por cuenta en el periodo **2021-2026**. El veredicto medido es
> **`REFUTED`**, y la refutación se sostiene por **dos medidas independientes**: el R por ciclo del
> replay y el **porcentaje de la cuenta** derivado de los flujos de caja de los fills.

El interés de auditar un **NO** es que el incentivo va en contra de quien lo publica: si el número
estuviera inflado a la baja por un error, el error perjudica al autor, no lo favorece.

---

## 2. Auditoría en 5 minutos (sin base de datos)

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git
cd Bolsa_V1
# OJO: el artefacto se midió con el árbol de `d2bcd16a` (versión en package.json:
# 2.11.183-beta). El tag `v2.88.183-beta` es ANTERIOR a la capa de evidencia y NO la contiene.
# El sello `2.11.184-beta` sí la contiene, pero se creó después de medir.
git checkout d2bcd16a

# 1. La aritmética de la capa: 20 tests puros, sin red ni PostgreSQL
uv run pytest packages/py/application/tests/test_dia_d_equity_evidence.py -q
#    esperado: 20 passed

# 2. Los umbrales de la política son DEFAULTS de código, no números escogidos a posteriori
grep -n "min_windows\|min_positive_window_pct\|min_net_return_pct\|max_drawdown_pct" \
  packages/py/application/src/bolsa_application/account_evidence_policy.py
#    esperado: min_windows=30, min_trades_total=100, min_positive_window_pct=60.0,
#              min_net_return_pct=0.0, max_drawdown_pct=15.0, min_excess_vs_buy_hold_pct=0.0,
#              holdout_pct=30.0, 2*(5+5)+2 = 22 bps ida+vuelta

# 3. El artefacto publicado es exactamente el que se midió
sha256sum -c SHA256SUMS.txt
```

Si (1), (2) o (3) fallan, este expediente queda **refutado** en su parte aritmética. Ese es el
objetivo del documento.

---

## 3. Afirmaciones falsables

Cada fila se puede atacar por separado. Ninguna depende de la palabra del autor.

### A1 — Los umbrales se fijaron ANTES de medir

* **Cómo se verifica:** `git log -1 --format="%h %ad %s" --date=iso 97a7c3c5`
  → `2026-11-05 17:10:06 +0100` (política, defaults incluidos).
  `git log -1 --format="%h %ad %s" --date=iso d8976c9f` → `2026-11-05 22:05:58 +0100` (capa que
  mide). El artefacto se generó **después** de que existiera la política, por ~5 h.
* **Cómo se refuta:** encontrar un commit **anterior** a `97a7c3c5` que ya contuviera estos
  umbrales, o demostrar que el artefacto se produjo antes de esa fecha.

### A2 — El signo no depende de la unidad (R vs %)

* **Medido en R** (misma corrida): `summary.expectancyR = -0,2037 R/ciclo`,
  `summary.measuredCycles = 192`, `summary.hitRate = 0,4167`.
  Breakeven de una estrategia con esa geometría de salida: `1/(1+1) = 50 %`; medido `41,67 %`.
* **Medido en % de cuenta**: `equityEvidence.netReturnPct = -42,13 %`.
* **Chequeo de orden de magnitud:** `-0,2037 × 192 ≈ -39,1 R`; con el tope de riesgo de `1 %` por
  operación del motor, el % de cuenta debe ser del mismo orden. Lo es (`-42,13 %`). Dos medidas
  que comparten *sólo* los ciclos, no la unidad.
* **Cómo se refuta:** encontrar que el artefacto `equityEvidence` no deriva de los mismos ciclos
  que `summary`, o que la curva se construyó con `R × constante` (ver §4: se construye con caja).

### A3 — La curva sale de los FLUJOS, no de una regla de tres sobre R

* **Cómo se verifica:** en `dia_d_equity_evidence.py`, `flows_from_fill_rows` toma `side`,
  `quantity`, `price` y el día de **cada fill**; `_curve` acumula
  `equity += -qty×price` (compra) o `+qty×price` (venta). No hay `R` en la función.
* **Cómo se refuta:** señalar cualquier ruta por la que un `R` entre en `_curve`, o un fill
  contado dos veces.

### A4 — El benchmark de «comprar y mantener» es honesto, no un espantapájaros

* **Medido**: `buyHold.pct = +72,87 %`, `symbolsMeasured = 20/20` (equiponderado, mismo watch y
  mismo tramo `2022-01-27 → 2026-10-26`). `excessPct = -115,00 %`.
* Un sólo símbolo sin barra en **ambos** extremos se descarta (no se promedia a medias), y se
  publica el recuento.
* **Cómo se refuta:** recalcular el benchmark desde `coverage.years[].watch` y las barras
  durables del repositorio y comparar; o demostrar que el watch del benchmark no es el de la
  estrategia (sería un benchmark más fácil de batir, y el veredicto empeoraría).

### A5 — Una ventana sin operación no cuenta como «ventana plana»

* **Medido**: `positiveWindows.measuredWindows = 122`, `positiveWindows = 52`,
  `negativeWindows = 70`, `positivePct = 42,62 %` contra un mínimo de `60 %`.
* Si los días sin movimiento entraran en el denominador, el `%` cambiaría; por eso `window_returns`
  los **excluye** explícitamente (`change == 0` no es ni positivo ni negativo).
* **Cómo se refuta:** recalcular con el criterio «plana = no negativa» y mostrar que `42,62 %`
  se convierte en un número que supera `60 %`. (Con 122 ventanas y 52 positivas, no lo hará.)

### A6 — El drawdown es *high-water-mark* y no se recorta

* **Medido**: `maxDrawdownPct = 47,50 %` contra un techo de `15 %`.
* **Verificación a mano:** el mínimo de la curva es `52 498,98` el `2022-10-19`; el pico previo es
  el capital inicial `100 000,00`. `(100000 - 52498.98) / 100000 = 47,50 %`.
* **Cómo se refuta:** encontrar un punto de la curva con un drawdown mayor desde su pico, o
  mostrar que el pico usado no es el máximo previo.

### A7 — La reserva fuera de muestra se elige por DÍAS, no por resultado

* **Medido**: `holdout.holdoutPct = 30`, `cutDay = 2025-03-17`, `inSampleDays = 85`,
  `outOfSampleDays = 37`. Dentro: `-44,95 %` (DD `47,50 %`). Fuera: `+5,67 %` (DD `14,38 %`).
* El corte son los **últimos 30 % de días con flujo**, en orden cronológico: no se puede mover la
  frontera mirando qué tramo sale mejor.
* **Honestidad sobre el hallazgo incómodo:** el tramo reciente es positivo y **no** se usa para
  rescatar la evidencia (son 37 días frente a 85, y el veredicto se emite sobre el conjunto).
* **Detalle declarado (baseline del tramo fuera de muestra):** el retorno del tramo fuera de
  muestra se calcula con **su primer punto como base**, es decir, el equity al **cierre** del
  primer día fuera de muestra; por tanto **no** incluye el movimiento de ese primer día. El tramo
  dentro de muestra sí arranca en el capital inicial. El efecto está acotado a un día de 37 y
  **no** interviene en el veredicto (el `holdout` se publica como contexto, no como umbral).
  Anotado como refinamiento pendiente, no como resultado.
* **Cómo se refuta:** mostrar que `cutDay` se eligió por resultado; o que el tramo fuera de
  muestra arrastra una base distinta de la que aquí se declara.

### A8 — Un hueco se declara, no se rellena con `0`

* **Medido**: `flowsMeasured = 2 197`, `flowsUnmeasured = 1 037`,
  `unmeasuredReasons = {"day": 1037}` (fills sin `created_at` y cuyo ciclo no aporta día).
* Efecto declarado: son el `32 %` de los fills y quedan **fuera** de la curva. **No** se les
  asigna el día del vecino (afirmaría una cronología inexistente) ni se cuentan como `0`
  (afirmaría que no movieron dinero).
* Consecuencia admitida: la curva **no** es el PnL completo, es la caja realizada de los fills
  con fecha. Por eso el veredicto se contrasta con la medida en R (A2), que **no** depende de esos
  fills.
* **Cómo se refuta:** mostrar que esos 1 037 fills, si se fecharan, **cambiarían el signo** del
  retorno. Con `-42 %` de retorno y `-39 R` de expectativa, la carga de la prueba es alta.

### A9 — El coste medido es MENOR que el mínimo que la política exige

* **Medido**: `realizedCostBps = 12,71` bps por lado (`|price/reference_mid - 1| × 10000`),
  frente a `22` bps ida+vuelta exigidos por la política → `FAIL`.
* **Interpretación honesta:** el motor simulado paga **menos fricción** de la que la política
  considera creíble. Eso hace que el `-42 %` sea un **techo optimista**: con más fricción, peor.
* **Cómo se refuta:** recalcular la fricción desde `reference_mid` de los fills y mostrar que el
  real era ≥ 22 bps (lo que **agravaría** el veredicto, no lo salvaría).

---

## 4. La curva de equity: construcción exacta

1. Cada fill aporta **caja con signo**: compra `-cantidad × precio`, venta `+cantidad × precio`.
2. Los flujos se agregan **por día** y se acumulan sobre `initialEquity = 100 000`.
3. Los días sin flujo **no** aparecen en la curva (no son ventanas medidas).
4. **Detalle de representación (declarado):** el primer punto de `curve` es el capital inicial
   (`100 000`, día `2022-01-27`) y el segundo es el cierre de **ese mismo día** tras sus flujos
   (`80 184,91`). Por eso `curvePoints = 123` con 122 ventanas: el punto 0 es el baseline, no un
   día extra. `holdout` deduplica días y no se ve afectado. Un lector que ignore esta nota
   contará un día de más; se declara aquí para que no parezca un error oculto.

**Verificación a mano de las dos cifras cabecera:**

```
retorno neto = 57 869,08594727125 / 100 000 - 1 = -0,42130914 → -42,13 %
drawdown     = (100 000 - 52 498,97939436854) / 100 000 = 0,47501 → 47,50 %
```

Cualquier calculadora reproduce esto desde `equityEvidence.curve` del artefacto publicado.

---

## 5. Lo que este expediente NO permite verificar (límites)

| No verificable sin el autor | Por qué |
| --- | --- |
| **Re-ejecutar el barrido `v2_93` completo** | Necesita PostgreSQL con las barras D1 durables (2021-10-27 → 2026-11-05) y `.env`. No viajan en el repositorio (`.gitignore: /operability_runs/`, `.env`). |
| **Que las barras de entrada sean las «reales»** | El replay es determinista sobre el `price_script` inyectado; la calidad del dato de origen queda fuera de este expediente. |
| **La ventana PAPER en vivo** | Se mide con el stack local. `CONFIRMED` sigue reservado a la ventana real; este expediente **no** lo emite. |
| **El coste de mercado real** | `reference_mid` es el mid del simulador, no un libro de órdenes real. |
| **La reproducibilidad byte a byte del artefacto** | El `sha256` publicado acredita **que no se alteró después**; no acredita que otra máquina produzca los mismos bytes. |

Lo que **sí** se puede auditar sin el autor: toda la aritmética (§2, §4), los umbrales, la
semántica `fail-closed` del código, el artefacto publicado y la trazabilidad de commits.

---

## 6. Gobernanza: qué se hizo con el resultado

* **AUTO sigue `OFF`.** No se relajó ningún umbral para que pasara; se publicó el `REFUTED`.
* **PAPER sigue `INCONCLUSIVE`.** Un replay no es evidencia PAPER.
* El veredicto **no** habilita operar: cierra la pregunta «¿hay evidencia de rentabilidad?» con
  un **no** medido, que es información operativa, no permiso.

---

## 7. Inventario

| Fichero | Qué es | `sha256` |
| --- | --- | --- |
| `README.md` | Este expediente | — |
| `v2_93_policy_equity_2026-11-05.json` | Artefacto completo del barrido (`v2.93`, 118 KB): cobertura, resumen, curva, ventanas, benchmark, holdout, evaluación por umbral y límites declarados | `91af8603205c8144297d4c3ee38031ed5ee0ad77da49b4f176192321b37eb5f8` |
| `SHA256SUMS.txt` | Manifiesto verificable con `sha256sum -c` | — |

Trazabilidad de commits (rama `fix/059-060-proveedores`):

| Commit | Qué acredita |
| --- | --- |
| `97a7c3c5` | Política de evidencia por cuenta y sus **defaults estrictos** (17:10) |
| `681eb9f9` | Migración `066` certificada contra PostgreSQL real y añadida a CI |
| `100b42e6` | Capa de evidencia monetaria (flujos → curva → umbrales) (20:52) |
| `d8976c9f` | Medición del barrido y veredicto `REFUTED` documentado (22:05) |
| `d2bcd16a` | Merge del PR #98 (capa + tests + documentación) |

Versión del artefacto: **`2.11.183-beta`** (`meta.bump` del `v2_93` en el momento de medir). El
sello `2.11.184-beta` **no** re-mide: cambia el código, no el resultado histórico. Los artefactos
conservan la versión con la que se produjeron.
