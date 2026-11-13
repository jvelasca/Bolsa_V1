# Evidencia S4 — Ventana maximizada de DECISIÓN · 2026-11-12

> Alcance: composición de la ventana maximizada de escritorio de DECISIÓN
> (`/trading`), hero de recomendación principal, chip de estado de cartera (S3),
> helper puro de vía de actuación y rejilla de contenedor con cortes 52rem y 78rem.
>
> Estado: **implementado y verificado**. Sin commit, sin `git add`, sin migración, sin
> `contract:gen`, sin tocar S0/F4-067. `CHANGELOG.md` y `PROJECT_STATE.md` no se tocan.

## 1 · Invariantes

| Invariante | Comprobación | Resultado |
| --- | --- | --- |
| `Δ motor = 0` | `Get-ChildItem packages/py, apps/api-python -Recurse -Filter *.py \| Where LastWriteTime -gt 12:35` | Sin archivos: ningún `.py` del motor se tocó en este slice |
| `Δ motor = 0` (matiz) | `git status --porcelain -- packages/py apps/api-python` | Los listados ya venían modificados por F4-067 **antes** de S4; ninguno se revirtió ni se preparó |
| `Δ decisión = 0` | `compute_stance`, umbrales, gate, sizing, ejecución | Sin cambios |
| Sin migración | `git status` sobre `versions/` | Nada añadido |
| Sin `contract:gen` | `pnpm --filter @bolsa/web contract:check` | `OK — openapi.json y schema.d.ts coinciden con el commit` |
| S0/F4-067 intactos | `git status --porcelain` | Los archivos ajenos siguen modificados, no revertidos ni staged |
| Sin commit ni `git add` | `git log -1` / índice | HEAD sin cambios; nada staged |
| Sin persistencia | código de S4 | Todo el estado nuevo es de presentación |

## 2 · Pruebas ejecutadas

```text
pnpm --filter @bolsa/web test -- operativa-action-hint operativa-recomendacion-principal trading-operativa-panel.maximized trading-layout operativa-recomendacion-vocabulary
  ✓ src/features/trading/operativa-action-hint.test.ts (7 tests)
  ✓ src/stores/trading-layout-store.test.ts (11 tests)
  ✓ src/components/layout/trading-layout.test.tsx (4 tests)
  ✓ src/features/trading/operativa-recomendacion-principal.test.tsx (7 tests)
  ✓ src/features/trading/operativa-recomendacion-vocabulary.test.tsx (9 tests)
  ✓ src/features/trading/trading-operativa-panel.maximized.test.tsx (7 tests)
  Test Files  6 passed (6) · Tests  45 passed (45)

pnpm --filter @bolsa/web test
  Test Files  388 passed (388)
  Tests       2888 passed (2888)

pnpm --filter @bolsa/shared test -- asesor-cartera
  ✓ src/cognitive/asesor-cartera.test.ts (34 tests)
```

Cobertura declarada y falsable:

**Vía de actuación (`operativa-action-hint.test.ts`)**

- `sin_datos` ⇒ `sin_actuacion`, sin afirmar «sin posición»;
- `recomendacion_favorable` con compuertas abiertas ⇒ `entrada_disponible`;
- posición abierta (categorías `posicion_abierta` y `posicion_sin_respaldo`) ⇒
  `salida_en_accion`;
- `evaluado_sin_oportunidad` ⇒ `sin_actuacion`, aunque el contexto técnico sea bueno;
- un caso por motivo de bloqueo y precedencia `sin_cuenta` → … → `fuera_de_estudio`;
- con varias condiciones fallando gana la primera; los motivos no se acumulan;
- ninguna etiqueta contiene claves `snake_case`.

**Hero (`operativa-recomendacion-principal.test.tsx`)**

- las cuatro categorías con `data-state` y `data-action-hint` correctos;
- `overbought` ⇒ «Posición sin respaldo», sin «Sobrecomprado»/«sobrecompra»;
- cartera no medida ⇒ «Sin datos suficientes», sin «sin posición»;
- confianza y primer motivo visibles en el dictamen;
- entrada bloqueada declara `data-blocked-reason="entradas_bloqueadas"`;
- en carga: `data-state="midiendo"`, sin chip y con «Midiendo recomendación…»;
- el aviso declara que informa, que no ejecuta y que la firma vive en Confirm.

**Composición (`trading-operativa-panel.maximized.test.tsx`)**

- `surface="maximized"`: hero → ACCIÓN → contexto técnico → seguimiento, verificado con
  `compareDocumentPosition`;
- **un solo** `operativa-dictamen`, dentro del hero y con `data-variant="hero"`;
- contexto técnico contiene Análisis diario y Estructura, y declara «Informan; no
  autorizan entradas»;
- cartera no medida y `overbought` con posición llegan al primer nivel;
- `dock` y `narrow`: no hay hero, el dictamen sigue en Evidencia y es `compact`.

**Layout (`trading-layout.test.tsx`)**

- maximizado de escritorio ⇒ `data-surface="maximized"`;
- dock ⇒ `data-surface="dock"`;
- ventana estrecha ⇒ `data-surface="narrow"` con `data-maximized="true"`.

## 3 · Comprobación visual (navegador, dev server 5173)

Viewport emulado, consultando el DOM real:

```text
1600 × 1000
  panel.surface            = maximized
  dictámenes               = 1   (variant = hero)
  hero.state               = evaluado_sin_oportunidad
  hero.actionHint          = sin_actuacion
  grid-template-columns    = 415.99px 543.16px 543.17px
  orden y posición         = acción (56, 282) · contexto (484, 282) ·
                             seguimiento (1039, 282) · evidencia (56, 907 ancho completo)

1200 × 900
  grid-template-columns    = 557.16px 557.17px
  orden y posición         = acción (56, 282) · contexto (625, 282) ·
                             seguimiento (56, 907) · evidencia (625, 907)

403 × (ventana estrecha)
  panel.surface            = narrow  (sin hero; composición anterior)
```

Texto real del hero en la comprobación (BBVA):

```text
RECOMENDACIÓN DEL DÍA · BBVA
Sin oportunidad
RECOMENDACIÓN  Mantener
Confianza 68 / 100 · ★★★★☆
ACTUACIÓN  Sin actuación
El dictamen no emitió compra: no hay entrada que proponer. El contexto técnico informa, no habilita.
Esta ventana informa: la recomendación no ejecuta. La firma vive en Confirm y la operación en ACCIÓN.
```

## 4 · Tipos, lint y build

```text
pnpm --filter @bolsa/web typecheck      → OK (tsc -b --noEmit)
pnpm --filter @bolsa/web lint           → 0 errores (23 warnings preexistentes)
pnpm --filter @bolsa/web build          → OK (built in ~5 s)
pnpm --filter @bolsa/web contract:check → OK
```

Nota de honestidad: `packages/shared` se consume compilado (`dist/`) porque `apps/web`
lo importa; el paso `pnpm --filter @bolsa/shared build` es el habitual del monorepo y no
genera artefactos versionados.

## 5 · Ajuste colateral obligado (fuera de S4)

El suite completo estaba en rojo por `src/lib/format-ratchet.test.ts`: la línea base es
131 llamadas a `.toFixed(2)` y el árbol tenía 132 desde S3, por la fila de
`structureProvenance.atrRef` en `asesor-cartera-panel.tsx`.

Se respetó el propósito del ratchet en vez de subir la línea base: el ATR de referencia
se formatea con `formatNumberWith(..., { minimumFractionDigits: 2,
maximumFractionDigits: 2 })` de `@/lib/format`. Sin cambios de contenido visible y sin
tocar la línea base. Es el único cambio fuera de los archivos de S4.

## 6 · Archivos de S4

**Nuevos**

- `apps/web/src/features/trading/operativa-recomendacion-principal.tsx`
- `apps/web/src/features/trading/operativa-recomendacion-principal.test.tsx`
- `apps/web/src/features/trading/operativa-action-hint.ts`
- `apps/web/src/features/trading/operativa-action-hint.test.ts`
- `apps/web/src/features/trading/trading-operativa-panel.maximized.test.tsx`
- `docs/engineering/diseno-decision-maximizada-s4-2026-11-12.md`
- `docs/engineering/evidence/s4-decision-maximizada-2026-11-12/README.md`

**Modificados**

- `apps/web/src/features/trading/trading-operativa-panel.tsx` — prop `surface`,
  clasificador S3, helper de actuación, fragmentos compartidos y recomposición de la
  maximizada.
- `apps/web/src/features/trading/operativa-dictamen.tsx` — `variant="hero"`.
- `apps/web/src/components/layout/trading-layout.tsx` — cableado de `surface`.
- `apps/web/src/components/layout/trading-layout.test.tsx` — las tres superficies.
- `apps/web/src/features/trading/operativa-recomendacion-vocabulary.test.tsx` — el hero
  entra en la guarda de términos retirados.
- `apps/web/src/index.css` — `.operativa-maximized-grid` y sus cortes.
- `apps/web/src/features/research/asesor-cartera-panel.tsx` — ver §5 (ratchet).

## 7 · Límites de esta evidencia

- Sin commit: no hay SHA ni CI ejecutada sobre este árbol.
- No se miden tiempos de carga ni se comparan contra S3.
- La verificación visual se hizo con emulación de viewport en el navegador del IDE, no
  con capturas E2E del cierre S5.
- El dock y la ventana estrecha se validan por tests y por el atributo `data-surface`,
  no con una captura nueva: su composición no cambia.
