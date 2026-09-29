"""
30-Kerzen BTC Bot
Polymarket Forward BTC Analysis

Version: 0.1.0

Zweck
-----
Untersucht, was BTC NACH einem echten 26/30-Signal macht.

Getestete Regeln:
- Close > Close 2
- Close > Close 3
- Close > Close 5
- Close > Close 10

Horizonte:
- 5 Minuten
- 10 Minuten
- 15 Minuten
- 30 Minuten
- 60 Minuten
- 2 Stunden
- 4 Stunden

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
from statistics import median
from datetime import datetime, timezone


# ============================================================
# KONFIGURATION
# ============================================================

VERSION = "0.1.0"

BTC_FILE = Path(
    "data/BTC_USD_5m_polymarket_period.csv"
)

WINDOW = 30
THRESHOLD = 26

LOOKBACKS = [2, 3, 5, 10]

HORIZONS = {
    "5m": 1,
    "10m": 2,
    "15m": 3,
    "30m": 6,
    "60m": 12,
    "2h": 24,
    "4h": 48,
}

TRADING_FEE = 0.001
SLIPPAGE = 0.0005


# ============================================================
# HILFSFUNKTIONEN
# ============================================================

def timestamp_to_datetime(timestamp):
    return datetime.fromtimestamp(
        int(timestamp),
        tz=timezone.utc
    )


def print_header():
    print()
    print("=" * 90)
    print("30-KERZEN BTC BOT")
    print("POLYMARKET FORWARD BTC ANALYSIS")
    print("=" * 90)

    print(f"Version:              {VERSION}")
    print(f"BTC Datei:            {BTC_FILE}")
    print(f"Fenster:              {WINDOW}")
    print(f"Schwelle:             {THRESHOLD}/{WINDOW}")

    print()
    print("LOOKBACKS")
    print("-" * 90)

    for lookback in LOOKBACKS:
        print(
            f"Close > Close {lookback}"
        )

    print()
    print("FORWARD HORIZONTE")
    print("-" * 90)

    for name, bars in HORIZONS.items():
        print(
            f"{name:6} = {bars:2} BTC-5m-Kerzen"
        )

    print()
    print("KOSTEN")
    print("-" * 90)
    print(
        f"Trading Fee:          {TRADING_FEE:.2%}"
    )
    print(
        f"Slippage:             {SLIPPAGE:.2%}"
    )

    print()
    print("=" * 90)


# ============================================================
# BTC LADEN
# ============================================================

def load_btc():

    print()
    print("BTC-DATEN LADEN")
    print("-" * 90)

    if not BTC_FILE.exists():

        print(
            f"FEHLER: {BTC_FILE} nicht gefunden."
        )

        return []

    rows = []

    with BTC_FILE.open(
        "r",
        encoding="utf-8",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        required = {
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

        if not required.issubset(
            reader.fieldnames or set()
        ):

            print(
                "FEHLER: Erwartete BTC-Spalten fehlen."
            )

            print(
                "Gefunden:",
                reader.fieldnames
            )

            return []

        for row in reader:

            try:

                timestamp = int(
                    float(
                        row["timestamp"]
                    )
                )

                # Millisekunden erkennen.
                if timestamp > 10_000_000_000:
                    timestamp //= 1000

                rows.append(
                    {
                        "timestamp": timestamp,
                        "open": float(
                            row["open"]
                        ),
                        "high": float(
                            row["high"]
                        ),
                        "low": float(
                            row["low"]
                        ),
                        "close": float(
                            row["close"]
                        ),
                        "volume": float(
                            row["volume"]
                        ),
                    }
                )

            except (
                ValueError,
                TypeError
            ):
                continue

    rows.sort(
        key=lambda x: x["timestamp"]
    )

    print(
        f"BTC Kerzen:      {len(rows):,}"
    )

    if rows:

        print(
            "BTC Zeitraum:    "
            f"{timestamp_to_datetime(rows[0]['timestamp'])}"
            " → "
            f"{timestamp_to_datetime(rows[-1]['timestamp'])}"
        )

    return rows


# ============================================================
# BTC INDEX
# ============================================================

def build_btc_index(btc_rows):

    return {
        row["timestamp"]: row
        for row in btc_rows
    }


# ============================================================
# SIGNAL-BERECHNUNG
# ============================================================

def calculate_signal_count(
    candles,
    lookback
):
    """
    candles enthält:

    LOOKBACK Vorgängerkerzen
    +
    30 Signalkerzen.

    Es werden exakt 30 Vergleiche durchgeführt.
    """

    expected_length = (
        WINDOW + lookback
    )

    if len(candles) != expected_length:
        return None

    count = 0

    for i in range(
        lookback,
        expected_length
    ):

        if (
            candles[i]["close"]
            >
            candles[
                i - lookback
            ]["close"]
        ):

            count += 1

    return count


# ============================================================
# SIGNAL-SERIE
# ============================================================

def find_signals(
    btc_rows,
    btc_index,
    lookback
):

    """
    Sucht alle Zeitpunkte, an denen
    das 30-Kerzen-Fenster >= 26/30 erreicht.

    Wichtig:

    Wir erfassen jeden Zeitpunkt,
    an dem das Signal aktiv ist.

    Später können wir zusätzlich
    "nur erstes Signal einer Serie"
    untersuchen.
    """

    signals = []

    max_lookback = max(
        LOOKBACKS
    )

    # Wir benötigen genügend Historie
    # für Lookback und Forward-Test.

    for index in range(
        max_lookback + WINDOW,
        len(btc_rows)
    ):

        start_candle_index = (
            index - WINDOW
        )

        signal_start_ts = btc_rows[
            start_candle_index
        ]["timestamp"]

        signal_end_ts = btc_rows[
            index - 1
        ]["timestamp"]

        candles_start = (
            index
            - WINDOW
            - lookback
        )

        candles_end = index

        candles = btc_rows[
            candles_start:candles_end
        ]

        if len(candles) != (
            WINDOW + lookback
        ):
            continue

        signal_count = calculate_signal_count(
            candles,
            lookback
        )

        if signal_count is None:
            continue

        if signal_count < THRESHOLD:
            continue

        # Der Forward-Test startet
        # nach Abschluss der letzten
        # Signalkerze.

        entry_index = index

        if entry_index >= len(
            btc_rows
        ):
            continue

        entry_candle = btc_rows[
            entry_index
        ]

        signals.append(
            {
                "lookback": lookback,
                "signal_start_ts":
                    signal_start_ts,
                "signal_end_ts":
                    signal_end_ts,
                "signal_count":
                    signal_count,
                "entry_index":
                    entry_index,
                "entry_ts":
                    entry_candle["timestamp"],
                "entry_open":
                    entry_candle["open"],
            }
        )

    return signals


# ============================================================
# FORWARD TRADE
# ============================================================

def calculate_forward_return(
    btc_rows,
    signal,
    horizon_bars
):

    entry_index = signal[
        "entry_index"
    ]

    exit_index = (
        entry_index
        + horizon_bars
    )

    if exit_index >= len(
        btc_rows
    ):
        return None

    entry_price = (
        btc_rows[
            entry_index
        ]["open"]
    )

    exit_price = (
        btc_rows[
            exit_index
        ]["close"]
    )

    if entry_price <= 0:
        return None

    gross_return = (
        exit_price
        / entry_price
        - 1.0
    )

    # Kosten:
    #
    # Einstieg:
    # Fee + Slippage
    #
    # Ausstieg:
    # Fee + Slippage
    #
    # Insgesamt:
    # 2 * (Fee + Slippage)

    total_cost = 2.0 * (
        TRADING_FEE
        + SLIPPAGE
    )

    net_return = (
        gross_return
        - total_cost
    )

    return {
        "entry_price":
            entry_price,

        "exit_price":
            exit_price,

        "gross_return":
            gross_return,

        "net_return":
            net_return,
    }


# ============================================================
# STATISTIK
# ============================================================

def calculate_statistics(
    trades
):

    if not trades:
        return None

    gross_returns = [
        t["gross_return"]
        for t in trades
    ]

    net_returns = [
        t["net_return"]
        for t in trades
    ]

    positive_gross = [
        r
        for r in gross_returns
        if r > 0
    ]

    positive_net = [
        r
        for r in net_returns
        if r > 0
    ]

    negative_net = [
        r
        for r in net_returns
        if r < 0
    ]

    gross_average = (
        sum(gross_returns)
        / len(gross_returns)
    )

    net_average = (
        sum(net_returns)
        / len(net_returns)
    )

    net_median = median(
        net_returns
    )

    winrate = (
        len(positive_net)
        / len(net_returns)
    )

    if negative_net:

        gross_profit = sum(
            r
            for r in net_returns
            if r > 0
        )

        gross_loss = abs(
            sum(
                r
                for r in net_returns
                if r < 0
            )
        )

        if gross_loss > 0:
            profit_factor = (
                gross_profit
                / gross_loss
            )
        else:
            profit_factor = float(
                "inf"
            )

    else:

        profit_factor = float(
            "inf"
        )

    return {
        "count":
            len(trades),

        "gross_average":
            gross_average,

        "net_average":
            net_average,

        "net_median":
            net_median,

        "winrate":
            winrate,

        "best":
            max(net_returns),

        "worst":
            min(net_returns),

        "profit_factor":
            profit_factor,
    }


# ============================================================
# ANALYSE EINER REGEL
# ============================================================

def analyze_lookback(
    btc_rows,
    btc_index,
    lookback
):

    print()
    print("=" * 90)
    print(
        f"CLOSE > CLOSE {lookback}"
    )
    print("=" * 90)

    signals = find_signals(
        btc_rows,
        btc_index,
        lookback
    )

    print()
    print(
        f"26/30-Signale: "
        f"{len(signals):,}"
    )

    if not signals:

        print(
            "Keine Signale."
        )

        return

    print()
    print(
        "FORWARD-ERGEBNISSE"
    )
    print("-" * 90)

    all_results = {}

    for horizon_name, horizon_bars in HORIZONS.items():

        trades = []

        for signal in signals:

            result = calculate_forward_return(
                btc_rows,
                signal,
                horizon_bars
            )

            if result is None:
                continue

            trades.append(result)

        stats = calculate_statistics(
            trades
        )

        all_results[
            horizon_name
        ] = stats

        if stats is None:

            print(
                f"{horizon_name:6} "
                "keine auswertbaren Trades"
            )

            continue

        pf = stats[
            "profit_factor"
        ]

        if pf == float("inf"):
            pf_text = "∞"
        else:
            pf_text = f"{pf:.2f}"

        print(
            f"{horizon_name:6} | "
            f"N={stats['count']:4d} | "
            f"Ø brutto="
            f"{stats['gross_average']:+.3%} | "
            f"Ø netto="
            f"{stats['net_average']:+.3%} | "
            f"Median="
            f"{stats['net_median']:+.3%} | "
            f"Winrate="
            f"{stats['winrate']:.2%} | "
            f"Best="
            f"{stats['best']:+.3%} | "
            f"Worst="
            f"{stats['worst']:+.3%} | "
            f"PF="
            f"{pf_text}"
        )

    # ========================================================
    # DETAIL DER SIGNALZEITEN
    # ========================================================

    print()
    print(
        "SIGNALDETAILS – ERSTE 20"
    )
    print("-" * 90)

    for signal in signals[:20]:

        dt = timestamp_to_datetime(
            signal["entry_ts"]
        )

        print(
            f"{dt} | "
            f"Signal="
            f"{signal['signal_count']}/30 | "
            f"Entry="
            f"${signal['entry_open']:,.2f}"
        )

    return all_results


# ============================================================
# GESAMTANALYSE
# ============================================================

def analyze():

    btc_rows = load_btc()

    if not btc_rows:
        return

    btc_index = build_btc_index(
        btc_rows
    )

    print()
    print("=" * 90)
    print(
        "26/30 FORWARD-TEST"
    )
    print("=" * 90)

    print()
    print(
        "Interpretation:"
    )

    print(
        "Ein Signal entsteht, wenn "
        "mindestens 26 von 30 Vergleichen "
        "positiv sind."
    )

    print(
        "Der Einstieg erfolgt am Open "
        "der nächsten BTC-5m-Kerze."
    )

    print(
        "Der Ausstieg erfolgt nach dem "
        "jeweiligen Forward-Horizont "
        "zum Close."
    )

    print(
        "Netto berücksichtigt "
        "Gebühr + Slippage beim Einstieg "
        "und beim Ausstieg."
    )

    results = {}

    for lookback in LOOKBACKS:

        result = analyze_lookback(
            btc_rows,
            btc_index,
            lookback
        )

        results[
            lookback
        ] = result

    # ========================================================
    # VERGLEICHSTABELLE
    # ========================================================

    print()
    print()
    print("=" * 90)
    print(
        "GESAMTÜBERSICHT"
    )
    print("=" * 90)

    print()

    header = (
        f"{'Regel':18}"
        f"{'N':>8}"
        f"{'5m':>10}"
        f"{'15m':>10}"
        f"{'30m':>10}"
        f"{'60m':>10}"
        f"{'2h':>10}"
        f"{'4h':>10}"
    )

    print(header)
    print("-" * 90)

    for lookback in LOOKBACKS:

        result = results.get(
            lookback
        )

        if not result:
            continue

        signal_count = 0

        # Anzahl Signale erneut bestimmen
        # für die Übersicht.

        signal_count = len(
            find_signals(
                btc_rows,
                btc_index,
                lookback
            )
        )

        values = []

        for horizon in [
            "5m",
            "15m",
            "30m",
            "60m",
            "2h",
            "4h",
        ]:

            stats = result.get(
                horizon
            )

            if stats is None:

                values.append(
                    "n/a"
                )

            else:

                values.append(
                    f"{stats['net_average']:+.2%}"
                )

        print(
            f"Close > Close {lookback:<3}"
            f"{signal_count:>8}"
            f"{values[0]:>10}"
            f"{values[1]:>10}"
            f"{values[2]:>10}"
            f"{values[3]:>10}"
            f"{values[4]:>10}"
            f"{values[5]:>10}"
        )

    # ========================================================
    # SICHERHEITSSTATUS
    # ========================================================

    print()
    print("=" * 90)
    print(
        "SICHERHEITSSTATUS"
    )
    print("=" * 90)

    print()
    print(
        "HISTORISCHE DATENANALYSE"
    )

    print(
        "PAPER TRADING ONLY"
    )

    print(
        "KEIN LIVE TRADING"
    )

    print(
        "KEINE API KEYS"
    )

    print(
        "KEIN WALLET"
    )

    print(
        "KEINE PRIVATEN SCHLÜSSEL"
    )

    print(
        "KEINE ECHTEN ORDERS"
    )

    print()


# ============================================================
# MAIN
# ============================================================

def main():

    print_header()
    analyze()


if __name__ == "__main__":
    main()
