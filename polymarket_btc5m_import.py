"""
30-Kerzen BTC Bot
Polymarket BTC 5m Importer
Version 0.1.0

Zweck:
- Kleine veröffentlichte Polymarket BTC-5m-Matrix einlesen
- Datenstruktur prüfen
- BTC-5m-Märkte validieren
- Zeitbereich und Spalten ausgeben
- Noch KEIN Trading
- Noch KEIN Signal-Backtest

Quelle:
Filip303/Polymarket
data/sii_exec_matrix_btc5m.parquet

Quelle laut Repository:
23.338 BTC-5m-Märkte
2026-02-12 bis 2026-05-04 UTC
"""

from pathlib import Path
import sys

try:
    import pandas as pd
except ImportError:
    print("FEHLER: pandas fehlt.")
    print("Installation: pip install pandas pyarrow")
    sys.exit(1)

try:
    import pyarrow.parquet as pq
except ImportError:
    print("FEHLER: pyarrow fehlt.")
    print("Installation: pip install pyarrow")
    sys.exit(1)


PROJECT_NAME = "30-Kerzen BTC Bot"
VERSION = "0.1.0"

DATA_DIR = Path("data")

SOURCE_FILE = DATA_DIR / "sii_exec_matrix_btc5m.parquet"
OUTPUT_FILE = DATA_DIR / "polymarket_btc5m.csv"


def print_header():
    print("=" * 70)
    print(PROJECT_NAME)
    print("POLYMARKET BTC 5m IMPORT")
    print("=" * 70)
    print(f"Version:       {VERSION}")
    print(f"Quelle:        {SOURCE_FILE}")
    print(f"Zieldatei:     {OUTPUT_FILE}")
    print("=" * 70)


def check_source():
    if not SOURCE_FILE.exists():
        print()
        print("FEHLER: Quelldatei nicht gefunden.")
        print()
        print(f"Erwartet:")
        print(f"  {SOURCE_FILE}")
        print()
        print("Bitte die Datei")
        print("sii_exec_matrix_btc5m.parquet")
        print("in den Ordner data/ legen.")
        print()
        return False

    size_mb = SOURCE_FILE.stat().st_size / (1024 * 1024)

    print()
    print("QUELLDATEI")
    print("-" * 70)
    print(f"Datei:         {SOURCE_FILE}")
    print(f"Größe:         {size_mb:.2f} MB")
    print("Status:        GEFUNDEN")

    return True


def load_parquet():
    print()
    print("PARQUET EINLESEN")
    print("-" * 70)

    table = pq.read_table(SOURCE_FILE)

    print(f"Zeilen:        {table.num_rows:,}")
    print(f"Spalten:       {table.num_columns}")

    print()
    print("SCHEMA")
    print("-" * 70)

    for field in table.schema:
        print(f"{field.name:30} {field.type}")

    df = table.to_pandas()

    return df


def inspect_dataframe(df):
    print()
    print("DATENPRÜFUNG")
    print("-" * 70)

    print(f"Zeilen:        {len(df):,}")
    print(f"Spalten:       {len(df.columns)}")

    print()
    print("SPALTENNAMEN")
    print("-" * 70)

    for column in df.columns:
        print(column)

    print()
    print("ERSTE ZEILEN")
    print("-" * 70)

    print(df.head(5).to_string(index=False))

    print()
    print("LETZTE ZEILEN")
    print("-" * 70)

    print(df.tail(5).to_string(index=False))


def find_time_columns(df):
    candidates = [
        "timestamp",
        "timestamp_ms",
        "start_time",
        "market_start",
        "start_timestamp",
        "end_time",
    ]

    found = []

    for column in candidates:
        if column in df.columns:
            found.append(column)

    return found


def inspect_time(df):
    print()
    print("ZEITINFORMATION")
    print("-" * 70)

    time_columns = find_time_columns(df)

    if not time_columns:
        print("Keine bekannte Zeitspalte automatisch gefunden.")
        return

    for column in time_columns:
        print()
        print(f"Spalte: {column}")

        series = df[column]

        print(f"Datentyp: {series.dtype}")

        try:
            if pd.api.types.is_numeric_dtype(series):
                maximum = series.max()

                if maximum > 10_000_000_000:
                    dt = pd.to_datetime(series, unit="ms", utc=True)
                else:
                    dt = pd.to_datetime(series, unit="s", utc=True)
            else:
                dt = pd.to_datetime(series, utc=True, errors="coerce")

            print(f"Minimum:  {dt.min()}")
            print(f"Maximum:  {dt.max()}")

        except Exception as exc:
            print(f"Zeitprüfung nicht möglich: {exc}")


def inspect_labels(df):
    print()
    print("LABEL-PRÜFUNG")
    print("-" * 70)

    if "label_up" not in df.columns:
        print("Keine Spalte 'label_up' gefunden.")
        return

    print("label_up vorhanden.")

    print()
    print("Verteilung:")

    print(df["label_up"].value_counts(dropna=False).to_string())


def inspect_price_columns(df):
    print()
    print("PREISSPALTEN")
    print("-" * 70)

    keywords = [
        "price",
        "up",
        "down",
        "ask",
        "bid",
        "mid",
    ]

    found = []

    for column in df.columns:
        name = str(column).lower()

        if any(keyword in name for keyword in keywords):
            found.append(column)

    if not found:
        print("Keine offensichtlichen Preisspalten gefunden.")
        return

    for column in found:
        print(column)


def save_csv(df):
    print()
    print("CSV ERZEUGEN")
    print("-" * 70)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print(f"Gespeichert:   {OUTPUT_FILE}")

    size_mb = OUTPUT_FILE.stat().st_size / (1024 * 1024)

    print(f"CSV-Größe:     {size_mb:.2f} MB")


def main():
    print_header()

    if not check_source():
        sys.exit(1)

    df = load_parquet()

    inspect_dataframe(df)

    inspect_time(df)

    inspect_labels(df)

    inspect_price_columns(df)

    save_csv(df)

    print()
    print("=" * 70)
    print("IMPORT ABGESCHLOSSEN")
    print("=" * 70)
    print()
    print("PAPER TRADING ONLY")
    print("KEIN LIVE TRADING")
    print("KEINE API KEYS")
    print("KEIN WALLET")
    print("KEINE ECHTEN ORDERS")
    print()
    print("Nächster Schritt:")
    print("BTC-5m-Daten mit unseren BTC-Kerzen verbinden.")
    print("=" * 70)


if __name__ == "__main__":
    main()
