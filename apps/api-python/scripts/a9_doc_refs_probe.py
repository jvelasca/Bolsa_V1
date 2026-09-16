"""Auditoria INTERNA de las referencias del arranque/pack v2.40.3 (soporte de la fase).

Extrae de los dos documentos del hotfix los tokens con pinta de fichero (``*.py``, ``*.yml``,
``*.ini``, ``*.md``) y comprueba que existen: una referencia muerta en un documento de arranque es lo
primero que cobra un auditor externo (o el documento miente o el codigo se movio sin actualizarlo).

Resolucion por tres vias, en este orden:

1. relativa a la raiz del repo;
2. relativa a las raices del monorepo (``packages/py``, ``apps/api-python``);
3. relativa al directorio del propio documento (enlaces markdown ``./x.md``);
4. por **nombre** en todo el arbol (las citas del tipo ``execution_event.py`` sin ruta).

Trampa que costo una pasada de este mismo script: la primera version excluia en el lookbehind el
backtick, de modo que **no** miraba las rutas completas citadas entre backticks (las mas importantes)
y aun asi imprimia "TODAS existen". Si este script dice que todo esta bien, que sea habiendo mirado.

Uso: uv run --no-sync python apps/api-python/scripts/a9_doc_refs_probe.py
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[3]
DOCS = (
    "docs/engineering/arranque-auditor-v2-40-3-hotfix-idempotencia-2026-09-16.md",
    "docs/engineering/audit-pack-v2.40.3-idempotency-key-collision-2026-09-16.md",
)
_BASES = ("", "packages/py", "apps/api-python")
_EXT = r"(?:py|yml|yaml|ini|md|json)"
_RELPATH = re.compile(rf"(?<![\w/.-])((?:[\w.-]+/)+[\w.-]+\.{_EXT})")
_BARE = re.compile(rf"`([\w.-]+\.{_EXT})`")
# Referencias historicas (existen en el commit base, no en el arbol actual): se declaran, no se tapan.
_ALLOW_MISSING = {
    "versions/028_sim_finance_position_durable.py": "historica (commit base 11e2cb83)",
}


def _index_by_name() -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".git", "node_modules", ".venv", "dist", "build"} for part in path.parts):
            continue
        counts[path.name] = counts.get(path.name, 0) + 1
    return counts


def main() -> None:
    names = _index_by_name()
    missing: list[tuple[str, str]] = []
    checked = 0
    for doc in DOCS:
        doc_dir = (ROOT / doc).parent
        text = (ROOT / doc).read_text(encoding="utf-8")
        tokens = {t.strip("`.,;:()") for t in _RELPATH.findall(text)}
        tokens |= {t.strip("`.,;:()") for t in _BARE.findall(text)}
        for token in sorted(tokens):
            if any(ch in token for ch in "*<>"):
                continue
            candidate = token.lstrip("./")
            checked += 1
            if (ROOT / candidate).exists() or (doc_dir / candidate).exists():
                continue
            if any((ROOT / base / candidate).exists() for base in _BASES if base):
                continue
            if names.get(pathlib.Path(candidate).name):
                continue
            if pathlib.Path(token).name in _ALLOW_MISSING:
                continue
            missing.append((doc, token))

    print(f"referencias comprobadas: {checked}")
    print(f"referencias historicas declaradas: {sorted(_ALLOW_MISSING)}")
    if not missing:
        print("TODAS existen en el arbol actual")
        return
    for doc, token in missing:
        print(f"  REFERENCIA MUERTA en {doc}: {token}")


if __name__ == "__main__":
    main()
