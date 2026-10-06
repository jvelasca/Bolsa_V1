# Spec — AUTO para usuario básico: HOME de seis preguntas y tarjeta de operación

> **AsOf:** 2026-10-06 · **Estado:** **DISEÑO CONGELADO** (no es código).
> **Base auditada:** `v2.88.73-beta` → `a30dadff`. Hallazgos: [auditoría pantalla por pantalla](./auditoria-ui-auto-pantalla-2026-10-06.md).
> **Padres:** [modelo semántico 1.0](./spec-auto-ui-semantic-model-1-2026-10-05.md) · [spec 3.0](./spec-auto-ui-refactor-3-0-2026-10-06.md) · [cockpit 1.0](./spec-auto-cockpit-usuario-basico-2026-10-05.md).
> **Naturaleza:** UI / producto. **`Δ AUTO decision/execution motor = 0`**. Sin contrato HTTP, sin Alembic, sin refactor de `auto_simulation_worker.py`.
> **Regla de compatibilidad:** mientras esta spec y el modelo semántico discrepen en qué es un hecho, **manda el modelo**. Esta spec manda en la presentación de la HOME y de la tarjeta. Las filas `ORDER` y `FILL` del glosario de la spec 3.0 §4 quedan superadas por el §2 de este documento.

Este documento congela cómo se ve AUTO para un usuario básico. No implementa pantallas.

## 0. Propósito

Congela:

- la HOME de `/auto` que responde seis preguntas, en orden, y después posición de cuenta, P&L, efectivo simulado y riesgo;
- la tarjeta de una operación, con las mismas ranuras siempre visibles;
- el banner permanente de simulación frente a XTB;
- el corte básico / avanzado.

No congela la implementación, el menú global de la aplicación, la certificación UI = libro, ni la auditoría E2E de los diecisiete casos de ciclo. Esos quedan para sellos posteriores.

## 1. Principios

Heredados, sin cambio:

| # | Principio |
| --- | --- |
| 1 | No re-derivar. La UI copia hechos ya producidos. |
| 2 | `UNKNOWN ≠ 0`. Un hueco es «Sin dato todavía», nunca `0` ni un tick. |
| 3 | Una operación = un `cycleId`. |
| 4 | Hecho ≠ contexto ≠ aprendizaje. |
| 5 | El view-model de la tarjeta es de solo lectura y determinista. |
| 6 | Resumen arriba, causalidad técnica bajo demanda. |

Añadidos de esta spec:

| # | Principio |
| --- | --- |
| 7 | La UI no se salta peldaños. Cada ranura se pinta aunque el hecho no exista. |
| 8 | Un peldaño alcanzado no marca el siguiente. Decidir no es comprar. Anotar una orden no es ejecutarla. Un fill no es materializar. Materializar es el único peldaño que mueve posición, caja y ledger del SIM. |
| 9 | Evidencia incompleta no dice «operación terminada». |
| 10 | El dinero de AUTO es simulado en toda la superficie, con independencia del tipo de cuenta activa. |

## 2. Glosario de primer nivel

Supera las filas `ORDER` y `FILL` de la [spec 3.0 §4](./spec-auto-ui-refactor-3-0-2026-10-06.md). El término técnico permanece en el detalle avanzado.

| Hecho | Primer nivel | Prohibido en primer nivel |
| --- | --- | --- |
| Decisión de cartera | «AUTO decidió comprar» / «vender» / «no hacer nada» | Tratar esa frase como compra hecha |
| `ORDER` | «Orden anotada» | «Orden enviada», «pendiente de ack» |
| Ejecución / `FILL` | «Precio aplicado» y «cantidad aplicada / pedida» | «Operación ejecutada», «T1 ejecutado» |
| Fill incompleto | «Ejecución parcial» | Pintar el total como si estuviera cubierto |
| Materialización | «Aplicado a la simulación» solo con traza de apply | Un tick copiado del fill |
| Posición de cuenta | «Posición en la cuenta simulada» | «Posición abierta · Hecho» derivado del fill |
| Caja / P&L de cuenta | «Efectivo simulado» / «Resultado de la cuenta» | Presentarlos como dinero real |
| `NO MEDIDO` | «Sin dato todavía» | Rellenar con `0` o con un check |

`cycleId`, `TOP_N`, `venue`, `PAPER_D_EXECUTE`, `ExecutionRouter`, `OrderIntent` y `Idempotency` siguen fuera del primer nivel.

## 3. HOME — seis preguntas

`/auto` sigue siendo la landing. En el primer pantallazo, en este orden:

| Pregunta | Respuesta visible |
| --- | --- |
| ¿AUTO está funcionando? | Funcionando / Esperando / Detenido / Sin dato todavía |
| ¿Qué está haciendo? | Analizando / Esperando / Comprando / Vendiendo / Sin dato todavía |
| ¿Qué activo? | Símbolo, o Sin dato todavía |
| ¿Qué ha decidido? | Comprar / Vender / No hacer nada / Sin dato todavía |
| ¿Qué ha ocurrido realmente? | Orden anotada / Ejecución parcial / Precio aplicado / Materializada / Sin dato todavía |
| ¿Qué dinero utiliza? | `SIMULACIÓN — DINERO VIRTUAL` |

Debajo, cuatro cifras de **cuenta** (no de un ciclo), cada una con su medición: posición actual, P&L, efectivo simulado, riesgo. Lo que el read-model no trae se declara «Sin dato todavía».

El resto (oportunidades, DÍA-D, evidencia, investigación) va detrás de «Ver actividad».

```text
AUTO
SIMULACIÓN — DINERO VIRTUAL

Funcionando
Analizando mercado…
AAPL
Sin operación          ← solo si la decisión durable es «no hacer nada»
                         si no hay traza: «Sin dato todavía»

Capital simulado       10.000 €
Posición               (cuenta, o Sin dato todavía)
Resultado              (cuenta, o Sin dato todavía)

[ Ver actividad ]
```

Reglas de copia:

- El estado crudo del motor no se traduce a «Funcionando correctamente» si no distingue funcionando, esperando y detenido. Si el DTO solo trae un estado opaco, la casilla 1 dice «Sin dato todavía» y el valor crudo queda en avanzado.
- Las casillas 2, 3 y 4 no inventan «Analizando AAPL» ni «Comprar». Sin símbolo o sin `PortfolioDecision` durable, dicen «Sin dato todavía».
- La casilla 5 copia el estado de cabecera de la operación en curso (§5). Sin ciclo en curso, dice «Sin operación en curso», que es vacío, distinto de error y de «Sin dato todavía».
- Carga, error, vacío y hueco de dato siguen siendo cuatro estados.

## 4. Tarjeta de operación

Una tarjeta por `cycleId`. Las ranuras están siempre. El estado de cada ranura es uno de: `Hecho`, `Pendiente`, `No ocurrió`, `Sin dato todavía`.

```text
AAPL                         COMPRAR
AUTO decidió comprar
10 acciones

Decisión        Hecho
Orden           Hecho
Ejecución       Hecho    10/10
Simulación      Sin dato todavía
Posición        (cuenta, rotulada como cuenta)
Dinero          (cuenta, rotulado como cuenta)

Cabecera según §5
```

Si solo existe la orden:

```text
Decisión        Hecho | Sin dato todavía
Orden           Hecho
Ejecución       Pendiente
Simulación      Sin dato todavía
Posición        Sin dato todavía
Dinero          Sin dato todavía

ORDEN PENDIENTE
```

Ranuras:

| Ranura | Qué copia | Qué no afirma |
| --- | --- | --- |
| Decisión | Traza durable de cartera, el día que exista. Hoy: «Sin dato todavía» | Que se haya comprado |
| Orden | Paso `ORDER` | Envío a XTB |
| Ejecución | Paso `FILL`: cantidad aplicada / pedida. Si la aplicada es menor, «Ejecución parcial» | Que el libro haya cambiado |
| Simulación | Traza de apply (posición, caja o ledger de **este** ciclo). Sin esa traza: «Sin dato todavía», nunca un tick | Un check copiado del fill |
| Posición | Hecho de cuenta SIM, con el rótulo «en la cuenta simulada» | «Esta operación ya abrió la posición», salvo ranura Simulación en `Hecho` |
| Dinero | Efectivo y P&L de cuenta SIM, misma regla | Dinero real, o P&L de esta operación si el cierre no está medido |

La posición y el dinero de la cuenta pueden mostrarse junto a la tarjeta. Llevan el rótulo de cuenta. Solo pasan a «de esta operación» cuando la ranura Simulación está en `Hecho`.

## 5. Estado de cabecera

Se toma la ranura más alta **con evidencia**, y solo esa:

| Evidencia más alta | Cabecera |
| --- | --- |
| Orden anotada, ejecución aún no | Orden pendiente |
| Fill con cantidad aplicada menor que la pedida | Ejecución parcial |
| Fill con cantidad aplicada igual a la pedida, sin apply | Precio aplicado |
| Apply de este ciclo | Materializada |
| Apply y cierre medido completo | Completada |

Medición incompleta, conflicto de evidencia o paso ausente en medio de la cadena: la cabecera es «Sin dato todavía». No «Completada». No «Abierto».

«Precio aplicado» no es «Materializada». «Materializada» no es «Completada» si el cierre no está medido.

## 6. SIM frente a XTB

En toda superficie de `/auto/*`, permanente, por encima del contenido:

```text
SIMULACIÓN — DINERO VIRTUAL
```

Si la sesión tiene conexión XTB (cotización o bridge), una segunda línea:

```text
XTB conectado: no implica ejecución real
```

El rojo `REAL — DINERO REAL` queda especificado para un camino LIVE futuro de AUTO. **No se pinta** en este diseño. El tipo de cuenta `live` no cambia el banner de AUTO a rojo: AUTO no ejecuta ese camino. El tipo de cuenta, si hace falta, se dice en avanzado («cuenta activa: real») sin recolorear la operativa automática como dinero real.

Un tipo de cuenta ausente no apaga el banner de simulación. El banner declara el modo del espacio AUTO. Lo no medido (capital, armado, kill switch) sigue en ámbar, en su propia línea, sin convertir el banner en verde tranquilizador sobre un hueco de cifra.

## 7. Dos niveles

**Básico.** Las seis preguntas, la tarjeta y el banner. Tipografía de primer nivel (14 px o más). Frases, no tablas densas.

**Avanzado**, plegado, bajo el rótulo «Detalle técnico»: Decision, Risk evaluation, Reservation, Order, ExecutionEvent, Fill, Materialization, Transaction, Position, Ledger, Reconciliation, Idempotency. Ahí viven los ids, `venue`, el monitor `/auto-monitor` y la reconciliación. El monitor no se borra. Deja de ser la puerta de entrada: se abre desde «Ver detalles» de la tarjeta y desde Sistema.

Cartera, Riesgo, Análisis y Sistema se quedan. Su primer nivel no repite la jerga del avanzado. Cartera deja de mostrar «Orden enviada — pendiente de ack» y «T1 ejecutado» en filas que el usuario lee como AUTO: esas frases pasan al detalle, traducidas como «Orden anotada» y «Precio aplicado».

## 8. Falsabilidad

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | La HOME muestra las seis respuestas sin entrar en Sistema. | Que activo, decisión o «qué ocurrió» solo existan en otra sección. |
| 2 | Sin símbolo o sin decisión durable, la casilla dice «Sin dato todavía». | Que la UI escriba «Analizando AAPL» o «Comprar» sin ese hecho. |
| 3 | La tarjeta pinta las seis ranuras siempre. | Que una orden sin fill oculte Ejecución, Simulación o Posición. |
| 4 | Un fill no marca Simulación ni Posición de la operación. | Un tick de simulación o «Posición abierta · Hecho» copiado de `FILL`. |
| 5 | La cabecera «Completada» exige apply y cierre medido. | Que «Abierto», «Operación ejecutada» o un fill completo digan terminada. |
| 6 | AUTO muestra siempre `SIMULACIÓN — DINERO VIRTUAL`. | Que una cuenta `live` pinte `DINERO REAL` en `/auto`. |
| 7 | XTB conectado no se lee como ejecución real. | Que el banner de AUTO calle esa frase cuando hay bridge, o que diga que AUTO envió la orden. |
| 8 | El primer nivel no usa «Orden enviada», «Operación ejecutada» ni «T1 ejecutado». | Que esas cadenas aparezcan fuera de «Detalle técnico». |
| 9 | `Δ motor = 0` y el contrato HTTP no cambia al implementar esta spec. | Que el diff toque el worker, umbrales, Alembic o `openapi.json`. |

## 9. Límites

- **`PortfolioDecision` durable:** abierta. La casilla de decisión permanece «Sin dato todavía» hasta que el spine la exponga. Esta spec no la crea.
- **Paso de materialización en el monitor:** no existe. La ranura Simulación permanece «Sin dato todavía» hasta que un read-model ya producido la copie. La UI no calcula el apply.
- **Posición y caja de cuenta** se copian del resumen de cuenta ya existente, con medición. No se recalculan en la tarjeta.
- **LIVE / ejecución real de AUTO:** fuera. El banner rojo no se implementa ahora.
- **Menú global** (Inicio, Mercado, AUTO, Mis operaciones, Cartera, Configuración) y el cajón Avanzado de la aplicación: fase posterior.
- **Certificación** de que la UI coincide con posición, ledger y P&L: fase posterior. Esta spec fija qué tendría que coincidir; no la ejecuta.
- **Diecisiete casos E2E** (compra, venta, parciales, duplicados, caídas, reconciliación, precio ausente, capital, límites): fase posterior. El criterio ya vale: evidencia incompleta no afirma cierre.
- **Refactor de `auto_simulation_worker.py`:** fuera.
- **No** se re-mide DÍA-D.
