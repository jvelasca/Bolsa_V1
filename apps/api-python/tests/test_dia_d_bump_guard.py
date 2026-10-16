"""Guardián de trazabilidad D34-07: el ``meta.bump`` de los CLI DÍA-D == ``package.json``.

En ``v2.88.34`` el sandbox ``v2_89`` sellaba ``2.11.33-beta`` mientras el feedback ``v2_90``
sellaba ``2.11.34-beta``: artefactos históricos etiquetados con una versión anterior. Este test
exige que AMBOS coincidan con el ``version`` del monorepo para que no vuelva a divergir.

Hueco de cobertura cerrado en la auditoría del sello ``v2.88.138-beta``: el sello bumpeó **13**
scripts (``v2_87`` + los 9 CLI ``v2_89``…``v2_97`` + ``v2_98``/``v2_99``/``v2_100``), pero este
guardián sólo asertaba **12** — ``v2_87`` quedaba fuera. Se incorpora ``v2_87``, cuyo matiz de
DOS literales ``bump`` se declara y se ancla en ``test_v2_87_frozen_replay_bump_stays_pinned``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS = {
    # `v2_87` es el CLI del REPLAY OOS durable. Emite DOS artefactos con `bump` (ver el test
    # `test_v2_87_frozen_replay_bump_stays_pinned`): la banda OOS financiera —que SÍ sigue la
    # versión del monorepo— y el artefacto del replay congelado, cuyo literal está CONGELADO.
    "v2_87": _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_87_replay_oos_durable_cycle.py",
    "v2_89": _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_89_dia_d_auto_replay.py",
    "v2_90": _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_90_dia_d_feedback.py",
    "v2_91": _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_91_dia_d_longitudinal.py",
    "v2_92": _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_92_dia_d_attribution.py",
    "v2_93": _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_93_dia_d_multi.py",
    "v2_94": _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_94_dia_d_multi_band.py",
    "v2_95": _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_95_dia_d_multi_bootstrap.py",
    "v2_96": _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_96_dia_d_loss_origin.py",
    "v2_97": _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_97_dia_d_thesis_exit.py",
    "v2_98": _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_98_paper_window_certification.py",
    "v2_99": _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_99_auto_estudio_chain_evidence.py",
    "v2_100": _REPO_ROOT
    / "apps"
    / "api-python"
    / "scripts"
    / "v2_100_operational_certification_evidence.py",
}
_BUMP_RE = re.compile(r'"bump"\s*:\s*"([^"]+)"')


def _package_version() -> str:
    return json.loads((_REPO_ROOT / "package.json").read_text(encoding="utf-8"))["version"]


def test_dia_d_scripts_seal_the_package_version() -> None:
    expected = _package_version()
    for name, path in _SCRIPTS.items():
        match = _BUMP_RE.search(path.read_text(encoding="utf-8"))
        assert match is not None, f"{name}: no se encontró meta.bump"
        assert match.group(1) == expected, (
            f"{name}: meta.bump {match.group(1)} != package.json {expected}"
        )


#: `v2_87` emite DOS artefactos con `bump`. El de la banda OOS financiera (`_run_finance_band`)
#: sigue la versión del monorepo y lo cubre el guardián de arriba. El del REPLAY durable —el que
#: `replay-repro` regenera y ASSERTA byte a byte (sha256 `1E3ADAC2…`, 3 340 728 bytes)— viaja
#: CONGELADO en `2.11.0-beta` a propósito: bumpearlo cambiaría los bytes del artefacto y pondría
#: ROJO el job `replay-repro` del CI del tag. Por eso el sello `v2.88.138-beta` NO lo tocó (dejó
#: el sha idéntico al de `v2.88.136`/`v2.88.137`). Se declara aquí para que nadie lo «alinee» con
#: la versión del paquete y rompa el sello congelado.
_V2_87_FROZEN_REPLAY_BUMP = "2.11.0-beta"


def test_v2_87_frozen_replay_bump_stays_pinned() -> None:
    """`v2_87` sella la banda financiera con la versión del monorepo y CONGELA el replay.

    Falsable: si el literal del replay se «alinea» con `package.json`, el job `replay-repro`
    del CI del tag deja de reproducir el artefacto congelado. Este test es el tripwire.
    """
    expected = _package_version()
    bumps = _BUMP_RE.findall(_SCRIPTS["v2_87"].read_text(encoding="utf-8"))
    assert bumps.count(expected) >= 1, (
        f"v2_87: la banda financiera debe sellar la versión del monorepo {expected}; hallado {bumps}"
    )
    assert bumps.count(_V2_87_FROZEN_REPLAY_BUMP) == 1, (
        f"v2_87: el bump del replay CONGELADO debe seguir en {_V2_87_FROZEN_REPLAY_BUMP} "
        f"(bumpearlo rompería el sha256 del job replay-repro); hallado {bumps}"
    )
