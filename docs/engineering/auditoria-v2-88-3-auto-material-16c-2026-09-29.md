# Auditoría externa — `v2.88.3-beta` / `AUTO-MATERIAL-16c` (re-sello de la costura del journal): `APROBADO`

> **Objeto auditado:** tag anotado **`v2.88.3-beta`** (objeto `66f47cf8` → commit `0038adfc`) ·
> **Versión:** `2.11.3-beta` · **Fase:** `AUTO-MATERIAL-16c` (RE-SELLO 3) · **AsOf:** 2026-09-29 ·
> **Alembic head:** `046_fill_reference_mid` (**sin migración**) · **Auditor:** externo, **desde GitHub**
> (`github.com/jvelasca/Bolsa_V1`, repo **público**, clon sin credenciales).
> **Veredicto:** **APROBADO — 0 bloqueantes.**
> **Precisión del veredicto:** `v2.88.3` **corrige y certifica** la **validación del ciclo de
> reservas/journal**; **NO cierra** toda la deuda funcional de AUTO ni **`P3-2`/`P3-3`**.

---

## 0. Alcance y método

El auditor trabaja sobre el **objeto vigente** de la serie `v2.88` — el **RE-SELLO 3** / `AUTO-MATERIAL-16c` —
y no sobre los tres tags anteriores, que quedaron **rojos por causas distintas y se conservan**. La auditoría
es especialmente cuidadosa porque la serie arrastra **tres rojos consecutivos** y el objeto vigente es el
primero que cierra el último: el **CI del propio tag queda finalmente VERDE**.

**Regla de la casa aplicada:** ninguna cifra sin comando; un hueco se declara **`NO MEDIDO`**, jamás un `0`
fingido.

---

## 1. La secuencia `v2.88` → `v2.88.1` → `v2.88.2` → `v2.88.3`

La secuencia importa, y el auditor la reconstruye explícitamente:

```text
v2.88      OBS-14  cierre de turno / fail-open        🔴 inicialmente
v2.88.1    carrera concurrente                        🔴
v2.88.2    costura del journal                        🔴
v2.88.3    corrección de la costura                   🟢
```

Los **tres rojos anteriores se conservan como evidencia histórica**: no se borran ni se maquillan. El
objeto vigente es **`v2.88.3-beta`**.

Ciclo que la serie acredita:

```text
fallo → causa → corrección → regresión → nuevo CI
```

---

## 2. El fallo de `V2.88.2` **NO** estaba en el motor de producción

Punto fundamental del informe:

`V2.88.2` había añadido al motor:

```python
self._v2_owned_reservations.add(...)
```

pero uno de los **tests de costura** construía artificialmente el worker con:

```python
object.__new__(AutoSimulationWorker)
```

y por tanto **no ejecutaba `__init__`**. La costura declaraba `_v2_reservations`, `_v2_reservation_blocked`,
`_v2_reservation_carryover`… pero **no** `_v2_owned_reservations` ⇒ `AttributeError` en **seis** tests.

**Diagnosis del auditor (correcta):** el **motor no estaba roto**; estaba **incompleta una costura de
validación** que simulaba el worker sin inicializarlo. En producción `__init__` siempre corre.

---

## 3. La solución aplicada es la correcta

El informe contrasta las dos salidas posibles:

| | Solución incorrecta | Solución aplicada |
| --- | --- | --- |
| Mecanismo | `getattr(self, "_v2_owned_reservations", set())` | `worker._v2_owned_reservations = set()` **en el doble de test** |
| Efecto | El motor se vuelve **tolerante a un estado imposible** | La costura artificial **declara explícitamente el estado que necesita** |
| Riesgo | **Esconde** un fallo real de inicialización y **reintroduce el fail-open** de las fases previas | Ninguno: el motor sigue estricto |

**`🟢 Mucho mejor`** — y evita reintroducir precisamente el comportamiento **fail-open** que se venía
eliminando en las fases anteriores.

---

## 4. `M252` es una buena prueba de regresión

La mutación nueva elimina conceptualmente `persist reservation + register owner` y deja `reservation
persisted / owner = missing`:

```text
M252 → DETECTADA            matriz 252 / 252 mutaciones medidas
```

y la cazan **seis** tests relacionados con: persistencia de reservas · reconciliación · aislamiento entre
sesiones · liberación de huérfanas · dos turnos consecutivos.

**No es** «añadimos un test y pasa»: se demuestra que **si se elimina la propiedad, la batería realmente
cae**. `🟢 Sólido`.

---

## 5. El CI del tag `V2.88.3` está VERDE

Éste es uno de los cambios más importantes respecto a las versiones anteriores:

| | |
| --- | --- |
| Run | `Release tag CI` [`36558405748`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36558405748) |
| Resultado | **SUCCESS**, **primera pasada** (`attempt 1`), **8m29s** |
| Jobs | 10 jobs reales en verde; `playwright` integrado **skipped por diseño** |

Job `python` (el que provocó el rojo de `V2.88.2`):

```text
ruff     🟢
imports  🟢   (Contracts: 4 kept, 0 broken.)
mypy     🟢   (508 ficheros)
pytest   🟢   3040 passed · 37 skipped · 0 failed
```

`🟢 Este punto queda cerrado.`

---

## 6. Queda demostrada la parte realmente importante del ciclo

El CI de `V2.88.3` mantiene verdes:

- **`lifecycle-pg`** — crash/recovery · **tres sesiones concurrentes** sobre la misma señal · golden day ·
  aislamiento de cuenta;
- **`decision-spine`** — **604 passed**;
- **`a7-gate`** — **7 passed**.

La evidencia indica que la **carrera concurrente** que producía diferencias de capital reservado **ya no
reaparece**. `🟢` Esto es más relevante que el simple `pytest` verde: hay simultáneamente **correctitud +
concurrencia + recovery**.

---

## 7. El motor de `V2.88.3` está intacto respecto a `V2.88.2`

El diff de `V2.88.3` **no** modifica `auto_simulation_worker.py` ni la lógica de producción. La única
modificación funcional del re-sello es la **declaración del estado en la costura de test**, junto con `M252`
y documentación.

```text
V2.88.2 motor  ==  V2.88.3 motor
```

Por tanto, la certificación de `V2.88.3` significa, principalmente: **el motor que ya había superado las
pruebas funcionales de `V2.88.2` queda ahora validado por la batería completa de CI sin el falso rojo de la
costura.**

---

## 8. `OBS-14` queda correctamente cerrada

La cadena sobre reservas queda acreditada:

```text
reserva → owner → session → turn close → reconcile → only_ids
```

La evidencia declara **`OBS-14 = CLOSED`** pero **`OBS-14.b = OPEN`**. **La distinción es correcta.**

---

## 9. `OBS-14.b` sigue siendo importante

`OBS-14.b` afecta al **barrido de arranque sin ventana de gracia**. **No está cerrado.**

Aunque el cierre de turno esté correctamente acotado, queda una cuestión de **recuperación/arranque** que
debe comprobarse en condiciones reales: AUTO trabaja precisamente con `reservations + turns +
restart/recovery`, y un sistema puede tener `close()` correcto y `startup()` **incorrectamente agresivo**.

```text
OBS-14   🟢   NO implica   OBS-14.b 🟢
```

---

## 10. `OBS-15` es ahora el riesgo funcional más importante de esta rama

Declarado `OBS-15` **MEDIUM / OPEN**: el techo de **1000 filas `APPLIED`** que potencialmente puede
**detener el motor**. Y una frase especialmente importante del registro:

> **la madurez de la cuenta real está `NO MEDIDA`.**

Por tanto:

```text
CI                 🟢
tests              🟢
concurrencia       🟢
recovery           🟢
cuenta PAPER/real prolongada   🔴 NO MEDIDA
```

**Es exactamente el tipo de problema que los tests offline no pueden cerrar.**

---

## 11. Conexión con el objetivo original: AUTO real

La infraestructura de AUTO está cada vez mejor validada, pero **falta evidencia de longevidad operacional
real**:

```text
                AUTO
        ┌───────┴───────┐
        ▼               ▼
     startup          runtime
        │               │
        ▼               ▼
     recovery        reservations
        │               │
        └───────┬───────┘
                ▼
             close
                │
                ▼
          reconciliation
```

La mayoría está muy bien cubierta; lo que sigue **sin medirse** es:

```text
long-running account → 1000 APPLIED → comportamiento real
```

---

## 12. `P3-2` / `P3-3` siguen sin estar cerrados

No cambia en `V2.88.3`: el artefacto multianual de `v2.86`/`v2.87` **no sirve como evidencia de
estrategia** y **exige RE-EJECUCIÓN**, por lo que **no mueve** `P3-2` ni `P3-3`.

### Tabla de estado emitida por el auditor

| Objetivo | Estado |
| --- | --- |
| Motor AUTO | 🟢 |
| Reservas | 🟢 |
| Propiedad de reservas | 🟢 |
| Reconciliación | 🟢 |
| Concurrencia | 🟢 |
| Crash/recovery | 🟢 |
| CI completo | 🟢 |
| `M252` | 🟢 |
| `OBS-14` | 🟢 |
| `OBS-14.b` | 🟠 |
| `OBS-15` | 🟠/🔴 |
| `OBS-16` | 🟠 |
| PAPER longitudinal | 🔴 |
| `≥4 días` | 🔴 |
| `≥32 ciclos` | 🔴 |
| A/B real | 🔴 |
| `P3-2` | 🔴 |
| `P3-3` | 🔴 |

---

## 13. `OBS-16` es un problema de proceso, no del motor

Causa: **15 costuras `object.__new__(AutoSimulationWorker)`** mantienen manualmente una copia del estado que
necesitan. Entonces:

```text
__init__ → nuevo atributo → costura no lo sabe → CI rojo
```

La mitigación actual (**extraer el comando real de CI y ejecutarlo completo localmente**) es buena, pero la
**solución definitiva** sería una **factory común de test** con estado derivado del worker, en lugar de 15
mini-inicializaciones manuales.

**El auditor NO la implementaría inmediatamente:** primero comprobaría cuánto riesgo real aporta y cuántas
costuras siguen dependiendo de `object.__new__`.

---

## 14. Cobertura insuficiente declarada: la pata de SALIDA

El propio objeto lo reconoce: **no existe cobertura de mutación para la pata de SALIDA.**

```text
ENTRADA   reservar → propietario   🟢 (M252)
SALIDA    reservar → propietario   🟠 (_v2_reserve_exit sin mutación ni test dedicado)
```

Si solo hay garantía fuerte en la **entrada**, **el contrato no está simétricamente demostrado**.
`🔧 Ésta sería la siguiente mejora técnica prioritaria.`

---

## 15. Segunda mejora propuesta: prueba explícita de aislamiento de salida + `M253`

Añadir una prueba explícita del tipo:

```text
session A → reserve exit → session B → attempt reconcile
comprobar: B cannot release A's exit reservation
```

acompañada de una mutación específica **`M253`** que elimine el ownership de `_v2_reserve_exit`. Objetivo:

```text
M253 → test falla → ownership de SALIDA realmente protegido
```

Eso cerraría **la simetría**.

---

## 16. Valoración de `V2.88.3` (tabla del auditor)

| Área | Estado |
| --- | --- |
| Arquitectura AUTO | 🟢 |
| Motor | 🟢 |
| Reservas | 🟢 |
| Ownership entrada | 🟢 |
| Ownership salida | 🟠 |
| Reconciliación | 🟢 |
| Concurrencia | 🟢 |
| Crash/recovery | 🟢 |
| Account isolation | 🟢 |
| Decision spine | 🟢 |
| CI | 🟢 |
| Mutation matrix | 🟢 `252/252` |
| `OBS-14` | 🟢 |
| `OBS-14.b` | 🟠 |
| `OBS-15` | 🟠 |
| `OBS-16` | 🟠 |
| PAPER real longitudinal | 🔴 |
| `P3-2` | 🔴 |
| `P3-3` | 🔴 |

> **Infraestructura AUTO: muy sólida.** Pero **no** hay que confundirlo con
> **«Comportamiento de trading AUTO: todavía no certificado».**

---

## 17. 🎯 Qué haría ahora (recomendación del auditor)

**No** volvería a tocar `TOP_N` / `REGIME` / `RISK` / `SIGNALS` / `A/B` / `thresholds` por motivos de
comportamiento de mercado. En cambio, tres cosas concretas:

1. 🔧 **Cerrar la simetría de ownership** — test + mutación para `_v2_reserve_exit` (**`M253`**), demostrando
   que `A reserva salida → B no puede liberarla → A sí puede`.
2. 🔧 **Atacar `OBS-14.b`** — en particular `restart → startup sweep → reservas → ownership →
   grace/no grace`.
3. 🔥 **Después, volver al objetivo que importa: PAPER real.** Ya no otra cadena interminable de tests si no
   aparece un defecto. Pasar de *«¿puede AUTO sobrevivir correctamente?»* a
   *«¿qué hace AUTO durante varios días de operación real?»*.

**Cambio de prioridad declarado por el auditor:** no seguir endureciendo indiscriminadamente todo AUTO; solo
cerrar **ownership de SALIDA** + **`OBS-14.b`**, comprobar el riesgo de **1000 APPLIED**, y después volver a
centrar la auditoría en la **ejecución PAPER real**.

---

## 18. 🏁 Conclusión final del auditor

`v2.88.3-beta` es una versión **buena** y, sobre todo, **mucho más fiable que `v2.88.2-beta`**. Queda
**APROBADA**, con la precisión de que **no cierra toda la deuda funcional de AUTO ni `P3-2`/`P3-3`**.

Cadena acreditada:

```text
v2.88.2  🔴 6 tests → causa raíz identificada → v2.88.3 → M252 → 252/252
        → CI completo → 3040 passed / 37 skipped → Release Tag CI = SUCCESS
```

y simultáneamente siguen pasando **crash/recovery**, **tres sesiones concurrentes**, **aislamiento de
cuenta** y **golden day**.

### Pendientes que realmente importan ahora

| Estado | Pendiente |
| --- | --- |
| 🟢 Cerrado | `OBS-14` |
| 🟠 Pendiente | `OBS-14.b` |
| 🟠 Pendiente | `OBS-15` — límite 1000 `APPLIED` |
| 🟠 Pendiente | `OBS-16` — costuras manuales / cobertura local |
| 🟠 Pendiente | ownership de la rama de SALIDA |
| 🔴 Pendiente | PAPER longitudinal |
| 🔴 Pendiente | `≥32 ciclos` |
| 🔴 Pendiente | A/B real |
| 🔴 Pendiente | `P3-2` / `P3-3` |

---

## 19. Relación con la fase en curso

Esta auditoría es **documental**: se registra en `main` **sin bump**, **sin tag** y **sin tocar
`packages/`/`apps/`** (patrón docs-only `5510da85`). **No** mueve ningún árbol.

**Ninguna deuda se cierra por este informe.** `OBS-14.b`, `OBS-15`, `OBS-16`, la **pata de SALIDA**
(`_v2_reserve_exit`) y `P3-2`/`P3-3` **siguen ABIERTAS** y declaradas en la
[deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md). Las **tres acciones** del §17 son
**recomendaciones**, no trabajo ejecutado: su registro y su priorización corresponden a la fase siguiente.

**Punto de entrada del objeto auditado:** [`arranque-auditor-v2-88-auto-material-16-obs14-2026-09-29.md`](./arranque-auditor-v2-88-auto-material-16-obs14-2026-09-29.md) ·
[`entrega-auditoria-externa-mia-v2.88.3-2026-09-29.md`](./entrega-auditoria-externa-mia-v2.88.3-2026-09-29.md) ·
[evidencia `v2.88.3`](./evidence/v2.88.3/README.md) ·
[informe/relevo](./obs-14c-costura-sin-atributo-v2.88.3-2026-09-29.md).
