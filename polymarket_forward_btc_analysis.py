"""
30-Kerzen BTC Bot
Polymarket Forward BTC Analysis

Version 0.2.1

Test:
- BTC 5m
- 30-Kerzen-Fenster
- 26/30 Schwelle
- Lookbacks: 2, 3, 5, 10
- Forward-Horizonte bis 8 Stunden
- Einstieg: Open der nächsten BTC-5m-Kerze
- Ausstieg: Close nach Forward-Horizont
- Fee: 0.10% je Seite
- Slippage: 0.05% je Seite
- Nur historische Analyse
- Kein Live Trading
"""

import csv
import statistics
from pathlib import Path


# ============================================================
# CONFIG
# ============================================================

CSV_FILE = Path(
    "data/BTC_USD_5m_polymarket_period.csv"
)

WINDOW = 30
THRESHOLD = 26

LOOKBACKS = [2, 3, 5, 10]

# Anzahl BTC-5m-Kerzen
HORIZONS = {
    "5m": 1,
    "10m": 2,
    "15m": 3,
    "30m": 6,
    "60m": 12,
    "2h": 24,
    "4h": 48,
    "6h": 72,
    "8h": 96,
}

TRADING_FEE = 0.001
SLIPPAGE = 0.0005

# Einstieg + Ausstieg
TOTAL_COST_PER_TRADE = (
    2 * (TRADING_FEE + SLIPPAGE)
)


# ============================================================
# CSV LADEN
# ============================================================

def load_candles():

    if not CSV_FILE.exists():
        raise FileNotFoundError(
            f"BTC-Datei nicht gefunden: {CSV_FILE}"
        )

    candles = []

    with CSV_FILE.open(
        "r",
        encoding="utf-8",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            try:

                timestamp = row["timestamp"]

                open_price = float(
                    row["open"]
                )

                close_price = float(
                    row["close"]
                )

                candles.append(
                    {
                        "timestamp": timestamp,
                        "open": open_price,
                        "close": close_price,
                    }
                )

            except (
                KeyError,
                ValueError,
                TypeError
            ):
                continue

    candles.sort(
        key=lambda x: x["timestamp"]
    )

    return candles


# ============================================================
# 26/30 SIGNAL
# ============================================================

def positive_count(
    candles,
    end_index,
    lookback
):
    """
    Zählt exakt 30 Vergleiche.

    Vergleich:

        close[i] > close[i-lookback]

    Es werden genau 30 Vergleiche
    für das 30-Kerzen-Fenster durchgeführt.
    """

    start = end_index - WINDOW

    count = 0

    for i in range(
        start,
        end_index
    ):

        current_close = (
            candles[i]["close"]
        )

        previous_close = (
            candles[i - lookback]["close"]
        )

        if current_close > previous_close:
            count += 1

    return count


# ============================================================
# SIGNAL FINDEN
# ============================================================

def find_signals(
    candles,
    lookback
):
    """
    Sucht alle aktiven 26/30-Fenster.

    Wichtig:

    Diese Funktion betrachtet jedes aktive
    Fenster separat.

    Dadurch können mehrere Signale
    unmittelbar hintereinander entstehen.

    Dies ist eine Forward-Analyse und noch
    kein nicht-überlappender Portfolio-Backtest.
    """

    signals = []

    start_index = (
        WINDOW + lookback
    )

    for index in range(
        start_index,
        len(candles)
    ):

        count = positive_count(
            candles,
            index,
            lookback
        )

        if count >= THRESHOLD:

            # Einstieg am Open
            # der nächsten BTC-5m-Kerze
            entry_index = index

            if entry_index >= len(candles):
                continue

            signals.append(
                {
                    "signal_index": index,
                    "entry_index": entry_index,
                    "timestamp": candles[
                        index - 1
                    ]["timestamp"],
                    "signal_count": count,
                    "entry_price": candles[
                        entry_index
                    ]["open"],
                }
            )

    return signals


# ============================================================
# FORWARD RETURN
# ============================================================

def calculate_forward_return(
    candles,
    signal,
    horizon_bars
):

    entry_index = signal[
        "entry_index"
    ]

    exit_index = (
        entry_index
        + horizon_bars
        - 1
    )

    if exit_index >= len(candles):
        return None

    entry_price = candles[
        entry_index
    ]["open"]

    exit_price = candles[
        exit_index
    ]["close"]

    if entry_price <= 0:
        return None

    # Brutto-Return
    gross_return = (
        exit_price / entry_price
    ) - 1.0

    # Kosten:
    # 0.10% Fee + 0.05% Slippage
    # beim Einstieg
    #
    # 0.10% Fee + 0.05% Slippage
    # beim Ausstieg
    net_return = (
        gross_return
        - TOTAL_COST_PER_TRADE
    )

    return {
        "gross": gross_return,
        "net": net_return,
        "entry_price": entry_price,
        "exit_price": exit_price,
    }


# ============================================================
# STATISTIK
# ============================================================

def calculate_statistics(
    returns
):

    if not returns:
        return None

    # --------------------------------------------------------
    # Brutto
    # --------------------------------------------------------

    gross = [
        r["gross"]
        for r in returns
    ]

    # --------------------------------------------------------
    # Netto
    # --------------------------------------------------------

    net = [
        r["net"]
        for r in returns
    ]

    # --------------------------------------------------------
    # Gewinner
    # --------------------------------------------------------

    wins = [
        value
        for value in net
        if value > 0
    ]

    # --------------------------------------------------------
    # Verlierer
    # --------------------------------------------------------

    losses = [
        value
        for value in net
        if value < 0
    ]

    # --------------------------------------------------------
    # Winrate
    # --------------------------------------------------------

    winrate = (
        len(wins) / len(net)
        if net
        else 0.0
    )

    # --------------------------------------------------------
    # Profit Factor
    # --------------------------------------------------------

    positive_sum = sum(
        wins
    )

    negative_sum = abs(
        sum(losses)
    )

    if negative_sum > 0:

        profit_factor = (
            positive_sum
            / negative_sum
        )

    elif positive_sum > 0:

        profit_factor = float(
            "inf"
        )

    else:

        profit_factor = 0.0

    # --------------------------------------------------------
    # Ergebnis
    # --------------------------------------------------------

    return {
        "n": len(net),

        "avg_gross": statistics.mean(
            gross
        ),

        "avg_net": statistics.mean(
            net
        ),

        "median_net": statistics.median(
            net
        ),

        "winrate": winrate,

        "best": max(net),

        "worst": min(net),

        "profit_factor": profit_factor,
    }


# ============================================================
# FORWARD ANALYSE
# ============================================================

def analyze_rule(
    candles,
    lookback
):

    signals = find_signals(
        candles,
        lookback
    )

    print()
    print("=" * 90)
    print(
        f"CLOSE > CLOSE {lookback}"
    )
    print("=" * 90)

    print()

    print(
        f"26/30-Signale: {len(signals)}"
    )

    print()

    print(
        "FORWARD-ERGEBNISSE"
    )

    print("-" * 90)

    results = {}

    for (
        name,
        horizon_bars
    ) in HORIZONS.items():

        returns = []

        for signal in signals:

            result = (
                calculate_forward_return(
                    candles,
                    signal,
                    horizon_bars
                )
            )

            if result is not None:

                returns.append(
                    result
                )

        stats = calculate_statistics(
            returns
        )

        results[name] = stats

        if stats is None:

            print(
                f"{name:<5} | keine Daten"
            )

            continue

        pf = stats[
            "profit_factor"
        ]

        if pf == float("inf"):

            pf_text = "INF"

        else:

            pf_text = (
                f"{pf:.2f}"
            )

        print(
            f"{name:<5} | "
            f"N={stats['n']:>4} | "
            f"Ø brutto="
            f"{stats['avg_gross']:+.3%} | "
            f"Ø netto="
            f"{stats['avg_net']:+.3%} | "
            f"Median="
            f"{stats['median_net']:+.3%} | "
            f"Winrate="
            f"{stats['winrate']:.2%} | "
            f"Best="
            f"{stats['best']:+.3%} | "
            f"Worst="
            f"{stats['worst']:+.3%} | "
            f"PF="
            f"{pf_text}"
        )

    return (
        signals,
        results
    )


# ============================================================
# SIGNAL DETAILS
# ============================================================

def print_signal_details(
    candles,
    signals,
    limit=20
):

    print()

    print(
        "SIGNALDETAILS – ERSTE 20"
    )

    print("-" * 90)

    for signal in signals[:limit]:

        timestamp = (
            signal["timestamp"]
        )

        count = (
            signal["signal_count"]
        )

        entry = (
            signal["entry_price"]
        )

        print(
            f"{timestamp} | "
            f"Signal={count}/30 | "
            f"Entry=${entry:,.2f}"
        )


# ============================================================
# GESAMTÜBERSICHT
# ============================================================

def print_summary(
    all_results
):

    print()

    print(
        "=" * 120
    )

    print(
        "GESAMTÜBERSICHT"
    )

    print(
        "=" * 120
    )

    print()

    print(
        f"{'Regel':<25}"
        f"{'N':>6}"
        f"{'5m':>10}"
        f"{'15m':>10}"
        f"{'30m':>10}"
        f"{'60m':>10}"
        f"{'2h':>10}"
        f"{'4h':>10}"
        f"{'6h':>10}"
        f"{'8h':>10}"
    )

    print(
        "-" * 120
    )

    for (
        lookback,
        results
    ) in all_results.items():

        rule_name = (
            f"Close > Close {lookback}"
        )

        # ----------------------------------------------------
        # N
        # ----------------------------------------------------

        n = 0

        for stats in results.values():

            if stats is not None:

                n = stats["n"]

                break

        # ----------------------------------------------------
        # Horizonte
        # ----------------------------------------------------

        values = []

        for horizon in [
            "5m",
            "15m",
            "30m",
            "60m",
            "2h",
            "4h",
            "6h",
            "8h",
        ]:

            stats = results.get(
                horizon
            )

            if stats is None:

                values.append(
                    "n/a"
                )

            else:

                values.append(
                    f"{stats['avg_net']:+.2%}"
                )

        # ----------------------------------------------------
        # Ausgabe
        # ----------------------------------------------------

        print(
            f"{rule_name:<25}"
            f"{n:>6}"
            f"{values[0]:>10}"
            f"{values[1]:>10}"
            f"{values[2]:>10}"
            f"{values[3]:>10}"
            f"{values[4]:>10}"
            f"{values[5]:>10}"
            f"{values[6]:>10}"
            f"{values[7]:>10}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "=" * 90
    )

    print(
        "30-KERZEN BTC BOT"
    )

    print(
        "POLYMARKET FORWARD BTC ANALYSIS"
    )

    print(
        "=" * 90
    )

    print()

    print(
        "Version:              0.2.1"
    )

    print(
        f"BTC Datei:            "
        f"{CSV_FILE}"
    )

    print(
        f"Fenster:              "
        f"{WINDOW}"
    )

    print(
        f"Schwelle:             "
        f"{THRESHOLD}/30"
    )

    # --------------------------------------------------------
    # LOOKBACKS
    # --------------------------------------------------------

    print()

    print(
        "LOOKBACKS"
    )

    print(
        "-" * 90
    )

    for lookback in LOOKBACKS:

        print(
            f"Close > Close {lookback}"
        )

    # --------------------------------------------------------
    # FORWARD HORIZONTE
    # --------------------------------------------------------

    print()

    print(
        "FORWARD HORIZONTE"
    )

    print(
        "-" * 90
    )

    print(
        "5m     =  1 BTC-5m-Kerze"
    )

    print(
        "10m    =  2 BTC-5m-Kerzen"
    )

    print(
        "15m    =  3 BTC-5m-Kerzen"
    )

    print(
        "30m    =  6 BTC-5m-Kerzen"
    )

    print(
        "60m    = 12 BTC-5m-Kerzen"
    )

    print(
        "2h     = 24 BTC-5m-Kerzen"
    )

    print(
        "4h     = 48 BTC-5m-Kerzen"
    )

    print(
        "6h     = 72 BTC-5m-Kerzen"
    )

    print(
        "8h     = 96 BTC-5m-Kerzen"
    )

    # --------------------------------------------------------
    # KOSTEN
    # --------------------------------------------------------

    print()

    print(
        "KOSTEN"
    )

    print(
        "-" * 90
    )

    print(
        f"Trading Fee:          "
        f"{TRADING_FEE:.2%}"
    )

    print(
        f"Slippage:             "
        f"{SLIPPAGE:.2%}"
    )

    print(
        f"Gesamtkosten:         "
        f"{TOTAL_COST_PER_TRADE:.2%}"
    )

    print()

    print(
        "=" * 90
    )

    # --------------------------------------------------------
    # BTC LADEN
    # --------------------------------------------------------

    print()

    print(
        "BTC-DATEN LADEN"
    )

    print(
        "-" * 90
    )

    candles = load_candles()

    print(
        f"BTC Kerzen:      "
        f"{len(candles):,}"
    )

    if candles:

        print(
            f"BTC Zeitraum:    "
            f"{candles[0]['timestamp']} "
            f"→ "
            f"{candles[-1]['timestamp']}"
        )

    # --------------------------------------------------------
    # FORWARD TEST
    # --------------------------------------------------------

    print()

    print(
        "=" * 90
    )

    print(
        "26/30 FORWARD-TEST"
    )

    print(
        "=" * 90
    )

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
        "Netto berücksichtigt Gebühr + "
        "Slippage beim Einstieg und beim "
        "Ausstieg."
    )

    print(
        "6h = 72 Kerzen, "
        "8h = 96 Kerzen."
    )

    # --------------------------------------------------------
    # ALLE REGELN
    # --------------------------------------------------------

    all_results = {}

    for lookback in LOOKBACKS:

        (
            signals,
            results
        ) = analyze_rule(
            candles,
            lookback
        )

        print_signal_details(
            candles,
            signals
        )

        all_results[
            lookback
        ] = results

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print_summary(
        all_results
    )

    # --------------------------------------------------------
    # SECURITY
    # --------------------------------------------------------

    print()

    print(
        "=" * 90
    )

    print(
        "SICHERHEITSSTATUS"
    )

    print(
        "=" * 90
    )

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

    print(
        "=" * 90
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
