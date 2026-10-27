"""
Configuration for INDODAX UNIFIED DUAL ENGINE ADAPTIVE TRADING SYSTEM
Version: V6.1-MACO R11
"""

import os

VERSION = "V6.1-MACO R11"
MARKET_NAME = "Indodax IDR Spot"

# System Execution Flags
OPERATING_MODE = "PAPER_TRADING"  # PAPER_TRADING or BACKTEST
LIVE_TRADING_ENABLED = False     # Strictly FALSE per master spec
DCA_ENABLED = False              # Strictly FALSE per master spec
LEVERAGE_ENABLED = False         # Strictly FALSE per master spec
MARTINGALE_ENABLED = False       # Strictly FALSE per master spec

# Initial Capital
DEFAULT_PAPER_INITIAL_IDR = 5_000_000.0  # Rp 5,000,000 per V6.1 spec

# Portfolio & Unified Risk Limits (Section 7)
MAX_PLANNED_RISK_PER_TRADE = 0.005   # 0.5% equity (Rp 25,000 on Rp 5,000,000)
MAX_COMBINED_PLANNED_RISK = 0.030    # 3.0% equity aggregate open risk limit
MAX_DAILY_LOSS_PCT = 0.030           # 3.0% Start-Of-Day equity daily loss threshold

# Portfolio & Reserve Caps (Section 8)
MAX_POSITION_ALLOC_CAP_PCT = 0.40    # Max 40% initial capital per position
MAX_CONCURRENT_POSITIONS = 2         # Max 2 concurrent open positions
MIN_UNALLOCATED_RESERVE_PCT = 0.20   # Maintain min 20% initial capital reserve

# Engine A Cost-Aware Scalper Parameters (Section 4)
SCALPER_TARGET_GROSS_MIN_PCT = 0.015  # 1.5% gross target baseline
SCALPER_TARGET_GROSS_MAX_PCT = 0.030  # 3.0% gross target baseline
SCALPER_SPREAD_BASELINE_MAX = 0.0030  # 0.30% baseline spread parameter
EXPECTED_NET_REWARD_RISK_RATIO_MIN = 2.0  # Min 1:2 Reward-to-Risk Ratio (0.5)
CONSECUTIVE_LOSS_COOLDOWN_THRESHOLD = 2   # 2 consecutive losses trigger halt

# Exchange Fees & Execution
INDODAX_TAKER_FEE = 0.002            # 0.2% taker fee
INDODAX_MAKER_FEE = 0.001            # 0.1% maker fee
CONSERVATIVE_SLIPPAGE_DEFAULT = 0.0015  # 0.15% default slippage buffer
MIN_ORDER_IDR_DEFAULT = 10_000.0     # Min 10,000 IDR per Indodax spec

# API Settings
INDODAX_BASE_URL = "https://indodax.com"
API_REQUEST_TIMEOUT = 10             # seconds
API_RATE_LIMIT_SLEEP = 0.2           # seconds between calls to respect rate limits

# API Credentials (loaded securely from environment or credentials.json)
INDODAX_API_KEY = os.getenv("INDODAX_API_KEY", "")
INDODAX_SECRET_KEY = os.getenv("INDODAX_SECRET_KEY", "")

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

# Paths
STATE_FILE_PATH = "state.json"
TRADE_LOG_PATH = "trade_history.json"
BACKTEST_RESULTS_PATH = "backtest_results.json"
