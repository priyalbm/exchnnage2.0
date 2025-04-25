# helper.py
import logging
from asgiref.sync import sync_to_async
from crypto_bot.models import Order

logger = logging.getLogger(__name__)

async def handle_api_error(response, message="API Error"):
    """Process API errors from exchange clients"""
    if response.get('error'):
        error_detail = response.get('detail', 'Unknown error')
        logger.error(f"{message}: {error_detail}")
        return True, f"{message}: {error_detail}"
    return False, None

async def create_order_record(user, exchange_config, bot_config, order_data, side, order_type):
    """
    Create an order record in the database
    """
    try:
        order = Order(
            user=user,
            bot_config=bot_config,
            exchange_config=exchange_config,
            symbol=bot_config.symbol,
            order_id=order_data.get('orderId', ''),
            exchange_order_id=order_data.get('orderId', ''),
            side=side,
            order_type=order_type,
            price=float(order_data.get('price', 0)),
            amount=float(order_data.get('size', 0)),
            status='PENDING'
        )
        await sync_to_async(order.save)()
        return order
    except Exception as e:
        logger.error(f"Error creating order record: {str(e)}")
        return None