# Deuda P3 post-auditoría `v2.69` — 2026-09-25

> **AsOf:** 2026-09-25 · **Origen:** [auditoría de `v2.69-beta`](./auditoria-v2-69-auto-22-real-paper-run-2026-09-25.md)
> **Naturaleza:** observaciones **P3** (ninguna publica un número falso ni mueve el reparto).
> **Estado:** P3-1 (flake) **cerrada** en `v2.69`; P3-2 y P3-3 **abiertas** (requieren el primer
> dataset PAPER real). **El bloqueante central es MATERIAL, no código.**

## P3-1 — Flake ajeno del test runner (`core-r-scheduler.test.ts`)

**Estado: 🟢 CERRADA en `v2.69`.** `apps/web/src/features/backtests/core-r-scheduler.test.ts` declara
su presupuesto **por fichero** (`vi.setConfig({ testTimeout: 20_000, hookTimeout: 20_000 })`); la
suite completa queda verde **sin** el flag global `--testTimeout`. **Criterio de reversión:** un
deadlock real seguiría superando los 20 s, así que el margen no lo enmascara.

## P3-2 — Validación empírica de la correlación por cubos temporales

**Observación.** La correlación por cubo temporal es una buena **primera aproximación**, pero con
datos reales hay que comprobar que no introduce **correlación artificial** por:

- **distinta frecuencia de operaciones** (una estrategia opera 10× más que la otra ⇒ los cubos con un
  solo ciclo dominan la media de cubo);
- **buckets con pocos ciclos** (una media de cubo sobre 1 observación es ruido, no un resultado);
- **períodos de inactividad** (una estrategia parada: hoy el cubo solo existe si hay ciclo ⇒ la
  ausencia no entra, pero hay que certificarlo con datos);
- **diferencias de exposición temporal** (pocos cubos compartidos, ya declarado como
  `insufficient_buckets`).

**No es un bug de `v2.69`.** Es una **validación empírica** que solo puede hacerse con el primer
dataset real. La lectura ya declara `sharedBuckets`, `minBuckets` y sus notas.

**Herramienta lista (`v2.70`).** `auto_evidence_validate.py` publica, junto al número, los
**diagnósticos** que permiten juzgar el sesgo: ciclos y cubos activos por estrategia y
`sharedSingleCycleShare` (fracción de cubos compartidos sostenidos por un solo ciclo), por cubo
(`day`/`week`/`month`).

**Criterio de cierre.** Sonda sobre el primer dataset PAPER real que compare la correlación por cubos
contra un oráculo por **pares de ciclos emparejados** (o correlación sobre sub-muestras), y documente
si la frecuencia/exposición sesga el número. Si sesga, se declara la limitación **antes** de tocar la
métrica.

## P3-3 — `P(R>0)` frente al tamaño muestral

**Observación.** `P(R>0)` **no incorpora el tamaño muestral** en su forma: `N = 8, P(R>0) = 0.875` y
`N = 180, P(R>0) = 0.875` se leen igual. La arquitectura actual **correctamente** no la convierte en
`confidence` ni en allocation, pero el número publicado invita a esa lectura.

**Regla que se mantiene.** `P(R>0)` es **evidencia descriptiva**: nunca se traduce directamente en
`confidence` ni en sizing. La banda de edge (`ADAPTIVE_EDGE_*`) sigue siendo el eje que incorpora la
muestra (vía `effective_n`), y es la que se publica junto a la probabilidad en la evidencia del régimen.

**Herramienta lista (`v2.70`).** El barrido de `auto_evidence_validate.py` publica `P(R>0)`, `P(R>0)`
OOS, WFE y `effective_n` sobre el **prefijo cronológico** para `N ∈ {16, 32, 64, 128}`. **No elige un
`N`**: publica la serie para observar si la lectura se **estabiliza**. Un `N` mayor que el material
medido es **`NO MEDIDO`**.

**Criterio de cierre.** Con el primer dataset real, documentar la relación `P(R>0) ↔ N` (y el
`effective_n` asociado) y decidir si hace falta una banda de confianza muestral **explícita** en la
evidencia. Hasta entonces, **no** se convierte en permiso de sizing.

## Bloqueante central — material PAPER real

**No es deuda P3: es el límite declarado.** `v2.69` deja el RUN **listo y probado**, pero **la corrida
PAPER real no se ejecuta** (bloqueo por **material**, no por código). El primer RUN + su validación
son el **paso operativo del propietario** (ver
[`protocolo-primer-run-paper-real-v2.70-2026-09-25.md`](./protocolo-primer-run-paper-real-v2.70-2026-09-25.md)).
**No se bajan** `min cycles` / `min R` / `folds` para forzarlo.

## Fuera de alcance de esta deuda

- **Mejora de UI de procedencia** (punto 22 de la auditoría): abordada en `AUTO-23` / `v2.70`
  (`SOURCE` + `EXECUTION REALITY: VIRTUAL — NO REAL MONEY`).
- **Current-regime gating operativo:** fase posterior declarada.
- **Allocation dinámica** y **LIVE AUTO**: `❌`, no abordados.
