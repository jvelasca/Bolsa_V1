"""Reparador determinista del espaciado alrededor de codigo en linea en Markdown.

Reglas (solo insertan UN espacio, nunca borran ni reordenan):

* espacio **antes** de un span que abre, si lo precede una letra/digito o ``,``/``;``/``:``;
* espacio **despues** de un span que cierra, si lo sigue una letra/digito.

El emparejado es por pares de backticks de izquierda a derecha, asi que las lineas con un numero
impar de backticks se **saltan** (no se puede saber que abre y que cierra) y tambien las que usan
spans de doble backtick (literales anidados). Las lineas dentro de bloques de codigo ``` se saltan.

Uso: ``python fix_md_spacing.py [--dry] [ficheros...]`` — sin ficheros recorre todo `git ls-files "*.md"`.
"""

from __future__ import annotations

import re
import subprocess
import sys

WORD = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]")
OPENERS = {",", ";", ":"}


def repair_line(line: str) -> tuple[str, int]:
    """Devuelve la linea reparada y cuantos espacios se insertaron."""
    if line.count("`") % 2 or "``" in line:
        return line, 0
    ticks = [index for index, char in enumerate(line) if char == "`"]
    if not ticks:
        return line, 0
    insert_at: set[int] = set()
    for pair in range(0, len(ticks), 2):
        opening, closing = ticks[pair], ticks[pair + 1]
        if opening and (WORD.match(line[opening - 1]) or line[opening - 1] in OPENERS):
            insert_at.add(opening)
        if closing + 1 < len(line) and WORD.match(line[closing + 1]):
            insert_at.add(closing + 1)
    if not insert_at:
        return line, 0
    pieces: list[str] = []
    for index, char in enumerate(line):
        if index in insert_at:
            pieces.append(" ")
        pieces.append(char)
    return "".join(pieces), len(insert_at)


def repair_text(text: str) -> tuple[str, int]:
    lines = text.split("\n")
    inside_fence = False
    total = 0
    out: list[str] = []
    for line in lines:
        if line.lstrip().startswith("```"):
            inside_fence = not inside_fence
            out.append(line)
            continue
        if inside_fence:
            out.append(line)
            continue
        fixed, count = repair_line(line)
        total += count
        out.append(fixed)
    return "\n".join(out), total


def main() -> int:
    args = [arg for arg in sys.argv[1:] if arg != "--dry"]
    dry = "--dry" in sys.argv[1:]
    if args:
        paths = args
    else:
        listed = subprocess.run(
            ["git", "ls-files", "*.md"], capture_output=True, text=True, check=True
        )
        paths = [line for line in listed.stdout.split("\n") if line.strip()]
    touched = 0
    total = 0
    top: list[tuple[int, str]] = []
    for path in paths:
        with open(path, encoding="utf-8", newline="") as handle:
            original = handle.read()
        fixed, count = repair_text(original)
        if count == 0 or fixed == original:
            continue
        touched += 1
        total += count
        top.append((count, path))
        if not dry:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(fixed)
    print(f"ficheros vistos: {len(paths)} | con huecos: {touched} | espacios insertados: {total}")
    for count, path in sorted(top, reverse=True)[:12]:
        print(f"  {count:5}  {path}")
    if dry:
        print("(--dry: nada escrito)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
