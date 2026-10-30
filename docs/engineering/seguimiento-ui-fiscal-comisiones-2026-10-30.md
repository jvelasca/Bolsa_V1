# Seguimiento — consolidación UI · Comisiones y fiscal + página `/fiscal`

> **AsOf:** 2026-10-30 · **Área:** Configuración de cuenta → «Comisiones y fiscal», pasos
> Comisiones/Fiscal del asistente de alta y página `/fiscal`.
> **Naturaleza:** documento vivo de consolidación. Registra el contrato por área, los casos de
> prueba (backend → frontend), las evidencias y los defectos. No certifica el sello ni sustituye
> a una auditoría independiente.

---

## 0. Método de trabajo

Cada área se trabaja en tres pasos y **en este orden**:

1. **Backend**: contrato en código + pruebas automatizadas (unitarias de dominio y PostgreSQL real
   cuando el estado es durable). Si una prueba no se puede ejecutar, se declara como límite;
   nunca se cuenta como éxito.
2. **Frontend**: el mismo caso se reproduce en la UI y se cubre con Vitest/RTL.
3. **En vivo**: con el stack real (`pnpm dev` + PostgreSQL) se recorre el caso en el navegador y
   se guardan capturas y respuestas de red en `evidence/`.

Cada caso de la tabla de §3 tiene un identificador estable (`COM-*` para comisiones,
`FIS-*` para fiscal) que se usa igual en el test, en la evidencia y en este documento.

---

## 1. Estado del árbol al abrir esta consolidación

- Rama `fix/059-060-proveedores`, HEAD `7e8fe706`, árbol con cambios sin commit de otra área
  (auto-ops / estudio / proveedores). **Esta pasada no commitea ni crea rama.**
- Stack **ya levantado**: API `http://127.0.0.1:8000` (`status=ok`, esquema en head
  `060_provider_check_policy`) y web `http://127.0.0.1:5173` (200).
- Alcance acordado: pestaña **Configuración → Comisiones y fiscal**, pasos **Comisiones** y
  **Fiscal** del asistente de cuenta y página **`/fiscal`**. No se tocan General, Notificaciones,
  Atajos, BD ni Sync/proveedores.
- Decisión acordada: **el dominio Python es canónico** para el tipo de plusvalías ES (19 %) y
  para el redondeo de comisiones. El frontend se alinea al dominio, no al revés.
- **Ningún cambio de esquema ni de DTO**: `contract:check` sigue verde (§4.1).

### Defectos conocidos al abrir, y su estado

| ID | Severidad | Descripción | Estado |
| --- | --- | --- | --- |
| COM-D1 | Alta | El dominio define `capital_gains_tax_pct = 19.0` para ES, pero `TAX_PRESETS.ES` en TS enviaba `capitalGainsTaxPct: null`: las cuentas nacían sin tipo y el panel lo destruía al pasar por otra jurisdicción. El backend nunca estimaba impuesto desde la UI. | Corregido |
| COM-D2 | Alta | `estimatedTaxLiability` se calculaba en el dominio y viajaba en el DTO, pero no se pintaba en ninguna superficie y **no tenía una sola prueba**. | Corregido |
| COM-D3 | Alta | La card «Comisiones pagadas — Histórico acumulado» describía otra magnitud: el backend suma **solo el ejercicio fiscal** y **excluye custodia** (F-FIN-2). | Corregido |
| COM-D4 | Media | `capitalGainsTaxPct` existía en el wire y en el DTO pero ninguna superficie lo mostraba ni lo editaba. | Corregido |
| COM-D5 | Media | Ficha de cuenta y paso Revisión del asistente resumían solo `label · jurisdicción · método`: sin tipos, mínimos, IVA, custodia ni el ejemplo de comisión ya calculado. | Corregido |
| COM-D6 | Media | `stockCommissionMax < min` y `fiscalYearStartMonth` fuera de 1–12 solo los rechazaba el servidor (422); el panel enseñaba el texto crudo del error. | Corregido |
| COM-D7 | Media | El selector de cuenta de `/fiscal` cambia la **cuenta activa global** de la app sin declararlo. | Corregido |
| COM-D8 | Baja | `calculateTradeFees` en TS no replicaba el `quantize(0.0001, ROUND_HALF_UP)` del dominio: la vista previa podía diferir del asiento en la 4.ª decimal. | Corregido |
| COM-D9 | Baja | Importes sin moneda (`formatPrice` sin `currency`) y error genérico «No se pudo generar el informe fiscal». | Corregido |
| COM-D10 | Baja | «editar perfil fiscal» navegaba a `/accounts` a pelo: el usuario debía buscar pestaña y botón. | Corregido |
| COM-D11 | Baja | Hints del catálogo de comisiones duplicados en panel y asistente (drift garantizado). | Corregido |
| COM-D12 | Media | **Hallazgo nuevo.** «Sin comisiones» no es «sin impuestos»: el impuesto de transmisiones sale del perfil fiscal y con ES el backend sigue cobrando el 0,2 % en las compras. La UI prometía «ni comisiones ni impuestos simulados». | Corregido (texto honesto) |
| — | — | Cobertura UI inexistente: ningún test de `/fiscal`, del panel ni de los pasos del asistente en esta materia. | Corregido |

---

## 2. Contrato del área

| Superficie | Contrato |
| --- | --- |
| Catálogo de presets | `COMMISSION_PRESETS` y `TAX_PRESETS` (dominio Python) son la fuente de verdad. El espejo TS `packages/shared/src/account-settings.ts` debe tener **los mismos números**, verificados por tests de paridad en ambos lados. |
| Presentación | `describeCommissionPreset(id)`, `describeCommissionProfile(profile)`, `describeTaxProfile(tax)`, `TAX_JURISDICTION_LABELS`, `COST_BASIS_LABELS` y `commissionPresetLabel(id)` viven **solo** en `@bolsa/shared`; panel, asistente y ficha los consumen. |
| Cálculo de comisiones | `calculateTradeFees` = misma fórmula y mismo redondeo que `bolsa_domain.account_settings.calculate_trade_fees`: IVA sobre la comisión **sin redondear**, total **sin redondear**, cada componente cuantizado a 4 decimales `ROUND_HALF_UP` (`quantizeMoney4`). |
| Impuesto de transmisiones | Se cobra **solo en compras** y depende del **perfil fiscal**, no del preset de comisión. Con preset `none` + ES se siguen cobrando 0,2 %. |
| FX | Solo se cobra si la operación se declara como conversión (`isFxConversion`); nunca por defecto. |
| Defaults de alta | Una cuenta nueva con jurisdicción ES nace con `capitalGainsTaxPct = 19`, `dividendWithholdingPct = 19`, `stampDutyBuyPct = 0,2`, `costBasisMethod = fifo`, `fiscalYearStartMonth = 1`. |
| Estimación fiscal | `estimatedTaxLiability = netRealizedGain × capitalGainsTaxPct / 100` **solo** si hay tipo > 0 y neto > 0; en cualquier otro caso `null` (nunca `0` «conocido»: `UNKNOWN ≠ 0`). |
| Comisiones del informe | `feesPaidTotal` suma **solo** las fees del ejercicio pedido y **excluye custodia** (F-FIN-2). La UI lo dice en la etiqueta. |
| Validación | Servidor: 422 con detalle. Cliente: `max ≥ min`, todos los porcentajes ≥ 0, mes 1–12, custodia/tope nulos permitidos. **El cliente bloquea el guardado sin emitir la petición.** |
| Navegación | `/accounts?selected=<id>&tab=config&focus=fiscal` abre la ficha de esa cuenta con el diálogo de configuración en la pestaña **Fiscal**. |
| Tipo de plusvalías | Es una **proyección de un solo tramo**. El IRPF del ahorro real es progresivo (19/21/23/27/28 %); la UI lo declara en la propia card y en el panel. No se implementa escala progresiva. |

---

## 3. Casos de prueba

Leyenda de estado: `pendiente` · `verde` · `rojo` · `limite` (no ejecutable en esta máquina).

### 3.1 Comisiones y redondeo

| ID | Caso | Capa | Esperado | Estado |
| --- | --- | --- | --- | --- |
| COM-1 | Paridad del catálogo de comisiones | pytest | `standard_es` = 0,1 % / mín 1 / máx 29 / IVA 21 / FX 0,5 / custodia 0,2; `xtb_zero_stock`, `ibkr_tiered` y `none` con sus números | verde |
| COM-2 | Redondeo 4 decimales HALF_UP | pytest + vitest | Notional `1234.5678` ⇒ comisión 1,2346 · IVA 0,2593 · transmisiones 2,4691 · total 3,9630 **en ambos lados** | verde |
| COM-3 | Mínimo por operación | pytest + vitest | Notional 100 ⇒ comisión 1, IVA 0,21, transmisiones 0,2, total 1,41 | verde |
| COM-4 | Máximo por operación | pytest + vitest | Notional 100 000 ⇒ comisión topada en 29, total 235,09 | verde |
| COM-5 | Transmisiones solo en compra | pytest + vitest | Compra 5 000 ⇒ 10 de transmisiones; venta ⇒ 0 | verde |
| COM-6 | FX opt-in | pytest + vitest | Sin `isFxConversion` ⇒ 0; con ella y 10 000 ⇒ 50 | verde |
| COM-7 | Preset `none` no apaga los impuestos | pytest + vitest | Comisión/IVA/FX a 0, pero transmisiones ES 0,2 % ⇒ 10 sobre 5 000 (COM-D12) | verde |
| COM-8 | Overrides personalizados | vitest | `custom` 0,33 % / IVA 21 % sobre 1 000 ⇒ 3,3 + 0,693 = 3,993 | verde |
| COM-9 | Hint derivado del preset | vitest | El texto sale de los números del preset, no de una copia paralela | verde |
| COM-10 | Redondeo en el dominio | pytest | `settings_to_dict` conserva `capitalGainsTaxPct = 19.0` en el round-trip | verde |

### 3.2 Fiscal — backend

| ID | Caso | Capa | Esperado | Estado |
| --- | --- | --- | --- | --- |
| FIS-1 | Catálogo fiscal canónico | pytest | ES: FIFO, 0,2 transmisiones, 19 retención, **19 plusvalías**, mes 1; EU_OTHER 15; US 30; CUSTOM 0 | verde |
| FIS-2 | Estimación con tipo | pytest | Compra 10 @100 + venta 5 @120 ⇒ neto 100 ⇒ `estimatedTaxLiability = 19.0` | verde |
| FIS-3 | Estimación sin tipo | pytest | `capitalGainsTaxPct: None` ⇒ `estimatedTaxLiability is None` | verde |
| FIS-4 | Año en pérdidas | pytest | Neto −100 con tipo 19 ⇒ `None` (no se pinta impuesto) | verde |
| FIS-5 | Tipo cero | pytest | `0.0` ⇒ `None` | verde |
| FIS-6 | Estimación de punta a punta | pytest (PG real) | Alta de cuenta + buy + sell por HTTP ⇒ `netRealizedGain = 100`, `estimatedTaxLiability = 19`, `dividendWithholdingPct = 19` | verde |
| FIS-7 | Sin tipo, informe real | pytest (PG real) | La misma operación con `None` ⇒ `estimatedTaxLiability = null` | verde |
| FIS-8 | Round-trip del perfil fiscal | pytest (PG real) | `POST /api/accounts` y `PATCH /settings` devuelven `capitalGainsTaxPct = 19` (el fixture fijaba el `null` divergente) | verde |
| FIS-9 | Comisiones del ejercicio | pytest | `feesPaidTotal` suma solo el ejercicio pedido, ignora carry-in de años previos | verde |
| FIS-10 | Rango del ejercicio | pytest | `fiscalYearStartMonth = 9` ⇒ `[2024-09, 2025-09)` y una venta de 2025-mar cae en el ejercicio 2024 | verde |

### 3.3 UI — página `/fiscal`

| ID | Caso | Capa | Esperado | Estado |
| --- | --- | --- | --- | --- |
| UI-1 | Card de impuesto estimado | Vitest | Presente con el importe en la moneda del informe, el tipo aplicado y el aviso «proyección, no retención» | verde |
| UI-2 | Sin estimación, sin card | Vitest | `estimatedTaxLiability = null` ⇒ la card no existe (no se pinta un 0 falso) | verde |
| UI-3 | Comisiones del ejercicio | Vitest | Etiqueta «Comisiones de operaciones» + hint «sin custodia»; ya no aparece «Histórico acumulado» | verde |
| UI-4 | Moneda en todos los importes | Vitest | `formatPrice(..., report.currency)` en resumen y tablas | verde |
| UI-5 | Estado vacío | Vitest | «Sin ventas con plusvalía/minusvalía en …» cuando no hay realizadas | verde |
| UI-6 | Error con detalle | Vitest | Se muestra el mensaje del `ApiError`, no un texto genérico | verde |
| UI-7 | Efecto colateral declarado | Vitest | El selector se etiqueta «Cuenta activa de la app» y avisa de que cambia la cuenta de la app | verde |
| UI-8 | Deep link al perfil fiscal | Vitest + navegador | Enlace a `/accounts?selected=<id>&tab=config&focus=fiscal` | verde |
| UI-9 | Resumen del perfil aplicado | Vitest + navegador | Muestra `España (ES) · FIFO · transmisiones 0,2 % · retención div. 19 % · plusvalías 19 %` | verde |

### 3.4 UI — panel «Comisiones y fiscal»

| ID | Caso | Capa | Esperado | Estado |
| --- | --- | --- | --- | --- |
| UI-10 | Catálogo único de hints | Vitest | Los cinco presets describen sus números reales desde `@bolsa/shared` | verde |
| UI-11 | Edición marca «Personalizado» | Vitest | Cambiar un número conmuta el preset a `custom` sin perder el resto | verde |
| UI-12 | Jurisdicción aplica preset | Vitest | US → ES repone `capitalGainsTaxPct = 19` (COM-D1) | verde |
| UI-13 | Tipo de plusvalías editable | Vitest | Vacío ⇒ `null` en el PATCH (no estimar) | verde |
| UI-14 | Validación bloquea sin petición | Vitest + navegador | `max < min` ⇒ mensaje claro, botón deshabilitado, **cero** llamadas a la API | verde |
| UI-15 | Mes fuera de rango | Vitest | `validateAccountSettings` rechaza 0 y 13, acepta 1–12 | verde |
| UI-16 | PATCH con el borrador | Vitest + navegador | Un solo `PATCH` con `settings` completo; persiste tras recargar | verde |
| UI-17 | Vista previa = servidor | Vitest | Total 16,05 € para 5 000 con `standard_es`, con el mismo redondeo (COM-D8) | verde |

### 3.5 UI — asistente de alta y ficha de cuenta

| ID | Caso | Capa | Esperado | Estado |
| --- | --- | --- | --- | --- |
| UI-18 | Hints del paso Comisiones | Vitest | Catálogo compartido; «Personalizado» no se ofrece aquí (se afina en Configuración) | verde |
| UI-19 | Resumen del paso Fiscal | Vitest | Tipo de plusvalías, retención, transmisiones e inicio de ejercicio derivados del perfil resuelto | verde |
| UI-20 | Jurisdicción sin proyección | Vitest | US ⇒ «No se estima» y retención 30 % | verde |
| UI-21 | Revisión con detalle | Vitest + navegador | Filas de comisión, coste de una compra de 5 000 (comisión + IVA + transmisiones) y perfil fiscal completo | verde |
| UI-22 | Payload de alta | Vitest | La cuenta ES se crea con `capitalGainsTaxPct = 19` y `presetId = standard_es` | verde |
| UI-23 | Ficha de cuenta | Vitest* | Bloque «Comisiones y fiscal» con el detalle real (perfil + fiscal) | verde |
| UI-24 | `focus=fiscal` | Navegador | El diálogo abre en la pestaña **Fiscal** con `19` en el campo | verde |

\* UI-23 se cubre de forma directa por composición (el bloque usa los mismos helpers verificados
en UI-9/UI-17) y de forma indirecta por el barrido global; no tiene un test dedicado propio.

---

## 4. Evidencias

Directorio: `docs/engineering/evidence/fiscal-comisiones-2026-10-30/`.

### 4.1 Gates automatizados

| Evidencia | Contenido | Estado |
| --- | --- | --- |
| `pytest-area.txt` | 60 pruebas del área (dominio + integración PostgreSQL + contrato de esquemas) | verde |
| `ruff.txt` | `ruff check` sobre los cuatro ficheros Python tocados | verde |
| `vitest-area.txt` | 22 pruebas de las tres suites UI nuevas | verde |
| `vitest-shared.txt` | 19 pruebas de paridad del paquete `@bolsa/shared` | verde |
| `vitest-web-full.txt` | Suite completa de `apps/web`: **347 ficheros / 2604 pruebas** | verde |
| `tsc.txt` | `pnpm --filter @bolsa/web typecheck` (exit 0) | verde |
| `eslint.txt` | `eslint` sobre los 11 ficheros web tocados — exit 0, sin problemas | verde |
| `eslint-shared.txt` | `eslint` sobre `account-settings.ts` y su test — exit 0 | verde |
| `contract-check.txt` | `pnpm contract:check` — `openapi.json` y `schema.d.ts` al día | verde |

### 4.2 Peticiones reales capturadas (`red-*.json`)

| Evidencia | Caso | Resultado |
| --- | --- | --- |
| `red-tax-report.json` | FIS-2 / UI-1 | Cuenta temporal ES: `realizedLines[0].realizedGain = 98,185`, `netRealizedGain = 98,185`, **`estimatedTaxLiability = 18,655`**, `feesPaidTotal = 2,42`, `periodLabel = «Ejercicio 2026/27»` |
| `red-tax-report-vacio.json` | FIS-3 / UI-2 | Cuenta demo del operador sin ventas: `estimatedTaxLiability = null`, `feesPaidTotal = 0` |
| `red-account-settings.json` | FIS-8 / UI-16 | Tras guardar desde el panel: `capitalGainsTaxPct = 19`, `fiscalYearStartMonth = 4` (persistido) y `presetId = standard_es` |

Observación: al cambiar `fiscalYearStartMonth` de 1 a 4 el `periodLabel` pasó de
«Año natural 2026» a «Ejercicio 2026/27», es decir, el guardado del panel **sí** llega al cálculo
del backend y no es decorativo.

### 4.3 Recorrido en navegador (`ui-*.png`)

| Evidencia | Qué muestra |
| --- | --- |
| `ui-fiscal-impuesto-estimado.png` | `/fiscal` con la card **«Impuesto estimado sobre plusvalías — 18,66 €»**, hint `FIFO · tipo 19 % sobre el neto realizado · proyección, no retención` y el aviso del IRPF progresivo |
| `ui-fiscal-sin-plusvalias.png` | `/fiscal` sin ganancias realizadas: **sin** card de impuesto, «Comisiones de operaciones 0,00 € · Año natural 2026 · sin custodia» y estado vacío honesto |
| `ui-panel-fiscal-deeplink.png` | Deep link `?tab=config&focus=fiscal`: el diálogo abre en la pestaña **Fiscal** con «Tipo estimado sobre plusvalías (%) = 19» |
| `ui-panel-validacion-bloqueada.png` | `mín 5 / máx 2`: mensaje «El máximo por operación no puede ser menor que el mínimo» y botón **deshabilitado** |
| `ui-panel-comisiones-catalogo.png` | Catálogo de presets con hints derivados (incluido «Sin comisión de operación · los impuestos dependen de la jurisdicción») y vista previa de la compra de 5 000 |
| `ui-wizard-paso-fiscal.png` | Paso **Fiscal** del asistente con el bloque «Lo que aplicará el servidor» (plusvalías 19 %, retención 19 %, transmisiones 0,2 %, «Desde el 1 de enero») |
| `ui-wizard-revision.png` | Paso **Revisión** con comisión, coste de una compra de 5 000 (`16.05 € · comisión 5.00 € + IVA 1.05 € + transmisiones 10.00 €`) y perfil fiscal completo |

Nota técnica de las capturas: el panel del navegador integrado no repinta frames si el viewport no
cambia, así que las instantáneas se tomaron con `Page.captureScreenshot` tras forzar un
`Emulation.setDeviceMetricsOverride` (y se limpió con `Emulation.clearDeviceMetricsOverride`).
Sin ese forzado, capturas consecutivas devolvían el **mismo** hash (frame obsoleto).

---

## 5. Bitácora

| Fecha | Paso | Resultado |
| --- | --- | --- |
| 2026-10-30 | Baseline | Stack arriba, `/fiscal` y panel renderizando; 30 ficheros sin commit de otra área |
| 2026-10-30 | Contrato (`@bolsa/shared`) | `capitalGainsTaxPct` ES 19, `quantizeMoney4`, catálogo único de presentación — 19 pruebas verdes |
| 2026-10-30 | Dominio | `test_account_settings_presets.py` nuevo (catálogo + redondeo + «none» con transmisiones) |
| 2026-10-30 | Backend fiscal | Estimación cubierta en dominio e integración; `STANDARD_ES_SETTINGS` pasa a 19 |
| 2026-10-30 | `/fiscal` | Card de impuesto, etiqueta de comisiones, moneda, error con detalle, selector declarado y deep link |
| 2026-10-30 | Panel y asistente | Tipo editable, validación cliente, resumen fiscal y Revisión con detalle |
| 2026-10-30 | Ficha de cuenta | Bloque «Comisiones y fiscal» con detalle real y `focus=fiscal` |
| 2026-10-30 | UI tests | 3 suites nuevas (22 pruebas) + suite web completa (2604) en verde |
| 2026-10-30 | En vivo | Recorrido completo con 7 capturas y 3 respuestas reales; entorno restaurado |

---

## 6. Límites declarados

1. **El tipo de plusvalías es una proyección de un solo tramo.** El IRPF del ahorro es progresivo
   (19/21/23/27/28 %). La UI lo dice explícitamente; no se implementa la escala.
2. **No se ha añadido ninguna migración ni campo nuevo**: todo el contrato ya existía en el wire.
   Los cambios son de alineación y de presentación.
3. **La ruta en vivo escribió estado real.** Para poder ver la card de impuesto se creó una cuenta
   demo temporal (`QA fiscal temporal 2026-10-30`), se le sembró un mandato para pasar el gate de
   apertura, se ejecutó compra 10 @100 + venta 5 @120 y se ajustó `fiscalYearStartMonth` desde el
   panel. Al terminar:
   - cuenta temporal **cerrada** y purgada con el helper de tests (`purge_accounts`, mismo orden de
     FK que usan las suites de integración);
   - el perfil de catálogo autogenerado por el alta (`PROF-45b646297809`) **borrado** vía
     `DELETE /api/investor-profiles/{id}`;
   - la cuenta del operador queda **intacta**: `standard_es`, ES, `capitalGainsTaxPct = 19`,
     `stampDutyBuyPct = 0,2`, `vatOnCommissionPct = 21`, `fiscalYearStartMonth = 1`;
   - la cuenta activa del navegador se devolvió a `default-account-seed`.
4. **`DELETE /api/accounts/{id}` devolvió 500** sobre la cuenta temporal ya cerrada. La secuencia
   ejecutada fue: borrar primero el perfil de catálogo y después la cuenta. No se ha investigado la
   causa raíz (queda como observación, no como defecto cerrado): la limpieza se completó con el
   helper de purga. **No se ha modificado el endpoint.**
5. **La suite Python completa no se ejecutó** con el stack vivo: los tests de roundtrip de Alembic
   hacen `downgrade/upgrade` sobre `bolsa_v1`. Se ejecutaron las suites del área (§4.1).
6. **`feesPaidTotal` no incluye custodia** y la UI no la suma en ningún sitio; si en el futuro se
   quiere un total con custodia, necesita su propio campo en el DTO.
7. **UI-23 (ficha de cuenta) no tiene test dedicado**: se apoya en los helpers ya verificados y en
   el barrido global de primer nivel.
8. **No se ha tocado** el flujo de dividendos: `dividendWithholdingPct` viaja y se muestra, pero
   todavía no hay cálculo de retención sobre dividendos registrados.
