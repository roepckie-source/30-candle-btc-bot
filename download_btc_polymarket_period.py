"""
30-Kerzen BTC Bot
BTC Historical Data Downloader for Polymarket Period

Lädt automatisch den BTC-5m-Zeitraum,
der für den vorhandenen Polymarket-Datensatz benötigt wird.

Quelle:
Coinbase Public Exchange API

KEIN API KEY
KEIN LIVE TRADING
"""

from pathlib import Path
import csv
import time
import requests
from datetime import datetime, timezone


POLYMARKET_FILE = Path("data/polymarket_btc5m.csv")
OUTPUT_FILE = Path("data/BTC_USD_5m_polymarket_period.csv")

COINBASE_URL = (
    "https://api.exchange.coinbase.com/"
    "products/BTC-USD/candles"
)

GRANULARITY = 300

MAX_CANDLES_PER_REQUEST = 300

REQUEST_SLEEP = 0.25

WINDOW_CANDLES = 30

WINDOW_SECONDS = WINDOW_CANDLES * GRANULARITY


def ts_to_dt(ts):
    return datetime.fromtimestamp(
        ts,
        tz=timezone.utc
    )


def load_polymarket_range():

    if not POLYMARKET_FILE.exists():
        raise FileNotFoundError(
            f"{POLYMARKET_FILE} nicht gefunden."
        )

    timestamps = []

    with POLYMARKET_FILE.open(
        "r",
        encoding="utf-8",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        if "start_ts" not in reader.fieldnames:
            raise RuntimeError(
                "Spalte 'start_ts' fehlt in der Polymarket CSV."
            )

        for row in reader:

            try:
                timestamps.append(
                    int(float(row["start_ts"]))
                )

            except (ValueError, TypeError):
                continue

    if not timestamps:
        raise RuntimeError(
            "Keine gültigen Polymarket start_ts gefunden."
        )

    return min(timestamps), max(timestamps)


def fetch_chunk(start_ts, end_ts):

    params = {
        "granularity": GRANULARITY,
        "start": datetime.fromtimestamp(
            start_ts,
            tz=timezone.utc
        ).isoformat(),
        "end": datetime.fromtimestamp(
            end_ts,
            tz=timezone.utc
        ).isoformat(),
    }

    response = requests.get(
        COINBASE_URL,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):

        raise RuntimeError(
            "Unerwartete Coinbase Antwort:"
            f" {data}"
        )

    return data


def download():

    print()
    print("=" * 80)
    print("BTC HISTORICAL DATA FOR POLYMARKET")
    print("=" * 80)

    minimum, maximum = load_polymarket_range()

    original_minimum = minimum

    # 30 vollständige BTC-Kerzen vor dem ersten
    # Polymarket-Markt zusätzlich laden.
    minimum -= WINDOW_SECONDS

    print()
    print("POLYMARKET ZEITRAUM")
    print("-" * 80)

    print(
        f"Start: {ts_to_dt(original_minimum)}"
    )

    print(
        f"Ende:  {ts_to_dt(maximum)}"
    )

    print()
    print("BTC BENÖTIGTER ZEITRAUM")
    print("-" * 80)

    print(
        f"Start: {ts_to_dt(minimum)}"
    )

    print(
        f"Ende:  {ts_to_dt(maximum)}"
    )

    print()
    print(
        f"30-Kerzen-Puffer: "
        f"{WINDOW_CANDLES} × 5 Minuten"
    )

    print()

    all_rows = {}

    chunk_seconds = (
        MAX_CANDLES_PER_REQUEST
        * GRANULARITY
    )

    current = minimum

    total_requests = 0

    while current <= maximum:

        chunk_end = min(
            current + chunk_seconds,
            maximum + GRANULARITY
        )

        total_requests += 1

        print(
            f"Request {total_requests}: "
            f"{ts_to_dt(current)} → "
            f"{ts_to_dt(chunk_end)}"
        )

        data = fetch_chunk(
            current,
            chunk_end
        )

        print(
            f"  Coinbase Kerzen: {len(data)}"
        )

        for row in data:

            if len(row) < 6:
                continue

            timestamp = int(row[0])

            # Coinbase Format:
            #
            # [ timestamp,
            #   low,
            #   high,
            #   open,
            #   close,
            #   volume ]

            all_rows[timestamp] = {
                "timestamp": timestamp,
                "open": float(row[3]),
                "high": float(row[2]),
                "low": float(row[1]),
                "close": float(row[4]),
                "volume": float(row[5]),
            }

        current = chunk_end

        time.sleep(REQUEST_SLEEP)

    rows = sorted(
        all_rows.values(),
        key=lambda x: x["timestamp"]
    )

    print()
    print("=" * 80)
    print("DOWNLOAD ABGESCHLOSSEN")
    print("=" * 80)

    print(
        f"BTC Kerzen insgesamt: {len(rows):,}"
    )

    if rows:

        print(
            "Tatsächlicher Zeitraum:"
        )

        print(
            f"{ts_to_dt(rows[0]['timestamp'])}"
            " → "
            f"{ts_to_dt(rows[-1]['timestamp'])}"
        )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ],
        )

        writer.writeheader()

        writer.writerows(rows)

    print()
    print(
        f"Gespeichert: {OUTPUT_FILE}"
    )

    print()
    print("=" * 80)
    print("SICHERHEITSSTATUS")
    print("=" * 80)
    print()
    print("PAPER TRADING ONLY")
    print("KEIN LIVE TRADING")
    print("KEINE API KEYS")
    print("KEIN WALLET")
    print("KEINE PRIVATEN SCHLÜSSEL")
    print("KEINE ECHTEN ORDERS")
    print()


if __name__ == "__main__":
    download()
