import time
import hmac
import hashlib
import json
import urllib.parse
import requests
import logging
from abc import ABC, abstractmethod

# Set up logging
logger = logging.getLogger(__name__)

class ExchangeClient(ABC):
    """Abstract base class for all exchange clients"""
    
    def __init__(self, api_key=None, api_secret=None, base_url=None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
    
    @abstractmethod
    def get_trading_pairs(self):
        """Get available trading pairs from the exchange"""
        pass
    
    @abstractmethod
    def get_ticker(self, symbol):
        """Get ticker data for a trading pair"""
        pass
    
    @abstractmethod
    def get_order_book(self, symbol):
        """Get order book for a trading pair"""
        pass
    
    @abstractmethod
    def get_balance(self):
        """Get account balance"""
        pass
    
    @abstractmethod
    def create_order(self, symbol, side, order_type, quantity, price=None):
        """Create a new order"""
        pass
    
    @abstractmethod
    def cancel_order(self, symbol, order_id):
        """Cancel an existing order"""
        pass
    
    @abstractmethod
    def check_order_status(self, symbol, order_id):
        """Check status of an existing order"""
        pass