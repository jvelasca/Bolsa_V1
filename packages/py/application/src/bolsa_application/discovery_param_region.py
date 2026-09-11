"""V2.38 (incremento 3) — Region de parametros del Discovery (bucket determinista).

La evidencia adaptativa de V2.36/V2.37 se agrega por **familia H0** (``preset_key``). Este
modulo introduce la primera dimension de granularidad **realmente derivable** hoy: la
**region de parametros** dentro del grid de una familia.

Por que SOLO la region de parametros (y no regimen / clase de instrumento):

* **Region de parametros** — DERIVABLE. El grid de cada familia es un producto cartesiano
  determinista (``discovery_catalog.iter_param_points``) y el punto concreto se conoce al
  emitir la candidata. Basta etiquetarlo para poder agrupar la evidencia por region.
* **Regimen** — NO DISPONIBLE. Solo existe como clasificacion en memoria en la capa
  cognitiva (``bolsa_analytics.cognitive.market_state``); jamas se persiste en
  ``research_trials``. Etiquetarlo aqui seria inventar dato.
* **Clase de instrumento** — NO DISPONIBLE. ``instruments.type`` es un enum con un unico
  valor (``stock``) y ``sector`` es texto libre sin poblar; el concepto real ("equities")
  solo vive en Trading Policy, sin join a research.

Cuando esas dos dimensiones existan como dato persistido, se anadiran como nuevos
componentes de la clave compuesta sin romper este contrato (ver ``compose_granularity_key``).

Invariantes del modulo:

* **Determinista y versionado**: misma familia + mismo punto ⇒ misma region, siempre.
  La formula lleva ``math_version`` para poder reproducir buckets historicos.
* **Fail-closed**: un punto que no pertenece al grid declarado NO recibe region (``""``);
  no se inventa una region aproximada.
* **Sin LLM, sin red, sin BD**: aritmetica pura sobre el grid.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

# Version de la matematica del bucket (separada del esquema persistido): permite auditar
# con que formula se derivo una region y reproducirla. Analoga a las de discovery_evidence.
MATH_VERSION_PARAM_REGION_V0 = "discovery_param_region_v0"

# Separador de la clave compuesta. Se elige un caracter que no aparece en nombres de
# familia (identificadores ``snake_case``) ni en las claves de region.
_GRANULARITY_SEPARATOR = "|"

# Sin region: la clave compuesta ES la familia (compatibilidad byte a byte con los
# snapshots de V2.36/V2.37, que agregaban solo por familia).
_NO_REGION = ""


def _canonical_point(point: Mapping[str, Any]) -> str:
    """Representacion canonica (ordenada) del punto de parametros, para hashear."""
    return json.dumps(
        {str(k): point[k] for k in sorted(point, key=str)},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def param_region_for_point(
    param_space: Mapping[str, Sequence[Any]],
    point: Mapping[str, Any],
    *,
    math_version: str = MATH_VERSION_PARAM_REGION_V0,
) -> str:
    """Clave determinista de la region de parametros de ``point`` dentro de ``param_space``.

    La region se identifica por dos cosas, para que sea estable ante cambios del grid y
    a la vez legible en auditoria:

    * el **ordinal** del punto en el producto cartesiano determinista del grid (posicion
      reproducible, util para lectura humana y para ordenar);
    * un **hash corto** de los valores del punto (identidad del contenido, independiente
      del ordinal).

    Fail-closed: si el punto no pertenece al grid declarado (mismas claves y mismos
    valores), devuelve ``""`` — no se inventa una region. Con un grid vacio (``{}``), el
    unico punto valido es ``{}``, que tambien devuelve ``""`` (no hay nada que
    granularizar).

    Determinista: el mismo ``(param_space, point)`` produce siempre la misma clave.
    """
    from bolsa_application.discovery_catalog import iter_param_points

    normalized = {str(k): point[k] for k in point}
    if not param_space:
        # Grid vacio = un unico punto trivial (``{}``): no hay nada que granularizar.
        return _NO_REGION
    points = iter_param_points(param_space)
    if not points:
        return _NO_REGION
    canonical = _canonical_point(normalized)
    for ordinal, candidate in enumerate(points):
        if _canonical_point(candidate) == canonical:
            digest = hashlib.sha256(canonical.encode()).hexdigest()[:12]
            return f"r{ordinal:02d}:{digest}"
    return _NO_REGION


def param_region_label(
    point: Mapping[str, Any],
) -> str:
    """Etiqueta legible del punto (``clave=valor`` ordenado), para observabilidad.

    No participa en hashes: es puramente descriptiva.
    """
    return ",".join(f"{key}={point[key]}" for key in sorted(point, key=str))


def compose_granularity_key(preset_key: str, param_region: str = "") -> str:
    """Clave compuesta canonica de granularidad: ``family`` o ``family|region``.

    Sin region (``""``) la clave es exactamente la familia, de modo que la agregacion y
    el ``snapshot_hash`` de V2.36/V2.37 se mantienen **byte a byte** cuando no hay
    region. Esto permite introducir la granularidad como ampliacion retrocompatible.
    """
    family = str(preset_key or "").strip()
    region = str(param_region or "").strip()
    if not region:
        return family
    return f"{family}{_GRANULARITY_SEPARATOR}{region}"


def split_granularity_key(key: str) -> tuple[str, str]:
    """Inversa de ``compose_granularity_key``: ``(family, region)``.

    Sin separador devuelve ``(key, "")`` (evidencia agregada solo por familia).
    """
    text = str(key or "")
    if _GRANULARITY_SEPARATOR not in text:
        return text, ""
    family, region = text.split(_GRANULARITY_SEPARATOR, 1)
    return family, region


def granularity_key_dimension(key: str) -> str:
    """Etiqueta de la dimension de la clave: ``family`` o ``family+param_region``.

    Observabilidad: permite medir cuanto de la evidencia ya viene granularizada.
    """
    _, region = split_granularity_key(key)
    return "family+param_region" if region else "family"
