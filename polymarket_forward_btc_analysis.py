"""
POLYMARKET BTC FORWARD ANALYSIS
Version 0.2.2

Zweck:
- Prüft BTC-Forward-Performance nach 26/30-Signalen
- BTC 5-Minuten-Kerzen
- Vergleich verschiedener Lookbacks
- Horizonte bis 12 Stunden
- Paper analysis only
- Keine API Keys
- Keine Wallet
- Keine echten Orders

Signal:
30 Vergleiche innerhalb eines 30-Kerzen-Fensters.

Varianten:
Close > Close N candles back

N:
2, 3, 5, 10

Forward-Horizonte:
5m, 10m, 15m, 30m, 60m,
2h, 4h, 6h, 8h, 10h, 12h
"""

import csv
import statistics
from datetime import datetime, timezone


# ============================================================
# CONFIG
# ============================================================

BTC_FILE = "data/BTC_USD_5m_polymarket_period.csv"

CANDLE_WINDOW = 30
MIN_POSITIVE_CANDLES = 26

LOOKBACKS = [2, 3, 5, 10]

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
    "10h": 120,
    "12h": 144,
}

# Kosten pro Seite
FEE = 0.001
SLIPPAGE = 0.0005

# Insgesamt:
# Entry = 0.15 %
# Exit  = 0.15 %
# Roundtrip = 0.30 %


# ============================================================
# TIME
# ============================================================

def parse_timestamp(value):
    value = str(value).strip()

    try:
        numeric = float(value)

        # Unix seconds
        if numeric > 10_000_000_000:
            numeric /= 1000.0

        return datetime.fromtimestamp(
            numeric,
            tz=timezone.utc
        )

    except Exception:
        pass

    value = value.replace("Z", "+00:00")

    dt = datetime.fromisoformat(value)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def format_time(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


# ============================================================
# LOAD BTC DATA
# ============================================================

def load_btc_data(path):

    candles = []

    with open(path, "r", encoding="utf-8") as f:

        reader = csv.DictReader(f)

        for row in reader:

            try:
                timestamp_raw = (
                    row.get("timestamp")
                    or row.get("time")
                    or row.get("datetime")
                    or row.get("start")
                )

                open_price = float(row["open"])
                close_price = float(row["close"])

                timestamp = parse_timestamp(timestamp_raw)

                candles.append({
                    "timestamp": timestamp,
                    "open": open_price,
                    "close": close_price,
                })

            except Exception:
                continue

    candles.sort(key=lambda x: x["timestamp"])

    # Duplikate entfernen
    unique = {}

    for candle in candles:
        unique[candle["timestamp"]] = candle

    candles = [
        unique[key]
        for key in sorted(unique)
    ]

    return candles


# ============================================================
# SIGNAL
# ============================================================

def count_positive(candles, end_index, lookback):

    """
    Zählt exakt 30 Vergleiche:

    close[i] > close[i-lookback]

    für i innerhalb des 30-Kerzen-Fensters.
    """

    start_index = end_index - CANDLE_WINDOW + 1

    positive = 0

    for i in range(start_index, end_index + 1):

        if i - lookback < 0:
            return None

        if candles[i]["close"] > candles[i - lookback]["close"]:
            positive += 1

    return positive


def find_signals(candles, lookback):

    signals = []

    previous_active = False

    # Wir benötigen:
    # 30 Kerzen
    # + lookback Vorgänger
    first_index = CANDLE_WINDOW - 1 + lookback

    for i in range(first_index, len(candles)):

        positive = count_positive(
            candles,
            i,
            lookback
        )

        if positive is None:
            continue

        active = positive >= MIN_POSITIVE_CANDLES

        # Nur Aktivierungssignal:
        # inactive -> active
        if active and not previous_active:

            signals.append({
                "index": i,
                "timestamp": candles[i]["timestamp"],
                "positive": positive,
                "ratio": positive / CANDLE_WINDOW,
            })

        previous_active = active

    return signals


# ============================================================
# FORWARD RETURN
# ============================================================

def calculate_forward_return(
    candles,
    signal,
    horizon_bars
):

    signal_index = signal["index"]

    entry_index = signal_index + 1
    exit_index = entry_index + horizon_bars

    if exit_index >= len(candles):
        return None

    entry_price = candles[entry_index]["open"]
    exit_price = candles[exit_index]["close"]

    if entry_price <= 0:
        return None

    gross = (
        (exit_price / entry_price) - 1.0
    )

    # Entry-Kosten
    entry_cost = FEE + SLIPPAGE

    # Exit-Kosten
    exit_cost = FEE + SLIPPAGE

    net = (
        (1.0 + gross)
        * (1.0 - entry_cost)
        * (1.0 - exit_cost)
        - 1.0
    )

    return {
        "signal_time": signal["timestamp"],
        "entry_time": candles[entry_index]["timestamp"],
        "exit_time": candles[exit_index]["timestamp"],
        "entry_price": entry_price,
        "exit_price": exit_price,
        "gross": gross,
        "net": net,
    }


# ============================================================
# STATISTICS
# ============================================================

def calculate_statistics(returns):

    if not returns:
        return None

    gross = [
        r["gross"]
        for r in returns
    ]

    net = [
        r["net"]
        for r in returns
    ]

    wins = [
        value
        for value in net
        if value > 0
    ]

    losses = [
        value
        for value in net
        if value < 0
    ]

    winrate = (
        len(wins) / len(net)
        if net
        else 0.0
    )

    positive_sum = sum(wins)
    negative_sum = abs(sum(losses))

    if negative_sum > 0:

        profit_factor = (
            positive_sum /
            negative_sum
        )

    elif positive_sum > 0:

        profit_factor = float("inf")

    else:

        profit_factor = 0.0

    return {
        "n": len(net),
        "avg_gross": statistics.mean(gross),
        "avg_net": statistics.mean(net),
        "median_net": statistics.median(net),
        "winrate": winrate,
        "best": max(net),
        "worst": min(net),
        "profit_factor": profit_factor,
    }


# ============================================================
# MAIN ANALYSIS
# ============================================================

def run_analysis():

    print("=" * 68)
    print("POLYMARKET BTC FORWARD ANALYSIS")
    print("VERSION 0.2.2")
    print("=" * 68)

    print()
    print("PAPER ANALYSIS ONLY")
    print("NO API KEYS")
    print("NO WALLET")
    print("NO REAL ORDERS")
    print()

    print("CONFIG")
    print("-" * 68)
    print(f"BTC file:             {BTC_FILE}")
    print(f"Candle window:        {CANDLE_WINDOW}")
    print(f"Minimum positive:     {MIN_POSITIVE_CANDLES}/30")
    print(f"Lookbacks:            {LOOKBACKS}")
    print(f"Fee per side:         {FEE:.2%}")
    print(f"Slippage per side:    {SLIPPAGE:.2%}")
    print(f"Roundtrip costs:      {(2 * (FEE + SLIPPAGE)):.2%}")

    print()
    print("HORIZONS")
    print("-" * 68)

    for name, bars in HORIZONS.items():
        print(
            f"{name:>5} = {bars:>3} BTC 5m candles"
        )

    print()

    # ========================================================
    # LOAD
    # ========================================================

    candles = load_btc_data(BTC_FILE)

    print("BTC DATA")
    print("-" * 68)
    print(f"Candles:              {len(candles):,}")

    if candles:

        print(
            f"Start:                "
            f"{format_time(candles[0]['timestamp'])}"
        )

        print(
            f"End:                  "
            f"{format_time(candles[-1]['timestamp'])}"
        )

    print()

    # ========================================================
    # ANALYSIS
    # ========================================================

    all_results = {}

    for lookback in LOOKBACKS:

        print()
        print("=" * 68)
        print(
            f"CLOSE > CLOSE {lookback}"
        )
        print("=" * 68)

        signals = find_signals(
            candles,
            lookback
        )

        print()
        print(
            f"Activation signals:  {len(signals)}"
        )

        all_results[lookback] = {}

        for horizon_name, horizon_bars in HORIZONS.items():

            returns = []

            for signal in signals:

                result = calculate_forward_return(
                    candles,
                    signal,
                    horizon_bars
                )

                if result is not None:
                    returns.append(result)

            stats = calculate_statistics(
                returns
            )

            all_results[lookback][horizon_name] = {
                "signals": signals,
                "returns": returns,
                "stats": stats,
            }

            print()

            if stats is None:

                print(
                    f"{horizon_name:>5}: "
                    f"keine ausreichenden Daten"
                )

                continue

            pf = stats["profit_factor"]

            if pf == float("inf"):
                pf_text = "INF"
            else:
                pf_text = f"{pf:.2f}"

            print(
                f"{horizon_name:>5} | "
                f"N={stats['n']:>4} | "
                f"Avg Net={stats['avg_net']:+.3%} | "
                f"Median={stats['median_net']:+.3%} | "
                f"Winrate={stats['winrate']:.2%} | "
                f"Best={stats['best']:+.3%} | "
                f"Worst={stats['worst']:+.3%} | "
                f"PF={pf_text}"
            )

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print()
    print("=" * 68)
    print("SUMMARY")
    print("=" * 68)

    print()

    header = (
        f"{'Lookback':<12}"
        f"{'N':>6}"
        f"{'5m':>10}"
        f"{'15m':>10}"
        f"{'30m':>10}"
        f"{'60m':>10}"
        f"{'2h':>10}"
        f"{'4h':>10}"
        f"{'6h':>10}"
        f"{'8h':>10}"
        f"{'10h':>10}"
        f"{'12h':>10}"
    )

    print(header)
    print("-" * len(header))

    summary_horizons = [
        "5m",
        "15m",
        "30m",
        "60m",
        "2h",
        "4h",
        "6h",
        "8h",
        "10h",
        "12h",
    ]

    for lookback in LOOKBACKS:

        row = f"Close {lookback:<5}"

        base_stats = (
            all_results[lookback]["5m"]["stats"]
        )

        if base_stats:
            row += f"{base_stats['n']:>6}"
        else:
            row += f"{0:>6}"

        for horizon in summary_horizons:

            stats = (
                all_results[lookback][horizon]["stats"]
            )

            if stats is None:

                row += f"{'n/a':>10}"

            else:

                row += (
                    f"{stats['avg_net']:+.2%}"
                    .rjust(10)
                )

        print(row)

    # ========================================================
    # SIGNAL DETAILS
    # ========================================================

    print()
    print()
    print("=" * 68)
    print("SIGNAL DETAILS")
    print("=" * 68)

    for lookback in LOOKBACKS:

        signals = (
            all_results[lookback]["5m"]["signals"]
        )

        print()
        print(
            f"Close > Close {lookback}: "
            f"{len(signals)} Aktivierungen"
        )

        for signal in signals:

            print(
                f"  "
                f"{format_time(signal['timestamp'])} | "
                f"{signal['positive']}/30 "
                f"({signal['ratio']:.2%})"
            )

    # ========================================================
    # DATA SUFFICIENCY
    # ========================================================

    print()
    print()
    print("=" * 68)
    print("DATA SUFFICIENCY")
    print("=" * 68)

    for lookback in LOOKBACKS:

        signals = (
            all_results[lookback]["5m"]["signals"]
        )

        print()

        print(
            f"Close > Close {lookback}: "
            f"{len(signals)} signals"
        )

        for horizon in HORIZONS:

            stats = (
                all_results[lookback][horizon]["stats"]
            )

            if stats:

                print(
                    f"  {horizon:>5}: "
                    f"{stats['n']} verwertbare Signale"
                )

            else:

                print(
                    f"  {horizon:>5}: "
                    f"keine verwertbaren Signale"
                )

    print()
    print("=" * 68)
    print("ANALYSIS COMPLETE")
    print("=" * 68)
    print()
    print("Wichtig:")
    print("- Die Forward-Werte sind Event-Study-Werte.")
    print("- Signale können zeitlich überlappen.")
    print("- Sie sind NICHT automatisch Portfolio-Renditen.")
    print("- 26/30 bleibt die getestete Hypothese.")
    print("- Keine Variante wird hier als Gewinner bewertet.")
    print("- Keine Live-Trades wurden ausgeführt.")


# ============================================================
# SELF TEST
# ============================================================

def self_test():

    print()
    print("SELF TEST")
    print("-" * 68)

    assert len(HORIZONS) == 11
    assert HORIZONS["10h"] == 120
    assert HORIZONS["12h"] == 144

    assert MIN_POSITIVE_CANDLES == 26
    assert CANDLE_WINDOW == 30

    print("PASS: 10h = 120 Kerzen")
    print("PASS: 12h = 144 Kerzen")
    print("PASS: 26/30 threshold")
    print("PASS: 30-candle window")
    print("PASS: 11 horizons")
    print("PASS: Paper analysis only")


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    self_test()
    run_analysis()
