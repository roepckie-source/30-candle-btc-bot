"""
30-Kerzen BTC Bot
Historische Analyse
Version 0.1.1

ZWECK:
Analyse der vorhandenen BTC/USD 5m-Daten.

Es wird NICHT gehandelt.

Untersucht werden:
1. Close > Open
2. Close > vorheriger Close
3. Close > Close vor 2 Kerzen
4. Close > Close vor 5 Kerzen
5. Close > Close vor 10 Kerzen

Für jede Definition wird untersucht:
- Verteilung der positiven Kerzen innerhalb von 30er-Fenstern
- Minimum
- Maximum
- Durchschnitt
- Median
- Standardabweichung
- Anzahl der Fenster >= 26/30
- Schwellen von 20/30 bis 30/30

WICHTIG:
Diese Analyse verändert die eigentliche Bot-Strategie NICHT.
"""

from __future__ import annotations

import csv
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import config


# ============================================================
# DATEN LADEN
# ============================================================

def load_candles() -> list[dict]:
    csv_path = Path(config.CSV_FILE)

    if not csv_path.exists():
        raise FileNotFoundError(
            f"CSV nicht gefunden: {csv_path}"
        )

    candles = []

    with csv_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:
            candles.append(
                {
                    "timestamp": int(float(row["timestamp"])),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                }
            )

    candles.sort(
        key=lambda candle: candle["timestamp"]
    )

    return candles


# ============================================================
# ZEIT
# ============================================================

def format_timestamp(timestamp: int) -> str:
    return datetime.fromtimestamp(
        timestamp,
        tz=timezone.utc,
    ).strftime(
        "%Y-%m-%d %H:%M UTC"
    )


# ============================================================
# DEFINITION 1
# ============================================================

def positive_open_close(
    candles: list[dict],
    index: int,
) -> bool:
    """
    Positiv, wenn Close > Open.
    """

    return (
        candles[index]["close"]
        > candles[index]["open"]
    )


# ============================================================
# DEFINITION 2
# ============================================================

def positive_close_vs_previous(
    candles: list[dict],
    index: int,
) -> bool:
    """
    Positiv, wenn Close > Close der vorherigen Kerze.
    """

    if index <= 0:
        return False

    return (
        candles[index]["close"]
        > candles[index - 1]["close"]
    )


# ============================================================
# DEFINITION 3
# ============================================================

def positive_close_vs_two_back(
    candles: list[dict],
    index: int,
) -> bool:
    """
    Positiv, wenn Close > Close vor 2 Kerzen.
    """

    if index < 2:
        return False

    return (
        candles[index]["close"]
        > candles[index - 2]["close"]
    )


# ============================================================
# DEFINITION 4
# ============================================================

def positive_5_candle_trend(
    candles: list[dict],
    index: int,
) -> bool:
    """
    Positiv, wenn Close > Close vor 5 Kerzen.
    """

    if index < 5:
        return False

    return (
        candles[index]["close"]
        > candles[index - 5]["close"]
    )


# ============================================================
# DEFINITION 5
# ============================================================

def positive_10_candle_trend(
    candles: list[dict],
    index: int,
) -> bool:
    """
    Positiv, wenn Close > Close vor 10 Kerzen.
    """

    if index < 10:
        return False

    return (
        candles[index]["close"]
        > candles[index - 10]["close"]
    )


# ============================================================
# ANALYSE
# ============================================================

def analyze_definition(
    candles: list[dict],
    name: str,
    positive_function: Callable[
        [list[dict], int],
        bool,
    ],
) -> dict:

    positive_counts = []

    window_details = []

    minimum = None
    maximum = None

    maximum_index = None
    minimum_index = None

    for index in range(
        config.CANDLE_WINDOW - 1,
        len(candles),
    ):

        window_start = (
            index
            - config.CANDLE_WINDOW
            + 1
        )

        positive = 0

        for candle_index in range(
            window_start,
            index + 1,
        ):

            if positive_function(
                candles,
                candle_index,
            ):
                positive += 1

        positive_counts.append(
            positive
        )

        if (
            maximum is None
            or positive > maximum
        ):
            maximum = positive
            maximum_index = index

        if (
            minimum is None
            or positive < minimum
        ):
            minimum = positive
            minimum_index = index

        window_details.append(
            {
                "index": index,
                "positive": positive,
            }
        )

    average = statistics.mean(
        positive_counts
    )

    median = statistics.median(
        positive_counts
    )

    stdev = (
        statistics.stdev(
            positive_counts
        )
        if len(positive_counts) > 1
        else 0.0
    )

    distribution = Counter(
        positive_counts
    )

    active_windows = [
        item
        for item in window_details
        if item["positive"]
        >= config.MIN_POSITIVE_CANDLES
    ]

    return {
        "name": name,
        "counts": positive_counts,
        "distribution": distribution,
        "minimum": minimum,
        "maximum": maximum,
        "average": average,
        "median": median,
        "stdev": stdev,
        "maximum_index": maximum_index,
        "minimum_index": minimum_index,
        "active_windows": active_windows,
        "total_windows": len(
            positive_counts
        ),
    }


# ============================================================
# VERTEILUNG
# ============================================================

def print_distribution(
    result: dict,
) -> None:

    print()
    print(
        f"VERTEILUNG: {result['name']}"
    )
    print("-" * 70)

    distribution = result["distribution"]

    for count in range(31):

        number = distribution.get(
            count,
            0,
        )

        if number > 0:

            percentage = (
                number
                / result["total_windows"]
                * 100.0
            )

            print(
                f"{count:2d}/30  "
                f"{number:6d} Fenster  "
                f"({percentage:6.2f} %)"
            )


# ============================================================
# ERGEBNIS
# ============================================================

def print_result(
    result: dict,
    candles: list[dict],
) -> None:

    print()
    print("=" * 70)
    print(result["name"])
    print("=" * 70)

    print(
        f"Rollierende Fenster:   "
        f"{result['total_windows']}"
    )

    print(
        f"Minimum:               "
        f"{result['minimum']}/30"
    )

    print(
        f"Maximum:               "
        f"{result['maximum']}/30"
    )

    print(
        f"Durchschnitt:          "
        f"{result['average']:.2f}/30"
    )

    print(
        f"Median:                "
        f"{result['median']:.2f}/30"
    )

    print(
        f"Standardabweichung:    "
        f"{result['stdev']:.2f}"
    )

    print(
        f">= {config.MIN_POSITIVE_CANDLES}/30: "
        f"{len(result['active_windows'])}"
    )

    if result["maximum_index"] is not None:

        maximum_candle = candles[
            result["maximum_index"]
        ]

        print()
        print("MAXIMUM")

        print(
            f"Zeitpunkt:             "
            f"{format_timestamp(maximum_candle['timestamp'])}"
        )

        print(
            f"Positive Kerzen:       "
            f"{result['maximum']}/30"
        )

        print(
            f"BTC Close:             "
            f"${maximum_candle['close']:,.2f}"
        )

    print_distribution(result)


# ============================================================
# TOP-FENSTER
# ============================================================

def print_top_windows(
    result: dict,
    candles: list[dict],
    count: int = 10,
) -> None:

    print()
    print("=" * 70)
    print(
        f"TOP {count} FENSTER - "
        f"{result['name']}"
    )
    print("=" * 70)

    sorted_windows = sorted(
        (
            {
                "index": (
                    config.CANDLE_WINDOW
                    - 1
                    + i
                ),
                "positive": value,
            }
            for i, value in enumerate(
                result["counts"]
            )
        ),
        key=lambda item: item["positive"],
        reverse=True,
    )

    for rank, item in enumerate(
        sorted_windows[:count],
        start=1,
    ):

        candle = candles[
            item["index"]
        ]

        print(
            f"{rank:2d}. "
            f"{item['positive']:2d}/30"
            f" | "
            f"{format_timestamp(candle['timestamp'])}"
            f" | "
            f"Close "
            f"${candle['close']:,.2f}"
        )


# ============================================================
# SCHWELLENANALYSE
# ============================================================

def print_threshold_analysis(
    result: dict,
) -> None:

    print()
    print("=" * 70)
    print(
        f"SCHWELLENANALYSE - "
        f"{result['name']}"
    )
    print("=" * 70)

    for threshold in range(
        20,
        31,
    ):

        windows = sum(
            number
            for count, number
            in result["distribution"].items()
            if count >= threshold
        )

        percentage = (
            windows
            / result["total_windows"]
            * 100.0
        )

        print(
            f">= {threshold:2d}/30 : "
            f"{windows:6d} Fenster "
            f"({percentage:6.2f} %)"
        )

    print("=" * 70)


# ============================================================
# VERGLEICH
# ============================================================

def print_comparison(
    results: list[dict],
) -> None:

    print()
    print("=" * 70)
    print("VERGLEICH DER DEFINITIONEN")
    print("=" * 70)

    print(
        f"{'Definition':35s} "
        f"{'Min':>6s} "
        f"{'Max':>6s} "
        f"{'Ø':>8s} "
        f"{'>=26':>8s}"
    )

    print("-" * 70)

    for result in results:

        print(
            f"{result['name'][:35]:35s} "
            f"{result['minimum']:>5d}/30 "
            f"{result['maximum']:>5d}/30 "
            f"{result['average']:>7.2f} "
            f"{len(result['active_windows']):>8d}"
        )

    print("=" * 70)


# ============================================================
# SELF TEST
# ============================================================

def self_test() -> None:

    print("=" * 70)
    print("ANALYSE SELBSTTEST")
    print("=" * 70)

    test_candles = []

    # Steigender Kurs:
    # 100, 101, 102, 103 ...
    #
    # Dadurch funktionieren alle Vergleichstests
    # eindeutig.

    for index in range(40):

        open_price = 100.0 + index
        close_price = 101.0 + index

        test_candles.append(
            {
                "timestamp": index * 300,
                "open": open_price,
                "high": close_price,
                "low": open_price,
                "close": close_price,
                "volume": 1.0,
            }
        )

    # --------------------------------------------------------
    # Close > Open
    # --------------------------------------------------------

    for index in range(40):

        assert positive_open_close(
            test_candles,
            index,
        )

    print(
        "PASS: Close > Open"
    )

    # --------------------------------------------------------
    # Close > Previous Close
    # --------------------------------------------------------

    assert (
        positive_close_vs_previous(
            test_candles,
            0,
        )
        is False
    )

    for index in range(1, 40):

        assert positive_close_vs_previous(
            test_candles,
            index,
        )

    print(
        "PASS: Close > vorheriger Close"
    )

    # --------------------------------------------------------
    # Close > Close vor 2 Kerzen
    # --------------------------------------------------------

    assert (
        positive_close_vs_two_back(
            test_candles,
            0,
        )
        is False
    )

    assert (
        positive_close_vs_two_back(
            test_candles,
            1,
        )
        is False
    )

    for index in range(2, 40):

        assert positive_close_vs_two_back(
            test_candles,
            index,
        )

    print(
        "PASS: Close > Close vor 2 Kerzen"
    )

    # --------------------------------------------------------
    # 5-Kerzen-Trend
    # --------------------------------------------------------

    for index in range(5):

        assert (
            positive_5_candle_trend(
                test_candles,
                index,
            )
            is False
        )

    for index in range(5, 40):

        assert positive_5_candle_trend(
            test_candles,
            index,
        )

    print(
        "PASS: Close > Close vor 5 Kerzen"
    )

    # --------------------------------------------------------
    # 10-Kerzen-Trend
    # --------------------------------------------------------

    for index in range(10):

        assert (
            positive_10_candle_trend(
                test_candles,
                index,
            )
            is False
        )

    for index in range(10, 40):

        assert positive_10_candle_trend(
            test_candles,
            index,
        )

    print(
        "PASS: Close > Close vor 10 Kerzen"
    )

    print()
    print(
        "PASS: Analyse-Selbsttest"
    )

    print("=" * 70)


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print()
    print("=" * 70)
    print(
        "30-KERZEN BTC BOT - "
        "HISTORISCHE ANALYSE"
    )
    print("=" * 70)

    print()
    print("WICHTIG")
    print("-" * 70)

    print(
        "Dies ist ausschließlich "
        "eine historische Analyse."
    )

    print(
        "Es werden KEINE Trades ausgeführt."
    )

    print(
        "Die aktuelle Bot-Regel wird "
        "NICHT verändert."
    )

    print()
    print("Lade BTC-5m-Daten...")

    candles = load_candles()

    print(
        f"Geladene Kerzen: "
        f"{len(candles)}"
    )

    if len(candles) < config.CANDLE_WINDOW:
        raise ValueError(
            "Nicht genügend Kerzen vorhanden."
        )

    first = candles[0]
    last = candles[-1]

    print(
        f"Zeitraum: "
        f"{format_timestamp(first['timestamp'])}"
        f" → "
        f"{format_timestamp(last['timestamp'])}"
    )

    definitions = [
        (
            "1. Close > Open",
            positive_open_close,
        ),
        (
            "2. Close > vorheriger Close",
            positive_close_vs_previous,
        ),
        (
            "3. Close > Close vor 2 Kerzen",
            positive_close_vs_two_back,
        ),
        (
            "4. Close > Close vor 5 Kerzen",
            positive_5_candle_trend,
        ),
        (
            "5. Close > Close vor 10 Kerzen",
            positive_10_candle_trend,
        ),
    ]

    results = []

    for name, function in definitions:

        print()
        print(
            f"Analysiere: {name}"
        )

        result = analyze_definition(
            candles,
            name,
            function,
        )

        results.append(result)

        print_result(
            result,
            candles,
        )

        print_threshold_analysis(
            result,
        )

        print_top_windows(
            result,
            candles,
            count=10,
        )

    print_comparison(
        results
    )

    print()
    print("=" * 70)
    print("ANALYSE ABGESCHLOSSEN")
    print("=" * 70)

    print(
        "Die Analyse hat keine "
        "Trading-Regel geändert."
    )

    print(
        "26/30 bleibt weiterhin "
        "eine zu prüfende Annahme."
    )

    print("=" * 70)


if __name__ == "__main__":
    self_test()
    main()
