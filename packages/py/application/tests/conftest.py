"""Aislamiento de estado de PROCESO entre tests de aplicación.

``GLOBAL_EQUITY_MARK_BOOK`` es un libro de marcas compartido por proceso: la referencia
de drawdown de una cuenta se fija con el primer equity que ve el proceso. Desde P2
(auditoría .183) un drawdown heredado de otro test VETA aperturas legítimas con
``HardDailyDrawdown``, así que el resultado de un test pasaba a depender del orden de
ejecución.

Se limpia entre tests; dentro de un test el libro se comporta como en producción.
"""

from __future__ import annotations

import pytest

from bolsa_application.account_drawdown import GLOBAL_EQUITY_MARK_BOOK


@pytest.fixture(autouse=True)
def _reset_equity_mark_book() -> None:
    GLOBAL_EQUITY_MARK_BOOK.reset()
    yield
    GLOBAL_EQUITY_MARK_BOOK.reset()
