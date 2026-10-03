"""Guardián de trazabilidad D34-07: el ``meta.bump`` de los CLI DÍA-D == ``package.json``.

En ``v2.88.34`` el sandbox ``v2_89`` sellaba ``2.11.33-beta`` mientras el feedback ``v2_90``
sellaba ``2.11.34-beta``: artefactos históricos etiquetados con una versión anterior. Este test
exige que AMBOS coincidan con el ``version`` del monorepo para que no vuelva a divergir.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS = {
    "v2_89": _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_89_dia_d_auto_replay.py",
    "v2_90": _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_90_dia_d_feedback.py",
    "v2_91": _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_91_dia_d_longitudinal.py",
    "v2_92": _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_92_dia_d_attribution.py",
    "v2_93": _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_93_dia_d_multi.py",
    "v2_94": _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_94_dia_d_multi_band.py",
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
