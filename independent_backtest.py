"""
30-Kerzen BTC Bot
Vergleichstest für 2 / 3 / 5 / 10 Kerzen Abstand

Regel je Variante:
- 30-Kerzen-Fenster
- mindestens 26 positive Vergleiche
- positiv = Close[t] > Close[t-N]
- nur das erste Signal einer zusammenhängenden Signalserie
- keine überlappenden Trades
- Einstieg: nächste 5m-Kerze zum Open
- Haltedauer: 2h oder 4h
- 0,10% Gebühr je Seite
- 0,05% Slippage je Seite
- $100 Startkapital
- 10% Positionsgröße
- PAPER ONLY
"""

from pathlib import Path
import csv
import math
import statistics
from datetime import datetime, timezone


CSV_FILE = Path("data/BTC_USD_5m.csv")

STARTING_CAPITAL = 100.00

WINDOW = 30
THRESHOLD = 26

LOOKBACKS = [2, 3, 5, 10]

FEE = 0.001
SLIPPAGE = 0.0005

POSITION_SIZE_PERCENT = 0.10

HORIZONS = {
    "2h": 24,
    "4h": 48,
}


def load_data():
    if not CSV_FILE.exists():
        raise FileNotFoundError(
            f"CSV nicht gefunden: {CSV_FILE}"
        )

    rows = []

    with CSV_FILE.open(
        "r",
        encoding="utf-8-sig",
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

        missing = required - set(
            reader.fieldnames or []
        )

        if missing:
            raise ValueError(
                f"Fehlende CSV-Spalten: "
                f"{sorted(missing)}"
            )

        for row in reader:

            try:

                timestamp = datetime.fromisoformat(
                    row["timestamp"].replace(
                        "Z",
                        "+00:00"
                    )
                )

                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(
                        tzinfo=timezone.utc
                    )

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

            except (
                TypeError,
                ValueError
            ):
                continue

    rows.sort(
        key=lambda x: x["timestamp"]
    )

    unique = []
    seen = set()

    for row in rows:

        key = row["timestamp"]

        if key in seen:
            continue

        seen.add(key)
        unique.append(row)

    return unique


def positive_count(
    candles,
    end_index,
    lookback
):
    """
    Zählt innerhalb der letzten 30 Kerzen:

        Close[t] > Close[t-lookback]
    """

    start = (
        end_index
        - WINDOW
        + 1
    )

    if start < lookback:
        return None

    count = 0

    for i in range(
        start,
        end_index + 1
    ):

        if (
            candles[i]["close"]
            >
            candles[i - lookback]["close"]
        ):
            count += 1

    return count


def find_signal_series(
    candles,
    lookback
):
    """
    Eine Signalserie beginnt beim ersten
    aktiven 30-Kerzen-Fenster.

    Solange das Fenster aktiv bleibt,
    werden keine neuen Signale erzeugt.
    """

    active = [
        False
        for _ in candles
    ]

    counts = [
        None
        for _ in candles
    ]

    for i in range(
        len(candles)
    ):

        count = positive_count(
            candles,
            i,
            lookback
        )

        if count is None:
            continue

        counts[i] = count

        active[i] = (
            count >= THRESHOLD
        )

    signals = []

    for i, is_active in enumerate(
        active
    ):

        if not is_active:
            continue

        previous_active = (
            i > 0
            and active[i - 1]
        )

        if previous_active:
            continue

        entry_index = i + 1

        if entry_index >= len(candles):
            continue

        signals.append(
            {
                "signal_index": i,
                "signal_timestamp":
                    candles[i]["timestamp"],
                "positive_count":
                    counts[i],
                "entry_index":
                    entry_index,
                "entry_timestamp":
                    candles[entry_index]["timestamp"],
            }
        )

    return signals


def build_trade(
    signal,
    candles,
    horizon_bars
):
    """
    Einstieg:
        nächste 5m-Kerze zum Open

    Ausstieg:
        Schlusskurs nach gewünschter Haltedauer.

    2h = 24 x 5 Minuten
    4h = 48 x 5 Minuten
    """

    entry_index = (
        signal["entry_index"]
    )

    exit_index = (
        entry_index
        + horizon_bars
        - 1
    )

    if exit_index >= len(candles):
        return None

    raw_entry = float(
        candles[entry_index]["open"]
    )

    raw_exit = float(
        candles[exit_index]["close"]
    )

    effective_entry = (
        raw_entry
        * (1.0 + SLIPPAGE)
    )

    effective_exit = (
        raw_exit
        * (1.0 - SLIPPAGE)
    )

    net_multiple = (
        effective_exit
        / effective_entry
    ) * (
        1.0 - FEE
    ) / (
        1.0 + FEE
    )

    net_return = (
        net_multiple - 1.0
    )

    return {
        **signal,

        "exit_index":
            exit_index,

        "exit_timestamp":
            candles[exit_index]["timestamp"],

        "raw_entry":
            raw_entry,

        "raw_exit":
            raw_exit,

        "effective_entry":
            effective_entry,

        "effective_exit":
            effective_exit,

        "net_return":
            net_return,
    }


def select_non_overlapping_trades(
    signals,
    candles,
    horizon_bars
):

    trades = []

    next_allowed_entry = -1

    for signal in signals:

        if (
            signal["entry_index"]
            <
            next_allowed_entry
        ):
            continue

        trade = build_trade(
            signal,
            candles,
            horizon_bars
        )

        if trade is None:
            continue

        trades.append(trade)

        next_allowed_entry = (
            trade["exit_index"]
            + 1
        )

    return trades


def run_portfolio(
    trades
):

    capital = STARTING_CAPITAL

    equity_curve = [
        capital
    ]

    winning = 0
    losing = 0

    gross_profit = 0.0
    gross_loss = 0.0

    trade_returns = []

    for trade in trades:

        capital_before = capital

        position_size = (
            capital
            * POSITION_SIZE_PERCENT
        )

        pnl = (
            position_size
            * trade["net_return"]
        )

        capital = (
            capital
            + pnl
        )

        trade["capital_before"] = (
            capital_before
        )

        trade["position_size"] = (
            position_size
        )

        trade["pnl"] = pnl

        trade["capital_after"] = (
            capital
        )

        trade_returns.append(
            trade["net_return"]
        )

        equity_curve.append(
            capital
        )

        if pnl > 0:

            winning += 1
            gross_profit += pnl

        elif pnl < 0:

            losing += 1
            gross_loss += abs(pnl)

    total_trades = len(trades)

    if gross_loss > 0:

        profit_factor = (
            gross_profit
            / gross_loss
        )

    elif gross_profit > 0:

        profit_factor = math.inf

    else:

        profit_factor = 0.0

    peak = STARTING_CAPITAL

    max_drawdown = 0.0

    for equity in equity_curve:

        peak = max(
            peak,
            equity
        )

        drawdown = (
            equity / peak
            - 1.0
        )

        max_drawdown = min(
            max_drawdown,
            drawdown
        )

    return {
        "trades":
            total_trades,

        "wins":
            winning,

        "losses":
            losing,

        "win_rate":
            (
                winning / total_trades
                if total_trades
                else 0.0
            ),

        "profit_factor":
            profit_factor,

        "average_trade":
            (
                statistics.mean(
                    trade_returns
                )
                if trade_returns
                else 0.0
            ),

        "ending_capital":
            capital,

        "portfolio_return":
            (
                capital
                / STARTING_CAPITAL
                - 1.0
            ),

        "max_drawdown":
            max_drawdown,

        "gross_profit":
            gross_profit,

        "gross_loss":
            gross_loss,
    }


def format_pf(value):

    if math.isinf(value):
        return "INF"

    return f"{value:.2f}"


def self_test():

    assert WINDOW == 30

    assert THRESHOLD == 26

    assert LOOKBACKS == [
        2,
        3,
        5,
        10,
    ]

    assert HORIZONS["2h"] == 24

    assert HORIZONS["4h"] == 48

    candles = []

    for i in range(120):

        close = (
            100.0 + i
        )

        candles.append(
            {
                "timestamp":
                    datetime(
                        2026,
                        1,
                        1,
                        tzinfo=timezone.utc
                    ),

                "open":
                    close - 0.5,

                "high":
                    close,

                "low":
                    close - 1.0,

                "close":
                    close,

                "volume":
                    1.0,
            }
        )

    for lookback in LOOKBACKS:

        signals = find_signal_series(
            candles,
            lookback
        )

        assert len(signals) == 1, (
            f"Self-test Fehler bei "
            f"{lookback} Kerzen."
        )

    signal = {

        "signal_index":
            30,

        "signal_timestamp":
            candles[30]["timestamp"],

        "positive_count":
            30,

        "entry_index":
            31,

        "entry_timestamp":
            candles[31]["timestamp"],
    }

    flat = []

    for i in range(80):

        flat.append(
            {
                "timestamp":
                    datetime(
                        2026,
                        1,
                        1,
                        tzinfo=timezone.utc
                    ),

                "open":
                    100.0,

                "high":
                    100.0,

                "low":
                    100.0,

                "close":
                    100.0,

                "volume":
                    1.0,
            }
        )

    trade = build_trade(
        signal,
        flat,
        24
    )

    assert trade is not None

    assert (
        trade["net_return"] < 0
    )

    print(
        "SELF-TEST: PASS"
    )


def print_detail(
    label,
    lookback,
    signals,
    trades,
    result
):

    print()

    print(
        "=" * 78
    )

    print(
        f"{label} | "
        f"Close > Close-{lookback}"
    )

    print(
        "=" * 78
    )

    print(
        f"Signalserien:             "
        f"{len(signals)}"
    )

    print(
        f"Ausgeführte Trades:       "
        f"{len(trades)}"
    )

    print(
        f"Gewinntrades:             "
        f"{result['wins']}"
    )

    print(
        f"Verlusttrades:            "
        f"{result['losses']}"
    )

    print(
        f"Trefferquote:             "
        f"{result['win_rate']:.2%}"
    )

    print(
        f"Ø Netto-Trade:            "
        f"{result['average_trade']:.3%}"
    )

    print(
        f"Profit Factor:            "
        f"{format_pf(result['profit_factor'])}"
    )

    print(
        f"Max Drawdown:             "
        f"{result['max_drawdown']:.3%}"
    )

    print(
        f"Startkapital:             "
        f"${STARTING_CAPITAL:.2f}"
    )

    print(
        f"Endkapital:               "
        f"${result['ending_capital']:.2f}"
    )

    print(
        f"Portfolio Return:         "
        f"{result['portfolio_return']:.3%}"
    )

    if trades:

        print()

        print("Trades:")

        for n, trade in enumerate(
            trades,
            start=1
        ):

            print(
                f"  {n:>2} | "
                f"{trade['signal_timestamp']} | "
                f"{trade['positive_count']}/30 | "
                f"Entry "
                f"{trade['raw_entry']:.2f} | "
                f"Exit "
                f"{trade['raw_exit']:.2f} | "
                f"Net "
                f"{trade['net_return']:.3%} | "
                f"PnL "
                f"${trade['pnl']:.4f}"
            )


def main():

    print(
        "=" * 78
    )

    print(
        "30-KERZEN BTC BOT"
    )

    print(
        "2 / 3 / 5 / 10 KERZEN VERGLEICH"
    )

    print(
        "=" * 78
    )

    print()

    print(
        "PAPER TRADING ONLY"
    )

    print(
        "NO API KEYS"
    )

    print(
        "NO WALLET"
    )

    print(
        "NO REAL ORDERS"
    )

    print(
        "NO LIVE TRADING"
    )

    print()

    print(
        f"Fenster:                 "
        f"{WINDOW} Kerzen"
    )

    print(
        f"Schwelle:                "
        f"{THRESHOLD}/{WINDOW}"
    )

    print(
        f"Varianten:               "
        f"{LOOKBACKS}"
    )

    print(
        f"Startkapital:            "
        f"${STARTING_CAPITAL:.2f}"
    )

    print(
        f"Positionsgröße:          "
        f"{POSITION_SIZE_PERCENT:.0%}"
    )

    print(
        f"Fee je Seite:            "
        f"{FEE:.2%}"
    )

    print(
        f"Slippage je Seite:       "
        f"{SLIPPAGE:.2%}"
    )

    self_test()

    candles = load_data()

    print()

    print(
        "DATEN"
    )

    print(
        "-" * 78
    )

    print(
        f"Kerzen:                  "
        f"{len(candles)}"
    )

    print(
        f"Von:                     "
        f"{candles[0]['timestamp']}"
    )

    print(
        f"Bis:                     "
        f"{candles[-1]['timestamp']}"
    )

    all_results = []

    for (
        horizon_label,
        horizon_bars
    ) in HORIZONS.items():

        print()

        print()

        print(
            "#" * 78
        )

        print(
            f"HALTEDAUER: "
            f"{horizon_label}"
        )

        print(
            "#" * 78
        )

        for lookback in LOOKBACKS:

            signals = (
                find_signal_series(
                    candles,
                    lookback
                )
            )

            trades = (
                select_non_overlapping_trades(
                    signals,
                    candles,
                    horizon_bars
                )
            )

            result = run_portfolio(
                trades
            )

            all_results.append(
                {
                    "lookback":
                        lookback,

                    "horizon":
                        horizon_label,

                    "signals":
                        len(signals),

                    **result,
                }
            )

            print_detail(
                horizon_label,
                lookback,
                signals,
                trades,
                result
            )

    print()

    print()

    print(
        "=" * 78
    )

    print(
        "VERGLEICHSTABELLE"
    )

    print(
        "=" * 78
    )

    print(
        f"{'Regel':>8} "
        f"{'Horizon':>8} "
        f"{'Signale':>8} "
        f"{'Trades':>8} "
        f"{'Win%':>8} "
        f"{'PF':>8} "
        f"{'Return':>10} "
        f"{'MaxDD':>10} "
        f"{'End $':>10}"
    )

    for row in all_results:

        print(
            f"{row['lookback']:>7} "
            f"{row['horizon']:>8} "
            f"{row['signals']:>8} "
            f"{row['trades']:>8} "
            f"{row['win_rate']:>7.2%} "
            f"{format_pf(row['profit_factor']):>8} "
            f"{row['portfolio_return']:>9.2%} "
            f"{row['max_drawdown']:>9.2%} "
            f"{row['ending_capital']:>10.2f}"
        )

    print()

    print(
        "=" * 78
    )

    print(
        "VERGLEICH ABGESCHLOSSEN"
    )

    print(
        "=" * 78
    )

    print(
        "Die offizielle Bot-Regel "
        "wurde NICHT geändert."
    )

    print(
        "Dies ist ein unabhängiger "
        "historischer Paper-Backtest."
    )


if __name__ == "__main__":
    main()
