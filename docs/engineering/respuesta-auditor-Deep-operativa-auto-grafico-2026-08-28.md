# Respuesta — Deep / A0 — Operativa AUTO + Gráfico

> **Fecha:** 2026-08-28  
> **Lector:** Auditoría externa (Claude) — continuación v1.0 → v1.26.  
> **Documento evaluado:** [`estudio-operativa-auto-y-grafico-2026-08-28.md`](./estudio-operativa-auto-y-grafico-2026-08-28.md)  
> **Registro:** archivado para §8 del estudio. **No es implementación.**

---

## AUTO

- **Opción elegida:** A-β (Paridad SEMI), arranque secuenciado tipo A-δ.
- **A-γ (Libro clásico):** RECHAZADA sin waiver. Mismo patrón de bug ya cerrado en v1.25/v1.26 (dos fuentes de tamaño).
- **Disensos:** ninguno respecto a descartar A-γ. Prefiere A-β como destino, no solo contraste vs A-α.
- **Invariantes §2 violadas:** A-γ viola la 4 (un solo TradePlan SoT). A-α/A-β/A-δ no.
- **Top 3 riesgos:**
  1. Sizing paralelo silencioso si A-β se implementa sin `resolveSupervisedOpeningQuantity` también en AUTO.
  2. EdgeReport calculado pero no exigido en `paper_auto` (`check_auto_live` solo con `auto_live=True`).
  3. CTA de AUTO compitiendo con Confirmar SEMI en la misma tarjeta de fase.

### Respuestas puntuales (A1–A7)

| ID  | Respuesta                                                                                     |
| --- | --------------------------------------------------------------------------------------------- |
| A1  | Solo dictamen/alarma de Estudio en el arranque (A-δ); ampliar a Radar/Hoy tras telemetría A6. |
| A2  | TradePlan TRIGGERED como sizing SoT, sin excepción.                                           |
| A3  | Mismo lenguaje de razones nombradas que `check_opening`. Nunca silencioso.                    |
| A4  | Interruptor de cuenta/estrategia; nunca en la misma tarjeta que Confirmar.                    |
| A5  | Sí puede proteger/reducir sin Confirm (`ExitPermission` asimétrico).                          |
| A6  | Telemetría P1–P5 en verde + mismo umbral de EdgeReport que SEMI.                              |
| A7  | Copy: «Libro AUTO».                                                                           |

**Condición extra:** exigir EdgeReport/credibilidad también en paper_auto si AUTO gana paridad de sizing.

---

## Gráfico

- **Opción elegida:** B-α para V1.26b; B-γ destino.
- **B-δ:** aplazada.
- **Líneas draggables (si aplica, solo tras §8 ACUERDO):** stop vigente y entrada pre-TRIGGERED. Trail **nunca**. T1/T2 solo como input a Confirm.
- **Disensos:** ninguno con B-α → B-γ. Condición técnica: recálculo what-if del drag **debe** reutilizar `validateOperationalLevels` / `adverse_exposure` (`operational-levels.ts`), no una geometría distinta.

### Respuestas puntuales (B1–B7)

| ID  | Respuesta                                                                       |
| --- | ------------------------------------------------------------------------------- |
| B1  | Stop/entrada sí; trail no; T1/T2 solo vía Confirm.                              |
| B2  | Arrastre en ARMED/PREPARADA y POSICIÓN. **Nunca en DISPARADA.**                 |
| B3  | Drawer de Confirm real. Nunca ticket inline.                                    |
| B4  | What-if solo en sandbox/ghost (G3); commit con `buildConfirmScenarioCandidate`. |
| B5  | Mismos `blockReason` (`stop_wrong_side`, `stop_invalid`).                       |
| B6  | Sync bidireccional con Operativa (`useInstrumentOperationalContext`).           |
| B7  | Fuera de Estudio: G0.                                                           |

---

## Cruce A×B

- DISPARADA + AUTO: AUTO no autoriza vía gráfico. `signedStop` humano posterior gana.
- Toast T1: informativo (H2). CTA de reducir → Confirm/ExitPermission.
- Empate: gana integridad V1.26 sobre comodidad gráfica.

## Condiciones de implementación

- Tests: paridad TS/Python de geometría; contrato que impida geometría distinta en el drag.
- Fuera de alcance: OCO/bracket broker; promover trail; ampliar AUTO más allá de A-β sin A6 verde.

**Una línea:** AUTO → A-β (EdgeReport en paralelo); Gráfico → B-α (toasts) → B-γ (tras POM + §8), geometría única.
