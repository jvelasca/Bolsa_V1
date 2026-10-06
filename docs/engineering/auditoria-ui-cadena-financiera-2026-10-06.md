# Auditoría UI — cadena financiera en el primer nivel de AUTO (2026-10-06)

> **AsOf:** 2026-10-06 · **Base:** `v2.88.73-beta` (núcleo financiero congelado).
> **Naturaleza:** UI / view-model. **`Δ AUTO decision/execution motor = 0`**. Sin cambio de contrato HTTP, sin Alembic, sin tocar `auto_operational_monitor.py` ni el worker.

## Pregunta

¿El primer nivel de AUTO presenta como operación hecha, posición o dinero algo que sólo es una reserva, una orden anotada o un precio?

## Hallazgos

El DTO del monitor no distingue «reserva» de «cantidad neta»: si no hay cierre, `closed` vale `false` en ambos casos. La UI leía eso como «Abierto» y lo contaba en «N abiertas».

En la historia, el primer nivel decía más que el hecho:

| Etapa | Hecho durable | Lo que decía la UI |
| --- | --- | --- |
| `ORDER` | Registro `auto_entry_order` (pedido vs cantidad aplicada). No es un envío a XTB. | «Orden enviada» |
| `FILL` | Precio y cantidad. No cierra la cadena. | «Operación ejecutada» |
| `POSITION` | No hay paso propio. Copiaba el estado de `FILL`. | «Posición abierta · Hecho» |

`DECISION` ya se declaraba `NOT_MEASURED`. `EXIT` ya se plegaba en `SETTLEMENT`. El semáforo de realidad ya dice dinero virtual. CARTERA ya avisa DEMO.

El copy de primer nivel hablaba de broker como si AUTO lo usara (descripción de Sistema, texto de la operación, hint de navegación).

## Corrección (este slice)

Sólo texto y plegado. Los ids técnicos no cambian.

- `ORDER` → «Orden anotada». `FILL` → «Precio aplicado».
- `POSITION` se pliega en `FILL` mientras no exista un paso `POSITION` propio. La fila de precio dice que el precio no afirma la posición ni el dinero de la cuenta.
- Estado visible del ciclo, leído de los pasos que ya trae el DTO:
  - medición incompleta → «Sin dato todavía»
  - cerrada con medición completa → «Cerrada»
  - `FILL` alcanzado y no cerrada → «Precio aplicado»
  - `ORDER` alcanzado y sin fill → «Orden anotada»
  - si no → «Apartada»
- El contador de la HOME sólo suma ciclos en «Precio aplicado».
- El primer nivel deja de decir que AUTO usó un broker. El bloque experto «Broker / ejecución» sigue plegado en Sistema.

## Residuo declarado

El monitor no expone materialización, ledger ni caja como pasos propios. La UI no los inventa. «Precio aplicado» no es una posición ni dinero movido.

Fuera de este slice: `OperationsPanel`, «T1 ejecutado» y «Orden enviada — pendiente de ack» en el escritorio de trading. CARTERA los compone y ya declara DEMO. El worker no se refactoriza.
