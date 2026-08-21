# Estudio teórico — flujo SEMI vs apps top (R-12 Track B)

> **Padre:** [`plan-r12-auditoria-ux-2026-08-21.md`](./plan-r12-auditoria-ux-2026-08-21.md).
> **Estado:** teórico / comparativo. **Cero código frontend.** Track C bloqueado hasta aprobación línea a línea.
> **AsOf:** 2026-08-21 · audiencia: profesional de mercados que **no** es ingeniero de software.
> **Fuentes de nuestro lado:** `apps/web/src/app.tsx`, `trading-operativa-panel.tsx`, `supervised-f3-panel.tsx`, `demo-operating-modes-brief-2026-08-03.md`, ADR-019/023/024.

---

## 1. Qué debe sentir el usuario

Una frase: **«La app propone; yo firmo; el libro cuadra.»**

SEMI no es un motor oculto ni un laboratorio. Es un bucle diario:

1. Universo vigilado (Estudio)
2. Señales (Radar)
3. Dictamen junto al gráfico
4. Confirmar (cantidad, H≠M, sí/no)
5. Libro (posiciones + historial)

El laboratorio (backtests, DÍA D, Coach) es **otra puerta**, no el camino de cada mañana.

---

## 2. Cómo lo hacemos hoy (evidencia)

El camino real tiene ~12 pasos y **tres hubs** para un solo bucle mental:

| Hub         | Ruta           | Rol                                                                |
| ----------- | -------------- | ------------------------------------------------------------------ |
| Laboratorio | `/backtests`   | Wizard, Finalistas, Lista AUTO (~4513 LOC en `backtests-page.tsx`) |
| Asesor      | `/research`    | Diario, opiniones, alarmas FA                                      |
| Radar       | `/screeners`   | Scans, trackers, Paper D                                           |
| Mesa        | `/trading`     | Gráfico + watchlist + Operativa                                    |
| Confirm     | **no es ruta** | Ayuda → Plataforma IA → `supervised-f3-panel.tsx`                  |

Modo SEMI vive en Cuentas → Config, no en la mesa. AUTO se **ve** (pill, armado, kill switch) pero `PAPER_D_EXECUTE` está OFF: parece ejecutable y no lo es.

Patrón de producto que **sí** es ventaja y no se copia de nadie: LLM interpreta → motor determinista → humano confirma → Execution Router → paper con ledger. LAB ≠ TRADING (ADR-019).

---

## 3. Cómo lo hacen las apps top (rúbrica común)

Dimensiones: bucle único, dónde se confirma, visibilidad del modo, jerarquía de la mesa, IA como copiloto, vocabulario, tiempo hasta el primer fill paper.

### TradingView

- **Bucle:** un gráfico + watchlist + alertas. Investigación y ejecución se sienten el mismo sitio (broker embebido opcional).
- **Confirm:** ticket de orden en el gráfico o panel de trading, no un menú de ayuda.
- **Modo:** paper vs live es un selector explícito de cuenta/broker.
- **IA:** Supercharts / Pine; no un “Confirm F3” separado.
- **Vocabulario:** trader (alerta, orden, posición).
- **Qué nos gana:** un solo sitio para ver y actuar. **Qué no tiene:** embudo científico causal, ledger de custodia/fiscal, IA gobernada.

### IBKR Client Portal / TWS

- **Bucle:** book, ticket, blotter, account window. El profesional espera **libro** y **ticket** como objetos de primer nivel.
- **Confirm:** el ticket es la firma. Preview de margen/comisión antes de send.
- **Modo:** paper trading es una cuenta distinta, no un flag escondido.
- **Vocabulario:** orden, ejecución, comisión, buying power.
- **Qué nos gana:** claridad de “esto es dinero”. **Qué no tiene:** research funnel ni dictamen TA/FA unificado.

### thinkorswim

- **Bucle:** monitor + charts + Analyze + Activity. Pesado, pero cada pestaña es un **oficio**.
- **Paper:** OnDemand / paper money como entorno, no un modal de Help.
- **Qué nos gana:** separación Lab vs mesa sin mezclar nombres. **Qué no tiene:** nuestro IO/Estudio.

### Trading 212 / eToro (claridad retail)

- **Bucle:** buscar → ficha → comprar. Tres toques.
- **Confirm:** bottom sheet con importe. Cero jerga de ingeniería.
- **Qué nos gana:** tiempo a primer fill. **Qué no copiamos:** copy trading, CFD, gamificación. Nuestro usuario es profesional: quiere **por qué** y **rastreo**, no un slider.

### Koyfin (research → tesis)

- **Bucle:** universo → snapshot FA → watchlist. No ejecuta.
- **Qué nos gana:** jerarquía de tesis (primero el valor, después el timing). Encaja con nuestro Asesor/Opiniones, que hoy está **separado** del Confirm.

### TrendSpider / Composer (semi-auto)

- **Bucle:** regla o estrategia → alerta o rebalance → revisión humana.
- **Confirm:** Composer muestra el trade propuesto antes de ejecutar (cuando no es fully auto).
- **Qué nos gana:** “propuesta” como objeto de UI, no como cola escondida en Ayuda.

---

## 4. Qué hacemos mejor (no negociable)

| Ventaja                         | Por qué un profesional la notaría                        |
| ------------------------------- | -------------------------------------------------------- |
| Ledger + Decimal + idempotencia | El paper **cuadra**. Retail paper suele ser un slider    |
| Embudo causal Lab → Finalistas  | No hay look-ahead disfrazado de backtest                 |
| LAB ≠ TRADING                   | No contamina el libro con experimentos                   |
| IA gobernada                    | El modelo no gasta dinero; el humano firma               |
| Fiscal + custodia multi-periodo | Coste real de mantener la cuenta, no solo PnL de gráfica |
| Estudio + IO                    | Ranking operativo del universo supervisado               |

Estas ventajas se **diluyen** si Confirm está en Ayuda y el Lab es la home mental.

---

## 5. Dónde nos ganan (fricción real)

1. **Confirm no es de primer nivel.** Tras «Proponer F3» el usuario aterriza en Ayuda. En IBKR/TV la firma es el ticket.
2. **Tres nombres para un bucle** (Lab / Asesor / Rastreadores). El profesional pregunta “¿dónde están mis señales de hoy?”.
3. **SEMI opaco.** Requisitos repartidos: modo en Cuentas, membresía Estudio, supervisión Lab, gates por origen.
4. **AUTO visible pero inerte.** Viola la expectativa “si se ve, se puede usar”.
5. **Vocabulario de ingeniería.** F3, Camino C/D, PAPER_D_EXECUTE, H≠M sin leyenda de trader.
6. **God page de backtests.** 4500 líneas = carga cognitiva antes del primer fill SEMI.

---

## 6. Hipótesis de diseño (papel; Track C si se aprueba)

### Mesa diaria — 5 puertas (vocabulario trader)

| Puerta        | Hoy                              | Mañana (propuesta)                                                                      |
| ------------- | -------------------------------- | --------------------------------------------------------------------------------------- |
| **Universo**  | Listas + Estudio (membresía API) | Misma idea; copy “Universo en vigilancia”                                               |
| **Señales**   | `/screeners` + Asesor alarmas    | Un Radar; Asesor como capa de tesis, no hub rival                                       |
| **Dictamen**  | Columna Operativa                | Se queda en el gráfico (esto ya está bien)                                              |
| **Confirmar** | Ayuda → Plataforma IA            | Ruta `/confirm` o panel anclado en la barra de estado, badge F3 = “Pendientes de firma” |
| **Libro**     | Operaciones + Historial          | Unir copy: “Libro” = posiciones + fills + ledger                                        |

Laboratorio (`/backtests`) sale del nav principal hacia “Laboratorio”. Deep-link Finalistas → Rastreador (B0) se conserva.

### SEMI en una frase de UI

«La app propone operaciones sobre tu Universo. Tú las firmas aquí. Nunca se envían solas.»

AUTO: ocultar o marcar **«No disponible (BETA)»**. No pill armable.

### Research → Radar

El plan [`plan-unificacion-research-radar-2026-08-21.md`](./plan-unificacion-research-radar-2026-08-21.md) se trata como **capítulo de navegación** de este estudio, no como fase de código autónoma. Sin features nuevas.

---

## 7. Track C — bloqueado

No se implementa:

- ruta `/confirm`
- unificación de nav
- split de `backtests-page.tsx`
- ocultar AUTO

hasta que este documento (o una enmienda) esté **aprobado línea a línea** (E1). Entonces: plan C propio, fases pequeñas, tests de UI, HELP.

---

## 8. Criterio de “superar a las top”

No superar a TradingView en dibujo ni a IBKR en routing. Superarlas en **el oficio que nadie cubre bien**:

> Un profesional ve _por qué_ (embudo + dictamen), _firma_ en el mismo sitio donde opera, y el paper tiene la seriedad contable de un broker.

Eso es el delta de producto. Track C, si se abre, solo existe para hacer ese oficio **obvio**.
