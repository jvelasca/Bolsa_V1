# Certificación de la operativa de ASESOR · 2026-11-15

> **Padre:** [índice de ingeniería](./engineering-index-2026-08-03.md)
> **Auditoría:** [A0](./auditoria-operativa-asesor-2026-11-15.md)
> **Diseño:** [A1–A4](./diseno-operativa-asesor-2026-11-15.md)
> **Evidencia:** [verificación-2026-11-15.md](./evidence/operativa-asesor-2026-11-15/verificacion-2026-11-15.md)

## Alcance de esta certificación

Certifica el refactor de la puerta ASESOR (`/research`) en cinco slices: información
architecture, dictamen único, descomposición técnica, primer nivel honesto y cierre
(sexta categoría de cartera + E2E real).

**No certifica** el motor, la decisión, el contrato ni la ventana DECISIÓN: nada de eso
se ha tocado y sus certificaciones siguen vigentes por separado.

## Invariantes verificados

| Invariante | Cómo se verificó | Resultado |
| --- | --- | --- |
| `Δ motor = 0` | Sin cambios en `packages/py/**` ni `apps/api-python/**` | cumple |
| `Δ decisión = 0` | Sin cambios en `compute_stance`, umbrales, gate, sizing, ejecución ni AUTO | cumple |
| Contrato intacto | `contract:check` contra el commit | `OK — openapi.json y schema.d.ts coinciden` |
| Sin migración | No se añadió ni modificó ninguna | cumple |
| `UNKNOWN ≠ 0` | Sin `?? 0` de dato ausente en `features/research`; KPI con `formatPriceOrAbsent`; costes con guion de nivel 3 | cumple |
| Primer nivel sin jerga | Gate de 22 tokens sobre todos los módulos de Asesor | 13 pruebas verdes |
| Clasificador sin falsos huecos | Ninguna postura conocida devuelve «Dictamen no reconocido»; las tres posturas de salida sin posición son una categoría, no un error | cumple (H-5 cerrado) |

## Verificación ejecutada

| Comando | Resultado real |
| --- | --- |
| `pnpm --filter @bolsa/shared typecheck` | sin errores |
| `pnpm --filter @bolsa/shared test` | 108 archivos · 1041 passed · 1 todo |
| `pnpm --filter @bolsa/web typecheck` | sin errores |
| `pnpm --filter @bolsa/web test` | 395 archivos · 2957 tests passed |
| `pnpm --filter @bolsa/web lint` | 0 errores · 23 warnings preexistentes |
| `pnpm --filter @bolsa/web build` | `✓ built in 4.79s` · 2722 módulos |
| `pnpm --filter @bolsa/web contract:check` | `OK` |
| `uv run python -m pytest packages/py/application/tests/test_daily_opinion_service_hints.py -q` | 14 passed |
| `E2E_RUN=1 playwright test gp-s5-rediseno` | **11 passed (16.9s)** |

La suite web pasó de **392 archivos / 2938 tests** al inicio del frente a
**395 / 2957**: tres archivos y diecinueve pruebas nuevas que vigilan el adaptador de
dictamen, los tres estados del Diario, la ausencia de costes del experimento y la sexta
categoría de cartera. La suite compartida subió de 1039 a 1041 pruebas por el mismo
motivo.

## Huecos declarados de esta certificación

**E2E verificado (antes era un hueco).** `E2E_RUN=1 playwright test gp-s5-rediseno`
pasa **11 de 11** en 16,9 s, incluidas `S5.S3 · Asesor/Cartera clasifica la misma
cartera` y `S5.S3 · sin posición no inventa respaldo`. Las once fallas anteriores no
eran del refactor: `PLAYWRIGHT_BROWSERS_PATH` apuntaba a una caché temporal vacía, de
modo que `browserType.launch` abortaba antes de abrir la aplicación. Los binarios ya
estaban instalados en `%LOCALAPPDATA%\ms-playwright`; basta apuntar la variable ahí. No
hubo que tocar ninguna aserción ni ningún `data-testid`.

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = "$env:LOCALAPPDATA\ms-playwright"
$env:E2E_RUN="1"; pnpm --filter @bolsa/web exec playwright test gp-s5-rediseno
```

**Revisión visual hecha, con un hueco de contraste ajeno al Asesor.** Se capturaron
Asesor → Cartera y Asesor → Diario en tema claro y oscuro y se pasó axe (WCAG 2A/2AA)
sobre el Diario en ambos temas. El hero del Diario **no** genera violaciones: su línea de
contexto va sobre `--bolsa-card` y da 4,76:1. En claro sobrevive una violación `serious`
de `color-contrast` en el **armazón global**: el subtítulo de la página y las pestañas
(4,39:1 con `--bolsa-muted-foreground`) y los enlaces y «Asesor» del menú (3,45:1 con
`--bolsa-primary`). Es un token del sistema de diseño usado en toda la aplicación, no un
cambio de A4, y se registró como **H-21**. **Corregido el 2026-11-16** (§«Cierre de
pendientes»).

**Regresión declarada en el Diario.** La ★ y la confianza del Diario pasan a «Sin
medir» porque la fila del parte no transporta IO y el API no rellena `opinionDetails`.
Es consecuencia deliberada de la regla única de S1. Se cierra el día que el backend
pueble ese campo, y eso es trabajo de contrato/API, fuera de este frente.

**Hallazgo previo, no introducido aquí.** `/research?tab=diario` rompe a pantalla de
error si el parte llega sin `tradesToday`, `notes` o `week`; el panel lee `.length` sin
guarda y las mismas lecturas están en `HEAD`. Se registró como **H-22**. **Corregido el
2026-11-16** (§«Cierre de pendientes»).

## Cierre de pendientes (2026-11-16)

Los tres pendientes del frente se cierran en un solo cambio, sin tocar contrato ni motor.

| id | Antes | Ahora |
| --- | --- | --- |
| H-8 | La pestaña por defecto del Asesor era la más vacía | `parseTab` cae en **Cartera** cuando no hay `tab` válido: el hub abre con contenido y el resumen del Laboratorio queda a un clic |
| H-20 | El Diario no aceptaba `className`; sus hermanos sí | `AsesorDailyOpsPanel({ className })` con `cn("space-y-4", className)` |
| H-21 | `--bolsa-muted-foreground` 4,39:1 y `--bolsa-primary` 3,45:1 en claro | `#566578` → **5,50:1** y `#0e7268` → **5,35:1**; `--bolsa-primary-foreground` conserva 5,55:1 sobre el nuevo fondo |
| H-22 | El Diario caía a error boundary con un parte parcial | `asDeclaredList`/`asDeclaredNumber`: el hueco se declara, el cero solo se afirma cuando el array llegó vacío |
| H-23 | `heading-order` en Cartera y Análisis (`h1 → h3`) | `CardTitle level="h2"`; detectado al repetir el barrido, era previo |

La regla que gobierna H-22 no es «rellenar para no romper» sino la contraria: un dato que
no llega **se declara**. `?? []` habría convertido «no medido» en «cero operaciones», que
es exactamente la afirmación falsa que `UNKNOWN ≠ 0` prohíbe. Por eso solo la rama que
pasó por `Array.isArray` puede decir «Sin compras/ventas registradas hoy».

Medición después del cambio: **0 violaciones `critical`/`serious`** en claro y en oscuro
sobre Asesor → Cartera, Asesor → Diario, `/mesa` y `/backtests`, y el barrido de las rutas
L1 (`gp-e2e-ui5-0-axe-touched-routes-mock`) en **35/35**. `2968/2968` pruebas de
`@bolsa/web`, `typecheck` y `contract:check` en verde; `0` errores de lint (23 avisos
preexistentes).

## Riesgos residuales

- **Gate por archivo.** El invariante nuevo exige importador único y montaje dentro de
  un `TechnicalDetail`, y se autoprueba con casos negativos. Sigue siendo análisis
  textual: un fragmento importado dinámicamente escaparía al chequeo.
- **Caché del gráfico.** El `staleTime` único de 5 min reduce lecturas internas de
  velas; si producto quiere refresco más agresivo, es una constante, no un rediseño.
- **`data-testid` de estado por fila.** Sigue repitiéndose por diseño: nueve
  aserciones dependen del valor actual y el cambio no aportaba información.

## Lo que este documento no autoriza

No autoriza commit, tag ni bump de versión. No autoriza tocar `PROJECT_STATE.md` ni
`CHANGELOG.md`. El cierre de E2E que antes era un hueco está ejecutado y en verde
(§«Verificación ejecutada»). Los pendientes H-8, H-20, H-21, H-22 y H-23 quedaron cerrados el
2026-11-16 (§«Cierre de pendientes»); el frente Asesor no deja hallazgos abiertos de
severidad B o C salvo los declarados como conducta intencionada (§6.b de la auditoría).
