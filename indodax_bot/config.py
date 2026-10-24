"""
Configuration for INDODAX DUAL ENGINE — MULTI-ASSET & ACTIVE RESERVE DEPLOYMENT
Version: V5.3-MACO R3
"""

import os
from dataclasses import dataclass

VERSION = "V5.3-MACO R3"
MARKET_NAME = "Indodax IDR Spot"

# System Execution Flags
OPERATING_MODE = "PAPER_TRADING"  # PAPER_TRADING or BACKTEST
LIVE_TRADING_ENABLED = False     # Strictly FALSE per master spec
DCA_ENABLED = False              # Strictly FALSE per master spec
LEVERAGE_ENABLED = False         # Strictly FALSE per master spec
MARTINGALE_ENABLED = False       # Strictly FALSE per master spec

# Capital Tier Parameters
TIER_1_MIN_EQUITY = 1_000_000        # Rp 1,000,000
TIER_1_MAX_EQUITY = 30_000_000       # Rp 30,000,000
TIER_1_MAX_ENGINE_A_ALLOC = 0.40     # 40%
TIER_1_MAX_ENGINE_B_ALLOC = 0.40     # 40%
TIER_1_MAX_POSITIONS_PER_ENGINE = 1
TIER_1_MAX_TOTAL_POSITIONS = 2

TIER_2_MIN_EQUITY = 30_000_000.01     # Above Rp 30,000,000
TIER_2_MAX_EQUITY = 100_000_000      # Rp 100,000,000
TIER_2_ASSET_ALLOC_MIN = 0.05        # 5%
TIER_2_ASSET_ALLOC_MAX = 0.10        # 10%

EQUITY_HALT_THRESHOLD = 100_000_000  # Stop new entries above Rp 100M until tier configured

# Portfolio Risk Limits
MAX_PLANNED_RISK_PER_TRADE = 0.01    # 1% of current equity
MAX_COMBINED_PLANNED_RISK = 0.02     # 2% of current equity
MAX_DAILY_LOSS_PCT = 0.02            # 2% of Start-Of-Day equity
MAX_PORTFOLIO_EXPOSURE = 0.80        # 80% max exposure
MIN_CASH_RESERVE = 0.20              # 20% min cash reserve

# Exchange Fees & Execution
INDODAX_TAKER_FEE = 0.002            # 0.2% taker fee
INDODAX_MAKER_FEE = 0.001            # 0.1% maker fee
CONSERVATIVE_SLIPPAGE_DEFAULT = 0.0015  # 0.15% default slippage buffer
MIN_ORDER_IDR_DEFAULT = 10_000       # Min 10,000 IDR per Indodax spec

# API Settings
INDODAX_BASE_URL = "https://indodax.com"
API_REQUEST_TIMEOUT = 10             # seconds
API_RATE_LIMIT_SLEEP = 0.2           # seconds between calls to respect rate limits

# API Credentials (loaded securely from environment or credentials.json)
INDODAX_API_KEY = os.getenv("INDODAX_API_KEY", "")
INDODAX_SECRET_KEY = os.getenv("INDODAX_SECRET_KEY", "")

# Load from credentials.json if exists
CREDENTIALS_FILE_PATH = "credentials.json"
if os.path.exists(CREDENTIALS_FILE_PATH):
    try:
        import json
        with open(CREDENTIALS_FILE_PATH, "r") as f:
            creds = json.load(f)
            INDODAX_API_KEY = creds.get("api_key", INDODAX_API_KEY)
            INDODAX_SECRET_KEY = creds.get("secret_key", INDODAX_SECRET_KEY)
    except Exception:
        pass

# Initial Default Balance for Paper Trading
DEFAULT_PAPER_INITIAL_IDR = 10_000_000  # 10 Million IDR (Tier 1)

# Paths
STATE_FILE_PATH = "state.json"
TRADE_LOG_PATH = "trade_history.json"
BACKTEST_RESULTS_PATH = "backtest_results.json"
