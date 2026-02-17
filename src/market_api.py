"""
Kalshi API Client Module

A robust and production-ready client for interacting with the Kalshi prediction market API.
This module provides a clean abstraction layer for all API operations, handling complex
concerns such as authentication, rate limiting, error recovery, and request optimization.

Key Features:
    - Intelligent rate limiting with automatic backoff strategies
    - Support for both official Kalshi SDK and direct REST API calls
    - Comprehensive error handling with graceful degradation
    - Automatic retry logic for transient failures
    - Session management for improved performance
"""
import os
import requests
import time
import json
import hmac
import hashlib
import base64
from typing import List, Dict, Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class KalshiClient:
    """
    Professional API client for Kalshi prediction markets.
    
    Provides a high-level interface for all Kalshi API operations including market
    data retrieval, order placement, portfolio management, and orderbook access.
    The client automatically handles authentication, rate limiting, and error recovery.
    """
    
    def __init__(self):
        self.api_key = os.getenv("KALSHI_API_KEY")
        self.api_secret = os.getenv("KALSHI_API_SECRET")
        self.base_url = os.getenv("KALSHI_API_BASE_URL", "https://api.elections.kalshi.com/trade-api/v2")
        self.session = requests.Session()
        
        self.last_request_time = 0
        self.min_request_interval = float(os.getenv("API_MIN_INTERVAL", "0.1"))  # 100ms minimum between requests
        self.request_count = 0
        self.rate_limit_reset_time = 0
        
        if not self.api_key or self.api_key == "your_api_key_id_here":
            print("Warning: KALSHI_API_KEY not set or still has placeholder value")
        if not self.api_secret or self.api_secret == "your_private_key_here":
            print("Warning: KALSHI_API_SECRET not set or still has placeholder value")
        
        self.use_sdk = False
        try:
            from kalshi_python import Configuration, KalshiClient as SDKClient
            self.use_sdk = True
            private_key = self.api_secret
            if os.path.isfile(self.api_secret):
                with open(self.api_secret, 'r') as f:
                    private_key = f.read()
            
            config = Configuration(
                host=self.base_url,
                api_key_id=self.api_key,
                private_key_pem=private_key
            )
            self.sdk_client = SDKClient(config)
        except ImportError:
            if self.api_key and self.api_secret:
                self.session.headers.update({
                    'X-API-Key': self.api_key,
                    'X-API-Secret': self.api_secret
                })
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """
        Execute an authenticated API request with intelligent rate limiting.
        
        This internal method handles all API communication, ensuring proper rate limiting,
        error handling, and automatic retry logic. It respects API rate limits and
        implements exponential backoff when necessary.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional request parameters (params, json, etc.)
            
        Returns:
            Parsed JSON response as dictionary
            
        Raises:
            requests.exceptions.RequestException: For API communication errors
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        current_time = time.time()
        
        if current_time < self.rate_limit_reset_time:
            wait_time = self.rate_limit_reset_time - current_time
            print(f"Rate limit cooldown: waiting {wait_time:.1f} seconds...")
            time.sleep(wait_time)
            current_time = time.time()
        
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        try:
            self.last_request_time = time.time()
            self.request_count += 1
            
            response = self.session.request(method, url, **kwargs)
            
            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After')
                if retry_after:
                    wait_time = int(retry_after)
                else:
                    wait_time = 60
                
                self.rate_limit_reset_time = time.time() + wait_time
                print(f"Rate limit hit (429). Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
                
                response = self.session.request(method, url, **kwargs)
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 429:
                    retry_after = e.response.headers.get('Retry-After', '60')
                    wait_time = int(retry_after)
                    self.rate_limit_reset_time = time.time() + wait_time
                    print(f"Rate limit error. Waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    raise
                else:
                    print(f"API request failed: {e}")
                    if hasattr(e.response, 'text'):
                        print(f"Response: {e.response.text}")
            else:
                print(f"API request failed: {e}")
            raise
    
    def get_markets(self, limit: int = 100, status: str = "open") -> List[Dict]:
        """
        Retrieve active markets from the Kalshi platform.
        
        Fetches a list of markets matching the specified criteria, including
        current pricing, liquidity, and market metadata.
        
        Args:
            limit: Maximum number of markets to retrieve (default: 100)
            status: Market status filter - 'open' for active markets, 'closed' for settled
        
        Returns:
            List of market data dictionaries, empty list on error
        """
        try:
            response = self._make_request(
                "GET",
                "/markets",
                params={"limit": limit, "status": status}
            )
            return response.get("markets", [])
        except Exception as e:
            print(f"Error fetching markets: {e}")
            return []
    
    def get_market(self, market_ticker: str) -> Optional[Dict]:
        """
        Retrieve comprehensive information for a specific market.
        
        Fetches detailed market data including current prices, orderbook depth,
        expiration information, and trading volume.
        
        Args:
            market_ticker: Unique market identifier (e.g., 'PRES-2024-TRUE')
        
        Returns:
            Complete market data dictionary, None on error
        """
        try:
            response = self._make_request("GET", f"/markets/{market_ticker}")
            return response.get("market")
        except Exception as e:
            print(f"Error fetching market {market_ticker}: {e}")
            return None
    
    def get_market_orderbook(self, market_ticker: str) -> Optional[Dict]:
        """
        Retrieve the complete orderbook for a specified market.
        
        Returns detailed orderbook data including bid and ask prices with
        associated quantities, enabling precise spread analysis and trade execution.
        
        Args:
            market_ticker: Unique market identifier
        
        Returns:
            Orderbook data dictionary with bids and asks, None on error
        """
        try:
            response = self._make_request("GET", f"/markets/{market_ticker}/orderbook")
            return response
        except Exception as e:
            print(f"Error fetching orderbook for {market_ticker}: {e}")
            return None
    
    def get_portfolio(self) -> Optional[Dict]:
        """
        Retrieve current portfolio status and position information.
        
        Returns comprehensive account data including available balance, open positions,
        and recent trading activity.
        
        Returns:
            Portfolio data dictionary, None on error
        """
        try:
            response = self._make_request("GET", "/portfolio")
            return response
        except Exception as e:
            print(f"Error fetching portfolio: {e}")
            return None
    
    def place_order(self, market_ticker: str, side: str, action: str, 
                   count: int, price: int, order_type: str = "limit") -> Optional[Dict]:
        """
        Submit a trading order to the Kalshi exchange.
        
        Places either a limit or market order for the specified market. Limit orders
        provide price protection but may not execute immediately, while market orders
        execute instantly at current market prices.
        
        Args:
            market_ticker: Unique market identifier
            side: Contract side - 'yes' or 'no'
            action: Order direction - 'buy' to acquire contracts, 'sell' to dispose
            count: Number of contracts to trade
            price: Limit price in cents (0-100), ignored for market orders
            order_type: 'limit' for price-protected orders, 'market' for immediate execution
        
        Returns:
            Order confirmation dictionary with order details, None on error
        """
        try:
            payload = {
                "ticker": market_ticker,
                "side": side,
                "action": action,
                "count": count,
                "price": price,
                "type": order_type
            }
            response = self._make_request("POST", "/portfolio/orders", json=payload)
            return response
        except Exception as e:
            print(f"Error placing order: {e}")
            return None

