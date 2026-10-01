"""V2.88.7 / AUTO-MATERIAL-20 — CONGELAR y SEMBRAR la ENTRADA del replay OOS durable.

Por qué existe este script
--------------------------
El sello ``v2.88.7-beta`` publicó un artefacto de replay (3 393 187 B, SHA-256
``7D998E4D…C804A0461``) que **no era auditable desde GitHub**: el fichero vive fuera del
repo (``operability_runs/`` está en ``.gitignore``) y el CI **no podía regenerarlo**, porque
``v2_87_replay_oos_durable_cycle.py`` NO es hermético: hace ``ensure_migrated``, lee las
barras D1 reales (``SqlAlchemyOhlcvRepository``) y los sectores del catálogo. El
``db:seed`` del repo solo siembra INSTRUMENTOS, nunca OHLCV — esas barras vienen de un
   10|sync externo al proveedor—, así que un runner arrancaba con la tabla vacía y el censo
encontraba **0 días operables**: el replay no llegaba a producir artefacto alguno.

Este script cierra ese hueco congelando la ENTRADA exacta de la corrida sellada y
sembrándola en cualquier PostgreSQL (el del job del tag), de modo que el CI pueda
**regenerar** el artefacto y contrastar su SHA-256. La auditoría deja de depender de que el
lector confíe en un hash declarado: se vuelve reproducible.

Qué congela y qué NO (se declara, no se disfraza)
   20|-------------------------------------------------
* Se congelan los **20 instrumentos** del watch de la corrida sellada (fila COMPLETA del
  catálogo, JSONB incluido) y sus **25 700 barras D1** (1 285 por símbolo).
* Los valores numéricos viajan como el **TEXTO CANÓNICO de PostgreSQL** (``open::text``,
  ``numeric(18,6)``) y se re-insertan con ``CAST(… AS numeric)``: un ``float`` intermedio
  podría redondear y cambiar el artefacto. Lo mismo con ``timestamptz`` (ISO-8601 en UTC)
  y con los enums (``"Timeframe"``, ``"DataProvider"``, ``"InstrumentType"``).
* Se OMITEN solo las columnas que el replay **no lee nunca** y que son irrelevantes para
  él: ``ohlcv_bars.id`` y ``ohlcv_bars.created_at`` (se regeneran al sembrar). Queda
  declarado en el manifiesto del fixture.
* El **watch se pasa EXPLÍCITO** (la lista sellada, en el mismo orden) en vez de dejar que
  se derive del catálogo. Congelar la derivación exigiría versionar el catálogo entero
  (76 instrumentos / 96 020 barras ≈ 4× más datos) para que la selección volviese a dar la
  misma lista. La equivalencia NO se pide por fe: la certifica la igualdad del SHA-256 del
  artefacto regenerado.

Uso::

    # 1) Congelar la entrada desde una PostgreSQL con las barras reales (READ-ONLY)
    uv run --no-sync python apps/api-python/scripts/replay_oos_input_fixture.py export \
        --out docs/engineering/evidence/v2.88.7/replay-input-fixture.ndjson

    # 2) Sembrar la entrada en la BD destino (la del job del tag; idempotente)
    uv run --no-sync python apps/api-python/scripts/replay_oos_input_fixture.py seed \
        --fixture docs/engineering/evidence/v2.88.7/replay-input-fixture.ndjson

    # 3) Comprobar el fixture sin BD (recuentos + huella)
    uv run --no-sync python apps/api-python/scripts/replay_oos_input_fixture.py verify \
        --fixture docs/engineering/evidence/v2.88.7/replay-input-fixture.ndjson

    # 3b) Imprimir el watch congelado (CSV) para pasárselo al replay
    uv run --no-sync python apps/api-python/scripts/replay_oos_input_fixture.py watch \
        --fixture docs/engineering/evidence/v2.88.7/replay-input-fixture.ndjson

    # 4) Contraste del artefacto regenerado contra el sello (lo que hace el CI)
    uv run --no-sync python apps/api-python/scripts/replay_oos_input_fixture.py assert-artifact \
        --file operability_runs/replay.json
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import pathlib
import sys
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_DOTENV = _REPO_ROOT / ".env"

#: Formato del fixture. Subir la versión si cambia el contrato de las líneas.
_FORMAT = "replay-oos-input-fixture/1"

#: Watch de la corrida sellada ``v2.88.7-beta`` (MISMO orden que el artefacto publica).
#: El orden IMPORTA: ``split_watch`` reparte A/B por posición.
_SEALED_WATCH = (
    "0a5dc12fd5a24f0a89a91d36a",
    "0cf0907837fc422db221b0149",
    "240a4ae01a944d3bba1cf1b24",
    "31f9a597d03249319ea0c9345",
    "381dd3b0699a44e8b9d13ac13",
    "49596ff25acb4294b265f321b",
    "4d24ea029283461cb9304421a",
    "54283bcb54674ec1b70b4db72",
    "5a130eea1ad54dcaaa50b67b9",
    "5c34aaec1448406ebec94b20f",
    "615d243eb830473ab009c8997",
    "6655c5faff8a458186dcd8adc",
    "67c117a7d88f4c75a7174e998",
    "6db46176cc2d4845845b6ee6e",
    "6f6215d935c04e0f9ac7bfef7",
    "74c66a856dde4cbaad4888908",
    "7721cde9af0c49d29576786d5",
    "840a307d2b074e2db4dfc3373",
    "856510e40dda4c758f4d4df89",
    "8601a0c3f8d248b0b8052b963",
)

#: Artefacto de REFERENCIA del replay OOS: el que el job `replay-repro` regenera desde la entrada
#: congelada y **asserta**. Va en DOS renders porque el sello original se escribió en Windows en
#: modo texto y el runner escribe LF (medido en su día: 103 125 B = 1 `\r` por línea, secciones
#: idénticas byte a byte). Se declaran los dos y se asserta el CONTENIDO (`_assert_artifact`).
#:
#: HISTORIA del par (declarada, no borrada):
#:   * `v2.88.7-beta` selló `7D998E4D…C804A0461` / 3 393 187 B (CRLF) y `A4DA036C…13CB` /
#:     3 290 062 B (LF).
#:   * `W3` (v2.88.16) movió el ancla temporal del fill (`fill_seed(bar_tick, símbolo)` en vez
#:     del contador privado `_minute`) y el replay **conduce el motor real** ⇒ el artefacto
#:     cambió. El `replay-repro` del tag `v2.88.16.1-beta` salió **rojo** por eso.
#:   * `W3.2` (v2.88.16.2) lo **re-sella** con el delta **medido y aislado**: revertir SOLO el
#:     seed al minuto reproduce `A4DA036C…13CB` **byte a byte**, y la frontera de barras cerradas
#:     es **inerte** en el replay (control a `2099` ⇒ artefacto idéntico). La atribución completa,
#:     con la banda de sensibilidad de la muestra, vive en
#:     `docs/engineering/evidence/v2.88.16.2/README.md` y se re-verifica con
#:     `apps/api-python/scripts/v2_88_16_2_oos_anchor_ablation.py`.
_SEALED_ARTIFACT_SHA256 = "240662250347A2AAD0F8E9F0101185D8ACC80C1D4BD1B4BBFF02D4766D9F54F0"
_SEALED_ARTIFACT_BYTES = 3_445_622

#: EL MISMO CONTENIDO con separador LF: lo que escribe cualquier SO que no traduzca `\n` (el
#: runner de GitHub, sin ir más lejos). Es el par que el job `replay-repro` ve en Linux.
_SEALED_ARTIFACT_SHA256_LF = "1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7"
_SEALED_ARTIFACT_BYTES_LF = 3_340_728

#: ``to_char`` de un ``timestamptz`` a ISO-8601 UTC con microsegundos y offset explícito.
#: Se fija ``+00:00`` literal (``AT TIME ZONE 'UTC'`` ya normaliza) para no depender del
#: ``TimeZone`` del servidor ni del formato corto ``+00`` que emite ``OF``.
_ISO = "to_char({col} AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.US\"+00:00\"')"


def _sha256_file(path: pathlib.Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest().upper(), size


def _canonical_lf(raw: bytes) -> bytes:
    """Contenido con salto de línea LF (quita la traducción del modo texto de Windows).

    El artefacto se escribe con ``json.dumps(..., indent=2)``, así que sus únicos bytes
    ``\\r`` son los que el SO intercala delante de cada ``\\n`` al abrir el fichero en modo
    texto: dentro de las cadenas JSON un salto va escapado (``\\n``), nunca en crudo. Por eso
    normalizar ``\\r\\n`` → ``\\n`` no puede alterar la evidencia, solo el render.
    """
    return raw.replace(b"\r\n", b"\n")


def _render_of(raw: bytes) -> str:
    """Etiqueta el render del fichero: ``CRLF`` (Windows) o ``LF`` (todo lo demás)."""
    if raw.count(b"\r\n"):
        return "CRLF (modo texto de Windows)"
    return "LF"


def _write_line(handle: Any, row: dict[str, Any]) -> None:
    handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


# ── 1 · EXPORT (READ-ONLY) ───────────────────────────────────────────────────────


async def _export(args: argparse.Namespace) -> int:
    from dotenv import load_dotenv
    from sqlalchemy import bindparam, text

    load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    watch = list(args.watch.split(",")) if args.watch else list(_SEALED_WATCH)
    watch = [w.strip() for w in watch if w.strip()]
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    instrument_sql = text(
        f"""
        SELECT id, symbol, yahoo_symbol, isin, name, exchange, country, currency, sector,
               "type"::text AS type, is_active::text AS is_active,
               profile_snapshot::text AS profile_snapshot,
               last_xtb_validation::text AS last_xtb_validation,
               {_ISO.format(col='created_at')} AS created_at,
               {_ISO.format(col='updated_at')} AS updated_at
        FROM instruments
        WHERE id IN :ids
        ORDER BY id
        """
    ).bindparams(bindparam("ids", expanding=True))
    bars_sql = text(
        f"""
        SELECT instrument_id, timeframe::text AS timeframe,
               {_ISO.format(col='timestamp')} AS timestamp,
               open::text AS open, high::text AS high, low::text AS low,
               close::text AS close, volume AS volume,
               adj_close::text AS adj_close, source::text AS source
        FROM ohlcv_bars
        WHERE instrument_id IN :ids AND timeframe = '1d'
        ORDER BY instrument_id, timestamp
        """
    ).bindparams(bindparam("ids", expanding=True))

    try:
        async with factory() as session:
            instruments = [dict(row) for row in (await session.execute(instrument_sql, {"ids": watch})).mappings()]
            bars = [dict(row) for row in (await session.execute(bars_sql, {"ids": watch})).mappings()]
    finally:
        await engine.dispose()

    missing = [w for w in watch if w not in {row["id"] for row in instruments}]
    if missing:
        print(f"# ABORTO: el catálogo no tiene los instrumentos {missing}", file=sys.stderr)
        return 2
    bars_by_symbol: dict[str, int] = {}
    for row in bars:
        symbol = str(row["instrument_id"])
        bars_by_symbol[symbol] = bars_by_symbol.get(symbol, 0) + 1
    empty = [w for w in watch if bars_by_symbol.get(w, 0) == 0]
    if empty:
        print(f"# ABORTO: sin barras D1 para {empty}", file=sys.stderr)
        return 2

    with out.open("w", encoding="utf-8", newline="\n") as handle:
        _write_line(
            handle,
            {
                "kind": "manifest",
                "format": _FORMAT,
                "seal": "v2.88.7-beta",
                "phase": "AUTO-MATERIAL-20",
                "replayScript": "apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py",
                "watch": watch,
                "watchSize": len(watch),
                "timeframe": "1d",
                "instruments": len(instruments),
                "bars": len(bars),
                "barsPerSymbol": bars_by_symbol,
                "firstBar": min((row["timestamp"] for row in bars), default=None),
                "lastBar": max((row["timestamp"] for row in bars), default=None),
                "expectedArtifactSha256": _SEALED_ARTIFACT_SHA256,
                "expectedArtifactBytes": _SEALED_ARTIFACT_BYTES,
                "expectedArtifactSha256Lf": _SEALED_ARTIFACT_SHA256_LF,
                "expectedArtifactBytesLf": _SEALED_ARTIFACT_BYTES_LF,
                "expectedArtifactRenderNote": (
                    "El sello original se escribio en Windows en modo texto: su LF va como CRLF. "
                    "El MISMO contenido en LF es expectedArtifactSha256Lf/BytesLf. Los dos "
                    "renders son validos y las secciones son identicas byte a byte. La referencia "
                    "vigente desde W3.2 (v2.88.16.2) esta anclada a la BARRA: el delta y su "
                    "atribucion medida viven en docs/engineering/evidence/v2.88.16.2/."
                ),
                "omittedColumns": [
                    "ohlcv_bars.id",
                    "ohlcv_bars.created_at",
                ],
                "omittedBecause": (
                    "El replay no lee ninguna de las dos: `id` no se selecciona en "
                    "`SqlAlchemyOhlcvRepository.get_bars` y `created_at` tampoco. Se "
                    "regeneran al sembrar (id nuevo + now()), de modo que no pueden "
                    "afectar al artefacto."
                ),
                "watchFrozen": (
                    "El watch va EXPLICITO (lista sellada, mismo orden) en vez de derivarse "
                    "del catalogo: congelar la derivacion exigiria versionar los 76 "
                    "instrumentos y las 96 020 barras del catalogo. La equivalencia la "
                    "certifica la igualdad del SHA-256 del artefacto regenerado."
                ),
                "numericFidelity": (
                    "Los numeros viajan como TEXTO CANONICO de PostgreSQL (numeric(18,6)) y "
                    "se re-insertan con CAST(… AS numeric): sin float intermedio, sin redondeo."
                ),
            },
        )
        for row in instruments:
            _write_line(
                handle,
                {
                    "kind": "instrument",
                    "id": str(row["id"]),
                    "symbol": row["symbol"],
                    "yahooSymbol": row["yahoo_symbol"],
                    "isin": row["isin"],
                    "name": row["name"],
                    "exchange": row["exchange"],
                    "country": row["country"],
                    "currency": row["currency"],
                    "sector": row["sector"],
                    "type": row["type"],
                    "isActive": row["is_active"] == "true",
                    "profileSnapshot": row["profile_snapshot"],
                    "lastXtbValidation": row["last_xtb_validation"],
                    "createdAt": row["created_at"],
                    "updatedAt": row["updated_at"],
                },
            )
        for row in bars:
            _write_line(
                handle,
                {
                    "kind": "bar",
                    "instrumentId": str(row["instrument_id"]),
                    "timeframe": row["timeframe"],
                    "timestamp": row["timestamp"],
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": int(row["volume"]),
                    "adjClose": row["adj_close"],
                    "source": row["source"],
                },
            )

    digest, size = _sha256_file(out)
    print(f"# fixture  {out}")
    print(f"# lineas   {1 + len(instruments) + len(bars)} (1 manifiesto + {len(instruments)} instrumentos + {len(bars)} barras)")
    print(f"# bytes    {size}")
    print(f"# sha256   {digest}")
    print(f"# esperado {_SEALED_ARTIFACT_SHA256} ({_SEALED_ARTIFACT_BYTES} B) del artefacto regenerado")
    return 0


# ── 2 · SEED ─────────────────────────────────────────────────────────────────────


async def _seed(args: argparse.Namespace) -> int:
    from dotenv import load_dotenv
    from sqlalchemy import text

    load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory
    from bolsa_infrastructure.ids import new_id

    fixture = pathlib.Path(args.fixture)
    instruments, bars = _read_fixture(fixture)

    get_settings.cache_clear()
    settings = get_settings()
    await asyncio.to_thread(ensure_migrated)
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    instrument_sql = text(
        """
        INSERT INTO instruments (
            id, symbol, yahoo_symbol, isin, name, exchange, country, currency, sector,
            "type", is_active, profile_snapshot, last_xtb_validation, created_at, updated_at
        ) VALUES (
            :id, :symbol, :yahoo_symbol, :isin, :name, :exchange, :country, :currency, :sector,
            CAST(:type AS "InstrumentType"), CAST(:is_active AS boolean),
            CAST(:profile_snapshot AS jsonb), CAST(:last_xtb_validation AS jsonb),
            CAST(:created_at AS timestamptz), CAST(:updated_at AS timestamptz)
        )
        ON CONFLICT (id) DO UPDATE SET
            symbol = EXCLUDED.symbol, yahoo_symbol = EXCLUDED.yahoo_symbol,
            isin = EXCLUDED.isin, name = EXCLUDED.name, exchange = EXCLUDED.exchange,
            country = EXCLUDED.country, currency = EXCLUDED.currency,
            sector = EXCLUDED.sector, "type" = EXCLUDED."type", is_active = EXCLUDED.is_active,
            profile_snapshot = EXCLUDED.profile_snapshot,
            last_xtb_validation = EXCLUDED.last_xtb_validation,
            created_at = EXCLUDED.created_at, updated_at = EXCLUDED.updated_at
        """
    )
    bar_sql = text(
        """
        INSERT INTO ohlcv_bars (
            id, instrument_id, timeframe, "timestamp", open, high, low, close, volume,
            adj_close, source, created_at
        ) VALUES (
            :id, :instrument_id, CAST(:timeframe AS "Timeframe"),
            CAST(:timestamp AS timestamptz), CAST(:open AS numeric), CAST(:high AS numeric),
            CAST(:low AS numeric), CAST(:close AS numeric), CAST(:volume AS bigint),
            CAST(:adj_close AS numeric), CAST(:source AS "DataProvider"), now()
        )
        ON CONFLICT (instrument_id, timeframe, "timestamp") DO UPDATE SET
            open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
            close = EXCLUDED.close, volume = EXCLUDED.volume,
            adj_close = EXCLUDED.adj_close, source = EXCLUDED.source
        """
    )

    seeded_instruments = 0
    seeded_bars = 0
    try:
        async with factory() as session:
            for instrument in instruments:
                await session.execute(instrument_sql, instrument)
                seeded_instruments += 1
            for _symbol, rows in _group(bars).items():
                payload = [{**row, "id": new_id()} for row in rows]
                await session.execute(bar_sql, payload)
                seeded_bars += len(payload)
            await session.commit()
    finally:
        await engine.dispose()

    print(f"# sembrado  {seeded_instruments} instrumentos, {seeded_bars} barras D1")
    return 0


def _group(bars: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Agrupa por símbolo. Opera sobre la forma INTERNA (``instrument_id``), la que usan
    tanto el sembrado como la verificación tras ``_read_fixture``."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in bars:
        grouped.setdefault(str(row["instrument_id"]), []).append(row)
    return grouped


# ── LECTURA / VERIFICACIÓN DEL FIXTURE (sin BD) ───────────────────────────────────


def _read_manifest(path: pathlib.Path) -> dict[str, Any]:
    """Lee SOLO la línea de manifiesto (evita parsear los 7,5 MB de barras)."""
    with path.open("r", encoding="utf-8") as handle:
        first = handle.readline().strip()
    if not first:
        raise ValueError(f"{path}: fichero vacío")
    manifest = json.loads(first)
    if manifest.get("kind") != "manifest":
        raise ValueError(f"{path}: la primera línea no es el manifiesto")
    if manifest.get("format") != _FORMAT:
        raise ValueError(f"{path}: formato {manifest.get('format')!r} != {_FORMAT!r}")
    return manifest


def _read_fixture(path: pathlib.Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Lee el NDJSON y devuelve ``(instruments, bars)`` listos para el INSERT (snake_case)."""
    manifest = _read_manifest(path)
    instruments: list[dict[str, Any]] = []
    bars: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            kind = row.get("kind")
            if kind == "manifest":
                manifest = row
            elif kind == "instrument":
                instruments.append(
                    {
                        "id": row["id"], "symbol": row["symbol"],
                        "yahoo_symbol": row["yahooSymbol"], "isin": row["isin"],
                        "name": row["name"], "exchange": row["exchange"],
                        "country": row["country"], "currency": row["currency"],
                        "sector": row["sector"], "type": row["type"],
                        "is_active": "true" if row["isActive"] else "false",
                        "profile_snapshot": row["profileSnapshot"],
                        "last_xtb_validation": row["lastXtbValidation"],
                        "created_at": row["createdAt"], "updated_at": row["updatedAt"],
                    }
                )
            elif kind == "bar":
                bars.append(
                    {
                        "instrument_id": row["instrumentId"], "timeframe": row["timeframe"],
                        "timestamp": row["timestamp"], "open": row["open"],
                        "high": row["high"], "low": row["low"], "close": row["close"],
                        "volume": row["volume"], "adj_close": row["adjClose"],
                        "source": row["source"],
                    }
                )
            else:
                raise ValueError(f"{path}:{number}: linea con 'kind' desconocido: {kind!r}")
    if len(instruments) != manifest["instruments"] or len(bars) != manifest["bars"]:
        raise ValueError(
            f"{path}: recuento no cuadra con el manifiesto "
            f"(instrumentos {len(instruments)}/{manifest['instruments']}, "
            f"barras {len(bars)}/{manifest['bars']})"
        )
    return instruments, bars


def _verify(args: argparse.Namespace) -> int:
    fixture = pathlib.Path(args.fixture)
    instruments, bars = _read_fixture(fixture)
    digest, size = _sha256_file(fixture)
    per_symbol = _group(bars)
    counts = {symbol: len(rows) for symbol, rows in sorted(per_symbol.items())}
    print(f"fixture          {fixture}")
    print(f"formato          {_FORMAT}")
    print(f"instrumentos     {len(instruments)}")
    print(f"barras           {len(bars)}")
    print(f"simbolos         {len(per_symbol)}")
    print(f"barras/simbolo   {sorted(set(counts.values()))}")
    print(f"primera barra    {min(row['timestamp'] for row in bars)}")
    print(f"ultima barra     {max(row['timestamp'] for row in bars)}")
    print(f"timeframes       {sorted({row['timeframe'] for row in bars})}")
    print(f"fuentes          {sorted({row['source'] for row in bars})}")
    print(f"adj_close nulos  {sum(1 for row in bars if row['adj_close'] is None)}")
    print(f"bytes            {size}")
    print(f"sha256           {digest}")
    print(f"a reproducir     {_SEALED_ARTIFACT_SHA256} ({_SEALED_ARTIFACT_BYTES} B)  render del sello (CRLF)")
    print(f"                 {_SEALED_ARTIFACT_SHA256_LF} ({_SEALED_ARTIFACT_BYTES_LF} B)  el MISMO contenido en LF")
    return 0


def _print_watch(args: argparse.Namespace) -> int:
    """Imprime el watch congelado (CSV) para pasárselo al replay SIN duplicar la lista.

    El workflow del tag lee de aquí los ids en vez de repetirlos: la única fuente de verdad
    del watch es el manifiesto del fixture, de modo que no puede derivar.
    """
    manifest = _read_manifest(pathlib.Path(args.fixture))
    print(",".join(manifest["watch"]))
    return 0


def _assert_artifact(args: argparse.Namespace) -> int:
    """Contrasta el artefacto regenerado con la REFERENCIA, separando CONTENIDO de RENDER.

    El sello original se escribió en Windows en modo texto y el runner escribe en LF: el `sha256`
    del fichero **no** identifica la evidencia, identifica su render (medido: 103 125 bytes de
    diferencia = 1 `\\r` por línea, con las secciones idénticas). Así que hay dos formas válidas
    de estar «reproducido», y se declaran las dos en vez de esconder una (valores vigentes =
    los de `_SEALED_ARTIFACT_*`):

    * **render del sello**: byte a byte == `24066225…6D9F54F0` / 3 445 622 B (fichero CRLF);
    * **mismo contenido**: LF normalizado == `1E3ADAC2…929A37E7` / 3 340 728 B (fichero LF).

    Si se pasan `--sha256`/`--bytes` explícitos se exige ese render concreto: la vía
    normalizada solo se acepta contra los valores SELLADOS, no contra un valor suelto.
    """
    path = pathlib.Path(args.file)
    if not path.is_file():
        print(f"# ABORTO: no existe el artefacto {path}", file=sys.stderr)
        return 2

    raw = path.read_bytes()
    digest, size = _sha256_file(path)
    canonical = _canonical_lf(raw)
    canonical_digest = hashlib.sha256(canonical).hexdigest().upper()

    expected_sha = (args.sha256 or _SEALED_ARTIFACT_SHA256).upper()
    expected_bytes = int(args.bytes or _SEALED_ARTIFACT_BYTES)
    override = bool(args.sha256 or args.bytes)

    render_ok = digest == expected_sha and size == expected_bytes
    content_ok = (
        not override
        and canonical_digest == _SEALED_ARTIFACT_SHA256_LF
        and len(canonical) == _SEALED_ARTIFACT_BYTES_LF
    )

    print(f"artefacto        {path}")
    print(f"render           {_render_of(raw)}")
    print(f"bytes            {size}  (sello {expected_bytes} · mismo contenido en LF {_SEALED_ARTIFACT_BYTES_LF})")
    print(f"sha256           {digest}")
    print(f"sello (render)   {expected_sha}")
    print(f"sha256 LF        {canonical_digest}")
    print(f"sello (contenido){_SEALED_ARTIFACT_SHA256_LF}")
    if render_ok:
        verdict = "REPRODUCIDO (render del sello, byte a byte)"
    elif content_ok:
        verdict = "REPRODUCIDO (mismo CONTENIDO; el sello está en CRLF y este fichero en LF)"
    else:
        verdict = "NO reproducido"
    print(f"VEREDICTO        {verdict}")
    return 0 if (render_ok or content_ok) else 1


# ── CLI ──────────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    if sys.platform == "win32":  # pragma: no cover — psycopg async no soporta ProactorEventLoop.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_export = sub.add_parser("export", help="congela la entrada desde PostgreSQL (READ-ONLY)")
    p_export.add_argument("--out", required=True, help="ruta del NDJSON a escribir")
    p_export.add_argument("--watch", default=None, help="ids separados por coma (por defecto: los sellados)")
    p_export.set_defaults(func=lambda args: asyncio.run(_export(args)))

    p_seed = sub.add_parser("seed", help="siembra el fixture en la BD destino (idempotente)")
    p_seed.add_argument("--fixture", required=True, help="ruta del NDJSON")
    p_seed.set_defaults(func=lambda args: asyncio.run(_seed(args)))

    p_verify = sub.add_parser("verify", help="comprueba el fixture sin BD (recuentos + huella)")
    p_verify.add_argument("--fixture", required=True, help="ruta del NDJSON")
    p_verify.set_defaults(func=_verify)

    p_watch = sub.add_parser("watch", help="imprime el watch congelado (CSV) para el replay")
    p_watch.add_argument("--fixture", required=True, help="ruta del NDJSON")
    p_watch.set_defaults(func=_print_watch)

    p_assert = sub.add_parser("assert-artifact", help="contrasta el artefacto regenerado con el sello")
    p_assert.add_argument("--file", required=True, help="artefacto regenerado por el replay")
    p_assert.add_argument("--sha256", default=None, help="hash esperado (por defecto: el sellado)")
    p_assert.add_argument("--bytes", default=None, help="tamaño esperado (por defecto: el sellado)")
    p_assert.set_defaults(func=_assert_artifact)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
