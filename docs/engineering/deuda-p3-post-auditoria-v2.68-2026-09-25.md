# Deuda P3 post-auditoría `v2.68` — 2026-09-25

> **AsOf:** 2026-09-25 · **Origen:** [auditoría de `v2.68-beta`](./auditoria-v2-68-auto-21-probabilidad-correlacion-regimen-2026-09-25.md)
> **Naturaleza:** observaciones **P3** (ninguna publica un número falso ni mueve el reparto).
> **Estado:** P3-1 (flake) **cerrada** en `v2.69`; P3-2 y P3-3 **abiertas** (requieren el primer
> dataset PAPER real; no son bloqueantes de la fase).

## P3-1 — Flake ajeno del test runner (`core-r-scheduler.test.ts`)

**Observación.** `apps/web/src/features/backtests/core-r-scheduler.test.ts`
(`runCoreRSchedulerTick > skips when disabled` / `> skips when no listId`) falla con
`Error: Test timed out in 5000ms` **solo bajo la carga de la suite completa** (cientos de ficheros,
`import()` dinámicos y jsdom). **Aislado pasa siempre** y el fichero **no se tocó** en `v2.68`.

**Clasificación.** 🟠 **Deuda de infraestructura/test runner**, no bug funcional de `AUTO-21`.
Es exactamente la clase de rojo que "no dice nada del código" y que, aun así, tumba un sello.

**Cierre (conservador y declarado).** Presupuesto **por fichero**, sin tocar `vitest.config.ts` (el
flake es de este fichero, no de la suite) ni aflojar ningún aserto:

```ts
// P3-1: bajo la suite completa este fichero rozaba el timeout por defecto (5 s). El scheduler no
// hace nada pesado: el margen se declara AQUÍ, por fichero; el resto de la suite mantiene su
// presupuesto estricto. Un deadlock real seguiría superando este margen.
vi.setConfig({ testTimeout: 20_000, hookTimeout: 20_000 });
```

**Criterio de reversión.** Si un deadlock real apareciera, seguiría superando los 20 s ⇒ el margen no
lo enmascara. No se subió `testTimeout` global (no se le regala presupuesto a tests que no lo necesitan).

## P3-2 — Validación empírica de la correlación por cubos temporales

**Observación.** La correlación por cubo temporal es una buena **primera aproximación**, pero con datos
reales hay que comprobar que no se introduce **correlación artificial** por:

- **distinta frecuencia de operaciones** (una estrategia opera 10× más que la otra ⇒ los cubos con un
  solo ciclo dominan la media de cubo);
- **buckets con pocos ciclos** (una media de cubo sobre 1 observación es ruido, no un resultado);
- **períodos de inactividad** (una estrategia parada ⇒ cuenta como "0" en el cubo? hoy el cubo solo
  existe si hay ciclo ⇒ la ausencia **no** entra, pero hay que certificarlo con datos);
- **diferencias de exposición temporal** (dos estrategias activas en ventanas distintas ⇒ pocos cubos
  compartidos, ya declarado como `insufficient_buckets`).

**No es un bug de `v2.68`.** Es una **validación empírica** que solo puede hacerse con el primer dataset
real. La lectura ya declara `sharedBuckets`, `minBuckets` y sus notas; lo que falta es comprobar que esos
números se comportan como se espera sobre material real.

**Criterio de cierre.** Sonda sobre el primer dataset PAPER real que compare la correlación por cubos
contra un oráculo por **pares de ciclos emparejados** (o correlación sobre sub-muestras), y documente si
la frecuencia/exposición sesga el número. Si sesga, se declara la limitación antes de tocar la métrica.

## P3-3 — `P(R>0)` frente al tamaño muestral

**Observación.** `P(R>0)` **no incorpora el tamaño muestral** en su forma: `N = 8, P(R>0) = 0.875` y
`N = 180, P(R>0) = 0.875` se leen igual. La arquitectura actual **correctamente** no la convierte en
`confidence` ni en allocation, pero el número publicado invita a esa lectura.

**Regla que se mantiene.** `P(R>0)` es **evidencia descriptiva**: nunca se traduce directamente en
`confidence` ni en sizing. La banda de edge (`ADAPTIVE_EDGE_*`) sigue siendo el eje que incorpora la
muestra (vía `effective_n`), y es la que se publica junto a la probabilidad en la evidencia del régimen.

**Criterio de cierre.** Con el primer dataset real, documentar la relación `P(R>0)` ↔ `N` (y el
`effective_n` asociado) y decidir si hace falta una banda de confianza muestral **explícita** en la
evidencia. Hasta entonces, **no** se convierte en permission de sizing.

## Fuera de alcance de esta deuda

- **Current-regime gating operativo** (`🟠` en el estado de la auditoría): sigue fuera de alcance; no es
  deuda P3, es una fase posterior declarada.
- **Allocation dinámica** y **LIVE AUTO**: `❌`, no abordados.
