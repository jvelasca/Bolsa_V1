# Premisas responsive — Bolsa V1

Documento de referencia (jul 2026) para **cualquier** cambio de layout en trading y gráficos.  
Complementa [CHART_RESPONSIVE.md](./CHART_RESPONSIVE.md) y [UI_PLATFORM.md](./UI_PLATFORM.md).

---

## 1. Qué medimos (y qué no)

| Medimos | No medimos (solo) |
|---------|-------------------|
| Ancho del **panel del gráfico** (`chart-workspace-shell`) | Ancho del monitor |
| Ancho del **dock de listas** al redimensionar | Breakpoints genéricos `sm:` / `md:` en el chart |

**Motivo:** en un monitor grande el gráfico puede quedar estrecho (listas al 40 %, inspector abierto, operaciones abajo). El responsive debe reaccionar al **espacio real del componente**.

**Excepción:** chrome global fuera del chart (p. ej. barra de estado inferior) puede usar `@media` del viewport.

---

## 2. Contenedor raíz

```css
.chart-workspace-shell {
  container-type: inline-size;
  container-name: chart-workspace;
}
```

Todas las reglas `@container chart-workspace (…)` viven en `apps/web/src/index.css`.

---

## 3. Nombres de barras (glosario)

| Barra | Zonas típicas | Archivo |
|-------|---------------|---------|
| **Global del workspace** | Indicadores, plantillas, C/V, BD, TV, Inspector | `chart-toolbar-global-bar.tsx` |
| **De datos del gráfico** (por tab) | **Escala**, **Valor**, **Cursor**, atajos inspector, ⚙ | `chart-toolbar-chart-bar.tsx` |

«Escala / Valor / Cursor» = **barra de datos del gráfico** (no confundir con la barra global).

---

## 4. Reglas de diseño (no negociables)

1. **Altura de fila fija** en zonas de datos: `1.375rem`. El contenido extra **no** debe romper la altura; usar scroll horizontal **dentro** de la zona.
2. **Ninguna prestación se elimina** en modo estrecho: se reordena, apila o desplaza con scroll; no se ocultan acciones críticas sin equivalente (menú, inspector, etc.).
3. **Apariencia conservada** en panel ancho: una fila lógica, separadores `|`, tipografía y chips iguales.
4. **Dos modos de usuario** (configurables con `wrapRows`):
   - **Adaptativo** (`wrapRows: true`, defecto): varias filas según ancho del panel; atajos a la derecha o en segunda rail.
   - **Scroll** (`wrapRows: false`): una sola fila con `overflow-x: auto` en toda la barra.
5. **Chips y favoritos** no empujan el layout: clase `chart-bar-zone-scroll` en la fila de chips.
6. **Zonas apilables** en panel estrecho: cada zona (Escala, Valor, Cursor) puede ocupar **100 %** del ancho y scroll interno.
7. **Atajos del inspector** permanecen agrupados a la **derecha** en panel ancho; en panel estrecho pasan a una **segunda rail** alineada a la derecha.

---

## 5. Umbrales del panel del gráfico

| Umbral | Efecto en barra de datos |
|--------|--------------------------|
| ≥ 48 rem | Una fila: datos a la izquierda, atajos + ⚙ a la derecha |
| 32 – 48 rem | Datos con `flex-wrap` entre zonas; atajos en segunda rail |
| &lt; 32 rem | Cada zona (Escala, Valor, Cursor) al **100 %** de ancho; chips con scroll interno |
| &lt; 28 rem | Etiquetas abreviadas (Ind., S/gráf.) — ver CHART_RESPONSIVE.md |

---

## 6. Patrón de zona (plantilla)

```tsx
<div className={CHART_BAR_ZONE_ROW_CLASS}>
  <span className={CHART_BAR_ZONE_LABEL_CLASS}>Escala</span>
  <div className={CHART_BAR_ZONE_SCROLL_ROW_CLASS}>
    {/* chips shrink-0 */}
  </div>
</div>
```

**No** usar `flex-wrap` en la fila de chips salvo en modo scroll de barra completa desactivado y documentado.

---

## 7. Configuración de usuario

| Control | Ubicación | Campo |
|---------|-----------|-------|
| Apilar zonas / scroll horizontal | ⚙ global → Global | `chartLayoutDefaults.wrapRows` |
| Override por gráfico | ⚙ del gráfico → Este gráfico | `toolbar.layout.wrapRows` |

Texto UI: «Apilar zonas en varias filas si no caben (sin scroll horizontal)».

---

## 8. Checklist al añadir una zona nueva

- [ ] ¿Usa `CHART_BAR_ZONE_ROW_CLASS` + `CHART_BAR_ZONE_SCROLL_ROW_CLASS`?
- [ ] ¿Los chips tienen `shrink-0`?
- [ ] ¿Se probó con listas al 45 % y inspector abierto?
- [ ] ¿Se probó con `wrapRows` true y false?
- [ ] ¿Documentado en CHART_RESPONSIVE.md si cambia umbrales?

---

## 9. Historial

| Fecha | Cambio |
|-------|--------|
| Jul 2026 | Refactor barra de datos: rails primary/actions, container queries 48/32 rem, chips siempre scroll interno |
| Jul 2026 | Snapshot previo: `docs/architecture/_snapshots/chart-toolbar-responsive-2026-07-08.md` |
