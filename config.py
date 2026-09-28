"""
30-Kerzen BTC Bot
Version 0.1.0

V1:
- BTC
- 5-Minuten-Kerzen
- 30-Kerzen-Fenster
- Aktivierung ab 26 positiven Kerzen
- Positive Kerze = Close > Open
- Paper Trading only
"""

PROJECT_NAME = "30-Kerzen BTC Bot"
VERSION = "0.1.0"


# ============================================================
# MARKET
# ============================================================

SYMBOL = "BTC/USDT"

TIMEFRAME = "5m"

# Coinbase public market-data product
COINBASE_PRODUCT_ID = "BTC-USD"

# 5 Minuten = 300 Sekunden
CANDLE_SECONDS = 300


# ============================================================
# 30-KERZEN-TEST
# ============================================================

CANDLE_WINDOW = 30

MIN_POSITIVE_CANDLES = 26

# 26 / 30 = 86.67 %
MIN_POSITIVE_RATIO = MIN_POSITIVE_CANDLES / CANDLE_WINDOW


# ============================================================
# KERZEN-KLASSIFIZIERUNG
# ============================================================

# V1:
#
# Eine Kerze gilt als positiv, wenn:
#
#     Close > Open
#
# Andernfalls gilt sie als nicht positiv.

POSITIVE_CANDLE_RULE = "CLOSE_GT_OPEN"


# ============================================================
# PAPER TRADING
# ============================================================

PAPER_TRADING = True

LIVE_TRADING = False

STARTING_CAPITAL = 100.00


# ============================================================
# RISIKO
# ============================================================

# Kelly wird erst in einer späteren Version eingebaut.
# Zunächst testen wir ausschließlich das 26-von-30-Signal.

MAX_POSITION_PERCENT = 0.10

TRADING_FEE = 0.001

SLIPPAGE = 0.0005


# ============================================================
# DATEN
# ============================================================

DATA_DIR = "data"

CSV_FILE = "data/BTC_USD_5m.csv"

MAX_CANDLES_PER_REQUEST = 300


# ============================================================
# SICHERHEIT
# ============================================================

assert PAPER_TRADING is True, \
    "Paper Trading muss aktiviert sein."

assert LIVE_TRADING is False, \
    "Live Trading ist in V1 deaktiviert."

assert CANDLE_WINDOW == 30, \
    "V1 benötigt genau 30 Kerzen."

assert MIN_POSITIVE_CANDLES <= CANDLE_WINDOW

assert MIN_POSITIVE_CANDLES > 0

assert 0 < MIN_POSITIVE_RATIO <= 1.0


# ============================================================
# KONFIGURATION AUSGEBEN
# ============================================================

def print_config():
    """Gibt die aktuelle Konfiguration aus."""

    print("=" * 60)
    print(PROJECT_NAME)
    print("=" * 60)

    print(f"Version:              {VERSION}")
    print(f"Symbol:               {SYMBOL}")
    print(f"Timeframe:            {TIMEFRAME}")

    print()
    print("30-KERZEN-TEST")
    print("-" * 60)

    print(f"Kerzenfenster:        {CANDLE_WINDOW}")
    print(f"Minimum positiv:      {MIN_POSITIVE_CANDLES}")
    print(f"Benötigter Anteil:    {MIN_POSITIVE_RATIO:.2%}")
    print(f"Positive Regel:       {POSITIVE_CANDLE_RULE}")

    print()
    print("TRADING")
    print("-" * 60)

    print(f"Startkapital:         ${STARTING_CAPITAL:.2f}")
    print(f"Paper Trading:        {PAPER_TRADING}")
    print(f"Live Trading:         {LIVE_TRADING}")

    print()
    print("RISIKO")
    print("-" * 60)

    print(f"Max. Position:        {MAX_POSITION_PERCENT:.2%}")
    print(f"Trading Fee:          {TRADING_FEE:.2%}")
    print(f"Slippage:             {SLIPPAGE:.2%}")

    print("=" * 60)


if __name__ == "__main__":
    print_config()
