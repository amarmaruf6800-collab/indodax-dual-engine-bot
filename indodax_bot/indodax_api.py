"""
Indodax REST API Client with error handling, rate limiting, and health tracking.
"""

import time
import hmac
import hashlib
import urllib.parse
import logging
import requests
from typing import Dict, List, Any, Optional
from indodax_bot.config import INDODAX_BASE_URL, API_REQUEST_TIMEOUT, API_RATE_LIMIT_SLEEP, INDODAX_API_KEY, INDODAX_SECRET_KEY

logger = logging.getLogger(__name__)

class IndodaxAPIClient:
    def __init__(self, base_url: str = INDODAX_BASE_URL, api_key: str = INDODAX_API_KEY, secret_key: str = INDODAX_SECRET_KEY):
        self.base_url = base_url
        self.api_key = api_key
        self.secret_key = secret_key
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Indodax-Dual-Engine-Bot/5.3",
            "Accept": "application/json"
        })
        self.last_request_time = 0.0

        # Health metrics
        self.total_requests = 0
        self.failed_requests = 0
        self.last_latency_ms = 0.0
        self.last_error_message: Optional[str] = None

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < API_RATE_LIMIT_SLEEP:
            time.sleep(API_RATE_LIMIT_SLEEP - elapsed)
        self.last_request_time = time.time()

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, timeout: float = API_REQUEST_TIMEOUT) -> Any:
        self._rate_limit()
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        self.total_requests += 1

        try:
            resp = self.session.get(url, params=params, timeout=timeout)
            self.last_latency_ms = (time.time() - start_time) * 1000.0
            resp.raise_for_status()
            data = resp.json()
            return data
        except Exception as e:
            self.failed_requests += 1
            self.last_error_message = str(e)
            logger.debug(f"Indodax API request note on {endpoint}: {e}")
            raise e

    def get_pairs(self) -> List[Dict[str, Any]]:
        """Fetch list of all active pairs on Indodax."""
        return self._get("/api/pairs")

    def get_ticker_all(self) -> Dict[str, Any]:
        """Fetch tickers for all pairs in one call."""
        return self._get("/api/ticker_all")

    def get_depth(self, pair_id: str, timeout: float = 3.0) -> Dict[str, Any]:
        """Fetch order book depth for a pair (e.g., 'btcidr') with 3s fast timeout."""
        return self._get(f"/api/depth/{pair_id}", timeout=timeout)

    def get_trades(self, pair_id: str) -> List[Dict[str, Any]]:
        """Fetch recent market trades for a pair."""
        return self._get(f"/api/trades/{pair_id}")

    def _post_tapi(self, method_name: str, extra_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute private Indodax Trade API (tapi) call with HMAC-SHA512 signature."""
        if not self.api_key or not self.secret_key:
            return {"success": 0, "error": "API Key and Secret Key are required for private API calls"}

        self._rate_limit()
        url = f"{self.base_url}/tapi"

        payload = {
            "method": method_name,
            "timestamp": int(time.time() * 1000)
        }
        if extra_params:
            payload.update(extra_params)

        post_data = urllib.parse.urlencode(payload)
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            post_data.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()

        headers = {
            "Key": self.api_key,
            "Sign": signature,
            "Content-Type": "application/x-www-form-urlencoded"
        }

        start_time = time.time()
        self.total_requests += 1

        try:
            resp = self.session.post(url, data=post_data, headers=headers, timeout=API_REQUEST_TIMEOUT)
            self.last_latency_ms = (time.time() - start_time) * 1000.0
            resp.raise_for_status()
            data = resp.json()
            return data
        except Exception as e:
            self.failed_requests += 1
            self.last_error_message = str(e)
            logger.warning(f"Indodax Private TAPI error on {method_name}: {e}")
            return {"success": 0, "error": str(e)}

    def get_account_info(self) -> Dict[str, Any]:
        """Fetch real Indodax account info and balances via getInfo TAPI method."""
        return self._post_tapi("getInfo")

    def get_api_health(self) -> Dict[str, Any]:
        """Return API connection health metrics."""
        success_rate = 100.0 if self.total_requests == 0 else (
            ((self.total_requests - self.failed_requests) / self.total_requests) * 100.0
        )
        return {
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "success_rate_pct": round(success_rate, 2),
            "last_latency_ms": round(self.last_latency_ms, 1),
            "last_error": self.last_error_message,
            "status": "HEALTHY" if success_rate >= 95.0 else "DEGRADED"
        }
