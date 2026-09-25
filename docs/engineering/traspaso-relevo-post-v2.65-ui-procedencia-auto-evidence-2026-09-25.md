# Traspaso / relevo — post `v2.65-beta` (`AUTO-20D` · UI de procedencia del AUTO EVIDENCE REPORT)

**Para el siguiente agente.** Lee esto antes de tocar nada. Fuente de verdad de la fase:
[plan](./plan-v2-65-ui-procedencia-auto-evidence-2026-09-25.md) ·
[audit-pack](./audit-pack-v2-65-ui-procedencia-auto-evidence-2026-09-25.md) ·
[invariante PAPER virtual](./invariante-paper-virtual-2026-09-25.md) ·
[arranque del auditor](./arranque-auditor-v2.65-ui-procedencia-auto-evidence-2026-09-25.md).

## 1. Dónde estamos
    10|
- **`v2.65-beta` (`1.90.0-beta`)** sellada. Base de auditoría: el cierre de `v2.64-beta`.
- `AUTO-20D` añade la **superficie de cabina** que lee el artefacto `auto20c_evidence_artifact_v1` y muestra
  un **badge de procedencia** prominente (`PAPER REAL` / `FIXTURE SINTÉTICO` / `SIN MATERIAL` /
  `DESCONOCIDA`), sin recalcular métricas y sin tocar la cadena Python.
- El **reparto no se movió**: `auto18-v1` / `auto15-v1`; **sin migración** (head en `046_fill_reference_mid`).

## 2. Qué se hizo (y por qué)

| Pieza | Qué cambia |
|---|---|
    20||---|---|
| **Módulo puro** | `apps/web/src/features/operational-console/auto-evidence-report.ts`: `parseAutoEvidenceArtifact`, `classifyEvidenceSource`, `buildEvidenceView`, `integrityWarnings`. Rechaza esquemas ajenos con motivo y nunca inventa un `0` (`null` ⇒ `NO MEDIDO`) ni un veredicto (ausente ⇒ `INCONCLUSIVE`). |
| **Archivo local** | `apps/web/src/stores/auto-evidence-archive-store.ts`: zustand `persist`, cap 10, dedupe por `schema|materialOrigin|fingerprint`. Sin backend, sin migración. |
| **Sección** | `auto-evidence-section.tsx` (`OpsAutoEvidenceSection`): badge SOURCE en banda propia, tres ejes separados (origen / ejecución / dinero real), bloques Material / Calibration / Declared / perímetro, avisos de integridad, import por fichero o pegado, limpiar. |
| **Montaje** | `operational-console-page.tsx`: la sección entra en la **rejilla de primer nivel** (siempre visible). |
| **Tests** | 30 nuevos (report 19 · sección 7 · store 4) + el de la página actualizado. |

**Por qué la UI no recalcula:** el artefacto ya trae el `report` **verbatim** (decisión de `AUTO-20C`); la
cabina solo lo presenta. Re-derivar R/WFE/coverage sería crear un segundo camino que pudiera divergir en
    30|silencio, justo lo que la casa prohíbe.

## 3. Estado medido (compuertas)

* `pnpm --filter @bolsa/web test` — **1320 passed** (232 ficheros).
* `pnpm --filter @bolsa/web typecheck` — **OK**.
* `pnpm --filter @bolsa/web lint` — **0 errores** (23 warnings preexistentes).
* `packages/py` y el freeze **intactos** (el diff no los toca); **sin migración**.

## 4. Huecos declarados (lo que ESTA fase NO cierra)

1. **La corrida PAPER real (AUTO-20D) sigue sin ejecutarse.** Comprobación read-only del PostgreSQL local:
   `sim_fill_finance_context` = **628 fills, `cycle_id` NULL en todos** ⇒ el exportador bloquearía con
    40|   `exit 2`. El estado real es **`SIN MATERIAL · NO MEDIDO`**, que la UI ya declara. Bloqueo por
   **material**, no por código.
2. **Import manual**: no hay endpoint que sirva el artefacto; se sube o se pega en la sección.
3. **Procedencia autodeclarada**: la huella sella el universo, no es prueba criptográfica de origen.
4. `P(R>0)`, correlación y current-regime gating siguen fuera (AUTO-21).

## 5. Ficheros clave

* `apps/web/src/features/operational-console/auto-evidence-report.ts` — **nuevo**: parser + procedencia + vista.
    50|* `apps/web/src/stores/auto-evidence-archive-store.ts` — **nuevo**: archivo local.
* `apps/web/src/features/operational-console/auto-evidence-section.tsx` — **nuevo**: la sección.
* `apps/web/src/features/operational-console/operational-console-page.tsx` — montaje primer nivel.
* `auto-evidence-report.test.ts`, `auto-evidence-section.test.tsx`, `auto-evidence-archive-store.test.ts` — **nuevos**.

## 6. Paso operativo del propietario (no lo fabrica la fase)

Con **≥32 ciclos medidos por estrategia** en una cuenta PAPER (**virtual**):

```powershell
uv run --no-sync python apps/api-python/scripts/paper_cycles_export.py --account-id <uuid> --strategy-version <v> > ciclos.json
    60|uv run --no-sync python scripts/research/auto_replay_battery.py --walk-forward --cycles ciclos.json --out AUTO20C_REAL_PAPER_REPORT.json --render AUTO20C_REAL_PAPER_REPORT.txt
```

Importar `AUTO20C_REAL_PAPER_REPORT.json` en la sección **Evidencia AUTO (AUTO-20D)** de la Consola
operacional y aceptar honestamente cualquiera de los tres veredictos **sin tocar umbrales**.

## 7. Cómo re-verificar en frío

```powershell
pnpm --filter @bolsa/web test
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web lint
```

    70|
## 8. Reglas de la casa que siguen vigentes

* **PAPER = dinero VIRTUAL** — ninguna operación se ejecuta sobre XTB ni plataforma real.
* **Lo que no se midió se declara** — nunca un veredicto, un conteo ni un cero inventados.
* **Un solo productor por medida** — la UI **presenta** el informe, no lo recalcula.
* **Nada de evidencia mueve el reparto** — `auto18-v1` no se toca sin fase propia.
* **`INCONCLUSIVE` es un resultado**, no un error: no se "arregla" bajando `min_is`/`min_oos`/`folds`.
