"""
30-Kerzen BTC Bot
Signal Module
Version 0.1.0

V1-Regel:

- Es werden genau 30 Kerzen betrachtet.
- Eine Kerze ist positiv, wenn Close > Open.
- Ab 26 positiven Kerzen wird das Signal AKTIV.
- Unter 26 positiven Kerzen bleibt das Signal INAKTIV.

Noch kein echtes Trading.
Noch kein Kelly-Sizing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import config


# ============================================================
# SIGNAL RESULT
# ============================================================

@dataclass
class SignalResult:
    """
    Ergebnis der 30-Kerzen-Auswertung.
    """

    total_candles: int
    positive_candles: int
    negative_candles: int
    positive_ratio: float
    active: bool

    @property
    def signal(self) -> str:
        """
        Gibt den Signalstatus zurück.
        """

        if self.active:
            return "ACTIVE"

        return "INACTIVE"

    def short_description(self) -> str:
        """
        Kurze lesbare Zusammenfassung.
        """

        return (
            f"{self.positive_candles}/"
            f"{self.total_candles} positiv "
            f"({self.positive_ratio:.2%}) "
            f"→ {self.signal}"
        )


# ============================================================
# KERZEN KLASSIFIZIEREN
# ============================================================

def is_positive_candle(
    candle: dict[str, Any],
) -> bool:
    """
    Prüft, ob eine Kerze positiv ist.

    V1-Regel:

        Close > Open

    Eine Doji-Kerze mit:

        Close == Open

    gilt NICHT als positiv.
    """

    open_price = float(candle["open"])
    close_price = float(candle["close"])

    return close_price > open_price


# ============================================================
# 30-KERZEN-SIGNAL
# ============================================================

def evaluate_30_candles(
    candles: list[dict[str, Any]],
) -> SignalResult:
    """
    Bewertet die letzten 30 Kerzen.

    Es müssen mindestens 30 Kerzen vorhanden sein.

    Die letzten 30 Kerzen werden verwendet.
    """

    if len(candles) < config.CANDLE_WINDOW:
        raise ValueError(
            f"Mindestens {config.CANDLE_WINDOW} Kerzen "
            f"erforderlich, erhalten: {len(candles)}"
        )

    # Nur die letzten 30 Kerzen verwenden.
    window = candles[-config.CANDLE_WINDOW:]

    positive_candles = sum(
        1
        for candle in window
        if is_positive_candle(candle)
    )

    total_candles = len(window)

    negative_candles = (
        total_candles - positive_candles
    )

    positive_ratio = (
        positive_candles / total_candles
    )

    active = (
        positive_candles
        >= config.MIN_POSITIVE_CANDLES
    )

    return SignalResult(
        total_candles=total_candles,
        positive_candles=positive_candles,
        negative_candles=negative_candles,
        positive_ratio=positive_ratio,
        active=active,
    )


# ============================================================
# SIGNAL AUSGEBEN
# ============================================================

def print_signal(
    result: SignalResult,
) -> None:
    """
    Gibt das Signal übersichtlich aus.
    """

    print("=" * 60)
    print("30-KERZEN SIGNAL")
    print("=" * 60)

    print(
        f"Kerzen insgesamt:    {result.total_candles}"
    )

    print(
        f"Positive Kerzen:     {result.positive_candles}"
    )

    print(
        f"Nicht positive:      {result.negative_candles}"
    )

    print(
        f"Positiver Anteil:    "
        f"{result.positive_ratio:.2%}"
    )

    print(
        f"Minimum benötigt:    "
        f"{config.MIN_POSITIVE_CANDLES}"
    )

    print()

    if result.active:

        print("SIGNAL:               AKTIV")

    else:

        print("SIGNAL:               INAKTIV")

    print()

    print(
        result.short_description()
    )

    print("=" * 60)


# ============================================================
# SELF TEST
# ============================================================

def self_test() -> None:
    """
    Testet die 30-Kerzen-Regel mit künstlichen Daten.
    """

    print("=" * 60)
    print("SIGNALS SELF TEST")
    print("=" * 60)

    # --------------------------------------------------------
    # TEST 1
    # Genau 26 positive Kerzen
    # --------------------------------------------------------

    candles_26 = []

    for index in range(30):

        if index < 26:

            open_price = 100.0
            close_price = 101.0

        else:

            open_price = 100.0
            close_price = 99.0

        candles_26.append({
            "timestamp": index * 300,
            "open": open_price,
            "high": max(
                open_price,
                close_price,
            ),
            "low": min(
                open_price,
                close_price,
            ),
            "close": close_price,
            "volume": 1.0,
        })

    result_26 = evaluate_30_candles(
        candles_26
    )

    assert result_26.total_candles == 30

    assert result_26.positive_candles == 26

    assert result_26.negative_candles == 4

    assert result_26.positive_ratio == 26 / 30

    assert result_26.active is True

    print(
        "PASS: 26/30 → AKTIV"
    )

    # --------------------------------------------------------
    # TEST 2
    # 25 positive Kerzen
    # --------------------------------------------------------

    candles_25 = []

    for index in range(30):

        if index < 25:

            open_price = 100.0
            close_price = 101.0

        else:

            open_price = 100.0
            close_price = 99.0

        candles_25.append({
            "timestamp": index * 300,
            "open": open_price,
            "high": max(
                open_price,
                close_price,
            ),
            "low": min(
                open_price,
                close_price,
            ),
            "close": close_price,
            "volume": 1.0,
        })

    result_25 = evaluate_30_candles(
        candles_25
    )

    assert result_25.total_candles == 30

    assert result_25.positive_candles == 25

    assert result_25.negative_candles == 5

    assert result_25.active is False

    print(
        "PASS: 25/30 → INAKTIV"
    )

    # --------------------------------------------------------
    # TEST 3
    # Doji ist nicht positiv
    # --------------------------------------------------------

    doji = {
        "timestamp": 9999,
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.0,
        "volume": 1.0,
    }

    assert is_positive_candle(doji) is False

    print(
        "PASS: Doji → nicht positiv"
    )

    # --------------------------------------------------------
    # TEST 4
    # Zu wenige Kerzen
    # --------------------------------------------------------

    try:

        evaluate_30_candles(
            candles_26[:29]
        )

        raise AssertionError(
            "Zu wenige Kerzen wurden nicht erkannt."
        )

    except ValueError:

        print(
            "PASS: <30 Kerzen → Fehler erkannt"
        )

    print()

    print(
        "PASS: Signals Self Test"
    )

    print("=" * 60)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    self_test()
