"""
Trading 212 API Service
Handles HTTP Basic Authentication (Authorization: Basic <base64(key:secret)>) and direct API token auth,
account cash balance lookup, portfolio positions, and order execution across Demo and Live environments.
"""

import base64
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import requests

logger = logging.getLogger(__name__)


@dataclass
class AccountCash:
    """Represents account cash balances in Trading 212."""
    free: float
    total: float
    invested: float
    ppl: float  # Profit/Loss
    result: float


@dataclass
class Position:
    """Represents an open stock position."""
    ticker: str
    quantity: float
    average_price: float
    current_price: float
    ppl: float
    fx_ppl: Optional[float] = 0.0
    initial_fill_date: Optional[str] = None


@dataclass
class OrderResult:
    """Represents the response of a placed order."""
    success: bool
    order_id: Optional[int]
    ticker: str
    action: str
    quantity: float
    filled_quantity: float
    filled_value: float
    status: str
    raw_response: Dict[str, Any]
    error_message: Optional[str] = None


class Trading212Client:
    """
    Client for interacting with the official Trading 212 REST API.
    Supports both DEMO and LIVE trading modes.
    Encodes credentials into HTTP Basic Authentication header:
    'Authorization: Basic <base64(API_KEY:API_SECRET)>'.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_key_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        environment: str = "demo",
        timeout: int = 15
    ):
        self.api_key = (api_key or "").strip()
        self.api_key_id = (api_key_id or "").strip()
        self.secret_key = (secret_key or "").strip()
        self.api_secret = (api_secret or "").strip()
        self.environment = environment.lower().strip()
        self.timeout = timeout
        self.base_url = (
            "https://live.trading212.com/api/v0"
            if self.environment == "live"
            else "https://demo.trading212.com/api/v0"
        )

        self._session = requests.Session()
        self._session.headers.update(self._get_headers())

    def is_configured(self) -> bool:
        """Checks whether Trading 212 API credentials are configured."""
        effective_key = self.api_key or self.api_key_id
        return bool(
            effective_key
            and effective_key not in ("your_t212_api_key_here", "mock_key", "")
        )

    def _get_headers(self) -> Dict[str, str]:
        """
        Builds request headers for Trading 212 API.
        Formats HTTP Basic Auth header: 'Authorization: Basic <base64(key:secret)>'.
        Falls back to plain api_key string if secret is not supplied.
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "AutoTradingBot/1.0",
        }

        api_key = self.api_key_id or self.api_key
        secret_key = self.secret_key or self.api_secret

        if api_key and secret_key:
            credentials = f"{api_key}:{secret_key}"
            encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
            headers["Authorization"] = f"Basic {encoded_credentials}"
        elif api_key:
            headers["Authorization"] = api_key

        return headers

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Internal helper to dispatch HTTP requests with unified error handling."""
        api_key = self.api_key_id or self.api_key
        if not api_key or api_key in ("your_trading_212_api_key_here", "your_trading_212_api_key_id_here"):
            raise ValueError(
                "Trading 212 credentials are not configured. Please set T212_API_KEY (and optionally T212_SECRET_KEY) in .env."
            )

        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        logger.debug(f"Trading212 API [{self.environment.upper()}] {method} {url}")

        try:
            response = self._session.request(method, url, timeout=self.timeout, **kwargs)
            if response.status_code == 204:
                return {}

            if not response.ok:
                err_data = {}
                try:
                    err_data = response.json()
                except Exception:
                    pass
                msg = err_data.get("errorMessage") or err_data.get("message") or response.text
                logger.error(f"Trading212 API error ({response.status_code}) on {url}: {msg}")
                response.raise_for_status()

            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Trading 212 connection error: {e}")
            raise

    def get_account_cash(self) -> AccountCash:
        """
        Retrieves current account cash balances (free cash, invested, total, and profit/loss).
        """
        data = self._request("GET", "/equity/account/cash")
        return AccountCash(
            free=float(data.get("free", 0.0)),
            total=float(data.get("total", 0.0)),
            invested=float(data.get("invested", 0.0)),
            ppl=float(data.get("ppl", 0.0)),
            result=float(data.get("result", 0.0)),
        )

    def get_open_positions(self) -> List[Position]:
        """
        Retrieves all currently open positions in the equity account.
        """
        data = self._request("GET", "/equity/portfolio")
        if not isinstance(data, list):
            return []

        positions: List[Position] = []
        for item in data:
            positions.append(Position(
                ticker=item.get("ticker", ""),
                quantity=float(item.get("quantity", 0.0)),
                average_price=float(item.get("averagePrice", 0.0)),
                current_price=float(item.get("currentPrice", 0.0)),
                ppl=float(item.get("ppl", 0.0)),
                fx_ppl=float(item.get("fxPpl", 0.0)) if item.get("fxPpl") is not None else 0.0,
                initial_fill_date=item.get("initialFillDate"),
            ))
        return positions

    def get_position(self, ticker: str) -> Optional[Position]:
        """
        Retrieves specific open position for a ticker, or None if no position is open.
        """
        try:
            data = self._request("GET", f"/equity/portfolio/{ticker}")
            if not data or not isinstance(data, dict):
                return None
            return Position(
                ticker=data.get("ticker", ticker),
                quantity=float(data.get("quantity", 0.0)),
                average_price=float(data.get("averagePrice", 0.0)),
                current_price=float(data.get("currentPrice", 0.0)),
                ppl=float(data.get("ppl", 0.0)),
                fx_ppl=float(data.get("fxPpl", 0.0)) if data.get("fxPpl") is not None else 0.0,
                initial_fill_date=data.get("initialFillDate"),
            )
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return None
            raise

    def place_market_order(self, ticker: str, quantity: float) -> OrderResult:
        """
        Places a market order for a specified quantity of shares.
        Positive quantity = BUY, Negative quantity = SELL.
        """
        action = "BUY" if quantity > 0 else "SELL"
        abs_qty = abs(quantity)
        logger.info(f"Submitting Trading 212 {action} market order: {abs_qty} shares of {ticker}")

        payload = {
            "quantity": abs_qty if action == "BUY" else -abs_qty,
            "ticker": ticker
        }

        try:
            data = self._request("POST", "/equity/orders/market", json=payload)
            order_id = data.get("id") or data.get("orderId")
            status = data.get("status", "SUBMITTED")
            filled_qty = float(data.get("filledQuantity", abs_qty))
            filled_val = float(data.get("filledValue", 0.0))

            return OrderResult(
                success=True,
                order_id=order_id,
                ticker=ticker,
                action=action,
                quantity=abs_qty,
                filled_quantity=filled_qty,
                filled_value=filled_val,
                status=status,
                raw_response=data,
            )
        except Exception as e:
            logger.error(f"Failed to execute market order for {ticker}: {e}")
            return OrderResult(
                success=False,
                order_id=None,
                ticker=ticker,
                action=action,
                quantity=abs_qty,
                filled_quantity=0.0,
                filled_value=0.0,
                status="FAILED",
                raw_response={},
                error_message=str(e),
            )

    def place_value_order(self, ticker: str, value: float, current_price: Optional[float] = None) -> OrderResult:
        """
        Places an order based on cash value allocation (e.g. $25 worth of shares).
        Attempts direct value order endpoint or calculates fractional share quantity.
        """
        logger.info(f"Placing value order for {ticker}: {value:.2f} value")
        try:
            payload = {"ticker": ticker, "value": value}
            data = self._request("POST", "/equity/orders/value", json=payload)
            order_id = data.get("id") or data.get("orderId")
            return OrderResult(
                success=True,
                order_id=order_id,
                ticker=ticker,
                action="BUY",
                quantity=float(data.get("quantity", 0.0)),
                filled_quantity=float(data.get("filledQuantity", 0.0)),
                filled_value=value,
                status=data.get("status", "SUBMITTED"),
                raw_response=data,
            )
        except Exception as value_err:
            logger.debug(f"Direct value order not accepted ({value_err}). Falling back to fractional market order.")
            if current_price and current_price > 0:
                fractional_qty = round(value / current_price, 6)
                return self.place_market_order(ticker=ticker, quantity=fractional_qty)
            raise ValueError(f"Cannot calculate share quantity for value order without current price for {ticker}.")

    def get_order_status(self, order_id: int) -> Dict[str, Any]:
        """Fetches the latest status of a specific order ID."""
        return self._request("GET", f"/equity/orders/{order_id}")

    def get_instruments(self) -> List[Dict[str, Any]]:
        """
        Fetches all available tradable equity instruments from Trading 212 metadata API.
        Endpoint: GET /equity/metadata/instruments
        """
        try:
            data = self._request("GET", "/equity/metadata/instruments")
            if isinstance(data, list):
                return data
            return []
        except Exception as e:
            logger.warning(f"Could not fetch Trading 212 instruments metadata: {e}")
            return []
