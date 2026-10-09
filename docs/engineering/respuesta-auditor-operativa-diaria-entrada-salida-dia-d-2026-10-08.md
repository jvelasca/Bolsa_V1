# Respuesta del auditor externo — operativa diaria (entrada/salida · estrategia/indicadores · DÍA-D)

> **Fecha:** 2026-10-08 · **Lector:** auditoría externa.
> **Documento evaluado:** [`auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md`](./auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md) (punto de entrada: [`arranque-auditor-operativa-diaria-entrada-salida-dia-d-2026-10-08.md`](./arranque-auditor-operativa-diaria-entrada-salida-dia-d-2026-10-08.md)).
> **Base auditada:** `1a2ce597` (sobre el sello [`v2.88.94-beta`](./evidence/v2.88.94/README.md) → `20fd538c`). El rango `20fd538c → 1a2ce597` es **solo documentación** ⇒ el **código auditado es el de `v2.88.94-beta`**.
> **Registro:** dictamen archivado. **Es documentación, no implementación** (`Δ motor = 0`).

---

## 1. Dictamen global

- **Auditoría:** **ACEPTADA**. Es falsable, no fabrica datos y distingue correctamente `ranking ≠ decisión`, `OOS ≠ PAPER`, `UNKNOWN ≠ 0`, `READY ≠ CONFIRMED`.
- **Pilares:** `P2`/`P3`/`P4` quedan en **CUMPLE PARCIAL**. Ninguno se declara CUMPLE completo.
- **Hallazgos:** **no se refuta ninguno de los 12**. Se preservan como CUMPLE `P2-1`, `P3-2`, `P4-1`.
- **Slices:** `S1`–`S3` **aceptados**; `S4` **aceptado como objetivo pero no como contrato actual** (reformulado).
- **Incoherencia documental `§5`:** **confirmada**; se resuelve **alineando la documentación al código**, no forzando `CONFIRMED`.

---

## 2. Veredicto por pilar

| Pilar | Veredicto | Conclusión |
| --- | --- | --- |
| `P2` — Entrada/salida | CUMPLE PARCIAL | Entrada clara; huecos reales en salida y en `prepared`/Journey. |
| `P3` — Estrategia/indicadores | CUMPLE PARCIAL | Tipo ejecutable bien saneado; estrategia + indicadores + razones no llegan juntas a primer nivel. |
| `P4` — DÍA-D | CUMPLE PARCIAL | Medición honesta y fail-closed; sin `CONFIRMED` operativo y veredicto fragmentado. |

## 3. Los 12 hallazgos (no refutados)

| Hallazgo | Dictamen externo |
| --- | --- |
| `P2-1` | **SE SOSTIENE — CUMPLE** (entrada clara: cockpit `full` + HUD `E·S·T1`) |
| `P2-2` | SE SOSTIENE (`ExitPlan` sin precio por peldaño) |
| `P2-3` | SE SOSTIENE (`simple` + `prepared`: solo `Trigger`, no «Entrada») |
| `P2-4` | SE SOSTIENE (T1/T2 del Journey en `sr-only`) |
| `P3-1` | SE SOSTIENE (indicadores no visibles a primer nivel) |
| `P3-2` | **SE SOSTIENE — CUMPLE** (tipo ejecutable saneado; no convertirlo en deuda) |
| `P3-3` | SE SOSTIENE (catálogo del gráfico ≠ evidencia de la estrategia) |
| `P3-4` | SE SOSTIENE (`reasons` almacenadas ≠ presentadas) |
| `P4-1` | **SE SOSTIENE — CUMPLE** (comparador declarado↔ejecutado honesto) |
| `P4-2` | SE SOSTIENE — **CRÍTICO** (`CONFIRMED` reservado, no emitido; `OOS_SUPPORTED ≠ CONFIRMED`) |
| `P4-3` | SE SOSTIENE (medición por artefacto, no en vivo) |
| `P4-4` | SE SOSTIENE (tres vocabularios sin veredicto unificado) |

## 4. Slices `S1`–`S4`

| Slice | Dictamen | Condición |
| --- | --- | --- |
| `S1-exit-precio` | **ACEPTO** | UI-only **solo si** T1/T2 ya están en el objeto que recibe `F3ExitPlanBlock`. Si el backend no los aporta, **se detiene**; no se calcula ni se inventa desde la UI. |
| `S2-entrada-literal` | **ACEPTO con modificación semántica** | Resolver la **semántica** (`Entrada` = nivel operativo; `Trigger` = condición de activación); coexisten solo si son distintos. **No** duplicar la misma línea. |
| `S3-indicadores-razon` | **ACEPTO** | Limitar a **Estrategia → indicadores que la sustentan → razón**; sin ficha técnica. Si no hay evidencia de un indicador, «Sin dato todavía»; **no** deducir del catálogo del gráfico. |
| `S4` (reformulado a **`S4-agregador-evidencia`**) | **ACEPTO el objetivo, NO la implementación tal cual** | El contrato actual no puede producir `CONFIRMED`. Debe **agregar** evidencia: declarado↔ejecutado · OOS · PAPER, y concluir `NO CONFIRMADO` mientras no haya PAPER. **Prohibido** `OOS_SUPPORTED + MATCH → CONFIRMED`. No se lanza hasta corregir el contrato semántico. |

## 5. Incoherencia `§5` y resolución

**Confirmada.** `§5` describía un veredicto `CONFIRMED` que el código **no** emite; `operability_window.py` usa `READY`/`INCONCLUSIVE`. Son **cuatro capas semánticas** distintas:

| Capa | Emisor | Valores |
| --- | --- | --- |
| A · Ventana | `window_gate` (`operability_window.py`) | `READY` / `INCONCLUSIVE` |
| B · Reconciliación declarado↔ejecutado | `dia_d_auto.py` | `MATCH` / `PARTIAL` / `DIVERGENT` / `NOT_MEASURED` |
| C · Evidencia OOS | `dia_d_auto_feedback.py` | `OOS_SUPPORTED` / `MIXED` / `REFUTED` / `NOT_MEASURED` |
| D · Confirmación PAPER | reservado | `CONFIRMED` — **no emitido** |

**Resolución (aplicada):** se corrige `§5.2` de [`PROJECT_PREMISES.md`](../PROJECT_PREMISES.md) para describir el contrato real con la jerarquía `VENTANA → RECONCILIACIÓN → EVIDENCIA OOS → EVIDENCIA PAPER` y las **no-equivalencias** (`READY ≠ CONFIRMED`, `MATCH ≠ CONFIRMED`, `OOS_SUPPORTED ≠ CONFIRMED`). **No se cambia el código** para que emita `CONFIRMED`.

## 6. Trazabilidad SHA (corregida)

El auditor detectó que el paquete documental citaba `e92e9cf5`/`3f98cf48` como `main` vivo. **Corregido:** todo ancla a **`base auditada = 1a2ce597`** y `Δ motor = 0` se expresa con el rango estable respecto al sello `git diff --name-only 20fd538c 1a2ce597 -- packages/py` (vacío).

## 7. Acciones resultantes

1. `§5.2` y fila `P4` de `§6.1` realineadas al contrato real (cuatro capas + no-equivalencias).
2. `S2` reformulado (semántica) y `S4` reformulado a **agregador de evidencia** (no lanzado).
3. SHA anclados a `1a2ce597`; retirado `e92e9cf5`/`3f98cf48`.
4. **`S1`–`S3` implementados** en [`704c4547`](https://github.com/jvelasca/Bolsa_V1/commit/704c4547) (`apps/web/**` + `packages/shared/**`, `Δ motor = 0`, sin contrato HTTP ni Alembic): `S1` objetivos T1/T2 con precio (backend-provided), `S2` `Entrada`≠`Trigger` coexistentes sin duplicar, `S3` cadena estrategia→indicadores→razón en Finalistas. `S4` **sigue no lanzado**.

**Sin motor:** no se toca `packages/py/**`, contrato HTTP ni Alembic; no se emite `CONFIRMED` ni se re-mide DÍA-D.
