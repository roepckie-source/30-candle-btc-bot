"""
30-Kerzen BTC Bot
Forward Return Analysis
Version 0.1.0

Zweck:
Historische Untersuchung der BTC-Rendite nach einem 26/30-Signal.

WICHTIG:
- Kein Trading
- Keine Orders
- Kein API-Key
- Kein Wallet
- Kein Kelly
- Keine Änderung der aktuellen Bot-Regel

Untersucht werden fünf mögliche Definitionen einer "positiven" Bewegung:

1. Close > Open
2. Close > Close der vorherigen Kerze
3. Close > Close vor 2 Kerzen
4. Close > Close vor 5 Kerzen
5. Close > Close vor 10 Kerzen

Für jedes 30-Kerzen-Fenster mit mindestens 26 positiven Kerzen
wird die zukünftige BTC-Rendite untersucht.

Horizonte:
5m, 10m, 15m, 30m, 60m, 2h, 4h

Es werden zwei Renditearten berechnet:

A) Signal Close -> Future Close
B) Next Open -> Future Close

B ist die realistischere Variante, weil das Signal erst nach
dem Abschluss der letzten Signal-Kerze bekannt ist.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean, median, pstdev
from typing import Callable

import config


CSV_FILE = config.CSV_FILE

WINDOW = 30
THRESHOLD = 26

HORIZONS = {
    "5m": 1,
    "10m": 2,
    "15m": 3,
    "30m": 6,
    "60m": 12,
    "2h": 24,
    "4h": 48,
}


@dataclass
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class SignalEvent:
    index: int
    timestamp: int
    positive_count: int
    signal_close: float


@dataclass
class ReturnStats:
    count: int
    average: float
    median: float
    stddev: float
    win_rate: float
    best: float
    worst: float
    cumulative: float


def parse_float(value: str) -> float:
    return float(value.strip().replace(",", "."))


def load_candles(filename: str) -> list[Candle]:
    candles: list[Candle] = []

    with open(filename, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)

        header = next(reader, None)

        if header is None:
            raise ValueError("CSV ist leer.")

        for row_number, row in enumerate(reader, start=2):
            if len(row) < 6:
                continue

            try:
                candles.append(
                    Candle(
                        timestamp=int(float(row[0])),
                        open=parse_float(row[1]),
                        high=parse_float(row[2]),
                        low=parse_float(row[3]),
                        close=parse_float(row[4]),
                        volume=parse_float(row[5]),
                    )
                )
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"Ungültige CSV-Zeile {row_number}: {row}"
                ) from exc

    candles.sort(key=lambda candle: candle.timestamp)

    if len(candles) < WINDOW:
        raise ValueError(
            f"Zu wenige Kerzen: {len(candles)}. "
            f"Mindestens {WINDOW} erforderlich."
        )

    return candles


def is_positive_close_open(
    candles: list[Candle],
    index: int,
) -> bool:
    return candles[index].close > candles[index].open


def is_positive_previous_close(
    candles: list[Candle],
    index: int,
) -> bool:
    if index < 1:
        return False

    return candles[index].close > candles[index - 1].close


def is_positive_2_back(
    candles: list[Candle],
    index: int,
) -> bool:
    if index < 2:
        return False

    return candles[index].close > candles[index - 2].close


def is_positive_5_back(
    candles: list[Candle],
    index: int,
) -> bool:
    if index < 5:
        return False

    return candles[index].close > candles[index - 5].close


def is_positive_10_back(
    candles: list[Candle],
    index: int,
) -> bool:
    if index < 10:
        return False

    return candles[index].close > candles[index - 10].close


DEFINITIONS: list[tuple[str, Callable[[list[Candle], int], bool]]] = [
    (
        "1. Close > Open",
        is_positive_close_open,
    ),
    (
        "2. Close > Previous Close",
        is_positive_previous_close,
    ),
    (
        "3. Close > Close 2 Back",
        is_positive_2_back,
    ),
    (
        "4. Close > Close 5 Back",
        is_positive_5_back,
    ),
    (
        "5. Close > Close 10 Back",
        is_positive_10_back,
    ),
]


def find_signal_events(
    candles: list[Candle],
    positive_rule: Callable[[list[Candle], int], bool],
) -> list[SignalEvent]:

    events: list[SignalEvent] = []

    start_index = max(WINDOW - 1, 10)

    for index in range(start_index, len(candles)):
        window_start = index - WINDOW + 1

        positive_count = 0

        for candle_index in range(window_start, index + 1):
            if positive_rule(candles, candle_index):
                positive_count += 1

        if positive_count >= THRESHOLD:
            events.append(
                SignalEvent(
                    index=index,
                    timestamp=candles[index].timestamp,
                    positive_count=positive_count,
                    signal_close=candles[index].close,
                )
            )

    return events


def percentage_return(
    entry_price: float,
    exit_price: float,
) -> float:
    if entry_price <= 0:
        raise ValueError("Entry-Preis muss > 0 sein.")

    return (exit_price / entry_price - 1.0) * 100.0


def calculate_stats(values: list[float]) -> ReturnStats | None:
    if not values:
        return None

    wins = sum(1 for value in values if value > 0)

    cumulative_factor = 1.0

    for value in values:
        cumulative_factor *= 1.0 + value / 100.0

    cumulative = (cumulative_factor - 1.0) * 100.0

    return ReturnStats(
        count=len(values),
        average=mean(values),
        median=median(values),
        stddev=pstdev(values) if len(values) > 1 else 0.0,
        win_rate=(wins / len(values)) * 100.0,
        best=max(values),
        worst=min(values),
        cumulative=cumulative,
    )


def calculate_forward_returns(
    candles: list[Candle],
    events: list[SignalEvent],
) -> dict[str, dict[str, list[float]]]:

    results: dict[str, dict[str, list[float]]] = {
        horizon: {
            "signal_close": [],
            "next_open": [],
        }
        for horizon in HORIZONS
    }

    for event in events:

        signal_index = event.index

        next_open_index = signal_index + 1

        if next_open_index >= len(candles):
            continue

        next_open = candles[next_open_index].open

        for horizon_name, horizon_candles in HORIZONS.items():

            future_index = signal_index + horizon_candles

            if future_index >= len(candles):
                continue

            future_close = candles[future_index].close

            signal_close_return = percentage_return(
                event.signal_close,
                future_close,
            )

            next_open_return = percentage_return(
                next_open,
                future_close,
            )

            results[horizon_name]["signal_close"].append(
                signal_close_return
            )

            results[horizon_name]["next_open"].append(
                next_open_return
            )

    return results


def format_timestamp(timestamp: int) -> str:
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)

    return dt.strftime("%Y-%m-%d %H:%M UTC")


def print_stats(
    horizon: str,
    entry_type: str,
    values: list[float],
) -> None:

    stats = calculate_stats(values)

    if stats is None:
        print(
            f"{horizon:>4} | "
            f"{entry_type:<20} | "
            f"keine Daten"
        )
        return

    print(
        f"{horizon:>4} | "
        f"{entry_type:<20} | "
        f"N={stats.count:<5} | "
        f"Ø={stats.average:+7.3f}% | "
        f"Median={stats.median:+7.3f}% | "
        f"WR={stats.win_rate:6.2f}% | "
        f"Best={stats.best:+7.3f}% | "
        f"Worst={stats.worst:+7.3f}% | "
        f"Cum={stats.cumulative:+8.3f}%"
    )


def print_signal_summary(
    candles: list[Candle],
    events: list[SignalEvent],
) -> None:

    print()
    print("=" * 100)
    print("SIGNAL-ZUSAMMENFASSUNG")
    print("=" * 100)

    print(f"Signale insgesamt:     {len(events)}")

    if not events:
        print("Keine 26/30-Signale gefunden.")
        return

    counts = [event.positive_count for event in events]

    print(f"Minimum:               {min(counts)}/30")
    print(f"Maximum:               {max(counts)}/30")
    print(f"Durchschnitt:          {mean(counts):.2f}/30")
    print(f"Median:                {median(counts):.2f}/30")

    print()
    print("ERSTES SIGNAL")
    print("-" * 100)

    first = events[0]

    print(
        f"{format_timestamp(first.timestamp)} | "
        f"{first.positive_count}/30 | "
        f"BTC ${first.signal_close:,.2f}"
    )

    print()
    print("LETZTES SIGNAL")
    print("-" * 100)

    last = events[-1]

    print(
        f"{format_timestamp(last.timestamp)} | "
        f"{last.positive_count}/30 | "
        f"BTC ${last.signal_close:,.2f}"
    )

    print()
    print("TOP 10 SIGNAL-FENSTER")
    print("-" * 100)

    top_events = sorted(
        events,
        key=lambda event: (
            event.positive_count,
            event.timestamp,
        ),
        reverse=True,
    )[:10]

    for number, event in enumerate(top_events, start=1):
        print(
            f"{number:2d}. "
            f"{event.positive_count:2d}/30 | "
            f"{format_timestamp(event.timestamp)} | "
            f"${event.signal_close:,.2f}"
        )


def print_forward_analysis(
    results: dict[str, dict[str, list[float]]],
) -> None:

    print()
    print("=" * 100)
    print("FORWARD-RETURN-ANALYSE")
    print("=" * 100)

    print()
    print(
        "Signal Close -> Future Close:"
    )

    print("-" * 100)

    for horizon in HORIZONS:
        print_stats(
            horizon,
            "Signal Close",
            results[horizon]["signal_close"],
        )

    print()
    print(
        "Next Open -> Future Close:"
    )

    print("-" * 100)

    for horizon in HORIZONS:
        print_stats(
            horizon,
            "Next Open",
            results[horizon]["next_open"],
        )


def print_best_horizons(
    results: dict[str, dict[str, list[float]]],
) -> None:

    print()
    print("=" * 100)
    print("HORIZONT-ÜBERSICHT")
    print("=" * 100)

    rows = []

    for horizon in HORIZONS:
        values = results[horizon]["next_open"]

        stats = calculate_stats(values)

        if stats is None:
            continue

        rows.append(
            (
                horizon,
                stats.average,
                stats.median,
                stats.win_rate,
                stats.best,
                stats.worst,
            )
        )

    if not rows:
        print("Keine auswertbaren Forward Returns.")
        return

    print(
        f"{'Horizont':>8} | "
        f"{'Ø Rendite':>10} | "
        f"{'Median':>10} | "
        f"{'Winrate':>9} | "
        f"{'Best':>10} | "
        f"{'Worst':>10}"
    )

    print("-" * 75)

    for row in rows:
        print(
            f"{row[0]:>8} | "
            f"{row[1]:+9.3f}% | "
            f"{row[2]:+9.3f}% | "
            f"{row[3]:8.2f}% | "
            f"{row[4]:+9.3f}% | "
            f"{row[5]:+9.3f}%"
        )


def analyze_definition(
    candles: list[Candle],
    name: str,
    rule: Callable[[list[Candle], int], bool],
) -> None:

    print()
    print()
    print("#" * 100)
    print(name)
    print("#" * 100)

    print()
    print("Suche 26/30-Signale...")

    events = find_signal_events(
        candles,
        rule,
    )

    print_signal_summary(
        candles,
        events,
    )

    if not events:
        print()
        print("Keine Forward-Analyse möglich.")
        return

    results = calculate_forward_returns(
        candles,
        events,
    )

    print_forward_analysis(
        results,
    )

    print_best_horizons(
        results,
    )


def self_test() -> None:

    print("=" * 100)
    print("FORWARD ANALYSIS SELF TEST")
    print("=" * 100)

    candles: list[Candle] = []

    base_timestamp = 1_700_000_000

    for index in range(100):

        price = 100.0 + index

        candles.append(
            Candle(
                timestamp=base_timestamp + index * 300,
                open=price,
                high=price + 1,
                low=price - 1,
                close=price + 0.5,
                volume=1.0,
            )
        )

    events = find_signal_events(
        candles,
        is_positive_close_open,
    )

    assert len(events) > 0

    results = calculate_forward_returns(
        candles,
        events,
    )

    assert results["5m"]["signal_close"]
    assert results["60m"]["signal_close"]

    print("PASS: 26/30-Signale erkannt")
    print("PASS: Forward Returns berechnet")
    print("PASS: 5m bis 4h Horizonte vorhanden")
    print()
    print("BESTANDEN: Forward Analysis Self Test")
    print("=" * 100)


def main() -> None:

    self_test()

    print()
    print()
    print("=" * 100)
    print("30-KERZEN BTC BOT - FORWARD RETURN ANALYSE")
    print("=" * 100)

    print()
    print("WICHTIG")
    print("-" * 100)
    print("Dies ist ausschließlich eine historische Analyse.")
    print("Es werden KEINE Trades ausgeführt.")
    print("Keine API-Keys.")
    print("Kein Wallet.")
    print("Keine echten Orders.")
    print("Kelly-Sizing ist NICHT aktiv.")
    print("Die aktuelle Bot-Regel wird NICHT verändert.")

    print()
    print("Lade historische BTC-5m-Daten...")

    candles = load_candles(
        CSV_FILE
    )

    print(f"Geladene Kerzen: {len(candles)}")

    first_timestamp = candles[0].timestamp
    last_timestamp = candles[-1].timestamp

    print(
        f"Zeitraum: "
        f"{format_timestamp(first_timestamp)}"
        f" → "
        f"{format_timestamp(last_timestamp)}"
    )

    print()
    print(
        "Schwelle: "
        f"{THRESHOLD}/{WINDOW}"
    )

    print(
        "Horizonte: "
        + ", ".join(HORIZONS.keys())
    )

    for name, rule in DEFINITIONS:

        analyze_definition(
            candles,
            name,
            rule,
        )

    print()
    print()
    print("=" * 100)
    print("FORWARD ANALYSE ABGESCHLOSSEN")
    print("=" * 100)
    print()
    print("Keine Handelsstrategie wurde verändert.")
    print("Keine echten Trades wurden ausgeführt.")
    print("=" * 100)


if __name__ == "__main__":
    main()
