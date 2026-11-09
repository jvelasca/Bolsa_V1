# Paridad del cliente API y plan de migración — Fase 3.4 — 2026-11-08

Cierre de `p3-api` (Fase 3 / 3.4 del plan de remediación). Se añade una guarda
ejecutable de paridad entre `apps/web/src/lib/api.ts` y el contrato OpenAPI, y se deja
por escrito la migración que queda pendiente hacia tipos generados.

## Estado medido (no el del informe)

La premisa del informe («métodos escritos a mano») ya no describe el árbol:

| Elemento | Medición |
| --- | --- |
| `apps/web/src/lib/api.ts` | 2.817 líneas |
| Llamadas `client.GET/POST/PUT/PATCH/DELETE` | 241, **todas con path literal** |
| Transporte | `openapi-fetch` tipado con `paths` de `src/api/schema.d.ts` |
| Endpoints en `api/openapi.json` | 240 paths |
| `apiBody(...)` (cast a `never` del body) | 54 usos |
| Wrapper `call<T>` | 241 usos, uno por endpoint |

Por tanto el transporte ya es tipado: un path inexistente lo rechaza `tsc`. Lo que
queda es deuda de **forma de los DTOs** y del wrapper manual.

## Qué se añadió

`apps/web/src/lib/api-contract-parity.test.ts` (se ejecuta en `pnpm --filter @bolsa/web
test`, que ya corre en `frontend-ci.yml`):

1. **Extracción no ciega**: cuenta todas las llamadas `client.*` y exige que el número
   coincida con las que llevan path literal. Si alguien introduce un path calculado, el
   test falla en vez de ignorarlo.
2. **OpenAPI**: cada `(método, path)` usado por `api.ts` existe en `api/openapi.json`
   con ese método; el mensaje distingue «path ausente» de «path sí, método no».
3. **schema.d.ts**: cada path usado aparece como clave en `src/api/schema.d.ts`, lo que
   detecta una regeneración parcial (spec actualizado, tipos no).

No sustituye a `tsc` ni a `contract:check`: es la guarda barata que corre en cada PR sin
necesitar el venv de Python.

## Migración pendiente (plan)

El objetivo no es reescribir `api.ts`, sino eliminar las dos fuentes de deriva que el
tipo no cubre. Orden propuesto, cada paso con `tsc` + test de paridad en verde:

### Paso 1 — Derivar los tipos de respuesta del contrato

Hoy cada método repite la forma: `call<{ status: string; ... }>(() => client.GET(...))`.
Sustituir por alias derivados de `components["schemas"]`:

```ts
type Schemas = components["schemas"];
type AccountSummary = Schemas["AccountSummaryDto"];

getAccountSummary: (id: string) =>
  call<AccountSummary>(() => client.GET("/api/accounts/{account_id}", {
    params: { path: { account_id: id } },
  })),
```

- Empezar por los DTOs que ya existen en el spec; no inventar tipos nuevos.
- Un endpoint sin schema de respuesta se queda con su tipo manual y se anota; no se
  bloquea el paso por él.
- Criterio de cierre: `rg 'call<\{\s*$' api.ts` baja de forma monótona. No hace falta
  llegar a cero en este paso.

### Paso 2 — Retirar `apiBody` donde el DTO compartido ya encaja

`apiBody` existe para divergencias de optionality y de index-signature entre
`@bolsa/shared` y el `requestBody` generado. Dos salidas, por orden de preferencia:

1. Ajustar el DTO de `@bolsa/shared` para que case con el contrato (el backend es la
   fuente de verdad), y borrar el cast.
2. Si la divergencia es real y el wire format es idéntico, mantener el cast **con
   comentario y test**; nunca añadir uno nuevo sin justificación.

Criterio de cierre: ratchet del número de `apiBody(` (54 al cerrar esta fase) que solo
pueda bajar, igual que el ratchet de `toFixed(2)`.

### Paso 3 — Decidir el futuro del wrapper `call<T>`

`call<T>` centraliza la semántica de `ApiError` (401 con mensaje propio, `detail`
estructurado, red → status 0) que ya prueban los tests. **No se elimina**: se tipa mejor
pasando el resultado de la operación como genérico, para que `data`/`error`/`response`
salgan del contrato en vez de un `ClientResult` borroso. Eliminarlo obligaría a repetir
ese manejo en 241 call sites; el wrapper es la abstracción correcta.

### Paso 4 — Fuente única de DTOs (decisión de producto, no de este PR)

Hay tres capas: Pydantic (backend) → `openapi.json` → `schema.d.ts`, y en paralelo
`@bolsa/shared` escrito a mano. La meta a medio plazo es que `@bolsa/shared` reexporte
los tipos generados (o se genere desde el mismo spec) y que la web no mantenga dos
definiciones del mismo DTO. Es un cambio con impacto en todos los consumidores del
paquete y merece su propia fase; este documento fija el orden, no lo ejecuta.

## Verificación

```bash
cd apps/web
pnpm run typecheck
pnpm exec vitest run src/lib/api-contract-parity.test.ts
pnpm run test
pnpm run contract:check   # requiere uv; sin él avisa y termina en verde
```

- `typecheck`: OK.
- Test de paridad: 3 passed (todas las llamadas son literales; 241/241 resuelven en
  `openapi.json` y en `schema.d.ts`).
- `contract:check`: OK — el contrato no cambia en esta fase.
