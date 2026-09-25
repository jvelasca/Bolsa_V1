"""AUTO-20C — AUTO EVIDENCE REPORT y artefacto reproducible de una calibración PAPER (PURA).

Qué resuelve: la calibración de ``AUTO-19B`` produce un informe honesto (seis preguntas con su
veredicto y su muestra) pero **frío de leer** y **sin sello de procedencia**. Esta pieza añade dos
cosas que no miden nada nuevo —solo declaran lo ya medido—:

* El **artefacto reproducible** (``auto20c_evidence_artifact_v1``): un envoltorio determinista que
  pega, sin reinterpretar, el informe completo (``report``) con el manifest del material que se
  midió (``material``). Guardarlo permite reproducir el veredicto sin dudar del universo.
* El **render legible** (``AUTO EVIDENCE REPORT``): la tabla que un humano lee de un vistazo
  (Material / Shrinkage / Effective-N / Interval coverage / Edge sign / Confidence / Walk-forward
  efficiency), siempre con el mismo criterio: **lo que no se midió se imprime INCONCLUSIVE**, nunca
  un veredicto inventado.

Regla de ejecución (declarada, no asumida): el material PAPER de este pipeline es **VIRTUAL**. Las
operaciones se simulan con **dinero virtual** y **NUNCA** se ejecutan sobre XTB ni ninguna
plataforma real. ``EXECUTION_REALITY_VIRTUAL_PAPER`` y ``REAL_MONEY_AT_RISK = False`` son la ÚNICA
fuente de ese hecho: quien lo publique lo importa de aquí, no lo re-declara.

Regla de oro (viaja en el render): un resultado ``INCONCLUSIVE`` por **muestra insuficiente** no es
un error del software ni algo que se arregle bajando ``min_is``/``min_oos``/``folds``; es el
resultado honesto y se conserva.

Read-only y determinista: sin reloj, sin I/O, sin estado.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

__all__ = [
    "ALLOCATION_CHANGE_NONE",
    "EVIDENCE_ARTIFACT_SCHEMA",
    "EXECUTION_REALITY_NOTE",
    "EXECUTION_REALITY_VIRTUAL_PAPER",
    "GOLDEN_RULE_INSUFFICIENT_EVIDENCE",
    "MATERIAL_ORIGIN_PAPER_REAL",
    "MATERIAL_ORIGIN_SYNTHETIC_FIXTURE",
    "OUT_OF_SCOPE_AUTO21",
    "REAL_MONEY_AT_RISK",
    "build_evidence_artifact",
    "render_evidence_report",
]

#: Realidad de ejecución del pipeline PAPER de AUTO: **dinero VIRTUAL**, jamás una plataforma real.
#: Es la fuente única del invariante; el manifest, el artefacto y la nota del exportador lo importan.
EXECUTION_REALITY_VIRTUAL_PAPER = "virtual_paper_only"

#: ¿Hay dinero real en riesgo? Nunca en este pipeline: PAPER es virtual por diseño.
REAL_MONEY_AT_RISK = False

#: Sello del envoltorio del artefacto. Cambiar su forma obliga a subir este sello.
EVIDENCE_ARTIFACT_SCHEMA = "auto20c_evidence_artifact_v1"

#: Origen del material: la exportación real de PostgreSQL PAPER o el fixture sintético de tests.
MATERIAL_ORIGIN_PAPER_REAL = "paper_real"
MATERIAL_ORIGIN_SYNTHETIC_FIXTURE = "synthetic_fixture"

#: El reparto NO cambia por evidencia (``auto18-v1`` congelado): es un hecho declarado, no medido.
ALLOCATION_CHANGE_NONE = "none"

#: Huecos que este instrumento NO cubre todavía (``AUTO-21``): se declaran, no se inventan.
OUT_OF_SCOPE_AUTO21 = "AUTO-21 (fuera de alcance)"

#: La regla de oro de la fase, impresa en cada render para que nadie la olvide.
GOLDEN_RULE_INSUFFICIENT_EVIDENCE = (
    "INCONCLUSIVE por muestra insuficiente NO se arregla bajando min_is/min_oos/folds: "
    "se declara y se conserva como resultado."
)

#: Nota de procedencia que viaja en el artefacto (mismo texto que publica el exportador).
EXECUTION_REALITY_NOTE = (
    "PAPER VIRTUAL: este material y sus veredictos proceden de una cuenta PAPER con DINERO "
    "VIRTUAL; ninguna operación se ejecuta sobre XTB ni ninguna plataforma real."
)

#: Veredictos internos del instrumento → etiqueta que imprime el render.
_VERDICT_LABELS: dict[str, str] = {
    "supported": "SUPPORTED",
    "not_supported": "NOT_SUPPORTED",
    "inconclusive": "INCONCLUSIVE",
}

#: (clave de pregunta del informe, etiqueta del render) en el orden de la tabla del punto 30.
#: Las claves son las MISMAS que emite ``auto_adaptive_calibration`` (un solo productor).
_CALIBRATION_ROWS: tuple[tuple[str, str], ...] = (
    ("shrinkage_calibration", "Shrinkage"),
    ("effective_n_calibration", "Effective-N"),
    ("interval_coverage", "Interval coverage"),
    ("edge_sign_calibration", "Edge sign"),
    ("confidence_calibration", "Confidence calibration"),
    ("coverage_calibration", "Coverage (regime)"),
)

_INCONCLUSIVE_LABEL = "INCONCLUSIVE"


def _verdict_label(verdict: Any) -> str:
    """Veredicto interno → etiqueta del render; lo desconocido o ausente es ``INCONCLUSIVE``."""
    return _VERDICT_LABELS.get(str(verdict), _INCONCLUSIVE_LABEL)


def _question_verdict(report: Mapping[str, Any], key: str) -> str:
    """Veredicto de una pregunta del informe; sin pregunta ⇒ ``INCONCLUSIVE`` (nunca se inventa)."""
    for row in report.get("questions") or ():
        if isinstance(row, Mapping) and row.get("question") == key:
            return _verdict_label(row.get("verdict"))
    return _INCONCLUSIVE_LABEL


def _number_label(value: Any) -> str:
    """Número del agregado → texto; ``None`` ⇒ ``INCONCLUSIVE`` (sin cociente honesto)."""
    if value is None or isinstance(value, bool):
        return _INCONCLUSIVE_LABEL
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return _INCONCLUSIVE_LABEL


def _material_lines(material: Mapping[str, Any] | None) -> list[str]:
    """Bloque ``Material`` del render: conteos y huella del universo, o su ausencia declarada."""
    if material is None:
        return ["  (sin material declarado: corrida sin exportación PAPER)"]
    regimes = [str(item) for item in (material.get("regimesPresent") or ())]
    regime_text = ", ".join(regimes) if regimes else "(sin régimen declarado)"
    lines = [
        f"  origin:               {material.get('materialOrigin')}",
        f"  cycles:               {material.get('closedCycles')}",
        f"  measured (with R):    {material.get('cyclesWithRisk')}",
        f"  without R:            {material.get('cyclesWithoutRisk')}",
        f"  regimes:              {regime_text} ({len(regimes)})",
        f"  fingerprint:          {material.get('fingerprint')}",
    ]
    return lines


def _perimeter_lines(material: Mapping[str, Any] | None) -> list[str]:
    """Bloque ``perimeter``: el contorno del volcado, separado del universo realmente medido."""
    if material is None:
        return []
    requested = ", ".join(str(item) for item in (material.get("requestedStrategyVersions") or ()))
    observed = ", ".join(str(item) for item in (material.get("observedStrategyVersions") or ()))
    lines = [
        "perimeter",
        f"  requested versions:   {requested or '(ninguna)'}",
        f"  observed versions:    {observed or '(ninguna)'}",
        f"  fills total:          {material.get('fillsTotalForAccount')}",
        f"  fills selected:       {material.get('fillsSelected')}",
        f"  excluded (no version):{material.get('fillsExcludedNoVersion')}",
        f"  excluded (other):     {material.get('fillsExcludedOtherVersion')}",
        f"  reservations read:    {material.get('reservationsRead')}",
        "  risk read saturated:  "
        f"{material.get('riskReadSaturated')} "
        "(false = la lectura terminó; NO = 'todas las reservas existen')",
    ]
    versions_missing = ", ".join(
        str(item) for item in (material.get("versionsRequestedWithoutMaterial") or ())
    )
    versions_extra = ", ".join(
        str(item) for item in (material.get("versionsObservedNotRequested") or ())
    )
    if versions_missing:
        lines.append(f"  requested without material: {versions_missing}")
    if versions_extra:
        lines.append(f"  observed not requested:     {versions_extra}")
    return lines


def build_evidence_artifact(
    report: Any,
    *,
    material: Mapping[str, Any] | None = None,
    execution_reality: str = EXECUTION_REALITY_VIRTUAL_PAPER,
    broker_venue: str | None = None,
    material_origin: str = MATERIAL_ORIGIN_PAPER_REAL,
) -> dict[str, Any]:
    """(PURA) envuelve un informe de calibración en el artefacto reproducible ``AUTO-20C``.

    ``report`` es un ``CalibrationReport`` (o su ``as_dict``) y viaja **verbatim** bajo la clave
    ``report``: el artefacto no reinterpreta ninguna medición. El envoltorio añade el sello de
    esquema, la realidad de ejecución (PAPER **virtual**), la venue y el origen del material.
    """
    report_payload = report.as_dict() if hasattr(report, "as_dict") else dict(report)
    return {
        "schema": EVIDENCE_ARTIFACT_SCHEMA,
        "executionReality": execution_reality,
        "realMoneyAtRisk": REAL_MONEY_AT_RISK,
        "brokerVenue": broker_venue,
        "materialOrigin": material_origin,
        "note": EXECUTION_REALITY_NOTE,
        "material": dict(material) if material is not None else None,
        "report": report_payload,
    }


def render_evidence_report(artifact: Mapping[str, Any]) -> str:
    """(PURA) render legible del artefacto, en texto plano determinista.

    Imprime el bloque de Material, la tabla de calibración (un veredicto por pregunta, más el WFE),
    los huecos declarados fuera de alcance y la procedencia virtual. Un veredicto ausente se imprime
    ``INCONCLUSIVE``: el render no fabrica lo que el informe no midió.
    """
    report = artifact.get("report") or {}
    material = artifact.get("material")
    material = material if isinstance(material, Mapping) else None
    aggregate = report.get("aggregate") or {}
    aggregate = aggregate if isinstance(aggregate, Mapping) else {}

    rows: list[tuple[str, str]] = [
        (label, _question_verdict(report, key)) for key, label in _CALIBRATION_ROWS
    ]
    rows.append(
        ("Walk-forward efficiency", _number_label(aggregate.get("walkForwardEfficiency")))
    )

    width = max(len(label) for label, _ in rows) + 2
    lines: list[str] = [
        "AUTO EVIDENCE REPORT",
        "====================",
        "Material",
        *_material_lines(material),
        "",
        "Calibration",
    ]
    lines.extend(f"  {label.ljust(width)}{verdict}" for label, verdict in rows)
    lines.extend(
        [
            "",
            "Declared",
            f"  {'Current regime'.ljust(width)}{OUT_OF_SCOPE_AUTO21}",
            f"  {'Current evidence'.ljust(width)}{OUT_OF_SCOPE_AUTO21}",
            (
                f"  {'Allocation change'.ljust(width)}"
                f"{ALLOCATION_CHANGE_NONE} (auto18-v1 congelado: la evidencia no mueve el reparto)"
            ),
        ]
    )
    perimeter = _perimeter_lines(material)
    if perimeter:
        lines.append("")
        lines.extend(perimeter)
    lines.extend(
        [
            "",
            (
                "execution reality:    "
                f"{artifact.get('executionReality')} "
                f"(realMoneyAtRisk={artifact.get('realMoneyAtRisk')}, venue={artifact.get('brokerVenue')})"
            ),
            f"golden rule:          {GOLDEN_RULE_INSUFFICIENT_EVIDENCE}",
        ]
    )
    return "\n".join(lines) + "\n"
