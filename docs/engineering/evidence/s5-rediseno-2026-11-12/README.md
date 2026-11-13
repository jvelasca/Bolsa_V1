# Evidencia S5 — Rediseño S1–S4 (2026-11-12)

Capturas y guion de reproducción de la certificación
[`certificacion-s5-rediseno-2026-11-12.md`](../../certificacion-s5-rediseno-2026-11-12.md).

## Reproducir

```powershell
# 1) Matriz unitaria (incluye los 6 escenarios y el ratchet de formato)
pnpm --filter @bolsa/web test -- trading-operativa-panel.maximized
pnpm --filter @bolsa/web test

# 2) E2E determinista (auto-arranca Vite; API simulada)
$env:E2E_RUN="1"; pnpm --filter @bolsa/web exec playwright test gp-s5-rediseno

# 3) No regresión de accesibilidad en rutas tocadas
$env:E2E_RUN="1"; pnpm --filter @bolsa/web exec playwright test gp-e2e-ui5-0-axe-touched-routes-mock
```

Si Playwright acaba de instalarse: `pnpm --filter @bolsa/web exec playwright install chromium`.

Las capturas se escriben aquí automáticamente al correr el spec (no son baselines de
`toHaveScreenshot`; no hay comparación de píxeles).

## Mock determinista (`gp-s5-rediseno-s1-s4.spec.ts`)

Escenario y datos en `apps/web/e2e/helpers/s5-decision-scenarios.ts`. Todos a 1600×1000 con
DECISIÓN maximizada.

| Archivo | Escenario | Qué debe verse |
|---|---|---|
| `s5-favorable_sin_posicion-1600x1000.png` | `buy` 85, sin posición, compuertas abiertas | «Recomendación favorable» · «Entrada disponible»; CTA de preparar habilitado |
| `s5-posicion_con_respaldo-1600x1000.png` | `hold_watch` 72 + posición | «Posición abierta» · «Salida en ACCIÓN»; sin CTA de entrada |
| `s5-posicion_sin_respaldo-1600x1000.png` | `overbought` 61 + posición | «Posición sin respaldo» · «Salida en ACCIÓN»; sin «Sobrecomprado» |
| `s5-sin_datos-1600x1000.png` | cartera no medida | «Sin datos suficientes» · «Sin actuación»; aviso de cartera no medida |
| `s5-entrada_bloqueada-1600x1000.png` | `buy` sin posición + kill switch | «Entrada bloqueada» · `data-blocked-reason="entradas_bloqueadas"`; CTA deshabilitado «Entradas bloqueadas» |
| `s5-salida_con_entradas_bloqueadas-1600x1000.png` | `hold_watch` + posición + kill switch | «Salida en ACCIÓN»; sin motivo de bloqueo (la salida sigue disponible) |
| `s5-responsive-1600x1000.png` | favorable | grid de 3 columnas |
| `s5-responsive-1200x900.png` | favorable | grid de 2 columnas |
| `s5-responsive-403x900.png` | favorable | `data-surface="narrow"`, sin hero (composición anterior) |
| `s5-superficie-dock-1600x1000.png` | favorable | `data-surface="dock"`, sin hero; dictamen compacto en Evidencia |
| `s5-s2-contexto-tecnico-1600x1000.png` | favorable, 140 velas | readout `data-status="ok"` y «Informan; no autorizan entradas» |
| `s5-s3-asesor-cartera-posicion-1600x1000.png` | posición | fila `posicion_abierta` en Asesor/Cartera |
| `s5-s3-asesor-cartera-sin-posicion.png` | sin posición | fila `recomendacion_favorable`; sin «Sobrecomprado» |

## Stack real (`http://localhost:5173`, sin mocks)

Script efímero (no versionado): abre `/trading`, maximiza DECISIÓN y recoge el texto real;
después visita `/research?tab=cartera`. Instrumento activo: BBVA.

| Archivo | Lectura |
|---|---|
| `s5-real-maximizada-1600x1000.png` | hero `evaluado_sin_oportunidad` · «Sin oportunidad»; actuación `sin_actuacion`; dictamen «Mantener» 68/100 |
| `s5-real-maximizada-1200x900.png` | misma lectura; grid de 2 columnas |
| `s5-real-maximizada-403x900.png` | `data-surface="narrow"`, sin hero |
| `s5-real-asesor-cartera-1600x1000.png` | 80 valores en Estudio, 0 con posición, 80 `sin_datos` («Sin dictamen») |

La cartera real **no** alcanza los seis escenarios semánticos: solo el estado
`evaluado_sin_oportunidad` y, en Asesor, `sin_datos`. Los seis escenarios quedan certificados
por la matriz determinista. Consola de `/trading` sin errores durante el pase.

## Reserva

La captura del pase real no cubre la deuda `heading-order` de S2 detectada por
`gp-e2e-ui5-0-axe-touched-routes-mock` en `/trading @desktop` (impacto `moderate`,
best-practice; no WCAG A/AA). Ver §8 de la certificación: no se corrige en S5.

**Reserva aceptada (2026-11-12).** Producto aprobó el cierre de S5 asumiendo esta reserva. La
corrección de `heading-order` queda como **seguimiento S2 independiente**, no ejecutado y sin
autorización en este cierre.

## Estado del cierre

Aprobación de producto el 2026-11-12 (acta en §11 de la certificación). Documento **sin
versionar**: `HEAD` en `bcdc4584`, índice vacío y rama `feat/f4-067-opinion-account-scope` sin
cambios. `PROJECT_STATE.md` y `CHANGELOG.md` quedan excluidos por decisión de producto; S0/F4-067
sigue sin autorizar.
