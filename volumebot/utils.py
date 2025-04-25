import logging
from binance.client import Client as BinanceClient
from django.conf import settings
from django.contrib.auth import get_user_model
import ccxt
import time
User = get_user_model()

logger = logging.getLogger(__name__)




class ExchangeTradeHandler:
    def __init__(self, api_key, secret_key, exchange):
        self.api_key = api_key
        self.secret_key = secret_key
        self.exchange = exchange
        self.client = self._get_exchange_client()
        print(self.client)
    def _get_exchange_client(self):
        if self.exchange == 'BINANCE':
            return BinanceClient(self.api_key, self.secret_key)
        if self.exchange == 'PIONEX':
            print('PIONEX','PIONEX','PIONEX')
            return ccxt.pionex({
                'apiKey': self.api_key,
                'secret': self.secret_key,
            })
        raise ValueError(f"Unsupported exchange: {self.exchange}")
    
    def get_market_data(self, coin_pair):
        try:
            ticker = self.client.get_symbol_ticker(symbol=coin_pair)
            depth = self.client.get_order_book(symbol=coin_pair)
            
            return {
                'last_price': float(ticker['price']),
                'bid_price': float(depth['bids'][0][0]),
                'ask_price': float(depth['asks'][0][0])
            }
        except Exception as e:
            logger.error(f"Market data retrieval error: {str(e)}")
            raise
    
    def calculate_trade_volume(self, market_data, volume_percentage):
        # Implement volume calculation logic based on market data
        # This is a simplified example
        current_price = market_data['last_price']
        account_balance = self._get_account_balance()
        
        trade_volume = (account_balance * volume_percentage / 100) / current_price
        return trade_volume
    
    def execute_trade(self, coin_pair, volume):
        try:
            # Determine trade direction (buy/sell)
            trade_type = 'BUY' if self._should_buy() else 'SELL'
            
            if trade_type == 'BUY':
                order = self.client.create_order(
                    symbol=coin_pair,
                    side=self.client.SIDE_BUY,
                    type=self.client.ORDER_TYPE_MARKET,
                    quantity=volume
                )
            else:
                order = self.client.create_order(
                    symbol=coin_pair,
                    side=self.client.SIDE_SELL,
                    type=self.client.ORDER_TYPE_MARKET,
                    quantity=volume
                )
            
            return {
                'type': trade_type,
                'amount': volume,
                'price': float(order['fills'][0]['price']),
                'status': 'SUCCESS'
            }
        except Exception as e:
            logger.error(f"Trade execution error: {str(e)}")
            return {
                'type': trade_type,
                'amount': volume,
                'price': 0,
                'status': 'FAILED',
                'error': str(e)
            }
    
    def _should_buy(self):
        # Implement your trading strategy logic here
        # This is a placeholder and should be replaced with actual trading strategy
        return True
    
import requests
import hmac
import hashlib
import time
import logging
from typing import Dict, Any
import urllib.parse

class PionexTradeHandler:
    BASE_URL = 'https://api.pionex.com'
    
    def __init__(self, api_key, secret_key):
        """
        Initialize Pionex trade handler
        
        Args:
            api_key (str): Pionex API key
            secret_key (str): Pionex secret key
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.logger = logging.getLogger(__name__)
    
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """
        Generate HMAC SHA256 signature for Pionex API requests
        
        Args:
            params (dict): Request parameters
        
        Returns:
            str: Generated signature
        """
        # Sort parameters alphabetically
        sorted_params = sorted(params.items(), key=lambda x: x[0])
        
        # Convert to query string
        query_string = urllib.parse.urlencode(sorted_params)
        
        # Generate signature
        signature = hmac.new(
            self.secret_key.encode('utf-8'), 
            query_string.encode('utf-8'), 
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _make_request(self, endpoint: str, method: str = 'GET', params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Make authenticated request to Pionex API
        
        Args:
            endpoint (str): API endpoint
            method (str): HTTP method
            params (dict): Request parameters
        
        Returns:
            dict: API response
        """
        if params is None:
            params = {}
        
        # Add timestamp and API key
        params['timestamp'] = int(time.time() * 1000)
        params['api_key'] = self.api_key
        
        # Generate signature
        params['signature'] = self._generate_signature(params)
        
        # Construct full URL
        full_url = f"{self.BASE_URL}{endpoint}"
        try:
            if method == 'GET':
                response = requests.get(full_url, params=params)
            elif method == 'POST':
                response = requests.post(full_url, json=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Raise exception for bad responses
            response.raise_for_status()
            
            return response.json()
        
        except requests.RequestException as e:
            self.logger.error(f"API Request Error: {str(e)}")
            raise
    
    def get_market_data(self, symbol: str) -> Dict[str, float]:
        """
        Retrieve market data for a specific symbol
        
        Args:
            symbol (str): Trading pair symbol (e.g., 'MNTC_USDT')
        
        Returns:
            dict: Market data including last price, bid, and ask prices
        """
        try:
            # Endpoint for ticker data
            endpoint = '/api/v1/common/symbols'
            # endpoint = '/api/v1/market/ticker'
            params = {'symbol': symbol}
            # params = {'symbol': symbol}
            
            response = self._make_request(endpoint, params=params)
            symbol_data = next((item for item in response["data"]["symbols"] if item["symbol"] == symbol), None)

            print(symbol_data)
            return {
                'last_price': float(symbol_data['last']),
                'bid_price': float(symbol_data['buyCeiling']),
                'ask_price': float(symbol_data['sellFloor'])
            }
        except Exception as e:
            self.logger.error(f"Market data retrieval error for {symbol}: {str(e)}")
            raise
    
    def get_account_balance(self) -> Dict[str, float]:
        """
        Retrieve account balances
        
        Returns:
            dict: Account balances for different cryptocurrencies
        """
        try:
            # Endpoint for account balances
            endpoint = '/api/v1/account'
            
            response = self._make_request(endpoint)
            
            # Process and return balances
            balances = {}
            for balance in response['data']['balances']:
                balances[balance['asset']] = {
                    'total': float(balance['total']),
                    'available': float(balance['available'])
                }
            print(balances)
            return balances
        except Exception as e:
            self.logger.error(f"Balance retrieval error: {str(e)}")
            raise
    
    def calculate_trade_volume(self, market_data: Dict[str, float], 
                                balance_currency: str = 'USDT', 
                                volume_percentage: float = 10) -> float:
        """
        Calculate trade volume based on account balance and market price
        
        Args:
            market_data (dict): Current market data
            balance_currency (str): Currency to use for balance calculation
            volume_percentage (float): Percentage of balance to trade
        
        Returns:
            float: Calculated trade volume
        """
        try:
            # Get account balances
            balances = self.get_account_balance()
            print(balances,"balancesbalancesbalancesbalancesbalances")
            # Get current balance for specified currency
            current_balance = balances.get(balance_currency, {}).get('available', 0)
            current_price = market_data['last_price']
            
            # Calculate trade volume
            trade_volume = (current_balance * volume_percentage / 100) / current_price
            
            return trade_volume
        except Exception as e:
            self.logger.error(f"Volume calculation error: {str(e)}")
            raise
    
    def execute_trade(self, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
        """
        Execute a market order
        
        Args:
            symbol (str): Trading pair symbol
            side (str): 'BUY' or 'SELL'
            quantity (float): Amount to trade
        
        Returns:
            dict: Trade execution result
        """
        try:
            # Endpoint for placing orders
            endpoint = '/api/v1/order'
            
            # Prepare order parameters
            params = {
                'symbol': symbol,
                'side': side.upper(),
                'type': 'MARKET',
                'quantity': quantity
            }
            
            # Execute order
            response = self._make_request(endpoint, method='POST', params=params)
            
            return {
                'status': 'SUCCESS',
                'order_id': response['data']['orderId'],
                'executed_quantity': float(response['data']['executedQty']),
                'executed_price': float(response['data']['price'])
            }
        except Exception as e:
            self.logger.error(f"Trade execution error: {str(e)}")
            return {
                'status': 'FAILED',
                'error': str(e)
            }
    
    def trade_mntc_usdt(self, volume_percentage: float = 10) -> Dict[str, Any]:
        """
        Comprehensive trading method for MNTC/USDT
        
        Args:
            volume_percentage (float): Percentage of balance to trade
        
        Returns:
            dict: Trading result
        """
        try:
            # Retrieve market data
            market_data = self.get_market_data('MNTC_USDT')
            print("--------------------------------------------------------")
            # Calculate trade volume
            trade_volume = self.calculate_trade_volume(market_data, volume_percentage=volume_percentage)
            print(trade_volume,"trade_volume")
            print("--------------------------------------------------------")
            # Determine trade side (you can implement more complex logic here)
            trade_side = 'BUY'  # Simple default, replace with your strategy
            
            # Execute trade
            trade_result = self.execute_trade('MNTC_USDT', trade_side, trade_volume)
            print(trade_result,"trade_result")
            print("--------------------------------------------------------")
            return trade_result
        except Exception as e:
            self.logger.error(f"MNTC/USDT trade failed: {str(e)}")
            return {'status': 'FAILED', 'error': str(e)}
