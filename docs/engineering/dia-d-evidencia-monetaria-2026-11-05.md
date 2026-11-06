# DÍA-D · Evidencia MONETARIA 2021-2026 contra la política por cuenta (2026-11-05)

**Qué cierra:** el barrido `v2_93` medía el DÍA-D en **R por ciclo** y dejaba en `NOT_MEASURED`
todo lo que la política por cuenta exige en **porcentaje de la cuenta** (retorno neto, drawdown,
% de ventanas positivas, exceso sobre comprar y mantener, coste realizado y reserva fuera de
muestra). Esta capa mide esos umbrales con la **curva de equity de los flujos reales de los
fills** y emite un veredicto explícito, umbral a umbral.

**Artefacto:** `operability_runs/dia-d-auto/v2_93_policy_equity_2026-11-05.json`
(+ `.b.log` con la salida de texto).

**Comando (read-only, harness hermético `v2.86`/`v2.87` vía `v2_91`):**

```powershell
python apps/api-python/scripts/v2_93_dia_d_multi.py `
  --from-year 2021 --to-year 2026 --universe pit --json --cycle-detail --equity-evidence `
  --out operability_runs/dia-d-auto/v2_93_policy_equity_2026-11-05.json
```

`AUTO_ENGINE_SIM_V2_ATR_REQUIRED=1` (sin geometría sintética), `--venue paper`, edge declarado
`0.9`, `topK 5`, universo PIT por día. **Δ motor = 0**: no se toca el motor, ni umbrales, ni
allocation; todo es lectura.

## 1. Veredicto de la política (defaults estrictos, `isDefault=true`)

| umbral | exigido | medido | veredicto |
|---|---|---|---|
| `minWindows` | ≥ 30 | 122 | PASS |
| `minTradesTotal` | ≥ 100 | 192 | PASS |
| `minPositiveWindowPct` | ≥ 60 % | **42,62 %** | **FAIL** |
| `minNetReturnPct` | ≥ 0 % | **−42,13 %** | **FAIL** |
| `maxDrawdownPct` | ≤ 15 % | **47,50 %** | **FAIL** |
| `minExcessVsBuyHoldPct` | ≥ 0 % | **−115,00 %** | **FAIL** |
| `minRoundTripCostBps` | ≥ 22 bps | **12,71 bps** | **FAIL** |

**Veredicto global: `REFUTED`** (`failed:minPositiveWindowPct,minNetReturnPct,maxDrawdownPct,minExcessVsBuyHoldPct,minRoundTripCostBps`).
**Sin ningún umbral `NOT_MEASURED`**: la decisión ya no descansa en huecos.

Tramo medido: **2022-01-27 → 2026-10-26**, equity inicial 100 000 (misma unidad que el harness),
123 puntos de curva, 2 197 flujos de fill medidos sobre 192 ciclos cerrados.

## 2. Lectura honesta de cada número

* **Retorno neto −42,13 %** sobre ~4,7 años, coherente con el R medido en la misma corrida:
  expectativa **−0,2037 R/ciclo** × 192 ciclos = **−39,1 R**; con el tope de riesgo del 1 % por
  operación del motor, el orden de magnitud es el mismo. Dos medidas independientes (R y caja)
  coinciden en signo y en tamaño.
* **Drawdown máximo 47,50 %** contra un techo del 15 %: la caída se mide desde el pico
  (high-water-mark) de la curva de caja, no desde el depósito inicial.
* **Ventanas positivas 42,62 %** (52 de 122 días con movimiento). Un día **sin** operación
  cerrada **no** cuenta como ventana plana: no entra en el denominador.
* **Comprar y mantener +72,87 %** a partes iguales sobre el mismo watch y el mismo tramo
  (20/20 símbolos con barra en ambos extremos) ⇒ exceso **−115,00 %**. La estrategia no solo
  pierde: pierde contra no hacer nada.
* **Coste realizado 12,71 bps por lado** (media de `|price/reference_mid − 1| × 10000` sobre los
  fills que declaran `reference_mid`) contra un mínimo de 22 bps ida+vuelta exigido por la
  política. Es decir: el replay **no** está pagando la fricción mínima que la política considera
  creíble, así que su resultado —ya negativo— es un **techo optimista**, no un suelo.
* **Fuera de muestra (últimos 30 % de días, corte 2025-03-17):** dentro −44,95 % (DD 47,50 %),
  fuera **+5,67 %** (DD 14,38 %). El tramo reciente es plano/levemente positivo y **no** rescata
  la evidencia: son 37 días frente a 85, y el veredicto se emite sobre el conjunto.

## 3. Huecos declarados (no rellenados con 0)

* **1 037 de 3 234 fills sin día**: el fill no trae `created_at` y su ciclo tampoco entra en el
  respaldo por día de entrada. Quedan **fuera** de la curva y se publican atribuidos
  (`unmeasuredReasons: {"day": 1037}`). No se les asigna un día por orden de inserción: eso
  afirmaría una cronología que el artefacto no tiene.
* **La curva es de CAJA realizada**: una posición viva al cierre queda como caja salida (no se
  marca a mercado) y no se convierte a la divisa de la cuenta. Se declara en `caveats`.
* `startDay` = **2022-01-27** aunque el barrido empiece en 2021: 2021 no produjo ningún ciclo
  medible (universo PIT sin elegibles en la ventana), y un año sin ciclos no es una ventana.

## 4. Consecuencia de gobernanza

* **AUTO sigue OFF.** El DÍA-D ya no está `NOT_MEASURED`: está **`REFUTED`** por retorno,
  drawdown, ventanas positivas, exceso contra el benchmark y coste insuficiente.
* Se **confirma** la decisión de la corrida anterior (no acreditar los umbrales de la política):
  ahora hay dos medidas independientes que la sostienen, no una inferencia.
* Lo que esta capa **no** hace: no toca el motor, no cambia umbrales y no convierte un replay en
  evidencia PAPER (`CONFIRMED` sigue reservado a la ventana real).

## 5. Contrato de la capa (para quien la consuma)

* `packages/py/application/src/bolsa_application/dia_d_equity_evidence.py`
  (`dia-d-equity-evidence-v1`): flujos ← fills (`side`, `quantity`, `price`, día), curva,
  retorno neto, drawdown, ventanas, benchmark, holdout, coste realizado y
  `evaluate_evidence_policy` (PASS / FAIL / NOT_MEASURED por umbral).
* Un umbral **no medido** deja el global en `NOT_ACCREDITED`; uno **incumplido** lo deja en
  `REFUTED`. Nunca hay aprobación parcial.
* 20 tests puros en `packages/py/application/tests/test_dia_d_equity_evidence.py` (sin red, sin
  PostgreSQL), incluido el caso `Decimal` que vaciaba la curva entera.
