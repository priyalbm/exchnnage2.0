import logging
from .models import Exchange, ExchangeConfig
import importlib

logger = logging.getLogger(__name__)

def get_exchange_client(exchange_code, api_key=None, api_secret=None, base_url=None):
    """
    Factory function to create an exchange client based on exchange code
    """
    try:
        # Import the exchange client module dynamically
        exchange_code = exchange_code.upper()
        logger.debug(f"Creating exchange client for {exchange_code}")
        
        # Import the correct client class
        try:
            # Try to import from the exchange_clients module
            from .exchange_clients.pionex import PionexClient
            from .exchange_clients.binance import BinanceClient
            from .exchange_clients.kucoin import KuCoinClient
            
            # Map exchange codes to client classes
            client_map = {
                'PIONEX': PionexClient,
                'BINANCE': BinanceClient,
                'KUCOIN': KuCoinClient,
            }
            
            # Get the client class
            client_class = client_map.get(exchange_code)
            if client_class:
                logger.debug(f"Exchange client found: {client_class.__name__}")
                return client_class(api_key=api_key, api_secret=api_secret, base_url=base_url)
            else:
                logger.error(f"No client class found for exchange code: {exchange_code}")
                return None
        except (ImportError, AttributeError) as e:
            logger.error(f"Error importing exchange client: {str(e)}")
            # As a fallback, import directly from the file
            if exchange_code == 'PIONEX':
                from .exchange_clients.pionex import PionexClient
                return PionexClient(api_key=api_key, api_secret=api_secret, base_url=base_url)
            elif exchange_code == 'BINANCE':
                from .exchange_clients.binance import BinanceClient
                return BinanceClient(api_key=api_key, api_secret=api_secret, base_url=base_url)
            elif exchange_code == 'KUCOIN':
                from .exchange_clients.kucoin import KuCoinClient
                return KuCoinClient(api_key=api_key, api_secret=api_secret, base_url=base_url)
            else:
                logger.error(f"Unsupported exchange code: {exchange_code}")
                return None
                
    except Exception as e:
        logger.exception(f"Error creating exchange client: {str(e)}")
        return None

def format_price(price, decimal_places):
    """Format price with specific decimal places"""
    return round(float(price), decimal_places)

def format_quantity(quantity, decimal_places):
    """Format quantity with specific decimal places"""
    return round(float(quantity), decimal_places)

def calculate_order_quantity(per_order_volume, price, decimal_places):
    """Calculate order quantity based on volume and price"""
    if not price or float(price) == 0:
        return 0
    
    quantity = float(per_order_volume) / float(price)
    return format_quantity(quantity, decimal_places)
