"""
30-Kerzen BTC Bot
Polymarket Signal Analysis

Version: 0.1.0

Zweck
-----
Verbindet:

1. BTC 5-Minuten-Kerzen
2. Polymarket BTC 5-Minuten-Märkte

und untersucht:

- 30-Kerzen-Fenster
- 26/30 Schwelle
- verschiedene Definitionen positiver BTC-Kerzen
- Polymarket label_up
- Polymarket Preise
- 30s / 60s / 120s / 180s / 240s

WICHTIG
-------
Nur historische Datenanalyse.

KEIN LIVE TRADING
KEINE API KEYS
KEIN WALLET
KEINE ECHTEN ORDERS
"""

from pathlib import Path
import csv
from datetime import datetime, timezone

PROJECT_NAME = "30-Kerzen BTC Bot"
VERSION = "0.1.0"

BTC_FILE = Path("data/BTC_USD_5m_polymarket_period.csv")
POLYMARKET_FILE = Path("data/polymarket_btc5m.csv")

WINDOW = 30
THRESHOLD = 26

LOOKBACKS = [1, 2, 3, 5, 10]

PRICE_COLUMNS = [
    "first_price_up",
    "vwap_full_diag",
    "p_30s",
    "p_60s",
    "p_120s",
    "p_180s",
    "p_240s",
]


def print_header():
    print()
    print("=" * 80)
    print(PROJECT_NAME)
    print("POLYMARKET SIGNAL ANALYSIS")
    print("=" * 80)
    print(f"Version:          {VERSION}")
    print(f"BTC Datei:        {BTC_FILE}")
    print(f"Polymarket Datei: {POLYMARKET_FILE}")
    print(f"Fenster:          {WINDOW}")
    print(f"Schwelle:         {THRESHOLD}/{WINDOW}")
    print("=" * 80)


def timestamp_to_datetime(timestamp):
    return datetime.fromtimestamp(
        int(timestamp),
        tz=timezone.utc
    )


def load_btc():
    print()
    print("BTC-DATEN LADEN")
    print("-" * 80)

    if not BTC_FILE.exists():
        print(f"FEHLER: {BTC_FILE} nicht gefunden.")
        return []

    rows = []

    with BTC_FILE.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)

        required = {
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

        if not required.issubset(reader.fieldnames or set()):
            print("FEHLER: BTC CSV besitzt nicht die erwarteten Spalten.")
            print("Gefunden:", reader.fieldnames)
            return []

        for row in reader:
            try:
                timestamp = int(float(row["timestamp"]))

                # Falls Timestamp in Millisekunden vorliegt
                if timestamp > 10_000_000_000:
                    timestamp //= 1000

                rows.append(
                    {
                        "timestamp": timestamp,
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": float(row["volume"]),
                    }
                )

            except (ValueError, TypeError):
                continue

    rows.sort(key=lambda x: x["timestamp"])

    print(f"BTC Kerzen:      {len(rows):,}")

    if rows:
        print(
            "BTC Zeitraum:    "
            f"{timestamp_to_datetime(rows[0]['timestamp'])} "
            "→ "
            f"{timestamp_to_datetime(rows[-1]['timestamp'])}"
        )

    return rows


def load_polymarket():
    print()
    print("POLYMARKET-DATEN LADEN")
    print("-" * 80)

    if not POLYMARKET_FILE.exists():
        print(f"FEHLER: {POLYMARKET_FILE} nicht gefunden.")
        return []

    rows = []

    with POLYMARKET_FILE.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)

        required = {
            "condition_id",
            "label_up",
            "start_ts",
        }

        if not required.issubset(reader.fieldnames or set()):
            print("FEHLER: Polymarket CSV besitzt nicht die erwarteten Spalten.")
            print("Gefunden:", reader.fieldnames)
            return []

        for row in reader:
            try:
                start_ts = int(float(row["start_ts"]))

                item = {
                    "condition_id": row["condition_id"],
                    "label_up": int(row["label_up"]),
                    "start_ts": start_ts,
                }

                for column in PRICE_COLUMNS:
                    value = row.get(column, "")

                    if value is None or value == "":
                        item[column] = None
                    else:
                        try:
                            item[column] = float(value)
                        except ValueError:
                            item[column] = None

                rows.append(item)

            except (ValueError, TypeError):
                continue

    rows.sort(key=lambda x: x["start_ts"])

    print(f"Polymarket Märkte: {len(rows):,}")

    if rows:
        print(
            "Polymarket Zeitraum: "
            f"{timestamp_to_datetime(rows[0]['start_ts'])} "
            "→ "
            f"{timestamp_to_datetime(rows[-1]['start_ts'])}"
        )

    return rows


def build_btc_index(btc_rows):
    return {
        row["timestamp"]: row
        for row in btc_rows
    }


def get_30_candles(btc_index, start_ts):
    """
    Die 30 abgeschlossenen BTC-5m-Kerzen
    unmittelbar vor dem Polymarket-Marktstart.

    Marktstart selbst gehört NICHT zum Fenster.
    """

    candles = []

    for i in range(1, WINDOW + 1):
        timestamp = start_ts - (i * 300)

        candle = btc_index.get(timestamp)

        if candle is None:
            return None

        candles.append(candle)

    candles.reverse()

    return candles


def count_positive(candles, lookback):
    """
    Positive Definition:

    Close[i] > Close[i-lookback]

    Für lookback=1 entspricht das:
    Close > vorheriger Close
    """

    if len(candles) != WINDOW:
        return None

    count = 0

    for i in range(lookback, len(candles)):
        if candles[i]["close"] > candles[i - lookback]["close"]:
            count += 1

    return count


def count_close_open(candles):
    """
    Klassische grüne Kerze:

    Close > Open
    """

    if len(candles) != WINDOW:
        return None

    return sum(
        1
        for candle in candles
        if candle["close"] > candle["open"]
    )


def analyze():
    btc_rows = load_btc()
    polymarket_rows = load_polymarket()

    if not btc_rows or not polymarket_rows:
        return

    btc_index = build_btc_index(btc_rows)

    results = []

    matched = 0
    unmatched = 0

    for market in polymarket_rows:

        candles = get_30_candles(
            btc_index,
            market["start_ts"]
        )

        if candles is None:
            unmatched += 1
            continue

        matched += 1

        result = {
            "condition_id": market["condition_id"],
            "start_ts": market["start_ts"],
            "label_up": market["label_up"],
            "close_open": count_close_open(candles),
        }

        for lookback in LOOKBACKS:
            result[f"close_{lookback}"] = count_positive(
                candles,
                lookback
            )

        for column in PRICE_COLUMNS:
            result[column] = market[column]

        results.append(result)

    print()
    print("JOIN-ERGEBNIS")
    print("-" * 80)
    print(f"Polymarket Märkte:       {len(polymarket_rows):,}")
    print(f"BTC 30-Kerzen vorhanden: {matched:,}")
    print(f"Nicht zuordenbar:        {unmatched:,}")

    if not results:
        print()
        print("FEHLER: Keine Polymarket-Märkte konnten mit BTC-Kerzen verbunden werden.")
        print()
        print("Wahrscheinlich liegt der BTC-Datensatz zeitlich außerhalb")
        print("des Polymarket-Datensatzes.")
        return

    print()
    print("SIGNAL-VERTEILUNG")
    print("-" * 80)

    definitions = [
        ("Close > Open", "close_open"),
        ("Close > Close 1", "close_1"),
        ("Close > Close 2", "close_2"),
        ("Close > Close 3", "close_3"),
        ("Close > Close 5", "close_5"),
        ("Close > Close 10", "close_10"),
    ]

    for name, key in definitions:

        active = [
            r for r in results
            if r[key] is not None and r[key] >= THRESHOLD
        ]

        print()
        print(name)
        print(f"  Aktive Märkte: {len(active):,}")

        if not active:
            print("  Keine 26/30-Signale.")
            continue

        up = sum(1 for r in active if r["label_up"] == 1)
        down = sum(1 for r in active if r["label_up"] == 0)

        print(f"  label_up = 1: {up:,}")
        print(f"  label_up = 0: {down:,}")

        winrate = up / len(active)

        print(f"  UP-Anteil:    {winrate:.2%}")

        print()
        print("  Polymarket-Preise:")

        for column in PRICE_COLUMNS:
            values = [
                r[column]
                for r in active
                if r[column] is not None
            ]

            if not values:
                continue

            average = sum(values) / len(values)

            print(
                f"    {column:18} "
                f"Ø {average:.4f} "
                f"n={len(values):,}"
            )

    print()
    print("=" * 80)
    print("DETAILANALYSE DER 26/30-SIGNALE")
    print("=" * 80)

    for name, key in definitions:

        active = [
            r for r in results
            if r[key] is not None and r[key] >= THRESHOLD
        ]

        if not active:
            continue

        print()
        print(f"--- {name} ---")

        print(f"Signale:       {len(active):,}")

        up = sum(
            1
            for r in active
            if r["label_up"] == 1
        )

        down = len(active) - up

        print(f"UP:            {up:,}")
        print(f"DOWN:          {down:,}")

        print()
        print("Einzelne Signale:")

        for r in active[:20]:

            dt = timestamp_to_datetime(
                r["start_ts"]
            )

            print(
                f"{dt} | "
                f"signal={r[key]:2d}/30 | "
                f"label_up={r['label_up']} | "
                f"p30={r['p_30s']} | "
                f"p60={r['p_60s']} | "
                f"p120={r['p_120s']} | "
                f"p180={r['p_180s']} | "
                f"p240={r['p_240s']}"
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


def main():
    print_header()
    analyze()


if __name__ == "__main__":
    main()
