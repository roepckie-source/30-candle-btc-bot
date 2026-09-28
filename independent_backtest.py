"""
30-Kerzen BTC Bot
2 / 3 / 5 / 10 Kerzen Vergleich

Historischer Paper-Backtest.

Varianten:
    Close[t] > Close[t-2]
    Close[t] > Close[t-3]
    Close[t] > Close[t-5]
    Close[t] > Close[t-10]

Für jede Variante:
    - 30-Kerzen-Fenster
    - mindestens 26 positive Kerzen
    - nur erstes Signal einer Signalserie
    - keine überlappenden Trades
    - Einstieg nächste 5m-Kerze
    - Haltedauer 2h und 4h
    - 0,10% Fee je Seite
    - 0,05% Slippage je Seite
    - $100 Startkapital
    - 10% Positionsgröße

PAPER ONLY
NO API KEYS
NO WALLET
NO REAL ORDERS
NO LIVE TRADING
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


# ============================================================
# CSV EINLESEN
# ============================================================

def parse_timestamp(value):
    """
    Unterstützt mehrere mögliche Timestamp-Formate.
    """

    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    # ISO / ISO-Z
    try:
        ts = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if ts.tzinfo is None:
            ts = ts.replace(
                tzinfo=timezone.utc
            )

        return ts.astimezone(timezone.utc)

    except ValueError:
        pass

    # Unix Timestamp
    try:
        number = float(value)

        # Millisekunden erkennen
        if number > 10_000_000_000:
            number = number / 1000.0

        return datetime.fromtimestamp(
            number,
            tz=timezone.utc
        )

    except (ValueError, OverflowError):
        return None


def load_data():

    print()
    print("CSV EINLESEN")
    print("-" * 78)
    print(
        f"Datei: {CSV_FILE}"
    )

    if not CSV_FILE.exists():

        raise FileNotFoundError(
            f"CSV nicht gefunden: {CSV_FILE}"
        )

    file_size = CSV_FILE.stat().st_size

    print(
        f"Dateigröße: {file_size} Bytes"
    )

    if file_size == 0:

        raise ValueError(
            "CSV-Datei ist leer."
        )

    rows = []

    with CSV_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        fieldnames = reader.fieldnames or []

        print(
            f"CSV-Spalten: {fieldnames}"
        )

        required = {
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

        missing = (
            required
            - set(fieldnames)
        )

        if missing:

            raise ValueError(
                "CSV enthält nicht die "
                f"erwarteten Spalten. "
                f"Fehlen: {sorted(missing)}"
            )

        total_rows = 0
        invalid_rows = 0

        for row in reader:

            total_rows += 1

            try:

                timestamp = parse_timestamp(
                    row.get("timestamp")
                )

                if timestamp is None:
                    invalid_rows += 1
                    continue

                open_price = float(
                    row["open"]
                )

                high_price = float(
                    row["high"]
                )

                low_price = float(
                    row["low"]
                )

                close_price = float(
                    row["close"]
                )

                volume = float(
                    row["volume"]
                )

                rows.append(
                    {
                        "timestamp": timestamp,
                        "open": open_price,
                        "high": high_price,
                        "low": low_price,
                        "close": close_price,
                        "volume": volume,
                    }
                )

            except (
                TypeError,
                ValueError,
                KeyError
            ):

                invalid_rows += 1

        print(
            f"CSV-Datenzeilen: {total_rows}"
        )

        print(
            f"Ungültige Zeilen: {invalid_rows}"
        )

    rows.sort(
        key=lambda row:
        row["timestamp"]
    )

    # Doppelte Zeitstempel entfernen
    unique = []

    seen = set()

    for row in rows:

        timestamp = row["timestamp"]

        if timestamp in seen:
            continue

        seen.add(timestamp)

        unique.append(row)

    print(
        f"Gültige eindeutige Kerzen: "
        f"{len(unique)}"
    )

    if not unique:

        raise ValueError(
            "CSV wurde gefunden, aber es "
            "konnten KEINE gültigen Kerzen "
            "eingelesen werden."
        )

    return unique


# ============================================================
# POSITIVE KERZEN
# ============================================================

def positive_count(
    candles,
    end_index,
    lookback
):
    """
    Positive Bedingung:

        Close[t] > Close[t-lookback]

    Es werden genau die letzten
    30 Kerzen betrachtet.
    """

    start_index = (
        end_index
        - WINDOW
        + 1
    )

    if start_index < lookback:

        return None

    count = 0

    for i in range(
        start_index,
        end_index + 1
    ):

        current_close = (
            candles[i]["close"]
        )

        previous_close = (
            candles[
                i - lookback
            ]["close"]
        )

        if current_close > previous_close:

            count += 1

    return count


# ============================================================
# SIGNALSERIEN
# ============================================================

def find_signal_series(
    candles,
    lookback
):

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

    for i in range(
        len(candles)
    ):

        if not active[i]:
            continue

        previous_active = (
            i > 0
            and active[i - 1]
        )

        # Noch dieselbe Signalserie
        if previous_active:
            continue

        entry_index = i + 1

        if entry_index >= len(candles):
            continue

        signals.append(
            {
                "signal_index": i,

                "signal_timestamp":
                    candles[
                        i
                    ]["timestamp"],

                "positive_count":
                    counts[i],

                "entry_index":
                    entry_index,

                "entry_timestamp":
                    candles[
                        entry_index
                    ]["timestamp"],
            }
        )

    return signals


# ============================================================
# TRADE
# ============================================================

def build_trade(
    signal,
    candles,
    horizon_bars
):

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
        candles[
            entry_index
        ]["open"]
    )

    raw_exit = float(
        candles[
            exit_index
        ]["close"]
    )

    # Long Entry mit Slippage
    effective_entry = (
        raw_entry
        * (1.0 + SLIPPAGE)
    )

    # Long Exit mit Slippage
    effective_exit = (
        raw_exit
        * (1.0 - SLIPPAGE)
    )

    # Gebühren auf Entry und Exit
    net_multiple = (
        effective_exit
        / effective_entry
    ) * (
        1.0 - FEE
    ) / (
        1.0 + FEE
    )

    net_return = (
        net_multiple
        - 1.0
    )

    return {
        **signal,

        "exit_index":
            exit_index,

        "exit_timestamp":
            candles[
                exit_index
            ]["timestamp"],

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


# ============================================================
# KEINE ÜBERLAPPENDEN TRADES
# ============================================================

def select_non_overlapping_trades(
    signals,
    candles,
    horizon_bars
):

    trades = []

    next_allowed_entry = -1

    skipped_overlap = 0

    for signal in signals:

        if (
            signal["entry_index"]
            <
            next_allowed_entry
        ):

            skipped_overlap += 1

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

    return trades, skipped_overlap


# ============================================================
# PORTFOLIO
# ============================================================

def run_portfolio(
    trades
):

    capital = (
        STARTING_CAPITAL
    )

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

    total_trades = len(
        trades
    )

    if gross_loss > 0:

        profit_factor = (
            gross_profit
            / gross_loss
        )

    elif gross_profit > 0:

        profit_factor = math.inf

    else:

        profit_factor = 0.0

    if trade_returns:

        average_trade = (
            statistics.mean(
                trade_returns
            )
        )

        median_trade = (
            statistics.median(
                trade_returns
            )
        )

    else:

        average_trade = 0.0
        median_trade = 0.0

    peak = (
        STARTING_CAPITAL
    )

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
                winning
                / total_trades
                if total_trades
                else 0.0
            ),

        "average_trade":
            average_trade,

        "median_trade":
            median_trade,

        "profit_factor":
            profit_factor,

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


# ============================================================
# FORMAT
# ============================================================

def format_profit_factor(
    value
):

    if math.isinf(value):

        return "INF"

    return f"{value:.2f}"


# ============================================================
# SELF TEST
# ============================================================

def self_test():

    print()
    print(
        "SELF-TEST"
    )
    print(
        "-" * 78
    )

    assert WINDOW == 30

    assert THRESHOLD == 26

    assert LOOKBACKS == [
        2,
        3,
        5,
        10
    ]

    assert HORIZONS["2h"] == 24

    assert HORIZONS["4h"] == 48

    print(
        "PASS: Konfiguration"
    )

    # Steigende Kurse
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

        signals = (
            find_signal_series(
                candles,
                lookback
            )
        )

        assert len(
            signals
        ) == 1

        print(
            f"PASS: "
            f"{lookback} Kerzen"
        )

    # Seitwärtsmarkt:
    # Kosten müssen zu einem Verlust führen.
    signal = {

        "signal_index":
            30,

        "signal_timestamp":
            candles[
                30
            ]["timestamp"],

        "positive_count":
            30,

        "entry_index":
            31,

        "entry_timestamp":
            candles[
                31
            ]["timestamp"],
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
        trade["net_return"]
        < 0
    )

    print(
        "PASS: Gebühren/Slippage"
    )

    print(
        "SELF-TEST: PASS"
    )


# ============================================================
# DETAIL
# ============================================================

def print_detail(
    horizon_label,
    lookback,
    signals,
    trades,
    skipped_overlap,
    result
):

    print()
    print(
        "=" * 78
    )

    print(
        f"REGEL: Close > Close-{lookback}"
    )

    print(
        f"HALTEDAUER: {horizon_label}"
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
        f"Übersprungene Overlaps:   "
        f"{skipped_overlap}"
    )

    print()

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

    print()

    print(
        f"Ø Netto-Trade:            "
        f"{result['average_trade']:.3%}"
    )

    print(
        f"Median Netto-Trade:       "
        f"{result['median_trade']:.3%}"
    )

    print(
        f"Profit Factor:            "
        f"{format_profit_factor(result['profit_factor'])}"
    )

    print(
        f"Max Drawdown:             "
        f"{result['max_drawdown']:.3%}"
    )

    print()

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
        print(
            "TRADES"
        )

        print(
            "-" * 78
        )

        for number, trade in enumerate(
            trades,
            start=1
        ):

            print(
                f"{number:>3} | "
                f"{trade['signal_timestamp']} | "
                f"{trade['positive_count']}/30 | "
                f"Entry "
                f"${trade['raw_entry']:.2f} | "
                f"Exit "
                f"${trade['raw_exit']:.2f} | "
                f"Net "
                f"{trade['net_return']:.3%} | "
                f"PnL "
                f"${trade['pnl']:.4f}"
            )


# ============================================================
# MAIN
# ============================================================

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
        f"{THRESHOLD}/"
        f"{WINDOW}"
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

    # Sicherheitsprüfung
    if len(candles) < WINDOW:

        raise ValueError(
            f"Zu wenige Kerzen: "
            f"{len(candles)}. "
            f"Mindestens {WINDOW} "
            f"werden benötigt."
        )

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

            (
                trades,
                skipped_overlap
            ) = (
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

                    "trades":
                        result["trades"],

                    "wins":
                        result["wins"],

                    "losses":
                        result["losses"],

                    "win_rate":
                        result["win_rate"],

                    "profit_factor":
                        result["profit_factor"],

                    "portfolio_return":
                        result[
                            "portfolio_return"
                        ],

                    "max_drawdown":
                        result[
                            "max_drawdown"
                        ],

                    "ending_capital":
                        result[
                            "ending_capital"
                        ],
                }
            )

            print_detail(
                horizon_label,
                lookback,
                signals,
                trades,
                skipped_overlap,
                result
            )

    # ========================================================
    # VERGLEICHSTABELLE
    # ========================================================

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
        f"{'Zeit':>8} "
        f"{'Signale':>8} "
        f"{'Trades':>8} "
        f"{'Win%':>8} "
        f"{'PF':>8} "
        f"{'Return':>10} "
        f"{'MaxDD':>10} "
        f"{'End $':>10}"
    )

    print(
        "-" * 78
    )

    for row in all_results:

        print(
            f"{row['lookback']:>8} "
            f"{row['horizon']:>8} "
            f"{row['signals']:>8} "
            f"{row['trades']:>8} "
            f"{row['win_rate']:>7.2%} "
            f"{format_profit_factor(row['profit_factor']):>8} "
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
        "Dies ist ausschließlich "
        "ein historischer "
        "Paper-Backtest."
    )


if __name__ == "__main__":

    main()
