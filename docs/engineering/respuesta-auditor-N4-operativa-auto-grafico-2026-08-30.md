# Respuesta — N4 — Operativa AUTO + Gráfico

> **Fecha:** 2026-08-30  
> **Lector:** Owner producto (actúa como N4 — invariantes / mecánica).  
> **Documento evaluado:** [`estudio-operativa-auto-y-grafico-2026-08-28.md`](./estudio-operativa-auto-y-grafico-2026-08-28.md)  
> **Registro:** cierra pendiente N4 en §8. **No es implementación.**

---

## AUTO

- **Opción elegida:** A-β (destino ya cableado en V1.33+); **no** reabrir A-γ.
- **Disensos:** ninguno.
- **Invariantes §2 violadas:** ninguna.
- **Top 3 riesgos (fuera de este epic):** 1) flip `PAPER_D_EXECUTE` · 2) Radar/Hoy como trigger · 3) sizing paralelo.

---

## Gráfico

- **Opción elegida:** **B-γ** (Sandbox G3 + commit G4 vía Confirm).
- **B-δ:** RECHAZADA (no mutar `Position` / `PositionRevision` desde el gráfico).
- **Líneas draggables (slice V1.34):** **solo stop vigente**. Entrada / T1 / T2 / trail **fuera** (entrada queda deuda post-slice; Deep pedía entrada — owner estrecha a stop-only).
- **Disensos vs Deep:** stop-only (no entrada) en el primer corte. Geometría única = `operational-levels.ts` / `validateOperationalLevels` — acuerdo.

### Respuestas puntuales (B1–B7)

| ID  | Respuesta                                                                                                            |
| --- | -------------------------------------------------------------------------------------------------------------------- |
| B1  | Solo **stop vigente**. Trail nunca. T1/T2/entrada no draggables en V1.34.                                            |
| B2  | Drag en **ARMED/PREPARADA** y **POSICIÓN**. **Nunca en DISPARADA.**                                                  |
| B3  | Abre **drawer Confirm** real (`SupervisedF3Panel`). Nunca ticket inline.                                             |
| B4  | What-if / ghost solo en G3; commit usa mismos recálculos que el ticket (`signedStop` + risk signature).              |
| B5  | Geometría inválida → no commit; mismos `blockReason` (`stop_wrong_side`, `stop_invalid`).                            |
| B6  | Lectura vía `useInstrumentOperationalContext`; al commit, Confirm es SoT del intent (no reescribir plan silencioso). |
| B7  | Fuera de Estudio / sin niveles de plan: **G0** (sin drag).                                                           |

---

## Cruce A×B

- El gráfico **nunca autoriza**.
- Commit = pre-fill Confirm con `signedStop`; firma humana obligatoria.
- `signedStop` humano posterior gana sobre AUTO.
- Toast T1 informativo (H2); reduce → Confirm / ExitPermission, no drag T1.

## Condiciones de implementación

- Tests: geometría drag ≡ `operational-levels` / niveles chart; no abre Confirm si `blockReason`.
- Fuera: OCO · trail autoridad · B-δ protect directo · entrada/T1/T2 drag · móvil · flip execute · thaw.

**Una línea:** B-γ stop-only → Confirm; G0 fuera de fases permitidas; B-δ no.
