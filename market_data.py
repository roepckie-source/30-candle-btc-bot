"""
30-Kerzen BTC Bot
Market Data Module
Version 0.1.0

V1:
- BTC-USD
- 5-Minuten-Kerzen
- Öffentliche Coinbase-Marktdaten
- Kein API-Key
- Keine privaten Daten
- Speicherung als CSV
"""

from __future__ import annotations

import csv
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

import config


# ============================================================
# COINBASE API
# ============================================================

BASE_URL = "https://api.exchange.coinbase.com"

CANDLES_ENDPOINT = (
    f"{BASE_URL}/products/{config.COINBASE_PRODUCT_ID}/candles"
)


# ============================================================
# DATENSTRUKTUR
# ============================================================

CSV_HEADERS = [
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
]


# ============================================================
# HTTP
# ============================================================

def http_get_json(
    url: str,
    params: dict[str, Any] | None = None,
    timeout: int = 30,
) -> Any:
    """
    Führt einen öffentlichen GET-Request aus
    und gibt die JSON-Antwort zurück.
    """

    headers = {
        "User-Agent": "30-Kerzen-BTC-Bot/0.1.0",
        "Accept": "application/json",
    }

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=timeout,
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# EINEN DATENBLOCK LADEN
# ============================================================

def download_chunk(
    start: datetime,
    end: datetime,
) -> list[list[Any]]:
    """
    Lädt einen einzelnen Coinbase-Candles-Block.

    Coinbase liefert maximal eine begrenzte Anzahl Kerzen
    pro Request. Deshalb wird die Historie später in Blöcke
    aufgeteilt.

    Coinbase Candle Format:

        [
            time,
            low,
            high,
            open,
            close,
            volume
        ]
    """

    params = {
        "granularity": config.CANDLE_SECONDS,
        "start": start.astimezone(timezone.utc).isoformat(),
        "end": end.astimezone(timezone.utc).isoformat(),
    }

    data = http_get_json(
        CANDLES_ENDPOINT,
        params=params,
    )

    if not isinstance(data, list):
        raise RuntimeError(
            f"Unerwartete Coinbase-Antwort: {type(data)}"
        )

    return data


# ============================================================
# HISTORIE LADEN
# ============================================================

def download_history(
    days: int = 30,
    sleep_seconds: float = 0.25,
) -> list[dict[str, Any]]:
    """
    Lädt historische BTC-5m-Kerzen.

    Standard:
        30 Tage

    Die Daten werden in Coinbase-kompatible Blöcke
    aufgeteilt und anschließend dedupliziert und sortiert.
    """

    if days <= 0:
        raise ValueError("days muss größer als 0 sein.")

    print("=" * 60)
    print("BTC 5m MARKET DATA DOWNLOAD")
    print("=" * 60)

    print(f"Produkt:             {config.COINBASE_PRODUCT_ID}")
    print(f"Timeframe:           {config.TIMEFRAME}")
    print(f"Historie:            {days} Tage")
    print(f"Granularität:        {config.CANDLE_SECONDS} Sekunden")
    print()

    end_time = datetime.now(timezone.utc)

    start_time = end_time - timedelta(days=days)

    # Coinbase erlaubt nur eine begrenzte Anzahl Candles
    # pro Request.
    #
    # 300 * 5 Minuten = 1500 Minuten = 25 Stunden.
    chunk_duration = timedelta(
        seconds=config.CANDLE_SECONDS
        * config.MAX_CANDLES_PER_REQUEST
    )

    raw_candles: list[list[Any]] = []

    current_start = start_time

    request_number = 0

    while current_start < end_time:

        current_end = min(
            current_start + chunk_duration,
            end_time,
        )

        request_number += 1

        print(
            f"Request {request_number:02d}: "
            f"{current_start.strftime('%Y-%m-%d %H:%M')} UTC → "
            f"{current_end.strftime('%Y-%m-%d %H:%M')} UTC"
        )

        try:
            chunk = download_chunk(
                current_start,
                current_end,
            )

        except requests.HTTPError as exc:
            print(f"HTTP-Fehler: {exc}")

            if getattr(exc.response, "status_code", None) == 429:
                print("Rate Limit erreicht – warte 5 Sekunden.")
                time.sleep(5)
                continue

            raise

        print(f"  erhalten: {len(chunk)} Kerzen")

        raw_candles.extend(chunk)

        current_start = current_end

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    # --------------------------------------------------------
    # Konvertieren
    # --------------------------------------------------------

    candles_by_timestamp: dict[int, dict[str, Any]] = {}

    for row in raw_candles:

        if len(row) != 6:
            continue

        try:
            timestamp = int(row[0])

            low = float(row[1])
            high = float(row[2])
            open_price = float(row[3])
            close_price = float(row[4])
            volume = float(row[5])

        except (TypeError, ValueError):
            continue

        # Nur Daten aus dem angeforderten Zeitraum übernehmen.
        if timestamp < int(start_time.timestamp()):
            continue

        if timestamp > int(end_time.timestamp()):
            continue

        candles_by_timestamp[timestamp] = {
            "timestamp": timestamp,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close_price,
            "volume": volume,
        }

    candles = list(candles_by_timestamp.values())

    candles.sort(
        key=lambda candle: candle["timestamp"]
    )

    print()
    print(f"Gesamt eindeutige Kerzen: {len(candles)}")

    return candles


# ============================================================
# CSV SPEICHERN
# ============================================================

def save_csv(
    candles: list[dict[str, Any]],
    filename: str | None = None,
) -> Path:
    """
    Speichert Candles als CSV.
    """

    if filename is None:
        filename = config.CSV_FILE

    path = Path(filename)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=CSV_HEADERS,
        )

        writer.writeheader()

        for candle in candles:

            writer.writerow({
                "timestamp": candle["timestamp"],
                "open": f'{candle["open"]:.8f}',
                "high": f'{candle["high"]:.8f}',
                "low": f'{candle["low"]:.8f}',
                "close": f'{candle["close"]:.8f}',
                "volume": f'{candle["volume"]:.8f}',
            })

    print()
    print(f"CSV gespeichert: {path}")

    return path


# ============================================================
# CSV LADEN
# ============================================================

def load_csv(
    filename: str | None = None,
) -> list[dict[str, Any]]:
    """
    Lädt gespeicherte Candles aus einer CSV-Datei.
    """

    if filename is None:
        filename = config.CSV_FILE

    path = Path(filename)

    if not path.exists():
        raise FileNotFoundError(
            f"CSV-Datei nicht gefunden: {path}"
        )

    candles: list[dict[str, Any]] = []

    with path.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            candles.append({
                "timestamp": int(row["timestamp"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            })

    candles.sort(
        key=lambda candle: candle["timestamp"]
    )

    return candles


# ============================================================
# VALIDIERUNG
# ============================================================

def validate_data(
    candles: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    """
    Prüft die grundlegende Qualität der Marktdaten.
    """

    errors: list[str] = []

    if not candles:
        errors.append("Keine Candles vorhanden.")
        return False, errors

    previous_timestamp: int | None = None

    for index, candle in enumerate(candles):

        required_fields = [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]

        for field in required_fields:

            if field not in candle:
                errors.append(
                    f"Candle {index}: Feld '{field}' fehlt."
                )

        timestamp = candle["timestamp"]
        open_price = candle["open"]
        high = candle["high"]
        low = candle["low"]
        close = candle["close"]
        volume = candle["volume"]

        if previous_timestamp is not None:

            if timestamp <= previous_timestamp:
                errors.append(
                    f"Candle {index}: Zeitstempel nicht "
                    f"streng aufsteigend."
                )

        previous_timestamp = timestamp

        if open_price <= 0:
            errors.append(
                f"Candle {index}: Open <= 0."
            )

        if high <= 0:
            errors.append(
                f"Candle {index}: High <= 0."
            )

        if low <= 0:
            errors.append(
                f"Candle {index}: Low <= 0."
            )

        if close <= 0:
            errors.append(
                f"Candle {index}: Close <= 0."
            )

        if volume < 0:
            errors.append(
                f"Candle {index}: Volume < 0."
            )

        if high < low:
            errors.append(
                f"Candle {index}: High < Low."
            )

        if high < max(open_price, close):
            errors.append(
                f"Candle {index}: High ist kleiner "
                f"als Open/Close."
            )

        if low > min(open_price, close):
            errors.append(
                f"Candle {index}: Low ist größer "
                f"als Open/Close."
            )

    return len(errors) == 0, errors


# ============================================================
# LÜCKEN FINDEN
# ============================================================

def find_gaps(
    candles: list[dict[str, Any]],
) -> list[tuple[int, int]]:
    """
    Findet Lücken im 5-Minuten-Datensatz.

    Rückgabe:
        Liste aus (vorheriger_timestamp, aktueller_timestamp)
    """

    gaps: list[tuple[int, int]] = []

    expected_seconds = config.CANDLE_SECONDS

    for previous, current in zip(
        candles,
        candles[1:],
    ):

        difference = (
            current["timestamp"]
            - previous["timestamp"]
        )

        if difference != expected_seconds:
            gaps.append((
                previous["timestamp"],
                current["timestamp"],
            ))

    return gaps


# ============================================================
# ZEITSTEMPEL FORMATIEREN
# ============================================================

def format_timestamp(timestamp: int) -> str:
    """
    Unix-Zeitstempel → lesbare UTC-Zeit.
    """

    return datetime.fromtimestamp(
        timestamp,
        tz=timezone.utc,
    ).strftime("%Y-%m-%d %H:%M:%S UTC")


# ============================================================
# ZUSAMMENFASSUNG
# ============================================================

def print_summary(
    candles: list[dict[str, Any]],
) -> None:
    """
    Gibt eine Zusammenfassung der Marktdaten aus.
    """

    if not candles:
        print("Keine Daten.")
        return

    first = candles[0]
    last = candles[-1]

    gaps = find_gaps(candles)

    print()
    print("=" * 60)
    print("MARKET DATA SUMMARY")
    print("=" * 60)

    print(f"Produkt:             {config.COINBASE_PRODUCT_ID}")
    print(f"Timeframe:           {config.TIMEFRAME}")
    print(f"Kerzen:              {len(candles)}")

    print()
    print(
        "Erste Kerze:         "
        f"{format_timestamp(first['timestamp'])}"
    )

    print(
        "Letzte Kerze:        "
        f"{format_timestamp(last['timestamp'])}"
    )

    print()
    print(f"Erster Close:        ${first['close']:,.2f}")
    print(f"Letzter Close:       ${last['close']:,.2f}")

    print()
    print(f"Datenlücken:         {len(gaps)}")

    if gaps:

        print()
        print("Erste Lücken:")

        for previous, current in gaps[:10]:

            print(
                f"  {format_timestamp(previous)}"
                f" → "
                f"{format_timestamp(current)}"
            )

    print("=" * 60)


# ============================================================
# KOMPLETTER DOWNLOAD
# ============================================================

def download_and_save(
    days: int = 30,
) -> list[dict[str, Any]]:
    """
    Lädt Historie, validiert sie und speichert sie.
    """

    candles = download_history(
        days=days
    )

    valid, errors = validate_data(
        candles
    )

    print()

    if valid:

        print("VALIDIERUNG: PASS")

    else:

        print("VALIDIERUNG: FEHLER")

        for error in errors[:20]:
            print(f"  - {error}")

        if len(errors) > 20:
            print(
                f"  ... und {len(errors) - 20} weitere Fehler"
            )

        raise RuntimeError(
            "Marktdaten konnten nicht validiert werden."
        )

    save_csv(candles)

    print_summary(candles)

    return candles


# ============================================================
# SELF TEST
# ============================================================

def self_test() -> None:
    """
    Lokaler Test der Datenfunktionen.
    """

    print("=" * 60)
    print("MARKET DATA SELF TEST")
    print("=" * 60)

    sample = [
        {
            "timestamp": 1000,
            "open": 100.0,
            "high": 102.0,
            "low": 99.0,
            "close": 101.0,
            "volume": 10.0,
        },
        {
            "timestamp": 1300,
            "open": 101.0,
            "high": 103.0,
            "low": 100.0,
            "close": 102.0,
            "volume": 12.0,
        },
    ]

    valid, errors = validate_data(sample)

    assert valid, errors

    gaps = find_gaps(sample)

    assert len(gaps) == 0

    formatted = format_timestamp(0)

    assert formatted == "1970-01-01 00:00:00 UTC"

    print("PASS: Datenvalidierung")

    print("PASS: Gap-Prüfung")

    print("PASS: Zeitformatierung")

    print("PASS: Market Data Self Test")

    print("=" * 60)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    self_test()

    print()

    print(
        "Starte Download von 30 Tagen BTC-5m-Daten..."
    )

    download_and_save(days=30)
