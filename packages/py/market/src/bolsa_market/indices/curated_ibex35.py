"""IBEX 35 — constitutivos curados (espejo de packages/shared/src/constants.ts).

Fuente de verdad v1 para capa B · provider curated.
No usar «todos los BME».
"""

from __future__ import annotations

# (symbol, yahoo_symbol, name)
IBEX35_CURATED: tuple[tuple[str, str, str], ...] = (
    ("SAN", "SAN.MC", "Banco Santander"),
    ("BBVA", "BBVA.MC", "BBVA"),
    ("IBE", "IBE.MC", "Iberdrola"),
    ("ITX", "ITX.MC", "Inditex"),
    ("TEF", "TEF.MC", "Telefónica"),
    ("REP", "REP.MC", "Repsol"),
    ("FER", "FER.MC", "Ferrovial"),
    ("ACS", "ACS.MC", "ACS"),
    ("ENG", "ENG.MC", "Enagás"),
    ("GRF", "GRF.MC", "Grifols"),
    ("AENA", "AENA.MC", "Aena"),
    ("IAG", "IAG.MC", "IAG"),
    ("MAP", "MAP.MC", "Mapfre"),
    ("MEL", "MEL.MC", "Meliá Hotels"),
    ("RED", "RED.MC", "Redeia"),
    ("CLNX", "CLNX.MC", "Cellnex"),
    ("AMS", "AMS.MC", "Amadeus"),
    ("CABK", "CABK.MC", "CaixaBank"),
    ("SAB", "SAB.MC", "Banco Sabadell"),
    ("LOG", "LOG.MC", "Logista"),
    ("COL", "COL.MC", "Inmobiliaria Colonial"),
    ("NTGY", "NTGY.MC", "Naturgy"),
    ("ACX", "ACX.MC", "Acerinox"),
    ("FDR", "FDR.MC", "Fluidra"),
    ("VIS", "VIS.MC", "Viscofan"),
    ("ROVI", "ROVI.MC", "Laboratorios Rovi"),
    ("PHM", "PHM.MC", "PharmaMar"),
    ("ALM", "ALM.MC", "Almirall"),
    ("UNI", "UNI.MC", "Unicaja Banco"),
    ("BKT", "BKT.MC", "Bankinter"),
    ("SCYR", "SCYR.MC", "Sacyr"),
    ("IDR", "IDR.MC", "Indra"),
    ("CAF", "CAF.MC", "CAF"),
    ("ELE", "ELE.MC", "Endesa"),
    ("ANA", "ANA.MC", "Acciona"),
)

assert len(IBEX35_CURATED) == 35
