# Invariante — PAPER = dinero VIRTUAL, nunca XTB ni plataforma real (`V2.64` / `AUTO-20C`)

**Fecha:** 2026-09-25 · **Fase que lo instala:** `v2.64-beta` (`AUTO-20C`) · **Estado:** vigente.

## 1. La regla, en una línea

Todo el material, los veredictos y los artefactos de la cadena `AUTO`/`PAPER` proceden de una cuenta
PAPER con **dinero VIRTUAL**. **Ninguna operación se ejecuta jamás sobre XTB ni ninguna plataforma real.**

AUTO permanece **SIM-only**: `LIVE_EXECUTION_AUTHORIZED` y `LIVE_EXECUTION_UNLOCKED` en `false`. Esta
fase **no** abre ningún camino LIVE nuevo: solo **declara** la realidad virtual en los artefactos y
bloquea (fail-closed) el sellado cuando la venue no es `paper`.

## 2. Fuente única de verdad

`packages/py/analytics/src/bolsa_analytics/cognitive/auto_evidence_report.py`:

```python
EXECUTION_REALITY_VIRTUAL_PAPER = "virtual_paper_only"
REAL_MONEY_AT_RISK = False
EVIDENCE_ARTIFACT_SCHEMA = "auto20c_evidence_artifact_v1"
```

Nadie re-declara estos valores: el manifest, el artefacto y la nota del exportador **importan** de aquí
(regla de la casa: *un solo productor por medida*).

## 3. Dónde se declara (mapa de propagación)

| Sitio | Qué declara |
|---|---|
| Artefacto `AUTO20C_REAL_PAPER_REPORT.json` | `executionReality`, `realMoneyAtRisk: false`, `brokerVenue`, `materialOrigin` y `note` ("PAPER VIRTUAL…"). |
| Manifest (`material_manifest`) | `executionReality` y `brokerVenue` (de `get_settings()`). |
| Nota del exportador (`MATERIAL_NOTE`) | El material es PAPER **real sobre cuenta PAPER virtual** (dinero virtual, nunca XTB). |
| Guard del exportador | Si `settings.broker_venue != "paper"` ⇒ `exit 2` (BLOQUEADO) con el motivo. |
| Render `AUTO EVIDENCE REPORT` | Pie con `execution reality: virtual_paper_only`, `realMoneyAtRisk`, `venue`. |
| Tests | La procedencia virtual y el bloqueo de venue no-PAPER tienen test propio (ver §4). |

## 4. Cómo se comprueba (no es una promesa, es un gate)

- `packages/py/analytics/tests/test_auto_evidence_report.py` — el artefacto declara la realidad virtual,
  `realMoneyAtRisk is False` y la nota lo dice.
- `apps/api-python/tests/test_auto_v64_auto20c_artifact.py` — el artefacto escrito en disco declara
  `virtual_paper_only`, venue `paper` y origen `paper_real`; y el exportador **se bloquea con `2`** si la
  venue no es `paper` (sin imprimir JSON).
- Mutación **M177** borra `executionReality` del artefacto y muere; **M178** deja de volcar el artefacto y
  muere (ver `audit-pack-v2-64`).

## 5. Qué NO implica

- No certifica que el material tenga edge ni que el walk-forward real haya corrido (sigue siendo el paso
  **operativo** del propietario sobre su cuenta PAPER).
- No es un sustituto de los gates LIVE de la casa: es una **declaración** de procedencia y un **bloqueo**
  de venue aplicado a este exportador de material.
