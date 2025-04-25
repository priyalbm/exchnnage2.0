from abc import ABC, abstractmethod


class BaseExchangeClient(ABC):
    """
    Abstract base class for exchange clients.
    All exchange clients must implement these methods.
    """
    
    def __init__(self, api_key, secret_key):
        """
        Initialize the exchange client with API keys.
        
        Args:
            api_key (str): API key for the exchange
            secret_key (str): Secret key for the exchange
        """
        self.api_key = api_key
        self.secret_key = secret_key
    
    @abstractmethod
    async def get_wallet_balance(self):
        """
        Get the wallet balance from the exchange.
        
        Returns:
            dict: A dictionary mapping currency codes to their amounts
        """
        pass
    
    @abstractmethod
    async def get_order_book(self, pair):
        """
        Get the order book for a trading pair.
        
        Args:
            pair (str): The trading pair symbol
            
        Returns:
            dict: The order book containing bids and asks
        """
        pass
    
    @abstractmethod
    async def get_24h_ticker(self, pair):
        """
        Get the 24-hour ticker data for a trading pair.
        
        Args:
            pair (str): The trading pair symbol
            
        Returns:
            dict: The 24-hour ticker data
        """
        pass
    
    @abstractmethod
    async def place_order(self, order_type, pair, volume, price):
        """
        Place an order on the exchange.
        
        Args:
            order_type (str): The type of order ('buy' or 'sell')
            pair (str): The trading pair symbol
            volume (float): The volume to trade
            price (float): The price for the order
            
        Returns:
            dict: The order details returned by the exchange
        """
        pass
    
    @abstractmethod
    async def get_pairs(self):
        """
        Get all trading pairs available on the exchange.
        
        Returns:
            list: A list of trading pair symbols
        """
        pass
