from .base import BaseExchangeClient
from .pionex import PionexClient
from .binance import BinanceClient


def get_exchange_client(exchange, api_key, secret_key):
    """
    Factory function to create a client for the specified exchange.
    
    Args:
        exchange (str): The name of the exchange (pionex or binance)
        api_key (str): API key for the exchange
        secret_key (str): Secret key for the exchange
        
    Returns:
        BaseExchangeClient: An instance of the appropriate exchange client
        
    Raises:
        ValueError: If the exchange is not supported
    """
    if exchange.lower() == 'pionex':
        return PionexClient(api_key, secret_key)
    elif exchange.lower() == 'binance':
        return BinanceClient(api_key, secret_key)
    else:
        raise ValueError(f"Unsupported exchange: {exchange}")
