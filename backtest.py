"""
30-Kerzen BTC Bot
Historischer Backtest
Version 0.1.0

TESTREGEL:
- BTC/USD 5-Minuten-Kerzen
- Rollierendes 30-Kerzen-Fenster
- Positive Kerze = Close > Open
- Signal AKTIV ab 26/30 positiven Kerzen

BACKTEST:
Variante A:
    Einstieg nach Aktivierung
    Ausstieg nach genau 1 weiterer 5-Minuten-Kerze

Variante B:
    Einstieg bei INAKTIV -> AKTIV
    Position bleibt offen, solange das Signal aktiv ist
    Ausstieg, sobald das Signal unter 26/30 fällt

WICHTIG:
- Nur historischer Paper-Backtest
- Keine API Keys
- Keine echten Orders
- Kein Live Trading
- Kein Kelly-Sizing
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import config
from signals import evaluate_30_candles


# ============================================================
# DATENSTRUKTUREN
# ============================================================

@dataclass
class Trade:
    entry_time: datetime
    exit_time: datetime

    entry_price: float
    exit_price: float

    positive_candles: int

    gross_return: float
    net_return: float

    start_capital: float
    end_capital: float

    reason: str


# ============================================================
# HILFSFUNKTIONEN
# ============================================================

def timestamp_to_datetime(timestamp: int | float) -> datetime:
    """
    Coinbase-Timestamp in UTC-Datetime umwandeln.
    """
    return datetime.fromtimestamp(
        float(timestamp),
        tz=timezone.utc,
    )


def load_candles() -> list[dict]:
    """
    BTC 5m CSV laden.
    """

    csv_path = Path(config.CSV_FILE)

    if not csv_path.exists():
        raise FileNotFoundError(
            f"CSV nicht gefunden: {csv_path}\n"
            f"Bitte zuerst market_data.py ausführen."
        )

    candles: list[dict] = []

    with csv_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:

        reader = csv.DictReader(file)

        required_columns = {
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

        if not required_columns.issubset(
            set(reader.fieldnames or [])
        ):
            raise ValueError(
                "CSV enthält nicht alle benötigten Spalten."
            )

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

    candles.sort(key=lambda candle: candle["timestamp"])

    return candles


def apply_costs(
    price: float,
    direction: str,
) -> float:
    """
    Gebühren + Slippage auf den Preis anwenden.

    BUY:
        Wir kaufen etwas teurer.

    SELL:
        Wir verkaufen etwas günstiger.
    """

    fee = config.TRADING_FEE
    slippage = config.SLIPPAGE

    if direction == "BUY":
        return price * (1.0 + fee + slippage)

    if direction == "SELL":
        return price * (1.0 - fee - slippage)

    raise ValueError(
        f"Unbekannte Richtung: {direction}"
    )


def calculate_return(
    entry_price: float,
    exit_price: float,
) -> float:
    """
    Nettorendite einer Long-Position.

    Kosten werden bereits über die angepassten
    Entry-/Exit-Preise berücksichtigt.
    """

    if entry_price <= 0:
        raise ValueError("Entry-Preis muss > 0 sein.")

    return (exit_price / entry_price) - 1.0


# ============================================================
# SIGNAL-SCAN
# ============================================================

def scan_signals(
    candles: list[dict],
) -> list[dict]:
    """
    Scannt alle rollierenden 30-Kerzen-Fenster.

    Gibt für jede mögliche Position zurück:
    - Timestamp
    - positive Kerzen
    - aktive/inaktive Phase
    """

    results: list[dict] = []

    for index in range(
        config.CANDLE_WINDOW - 1,
        len(candles),
    ):

        window = candles[
            index - config.CANDLE_WINDOW + 1:
            index + 1
        ]

        signal = evaluate_30_candles(window)

        results.append(
            {
                "index": index,
                "timestamp": candles[index]["timestamp"],
                "positive": signal.positive_candles,
                "negative": signal.negative_candles,
                "ratio": signal.positive_ratio,
                "active": signal.active,
            }
        )

    return results


# ============================================================
# VARIANTE A
# ============================================================

def backtest_variant_a(
    candles: list[dict],
    signals: list[dict],
) -> list[Trade]:
    """
    Variante A:

    Signal wird am Ende einer abgeschlossenen Kerze erkannt.

    Einstieg:
        nächste Kerze

    Ausstieg:
        Ende derselben nächsten Kerze

    Damit vermeiden wir Look-Ahead-Bias.
    """

    trades: list[Trade] = []

    capital = float(config.STARTING_CAPITAL)

    for signal_index, signal in enumerate(signals):

        if not signal["active"]:
            continue

        candle_index = signal["index"]

        entry_index = candle_index + 1
        exit_index = candle_index + 1

        if exit_index >= len(candles):
            continue

        entry_candle = candles[entry_index]
        exit_candle = candles[exit_index]

        raw_entry = entry_candle["open"]
        raw_exit = exit_candle["close"]

        entry_price = apply_costs(
            raw_entry,
            "BUY",
        )

        exit_price = apply_costs(
            raw_exit,
            "SELL",
        )

        net_return = calculate_return(
            entry_price,
            exit_price,
        )

        start_capital = capital

        capital = capital * (
            1.0 + net_return
        )

        trade = Trade(
            entry_time=timestamp_to_datetime(
                entry_candle["timestamp"]
            ),
            exit_time=timestamp_to_datetime(
                exit_candle["timestamp"]
            ),
            entry_price=raw_entry,
            exit_price=raw_exit,
            positive_candles=signal["positive"],
            gross_return=(
                raw_exit / raw_entry
            ) - 1.0,
            net_return=net_return,
            start_capital=start_capital,
            end_capital=capital,
            reason="1_CANDLE_EXIT",
        )

        trades.append(trade)

    return trades


# ============================================================
# VARIANTE B
# ============================================================

def backtest_variant_b(
    candles: list[dict],
    signals: list[dict],
) -> list[Trade]:
    """
    Variante B:

    Einstieg:
        erste Kerze nach INAKTIV -> AKTIV

    Halten:
        solange Signal aktiv bleibt

    Ausstieg:
        erste Kerze nach dem Wechsel
        AKTIV -> INAKTIV

    Auch hier wird nur mit abgeschlossenen Kerzen
    gearbeitet.
    """

    trades: list[Trade] = []

    capital = float(config.STARTING_CAPITAL)

    in_position = False

    entry_index: int | None = None
    entry_positive: int = 0

    previous_active = False

    for signal in signals:

        candle_index = signal["index"]
        active = signal["active"]

        # ----------------------------------------------------
        # ENTRY
        # ----------------------------------------------------

        if (
            not in_position
            and active
            and not previous_active
        ):

            entry_index = candle_index + 1

            if entry_index >= len(candles):
                break

            entry_positive = signal["positive"]

            in_position = True

        # ----------------------------------------------------
        # EXIT
        # ----------------------------------------------------

        elif (
            in_position
            and not active
            and previous_active
        ):

            if entry_index is None:
                raise RuntimeError(
                    "Position ohne Entry gefunden."
                )

            exit_index = candle_index + 1

            if exit_index >= len(candles):
                break

            entry_candle = candles[entry_index]
            exit_candle = candles[exit_index]

            raw_entry = entry_candle["open"]
            raw_exit = exit_candle["close"]

            entry_price = apply_costs(
                raw_entry,
                "BUY",
            )

            exit_price = apply_costs(
                raw_exit,
                "SELL",
            )

            net_return = calculate_return(
                entry_price,
                exit_price,
            )

            start_capital = capital

            capital = capital * (
                1.0 + net_return
            )

            trades.append(
                Trade(
                    entry_time=timestamp_to_datetime(
                        entry_candle["timestamp"]
                    ),
                    exit_time=timestamp_to_datetime(
                        exit_candle["timestamp"]
                    ),
                    entry_price=raw_entry,
                    exit_price=raw_exit,
                    positive_candles=entry_positive,
                    gross_return=(
                        raw_exit / raw_entry
                    ) - 1.0,
                    net_return=net_return,
                    start_capital=start_capital,
                    end_capital=capital,
                    reason="SIGNAL_DEACTIVATED",
                )
            )

            in_position = False
            entry_index = None
            entry_positive = 0

        previous_active = active

    return trades


# ============================================================
# AUSWERTUNG
# ============================================================

def print_trade_summary(
    name: str,
    trades: list[Trade],
) -> None:

    print()
    print("=" * 70)
    print(name)
    print("=" * 70)

    if not trades:
        print("Keine Trades.")
        return

    winning_trades = [
        trade
        for trade in trades
        if trade.net_return > 0
    ]

    losing_trades = [
        trade
        for trade in trades
        if trade.net_return < 0
    ]

    start_capital = trades[0].start_capital
    end_capital = trades[-1].end_capital

    total_return = (
        end_capital / start_capital
    ) - 1.0

    gross_sum = sum(
        trade.gross_return
        for trade in trades
    )

    net_sum = sum(
        trade.net_return
        for trade in trades
    )

    win_rate = (
        len(winning_trades) / len(trades)
        if trades
        else 0.0
    )

    print(f"Startkapital:       ${start_capital:,.2f}")
    print(f"Endkapital:         ${end_capital:,.2f}")
    print(f"Gesamtrendite:      {total_return:.2%}")
    print()

    print(f"Trades:             {len(trades)}")
    print(f"Gewinntrades:       {len(winning_trades)}")
    print(f"Verlusttrades:      {len(losing_trades)}")
    print(f"Trefferquote:       {win_rate:.2%}")
    print()

    print(f"Brutto Summe:       {gross_sum:.2%}")
    print(f"Netto Summe:        {net_sum:.2%}")
    print()

    print(
        f"Gewinn absolut:     "
        f"${end_capital - start_capital:,.2f}"
    )

    print("=" * 70)


def print_signal_summary(
    signals: list[dict],
) -> None:

    active_windows = [
        signal
        for signal in signals
        if signal["active"]
    ]

    activations = []

    previous_active = False

    for signal in signals:

        if (
            signal["active"]
            and not previous_active
        ):
            activations.append(signal)

        previous_active = signal["active"]

    print()
    print("=" * 70)
    print("30-KERZEN SIGNAL AUSWERTUNG")
    print("=" * 70)

    print(
        f"Rollierende Fenster:  {len(signals)}"
    )

    print(
        f"Aktive Fenster:       "
        f"{len(active_windows)}"
    )

    print(
        f"Echte Aktivierungen:  "
        f"{len(activations)}"
    )

    if activations:

        print()
        print("ERSTE AKTIVIERUNGEN")
        print("-" * 70)

        for activation in activations[:20]:

            timestamp = timestamp_to_datetime(
                activation["timestamp"]
            )

            print(
                f"{timestamp.strftime('%Y-%m-%d %H:%M')} UTC"
                f" | "
                f"{activation['positive']:2d}/30"
            )

    print("=" * 70)


def print_trade_details(
    name: str,
    trades: list[Trade],
) -> None:

    print()
    print("=" * 70)
    print(f"{name} - TRADE DETAILS")
    print("=" * 70)

    if not trades:
        print("Keine Trades.")
        return

    for number, trade in enumerate(
        trades,
        start=1,
    ):

        print(
            f"{number:3d}. "
            f"{trade.entry_time.strftime('%Y-%m-%d %H:%M')} UTC"
            f" -> "
            f"{trade.exit_time.strftime('%Y-%m-%d %H:%M')} UTC"
            f" | "
            f"{trade.positive_candles}/30"
            f" | "
            f"{trade.net_return:+.4%}"
            f" | "
            f"${trade.end_capital:,.2f}"
        )

    print("=" * 70)


# ============================================================
# SELF TEST
# ============================================================

def self_test() -> None:

    print("=" * 70)
    print("BACKTEST SELF TEST")
    print("=" * 70)

    candles = []

    for index in range(40):

        candles.append(
            {
                "timestamp": index * 300,
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 101.0,
                "volume": 1.0,
            }
        )

    signals = scan_signals(candles)

    assert len(signals) == 11

    for signal in signals:
        assert signal["positive"] == 30
        assert signal["active"] is True

    print(
        "PASS: Rollierendes 30-Kerzen-Fenster"
    )

    print(
        "PASS: 30/30 wird als AKTIV erkannt"
    )

    print(
        "PASS: Backtest Self Test"
    )

    print("=" * 70)


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print()
    print("=" * 70)
    print("30-KERZEN BTC BOT - HISTORISCHER BACKTEST")
    print("=" * 70)

    print()
    print("REGEL")
    print("-" * 70)
    print(
        "Positive Kerze = Close > Open"
    )
    print(
        f"Aktiv ab {config.MIN_POSITIVE_CANDLES}/"
        f"{config.CANDLE_WINDOW}"
    )

    print()
    print("BACKTEST PARAMETER")
    print("-" * 70)
    print(
        f"Startkapital:       "
        f"${config.STARTING_CAPITAL:.2f}"
    )
    print(
        f"Trading Fee:        "
        f"{config.TRADING_FEE:.2%}"
    )
    print(
        f"Slippage:           "
        f"{config.SLIPPAGE:.2%}"
    )

    print()
    print("Lade historische Daten...")

    candles = load_candles()

    print(
        f"Geladene Kerzen:    {len(candles)}"
    )

    if len(candles) < config.CANDLE_WINDOW + 2:
        raise ValueError(
            "Nicht genügend Kerzen für den Backtest."
        )

    first_time = timestamp_to_datetime(
        candles[0]["timestamp"]
    )

    last_time = timestamp_to_datetime(
        candles[-1]["timestamp"]
    )

    print(
        f"Zeitraum:            "
        f"{first_time.strftime('%Y-%m-%d %H:%M')} UTC"
        f" → "
        f"{last_time.strftime('%Y-%m-%d %H:%M')} UTC"
    )

    print()
    print("Scanne 30-Kerzen-Fenster...")

    signals = scan_signals(candles)

    print_signal_summary(signals)

    print()
    print("Berechne Variante A...")

    trades_a = backtest_variant_a(
        candles,
        signals,
    )

    print_trade_summary(
        "VARIANTE A - 1 KERZE HALTEN",
        trades_a,
    )

    print_trade_details(
        "VARIANTE A",
        trades_a,
    )

    print()
    print("Berechne Variante B...")

    trades_b = backtest_variant_b(
        candles,
        signals,
    )

    print_trade_summary(
        "VARIANTE B - SOLANGE SIGNAL AKTIV",
        trades_b,
    )

    print_trade_details(
        "VARIANTE B",
        trades_b,
    )

    print()
    print("=" * 70)
    print("BACKTEST ABGESCHLOSSEN")
    print("=" * 70)
    print()
    print(
        "WICHTIG: Dies ist ein historischer Paper-Backtest."
    )
    print(
        "Keine echten Orders wurden ausgeführt."
    )
    print(
        "Kelly-Sizing ist noch NICHT implementiert."
    )
    print("=" * 70)


if __name__ == "__main__":
    self_test()
    main()
