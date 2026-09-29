"""
30-Kerzen BTC Bot
Polymarket BTC 5m Importer

Version: 0.1.0

Zweck
-----
Dieses Programm:

1. liest den veröffentlichten Polymarket BTC-5m-Datensatz ein
2. prüft die Parquet-Datei
3. zeigt Struktur und Spalten
4. untersucht Zeitinformationen
5. untersucht label_up
6. untersucht Preisfelder
7. schreibt eine CSV-Kopie für weitere Analysen

WICHTIG
-------
Dieses Programm führt KEIN Trading durch.

- Kein Live Trading
- Keine API Keys
- Kein Wallet
- Keine echten Orders
- Keine privaten Schlüssel

Es handelt sich ausschließlich um Datenanalyse.

Quelle
------
sii_exec_matrix_btc5m.parquet

Die Datei wird durch GitHub Actions automatisch heruntergeladen.
"""


from pathlib import Path
import sys


# ============================================================
# ABHÄNGIGKEITEN
# ============================================================

try:
    import pandas as pd
except ImportError:
    print()
    print("FEHLER: pandas ist nicht installiert.")
    print()
    print("Installation:")
    print("pip install pandas")
    print()
    sys.exit(1)


try:
    import pyarrow.parquet as pq
except ImportError:
    print()
    print("FEHLER: pyarrow ist nicht installiert.")
    print()
    print("Installation:")
    print("pip install pyarrow")
    print()
    sys.exit(1)


# ============================================================
# KONFIGURATION
# ============================================================

PROJECT_NAME = "30-Kerzen BTC Bot"
VERSION = "0.1.0"

DATA_DIR = Path("data")

SOURCE_FILE = DATA_DIR / "sii_exec_matrix_btc5m.parquet"
OUTPUT_FILE = DATA_DIR / "polymarket_btc5m.csv"


# ============================================================
# AUSGABE
# ============================================================

def print_header():
    print()
    print("=" * 70)
    print(PROJECT_NAME)
    print("POLYMARKET BTC 5m IMPORTER")
    print("=" * 70)
    print(f"Version:       {VERSION}")
    print(f"Quelle:        {SOURCE_FILE}")
    print(f"Zieldatei:     {OUTPUT_FILE}")
    print("=" * 70)


# ============================================================
# QUELLDATEI PRÜFEN
# ============================================================

def check_source():
    """
    Prüft, ob die Parquet-Datei vorhanden ist.
    """

    print()
    print("QUELLDATEI")
    print("-" * 70)

    if not SOURCE_FILE.exists():

        print("FEHLER: Quelldatei nicht gefunden.")
        print()
        print(f"Erwartete Datei:")
        print(f"  {SOURCE_FILE}")
        print()
        print("Die GitHub Action sollte die Datei automatisch")
        print("herunterladen.")
        print()

        return False

    file_size_mb = SOURCE_FILE.stat().st_size / (1024 * 1024)

    print(f"Datei:         {SOURCE_FILE}")
    print(f"Größe:         {file_size_mb:.2f} MB")
    print("Status:        GEFUNDEN")

    return True


# ============================================================
# PARQUET EINLESEN
# ============================================================

def load_parquet():
    """
    Liest die komplette Parquet-Datei ein.
    """

    print()
    print("PARQUET EINLESEN")
    print("-" * 70)

    try:

        table = pq.read_table(SOURCE_FILE)

    except Exception as exc:

        print()
        print("FEHLER beim Lesen der Parquet-Datei:")
        print(exc)
        print()

        sys.exit(1)

    print(f"Zeilen:        {table.num_rows:,}")
    print(f"Spalten:       {table.num_columns}")

    print()
    print("SCHEMA")
    print("-" * 70)

    for field in table.schema:

        print(
            f"{field.name:35} "
            f"{field.type}"
        )

    try:

        df = table.to_pandas()

    except Exception as exc:

        print()
        print("FEHLER beim Umwandeln in pandas:")
        print(exc)
        print()

        sys.exit(1)

    return df


# ============================================================
# DATAFRAME PRÜFEN
# ============================================================

def inspect_dataframe(df):
    """
    Grundlegende Prüfung der eingelesenen Daten.
    """

    print()
    print("DATENPRÜFUNG")
    print("-" * 70)

    print(f"Anzahl Zeilen:       {len(df):,}")
    print(f"Anzahl Spalten:      {len(df.columns)}")

    print()
    print("SPALTENNAMEN")
    print("-" * 70)

    for column in df.columns:

        print(f"  {column}")

    print()
    print("ERSTE 5 ZEILEN")
    print("-" * 70)

    if len(df) > 0:

        print(
            df.head(5).to_string(
                index=False
            )
        )

    else:

        print("Keine Daten vorhanden.")

    print()
    print("LETZTE 5 ZEILEN")
    print("-" * 70)

    if len(df) > 0:

        print(
            df.tail(5).to_string(
                index=False
            )
        )

    else:

        print("Keine Daten vorhanden.")


# ============================================================
# ZEITSPALTEN SUCHEN
# ============================================================

def find_time_columns(df):
    """
    Sucht bekannte Zeitspalten.
    """

    candidates = [

        "timestamp",

        "timestamp_ms",

        "timestamp_s",

        "time",

        "start_time",

        "market_start",

        "start_timestamp",

        "end_time",

        "created_at",

        "updated_at",

    ]

    found = []

    for column in candidates:

        if column in df.columns:

            found.append(column)

    return found


# ============================================================
# ZEITINFORMATIONEN
# ============================================================

def inspect_time(df):
    """
    Prüft vorhandene Zeitspalten.
    """

    print()
    print("ZEITINFORMATION")
    print("-" * 70)

    time_columns = find_time_columns(df)

    if not time_columns:

        print(
            "Keine bekannte Zeitspalte "
            "automatisch gefunden."
        )

        return

    for column in time_columns:

        print()
        print(f"Spalte: {column}")

        series = df[column]

        print(
            f"Datentyp: {series.dtype}"
        )

        try:

            if pd.api.types.is_numeric_dtype(series):

                valid_values = series.dropna()

                if len(valid_values) == 0:

                    print(
                        "Keine gültigen Werte."
                    )

                    continue

                maximum = valid_values.max()

                minimum = valid_values.min()

                # Millisekunden
                if maximum > 10_000_000_000:

                    dt = pd.to_datetime(
                        series,
                        unit="ms",
                        utc=True,
                        errors="coerce",
                    )

                # Sekunden
                else:

                    dt = pd.to_datetime(
                        series,
                        unit="s",
                        utc=True,
                        errors="coerce",
                    )

            else:

                dt = pd.to_datetime(
                    series,
                    utc=True,
                    errors="coerce",
                )

            print(
                f"Minimum:  {dt.min()}"
            )

            print(
                f"Maximum:  {dt.max()}"
            )

            valid_count = dt.notna().sum()

            print(
                f"Gültige Werte: {valid_count:,}"
            )

        except Exception as exc:

            print(
                f"Zeitprüfung nicht möglich: {exc}"
            )


# ============================================================
# LABEL UP
# ============================================================

def inspect_labels(df):
    """
    Prüft label_up.
    """

    print()
    print("LABEL-UP-PRÜFUNG")
    print("-" * 70)

    if "label_up" not in df.columns:

        print(
            "Keine Spalte 'label_up' gefunden."
        )

        return

    print(
        "Spalte 'label_up' gefunden."
    )

    print()
    print("Verteilung:")

    try:

        distribution = (
            df["label_up"]
            .value_counts(
                dropna=False
            )
        )

        print(
            distribution.to_string()
        )

    except Exception as exc:

        print(
            f"Fehler bei label_up: {exc}"
        )


# ============================================================
# PREISSPALTEN
# ============================================================

def inspect_price_columns(df):
    """
    Sucht nach offensichtlichen Preisfeldern.
    """

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

        "prob",

        "quote",

    ]

    found = []

    for column in df.columns:

        name = str(column).lower()

        if any(
            keyword in name
            for keyword in keywords
        ):

            found.append(column)

    if not found:

        print(
            "Keine offensichtlichen "
            "Preisspalten gefunden."
        )

        return

    for column in found:

        print(
            f"  {column}"
        )


# ============================================================
# NULL-PRÜFUNG
# ============================================================

def inspect_missing_values(df):
    """
    Prüft fehlende Werte.
    """

    print()
    print("MISSING VALUES")
    print("-" * 70)

    missing = df.isna().sum()

    missing = missing[
        missing > 0
    ]

    if len(missing) == 0:

        print(
            "Keine fehlenden Werte gefunden."
        )

        return

    print(
        missing.to_string()
    )


# ============================================================
# DUPLIKATE
# ============================================================

def inspect_duplicates(df):
    """
    Prüft doppelte Datensätze.
    """

    print()
    print("DUPLIKATE")
    print("-" * 70)

    duplicates = df.duplicated().sum()

    print(
        f"Doppelte Zeilen: {duplicates:,}"
    )


# ============================================================
# CSV SPEICHERN
# ============================================================

def save_csv(df):
    """
    Speichert eine CSV-Kopie.
    """

    print()
    print("CSV ERZEUGEN")
    print("-" * 70)

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:

        df.to_csv(
            OUTPUT_FILE,
            index=False,
        )

    except Exception as exc:

        print()
        print("FEHLER beim Speichern:")
        print(exc)
        print()

        sys.exit(1)

    file_size_mb = (
        OUTPUT_FILE.stat().st_size
        / (1024 * 1024)
    )

    print(
        f"Gespeichert:   {OUTPUT_FILE}"
    )

    print(
        f"CSV-Größe:     {file_size_mb:.2f} MB"
    )


# ============================================================
# ZUSAMMENFASSUNG
# ============================================================

def print_summary(df):
    """
    Gibt eine kompakte Zusammenfassung aus.
    """

    print()
    print("=" * 70)
    print("IMPORT-ZUSAMMENFASSUNG")
    print("=" * 70)

    print(
        f"Datensätze:       {len(df):,}"
    )

    print(
        f"Spalten:          {len(df.columns)}"
    )

    print(
        f"Parquet-Datei:    {SOURCE_FILE}"
    )

    print(
        f"CSV-Datei:        {OUTPUT_FILE}"
    )

    print()
    print(
        "Der Datensatz wurde erfolgreich "
        "eingelesen und geprüft."
    )

    print("=" * 70)


# ============================================================
# MAIN
# ============================================================

def main():

    print_header()

    # --------------------------------------------------------
    # Quelldatei
    # --------------------------------------------------------

    if not check_source():

        sys.exit(1)

    # --------------------------------------------------------
    # Daten laden
    # --------------------------------------------------------

    df = load_parquet()

    # --------------------------------------------------------
    # Prüfungen
    # --------------------------------------------------------

    inspect_dataframe(df)

    inspect_time(df)

    inspect_labels(df)

    inspect_price_columns(df)

    inspect_missing_values(df)

    inspect_duplicates(df)

    # --------------------------------------------------------
    # CSV
    # --------------------------------------------------------

    save_csv(df)

    # --------------------------------------------------------
    # Zusammenfassung
    # --------------------------------------------------------

    print_summary(df)

    # --------------------------------------------------------
    # Sicherheitshinweis
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("SICHERHEITSSTATUS")
    print("=" * 70)
    print()
    print("PAPER TRADING ONLY")
    print("KEIN LIVE TRADING")
    print("KEINE API KEYS")
    print("KEIN WALLET")
    print("KEINE PRIVATEN SCHLÜSSEL")
    print("KEINE ECHTEN ORDERS")
    print()
    print("=" * 70)

    print()
    print(
        "NÄCHSTER SCHRITT:"
    )

    print(
        "Polymarket BTC-5m-Daten mit "
        "den BTC-5m-Kerzen verbinden."
    )

    print()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
