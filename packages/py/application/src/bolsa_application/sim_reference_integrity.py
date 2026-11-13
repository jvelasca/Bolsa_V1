"""Guardián de integridad referencial de las tablas SIM (que no tienen FK en la BD).

``sim_auto_positions`` y ``sim_fill_finance_context`` solo declaran PK: nada impide que una
fila apunte a una cuenta (``account_id``) o a un instrumento que ya no existe. Un preflight
que contó esas filas como si fueran cuentas reales publicó un diagnóstico equivocado (PR
#120); este módulo existe para que el recuento sea explícito y no pueda repetirse:

* el informe cuenta **filas** por tabla y, por separado, lista los **ids distintos** huérfanos;
* ``account_id`` y el instrumento son dos motivos independientes: una fila puede fallar por
  ambos y se cuenta en los dos recuentos (``both_orphan_rows`` declara el solapamiento, así
  que ``orphan_rows`` nunca se obtiene sumando los dos recuentos);
* un id ausente (``None``) o en blanco se considera huérfano **declarado** (nunca se asume
  que apunta a algo: la ausencia no es una cuenta ni un instrumento);
* el orden de los ids es estable (orden lexicográfico), de modo que dos auditorías del mismo
  estado producen el mismo informe.

La función es **pura**: no hace I/O, no construye SQL y no importa nada de infraestructura.
Las filas se reciben como mapeos (``dict``) para poder probarla sin base de datos.

Columnas (medidas en la auditoría del 2026-11-13):

* ``sim_auto_positions`` usa ``symbol`` como id de instrumento (NO ``instrument_id``).
* ``sim_fill_finance_context`` usa ``instrument_id``.
* La tabla de instrumentos es ``instruments`` y su columna ``id``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

__all__ = [
    "FILLS_INSTRUMENT_COLUMN",
    "POSITIONS_INSTRUMENT_COLUMN",
    "REASON_ACCOUNT_MISSING",
    "REASON_INSTRUMENT_MISSING",
    "TABLE_SIM_AUTO_POSITIONS",
    "TABLE_SIM_FILL_FINANCE_CONTEXT",
    "SimReferenceIntegrityReport",
    "TableReferenceIntegrity",
    "find_orphan_sim_rows",
]

#: Nombre real de las tablas auditadas (el informe las nombra tal cual).
TABLE_SIM_AUTO_POSITIONS = "sim_auto_positions"
TABLE_SIM_FILL_FINANCE_CONTEXT = "sim_fill_finance_context"

#: ``sim_auto_positions`` identifica el instrumento por ``symbol`` (no por ``instrument_id``).
POSITIONS_INSTRUMENT_COLUMN = "symbol"
#: ``sim_fill_finance_context`` identifica el instrumento por ``instrument_id``.
FILLS_INSTRUMENT_COLUMN = "instrument_id"

#: Motivos de orfandad, independientes y acumulables en la misma fila.
REASON_ACCOUNT_MISSING = "account_missing"
REASON_INSTRUMENT_MISSING = "instrument_missing"

#: Declaraciones que el informe publica junto a los números para que no se malinterpreten.
_DECLARATIONS: dict[str, str] = {
    "orphanRows": (
        "filas distintas con al menos una referencia rota; una fila rota por cuenta y por "
        "instrumento cuenta UNA sola vez aquí"
    ),
    "accountOrphanRows": "filas cuyo account_id no existe (incluye ids None o en blanco)",
    "instrumentOrphanRows": "filas cuyo instrumento no existe (incluye ids None o en blanco)",
    "bothOrphanRows": (
        "filas que fallan por ambos motivos; se suman en los dos recuentos anteriores "
        "(solapamiento declarado, no sumar los recuentos para obtener orphanRows)"
    ),
    "blankId": (
        "None o cadena en blanco se considera huérfano por definición y se lista como \"\""
    ),
}


def _normalize_identifier(value: object) -> str | None:
    """Normaliza un id para compararlo: ``None``/blanco ⇒ ``None``; el resto, texto sin bordes."""
    if value is None:
        return None
    text = value.strip() if isinstance(value, str) else str(value).strip()
    return text or None


def _normalize_known_ids(values: Iterable[str]) -> frozenset[str]:
    """Ids conocidos normalizados; los vacíos se descartan (no acreditan a nadie)."""
    known: set[str] = set()
    for value in values:
        normalized = _normalize_identifier(value)
        if normalized is not None:
            known.add(normalized)
    return frozenset(known)


@dataclass(frozen=True, slots=True)
class TableReferenceIntegrity:
    """Informe de UNA tabla: recuentos por fila y ids distintos huérfanos ya ordenados.

    ``orphan_rows`` cuenta filas distintas con al menos una referencia rota. Los recuentos
    ``account_orphan_rows`` e ``instrument_orphan_rows`` se solapan cuando una fila falla por
    ambos motivos (``both_orphan_rows`` lo declara); no deben sumarse entre sí.
    """

    table: str
    account_column: str
    instrument_column: str
    total_rows: int
    orphan_rows: int
    account_orphan_rows: int
    instrument_orphan_rows: int
    both_orphan_rows: int
    blank_account_rows: int
    blank_instrument_rows: int
    orphan_account_ids: tuple[str, ...]
    orphan_instrument_ids: tuple[str, ...]

    @property
    def clean(self) -> bool:
        """``True`` solo si la tabla no tiene ninguna referencia rota."""
        return self.orphan_rows == 0

    @property
    def orphan_reasons(self) -> tuple[str, ...]:
        """Motivos presentes en la tabla, en orden estable; vacío si está limpia."""
        reasons: list[str] = []
        if self.account_orphan_rows:
            reasons.append(REASON_ACCOUNT_MISSING)
        if self.instrument_orphan_rows:
            reasons.append(REASON_INSTRUMENT_MISSING)
        return tuple(reasons)

    def to_dict(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "accountColumn": self.account_column,
            "instrumentColumn": self.instrument_column,
            "totalRows": self.total_rows,
            "orphanRows": self.orphan_rows,
            "accountOrphanRows": self.account_orphan_rows,
            "instrumentOrphanRows": self.instrument_orphan_rows,
            "bothOrphanRows": self.both_orphan_rows,
            "doubleCountedRows": self.both_orphan_rows,
            "blankAccountRows": self.blank_account_rows,
            "blankInstrumentRows": self.blank_instrument_rows,
            "orphanAccountIds": list(self.orphan_account_ids),
            "orphanInstrumentIds": list(self.orphan_instrument_ids),
            "orphanReasons": list(self.orphan_reasons),
            "clean": self.clean,
        }


@dataclass(frozen=True, slots=True)
class SimReferenceIntegrityReport:
    """Informe agregado de las dos tablas SIM auditadas, con declaraciones incluidas."""

    positions: TableReferenceIntegrity
    fills: TableReferenceIntegrity
    known_account_count: int
    known_instrument_count: int

    @property
    def orphan_rows(self) -> int:
        """Filas huérfanas distintas sumando las dos tablas (sin doble recuento por motivo)."""
        return self.positions.orphan_rows + self.fills.orphan_rows

    @property
    def clean(self) -> bool:
        """``True`` solo si ninguna de las dos tablas tiene referencias rotas."""
        return self.positions.clean and self.fills.clean

    @property
    def orphan_account_ids(self) -> tuple[str, ...]:
        """Ids de cuenta distintos huérfanos en ambas tablas, ordenados."""
        return tuple(
            sorted(set(self.positions.orphan_account_ids) | set(self.fills.orphan_account_ids))
        )

    @property
    def orphan_instrument_ids(self) -> tuple[str, ...]:
        """Ids de instrumento distintos huérfanos en ambas tablas, ordenados."""
        return tuple(
            sorted(
                set(self.positions.orphan_instrument_ids)
                | set(self.fills.orphan_instrument_ids)
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "clean": self.clean,
            "orphanRowsTotal": self.orphan_rows,
            "knownAccountIds": self.known_account_count,
            "knownInstrumentIds": self.known_instrument_count,
            "orphanAccountIds": list(self.orphan_account_ids),
            "orphanInstrumentIds": list(self.orphan_instrument_ids),
            "declarations": dict(_DECLARATIONS),
            "tables": {
                self.positions.table: self.positions.to_dict(),
                self.fills.table: self.fills.to_dict(),
            },
        }


def _table_integrity(
    *,
    table: str,
    rows: Iterable[Mapping[str, object]],
    account_column: str,
    instrument_column: str,
    known_account_ids: frozenset[str],
    known_instrument_ids: frozenset[str],
) -> TableReferenceIntegrity:
    """Recorre las filas de UNA tabla y compone su informe (sin I/O ni orden implícito)."""
    total_rows = 0
    orphan_rows = 0
    account_orphan_rows = 0
    instrument_orphan_rows = 0
    both_orphan_rows = 0
    blank_account_rows = 0
    blank_instrument_rows = 0
    orphan_account_ids: set[str] = set()
    orphan_instrument_ids: set[str] = set()

    for row in rows:
        total_rows += 1
        account = _normalize_identifier(row.get(account_column))
        instrument = _normalize_identifier(row.get(instrument_column))

        if account is None:
            blank_account_rows += 1
        if instrument is None:
            blank_instrument_rows += 1

        account_missing = account is None or account not in known_account_ids
        instrument_missing = instrument is None or instrument not in known_instrument_ids

        if account_missing:
            account_orphan_rows += 1
            # Un id ausente se lista como cadena vacía: declarado, no inventado.
            orphan_account_ids.add(account or "")
        if instrument_missing:
            instrument_orphan_rows += 1
            orphan_instrument_ids.add(instrument or "")
        if account_missing and instrument_missing:
            both_orphan_rows += 1
        if account_missing or instrument_missing:
            orphan_rows += 1

    return TableReferenceIntegrity(
        table=table,
        account_column=account_column,
        instrument_column=instrument_column,
        total_rows=total_rows,
        orphan_rows=orphan_rows,
        account_orphan_rows=account_orphan_rows,
        instrument_orphan_rows=instrument_orphan_rows,
        both_orphan_rows=both_orphan_rows,
        blank_account_rows=blank_account_rows,
        blank_instrument_rows=blank_instrument_rows,
        orphan_account_ids=tuple(sorted(orphan_account_ids)),
        orphan_instrument_ids=tuple(sorted(orphan_instrument_ids)),
    )


def find_orphan_sim_rows(
    positions: Iterable[Mapping[str, object]],
    fills: Iterable[Mapping[str, object]],
    known_account_ids: Iterable[str],
    known_instrument_ids: Iterable[str],
) -> SimReferenceIntegrityReport:
    """Detecta filas de las tablas SIM cuyas referencias ya no existen.

    Args:
        positions: filas de ``sim_auto_positions``; se leen ``account_id`` y ``symbol``.
        fills: filas de ``sim_fill_finance_context``; se leen ``account_id`` e
            ``instrument_id``.
        known_account_ids: ids existentes en ``investment_accounts``.
        known_instrument_ids: ids existentes en ``instruments.id``.

    Returns:
        Informe determinista: los ids distintos se listan ordenados y una fila rota por
        cuenta y por instrumento se cuenta en ambos recuentos (el solapamiento queda
        declarado en ``both_orphan_rows``).

    Una fila sin la columna esperada también es huérfana: asumir que apunta a algo existente
    sería justo el error que este guardián evita. Los ids conocidos y los de las filas se
    comparan ya normalizados (sin espacios en los bordes).
    """
    accounts = _normalize_known_ids(known_account_ids)
    instruments = _normalize_known_ids(known_instrument_ids)

    positions_report = _table_integrity(
        table=TABLE_SIM_AUTO_POSITIONS,
        rows=positions,
        account_column="account_id",
        instrument_column=POSITIONS_INSTRUMENT_COLUMN,
        known_account_ids=accounts,
        known_instrument_ids=instruments,
    )
    fills_report = _table_integrity(
        table=TABLE_SIM_FILL_FINANCE_CONTEXT,
        rows=fills,
        account_column="account_id",
        instrument_column=FILLS_INSTRUMENT_COLUMN,
        known_account_ids=accounts,
        known_instrument_ids=instruments,
    )
    return SimReferenceIntegrityReport(
        positions=positions_report,
        fills=fills_report,
        known_account_count=len(accounts),
        known_instrument_count=len(instruments),
    )
