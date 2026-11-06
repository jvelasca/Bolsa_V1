# Dictamen de cierre del plan C-1 — lecturas tipadas, `readGaps` y exactly-once multiproceso

**Fecha:** 2026-11-03 · **Rama:** `fix/059-060-proveedores` · **HEAD auditado:** `e93131e4`
**Naturaleza:** **registro de aceptación de un dictamen externo**. No modifica código, tests, contrato,
CI, migraciones, `package.json`, `CHANGELOG`, `PROJECT_STATE.md` ni tags. No re-mide nada: cita la
medición publicada en la evidencia y la ancla a los commits que la contienen.
**Veredicto:** **PLAN CERRADO**.

---

## 0. Qué es este documento

El dictamen que aquí se registra cierra **C-1** (lecturas tipadas y `readGaps`) y las dos deudas que
arrastraba —la documentación del contrato y el exactly-once multiproceso—, y da por suficiente la
separación de la secuencia de commits entre cambio funcional, documentación, corrección de test y
registro de evidencias.

Lo que este acto añade no es una medición nueva, sino la **fijación del estado de referencia
auditado**: qué SHA se da por bueno, qué evidencia lo respalda y qué queda explícitamente fuera.

---

## 1. Cadena de commits cubierta

Los cinco commits están en `fix/059-060-proveedores`, sobre `d3236b5c`, y se dan por buenos en su
reparto funcional:

| SHA | Asunto | Papel en la cadena |
| --- | --- | --- |
| `544b9d05` | `fix(auto,web): C-1 publica readGaps y la ficha distingue «no leído» de «sin propuesta»` | Cambio funcional: lector durable, artefacto, DTO, contrato generado y superficie de UI |
| `53e72e9d` | `docs(evidence): documenta el contrato readGaps de la cadena (C-1)` | Documentación del contrato en el addendum §10 de `v2.88.131` |
| `8545b936` | `test(auto): el exactly-once multiproceso espera la materialización real` | Corrección del test (no del producto) |
| `49b32f2f` | `docs(evidence): diagnostica la deuda multiproceso y corrige «solo Windows»` | Diagnóstico reproducible del defecto de sincronización |
| `e93131e4` | `docs(evidence): publica el cierre del flaky de lab discovery` | Registro de evidencia del flaky y de su red de determinismo |

Un commit funcional, dos documentales, uno de test y uno de cierre de evidencia: ningún commit
mezcla bloques distintos, y ninguno de ellos toca DS-1, O-2, H-1 ni GP-V190.

---

## 2. Dictamen por bloque

| Bloque | Dictamen |
| --- | --- |
| C-1 — lecturas tipadas y `readGaps` | **Cerrado** |
| Contrato `readGaps` y compatibilidad | **Cerrado** |
| PostgreSQL real: 6 pruebas | **6/6** |
| Exactly-once multiproceso | **Corregido y verificado** |
| Diagnóstico de `lab-discovery` flaky | **Documentado** |

Las seis pruebas PostgreSQL de C-1 son las de
`apps/api-python/tests/test_auto_chain_read_gaps_pg.py`, ejecutadas con
`AUTO_CHAIN_READ_GAPS_PG_REQUIRED=1` y **sin ningún `skipped`**: con ese gate, un skip cuenta como
fallo duro, de modo que «6/6» significa seis ejecuciones reales contra el motor, no seis tests
recolectados.

---

## 3. Los dos puntos que sostienen el cierre

### 3.1 C-1 queda mucho mejor certificado

La ejecución con `AUTO_CHAIN_READ_GAPS_PG_REQUIRED=1` y seis pruebas sin skips cierra la principal
carencia de integración PostgreSQL señalada en la auditoría anterior: hasta entonces el hueco de
lectura solo estaba cubierto con dobles. El contrato, además, queda fijado en cuatro reglas duras:

- **`unmeasured` no equivale a `not_proposed`.** Un ciclo cuyas propuestas no se pudieron leer se
  atribuye como `unmeasured` con su motivo (`proposals_unreadable`), nunca como «nació sin
  propuesta». Es la afirmación contraria a la del hueco real.
- **Un fallo de lectura no degrada automáticamente el veredicto del journal.** Un veredicto ya
  sellado (`exact`) se mantiene; el hueco viaja por su propio canal (`readGaps`). La atribución solo
  cambia cuando lo que falta es la medición del enlace, no cuando el journal ya la declaró.
- **Los servidores anteriores siguen siendo compatibles.** La clave es aditiva y opcional:
  `schemaVersion` no sube, un cliente antiguo que la ignore no cambia de comportamiento y un
  servidor antiguo que no la envíe no hace que la UI invente un fallo.
- **Los motivos desconocidos no desaparecen silenciosamente.** Una etapa o un motivo que el cliente
  no conoce se conserva y se muestra en crudo, en vez de descartarse.

La lectura va sellada en `SAVEPOINT` con uno por etapa, de forma que un fallo DÍA-D no vacía el
enlace de propuestas ni al revés — y esa protección está probada por mutación: al retirar
`async with session.begin_nested():` de `read_daily_proposals`, el test falla con
`InFailedSqlTransaction`.

### 3.2 El arreglo multiproceso corrige el test, no el comportamiento productivo

Esta distinción es la que impide leer el verde como una certificación nueva del mecanismo de
reservas. El test suponía una atomicidad que el camino real **no** garantiza:

| Paso | Código | Transacción |
| --- | --- | --- |
| 1 | `_persist_position(...)` → `PostgresSimAutoPositionStore.upsert` | COMMIT de `sim_auto_positions` |
| 2 | `_v2_release_reservations_for_fill(...)` → `store.release(...)` | COMMIT de `portfolio_reservations` |

Entre esos dos commits existe un estado durable y legítimo: hay posición y la reserva sigue `OPEN`
con `released_qty = 0` y `remaining_qty = quantity`. El bucle anterior lo tomaba por «carrera
resuelta» y assertaba acto seguido `released_qty > 0`: de ahí el `assert Decimal('0') > 0` del run
[`41594625695`](https://github.com/jvelasca/Bolsa_V1/actions/runs/41594625695), fallido en 5,68 s
sobre Linux. En el sentido opuesto, con un fill completo la reserva queda `RELEASED_BY_FILL` con
cola cero y el proxy no rompía nunca: agotaba los 80 s de presupuesto y por eso la corrida local
duraba 115 s.

La condición nueva espera al hecho que el test realmente asserta:

```python
if released > 0 and released + remaining == requested:
    return True
```

- `released > 0` exige al menos una trancha materializada.
- `released + remaining == requested` exige contabilidad cerrada, que el libro mantiene en cada
  liberación —también con `released = 0`—, así que no se espera un estado que el producto no
  prometa.

No se tocaron reservas ni fills para adaptar el producto a una expectativa incorrecta del test. La
ventana entre los dos commits es deliberada: el espejo de posición es reconstruible, su commit
propio no tumba el turno y un crash intermedio lo reconcilia el arranque. Verificación publicada:
**5/5 corridas en verde, ~36 s cada una** (antes 115 s y con fallo intermitente en CI), más una
prueba pura que rechaza explícitamente el estado intermedio
`(positions=1, OPEN, released=0, remaining=qty)`.

---

## 4. Riesgos residuales registrados

1. **Cobertura de `readGaps`.** Una etapa futura sin lector tipado podría quedar sin declarar. Toda
   etapa nueva de la cadena debe incorporar su contrato de lectura y sus pruebas; el campo no se
   hereda por el hecho de existir.
2. **FASE 2: dwell de 30 segundos.** Se mantiene fijo, y es razonable que lo esté por su función de
   protección contra reservas duplicadas: es la ventana en la que un reemplazo defectuoso apilaría
   una segunda reserva o una segunda orden. No se convierte en configuración ajustable sin una
   prueba específica de seguridad que demuestre que acortarlo no debilita el invariante.
3. **Exactly-once.** El test queda corregido y más rápido, pero la corrección de la prueba **no** es
   una nueva certificación del mecanismo productivo de reservas. Su garantía sigue siendo la que ya
   estaba documentada; lo que cambia es que la prueba deja de fallar por una expectativa propia.

---

## 5. Fuera de alcance

- **DS-1, O-2, H-1 y GP-V190 no se mezclan con esta cadena.** Su código y sus pruebas siguen en el
  árbol de trabajo, sin commitear, y no forman parte del estado que este dictamen acepta. El
  material PostgreSQL que acompaña a esas condiciones (`scan_job_lease.py`,
  `test_scan_job_lease_pg.py`, `test_estudio_daily_proposal_savepoint_pg.py`) pertenece a su bloque
  y se registrará cuando ese bloque se cierre.
- No se reabre C-1. El estado de referencia auditado es `e93131e4` sobre los cinco commits de §1, y
  se conserva como tal.
- Una etapa posterior no puede invocar este documento para dar por cubierta una etapa nueva sin
  lector tipado (ver riesgo 1).

---

## 6. Anclas

Evidencia publicada, ya versionada, que sostiene cada afirmación de este dictamen:

| Documento | Qué respalda |
| --- | --- |
| [`evidence/certificacion-pg-c1-ds1-o2-2026-11-03/README.md`](evidence/certificacion-pg-c1-ds1-o2-2026-11-03/README.md) | Matriz condición → test → resultado, pruebas por mutación, cableado de CI y suites completas |
| [`evidence/certificacion-pg-c1-ds1-o2-2026-11-03/deuda-multiproceso.md`](evidence/certificacion-pg-c1-ds1-o2-2026-11-03/deuda-multiproceso.md) | Diagnóstico del defecto de sincronización, hipótesis descartadas y las 5/5 corridas del arreglo |
| [`evidence/certificacion-pg-c1-ds1-o2-2026-11-03/flaky-lab-discovery.md`](evidence/certificacion-pg-c1-ds1-o2-2026-11-03/flaky-lab-discovery.md) | 84 ejecuciones sin reproducción y el test de determinismo que sustituye la duda abierta |
| [`evidence/v2.88.131/README.md`](evidence/v2.88.131/README.md) §10 | Contrato de `readGaps`: semántica por etapa, compatibilidad y propagación |

Ninguno de esos documentos se modifica aquí; este registro solo los cita como ancla.
